# -*- coding: utf-8 -*-
"""Next episode: the "still watching?" guard and starting the prompt at the credits."""

import threading
import types
import unittest
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import next_episode_credits as credits
import next_episode_dialog as dlg_mod
import next_episode_guard as guard
import next_episode_prompt as prompt
import next_episode_toast as toast
import segment_types
from next_episode_state import (
    MIN_CREDITS_REMAINING_S,
    NextEpisodeState,
    in_prompt_window,
    rearm_if_before_window,
    reset_guard,
    window_start,
)


def seg(start, end, label="credits"):
    return types.SimpleNamespace(
        start_seconds=start, end_seconds=end, segment_type_label=label
    )


def is_credits(segment):
    return segment.segment_type_label == "credits"


class CreditsStartTests(unittest.TestCase):
    def start(self, segments, total=1500.0):
        return credits.credits_start_seconds(segments, total, is_credits)

    def test_the_credits_segment_gives_the_start(self):
        self.assertEqual(self.start([seg(0, 90, "intro"), seg(1380, 1500)]), 1380.0)

    def test_the_earliest_credits_segment_wins(self):
        self.assertEqual(self.start([seg(1450, 1500), seg(1390, 1420)]), 1390.0)

    def test_only_the_second_half_counts(self):
        self.assertIsNone(self.start([seg(100, 160)]))
        self.assertEqual(self.start([seg(100, 160), seg(750, 800)]), 750.0)

    def test_other_segment_types_are_ignored(self):
        self.assertIsNone(self.start([seg(1380, 1500, "recap")]))

    def test_empty_or_reversed_segments_are_ignored(self):
        self.assertIsNone(self.start([seg(1400, 1400), seg(1450, 1440)]))

    def test_nothing_without_segments_or_a_total(self):
        self.assertIsNone(self.start([]))
        self.assertIsNone(self.start(None))
        self.assertIsNone(self.start([seg(1380, 1500)], total=0))
        self.assertIsNone(self.start([seg(1380, 1500)], total="x"))

    def test_broken_segments_do_not_stop_the_search(self):
        broken = types.SimpleNamespace(start_seconds="a", end_seconds=1, segment_type_label="credits")
        no_times = object()
        self.assertEqual(self.start([broken, no_times, seg(1400, 1500)]), 1400.0)

    def test_a_failing_type_check_skips_that_segment_only(self):
        def flaky(segment):
            if segment.start_seconds == 1380:
                raise RuntimeError("catalog")
            return True

        found = credits.credits_start_seconds([seg(1380, 1400), seg(1420, 1500)], 1500.0, flaky)
        self.assertEqual(found, 1420.0)


class CreditsTypeTests(unittest.TestCase):
    def setUp(self):
        segment_types.set_catalog_for_tests(segment_types.seeded_builtin_types())
        self.addCleanup(segment_types.set_catalog_for_tests, None)

    def test_the_label_and_its_aliases_are_credits(self):
        for label in ("credits", "Credits", "end credits", "outro"):
            self.assertTrue(credits.segment_is_credits(seg(0, 1, label)), label)

    def test_other_types_are_not(self):
        for label in ("intro", "recap", "opening credits", "", "something else"):
            self.assertFalse(credits.segment_is_credits(seg(0, 1, label)), label)

    def test_a_segment_without_a_label_is_not(self):
        self.assertFalse(credits.segment_is_credits(object()))

    def test_default_lookup_uses_the_catalog(self):
        found = credits.credits_start_seconds([seg(1380, 1500, "end credits")], 1500.0)
        self.assertEqual(found, 1380.0)


class WindowWithCreditsTests(unittest.TestCase):
    def test_credits_replace_the_lead(self):
        self.assertEqual(window_start(1500, 45, 1200), 1200.0)
        self.assertEqual(window_start(1500, 45, 1470), 1470.0)

    def test_without_credits_nothing_changes(self):
        self.assertEqual(window_start(1500, 45), 1455.0)
        self.assertEqual(window_start(1500, 45, None), 1455.0)

    def test_unusable_credits_fall_back_to_the_lead(self):
        self.assertEqual(window_start(1500, 45, 20), 1455.0)
        self.assertEqual(window_start(1500, 45, 1495), 1455.0)
        self.assertEqual(window_start(1500, 45, "x"), 1455.0)

    def test_the_last_usable_credits_start_is_ten_seconds_from_the_end(self):
        self.assertEqual(window_start(1500, 45, 1500 - MIN_CREDITS_REMAINING_S), 1490.0)
        self.assertEqual(window_start(1500, 45, 1500 - MIN_CREDITS_REMAINING_S + 1), 1455.0)

    def test_a_clip_shorter_than_the_lead_can_still_use_its_credits(self):
        self.assertIsNone(window_start(60, 45))
        self.assertEqual(window_start(60, 45, 40), 40.0)

    def test_the_window_bounds_follow_the_credits(self):
        self.assertFalse(in_prompt_window(1199, 1500, 45, 1200))
        self.assertTrue(in_prompt_window(1200, 1500, 45, 1200))
        self.assertFalse(in_prompt_window(1499.5, 1500, 45, 1200))

    def test_rearming_uses_the_credits_start(self):
        state = NextEpisodeState(video="v", dismissed=True)
        self.assertFalse(rearm_if_before_window(state, 1196, 1500, 45, 1200))
        self.assertTrue(state.dismissed)
        self.assertTrue(rearm_if_before_window(state, 1190, 1500, 45, 1200))
        self.assertFalse(state.dismissed)

    def test_rearming_forgets_the_still_watching_decision(self):
        event = threading.Event()
        state = NextEpisodeState(
            video="v", dismissed=True, guard_checked=True, guard_ask=True, guard_cancel=event
        )
        rearm_if_before_window(state, 100, 1500, 45)
        self.assertTrue(event.is_set())
        self.assertEqual((state.guard_checked, state.guard_ask, state.guard_cancel), (False, False, None))

    def test_reset_guard_copes_with_a_broken_event(self):
        state = NextEpisodeState(video="v", guard_cancel=object())
        reset_guard(state)
        self.assertIsNone(state.guard_cancel)


class WatchChainTests(unittest.TestCase):
    def test_a_manual_start_ends_the_run(self):
        chain = guard.WatchChain(unattended=2)
        guard.begin_episode(chain)
        self.assertEqual(chain.unattended, 0)

    def test_an_automatic_hand_off_keeps_the_run(self):
        chain = guard.WatchChain(unattended=2, autoplay_pending=True)
        guard.begin_episode(chain)
        self.assertEqual((chain.unattended, chain.autoplay_pending), (2, False))

    def test_input_needs_to_be_clearly_after_the_start(self):
        self.assertFalse(guard.input_since(0.0, 1400.0, 1400.0))
        self.assertFalse(guard.input_since(0.0, 1400.0, 1395.0))
        self.assertTrue(guard.input_since(0.0, 1400.0, 600.0))
        self.assertFalse(guard.input_since(0.0, 1400.0, 1400.0 - guard.IDLE_SLACK_S))
        self.assertTrue(guard.input_since(0.0, 1400.0, 1400.0 - guard.IDLE_SLACK_S - 1))

    def test_an_unknown_clock_counts_as_input(self):
        self.assertTrue(guard.input_since(0.0, 1400.0, None))
        self.assertTrue(guard.input_since(0.0, 1400.0, "x"))

    def run_episodes(self, limit, count, pressed=()):
        """Ask results for ``count`` untouched episodes; ``pressed`` = indexes with a press."""
        chain = guard.WatchChain()
        out = []
        for index in range(count):
            guard.begin_episode(chain)
            idle = 100.0 if index in pressed else 1400.0
            out.append(guard.evaluate(chain, 0.0, 1400.0, idle, limit))
            chain.autoplay_pending = True
        return out

    def test_the_question_comes_after_the_limit(self):
        self.assertEqual(self.run_episodes(3, 4), [False, False, True, True])

    def test_a_press_starts_the_count_over(self):
        self.assertEqual(
            self.run_episodes(3, 6, pressed=(1,)), [False, False, False, False, True, True]
        )

    def test_a_limit_of_one_asks_after_every_untouched_episode(self):
        self.assertEqual(self.run_episodes(1, 2), [True, True])
        self.assertEqual(self.run_episodes(1, 2, pressed=(0, 1)), [False, False])

    def test_a_bad_limit_never_asks(self):
        chain = guard.WatchChain(unattended=50)
        self.assertFalse(guard.evaluate(chain, 0.0, 1400.0, 1400.0, 0))
        self.assertFalse(guard.evaluate(chain, 0.0, 1400.0, 1400.0, "x"))
        self.assertFalse(guard.evaluate(chain, 0.0, 1400.0, 1400.0, None))


class _Player:
    """Plays for ``max_polls`` polls, so a watchdog that never ends cannot hang the suite."""

    def __init__(self, heads, playing=True, max_polls=25):
        self.heads = list(heads)
        self.playing = playing
        self.max_polls = max_polls
        self.polls = 0
        self.stopped = 0

    def isPlaying(self):
        self.polls += 1
        return self.playing and self.polls <= self.max_polls

    def getTime(self):
        return self.heads.pop(0) if len(self.heads) > 1 else self.heads[0]

    def stop(self):
        self.stopped += 1


class WatchdogTests(unittest.TestCase):
    def watch(self, player, cancel=None):
        cancel = cancel or threading.Event()
        return guard.watch_for_the_end(player, 1455.0, 1500.0, cancel, tick=0.0), cancel

    def test_it_stops_playback_shortly_before_the_end(self):
        player = _Player([1460.0, 1480.0, 1497.5])
        stopped, _ = self.watch(player)
        self.assertTrue(stopped)
        self.assertEqual(player.stopped, 1)
        self.assertEqual(player.polls, 3)

    def test_it_leaves_playback_alone_until_then(self):
        player = _Player([1460.0, 1470.0, 1490.0], max_polls=3)
        stopped, _ = self.watch(player)
        self.assertFalse(stopped)
        self.assertEqual(player.stopped, 0)

    def test_it_does_nothing_once_cancelled(self):
        player = _Player([1499.0])
        cancel = threading.Event()
        cancel.set()
        stopped, _ = self.watch(player, cancel)
        self.assertFalse(stopped)
        self.assertEqual(player.stopped, 0)

    def test_it_gives_up_when_playback_stopped(self):
        player = _Player([1499.0], playing=False)
        self.assertFalse(self.watch(player)[0])
        self.assertEqual((player.stopped, player.polls), (0, 1))

    def test_it_gives_up_when_the_viewer_goes_back(self):
        player = _Player([1400.0])
        self.assertFalse(self.watch(player)[0])
        self.assertEqual((player.stopped, player.polls), (0, 1))

    def test_a_broken_player_ends_it_quietly(self):
        class Broken:
            def isPlaying(self):
                raise RuntimeError("gone")

        self.assertFalse(self.watch(Broken())[0])

        class CannotStop(_Player):
            def stop(self):
                raise RuntimeError("nope")

        self.assertFalse(self.watch(CannotStop([1499.0]))[0])

    def test_start_returns_an_event_that_ends_the_thread(self):
        player = _Player([1460.0])
        cancel = guard.start_stop_watchdog(player, 1455.0, 1500.0, tick=0.01)
        self.assertFalse(cancel.is_set())
        cancel.set()


class StillWatchingTextTests(unittest.TestCase):
    def test_toast_texts(self):
        with patch.object(toast, "get_localized", lambda a, i, d, *r: "%d|%s" % (i, d)):
            heading, body = toast.build_toast_texts(None, {"season": 1, "episode": 3}, True)
            self.assertEqual(heading, "47070|Still watching?")
            self.assertTrue(body.endswith("47073|Press OK to continue"))
            heading, body = toast.build_toast_texts(None, {"season": 1, "episode": 3})
            self.assertEqual(heading, "47020|Play next episode?")
            self.assertTrue(body.endswith("47021|Press OK to play"))

    def test_the_prompt_passes_the_question_on(self):
        for style, target in (("Custom", "dialog"), ("Native", "toast")):
            dialog, toast_fn = MagicMock(return_value="d"), MagicMock(return_value="t")
            with patch.object(
                prompt, "addon_get_setting_text", lambda a, k, default="": style
            ), patch.object(prompt, "show_next_episode_toast", toast_fn), patch.object(
                prompt, "load_popup_draft", lambda a: {}
            ), patch.dict(
                "sys.modules",
                {"next_episode_dialog": types.SimpleNamespace(show_next_episode_dialog=dialog)},
            ):
                prompt.show_next_episode_prompt("a", "p", {}, 1.0, 2.0, still_watching=True)
            used = dialog if target == "dialog" else toast_fn
            self.assertTrue(used.call_args.kwargs["still_watching"], style)

    def popup(self, still_watching, focus="Play"):
        dialog = dlg_mod.NextEpisodeDialog.__new__(dlg_mod.NextEpisodeDialog)
        dialog.addon = MagicMock()
        dialog.draft = dict(dlg_mod.DEFAULT_DRAFT, **{dlg_mod.KEY_FOCUS: focus})
        dialog.next_episode = {"season": 1, "episode": 2, "title": "T"}
        dialog.player = None
        dialog.window_start, dialog.total = 10.0, 60.0
        dialog.preview, dialog.still_watching = True, still_watching
        dialog._stop = threading.Event()
        dialog._xml_layout = "NextEpisodeDialog.xml"
        dialog._skin_resolution = "720p"
        dialog._started = 0.0
        dialog._layout = None
        self.props, self.labels, self.focus = {}, {}, []
        dialog.setProperty = lambda k, v: self.props.__setitem__(k, v)
        dialog.setFocusId = lambda cid: self.focus.append(cid)
        dialog._apply_layout = lambda layout: None
        dialog._update_countdown = lambda head: None

        def ctrl(cid):
            control = MagicMock()
            control.setLabel = lambda text, c=cid: self.labels.__setitem__(c, text)
            return control

        dialog._ctrl = ctrl
        with patch.object(dlg_mod, "get_localized", lambda a, i, d, *r: "%d" % i), patch.object(
            dlg_mod, "reconcile_window_xml_skin_resolution", lambda *a, **k: "720p"
        ), patch.object(dlg_mod, "_text_color", lambda a: "FFFFFFFF"), patch.object(
            dlg_mod.threading, "Thread"
        ):
            dialog.onInit()
        return dialog

    def test_the_question_has_its_own_heading_and_buttons(self):
        self.popup(True)
        self.assertEqual(self.props["next_ep_heading"], "47070")
        self.assertEqual(self.labels[dlg_mod.ID_PLAY], "47071")
        self.assertEqual(self.labels[dlg_mod.ID_CLOSE], "47072")

    def test_the_usual_prompt_keeps_its_texts(self):
        self.popup(False)
        self.assertEqual(self.props["next_ep_heading"], "47020")
        self.assertEqual(self.labels[dlg_mod.ID_PLAY], "47050")
        self.assertEqual(self.labels[dlg_mod.ID_CLOSE], "40001")

    def test_continue_is_focused_even_when_close_is_the_default_button(self):
        self.popup(True, focus="Close")
        self.assertEqual(self.focus[-1], dlg_mod.ID_PLAY)
        self.popup(False, focus="Close")
        self.assertEqual(self.focus[-1], dlg_mod.ID_CLOSE)

    def test_the_dialog_function_hands_the_question_to_the_window(self):
        seen = {}

        class Fake(dlg_mod.NextEpisodeDialog):
            def __init__(self, *args, **kwargs):
                seen.update(kwargs)
                self.result = False
                self._stop = threading.Event()

            def doModal(self):
                pass

        addon = MagicMock()
        addon.getAddonInfo.return_value = "/addon"
        with patch.object(dlg_mod, "NextEpisodeDialog", Fake):
            answer = dlg_mod.show_next_episode_dialog(addon, None, {}, 1.0, 2.0, still_watching=True)
        self.assertIs(answer, False)
        self.assertTrue(seen["still_watching"])


if __name__ == "__main__":
    unittest.main()
