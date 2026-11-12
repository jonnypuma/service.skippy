# -*- coding: utf-8 -*-
"""Reading and writing sidecar files (.edl and chapters.xml) on a real folder.

These are the files Skippy, the Segment Marker and the Segment Editor share with the user, so
a save must read back exactly, must never leave a half-written or empty file, and must keep
the old file when a write fails.
"""

import os
import unittest
from unittest.mock import patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import segment_editor_parser as parser  # noqa: E402
import service_sidecar_paths as paths  # noqa: E402
from segment_types import seeded_builtin_types, set_catalog_for_tests  # noqa: E402
from tests import fake_vfs  # noqa: E402

SegmentItem = parser.SegmentItem


class _Addon:
    def __init__(self, settings=None):
        self.settings = dict(settings or {})

    def getSetting(self, key):
        return self.settings.get(key, "")


class _SidecarTest(unittest.TestCase):
    def setUp(self):
        set_catalog_for_tests(seeded_builtin_types())
        self.addCleanup(set_catalog_for_tests, None)
        self.vfs, self.folder = fake_vfs.install(self, parser, paths)
        self.video = os.path.join(self.folder, "Show S01E01.mkv")
        fake_vfs.write(self.video, "video")
        self.addon = _Addon({"segment_editor_backup_before_write": "false"})
        patcher = patch.object(parser, "get_addon", lambda: self.addon)
        patcher.start()
        self.addCleanup(patcher.stop)

    def path(self, name):
        return os.path.join(self.folder, name)

    def segments(self):
        return [
            SegmentItem(0.0, 42.5, "Recap"),
            SegmentItem(60.25, 150.0, "Intro"),
            SegmentItem(1300.0, 1380.125, "Credits"),
        ]


class EdlRoundTripTests(_SidecarTest):
    def test_saved_edl_reads_back_the_same_segments(self):
        self.assertTrue(parser.save_edl(self.video, self.segments()))
        text = fake_vfs.read(self.path("Show S01E01.edl"))
        self.assertEqual(text.splitlines()[1], "60.250\t150.000\t5")
        read = parser.parse_edl(self.video)
        self.assertEqual(
            [(s.start_seconds, s.end_seconds, s.segment_type_label) for s in read],
            [(0.0, 42.5, "recap"), (60.25, 150.0, "intro"), (1300.0, 1380.125, "credits")],
        )

    def test_a_shorter_save_leaves_no_old_bytes_at_the_end(self):
        self.vfs.truncate_on_open = False  # network shares often do not truncate on overwrite
        parser.save_edl(self.video, self.segments())
        parser.save_edl(self.video, [SegmentItem(1.0, 2.0, "Intro")])
        self.assertEqual(fake_vfs.read(self.path("Show S01E01.edl")), "1.000\t2.000\t5\n")

    def test_a_row_ending_before_it_starts_does_not_drop_the_rows_after_it(self):
        fake_vfs.write(self.path("Show S01E01.edl"), "10\t20\t5\n30\t25\t5\n40\t50\t8\n")
        read = parser.parse_edl(self.video)
        self.assertEqual([(s.start_seconds, s.end_seconds) for s in read], [(10.0, 20.0), (40.0, 50.0)])

    def test_bad_rows_and_comments_are_skipped_not_fatal(self):
        fake_vfs.write(
            self.path("Show S01E01.edl"),
            "# made by hand\n10\t20\t5\nnot a row\n30 25 5\n-1 4 5\n40\t50\t8\textra\n",
        )
        read = parser.parse_edl(self.video)
        self.assertEqual([(s.start_seconds, s.end_seconds) for s in read], [(10.0, 20.0), (40.0, 50.0)])

    def test_no_edl_gives_an_empty_list(self):
        self.assertEqual(parser.parse_edl(self.video), [])


class ChapterXmlRoundTripTests(_SidecarTest):
    def test_saved_chapters_read_back_the_same_segments(self):
        self.assertTrue(parser.save_chapters(self.video, self.segments()))
        written = self.path("Show S01E01_chapters.xml")
        self.assertTrue(os.path.exists(written))
        self.assertTrue(fake_vfs.read(written).startswith('<?xml version="1.0" encoding="UTF-8"?>'))
        read = parser.parse_chapters(self.video)
        self.assertEqual(
            [(s.start_seconds, s.end_seconds, s.segment_type_label) for s in read],
            [(0.0, 42.5, "recap"), (60.25, 150.0, "intro"), (1300.0, 1380.125, "credits")],
        )

    def test_an_existing_chapter_file_keeps_its_name(self):
        existing = self.path("Show S01E01-chapters.xml")
        fake_vfs.write(existing, "<Chapters><EditionEntry/></Chapters>")
        parser.save_chapters(self.video, self.segments())
        self.assertFalse(os.path.exists(self.path("Show S01E01_chapters.xml")))
        self.assertEqual(len(parser.parse_chapters(self.video)), 3)

    def test_a_bom_and_a_doubled_declaration_still_parse(self):
        fake_vfs.write(
            self.path("Show S01E01.chapters.xml"),
            "﻿\n  <?xml version=\"1.0\"?>\n<?xml version=\"1.0\"?>"
            "<Chapters><EditionEntry><ChapterAtom><ChapterTimeStart>00:00:05.000</ChapterTimeStart>"
            "<ChapterTimeEnd>00:01:00.000</ChapterTimeEnd><ChapterDisplay><ChapterString>Intro"
            "</ChapterString></ChapterDisplay></ChapterAtom></EditionEntry></Chapters>",
        )
        read = parser.parse_chapters(self.video)
        self.assertEqual([(s.start_seconds, s.end_seconds) for s in read], [(5.0, 60.0)])

    def test_a_placeholder_file_is_skipped_for_the_next_one(self):
        fake_vfs.write(self.path("Show S01E01_chapters.xml"), "<Chapters><EditionEntry/></Chapters>")
        fake_vfs.write(
            self.path("chapters.xml"),
            "<Chapters><EditionEntry><ChapterAtom><ChapterTimeStart>00:00:01.000</ChapterTimeStart>"
            "<ChapterTimeEnd>00:00:09.000</ChapterTimeEnd></ChapterAtom></EditionEntry></Chapters>",
        )
        read = parser.parse_chapters(self.video)
        self.assertEqual([(s.start_seconds, s.end_seconds, s.segment_type_label) for s in read], [(1.0, 9.0, "segment")])

    def test_broken_xml_gives_none(self):
        fake_vfs.write(self.path("Show S01E01_chapters.xml"), "<Chapters><EditionEntry>")
        self.assertIsNone(parser.parse_chapters(self.video))

    def test_overlapping_atoms_of_one_type_are_merged(self):
        fake_vfs.write(
            self.path("Show S01E01_chapters.xml"),
            "<Chapters><EditionEntry>"
            "<ChapterAtom><ChapterTimeStart>00:00:10.000</ChapterTimeStart><ChapterTimeEnd>00:00:50.000</ChapterTimeEnd>"
            "<ChapterDisplay><ChapterString>Intro</ChapterString></ChapterDisplay></ChapterAtom>"
            "<ChapterAtom><ChapterTimeStart>00:00:49.500</ChapterTimeStart><ChapterTimeEnd>00:01:20.000</ChapterTimeEnd>"
            "<ChapterDisplay><ChapterString>intro</ChapterString></ChapterDisplay></ChapterAtom>"
            "</EditionEntry></Chapters>",
        )
        read = parser.parse_chapters(self.video)
        self.assertEqual([(s.start_seconds, s.end_seconds) for s in read], [(10.0, 80.0)])


class SafeWriteTests(_SidecarTest):
    def test_a_failed_overwrite_keeps_the_old_file(self):
        target = self.path("Show S01E01.edl")
        fake_vfs.write(target, "1.000\t2.000\t5\n")
        self.vfs.fail_writes_to[target] = 1
        ok, written = parser.safe_file_write(target, "9.000\t10.000\t5\n")
        self.assertEqual((ok, written), (False, None))
        self.assertEqual(fake_vfs.read(target), "1.000\t2.000\t5\n")

    def test_a_failed_new_file_leaves_nothing_behind(self):
        target = self.path("new.edl")
        self.vfs.fail_writes_to[target] = 5
        self.assertEqual(parser.safe_file_write(target, "1\t2\t5\n"), (False, None))
        self.assertFalse(os.path.exists(target))

    def test_a_successful_write_reports_the_bytes(self):
        target = self.path("new.edl")
        ok, written = parser.safe_file_write(target, "abc")
        self.assertTrue(ok)
        self.assertIn(written, (True, 3))
        self.assertEqual(fake_vfs.read(target), "abc")

    def test_nfs_paths_get_fallback_variations(self):
        self.assertEqual(parser.remap_nfs_path_for_write("/local/a.edl"), ["/local/a.edl"])
        self.assertEqual(
            parser.remap_nfs_path_for_write("nfs://server/export/tv/show.edl"),
            ["nfs://server/export/tv/show.edl", "nfs://server/tv/show.edl"],
        )

    def test_a_failed_nfs_write_never_lands_in_the_share_root(self):
        for path in (
            "nfs://server/export/tv/show.edl",
            "nfs://server/export/show.edl",
            "nfs://server/show.edl",
            "nfs://server/a/b/c/show.edl",
        ):
            for variation in parser.remap_nfs_path_for_write(path):
                self.assertNotEqual(variation, "nfs://server/show.edl" if path != "nfs://server/show.edl" else None, path)
                self.assertTrue(variation.endswith("/show.edl"))
                self.assertGreaterEqual(variation.count("/"), path.count("/") - 1, (path, variation))
        self.assertEqual(parser.remap_nfs_path_for_write("nfs://server/export/show.edl"), ["nfs://server/export/show.edl"])


class SaveSegmentsTests(_SidecarTest):
    def test_both_formats_are_written_in_time_order(self):
        segs = list(reversed(self.segments()))
        self.assertEqual(parser.save_segments(self.video, segs, "Both"), (True, True))
        starts = [line.split("\t")[0] for line in fake_vfs.read(self.path("Show S01E01.edl")).splitlines()]
        self.assertEqual(starts, ["0.000", "60.250", "1300.000"])
        self.assertTrue(os.path.exists(self.path("Show S01E01_chapters.xml")))

    def test_one_format_writes_only_that_file(self):
        self.assertEqual(parser.save_segments(self.video, self.segments(), "EDL only"), (True, False))
        self.assertFalse(os.path.exists(self.path("Show S01E01_chapters.xml")))
        os.remove(self.path("Show S01E01.edl"))
        self.assertEqual(parser.save_segments(self.video, self.segments(), "xml"), (False, True))
        self.assertFalse(os.path.exists(self.path("Show S01E01.edl")))

    def test_a_backup_is_made_when_asked(self):
        target = self.path("Show S01E01.edl")
        fake_vfs.write(target, "1.000\t2.000\t5\n")
        self.addon.settings["segment_editor_backup_before_write"] = "true"
        parser.save_segments(self.video, self.segments(), "edl")
        self.assertEqual(fake_vfs.read(target + ".bck"), "1.000\t2.000\t5\n")
        self.assertNotEqual(fake_vfs.read(target), "1.000\t2.000\t5\n")

    def test_no_backup_unless_asked(self):
        target = self.path("Show S01E01.edl")
        fake_vfs.write(target, "1.000\t2.000\t5\n")
        parser.save_segments(self.video, self.segments(), "edl")
        self.assertFalse(os.path.exists(target + ".bck"))

    def test_the_save_format_setting_and_its_old_names(self):
        for raw, expected in (
            ("Both", "both"), ("EDL only", "edl"), ("Chapter XML only", "xml"), ("Auto detect", "both"),
            ("xml", "xml"), ("", "both"), (None, "both"), ("nonsense", "both"),
        ):
            self.assertEqual(parser.normalize_save_format(raw), expected, raw)
        self.addon.settings["segment_editor_save_format"] = "EDL only"
        self.assertEqual(parser.get_save_format(), "edl")

    def test_deleting_removes_only_the_chosen_format(self):
        parser.save_segments(self.video, self.segments(), "both")
        deleted = parser.delete_segment_files(self.video, "edl")
        self.assertEqual([os.path.basename(p) for p in deleted], ["Show S01E01.edl"])
        self.assertTrue(os.path.exists(self.path("Show S01E01_chapters.xml")))
        deleted = parser.delete_segment_files(self.video, "both")
        self.assertEqual([os.path.basename(p) for p in deleted], ["Show S01E01_chapters.xml"])


class SegmentHelpersTests(unittest.TestCase):
    def test_a_segment_must_have_a_positive_length(self):
        with self.assertRaises(ValueError):
            SegmentItem(10, 10)
        with self.assertRaises(ValueError):
            SegmentItem(-1, 10)
        self.assertEqual(SegmentItem("1.5", "3").get_duration(), 1.5)

    def test_touching_windows_of_one_label_merge_and_other_labels_stay(self):
        merged = parser.dedupe_overlapping_same_label_segments(
            [SegmentItem(0, 10, "Intro"), SegmentItem(11, 20, "intro"), SegmentItem(30, 40, "Recap")]
        )
        self.assertEqual(
            [(s.start_seconds, s.end_seconds, s.segment_type_label) for s in merged],
            [(0.0, 20.0, "intro"), (30.0, 40.0, "recap")],
        )
        # Only neighbours merge: another type between two intros keeps them apart.
        between = parser.dedupe_overlapping_same_label_segments(
            [SegmentItem(0, 10, "Intro"), SegmentItem(5, 15, "Recap"), SegmentItem(11, 20, "Intro")]
        )
        self.assertEqual(len(between), 3)
        apart = parser.dedupe_overlapping_same_label_segments(
            [SegmentItem(0, 10, "Intro"), SegmentItem(12, 20, "Intro")]
        )
        self.assertEqual(len(apart), 2)

    def test_chronological_order(self):
        segs = [SegmentItem(5, 9), SegmentItem(1, 3), SegmentItem(1, 2)]
        self.assertEqual(
            [(s.start_seconds, s.end_seconds) for s in parser.segments_chronological(segs)],
            [(1.0, 2.0), (1.0, 3.0), (5.0, 9.0)],
        )
        self.assertEqual(parser.segments_chronological([]), [])

    def test_xml_text_normalisation(self):
        self.assertEqual(parser.normalize_matroska_chapter_xml_text(None), "")
        self.assertEqual(parser.normalize_matroska_chapter_xml_text(b"\xef\xbb\xbf<a/>"), "<a/>")
        doubled = '<?xml version="1.0"?>  \n<?xml version="1.0"?><a/>'
        self.assertEqual(parser.normalize_matroska_chapter_xml_text(doubled), '<?xml version="1.0"?>\n<a/>')


if __name__ == "__main__":
    unittest.main()
