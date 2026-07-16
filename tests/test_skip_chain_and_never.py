# -*- coding: utf-8 -*-
"""Never segments stay prompted; ask skips chain without waiting for next tick."""

import unittest
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

from segment_item import SegmentItem


class NeverPromptedTests(unittest.TestCase):
    def test_never_adds_to_prompted(self):
        import service_loop_skip as mod

        monitor = MagicMock()
        monitor.playback_ready = True
        monitor.prompted = set()
        monitor.recently_dismissed = set()
        monitor.skipped_to_nested_segment = {}
        monitor.current_segments = [
            SegmentItem(0.0, 100.0, "main", source="xml"),
        ]
        monitor._last_log_state = {}

        ctx = MagicMock()
        ctx.monitor = monitor
        ctx.log_if_changed = MagicMock()
        ctx.should_suppress_segment_dialog = MagicMock(return_value=False)

        with patch("service_loop_skip.get_addon", return_value=MagicMock()):
            with patch("service_loop_skip.get_user_skip_mode", return_value="never"):
                mod.process_segment_skips(
                    ctx,
                    video="/v.mkv",
                    playback_type="episode",
                    show_dialogs=True,
                    current_time=10.0,
                    major_rewind_detected=False,
                )

        self.assertIn((0, 100), monitor.prompted)


class AskChainTests(unittest.TestCase):
    @patch("service_loop_skip.SkipDialog")
    @patch("service_loop_skip.xbmc.sleep")
    def test_confirmed_ask_chains_next_without_debounce(self, mock_sleep, mock_dialog_cls):
        import service_loop_skip as mod

        recap = SegmentItem(0.0, 65.0, "recap", source="xml")
        intro = SegmentItem(65.0, 127.0, "intro", source="xml")

        dialog = MagicMock()
        dialog._skippy_dialog_result = 65.0
        mock_dialog_cls.return_value = dialog

        monitor = MagicMock()
        monitor.playback_ready = True
        monitor.prompted = set()
        monitor.recently_dismissed = set()
        monitor.skipped_to_nested_segment = {}
        monitor.cleared_parent_dismissals = set()
        monitor.skip_dialog_modal_active = False
        monitor.skippy_skipping_since = 1.0
        monitor.current_segments = [recap, intro]
        monitor._last_log_state = {}

        player = MagicMock()
        player.isPlayingVideo.return_value = True
        player.isPlaying.return_value = True
        player.getTime.return_value = 65.0

        ctx = MagicMock()
        ctx.monitor = monitor
        ctx.player = player
        ctx.icon_path = ""
        ctx.log_if_changed = MagicMock()
        ctx.should_suppress_segment_dialog = MagicMock(return_value=False)
        ctx.is_nested_segment = MagicMock(return_value=False)
        ctx.skip_dialog_layout_suffix = MagicMock(return_value="BottomRight")
        ctx.warm_skip_dialog_skin_textures = MagicMock()

        addon = MagicMock()
        addon.getAddonInfo.return_value = "/addon"

        call_count = {"n": 0}

        def mode_for(label):
            return "ask"

        def dialog_factory(*_a, **kwargs):
            call_count["n"] += 1
            d = MagicMock()
            if call_count["n"] == 1:
                d._skippy_dialog_result = 65.0
            else:
                d._skippy_dialog_result = False
            return d

        mock_dialog_cls.side_effect = dialog_factory

        with patch("service_loop_skip.get_addon", return_value=addon):
            with patch("service_loop_skip.get_user_skip_mode", side_effect=mode_for):
                with patch("service_loop_skip.is_skip_enabled", return_value=True):
                    with patch(
                        "service_loop_skip.compute_skip_seek_destination_seconds",
                        side_effect=lambda seg, _a: float(seg.end_seconds) + 1.0,
                    ):
                        with patch("service_loop_skip.addon_get_int", return_value=300):
                            with patch(
                                "service_loop_skip.addon_get_setting_text",
                                return_value="Full",
                            ):
                                with patch(
                                    "service_loop_skip.addon_get_bool",
                                    return_value=False,
                                ):
                                    with patch(
                                        "service_loop_skip.xbmc.getCondVisibility",
                                        return_value=False,
                                    ):
                                        with patch(
                                            "service_loop_skip.get_home_window",
                                            return_value=MagicMock(),
                                        ):
                                            with patch(
                                                "service_loop_skip.mark_skippy_skipping"
                                            ):
                                                mod.process_segment_skips(
                                                    ctx,
                                                    video="/v.mkv",
                                                    playback_type="episode",
                                                    show_dialogs=True,
                                                    current_time=1.0,
                                                    major_rewind_detected=False,
                                                )

        self.assertEqual(call_count["n"], 2)
        # First dialog debounced; chained intro skips debounce.
        self.assertEqual(mock_sleep.call_count, 1)
        self.assertEqual(mock_sleep.call_args_list[0].args[0], 300)


class ResetKeepsPlaybackCacheTests(unittest.TestCase):
    def test_reset_does_not_clear_playback_context(self):
        import service_loop_playback as mod

        monitor = MagicMock()
        monitor.prompted = set()
        monitor.recently_dismissed = set()
        monitor.cleared_parent_dismissals = set()
        monitor.skipped_to_nested_segment = {}
        monitor._last_log_state = {}
        monitor._playback_context_cache = object()
        monitor._playback_context_video = "/v.mkv"
        monitor.remote_segment_cache = {}

        ctx = MagicMock()
        ctx.monitor = monitor
        ctx.clear_deferred_remote_probe_state = MagicMock()

        with patch("service_loop_playback.clear_segment_processed_cache"):
            with patch("service_loop_playback.publish_parse_cache"):
                with patch("service_loop_playback.clear_tv_prefetch_thread_state"):
                    with patch("service_loop_playback.clear_sidecar_probe_cache"):
                        with patch("service_loop_playback.clear_skippy_skipping"):
                            mod.reset_monitor_playback_state(
                                ctx, log_prefix="✅ New video"
                            )

        self.assertIsNotNone(monitor._playback_context_cache)
        self.assertEqual(monitor._playback_context_video, "/v.mkv")


if __name__ == "__main__":
    unittest.main()
