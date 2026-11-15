# -*- coding: utf-8 -*-
"""The skin's own next episode popup: answers, button presses, texts and the Home properties."""

import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import next_episode_skin as skin  # noqa: E402
import skin_properties as sp  # noqa: E402
from next_episode_state import TIMED_OUT  # noqa: E402

NEXT = {"source": "library", "episodeid": 3, "title": "The Return", "showtitle": "Arrow",
        "season": 2, "episode": 5, "thumb": "image://t.jpg/", "plot": "Oliver comes home."}
MOVIE = {"source": "movie", "title": "Dune: Part Two", "year": 2024, "season": None,
         "episode": None, "showtitle": "", "thumb": ""}


def _addon():
    addon = MagicMock()
    addon.getLocalizedString.return_value = ""
    return addon


def _prompt(**kw):
    values = dict(begin=100.0, end=145.0, timed=False, end_action="Close", still_watching=False)
    values.update(kw)
    return skin.SkinPrompt(**values)


class AnswerTests(unittest.TestCase):
    def test_buttons(self):
        self.assertIs(skin.prompt_answer(_prompt(), 110, skin.REQUEST_PLAY), True)
        self.assertIs(skin.prompt_answer(_prompt(), 110, skin.REQUEST_CLOSE), False)
        self.assertIsNone(skin.prompt_answer(_prompt(), 110, None))
        self.assertIsNone(skin.prompt_answer(_prompt(), "x", None))

    def test_running_out(self):
        self.assertEqual(skin.prompt_answer(_prompt(timed=True, end=120), 120, None), TIMED_OUT)
        self.assertEqual(skin.prompt_answer(_prompt(end_action="Play"), 144.0, None), TIMED_OUT)
        self.assertEqual(skin.prompt_answer(_prompt(), 144.0, None), skin.ENDED)
        self.assertIsNone(skin.prompt_answer(_prompt(), 143.9, None))
        sw = _prompt(still_watching=True, end_action="Play")
        self.assertEqual(skin.prompt_answer(sw, 144.0, None), skin.ENDED)

    def test_requests_are_taken_once_and_expire(self):
        monitor = SimpleNamespace()
        self.assertIsNone(skin.take_request(monitor))
        with patch.object(skin.time, "monotonic", return_value=50.0):
            skin.request_next_episode(monitor, skin.REQUEST_PLAY)
        self.assertEqual(skin.take_request(monitor, now=52.0), skin.REQUEST_PLAY)
        self.assertIsNone(skin.take_request(monitor, now=52.0))
        with patch.object(skin.time, "monotonic", return_value=50.0):
            skin.request_next_episode(monitor, skin.REQUEST_CLOSE)
        self.assertIsNone(skin.take_request(monitor, now=50.0 + skin.REQUEST_MAX_AGE_S + 1))
        skin.request_next_episode(monitor, "bogus")
        self.assertIsNone(getattr(monitor, "next_episode_request"))
        skin.request_next_episode(None, skin.REQUEST_PLAY)

    def test_handshake(self):
        win = MagicMock()
        win.getProperty.return_value = "True"
        self.assertTrue(skin.skin_draws_next_episode(win))
        win.getProperty.return_value = ""
        self.assertFalse(skin.skin_draws_next_episode(win))
        self.assertFalse(skin.skin_draws_next_episode(None))


class TextTests(unittest.TestCase):
    def test_play_next_texts_and_countdown(self):
        prompt = skin.build_prompt(_addon(), NEXT, 100, 145, False, "Close", False)
        self.assertEqual(prompt.heading, "Play next episode?")
        self.assertEqual(prompt.label, "S02E05 · The Return")
        self.assertEqual((prompt.play_label, prompt.close_label), ("Play now", "Close"))
        skin.update_countdown(prompt, _addon(), 118.0)
        self.assertEqual(prompt.countdown, "Episode ends in 00:27")
        self.assertEqual((prompt.seconds_left, prompt.progress), (27, 40))

    def test_still_watching_and_timed_countdowns(self):
        prompt = skin.build_prompt(_addon(), NEXT, 100, 145, True, "Play", True)
        self.assertEqual(prompt.heading, "Still watching?")
        self.assertEqual((prompt.play_label, prompt.close_label), ("Continue", "Stop"))
        self.assertFalse(prompt.timed)
        timed = skin.build_prompt(_addon(), NEXT, 100, 120, True, "Play", False)
        skin.update_countdown(timed, _addon(), 110.0)
        self.assertEqual(timed.countdown, "Next episode starts in 00:10")
        closing = skin.build_prompt(_addon(), NEXT, 100, 120, True, "Close", False)
        skin.update_countdown(closing, _addon(), 110.0)
        self.assertEqual(closing.countdown, "Closing in 00:10")

    def test_movie(self):
        prompt = skin.build_prompt(_addon(), MOVIE, 100, 145, False, "Close", False)
        self.assertEqual(prompt.heading, "Play next movie?")
        skin.update_countdown(prompt, _addon(), 100.0, movie=True)
        self.assertEqual(prompt.countdown, "Movie ends in 00:45")


class PropertyTests(unittest.TestCase):
    def props(self, item, prompt=None):
        monitor = SimpleNamespace(next_episode_state=SimpleNamespace(next_item=item, skin_prompt=prompt))
        return sp.build_skin_properties([], 0, monitor=monitor)

    def test_next_episode_details(self):
        props = self.props(NEXT)
        self.assertEqual(props["Skippy.NextEpisode.Title"], "The Return")
        self.assertEqual(props["Skippy.NextEpisode.ShowTitle"], "Arrow")
        self.assertEqual((props["Skippy.NextEpisode.Season"], props["Skippy.NextEpisode.Episode"]), ("2", "5"))
        self.assertEqual(props["Skippy.NextEpisode.Plot"], "Oliver comes home.")
        self.assertEqual(props["Skippy.NextEpisode.Thumb"], "image://t.jpg/")
        self.assertEqual(props["Skippy.NextEpisode.Visible"], "")

    def test_movie_has_no_show_or_numbers(self):
        props = self.props(MOVIE)
        self.assertEqual(props["Skippy.NextEpisode.Label"], "Dune: Part Two (2024)")
        self.assertEqual((props["Skippy.NextEpisode.ShowTitle"], props["Skippy.NextEpisode.Season"]), ("", ""))

    def test_prompt_up_and_finished(self):
        prompt = skin.build_prompt(_addon(), NEXT, 100, 145, False, "Close", False)
        skin.update_countdown(prompt, _addon(), 118.0)
        props = self.props(NEXT, prompt)
        self.assertEqual(props["Skippy.NextEpisode.Visible"], "true")
        self.assertEqual(props["Skippy.NextEpisode.StillWatching"], "")
        self.assertEqual(props["Skippy.NextEpisode.Heading"], "Play next episode?")
        self.assertEqual(props["Skippy.NextEpisode.PlayLabel"], "Play now")
        self.assertEqual(props["Skippy.NextEpisode.CloseLabel"], "Close")
        self.assertEqual(props["Skippy.NextEpisode.Countdown"], "Episode ends in 00:27")
        self.assertEqual(props["Skippy.NextEpisode.SecondsLeft"], "27")
        self.assertEqual(props["Skippy.NextEpisode.Progress"], "40")
        prompt.finished = True
        self.assertEqual(self.props(NEXT, prompt)["Skippy.NextEpisode.Visible"], "")


class CommandTests(unittest.TestCase):
    def test_runscript_buttons_notify_the_service(self):
        import skippy_runscript_entry as entry

        for command in ("next_episode_play", "next_episode_close"):
            with patch.object(sys, "argv", ["x", command]), patch("xbmc.executebuiltin") as builtin:
                entry.main()
            builtin.assert_called_once_with("NotifyAll(service.skippy,%s)" % command)

    def test_service_notification_records_the_press(self):
        from tests.kodi_stubs import import_fresh

        with patch("service_main_loop.run_service_main_loop", lambda _ctx: None):
            service = import_fresh("service")
        monitor = service.PlayerMonitor()
        monitor.onNotification("service.skippy", "Other.next_episode_play", "")
        self.assertEqual(monitor.next_episode_request[0], skin.REQUEST_PLAY)
        monitor.onNotification("service.skippy", "Other.next_episode_close", "")
        self.assertEqual(monitor.next_episode_request[0], skin.REQUEST_CLOSE)


if __name__ == "__main__":
    unittest.main()
