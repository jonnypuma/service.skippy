# -*- coding: utf-8 -*-
"""What a new video (or a replay) clears, and what it keeps for the steps after the reset."""

import types
import unittest

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

from next_episode_state import NextEpisodeState  # noqa: E402
from service_playback_state import init_playback_session, reset_playback_session  # noqa: E402


def _reset(monitor):
    reset_playback_session(
        monitor, clear_deferred=lambda _m: None, log_prefix="test", log_fn=lambda *_a: None
    )


class PlaybackSessionResetTests(unittest.TestCase):
    def setUp(self):
        self.monitor = types.SimpleNamespace()
        init_playback_session(self.monitor)

    def test_the_segments_of_the_old_video_are_dropped(self):
        self.monitor.current_segments = ["credits of the episode before"]
        _reset(self.monitor)
        self.assertEqual(self.monitor.current_segments, [])

    def test_the_next_episode_state_is_kept_aside_for_one_look(self):
        state = NextEpisodeState(video="e1.mkv")
        self.monitor.next_episode_state = state
        _reset(self.monitor)
        self.assertIsNone(self.monitor.next_episode_state)
        self.assertIs(self.monitor.next_episode_previous, state)

    def test_a_second_reset_keeps_the_state_it_already_set_aside(self):
        state = NextEpisodeState(video="e1.mkv")
        self.monitor.next_episode_state = state
        _reset(self.monitor)
        _reset(self.monitor)
        self.assertIs(self.monitor.next_episode_previous, state)


if __name__ == "__main__":
    unittest.main()
