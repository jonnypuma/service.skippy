# -*- coding: utf-8 -*-
"""Segment Marker save-path helpers (policy, overlap, time formats)."""

import unittest

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

from segment_marker import (
    hms_to_seconds,
    normalize_marker_policy,
    parse_edl_line_range,
    ranges_overlap,
    seconds_to_edl,
    seconds_to_hms,
    trim_overlapping_edl_line,
)


class MarkerSaveHelperTests(unittest.TestCase):
    def test_normalize_marker_policy_aliases(self):
        self.assertEqual(normalize_marker_policy("MergeNonOverlapping"), "MergeNonOverlapping")
        self.assertEqual(normalize_marker_policy("merge"), "MergeNonOverlapping")
        self.assertEqual(normalize_marker_policy("Ask each time"), "AskEachTime")
        self.assertEqual(normalize_marker_policy("overwrite overlapping"), "OverwriteOverlapping")
        self.assertEqual(normalize_marker_policy("Replace file"), "ReplaceFile")
        self.assertEqual(normalize_marker_policy("Append always"), "AppendAlways")
        self.assertEqual(normalize_marker_policy("unknown-policy"), "MergeNonOverlapping")

    def test_ranges_overlap(self):
        self.assertTrue(ranges_overlap(0, 60, 50, 80))
        self.assertFalse(ranges_overlap(0, 60, 60, 80))  # touching end == start
        self.assertFalse(ranges_overlap(0, 10, 20, 30))

    def test_seconds_formats_roundtrip(self):
        self.assertEqual(seconds_to_hms(3661.5), "01:01:01.500")
        self.assertEqual(hms_to_seconds("01:01:01.500"), 3661.5)
        self.assertEqual(seconds_to_edl(12.3456), "12.346")

    def test_parse_edl_line_range(self):
        self.assertEqual(parse_edl_line_range("0.0 60.0 5"), (0.0, 60.0))
        self.assertEqual(parse_edl_line_range("20 40 9 ;label=recap"), (20.0, 40.0))
        self.assertIsNone(parse_edl_line_range("# comment"))
        self.assertIsNone(parse_edl_line_range(""))

    def test_trim_overlapping_edl_line(self):
        # New segment ends at 40; old line 30-60 → trim old start after new end
        trimmed = trim_overlapping_edl_line("30.000 60.000 5", 40.0, 60.0)
        self.assertIsNotNone(trimmed)
        parts = trimmed.split()
        self.assertAlmostEqual(float(parts[0]), 40.0, places=2)
        self.assertAlmostEqual(float(parts[1]), 60.0, places=2)


if __name__ == "__main__":
    unittest.main()
