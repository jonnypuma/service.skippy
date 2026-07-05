# -*- coding: utf-8 -*-
"""Post-seek must not block monitor loop with xbmc.sleep."""

import unittest
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

from segment_item import SegmentItem


class SeekSleepTests(unittest.TestCase):
    @patch("service_loop_skip.xbmc.sleep")
    @patch("service_loop_skip._maybe_show_skip_toast")
    def test_auto_skip_does_not_sleep(self, _toast, mock_sleep):
        import service_loop_skip as mod

        monitor = MagicMock()
        monitor.prompted = set()
        monitor.skipped_to_nested_segment = {}
        monitor.recently_dismissed = set()
        monitor.cleared_parent_dismissals = set()
        player = MagicMock()
        player.isPlaying.return_value = True
        player.getTime.return_value = 100.0
        ctx = MagicMock()
        ctx.monitor = monitor
        ctx.player = player
        seg = SegmentItem(0.0, 60.0, "intro", source="xml")
        addon = MagicMock()
        mod._handle_auto_skip(ctx, seg, (0, 60), 60.0, addon)
        mock_sleep.assert_not_called()

    @patch("service_loop_skip.SkipDialog")
    @patch("service_loop_skip.xbmc.sleep")
    def test_ask_skip_confirm_does_not_sleep(self, mock_sleep, mock_dialog_cls):
        import service_loop_skip as mod

        dialog = MagicMock()
        dialog._skippy_dialog_result = 60.0
        mock_dialog_cls.return_value = dialog
        monitor = MagicMock()
        monitor.prompted = set()
        monitor.skipped_to_nested_segment = {}
        monitor.recently_dismissed = set()
        monitor.cleared_parent_dismissals = set()
        monitor.skip_dialog_modal_active = False
        player = MagicMock()
        player.isPlayingVideo.return_value = True
        ctx = MagicMock()
        ctx.monitor = monitor
        ctx.player = player
        ctx.log_if_changed = MagicMock()
        ctx.skip_dialog_layout_suffix = MagicMock(return_value="BottomRight")
        ctx.warm_skip_dialog_skin_textures = MagicMock()
        seg = SegmentItem(0.0, 60.0, "intro", source="xml")
        addon = MagicMock()
        addon.getAddonInfo.return_value = {"path": "/addon"}
        with patch("service_loop_skip.addon_get_int", return_value=0):
            with patch("service_loop_skip.xbmc.getCondVisibility", return_value=False):
                with patch("service_loop_skip.get_home_window", return_value=MagicMock()):
                    mod._handle_ask_skip(ctx, seg, (0, 60), 60.0, addon)
        sleep_calls = [c for c in mock_sleep.call_args_list if c.args and c.args[0] >= 500]
        self.assertEqual(sleep_calls, [])


if __name__ == "__main__":
    unittest.main()
