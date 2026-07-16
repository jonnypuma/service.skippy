# -*- coding: utf-8 -*-
"""Pause during online lookup helper."""

import unittest
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()


class OnlineLookupPauseTests(unittest.TestCase):
    @patch("service_online_lookup_pause.xbmc")
    @patch("service_online_lookup_pause.pause_during_online_lookup_enabled", return_value=True)
    def test_pauses_active_playback(self, _en, mock_xbmc):
        from service_online_lookup_pause import (
            pause_playback_for_online_lookup,
            resume_playback_after_online_lookup,
            run_blocking_online_lookup,
        )

        mock_xbmc.getCondVisibility.side_effect = [False, True, True]
        player = MagicMock()
        player.isPlayingVideo.return_value = True

        we_paused = pause_playback_for_online_lookup(player)
        self.assertTrue(we_paused)
        player.pause.assert_called_once()

        resume_playback_after_online_lookup(player, we_paused)
        self.assertEqual(player.pause.call_count, 2)

    @patch("service_online_lookup_pause.pause_during_online_lookup_enabled", return_value=False)
    def test_skips_pause_when_disabled(self, _en):
        from service_online_lookup_pause import pause_playback_for_online_lookup

        player = MagicMock()
        player.isPlayingVideo.return_value = True
        self.assertFalse(pause_playback_for_online_lookup(player))
        player.pause.assert_not_called()

    @patch("service_online_lookup_pause.resume_playback_after_online_lookup")
    @patch("service_online_lookup_pause.pause_playback_for_online_lookup", return_value=True)
    def test_run_blocking_wraps_fetch(self, _pause, _resume):
        from service_online_lookup_pause import run_blocking_online_lookup

        player = MagicMock()
        result = run_blocking_online_lookup(player, lambda: ["seg"])
        self.assertEqual(result, ["seg"])
        _pause.assert_called_once_with(player)
        _resume.assert_called_once_with(player, True)


if __name__ == "__main__":
    unittest.main()
