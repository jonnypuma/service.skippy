# -*- coding: utf-8 -*-
"""Ask guards: just-skipped window, same-seg cooldown, consecutive / nested / overlap."""

import time
import unittest
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

from segment_item import SegmentItem
import service_loop_skip as mod


def _seg_id(seg):
    return (int(round(seg.start_seconds)), int(round(seg.end_seconds)))


def _base_monitor(segments):
    monitor = MagicMock()
    monitor.playback_ready = True
    monitor.prompted = set()
    monitor.recently_dismissed = set()
    monitor.skipped_to_nested_segment = {}
    monitor.cleared_parent_dismissals = set()
    monitor.skip_dialog_modal_active = False
    monitor.skippy_skipping_since = None
    monitor.last_skipped_seg_id = None
    monitor.last_skipped_seg_bounds = None
    monitor.last_ask_seg_id = None
    monitor.last_ask_mono = None
    monitor.current_segments = segments
    monitor._last_log_state = {}
    monitor.last_time = 0
    return monitor


def _base_ctx(monitor, player=None):
    if player is None:
        player = MagicMock()
        player.isPlayingVideo.return_value = True
        player.isPlaying.return_value = True
        player.getTime.return_value = 0.0
    ctx = MagicMock()
    ctx.monitor = monitor
    ctx.player = player
    ctx.icon_path = ""
    ctx.log_if_changed = MagicMock()
    ctx.should_suppress_segment_dialog = MagicMock(return_value=False)
    ctx.is_nested_segment = MagicMock(return_value=False)
    ctx.skip_dialog_layout_suffix = MagicMock(return_value="BottomRight")
    ctx.warm_skip_dialog_skin_textures = MagicMock()
    return ctx


class JustSkippedHelperTests(unittest.TestCase):
    def test_ignore_while_inside_clears_when_outside(self):
        monitor = MagicMock()
        monitor.last_skipped_seg_id = (0, 65)
        monitor.last_skipped_seg_bounds = (0.0, 65.0)
        self.assertTrue(mod.should_ignore_as_just_skipped(monitor, (0, 65), 64.5))
        self.assertFalse(mod.should_ignore_as_just_skipped(monitor, (65, 127), 64.5))
        mod.clear_last_skipped_if_outside(monitor, 66.0)
        self.assertIsNone(monitor.last_skipped_seg_id)
        self.assertIsNone(monitor.last_skipped_seg_bounds)

    def test_ask_cooldown_same_seg_only(self):
        monitor = MagicMock()
        monitor.last_ask_seg_id = (0, 65)
        monitor.last_ask_mono = time.monotonic()
        self.assertTrue(mod.ask_same_seg_on_cooldown(monitor, (0, 65)))
        self.assertFalse(mod.ask_same_seg_on_cooldown(monitor, (65, 127)))
        monitor.last_ask_mono = time.monotonic() - 1.0
        self.assertFalse(mod.ask_same_seg_on_cooldown(monitor, (0, 65)))


class JustSkippedProcessTests(unittest.TestCase):
    def test_blocks_same_seg_auto_while_still_inside(self):
        """Keyframe snap: still inside just-skipped window → no second auto."""
        recap = SegmentItem(0.0, 65.0, "recap", source="xml")
        monitor = _base_monitor([recap])
        # Simulate prompted cleared (e.g. false rewind) but still inside after skip.
        monitor.prompted = set()
        mod.mark_last_skipped_segment(monitor, recap, _seg_id(recap))

        ctx = _base_ctx(monitor)
        player = ctx.player
        player.getTime.return_value = 64.0

        with patch("service_loop_skip.get_addon", return_value=MagicMock()):
            with patch("service_loop_skip.get_user_skip_mode", return_value="auto"):
                with patch("service_loop_skip.is_skip_enabled", return_value=True):
                    with patch(
                        "service_loop_skip.compute_skip_seek_destination_seconds",
                        return_value=65.0,
                    ):
                        with patch("service_loop_skip.mark_skippy_skipping") as mskip:
                            mod.process_segment_skips(
                                ctx,
                                video="/v.mkv",
                                playback_type="episode",
                                show_dialogs=True,
                                current_time=64.0,
                                major_rewind_detected=False,
                            )
        player.seekTime.assert_not_called()
        mskip.assert_not_called()

    def test_consecutive_abutting_allows_next_segment(self):
        """Recap just-skipped at boundary; intro (different id) still processes."""
        recap = SegmentItem(0.0, 65.0, "recap", source="xml")
        intro = SegmentItem(65.0, 127.0, "intro", source="xml")
        monitor = _base_monitor([recap, intro])
        mod.mark_last_skipped_segment(monitor, recap, _seg_id(recap))
        # Still exactly at recap end (inside bounds) — intro must still run.
        monitor.prompted = {_seg_id(recap)}

        dialog = MagicMock()
        dialog._skippy_dialog_result = False

        ctx = _base_ctx(monitor)
        addon = MagicMock()
        addon.getAddonInfo.return_value = "/addon"

        with patch("service_loop_skip.get_addon", return_value=addon):
            with patch(
                "service_loop_skip.get_user_skip_mode",
                side_effect=lambda lab: "ask",
            ):
                with patch("service_loop_skip.is_skip_enabled", return_value=True):
                    with patch(
                        "service_loop_skip.compute_skip_seek_destination_seconds",
                        side_effect=lambda seg, _a: float(seg.end_seconds) + 1.0,
                    ):
                        with patch("service_loop_skip.SkipDialog", return_value=dialog):
                            with patch(
                                "service_loop_skip.addon_get_int", return_value=0
                            ):
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
                                                mod.process_segment_skips(
                                                    ctx,
                                                    video="/v.mkv",
                                                    playback_type="episode",
                                                    show_dialogs=True,
                                                    current_time=65.0,
                                                    major_rewind_detected=False,
                                                )

        dialog.doModal.assert_called_once()
        self.assertIn(_seg_id(intro), monitor.prompted)

    def test_nested_different_id_not_blocked_by_parent_just_skipped(self):
        parent = SegmentItem(0.0, 200.0, "recap", source="xml")
        nested = SegmentItem(50.0, 80.0, "intro", source="xml")
        monitor = _base_monitor([parent, nested])
        mod.mark_last_skipped_segment(monitor, parent, _seg_id(parent))
        monitor.prompted = {_seg_id(parent)}

        dialog = MagicMock()
        dialog._skippy_dialog_result = False
        ctx = _base_ctx(monitor)
        # Nested has priority; don't suppress nested for this test.
        ctx.should_suppress_segment_dialog = MagicMock(return_value=False)
        addon = MagicMock()
        addon.getAddonInfo.return_value = "/addon"

        with patch("service_loop_skip.get_addon", return_value=addon):
            with patch("service_loop_skip.get_user_skip_mode", return_value="ask"):
                with patch("service_loop_skip.is_skip_enabled", return_value=True):
                    with patch(
                        "service_loop_skip.compute_skip_seek_destination_seconds",
                        side_effect=lambda seg, _a: float(seg.end_seconds) + 1.0,
                    ):
                        with patch("service_loop_skip.SkipDialog", return_value=dialog):
                            with patch(
                                "service_loop_skip.addon_get_int", return_value=0
                            ):
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
                                                mod.process_segment_skips(
                                                    ctx,
                                                    video="/v.mkv",
                                                    playback_type="episode",
                                                    show_dialogs=True,
                                                    current_time=60.0,
                                                    major_rewind_detected=False,
                                                )

        dialog.doModal.assert_called_once()
        self.assertIn(_seg_id(nested), monitor.prompted)

    def test_overlapping_different_ids(self):
        """Just-skipped A still inside; overlapping B can still ask."""
        a = SegmentItem(0.0, 100.0, "recap", source="xml")
        b = SegmentItem(80.0, 150.0, "intro", source="xml")
        monitor = _base_monitor([a, b])
        mod.mark_last_skipped_segment(monitor, a, _seg_id(a))
        monitor.prompted = {_seg_id(a)}

        dialog = MagicMock()
        dialog._skippy_dialog_result = False
        ctx = _base_ctx(monitor)
        addon = MagicMock()
        addon.getAddonInfo.return_value = "/addon"

        with patch("service_loop_skip.get_addon", return_value=addon):
            with patch("service_loop_skip.get_user_skip_mode", return_value="ask"):
                with patch("service_loop_skip.is_skip_enabled", return_value=True):
                    with patch(
                        "service_loop_skip.compute_skip_seek_destination_seconds",
                        side_effect=lambda seg, _a: float(seg.end_seconds) + 1.0,
                    ):
                        with patch("service_loop_skip.SkipDialog", return_value=dialog):
                            with patch(
                                "service_loop_skip.addon_get_int", return_value=0
                            ):
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
                                                mod.process_segment_skips(
                                                    ctx,
                                                    video="/v.mkv",
                                                    playback_type="episode",
                                                    show_dialogs=True,
                                                    current_time=90.0,
                                                    major_rewind_detected=False,
                                                )

        dialog.doModal.assert_called_once()
        self.assertIn(_seg_id(b), monitor.prompted)


class AskCooldownProcessTests(unittest.TestCase):
    @patch("service_loop_skip.SkipDialog")
    def test_same_seg_refused_within_300ms(self, mock_dialog_cls):
        intro = SegmentItem(0.0, 100.0, "intro", source="xml")
        monitor = _base_monitor([intro])
        monitor.last_ask_seg_id = _seg_id(intro)
        monitor.last_ask_mono = time.monotonic()

        ctx = _base_ctx(monitor)
        addon = MagicMock()
        addon.getAddonInfo.return_value = "/addon"

        with patch("service_loop_skip.get_addon", return_value=addon):
            with patch("service_loop_skip.get_user_skip_mode", return_value="ask"):
                with patch("service_loop_skip.is_skip_enabled", return_value=True):
                    with patch(
                        "service_loop_skip.compute_skip_seek_destination_seconds",
                        return_value=101.0,
                    ):
                        with patch(
                            "service_loop_skip.xbmc.getCondVisibility",
                            return_value=False,
                        ):
                            with patch(
                                "service_loop_skip.get_home_window",
                                return_value=MagicMock(),
                            ):
                                mod.process_segment_skips(
                                    ctx,
                                    video="/v.mkv",
                                    playback_type="episode",
                                    show_dialogs=True,
                                    current_time=10.0,
                                    major_rewind_detected=False,
                                )

        mock_dialog_cls.assert_not_called()

    @patch("service_loop_skip.xbmc.sleep")
    @patch("service_loop_skip.SkipDialog")
    def test_debounce_default_zero_skips_sleep(self, mock_dialog_cls, mock_sleep):
        intro = SegmentItem(0.0, 100.0, "intro", source="xml")
        monitor = _base_monitor([intro])
        dialog = MagicMock()
        dialog._skippy_dialog_result = False
        mock_dialog_cls.return_value = dialog
        ctx = _base_ctx(monitor)
        addon = MagicMock()
        addon.getAddonInfo.return_value = "/addon"

        with patch("service_loop_skip.get_addon", return_value=addon):
            with patch("service_loop_skip.get_user_skip_mode", return_value="ask"):
                with patch("service_loop_skip.is_skip_enabled", return_value=True):
                    with patch(
                        "service_loop_skip.compute_skip_seek_destination_seconds",
                        return_value=101.0,
                    ):
                        with patch(
                            "service_loop_skip.addon_get_int", return_value=0
                        ):
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
                                            mod.process_segment_skips(
                                                ctx,
                                                video="/v.mkv",
                                                playback_type="episode",
                                                show_dialogs=True,
                                                current_time=10.0,
                                                major_rewind_detected=False,
                                            )

        mock_sleep.assert_not_called()
        dialog.doModal.assert_called_once()


class AskChainUpdatedTests(unittest.TestCase):
    @patch("service_loop_skip.SkipDialog")
    @patch("service_loop_skip.xbmc.sleep")
    def test_confirmed_ask_chains_next_no_sleep_when_debounce_zero(
        self, mock_sleep, mock_dialog_cls
    ):
        recap = SegmentItem(0.0, 65.0, "recap", source="xml")
        intro = SegmentItem(65.0, 127.0, "intro", source="xml")

        monitor = _base_monitor([recap, intro])
        monitor.skippy_skipping_since = 1.0

        player = MagicMock()
        player.isPlayingVideo.return_value = True
        player.isPlaying.return_value = True
        player.getTime.return_value = 65.0
        ctx = _base_ctx(monitor, player)

        call_count = {"n": 0}

        def dialog_factory(*_a, **kwargs):
            call_count["n"] += 1
            d = MagicMock()
            if call_count["n"] == 1:
                d._skippy_dialog_result = 65.0
            else:
                d._skippy_dialog_result = False
            return d

        mock_dialog_cls.side_effect = dialog_factory
        addon = MagicMock()
        addon.getAddonInfo.return_value = "/addon"

        with patch("service_loop_skip.get_addon", return_value=addon):
            with patch("service_loop_skip.get_user_skip_mode", return_value="ask"):
                with patch("service_loop_skip.is_skip_enabled", return_value=True):
                    with patch(
                        "service_loop_skip.compute_skip_seek_destination_seconds",
                        side_effect=lambda seg, _a: float(seg.end_seconds) + 1.0,
                    ):
                        with patch(
                            "service_loop_skip.addon_get_int", return_value=0
                        ):
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
        mock_sleep.assert_not_called()
        # Seek lands past recap end → just-skipped cleared on chain re-entry.
        self.assertIsNone(monitor.last_skipped_seg_id)
        self.assertIn(_seg_id(recap), monitor.prompted)
        self.assertIn(_seg_id(intro), monitor.prompted)


if __name__ == "__main__":
    unittest.main()
