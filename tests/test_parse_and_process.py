# -*- coding: utf-8 -*-
"""Pass 1/2 segment processing."""

import unittest

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

from segment_item import SegmentItem
from service_segment_processing import (
    build_nested_parent_map,
    is_nested_segment,
    should_suppress_segment_dialog,
)


class ParseAndProcessTests(unittest.TestCase):
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
