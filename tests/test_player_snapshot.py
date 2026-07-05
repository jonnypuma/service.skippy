# -*- coding: utf-8 -*-
"""Player snapshot reuse for JSON-RPC deduplication."""

import unittest
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

from service_player_snapshot import PlayerSnapshot, capture_player_snapshot, snapshot_matches_path


class PlayerSnapshotTests(unittest.TestCase):
    def test_snapshot_matches_path(self):
        snap = capture_player_snapshot(1, {"file": "/a.mkv"}, "/a.mkv")
        self.assertTrue(snapshot_matches_path(snap, "/a.mkv"))
        self.assertFalse(snapshot_matches_path(snap, "/b.mkv"))

    @patch("remote_segments.jsonrpc")
    @patch("remote_segments.get_active_video_player_id")
    def test_enriched_playing_item_reuses_snapshot_player_id(
        self, mock_active, mock_jsonrpc
    ):
        import remote_segments as mod

        snap = PlayerSnapshot(
            player_id=1,
            item={"file": "/a.mkv", "type": "episode", "id": 1, "uniqueid": {"tvdb": "1"}},
            video_path="/a.mkv",
        )
        item = mod.get_enriched_playing_item(snapshot=snap)
        self.assertIsNotNone(item)
        mock_active.assert_not_called()
        mock_jsonrpc.assert_not_called()


if __name__ == "__main__":
    unittest.main()
