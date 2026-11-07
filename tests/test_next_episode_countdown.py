# -*- coding: utf-8 -*-
"""How long the next episode prompt stays up and what happens when its countdown runs out."""

import os
import re
import threading
import types
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import next_episode_appearance as app
import next_episode_customize_ui as cust
import next_episode_dialog as dlg_mod
import next_episode_prompt as prompt
import next_episode_state as state_mod
import next_episode_toast as toast
import next_episode_view as view
import service_loop_next_episode as step
from next_episode_state import (
    END_CLOSE,
    END_PLAY,
    TIMED_OUT,
    NextEpisodeState,
    LOOKUP_FOUND,
    normalize_end_action,
    popup_span,
)
from tests.test_next_episode import LIBRARY_NEXT, SETTINGS, _Player as _FilePlayer

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class PopupSpanTests(unittest.TestCase):
    def test_no_duration_counts_down_over_the_whole_window(self):
        self.assertEqual(popup_span(1455.0, 1456.0, 1500.0, 0), (1455.0, 1500.0, False))

    def test_a_duration_counts_down_that_long_from_the_window_start(self):
        self.assertEqual(popup_span(1455.0, 1455.5, 1500.0, 20), (1455.5, 1475.5, True))

    def test_a_prompt_that_opens_late_gets_its_full_time_from_where_it_opens(self):
        # Seeking into the middle of the window must not leave a prompt that is already over.
        self.assertEqual(popup_span(1455.0, 1480.0, 1500.0, 15), (1480.0, 1495.0, True))

    def test_a_duration_that_reaches_the_end_of_the_file_is_not_timed(self):
        self.assertEqual(popup_span(1455.0, 1455.0, 1500.0, 60), (1455.0, 1500.0, False))
        # The last second belongs to Kodi's own end-of-file handling.
        self.assertEqual(popup_span(1455.0, 1455.0, 1500.0, 44.5), (1455.0, 1500.0, False))
        self.assertEqual(popup_span(1455.0, 1455.0, 1500.0, 43.0), (1455.0, 1498.0, True))

    def test_a_negative_duration_means_to_the_end(self):
        self.assertEqual(popup_span(1455.0, 1455.0, 1500.0, -5), (1455.0, 1500.0, False))

    def test_unreadable_numbers_fall_back_to_the_whole_window(self):
        self.assertEqual(popup_span(1455.0, "x", 1500.0, 20), (1455.0, 1500.0, False))
        self.assertEqual(popup_span(1455.0, None, 1500.0, 20), (1455.0, 1500.0, False))

    def test_end_actions_are_read_loosely_and_default_to_close(self):
        self.assertEqual(normalize_end_action("Play"), END_PLAY)
        self.assertEqual(normalize_end_action(" play "), END_PLAY)
        self.assertEqual(normalize_end_action("Close"), END_CLOSE)
        for junk in ("", None, "Skip", "2"):
            self.assertEqual(normalize_end_action(junk), END_CLOSE)


class _Addon:
    def __init__(self, **settings):
        self.settings = {k: str(v) for k, v in settings.items()}

    def getLocalizedString(self, string_id):
        return ""

    def getSetting(self, key):
        return self.settings.get(key, "")

    getSettingString = getSetting


class CountdownTextTests(unittest.TestCase):
    def test_the_line_says_what_happens_at_zero(self):
        addon = _Addon()
        self.assertEqual(view.countdown_text(addon, False, 42), "Episode ends in 00:42")
        self.assertEqual(
            view.countdown_text(addon, False, 20, view.COUNTDOWN_PLAYS), "Next episode starts in 00:20"
        )
        self.assertEqual(
            view.countdown_text(addon, False, 20, view.COUNTDOWN_CLOSES), "Closing in 00:20"
        )

    def test_capitals_apply_to_every_line(self):
        for mode in (view.COUNTDOWN_ENDS, view.COUNTDOWN_PLAYS, view.COUNTDOWN_CLOSES):
            text = view.countdown_text(_Addon(), True, 5, mode)
            self.assertEqual(text, text.upper())

    def test_an_unknown_mode_reads_like_the_episode_ending(self):
        self.assertEqual(view.countdown_text(_Addon(), False, 42, "?"), "Episode ends in 00:42")

    def test_mode_depends_on_the_action_and_on_whether_the_countdown_is_cut_short(self):
        self.assertEqual(view.countdown_mode(END_CLOSE, False), view.COUNTDOWN_ENDS)
        self.assertEqual(view.countdown_mode(END_CLOSE, True), view.COUNTDOWN_CLOSES)
        self.assertEqual(view.countdown_mode(END_PLAY, False), view.COUNTDOWN_PLAYS)
        self.assertEqual(view.countdown_mode(END_PLAY, True), view.COUNTDOWN_PLAYS)

    def test_the_still_watching_question_always_counts_down_to_the_episode_end(self):
        for action in (END_CLOSE, END_PLAY):
            for timed in (False, True):
                self.assertEqual(view.countdown_mode(action, timed, True), view.COUNTDOWN_ENDS)

    def test_the_saved_settings_are_read_and_cleaned_up(self):
        self.assertEqual(view.countdown_settings(_Addon()), (0, END_CLOSE))
        addon = _Addon(next_episode_popup_duration="20", next_episode_popup_end_action="Play")
        self.assertEqual(view.countdown_settings(addon), (20, END_PLAY))
        addon = _Addon(next_episode_popup_duration="9999", next_episode_popup_end_action="x")
        self.assertEqual(view.countdown_settings(addon), (state_mod.MAX_POPUP_DURATION_S, END_CLOSE))
        self.assertEqual(view.countdown_settings(None), (0, END_CLOSE))


class PromptPassThroughTests(unittest.TestCase):
    """The prompt hands the shortened countdown and the end action to whichever style is shown."""

    def run_prompt(self, style):
        toast_fn = MagicMock(return_value="toast")
        dialog_fn = MagicMock(return_value="dialog")
        text = lambda _addon, key, default="": style if key == app.KEY_STYLE else default
        with patch.object(prompt, "addon_get_setting_text", text), patch.object(
            prompt, "show_next_episode_toast", toast_fn
        ), patch.object(prompt, "load_popup_draft", lambda a: {"d": 1}), patch.dict(
            "sys.modules",
            {"next_episode_dialog": types.SimpleNamespace(show_next_episode_dialog=dialog_fn)},
        ):
            prompt.show_next_episode_prompt(
                "addon", "player", {"t": 1}, 10.0, 30.0, timed=True, end_action=END_PLAY
            )
        return toast_fn, dialog_fn

    def test_the_custom_popup_gets_them(self):
        toast_fn, dialog_fn = self.run_prompt("Custom")
        toast_fn.assert_not_called()
        self.assertEqual(dialog_fn.call_args.args[3:5], (10.0, 30.0))
        self.assertTrue(dialog_fn.call_args.kwargs["timed"])
        self.assertEqual(dialog_fn.call_args.kwargs["end_action"], END_PLAY)

    def test_the_native_toast_gets_them(self):
        toast_fn, dialog_fn = self.run_prompt("Native")
        dialog_fn.assert_not_called()
        self.assertEqual(toast_fn.call_args.args[3:5], (10.0, 30.0))
        self.assertTrue(toast_fn.call_args.kwargs["timed"])
        self.assertEqual(toast_fn.call_args.kwargs["end_action"], END_PLAY)

    def test_a_popup_that_cannot_be_built_falls_back_to_the_toast_with_them(self):
        toast_fn = MagicMock(return_value="toast")
        dialog_fn = MagicMock(side_effect=RuntimeError("x"))
        text = lambda _addon, key, default="": "Custom" if key == app.KEY_STYLE else default
        with patch.object(prompt, "addon_get_setting_text", text), patch.object(
            prompt, "show_next_episode_toast", toast_fn
        ), patch.object(prompt, "load_popup_draft", lambda a: {}), patch.object(
            prompt, "log_error"
        ), patch.dict(
            "sys.modules",
            {"next_episode_dialog": types.SimpleNamespace(show_next_episode_dialog=dialog_fn)},
        ):
            prompt.show_next_episode_prompt(
                "addon", "player", {}, 10.0, 30.0, timed=True, end_action=END_PLAY
            )
        self.assertTrue(toast_fn.call_args.kwargs["timed"])
        self.assertEqual(toast_fn.call_args.kwargs["end_action"], END_PLAY)


class _Player:
    def __init__(self, head, playing=True):
        self.head = head
        self.playing = playing

    def getTime(self):
        return self.head

    def isPlaying(self):
        return self.playing


def _dialog(player, *, total, timed, end_action, still_watching=False, window_start=1455.0):
    dialog = dlg_mod.NextEpisodeDialog.__new__(dlg_mod.NextEpisodeDialog)
    dialog.player = player
    dialog.window_start = window_start
    dialog.total = total
    dialog.preview = False
    dialog.result = None
    dialog._closing = False
    dialog._stop = threading.Event()
    dialog._layout = None
    dialog.close = MagicMock()
    dialog.timed = timed
    dialog.end_action = end_action
    dialog.still_watching = still_watching
    return dialog


def _watch(dialog, ticks=2):
    seen = []

    def update(head):
        seen.append(head)
        if len(seen) >= ticks:
            dialog._stop.set()

    dialog._update_countdown = update
    with patch.object(dlg_mod, "_TICK_S", 0.0):
        dialog._watch()
    return seen


class DialogCountdownEndTests(unittest.TestCase):
    def test_a_timed_popup_runs_out_exactly_where_it_was_set_to(self):
        dialog = _dialog(_Player(1475.0), total=1475.0, timed=True, end_action=END_CLOSE)
        _watch(dialog)
        self.assertEqual(dialog.result, TIMED_OUT)
        dialog.close.assert_called_once()

    def test_a_timed_popup_keeps_going_until_then(self):
        dialog = _dialog(_Player(1474.9), total=1475.0, timed=True, end_action=END_CLOSE)
        self.assertEqual(_watch(dialog), [1474.9, 1474.9])
        self.assertIsNone(dialog.result)
        self.assertFalse(dialog._closing)

    def test_a_popup_that_runs_to_the_end_of_the_file_just_closes_when_the_action_is_close(self):
        dialog = _dialog(_Player(1499.5), total=1500.0, timed=False, end_action=END_CLOSE)
        _watch(dialog)
        self.assertIsNone(dialog.result)
        self.assertTrue(dialog._closing)

    def test_a_popup_that_runs_to_the_end_of_the_file_times_out_when_the_action_is_play(self):
        dialog = _dialog(_Player(1499.5), total=1500.0, timed=False, end_action=END_PLAY)
        _watch(dialog)
        self.assertEqual(dialog.result, TIMED_OUT)

    def test_a_play_action_waits_for_the_last_second_not_before(self):
        dialog = _dialog(_Player(1498.9), total=1500.0, timed=False, end_action=END_PLAY)
        _watch(dialog)
        self.assertIsNone(dialog.result)
        self.assertFalse(dialog._closing)

    def test_stopping_playback_never_counts_as_a_timeout(self):
        dialog = _dialog(_Player(1475.0, playing=False), total=1475.0, timed=True, end_action=END_PLAY)
        _watch(dialog)
        self.assertIsNone(dialog.result)

    def test_seeking_back_before_the_window_never_counts_as_a_timeout(self):
        dialog = _dialog(_Player(1400.0), total=1475.0, timed=True, end_action=END_PLAY)
        _watch(dialog)
        self.assertIsNone(dialog.result)

    def test_the_still_watching_question_never_times_out(self):
        for timed in (False, True):
            dialog = _dialog(
                _Player(1499.5),
                total=1500.0,
                timed=timed,
                end_action=END_PLAY,
                still_watching=True,
            )
            dialog.timed = timed and not dialog.still_watching
            dialog.end_action = END_CLOSE
            _watch(dialog)
            self.assertIsNone(dialog.result, timed)

    def test_the_constructor_keeps_a_timeout_away_from_the_still_watching_question(self):
        with patch.object(dlg_mod, "init_window_xml_dialog", lambda *a, **k: "720p"):
            dialog = dlg_mod.NextEpisodeDialog(
                "x.xml", "p", "default", still_watching=True, timed=True, end_action=END_PLAY
            )
            plain = dlg_mod.NextEpisodeDialog(
                "x.xml", "p", "default", timed=True, end_action=END_PLAY
            )
        self.assertFalse(dialog.timed)
        self.assertEqual(dialog.end_action, END_CLOSE)
        self.assertTrue(plain.timed)
        self.assertEqual(plain.end_action, END_PLAY)

    def test_the_countdown_line_and_bar_run_over_the_shortened_time(self):
        dialog = _dialog(_Player(1465.0), total=1475.0, timed=True, end_action=END_PLAY)
        dialog.addon = None
        dialog._layout = dlg_mod.popup_layout(thumbnail=False, countdown=True, progress=True)
        dialog._look = None
        props = {}
        dialog.setProperty = lambda k, v: props.__setitem__(k, v)
        fill = MagicMock()
        dialog._ctrl = lambda cid: fill if cid == dlg_mod.ID_BAR_FILL else None
        dialog._sc = lambda v: v
        dialog._bar_tiled = True
        dialog._update_countdown(1465.0)
        self.assertEqual(props["next_ep_countdown"], "Next episode starts in 00:10")
        # 10 of the 20 seconds are left: half of the 500 px bar, in whole 8 px segments.
        fill.setWidth.assert_called_once_with(248)

    def test_a_close_action_on_a_timed_popup_says_it_is_closing(self):
        dialog = _dialog(_Player(1465.0), total=1475.0, timed=True, end_action=END_CLOSE)
        dialog.addon = None
        dialog._layout = dlg_mod.popup_layout(thumbnail=False, countdown=True, progress=False)
        dialog._look = None
        props = {}
        dialog.setProperty = lambda k, v: props.__setitem__(k, v)
        dialog._update_countdown(1465.0)
        self.assertEqual(props["next_ep_countdown"], "Closing in 00:10")

    def test_the_preview_loops_over_the_saved_time(self):
        dialog = _dialog(None, total=20.0, timed=True, end_action=END_CLOSE, window_start=0.0)
        dialog.preview = True
        dialog._started = 0.0
        for now, expected in ((0.0, 0.0), (5.0, 5.0), (19.9, 19.9), (20.0, 0.0), (45.0, 5.0)):
            with patch.object(dlg_mod.time, "monotonic", lambda n=now: n):
                self.assertAlmostEqual(dialog._head(), expected, places=6)

    def test_the_preview_uses_the_saved_settings(self):
        self.assertEqual(dlg_mod.preview_countdown(_Addon()), (dlg_mod._PREVIEW_LOOP_S, False, END_CLOSE))
        addon = _Addon(next_episode_popup_duration="20", next_episode_popup_end_action="Play")
        self.assertEqual(dlg_mod.preview_countdown(addon), (20.0, True, END_PLAY))

    def test_show_preview_hands_them_to_the_dialog(self):
        addon = _Addon(next_episode_popup_duration="20", next_episode_popup_end_action="Play")
        addon.getAddonInfo = lambda key: ROOT
        with patch.object(dlg_mod, "show_next_episode_dialog") as shown:
            dlg_mod.show_preview(addon, {"d": 1})
        args, kwargs = shown.call_args
        self.assertEqual(args[3:5], (0.0, 20.0))
        self.assertTrue(kwargs["preview"] and kwargs["timed"])
        self.assertEqual(kwargs["end_action"], END_PLAY)


class ToastCountdownEndTests(unittest.TestCase):
    def run_toast(self, *, head, playing, timed, end_action, total=1475.0, still_watching=False):
        """Run the toast with a keep-alive that fires once, as it does when the stretch is over."""
        holder = {}

        class _Keys:
            def __init__(self, *args):
                self.result = None
                self._done = False
                holder["keys"] = self

            def doModal(self):
                keepalive_close()

            def close(self):
                self.closed = True

            def _finish(self, value):
                if not self._done:
                    self._done = True
                    self.result = value

        def keepalive(player, window, post, close, stop):
            holder["window"] = window
            holder["close"] = close

        def keepalive_close():
            holder["close"]()

        player = _Player(head, playing)
        addon = MagicMock()
        addon.getAddonInfo = lambda key: "icon.png"
        addon.getLocalizedString = lambda _id: ""
        posted = []
        dialog = MagicMock()
        dialog.notification = lambda *a: posted.append(a)
        with patch.object(toast, "SkipToastKeys", _Keys), patch.object(
            toast, "_toast_keepalive", keepalive
        ), patch.object(toast, "_dismiss_toast"), patch.object(
            toast.xbmcgui, "Dialog", lambda: dialog
        ), patch.object(toast.threading, "Thread", lambda target, args, daemon: types.SimpleNamespace(start=lambda: target(*args))):
            answer = toast.show_next_episode_toast(
                addon,
                player,
                {"title": "T", "season": 1, "episode": 2},
                1455.0,
                total,
                still_watching=still_watching,
                timed=timed,
                end_action=end_action,
            )
        return answer, posted, holder

    def test_a_timed_toast_that_reaches_its_end_times_out(self):
        answer, _posted, holder = self.run_toast(head=1474.8, playing=True, timed=True, end_action=END_CLOSE)
        self.assertEqual(answer, TIMED_OUT)
        self.assertEqual(holder["window"].end_seconds, 1475.0)

    def test_a_toast_that_runs_to_the_end_of_the_file_times_out_only_for_a_play_action(self):
        answer, *_ = self.run_toast(
            head=1499.6, playing=True, timed=False, end_action=END_PLAY, total=1500.0
        )
        self.assertEqual(answer, TIMED_OUT)
        answer, *_ = self.run_toast(
            head=1499.6, playing=True, timed=False, end_action=END_CLOSE, total=1500.0
        )
        self.assertIsNone(answer)

    def test_a_toast_whose_playback_stopped_does_not_time_out(self):
        answer, *_ = self.run_toast(head=1474.8, playing=False, timed=True, end_action=END_PLAY)
        self.assertIsNone(answer)

    def test_a_toast_that_the_playhead_left_early_does_not_time_out(self):
        answer, *_ = self.run_toast(head=1400.0, playing=True, timed=True, end_action=END_PLAY)
        self.assertIsNone(answer)

    def test_the_still_watching_toast_never_times_out(self):
        answer, *_ = self.run_toast(
            head=1499.6,
            playing=True,
            timed=True,
            end_action=END_PLAY,
            total=1500.0,
            still_watching=True,
        )
        self.assertIsNone(answer)

    def test_the_toast_is_posted_for_the_shortened_time_only(self):
        _answer, posted, _holder = self.run_toast(
            head=1455.0, playing=True, timed=True, end_action=END_CLOSE
        )
        self.assertEqual(posted[0][3], 20000)


class HandlerCountdownTests(unittest.TestCase):
    """The service loop: the shortened span, and what each way the countdown ends does."""

    def setUp(self):
        self.monitor = types.SimpleNamespace(next_episode_state=None)
        self.ctx = types.SimpleNamespace(monitor=self.monitor, player=_FilePlayer())
        self.settings = dict(SETTINGS, next_episode_popup_duration=0, next_episode_popup_end_action="Close")
        self.answers = []
        self.calls = []
        self.plays = []
        self.now = 1000.0
        stack = [
            patch.object(step, "get_addon", lambda: object()),
            patch.object(
                step, "addon_get_bool", lambda _a, key, default=False: self.settings.get(key, default)
            ),
            patch.object(
                step,
                "addon_get_int",
                lambda _a, key, default=0, minimum=None, maximum=None: self.settings.get(key, default),
            ),
            patch.object(
                step,
                "countdown_settings",
                lambda _a: (
                    self.settings["next_episode_popup_duration"],
                    self.settings["next_episode_popup_end_action"],
                ),
            ),
            patch.object(step, "_upnext_enabled", lambda: False),
            patch.object(step, "_idle_seconds", lambda: None),
            patch.object(step, "show_next_episode_prompt", self._prompt),
            patch.object(step, "play_next", self._play),
            patch.object(step, "schedule_mark_watched", lambda *a: None),
            patch.object(step, "_start_lookup", lambda *a, **k: None),
            patch.object(step.time, "monotonic", lambda: self.now),
            patch.object(step, "log"),
            patch.object(step, "log_error"),
        ]
        for p in stack:
            p.start()
            self.addCleanup(p.stop)
        self.state = NextEpisodeState(
            video="ep.mkv",
            lookup=LOOKUP_FOUND,
            next_item=LIBRARY_NEXT,
            current_episode_id=7,
            current_playcount=1,
        )
        self.monitor.next_episode_state = self.state

    def _prompt(self, addon, player, item, start, total, **kwargs):
        self.calls.append((start, total, kwargs))
        return self.answers.pop(0) if self.answers else None

    def _play(self, item, resume=True):
        self.plays.append(item)
        return True

    def tick(self, current_time):
        return step.handle_next_episode(
            self.ctx,
            video="ep.mkv",
            playback_type="episode",
            current_time=current_time,
            player_item={"type": "episode", "id": 7},
        )

    def test_by_default_the_prompt_runs_over_the_whole_window_and_closes_there(self):
        self.tick(1460.0)
        start, total, kwargs = self.calls[0]
        self.assertEqual((start, total), (1455.0, 1500.0))
        self.assertEqual((kwargs["timed"], kwargs["end_action"]), (False, END_CLOSE))

    def test_a_duration_shortens_the_countdown(self):
        self.settings["next_episode_popup_duration"] = 20
        self.tick(1456.0)
        start, total, kwargs = self.calls[0]
        self.assertEqual((start, total, kwargs["timed"]), (1456.0, 1476.0, True))

    def test_a_close_action_closes_the_prompt_and_it_does_not_come_back(self):
        self.settings["next_episode_popup_duration"] = 20
        self.answers = [TIMED_OUT]
        result = self.tick(1456.0)
        self.assertTrue(self.state.dismissed)
        self.assertFalse(self.state.started)
        self.assertEqual(self.plays, [])
        self.assertFalse(result.switched)
        self.assertTrue(result.hide_skip_dialogs)
        self.now += 60.0
        self.tick(1480.0)
        self.assertEqual(len(self.calls), 1)

    def test_a_play_action_starts_the_next_episode_as_an_unattended_start(self):
        self.settings["next_episode_popup_duration"] = 20
        self.settings["next_episode_popup_end_action"] = "Play"
        self.answers = [TIMED_OUT]
        result = self.tick(1456.0)
        self.assertTrue(result.switched)
        self.assertEqual(self.plays, [LIBRARY_NEXT])
        self.assertTrue(self.state.started)
        # Nobody pressed anything: the episode counts towards "still watching?".
        self.assertTrue(self.monitor.next_episode_chain.autoplay_pending)

    def test_a_play_action_also_works_when_the_prompt_runs_to_the_end_of_the_file(self):
        self.settings["next_episode_popup_end_action"] = "Play"
        self.answers = [TIMED_OUT]
        result = self.tick(1460.0)
        start, total, kwargs = self.calls[0]
        self.assertEqual((start, total, kwargs["timed"], kwargs["end_action"]), (1455.0, 1500.0, False, END_PLAY))
        self.assertTrue(result.switched)

    def test_a_failed_start_after_a_timeout_is_not_tried_again(self):
        self.settings["next_episode_popup_end_action"] = "Play"
        self.answers = [TIMED_OUT]
        with patch.object(step, "play_next", lambda item, resume=True: False):
            result = self.tick(1460.0)
        self.assertFalse(result.switched)
        self.assertTrue(self.state.failed)

    def test_the_still_watching_question_ignores_both_settings(self):
        self.settings["next_episode_popup_duration"] = 20
        self.settings["next_episode_popup_end_action"] = "Play"
        self.settings["next_episode_autoplay"] = True
        self.state.guard_checked = True
        self.state.guard_ask = True
        self.tick(1460.0)
        start, total, kwargs = self.calls[0]
        self.assertTrue(kwargs["still_watching"])
        self.assertEqual((start, total), (1455.0, 1500.0))
        self.assertEqual((kwargs["timed"], kwargs["end_action"]), (False, END_CLOSE))

    def test_answering_still_works_as_before(self):
        self.settings["next_episode_popup_duration"] = 20
        self.answers = [True]
        self.assertTrue(self.tick(1456.0).switched)
        self.assertEqual(self.plays, [LIBRARY_NEXT])

    def test_back_still_dismisses(self):
        self.settings["next_episode_popup_duration"] = 20
        self.answers = [False]
        self.tick(1456.0)
        self.assertTrue(self.state.dismissed)

    def test_autoplay_does_not_open_the_prompt_at_all(self):
        self.settings["next_episode_autoplay"] = True
        self.settings["next_episode_popup_duration"] = 20
        self.state.guard_checked = True
        self.state.guard_ask = False
        self.assertTrue(self.tick(1460.0).switched)
        self.assertEqual(self.calls, [])


class MockCountdownTests(unittest.TestCase):
    def test_the_mockup_shows_the_whole_time_by_default(self):
        self.assertEqual(cust.mock_countdown_text(_Addon(), False), "Episode ends in 00:31")

    def test_a_fixed_time_shows_the_same_share_of_it(self):
        addon = _Addon(next_episode_popup_duration="45")
        self.assertEqual(cust.mock_countdown_text(addon, False), "Closing in 00:31")
        addon = _Addon(next_episode_popup_duration="20", next_episode_popup_end_action="Play")
        self.assertEqual(cust.mock_countdown_text(addon, False), "Next episode starts in 00:14")

    def test_capitals_follow_the_look(self):
        text = cust.mock_countdown_text(_Addon(next_episode_popup_duration="20"), True)
        self.assertEqual(text, text.upper())


class SettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ET.parse(os.path.join(ROOT, "resources", "settings.xml"))
        cls.found = {s.get("id"): s for s in tree.getroot().iter("setting")}

    def test_the_length_is_a_standard_level_spinner_from_off_to_two_minutes(self):
        setting = self.found["next_episode_popup_duration"]
        self.assertEqual(setting.get("type"), "integer")
        self.assertEqual(setting.findtext("level"), "1")
        self.assertEqual(setting.findtext("default"), "0")
        constraints = setting.find("constraints")
        self.assertEqual(
            [constraints.findtext(t) for t in ("minimum", "maximum", "step")], ["0", "120", "5"]
        )

    def test_the_end_action_offers_close_and_play_with_translated_labels(self):
        setting = self.found["next_episode_popup_end_action"]
        self.assertEqual(setting.findtext("level"), "1")
        self.assertEqual(setting.findtext("default"), "Close")
        options = [(o.get("label"), o.text) for o in setting.iter("option")]
        self.assertEqual(options, [("47122", "Close"), ("47123", "Play")])

    def test_both_belong_to_the_prompt_and_show_with_the_feature(self):
        for sid in ("next_episode_popup_duration", "next_episode_popup_end_action"):
            deps = [
                (d.get("setting"), d.text)
                for d in self.found[sid].iter("dependency")
                if d.get("type") == "visible"
            ]
            self.assertEqual(deps, [("next_episode_enabled", "true")], sid)

    def test_they_sit_right_after_the_start_at_credits_setting(self):
        order = [
            s.get("id")
            for s in ET.parse(os.path.join(ROOT, "resources", "settings.xml")).getroot().iter("setting")
        ]
        start = order.index("next_episode_start_at_credits")
        self.assertEqual(
            order[start + 1 : start + 3],
            ["next_episode_popup_duration", "next_episode_popup_end_action"],
        )

    def test_the_defaults_in_the_settings_file_match_the_code(self):
        self.assertEqual(self.found["next_episode_popup_duration"].findtext("default"), "0")
        self.assertEqual(self.found["next_episode_popup_end_action"].findtext("default"), END_CLOSE)
        self.assertEqual(state_mod.KEY_POPUP_DURATION, "next_episode_popup_duration")
        self.assertEqual(state_mod.KEY_END_ACTION, "next_episode_popup_end_action")
        self.assertEqual(
            self.found["next_episode_popup_duration"].find("constraints").findtext("maximum"),
            str(state_mod.MAX_POPUP_DURATION_S),
        )


class StringsTests(unittest.TestCase):
    IDS = range(47118, 47126)

    def packs(self):
        langs = os.path.join(ROOT, "resources", "language")
        for pack in sorted(os.listdir(langs)):
            path = os.path.join(langs, pack, "strings.po")
            if os.path.exists(path):
                with open(path, encoding="utf-8") as handle:
                    yield pack, handle.read()

    @staticmethod
    def entries(text):
        return {
            int(sid): (msgid, msgstr)
            for sid, msgid, msgstr in re.findall(
                r'msgctxt "#(\d+)"\nmsgid "(.*)"\nmsgstr "(.*)"', text
            )
        }

    def test_every_pack_has_every_string_with_the_same_placeholders(self):
        packs = list(self.packs())
        self.assertGreaterEqual(len(packs), 11)
        for pack, text in packs:
            entries = self.entries(text)
            for sid in self.IDS:
                self.assertIn(sid, entries, (pack, sid))
                msgid, msgstr = entries[sid]
                self.assertTrue(msgstr.strip(), (pack, sid))
                self.assertEqual(msgid.count("%s"), msgstr.count("%s"), (pack, sid))
                self.assertEqual(msgstr.count("%"), msgstr.count("%s"), (pack, sid))

    def test_the_translations_are_not_the_english_text(self):
        english = self.entries(dict(self.packs())["resource.language.en_gb"])
        for pack, text in self.packs():
            if pack.endswith("en_gb"):
                continue
            entries = self.entries(text)
            for sid in self.IDS:
                self.assertNotEqual(entries[sid][1], english[sid][1], (pack, sid))

    def test_the_two_countdown_lines_end_in_a_time(self):
        for pack, text in self.packs():
            entries = self.entries(text)
            for sid in (47124, 47125):
                self.assertEqual(entries[sid][1].count("%s"), 1, (pack, sid))


if __name__ == "__main__":
    unittest.main()
