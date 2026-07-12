# -*- coding: utf-8 -*-
"""Online segments applied toast."""

import unittest
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()


class OnlineSegmentsToastTests(unittest.TestCase):
    @patch("service_loop_toast.xbmcgui.Dialog")
    @patch("service_loop_toast.addon_get_bool", return_value=True)
    @patch("service_loop_toast.get_addon")
    def test_toast_once_when_segments_arrive(self, _addon, _bool, mock_dialog):
        from service_loop_toast import try_show_online_segments_applied_toast

        monitor = MagicMock()
        monitor.online_segments_toast_shown_for_path = None
        ctx = MagicMock()
        ctx.monitor = monitor
        ctx.icon_path = "/icon.png"
        try_show_online_segments_applied_toast(
            ctx, video="/v.mkv", previous_count=0, new_count=3
        )
        mock_dialog.return_value.notification.assert_called_once()
        self.assertEqual(monitor.online_segments_toast_shown_for_path, "/v.mkv")

    @patch("service_loop_toast.xbmcgui.Dialog")
    @patch("service_loop_toast.addon_get_bool", return_value=False)
    @patch("service_loop_toast.get_addon")
    def test_toast_suppressed_when_setting_off(self, _addon, _bool, mock_dialog):
        from service_loop_toast import try_show_online_segments_applied_toast

        monitor = MagicMock()
        ctx = MagicMock()
        ctx.monitor = monitor
        ctx.icon_path = "/icon.png"
        try_show_online_segments_applied_toast(
            ctx, video="/v.mkv", previous_count=0, new_count=3
        )
        mock_dialog.return_value.notification.assert_not_called()

    @patch("service_loop_toast.xbmc.getCondVisibility", return_value=False)
    @patch("service_loop_toast.xbmcgui.Dialog")
    @patch("service_loop_toast.is_deferred_remote_probe_pending", return_value=True)
    def test_missing_toast_suppressed_while_probe_running(
        self, _pending, mock_dialog, _paused
    ):
        from service_loop_toast import try_show_missing_segments_toast

        monitor = MagicMock()
        monitor.playback_ready = True
        monitor.shown_missing_file_toast = False
        monitor.playback_ready_time = 0
        monitor.segment_file_found = False
        ctx = MagicMock()
        ctx.monitor = monitor
        ctx.player.isPlayingVideo.return_value = True
        ctx.both_segment_sources_disabled_for_playback.return_value = False
        try_show_missing_segments_toast(
            ctx,
            video="/v.mkv",
            playback_type="episode",
            toast_movies=False,
            toast_episodes=True,
            current_time=10.0,
        )
        mock_dialog.return_value.notification.assert_not_called()


if __name__ == "__main__":
    unittest.main()
