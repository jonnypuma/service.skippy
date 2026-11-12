# -*- coding: utf-8 -*-
"""What the Segment Marker writes into an existing .edl or chapters.xml, policy by policy.

These policies decide what happens to segments the user already has, so each one is checked
against a real file: what is kept, trimmed, removed or left alone.
"""

import os
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import segment_editor_parser  # noqa: E402
import segment_marker as marker  # noqa: E402
import service_sidecar_paths  # noqa: E402
from segment_types import seeded_builtin_types, set_catalog_for_tests  # noqa: E402
from tests import fake_vfs  # noqa: E402

MERGE = marker._MARKER_POLICY_MERGE
KEEP_BOTH = marker._MARKER_POLICY_KEEP_BOTH
OVERWRITE = marker._MARKER_POLICY_OVERWRITE
APPEND = marker._MARKER_POLICY_APPEND
REPLACE = marker._MARKER_POLICY_REPLACE

EXISTING_EDL = "10.000\t70.000\t5\n300.000\t330.000\t7\n"


def _xml(*rows):
    atoms = "".join(
        "<ChapterAtom><ChapterTimeStart>%s</ChapterTimeStart><ChapterTimeEnd>%s</ChapterTimeEnd>"
        "<ChapterDisplay><ChapterString>%s</ChapterString></ChapterDisplay></ChapterAtom>" % row
        for row in rows
    )
    return "<Chapters><EditionEntry>%s</EditionEntry></Chapters>" % atoms


def _atoms(path):
    root = ET.parse(path).getroot()
    out = []
    for atom in root.iter("ChapterAtom"):
        out.append(
            (
                atom.findtext("ChapterTimeStart"),
                atom.findtext("ChapterTimeEnd"),
                atom.findtext("ChapterDisplay/ChapterString"),
            )
        )
    return out


class _MarkerTest(unittest.TestCase):
    def setUp(self):
        set_catalog_for_tests(seeded_builtin_types())
        self.addCleanup(set_catalog_for_tests, None)
        self.vfs, self.folder = fake_vfs.install(self, marker, segment_editor_parser, service_sidecar_paths)
        self.video = os.path.join(self.folder, "Show S01E01.mkv")
        fake_vfs.write(self.video, "video")
        patcher = patch.object(marker, "log")
        patcher.start()
        self.addCleanup(patcher.stop)

    def path(self, name):
        return os.path.join(self.folder, name)


class EdlPolicyTests(_MarkerTest):
    def setUp(self):
        super().setUp()
        self.edl = self.path("Show S01E01.edl")
        fake_vfs.write(self.edl, EXISTING_EDL)

    def save(self, start, end, label, policy):
        return marker.save_to_edl(self.video, start, end, label, "Default", None, policy=policy, backup_before_write=False)

    def test_a_new_segment_is_added_in_time_order(self):
        self.assertTrue(self.save(100, 160, "Recap", MERGE))
        self.assertEqual(
            fake_vfs.read(self.edl).splitlines(),
            ["10.000\t70.000\t5", "100.000\t160.000\t9", "300.000\t330.000\t7"],
        )

    def test_merge_leaves_the_file_alone_on_an_overlap(self):
        self.assertEqual(self.save(60, 90, "Recap", MERGE), "skipped")
        self.assertEqual(fake_vfs.read(self.edl), EXISTING_EDL)

    def test_overwrite_removes_the_overlapping_rows(self):
        self.assertTrue(self.save(60, 90, "Recap", OVERWRITE))
        self.assertEqual(fake_vfs.read(self.edl).splitlines(), ["60.000\t90.000\t9", "300.000\t330.000\t7"])

    def test_keep_both_moves_the_old_start_after_the_new_end(self):
        self.assertTrue(self.save(5, 40, "Recap", KEEP_BOTH))
        self.assertEqual(
            fake_vfs.read(self.edl).splitlines(),
            ["5.000\t40.000\t9", "40.000\t70.000\t5", "300.000\t330.000\t7"],
        )

    def test_keep_both_drops_an_old_row_the_new_one_covers(self):
        self.assertTrue(self.save(0, 80, "Recap", KEEP_BOTH))
        self.assertEqual(fake_vfs.read(self.edl).splitlines(), ["0.000\t80.000\t9", "300.000\t330.000\t7"])

    def test_append_keeps_everything(self):
        self.assertTrue(self.save(60, 90, "Recap", APPEND))
        self.assertEqual(len(fake_vfs.read(self.edl).splitlines()), 3)

    def test_replace_leaves_only_the_new_segment(self):
        self.assertTrue(self.save(60, 90, "Credits", REPLACE))
        self.assertEqual(fake_vfs.read(self.edl), "60.000\t90.000\t8\n")

    def test_a_backup_holds_the_old_file(self):
        marker.save_to_edl(self.video, 100, 160, "Recap", "Default", None, policy=MERGE, backup_before_write=True)
        self.assertEqual(fake_vfs.read(self.edl + ".bck"), EXISTING_EDL)

    def test_a_failed_write_is_not_reported_as_saved(self):
        self.vfs.fail_writes_to[self.edl] = 1
        self.assertFalse(self.save(100, 160, "Recap", MERGE))
        self.assertEqual(fake_vfs.read(self.edl), EXISTING_EDL)

    def test_overlap_check_before_asking(self):
        self.assertEqual(marker.marker_range_overlaps_existing(self.video, "Both", 60, 90), ["EDL"])
        self.assertEqual(marker.marker_range_overlaps_existing(self.video, "XML", 60, 90), [])
        self.assertEqual(marker.marker_range_overlaps_existing(self.video, "EDL", 70, 90), [])  # touching is fine
        self.assertTrue(marker.marker_selected_sidecars_exist(self.video, "EDL"))
        self.assertFalse(marker.marker_selected_sidecars_exist(self.video, "XML"))


class ChapterXmlPolicyTests(_MarkerTest):
    def setUp(self):
        super().setUp()
        self.xml = self.path("Show S01E01_chapters.xml")
        fake_vfs.write(
            self.xml,
            _xml(("00:00:10.000", "00:01:10.000", "Intro"), ("00:05:00.000", "00:05:30.000", "Commercial")),
        )

    def save(self, start, end, label, policy):
        return marker.save_to_chapters_xml(self.video, start, end, label, "Default", policy=policy, backup_before_write=False)

    def test_a_new_chapter_is_added_in_time_order(self):
        self.assertTrue(self.save(100, 160, "Recap", MERGE))
        self.assertEqual([a[2] for a in _atoms(self.xml)], ["Intro", "Recap", "Commercial"])

    def test_merge_leaves_the_file_alone_on_an_overlap(self):
        before = fake_vfs.read(self.xml)
        self.assertEqual(self.save(60, 90, "Recap", MERGE), "skipped")
        self.assertEqual(fake_vfs.read(self.xml), before)

    def test_overwrite_and_keep_both(self):
        self.assertTrue(self.save(60, 90, "Recap", OVERWRITE))
        self.assertEqual([a[2] for a in _atoms(self.xml)], ["Recap", "Commercial"])
        self.assertTrue(self.save(280, 310, "Recap", KEEP_BOTH))
        atoms = _atoms(self.xml)
        self.assertEqual(atoms[-1][:2], ("00:05:10.000", "00:05:30.000"))

    def test_replace_leaves_only_the_new_chapter(self):
        self.assertTrue(self.save(60, 90, "Credits", REPLACE))
        self.assertEqual(_atoms(self.xml), [("00:01:00.000", "00:01:30.000", "Credits")])

    def test_a_file_the_reader_accepts_can_be_added_to(self):
        # A blank line before the declaration and a second declaration: invalid XML that
        # Skippy's reader accepts, so the marker must accept it too.
        fake_vfs.write(
            self.xml,
            '\n<?xml version="1.0"?>\n<?xml version="1.0"?>' + _xml(("00:00:10.000", "00:01:10.000", "Intro")),
        )
        self.assertTrue(self.save(100, 160, "Recap", MERGE))
        self.assertEqual([a[2] for a in _atoms(self.xml)], ["Intro", "Recap"])
        self.assertEqual(marker.marker_range_overlaps_existing(self.video, "XML", 60, 90), ["chapters.xml"])

    def test_a_new_file_is_created_when_there_is_none(self):
        os.remove(self.xml)
        self.assertTrue(self.save(5, 50, "Intro", MERGE))
        self.assertEqual(_atoms(self.xml), [("00:00:05.000", "00:00:50.000", "Intro")])


class HelperTests(unittest.TestCase):
    def test_policy_names_old_and_new(self):
        for raw, expected in (
            ("MergeNonOverlapping", MERGE), ("Merge non-overlapping", MERGE), ("0", MERGE), ("", MERGE), (None, MERGE),
            ("Keep both (old starts after new)", KEEP_BOTH), ("overwrite", OVERWRITE), ("2", APPEND),
            ("Replace file", REPLACE), ("ask", marker._MARKER_POLICY_ASK), ("junk", MERGE),
        ):
            self.assertEqual(marker.normalize_marker_policy(raw), expected, raw)

    def test_trimming_and_sorting_rows(self):
        self.assertEqual(marker.trim_overlapping_edl_line("10\t70\t5", 40, 70), "40.000\t70.000\t5")
        self.assertIsNone(marker.trim_overlapping_edl_line("10\t70\t5", 80, 70))
        self.assertEqual(marker.trim_overlapping_edl_line("10 70", 40, 70), "40.000\t70.000\t4")
        self.assertEqual(marker.sorted_edl_content("30\t40\t5\n# note\n10\t20\t5"), "10\t20\t5\n30\t40\t5\n# note\n")
        self.assertEqual(marker.sorted_edl_content(""), "")

    def test_overlap_is_strict(self):
        self.assertTrue(marker.ranges_overlap(0, 10, 9, 20))
        self.assertFalse(marker.ranges_overlap(0, 10, 10, 20))


if __name__ == "__main__":
    unittest.main()
