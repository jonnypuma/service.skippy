# -*- coding: utf-8 -*-
"""Live TV / IPTV playback must not be statted or sent through the skip loop."""

import types
import unittest
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import import_fresh, install_kodi_stubs


class UnskippablePathTests(unittest.TestCase):
    def setUp(self):
        install_kodi_stubs()
        self.mod = import_fresh("settings_utils")

    def test_stream_urls_are_unskippable(self):
        for path in (
            "http://dispatcharr.local/proxy/12",
            "HTTPS://cdn.example/live.m3u8",
            "pvr://channels/tv/All channels/1",
            "rtp://239.1.1.1:1234",
            "rtsp://cam/stream",
            "rtmp://live/app",
            "udp://239.0.0.1:5000",
            "mmsh://radio/stream",
            "mms://radio/stream",
            "plugin://pvr.iptvsimple/?id=1",
        ):
            with self.subTest(path=path):
                self.assertTrue(self.mod.playback_path_is_unskippable(path))
                self.assertTrue(self.mod.skippy_ignores_playback(path))

    def test_local_and_share_paths_stay_skippable(self):
        for path in (
            "smb://nas/shows/Episode.mkv",
            "nfs://nas/movie.mkv",
            "/storage/videos/movie.mkv",
            "special://profile/file.mkv",
        ):
            with self.subTest(path=path):
                self.assertFalse(self.mod.playback_path_is_unskippable(path))
                self.assertFalse(self.mod.skippy_ignores_playback(path))

    def test_live_tv_condition_ignores_playback_before_a_path_exists(self):
        def _cond(cond):
            return cond == "PVR.IsPlayingTV"

        with patch.object(self.mod.xbmc, "getCondVisibility", side_effect=_cond):
            self.assertTrue(self.mod.is_live_tv_playback())
            self.assertTrue(self.mod.skippy_ignores_playback())
            self.assertTrue(self.mod.skippy_ignores_playback("smb://nas/movie.mkv"))


class QuietVideoPathTests(unittest.TestCase):
    def setUp(self):
        install_kodi_stubs()
        self.mod = import_fresh("service_playback_context")

    def test_http_url_is_not_statted(self):
        player = MagicMock()
        player.isPlayingVideo.return_value = True
        player.getPlayingFile.return_value = "http://dispatcharr/live/1"
        with patch.object(self.mod.xbmcvfs, "exists") as exists:
            exists.return_value = True
            self.assertIsNone(self.mod._quiet_video_path(player))
        exists.assert_not_called()

    def test_live_tv_does_not_read_the_playing_file(self):
        player = MagicMock()
        player.isPlayingVideo.return_value = True
        player.getPlayingFile.return_value = "http://dispatcharr/live/1"

        def _cond(cond):
            return cond == "VideoPlayer.Content(livetv)"

        with patch.object(self.mod.xbmc, "getCondVisibility", side_effect=_cond):
            with patch.object(self.mod.xbmcvfs, "exists") as exists:
                self.assertIsNone(self.mod._quiet_video_path(player))
        player.getPlayingFile.assert_not_called()
        exists.assert_not_called()

    def test_local_file_still_uses_exists(self):
        player = MagicMock()
        player.isPlayingVideo.return_value = True
        player.getPlayingFile.return_value = "smb://nas/movie.mkv"
        with patch.object(self.mod.xbmc, "getCondVisibility", return_value=False):
            with patch.object(self.mod.xbmcvfs, "exists", return_value=True) as exists:
                self.assertEqual(self.mod._quiet_video_path(player), "smb://nas/movie.mkv")
        exists.assert_called_once_with("smb://nas/movie.mkv")


class ServiceVideoFileTests(unittest.TestCase):
    def setUp(self):
        install_kodi_stubs()
        with patch("service_main_loop.run_service_main_loop", lambda _ctx: None):
            self.service = import_fresh("service")

    def test_http_url_is_not_statted(self):
        self.service.player = MagicMock()
        self.service.player.isPlayingVideo.return_value = True
        self.service.player.getPlayingFile.return_value = "http://dispatcharr/live/1"
        with patch.object(self.service.xbmcvfs, "exists", return_value=True) as exists:
            self.assertIsNone(self.service.get_video_file())
        exists.assert_not_called()

    def test_local_file_still_uses_exists(self):
        self.service.player = MagicMock()
        self.service.player.isPlayingVideo.return_value = True
        self.service.player.getPlayingFile.return_value = "smb://nas/movie.mkv"
        with patch.object(self.service.xbmc, "getCondVisibility", return_value=False):
            with patch.object(self.service.xbmcvfs, "exists", return_value=True) as exists:
                self.assertEqual(self.service.get_video_file(), "smb://nas/movie.mkv")
        exists.assert_called_once_with("smb://nas/movie.mkv")


class EditorVideoFileTests(unittest.TestCase):
    def setUp(self):
        install_kodi_stubs()
        self.mod = import_fresh("segment_editor_utils")

    def test_http_url_is_not_statted(self):
        player = MagicMock()
        player.isPlayingVideo.return_value = True
        player.getPlayingFile.return_value = "https://dispatcharr/live/2"
        with patch.object(self.mod.xbmc, "Player", return_value=player):
            with patch.object(self.mod.xbmcvfs, "exists", return_value=True) as exists:
                self.assertIsNone(self.mod.get_video_file())
        exists.assert_not_called()


class LiveTvLoopTests(unittest.TestCase):
    def test_live_tv_skips_playback_refresh(self):
        install_kodi_stubs()
        import service_main_loop
        from service_main_loop import ServiceLoopBindings, run_service_main_loop

        monitor = MagicMock()
        monitor.abortRequested.side_effect = [False, True]
        monitor.waitForAbort.return_value = False
        player = MagicMock()
        player.isPlayingVideo.return_value = True
        noop = lambda *a, **k: None
        ctx = ServiceLoopBindings(
            monitor=monitor,
            player=player,
            check_interval=1,
            icon_path="",
            get_video_file=MagicMock(return_value="http://dispatcharr/live/1"),
            skippy_skip_ui_suppression_state=lambda _win: types.SimpleNamespace(
                suppress=False, pending_marker_blocks=False
            ),
            log_if_changed=noop,
            infer_playback_type=lambda *a, **k: "movie",
            should_show_missing_file_toast=lambda *a, **k: False,
            both_segment_sources_disabled_for_playback=lambda *a, **k: False,
            missing_segments_toast_message=lambda *a, **k: "",
            parse_and_process_segments=lambda *a, **k: [],
            should_suppress_segment_dialog=lambda *a, **k: False,
            re_evaluate_segment_jump_points=noop,
            is_nested_segment=lambda *a, **k: False,
            skip_dialog_layout_suffix=lambda *a, **k: "BottomRight",
            warm_skip_dialog_skin_textures=noop,
            process_deferred_remote_probe=noop,
            clear_deferred_remote_probe_state=noop,
        )

        with patch.object(service_main_loop, "is_live_tv_playback", return_value=True):
            with patch.object(service_main_loop, "refresh_playback_context") as refresh:
                with patch.object(service_main_loop, "process_segment_skips") as skips:
                    run_service_main_loop(ctx)

        refresh.assert_not_called()
        skips.assert_not_called()
        ctx.get_video_file.assert_not_called()


if __name__ == "__main__":
    unittest.main()
