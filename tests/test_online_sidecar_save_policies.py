# -*- coding: utf-8 -*-
"""Saving online segments beside the video, through every existing-file policy.

The save module had no test that wrote a file, and a missing import made every Merge and
Update save raise NameError, which stopped segments loading for that video.
"""

import unittest
from unittest.mock import patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import service_online_sidecar_save as save  # noqa: E402
from segment_item import SegmentItem  # noqa: E402

VIDEO = "/media/Show/Show S01E01.mkv"
XML_PATH = "/media/Show/Show S01E01-chapters.xml"
EDL_PATH = "/media/Show/Show S01E01.edl"

EXISTING_XML = (
    '<?xml version="1.0"?><Chapters><EditionEntry>'
    "<ChapterAtom><ChapterTimeStart>00:00:10.000</ChapterTimeStart>"
    "<ChapterTimeEnd>00:01:00.000</ChapterTimeEnd>"
    "<ChapterDisplay><ChapterString>Intro</ChapterString></ChapterDisplay></ChapterAtom>"
    "</EditionEntry></Chapters>"
)

WRITING_POLICIES = (
    save._SAVE_CHAPTERS_MERGE,
    save._SAVE_CHAPTERS_UPDATE_SILENT,
    save._SAVE_CHAPTERS_UPDATE_ALL_SILENT,
    save._SAVE_CHAPTERS_OVERWRITE_SILENT,
)
# Update only retimes what the file already has; every other writing policy also adds the credits.
RETIME_ONLY = (save._SAVE_CHAPTERS_UPDATE_SILENT, save._SAVE_CHAPTERS_UPDATE_ASK)
ASKING_POLICIES = (
    save._SAVE_CHAPTERS_UPDATE_ASK,
    save._SAVE_CHAPTERS_UPDATE_ALL_ASK,
    save._SAVE_CHAPTERS_OVERWRITE_ASK,
)


def _check_written(test, policy, items):
    labels = [s.segment_type_label for s in items]
    if policy in RETIME_ONLY:
        test.assertEqual(labels, ["intro"], policy)
        test.assertEqual((items[0].start_seconds, items[0].end_seconds), (12.0, 62.0), policy)
    else:
        test.assertIn("credits", labels, policy)


def _existing():
    return [SegmentItem(10.0, 60.0, "intro", source="xml")]


def _online():
    # The intro differs from the file and a credits segment is new, so every policy has work.
    return [
        SegmentItem(12.0, 62.0, "intro", source="theintrodb"),
        SegmentItem(1300.0, 1380.0, "credits", source="theintrodb"),
    ]


class _Addon:
    def getLocalizedString(self, _string_id):
        return "text"


class ChapterXmlPolicyTests(unittest.TestCase):
    def setUp(self):
        self.written = []
        self.asked = []
        self.answer = True
        stack = [
            patch.object(save, "_find_existing_sidecar_chapter_xml_path", lambda _v: XML_PATH),
            patch.object(save, "safe_file_read", lambda _p: EXISTING_XML),
            patch.object(
                save, "_write_chapters_xml_to_path", lambda path, items: self.written.append((path, list(items)))
            ),
            patch.object(save, "_backup_sidecar_file", lambda *_a: None),
            patch.object(save, "addon_get_bool", lambda _a, _k, default=False: default),
            patch.object(save, "_build_sidecar_ask_detail", lambda *_a, **_k: ""),
            patch.object(save, "_sidecar_overwrite_yesno", self._yesno),
            patch.object(save, "log"),
            patch.object(save, "_log_sidecar_detail"),
        ]
        for p in stack:
            p.start()
            self.addCleanup(p.stop)

    def _yesno(self, heading, message):
        self.asked.append(heading)
        return self.answer

    def run_policy(self, policy, segments=None):
        save._maybe_save_online_segments_chapters_xml(
            VIDEO, _online() if segments is None else segments, policy, _Addon()
        )

    def test_every_writing_policy_writes_without_an_error(self):
        for policy in WRITING_POLICIES:
            with self.subTest(policy=policy):
                self.written.clear()
                self.run_policy(policy)
                self.assertEqual(len(self.written), 1, policy)
                path, items = self.written[0]
                self.assertEqual(path, XML_PATH)
                _check_written(self, policy, items)

    def test_merge_keeps_the_intro_already_in_the_file(self):
        self.run_policy(save._SAVE_CHAPTERS_MERGE)
        intro = [s for s in self.written[0][1] if s.segment_type_label == "intro"]
        self.assertEqual([(s.start_seconds, s.end_seconds) for s in intro], [(10.0, 60.0)])

    def test_merge_with_nothing_new_writes_nothing(self):
        self.run_policy(save._SAVE_CHAPTERS_MERGE, segments=_existing())
        self.assertEqual(self.written, [])

    def test_update_with_nothing_new_writes_nothing(self):
        for policy in (save._SAVE_CHAPTERS_UPDATE_SILENT, save._SAVE_CHAPTERS_UPDATE_ALL_SILENT):
            with self.subTest(policy=policy):
                self.run_policy(policy, segments=_existing())
                self.assertEqual(self.written, [])

    def test_asking_policies_write_after_yes_and_not_after_no(self):
        for policy in ASKING_POLICIES:
            with self.subTest(policy=policy):
                self.written.clear()
                self.asked.clear()
                self.answer = True
                self.run_policy(policy)
                self.assertEqual(len(self.asked), 1)
                self.assertEqual(len(self.written), 1)
                self.written.clear()
                self.answer = False
                self.run_policy(policy)
                self.assertEqual(self.written, [])

    def test_skip_if_exists_leaves_the_file_alone(self):
        self.run_policy(save._SAVE_CHAPTERS_SKIP_IF_EXISTS)
        self.assertEqual(self.written, [])


class EdlPolicyTests(unittest.TestCase):
    def setUp(self):
        self.saved = []
        self.asked = []
        stack = [
            patch.object(save, "_edl_paths_to_try", lambda _v: [EDL_PATH]),
            patch.object(save.xbmcvfs, "exists", lambda p: p == EDL_PATH),
            patch.object(save, "parse_edl", lambda _v, update_monitor=False: _existing()),
            patch.object(save, "safe_file_read", lambda _p: "10.0\t60.0\t5\n"),
            patch.object(save, "save_edl", lambda video, items: self.saved.append(list(items)) or True),
            patch.object(save, "_edl_file_triples_match_segments", lambda *_a: False),
            patch.object(save, "_backup_sidecar_file", lambda *_a: None),
            patch.object(save, "addon_get_bool", lambda _a, _k, default=False: default),
            patch.object(save, "_build_sidecar_ask_detail", lambda *_a, **_k: ""),
            patch.object(save, "_sidecar_overwrite_yesno", lambda h, m: self.asked.append(h) or True),
            patch.object(save, "log"),
            patch.object(save, "_log_sidecar_detail"),
        ]
        for p in stack:
            p.start()
            self.addCleanup(p.stop)

    def run_policy(self, policy, segments=None):
        save._maybe_save_online_segments_edl(
            VIDEO, _online() if segments is None else segments, policy, _Addon()
        )

    def test_every_writing_policy_writes_without_an_error(self):
        for policy in WRITING_POLICIES + ASKING_POLICIES:
            with self.subTest(policy=policy):
                self.saved.clear()
                self.run_policy(policy)
                self.assertEqual(len(self.saved), 1, policy)
                _check_written(self, policy, self.saved[0])

    def test_merge_and_update_with_nothing_new_write_nothing(self):
        for policy in (
            save._SAVE_CHAPTERS_MERGE,
            save._SAVE_CHAPTERS_UPDATE_SILENT,
            save._SAVE_CHAPTERS_UPDATE_ALL_SILENT,
        ):
            with self.subTest(policy=policy):
                self.saved.clear()
                self.run_policy(policy, segments=_existing())
                self.assertEqual(self.saved, [])


if __name__ == "__main__":
    unittest.main()
