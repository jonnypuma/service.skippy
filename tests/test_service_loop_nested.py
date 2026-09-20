# -*- coding: utf-8 -*-
"""Nested loop helpers."""

import unittest
from unittest.mock import MagicMock

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

from segment_item import SegmentItem
from segment_relations import segment_id
from service_loop_skip import _track_skip_to_nested
from service_segment_processing import build_nested_parent_map, is_nested_segment


class ServiceLoopNestedTests(unittest.TestCase):
    def test_parent_map_for_clearance(self):
        recap = SegmentItem(0.0, 100.0, "recap", source="xml")
        prologue = SegmentItem(75.0, 90.0, "prologue", source="xml")
        parent_map = build_nested_parent_map([recap, prologue])
        self.assertEqual(parent_map[(75, 90)], (0, 100))

    def test_track_skip_to_nested_allows_tiny_float_gap(self):
        parent = SegmentItem(0.0, 100.0, "recap", source="xml")
        child = SegmentItem(15.0, 90.0, "intro", source="xml")
        parent.next_segment_start = 15.00004
        ctx = MagicMock()
        ctx.monitor.current_segments = [parent, child]
        ctx.monitor.skipped_to_nested_segment = {}
        ctx.monitor.prompted = set()
        ctx.monitor.recently_dismissed = set()
        ctx.monitor.cleared_parent_dismissals = set()
        ctx.is_nested_segment = is_nested_segment
        parent_id = segment_id(parent)
        _track_skip_to_nested(ctx, parent, parent_id)
        self.assertIs(ctx.monitor.skipped_to_nested_segment[parent_id], child)


if __name__ == "__main__":
    unittest.main()
