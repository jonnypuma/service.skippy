# -*- coding: utf-8 -*-
import importlib
import unittest
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import install_kodi_stubs


class PlaybackContextTests(unittest.TestCase):
    def setUp(self):
        install_kodi_stubs()
        self.mod = importlib.import_module("service_playback_context")

    def test_pause_fast_path_skips_jsonrpc(self):
        monitor = MagicMock()
        monitor._playback_context_cache = self.mod.PlaybackContext(
            video_path="/v/a.mkv",
            playback_type="episode",
            toast_allowed=False,
            show_dialogs=True,
            toast_movies=False,
            toast_episodes=True,
            player_item={"showtitle": "Show"},
        )
        monitor._playback_context_video = "/v/a.mkv"

        player = MagicMock()
        player.isPlayingVideo.return_value = True
        player.getTime.return_value = 42.0

        ctx = MagicMock()
        ctx.player = player
        ctx.monitor = monitor
        ctx.log_if_changed = MagicMock()
        ctx.infer_playback_type = MagicMock(return_value="episode")
        ctx.get_video_file = MagicMock()

        with patch("xbmc.getCondVisibility", return_value=True):
            with patch.object(
                self.mod, "_quiet_video_path", return_value="/v/a.mkv"
            ):
                with patch.object(self.mod, "_fetch_player_item_via_jsonrpc") as rpc:
                    result = self.mod.refresh_playback_context(ctx)

        self.assertTrue(result.used_pause_fast_path)
        rpc.assert_not_called()
        ctx.get_video_file.assert_not_called()

    def test_video_change_fetches_jsonrpc(self):
        monitor = MagicMock()
        monitor._playback_context_cache = None
        monitor._playback_context_video = None

        player = MagicMock()
        player.isPlayingVideo.return_value = True
        player.getTime.return_value = 10.0

        ctx = MagicMock()
        ctx.player = player
        ctx.monitor = monitor
        ctx.log_if_changed = MagicMock()
        ctx.infer_playback_type = MagicMock(return_value="movie")
        ctx.get_video_file = MagicMock(return_value="/v/new.mkv")

        with patch("xbmc.getCondVisibility", return_value=False):
            with patch.object(
                self.mod,
                "_fetch_player_item_via_jsonrpc",
                return_value=({"title": "Film"}, True, 1),
            ) as rpc:
                with patch.object(self.mod, "get_addon", return_value=MagicMock()):
                    with patch.object(self.mod, "addon_get_bool", return_value=False):
                        with patch.object(
                            self.mod, "is_skip_dialog_enabled", return_value=True
                        ):
                            result = self.mod.refresh_playback_context(ctx)

        self.assertFalse(result.used_pause_fast_path)
        rpc.assert_called_once()
        self.assertEqual(result.video_path, "/v/new.mkv")


if __name__ == "__main__":
    unittest.main()
