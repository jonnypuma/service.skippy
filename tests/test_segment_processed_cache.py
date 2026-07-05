# -*- coding: utf-8 -*-
"""Tests for processed segment cache (link phase, invalidation)."""

import unittest

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

from segment_item import SegmentItem
from service_segment_processed_cache import (
    clear_segment_processed_cache,
    compute_link_boundaries,
    compute_link_phase,
    source_segment_fingerprint,
    store_segment_processed_cache,
    try_get_processed_cache,
)


class _Monitor:
    segment_processed_cache = None


def _noop_log_if_changed(_key, _msg):
    pass


class ProcessedCacheTests(unittest.TestCase):
    def test_link_phase_crosses_nested_boundary(self):
        boundaries = (75.0, 223.0)
        self.assertEqual(compute_link_phase(10.0, boundaries), 0)
        self.assertEqual(compute_link_phase(75.0, boundaries), 1)
        self.assertEqual(compute_link_phase(200.0, boundaries), 1)
        self.assertEqual(compute_link_phase(223.0, boundaries), 2)

    def test_compute_link_boundaries_nested(self):
        recap = SegmentItem(0.0, 100.0, "recap", source="xml")
        prologue = SegmentItem(75.0, 90.0, "prologue", source="xml")
        intro = SegmentItem(223.0, 283.0, "intro", source="xml")
        boundaries = compute_link_boundaries([recap, prologue, intro])
        self.assertEqual(boundaries, (75.0,))

    def test_cache_hit_same_phase(self):
        monitor = _Monitor()
        recap = SegmentItem(0.0, 75.0, "recap", source="xml")
        prologue = SegmentItem(75.0, 223.0, "prologue", source="xml")
        pass1 = [recap, prologue]
        processed = [recap, prologue]
        recap.next_segment_start = 75.0

        store_segment_processed_cache(
            monitor,
            "/video.mkv",
            "episode",
            pass1,
            pass1,
            processed,
            10.0,
            source_settings_sig=(("tv_use_local_chapter_edl", "true"),),
            sidecar_signature="sig1",
        )

        result, status = try_get_processed_cache(
            monitor,
            "/video.mkv",
            "episode",
            pass1,
            20.0,
            source_settings_sig=(("tv_use_local_chapter_edl", "true"),),
            sidecar_signature="sig1",
            clone_pass1_fn=lambda segs: list(segs),
            log_if_changed=_noop_log_if_changed,
        )
        self.assertEqual(status, "hit")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].next_segment_start, 75.0)

    def test_cache_miss_on_fingerprint_change(self):
        monitor = _Monitor()
        seg = SegmentItem(0.0, 60.0, "intro", source="xml")
        store_segment_processed_cache(
            monitor,
            "/video.mkv",
            "episode",
            [seg],
            [seg],
            [seg],
            5.0,
            source_settings_sig=(),
            sidecar_signature="sig1",
        )
        other = SegmentItem(0.0, 60.0, "recap", source="xml")
        result, status = try_get_processed_cache(
            monitor,
            "/video.mkv",
            "episode",
            [other],
            5.0,
            source_settings_sig=(),
            sidecar_signature="sig1",
            clone_pass1_fn=lambda segs: list(segs),
            log_if_changed=_noop_log_if_changed,
        )
        self.assertEqual(status, "miss")
        self.assertIsNone(result)

    def test_clear_invalidates(self):
        monitor = _Monitor()
        monitor.segment_processed_cache = {"key": "x"}
        clear_segment_processed_cache(monitor)
        self.assertIsNone(monitor.segment_processed_cache)

    def test_source_fingerprint_stable(self):
        a = SegmentItem(0.0, 10.0, "intro", source="xml")
        b = SegmentItem(20.0, 30.0, "credits", source="xml")
        fp = source_segment_fingerprint([b, a])
        self.assertEqual(fp[0][2], "intro")


if __name__ == "__main__":
    unittest.main()
