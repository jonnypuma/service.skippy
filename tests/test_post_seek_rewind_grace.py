# -*- coding: utf-8 -*-
"""False rewind after Skippy seek must not clear prompted / reopen ask dialog."""

import unittest
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()


class PostSeekRewindGraceTests(unittest.TestCase):
    def test_rewind_suppressed_during_skippy_seek_grace(self):
        import service_loop_nested as mod

        monitor = MagicMock()
        monitor.last_time = 720.665
        monitor.prompted = {(622, 720)}
        monitor.recently_dismissed = set()
        monitor.cleared_parent_dismissals = set()
        monitor.skipped_to_nested_segment = {}
        monitor.current_segments = []
        monitor.skippy_skipping_since = 1.0  # grace active

        player = MagicMock()
        player.isPlayingVideo.return_value = True

        ctx = MagicMock()
        ctx.monitor = monitor
        ctx.player = player
        ctx.re_evaluate_segment_jump_points = MagicMock()

        with patch("service_loop_nested.get_addon", return_value=MagicMock()):
            with patch("service_loop_nested.addon_get_int", return_value=8):
                with patch(
                    "service_loop_nested.xbmc.getCondVisibility", return_value=False
                ):
                    with patch(
                        "service_loop_nested.clear_segment_processed_cache"
                    ) as clear_cache:
                        major = mod.handle_rewind_and_nested_segments(ctx, 635.17)

        self.assertFalse(major)
        self.assertIn((622, 720), monitor.prompted)
        clear_cache.assert_not_called()

    def test_rewind_still_clears_without_grace(self):
        import service_loop_nested as mod

        monitor = MagicMock()
        monitor.last_time = 720.665
        monitor.prompted = {(622, 720)}
        monitor.recently_dismissed = set()
        monitor.cleared_parent_dismissals = set()
        monitor.skipped_to_nested_segment = {}
        monitor.current_segments = []
        monitor.skippy_skipping_since = None

        player = MagicMock()
        player.isPlayingVideo.return_value = True

        ctx = MagicMock()
        ctx.monitor = monitor
        ctx.player = player
        ctx.re_evaluate_segment_jump_points = MagicMock()

        with patch("service_loop_nested.get_addon", return_value=MagicMock()):
            with patch("service_loop_nested.addon_get_int", return_value=8):
                with patch(
                    "service_loop_nested.xbmc.getCondVisibility", return_value=False
                ):
                    with patch("service_loop_nested.clear_segment_processed_cache"):
                        major = mod.handle_rewind_and_nested_segments(ctx, 635.17)

        self.assertTrue(major)
        self.assertEqual(len(monitor.prompted), 0)


if __name__ == "__main__":
    unittest.main()
