# -*- coding: utf-8 -*-
"""Writing online segments as chapters.xml, backups, and the "already the same" checks.

The "unchanged" checks decide whether Skippy writes (or asks) at all, so a wrong answer either
rewrites a file every time a video plays or never saves new online data.
"""

import os
import unittest
from unittest.mock import patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import segment_editor_parser  # noqa: E402
import service_online_sidecar_write as write  # noqa: E402
from service_online_policy import _SAVE_CHAPTERS_SKIP_IF_EXISTS  # noqa: E402
import service_segment_sources  # noqa: E402
import service_sidecar_paths  # noqa: E402
from segment_item import SegmentItem  # noqa: E402
from segment_types import seeded_builtin_types, set_catalog_for_tests  # noqa: E402
from tests import fake_vfs  # noqa: E402


def _xml(*rows):
    atoms = "".join(
        "<ChapterAtom><ChapterTimeStart>%s</ChapterTimeStart><ChapterTimeEnd>%s</ChapterTimeEnd>"
        "<ChapterDisplay><ChapterString>%s</ChapterString></ChapterDisplay></ChapterAtom>" % row
        for row in rows
    )
    return "<Chapters><EditionEntry>%s</EditionEntry></Chapters>" % atoms


class _Addon:
    def __init__(self, **settings):
        self.settings = settings

    def getSetting(self, key):
        return self.settings.get(key, "")

    def getSettingString(self, key):
        return self.settings.get(key, "")


class _WriteTest(unittest.TestCase):
    def setUp(self):
        set_catalog_for_tests(seeded_builtin_types())
        self.addCleanup(set_catalog_for_tests, None)
        self.vfs, self.folder = fake_vfs.install(
            self, write, segment_editor_parser, service_segment_sources, service_sidecar_paths
        )
        self.video = os.path.join(self.folder, "Movie (2020).mkv")
        fake_vfs.write(self.video, "video")
        self.addon = _Addon()
        for target in (write, segment_editor_parser):
            patcher = patch.object(target, "get_addon", lambda: self.addon)
            patcher.start()
            self.addCleanup(patcher.stop)

    def path(self, name):
        return os.path.join(self.folder, name)


class ChapterXmlWriteTests(_WriteTest):
    def test_written_xml_uses_the_catalog_names_and_reads_back(self):
        out = self.path("Movie (2020)_chapters.xml")
        write._write_chapters_xml_to_path(
            out, [SegmentItem(12, 62, "intro", source="theintrodb"), SegmentItem(1300, 1380, "outro", source="introdb")]
        )
        text = fake_vfs.read(out)
        self.assertTrue(text.startswith('<?xml version="1.0" encoding="UTF-8"?>'))
        self.assertIn("<ChapterString>Intro</ChapterString>", text)
        self.assertIn("<ChapterString>Credits</ChapterString>", text)  # outro is Skippy's Credits
        read = segment_editor_parser.parse_chapters(self.video)
        self.assertEqual([(s.start_seconds, s.end_seconds) for s in read], [(12.0, 62.0), (1300.0, 1380.0)])

    def test_a_failed_write_raises_so_the_caller_can_report_it(self):
        out = self.path("Movie (2020)_chapters.xml")
        self.vfs.fail_writes_to[out] = 5
        with self.assertRaises(OSError):
            write._write_chapters_xml_to_path(out, [SegmentItem(1, 2, "intro")])

    def test_chapter_names(self):
        self.assertEqual(write._sidecar_xml_chapter_string("intro"), "Intro")
        self.assertEqual(write._sidecar_xml_chapter_string("my own thing"), "my own thing")
        self.assertEqual(write._sidecar_xml_chapter_string(""), "segment")
        self.assertEqual(write._sidecar_xml_chapter_string(None), "segment")


class BackupTests(_WriteTest):
    def test_the_backup_has_the_old_content(self):
        src = self.path("Movie (2020).edl")
        fake_vfs.write(src, "1\t2\t5\n")
        fake_vfs.write(src + ".bck", "older backup")
        write._backup_sidecar_file(self.addon, src)
        self.assertEqual(fake_vfs.read(src + ".bck"), "1\t2\t5\n")

    def test_a_failed_copy_falls_back_to_reading_and_writing(self):
        src = self.path("Movie (2020).edl")
        fake_vfs.write(src, "1\t2\t5\n")
        with patch.object(self.vfs, "copy", side_effect=OSError("no copy on this share")):
            write._backup_sidecar_file(self.addon, src)
        self.assertEqual(fake_vfs.read(src + ".bck"), "1\t2\t5\n")

    def test_no_backup_when_turned_off(self):
        src = self.path("Movie (2020).edl")
        fake_vfs.write(src, "1\t2\t5\n")
        self.addon.settings["save_online_chapters_backup_before_overwrite"] = "false"
        write._backup_sidecar_file(self.addon, src)
        self.assertFalse(os.path.exists(src + ".bck"))
        write._backup_sidecar_file(None, src)
        self.assertFalse(os.path.exists(src + ".bck"))


class UnchangedChapterXmlTests(_WriteTest):
    def setUp(self):
        super().setUp()
        fake_vfs.write(
            self.path("Movie (2020)_chapters.xml"),
            _xml(("00:00:12.000", "00:01:02.000", "Intro"), ("00:21:40.000", "00:23:00.000", "Credits")),
        )

    def same(self):
        return [SegmentItem(12, 62, "intro"), SegmentItem(1300, 1380, "credits")]

    def test_identical_online_data_needs_no_write_for_any_policy(self):
        for policy in (
            write._SAVE_CHAPTERS_MERGE,
            write._SAVE_CHAPTERS_OVERWRITE_SILENT,
            write._SAVE_CHAPTERS_OVERWRITE_ASK,
            write._SAVE_CHAPTERS_UPDATE_SILENT,
            write._SAVE_CHAPTERS_UPDATE_ALL_ASK,
        ):
            self.assertTrue(write._chapter_xml_save_content_unchanged(self.video, self.same(), policy), policy)

    def test_new_or_moved_data_needs_a_write(self):
        moved = [SegmentItem(15, 65, "intro"), SegmentItem(1300, 1380, "credits")]
        for policy in (write._SAVE_CHAPTERS_OVERWRITE_SILENT, write._SAVE_CHAPTERS_UPDATE_SILENT):
            self.assertFalse(write._chapter_xml_save_content_unchanged(self.video, moved, policy), policy)
        extra = self.same() + [SegmentItem(400, 430, "commercial")]
        self.assertFalse(write._chapter_xml_save_content_unchanged(self.video, extra, write._SAVE_CHAPTERS_MERGE))

    def test_skip_if_exists_never_counts_as_unchanged_and_nothing_online_does(self):
        self.assertFalse(
            write._chapter_xml_save_content_unchanged(self.video, self.same(), _SAVE_CHAPTERS_SKIP_IF_EXISTS)
        )
        self.assertTrue(write._chapter_xml_save_content_unchanged(self.video, [], write._SAVE_CHAPTERS_MERGE))

    def test_no_file_means_a_write(self):
        os.remove(self.path("Movie (2020)_chapters.xml"))
        self.assertFalse(
            write._chapter_xml_save_content_unchanged(self.video, self.same(), write._SAVE_CHAPTERS_MERGE)
        )


class UnchangedEdlTests(_WriteTest):
    def setUp(self):
        super().setUp()
        fake_vfs.write(self.path("Movie (2020).edl"), "12.000\t62.000\t5\n1300.000\t1380.000\t8\n")

    def same(self):
        return [SegmentItem(12, 62, "intro"), SegmentItem(1300, 1380, "credits")]

    def test_identical_rows_need_no_write(self):
        for policy in (
            write._SAVE_CHAPTERS_OVERWRITE_SILENT,
            write._SAVE_CHAPTERS_MERGE,
            write._SAVE_CHAPTERS_UPDATE_ALL_SILENT,
        ):
            self.assertTrue(write._edl_save_content_unchanged(self.video, self.same(), policy), policy)

    def test_a_different_action_needs_a_write(self):
        fake_vfs.write(self.path("Movie (2020).edl"), "12.000\t62.000\t9\n1300.000\t1380.000\t8\n")
        self.assertFalse(
            write._edl_save_content_unchanged(self.video, self.same(), write._SAVE_CHAPTERS_OVERWRITE_SILENT)
        )

    def test_edl_rows_compare_as_written(self):
        triples = write._edl_action_triples_from_segments([SegmentItem(1.23456, 2, "intro")])
        self.assertEqual(triples, ((1.235, 2.0, 5),))
        raw = "1\t2\t5\nbad\n3\t4\t3\n5\t6\t999\n"
        self.assertEqual(
            write._edl_action_triples_from_raw(raw, True, {5: "intro", 3: "commercial"}),
            ((1.0, 2.0, 5), (3.0, 4.0, 3)),
        )
        self.assertEqual(len(write._edl_action_triples_from_raw(raw, False, {})), 3)
        self.assertEqual(write._edl_action_triples_from_raw("", True, {}), ())


if __name__ == "__main__":
    unittest.main()
