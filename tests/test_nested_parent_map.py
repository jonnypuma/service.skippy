# -*- coding: utf-8 -*-
"""Nested parent map built during segment Pass 2."""

import unittest

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

from segment_item import SegmentItem
from service_segment_processing import build_nested_parent_map


class NestedParentMapTests(unittest.TestCase):
    def test_maps_nested_child_to_parent(self):
        recap = SegmentItem(0.0, 100.0, "recap", source="xml")
        prologue = SegmentItem(75.0, 90.0, "prologue", source="xml")
        intro = SegmentItem(223.0, 283.0, "intro", source="xml")
        parent_map = build_nested_parent_map([recap, prologue, intro])
        self.assertEqual(parent_map[(75, 90)], (0, 100))
        self.assertNotIn((223, 283), parent_map)

    def test_empty_when_no_nesting(self):
        a = SegmentItem(0.0, 60.0, "intro", source="xml")
        b = SegmentItem(60.0, 120.0, "credits", source="xml")
        self.assertEqual(build_nested_parent_map([a, b]), {})


if __name__ == "__main__":
    unittest.main()
