# -*- coding: utf-8 -*-
"""Remote merge cache must not store cooldown / transport failures."""

import unittest
from unittest.mock import patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

from segment_item import SegmentItem


class RemoteLookupCacheTests(unittest.TestCase):
    def test_does_not_cache_when_a_source_returns_none(self):
        from remote_lookup import fetch_remote_tv_segments_core

        cache = {}
        item = {"type": "episode"}
        context = {
            "type": "episode",
            "tmdb_id": 1,
            "imdb_id": "tt1",
            "show_imdb_id": "tt1",
            "season": 1,
            "episode": 1,
        }
        intro = [SegmentItem(0.0, 10.0, "intro", source="introdb")]
        with patch("remote_lookup.build_tv_episode_context", return_value=context), patch(
            "remote_lookup.fetch_theintrodb_segments", return_value=None
        ), patch(
            "remote_lookup.fetch_introdb_segments", return_value=intro
        ), patch(
            "remote_lookup._online_merge_introdb_primary", return_value=False
        ), patch(
            "remote_lookup.record_online_segments_downloaded"
        ):
            out = fetch_remote_tv_segments_core(item, 3600.0, cache)
        self.assertEqual(len(out), 1)
        self.assertEqual(cache, {})

    def test_caches_real_empty_when_both_sources_return_lists(self):
        from remote_lookup import build_tv_cache_key, fetch_remote_tv_segments_core

        cache = {}
        item = {"type": "episode"}
        context = {
            "type": "episode",
            "tmdb_id": 2,
            "imdb_id": "tt2",
            "show_imdb_id": "tt2",
            "season": 1,
            "episode": 2,
        }
        with patch("remote_lookup.build_tv_episode_context", return_value=context), patch(
            "remote_lookup.fetch_theintrodb_segments", return_value=[]
        ), patch(
            "remote_lookup.fetch_introdb_segments", return_value=[]
        ), patch(
            "remote_lookup._online_merge_introdb_primary", return_value=False
        ):
            out = fetch_remote_tv_segments_core(item, 3600.0, cache)
        self.assertEqual(out, [])
        self.assertIn(build_tv_cache_key(context), cache)
        self.assertEqual(cache[build_tv_cache_key(context)], [])


class RemoteOutroLabelTests(unittest.TestCase):
    def test_payload_key_outro_maps_to_credits(self):
        from remote_http import local_label_for_remote_payload_key

        self.assertEqual(local_label_for_remote_payload_key("outro"), "credits")
        self.assertEqual(local_label_for_remote_payload_key("credits"), "credits")
        self.assertEqual(local_label_for_remote_payload_key("intro"), "intro")

    def test_introdb_entries_store_outro_as_credits(self):
        from remote_lookup import _introdb_segment_entries

        segs = _introdb_segment_entries(
            {"outro": {"start_sec": 500.0, "end_sec": 560.0}, "intro": {"start_sec": 0.0, "end_sec": 45.0}},
            900.0,
        )
        labels = sorted(s.segment_type_label for s in segs)
        self.assertEqual(labels, ["credits", "intro"])
        credits = next(s for s in segs if s.segment_type_label == "credits")
        self.assertEqual(credits.source, "introdb")
        self.assertEqual(credits.start_seconds, 500.0)

    def test_theintrodb_entries_map_outro_key(self):
        from remote_lookup import _theintrodb_segment_entries

        segs = _theintrodb_segment_entries(
            {
                "outro": [{"start_ms": 500000, "end_ms": 560000}],
                "credits": [{"start_ms": 600000, "end_ms": 660000}],
            },
            900.0,
        )
        labels = [s.segment_type_label for s in segs]
        self.assertEqual(labels, ["credits", "credits"])


if __name__ == "__main__":
    unittest.main()
