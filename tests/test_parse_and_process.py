# -*- coding: utf-8 -*-
"""Pass 1/2 segment processing."""

import unittest
from unittest.mock import patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

from segment_item import SegmentItem
from service_segment_processing import re_evaluate_segment_jump_points
from service_segment_sources import parse_edl
from service_segment_processing import (
    build_nested_parent_map,
    is_nested_segment,
    should_suppress_segment_dialog,
)
from skipdialog import format_next_jump_label


class ParseAndProcessTests(unittest.TestCase):
    def test_exact_nested_edl_links_remaining_parent_label(self):
        """The reported 0-60 Intro / 20-40 Recap flow renders end-to-end."""
        with patch(
            "service_segment_sources.safe_file_read",
            return_value="0 60 5\n20 40 9\n",
        ), patch(
            "service_segment_sources.get_edl_type_map",
            return_value={5: "Intro", 9: "Recap"},
        ), patch("service_segment_sources.get_addon", return_value=None):
            segments = parse_edl("episode.mkv", update_monitor=False)

        self.assertEqual(
            [(s.start_seconds, s.end_seconds, s.segment_type_label) for s in segments],
            [(0.0, 60.0, "intro"), (20.0, 40.0, "recap")],
        )

        # At the nested segment, its skip lands at 40s inside the parent.
        re_evaluate_segment_jump_points(segments, current_time=20.0)
        recap = segments[1]
        self.assertEqual(recap.next_segment_start, 40.0)
        self.assertEqual(recap.next_segment_info, "remaining 'intro'")
        self.assertEqual(
            format_next_jump_label(
                None, recap.next_segment_info, recap.next_segment_start
            ),
            "Skip to remaining Intro at 00:40",
        )

    def test_nested_detection(self):
        parent = SegmentItem(0.0, 100.0, "recap", source="xml")
        child = SegmentItem(10.0, 50.0, "prologue", source="xml")
        self.assertTrue(is_nested_segment(parent, child))

    def test_suppress_parent_when_nested_active(self):
        parent = SegmentItem(0.0, 100.0, "recap", source="xml")
        child = SegmentItem(10.0, 50.0, "prologue", source="xml")
        segs = [parent, child]
        self.assertTrue(
            should_suppress_segment_dialog(parent, segs, 25.0, recently_dismissed=set())
        )

    def test_parent_map_matches_nested(self):
        parent = SegmentItem(0.0, 100.0, "recap", source="xml")
        child = SegmentItem(10.0, 50.0, "prologue", source="xml")
        parent_map = build_nested_parent_map([parent, child])
        self.assertEqual(parent_map[(10, 50)], (0, 100))


if __name__ == "__main__":
    unittest.main()
