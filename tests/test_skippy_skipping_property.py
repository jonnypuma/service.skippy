# -*- coding: utf-8 -*-
import time
import unittest
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import install_kodi_stubs


class SkippySkippingPropertyTests(unittest.TestCase):
    def setUp(self):
        install_kodi_stubs()

    def test_mark_sets_property(self):
        from service_skip_seek_property import (
            SKIPPY_SKIPPING_PROPERTY,
            mark_skippy_skipping,
        )

        home = MagicMock()
        monitor = MagicMock()
        monitor._home_window = home
        monitor.skippy_skipping_since = None
        addon = MagicMock()
        with patch(
            "service_skip_seek_property.addon_get_bool", return_value=True
        ):
            mark_skippy_skipping(monitor, addon)
        home.setProperty.assert_called_once_with(SKIPPY_SKIPPING_PROPERTY, "true")
        self.assertIsNotNone(monitor.skippy_skipping_since)

    @patch("service_skip_seek_property.addon_get_bool", return_value=False)
    def test_mark_respects_setting_off(self, _bool):
        from service_skip_seek_property import mark_skippy_skipping

        home = MagicMock()
        monitor = MagicMock()
        monitor._home_window = home
        monitor.skippy_skipping_since = None
        mark_skippy_skipping(monitor, MagicMock())
        home.setProperty.assert_not_called()
        self.assertIsNone(monitor.skippy_skipping_since)

    def test_maybe_clear_waits_for_min_duration(self):
        from service_skip_seek_property import maybe_clear_skippy_skipping

        home = MagicMock()
        home.getProperty.return_value = "true"
        monitor = MagicMock()
        monitor._home_window = home
        monitor.skippy_skipping_since = time.monotonic()
        with patch(
            "service_skip_seek_property.xbmc.getCondVisibility", return_value=False
        ):
            maybe_clear_skippy_skipping(monitor)
        home.clearProperty.assert_not_called()
        self.assertIsNotNone(monitor.skippy_skipping_since)

    def test_maybe_clear_after_settle(self):
        from service_skip_seek_property import (
            SKIPPY_SKIPPING_PROPERTY,
            maybe_clear_skippy_skipping,
        )

        home = MagicMock()
        monitor = MagicMock()
        monitor._home_window = home
        monitor.skippy_skipping_since = time.monotonic() - 5.5
        with patch(
            "service_skip_seek_property.xbmc.getCondVisibility", return_value=False
        ):
            maybe_clear_skippy_skipping(monitor)
        home.clearProperty.assert_called_with(SKIPPY_SKIPPING_PROPERTY)
        self.assertIsNone(monitor.skippy_skipping_since)

    def test_maybe_clear_waits_while_has_performed_seek(self):
        from service_skip_seek_property import maybe_clear_skippy_skipping

        home = MagicMock()
        monitor = MagicMock()
        monitor._home_window = home
        monitor.skippy_skipping_since = time.monotonic() - 6.0
        with patch(
            "service_skip_seek_property.xbmc.getCondVisibility", return_value=True
        ):
            maybe_clear_skippy_skipping(monitor)
        home.clearProperty.assert_not_called()
        self.assertIsNotNone(monitor.skippy_skipping_since)

    def test_tick_force_clear_when_not_playing(self):
        from service_skip_seek_property import (
            SKIPPY_SKIPPING_PROPERTY,
            tick_skippy_skipping_property,
        )

        home = MagicMock()
        monitor = MagicMock()
        monitor._home_window = home
        monitor.skippy_skipping_since = time.monotonic()
        tick_skippy_skipping_property(monitor, playing=False)
        home.clearProperty.assert_called_with(SKIPPY_SKIPPING_PROPERTY)
        self.assertIsNone(monitor.skippy_skipping_since)

    @patch("service_loop_skip.mark_skippy_skipping")
    @patch("service_loop_skip._maybe_show_skip_toast")
    def test_auto_skip_marks_before_seek(self, _toast, mock_mark):
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
        seg = MagicMock()
        seg.segment_type_label = "intro"
        seg.next_segment_start = None
        addon = MagicMock()

        call_order = []
        mock_mark.side_effect = lambda *_a, **_k: call_order.append("mark")
        player.seekTime.side_effect = lambda *_a, **_k: call_order.append("seek")

        mod._handle_auto_skip(ctx, seg, (0, 60), 60.0, addon)
        self.assertEqual(call_order[:2], ["mark", "seek"])
        mock_mark.assert_called_once_with(monitor, addon)
        player.seekTime.assert_called_once_with(60.0)


if __name__ == "__main__":
    unittest.main()
