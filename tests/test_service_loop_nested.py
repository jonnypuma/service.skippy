# -*- coding: utf-8 -*-
"""Nested loop helpers."""

import unittest

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

from segment_item import SegmentItem
from service_segment_processing import build_nested_parent_map


class ServiceLoopNestedTests(unittest.TestCase):
    def test_parent_map_for_clearance(self):
        recap = SegmentItem(0.0, 100.0, "recap", source="xml")
        prologue = SegmentItem(75.0, 90.0, "prologue", source="xml")
        parent_map = build_nested_parent_map([recap, prologue])
        self.assertEqual(parent_map[(75, 90)], (0, 100))


if __name__ == "__main__":
    unittest.main()
