# -*- coding: utf-8 -*-
"""Segment Editor save helpers (format normalize, dedupe, time utils)."""

import unittest

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

from segment_editor_parser import (
    SAVE_FORMAT_BOTH,
    SAVE_FORMAT_EDL,
    SAVE_FORMAT_XML,
    dedupe_overlapping_same_label_segments,
    hms_to_seconds,
    normalize_save_format,
    seconds_to_hms,
    segments_chronological,
)
from segment_item import SegmentItem


class EditorSaveHelperTests(unittest.TestCase):
    def test_normalize_save_format(self):
        self.assertEqual(normalize_save_format("Both"), SAVE_FORMAT_BOTH)
        self.assertEqual(normalize_save_format("EDL"), SAVE_FORMAT_EDL)
        self.assertEqual(normalize_save_format("XML"), SAVE_FORMAT_XML)
        self.assertEqual(normalize_save_format("both formats"), SAVE_FORMAT_BOTH)
        self.assertEqual(normalize_save_format(""), SAVE_FORMAT_BOTH)
        self.assertEqual(normalize_save_format("weird"), SAVE_FORMAT_BOTH)

    def test_seconds_hms_roundtrip(self):
        self.assertEqual(seconds_to_hms(90.25), "00:01:30.250")
        self.assertEqual(hms_to_seconds("00:01:30.250"), 90.25)

    def test_segments_chronological(self):
        segs = [
            SegmentItem(100.0, 120.0, "credits", source="edl"),
            SegmentItem(0.0, 60.0, "intro", source="edl"),
            SegmentItem(20.0, 40.0, "recap", source="edl"),
        ]
        ordered = segments_chronological(segs)
        self.assertEqual(
            [s.segment_type_label for s in ordered],
            ["intro", "recap", "credits"],
        )

    def test_dedupe_overlapping_same_label(self):
        segs = [
            SegmentItem(0.0, 50.0, "intro", source="xml"),
            SegmentItem(45.0, 90.0, "intro", source="xml"),
            SegmentItem(100.0, 120.0, "credits", source="xml"),
        ]
        out = dedupe_overlapping_same_label_segments(segs)
        intros = [s for s in out if s.segment_type_label == "intro"]
        self.assertEqual(len(intros), 1)
        self.assertEqual(intros[0].start_seconds, 0.0)
        self.assertEqual(intros[0].end_seconds, 90.0)
        self.assertEqual(len(out), 2)

    def test_dedupe_keeps_different_labels(self):
        segs = [
            SegmentItem(0.0, 60.0, "intro", source="xml"),
            SegmentItem(20.0, 40.0, "recap", source="xml"),
        ]
        out = dedupe_overlapping_same_label_segments(segs)
        self.assertEqual(len(out), 2)


if __name__ == "__main__":
    unittest.main()
