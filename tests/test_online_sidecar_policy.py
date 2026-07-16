# -*- coding: utf-8 -*-
"""Online sidecar save policy normalization + merge/update helpers."""

import unittest
from unittest.mock import MagicMock

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

from segment_item import SegmentItem
from service_online_policy import (
    _SAVE_CHAPTERS_MERGE,
    _SAVE_CHAPTERS_OVERWRITE_ASK,
    _SAVE_CHAPTERS_SKIP_IF_EXISTS,
    _SAVE_CHAPTERS_UPDATE_ALL_ASK,
    _SAVE_CHAPTERS_UPDATE_SILENT,
    _SAVE_ONLINE_FORMAT_BOTH,
    _SAVE_ONLINE_FORMAT_EDL,
    _SAVE_ONLINE_FORMAT_XML,
    _normalize_online_sidecar_policy,
    _normalize_save_online_format,
    _normalize_segment_source_priority,
    policy_allows_neighbor_snap,
)
from service_online_sidecar_save import (
    _finalize_sidecar_after_update_policy,
    _merge_sidecar_segments,
    _sidecar_update_plan,
    _update_sidecar_segments,
)


class OnlineSidecarPolicyTests(unittest.TestCase):
    def test_normalize_policy_storage_and_labels(self):
        self.assertEqual(
            _normalize_online_sidecar_policy("SkipIfExists"),
            _SAVE_CHAPTERS_SKIP_IF_EXISTS,
        )
        self.assertEqual(
            _normalize_online_sidecar_policy("Merge with existing"),
            _SAVE_CHAPTERS_MERGE,
        )
        self.assertEqual(
            _normalize_online_sidecar_policy("Update All (ask first)"),
            _SAVE_CHAPTERS_UPDATE_ALL_ASK,
        )
        self.assertEqual(
            _normalize_online_sidecar_policy("not-a-real-policy"),
            _SAVE_CHAPTERS_SKIP_IF_EXISTS,
        )

    def test_normalize_save_format(self):
        self.assertEqual(_normalize_save_online_format("Both"), _SAVE_ONLINE_FORMAT_BOTH)
        self.assertEqual(_normalize_save_online_format("EDL"), _SAVE_ONLINE_FORMAT_EDL)
        self.assertEqual(_normalize_save_online_format("XML"), _SAVE_ONLINE_FORMAT_XML)
        self.assertEqual(_normalize_save_online_format("edl only"), _SAVE_ONLINE_FORMAT_EDL)
        self.assertEqual(_normalize_save_online_format(""), _SAVE_ONLINE_FORMAT_BOTH)

    def test_normalize_segment_source_priority(self):
        self.assertEqual(_normalize_segment_source_priority("LocalFirst"), "LocalFirst")
        self.assertEqual(_normalize_segment_source_priority("Online first"), "OnlineFirst")
        self.assertEqual(_normalize_segment_source_priority("bogus"), "LocalFirst")

    def test_neighbor_snap_only_on_update_policies(self):
        self.assertTrue(policy_allows_neighbor_snap(_SAVE_CHAPTERS_UPDATE_SILENT))
        self.assertTrue(policy_allows_neighbor_snap(_SAVE_CHAPTERS_UPDATE_ALL_ASK))
        self.assertFalse(policy_allows_neighbor_snap(_SAVE_CHAPTERS_MERGE))
        self.assertFalse(policy_allows_neighbor_snap(_SAVE_CHAPTERS_OVERWRITE_ASK))
        self.assertFalse(policy_allows_neighbor_snap(_SAVE_CHAPTERS_SKIP_IF_EXISTS))


class OnlineSidecarMergeUpdateTests(unittest.TestCase):
    def test_merge_keeps_existing_adds_non_overlapping(self):
        local = [
            SegmentItem(0.0, 60.0, "intro", source="edl"),
            SegmentItem(100.0, 120.0, "credits", source="edl"),
        ]
        online = [
            SegmentItem(0.0, 55.0, "intro", source="theintrodb"),  # overlaps intro
            SegmentItem(200.0, 230.0, "preview", source="theintrodb"),
        ]
        merged = _merge_sidecar_segments(local, online)
        labels = [s.segment_type_label for s in merged]
        self.assertEqual(labels.count("intro"), 1)
        self.assertIn("preview", labels)
        self.assertEqual(len(merged), 3)

    def test_update_retimes_matched_bucket_preserves_unmatched_local(self):
        local = [
            SegmentItem(0.0, 60.0, "intro", source="edl"),
            SegmentItem(60.0, 90.0, "prologue", source="edl"),
            SegmentItem(500.0, 560.0, "credits", source="edl"),
        ]
        online = [
            SegmentItem(0.0, 45.0, "intro", source="theintrodb"),
            SegmentItem(510.0, 570.0, "credits", source="introdb"),
        ]
        changes, updated, unmatched = _sidecar_update_plan(local, online)
        self.assertEqual(len(unmatched), 0)
        self.assertEqual(len(changes), 2)
        by_label = {s.segment_type_label: s for s in updated}
        self.assertEqual(by_label["intro"].end_seconds, 45.0)
        self.assertEqual(by_label["credits"].start_seconds, 510.0)
        self.assertEqual(by_label["prologue"].start_seconds, 60.0)
        self.assertEqual(by_label["prologue"].end_seconds, 90.0)

    def test_update_all_inserts_unmatched_online_bucket(self):
        local = [SegmentItem(0.0, 60.0, "intro", source="edl")]
        online = [
            SegmentItem(0.0, 50.0, "intro", source="theintrodb"),
            SegmentItem(80.0, 100.0, "recap", source="theintrodb"),
        ]
        addon = MagicMock()
        addon.getSetting = lambda _k: "false"
        final = _finalize_sidecar_after_update_policy(
            local, online, _SAVE_CHAPTERS_UPDATE_ALL_ASK, addon
        )
        labels = [s.segment_type_label for s in final]
        self.assertIn("intro", labels)
        self.assertIn("recap", labels)
        intro = next(s for s in final if s.segment_type_label == "intro")
        self.assertEqual(intro.end_seconds, 50.0)

    def test_update_without_all_does_not_insert_unmatched(self):
        local = [SegmentItem(0.0, 60.0, "intro", source="edl")]
        online = [
            SegmentItem(0.0, 50.0, "intro", source="theintrodb"),
            SegmentItem(80.0, 100.0, "recap", source="theintrodb"),
        ]
        updated = _update_sidecar_segments(local, online)
        labels = [s.segment_type_label for s in updated]
        self.assertEqual(labels, ["intro"])
        self.assertEqual(updated[0].end_seconds, 50.0)


if __name__ == "__main__":
    unittest.main()
