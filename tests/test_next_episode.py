# -*- coding: utf-8 -*-
"""Next episode prompt: lookup, window arithmetic, hand-off, handler and settings."""

import os
import re
import threading
import types
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import next_episode_lookup as lookup
import next_episode_play as play
import next_episode_toast as toast
import service_loop_next_episode as step
from next_episode_guard import HANDOFF_GAP_S, WatchChain
from next_episode_state import (
    LOOKUP_FOUND,
    LOOKUP_IDLE,
    LOOKUP_NONE,
    MIN_REPROMPT_S,
    NextEpisodeState,
    in_prompt_window,
    rearm_if_before_window,
    window_start,
)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class FakeRpc:
    """Stand-in for ``remote_http.jsonrpc``: answers by method name."""

    def __init__(self, handlers):
        self.handlers = handlers
        self.calls = []

    def __call__(self, method, params=None, log_errors=True):
        self.calls.append((method, params))
        handler = self.handlers.get(method)
        if handler is None:
            return {}
        return handler(params) if callable(handler) else handler

    def params_for(self, method):
        return [p for m, p in self.calls if m == method]


def ep(episode_id, season, episode, playcount=0, file=None):
    return {
        "episodeid": episode_id,
        "season": season,
        "episode": episode,
        "playcount": playcount,
        "file": file or "/tv/s%02de%02d.mkv" % (season, episode),
    }


SEASON_ONE = [ep(1, 1, 1), ep(2, 1, 2), ep(3, 1, 3)]
SEASON_TWO = [ep(4, 2, 1), ep(5, 2, 2)]
CURRENT = {"id": 2, "season": 1, "episode": 2, "file": "/tv/s01e02.mkv"}


class PickNextEpisodeTests(unittest.TestCase):
    def pick(self, rows, current=None, **kw):
        row = lookup.pick_next_episode(rows, current or CURRENT, **kw)
        return row["episodeid"] if row else None

    def test_next_episode_in_the_same_season(self):
        self.assertEqual(self.pick(SEASON_ONE + SEASON_TWO), 3)

    def test_input_order_does_not_matter(self):
        self.assertEqual(self.pick(list(reversed(SEASON_ONE + SEASON_TWO))), 3)

    def test_gap_in_numbering_still_finds_the_next_one(self):
        rows = [ep(1, 1, 1), ep(2, 1, 2), ep(5, 1, 5), ep(6, 2, 1)]
        self.assertEqual(self.pick(rows), 5)

    def test_last_episode_of_a_season_continues_in_the_next(self):
        current = {"id": 3, "season": 1, "episode": 3, "file": "/tv/s01e03.mkv"}
        self.assertEqual(self.pick(SEASON_ONE + SEASON_TWO, current), 4)

    def test_last_episode_of_the_series_has_no_next(self):
        current = {"id": 5, "season": 2, "episode": 2, "file": "/tv/s02e02.mkv"}
        self.assertIsNone(self.pick(SEASON_ONE + SEASON_TWO, current))

    def test_specials_are_never_next_for_a_regular_episode(self):
        rows = SEASON_ONE + [ep(9, 0, 1)]
        current = {"id": 3, "season": 1, "episode": 3, "file": "/tv/s01e03.mkv"}
        self.assertIsNone(self.pick(rows, current))

    def test_a_special_is_followed_by_the_next_special_only(self):
        rows = [ep(8, 0, 1), ep(9, 0, 2)] + SEASON_ONE
        current = {"id": 8, "season": 0, "episode": 1, "file": "/tv/special1.mkv"}
        self.assertEqual(self.pick(rows, current), 9)
        current = {"id": 9, "season": 0, "episode": 2, "file": "/tv/special2.mkv"}
        self.assertIsNone(self.pick(rows, current))

    def test_episode_sharing_the_current_file_is_skipped(self):
        rows = [
            ep(1, 1, 1, file="/tv/double.mkv"),
            ep(2, 1, 2, file="/tv/double.mkv"),
            ep(3, 1, 3),
        ]
        current = {"id": 1, "season": 1, "episode": 1, "file": "/tv/double.mkv"}
        self.assertEqual(self.pick(rows, current), 3)

    def test_watched_episodes_are_offered_unless_skipping_them(self):
        rows = [ep(1, 1, 1), ep(2, 1, 2), ep(3, 1, 3, playcount=2), ep(4, 1, 4)]
        self.assertEqual(self.pick(rows), 3)
        self.assertEqual(self.pick(rows, skip_watched=True), 4)

    def test_unknown_numbering_gives_nothing(self):
        self.assertIsNone(self.pick(SEASON_ONE, {"id": 2, "season": None, "episode": 2}))
        self.assertIsNone(self.pick(SEASON_ONE, {"id": 2, "season": 1, "episode": -1}))

    def test_rows_without_ids_or_numbers_are_ignored(self):
        rows = [{"season": 1, "episode": 3}, {"episodeid": 7, "season": 1}, ep(3, 1, 3)]
        self.assertEqual(self.pick(rows), 3)


class DescribeCurrentEpisodeTests(unittest.TestCase):
    def test_missing_pieces_come_from_the_library_row(self):
        rpc = FakeRpc(
            {
                "VideoLibrary.GetEpisodeDetails": {
                    "result": {
                        "episodedetails": {
                            "tvshowid": 4,
                            "season": 1,
                            "episode": 2,
                            "file": "/tv/s01e02.mkv",
                            "playcount": 3,
                        }
                    }
                }
            }
        )
        item = {"type": "episode", "id": 2, "season": -1, "episode": -1, "file": ""}
        with patch.object(lookup, "jsonrpc", rpc):
            current = lookup.describe_current_episode(item)
        self.assertEqual(
            current,
            {
                "id": 2,
                "tvshowid": 4,
                "season": 1,
                "episode": 2,
                "file": "/tv/s01e02.mkv",
                "playcount": 3,
            },
        )

    def test_a_complete_item_still_reads_the_play_count(self):
        rpc = FakeRpc(
            {
                "VideoLibrary.GetEpisodeDetails": {
                    "result": {"episodedetails": {"playcount": 1}}
                }
            }
        )
        item = {
            "type": "episode",
            "id": 2,
            "tvshowid": 4,
            "season": 1,
            "episode": 2,
            "file": "/tv/a.mkv",
        }
        with patch.object(lookup, "jsonrpc", rpc):
            current = lookup.describe_current_episode(item)
        self.assertEqual(current["playcount"], 1)
        self.assertEqual(current["tvshowid"], 4)

    def test_a_file_that_is_not_a_library_episode_costs_no_call(self):
        rpc = FakeRpc({})
        with patch.object(lookup, "jsonrpc", rpc):
            current = lookup.describe_current_episode(
                {"type": "unknown", "id": -1, "season": 1, "episode": 2}
            )
        self.assertIsNone(current["id"])
        self.assertEqual(rpc.calls, [])


def library_rpc(rows=None, next_details=None):
    rows = SEASON_ONE + SEASON_TWO if rows is None else rows
    details = {
        3: {
            "episodeid": 3,
            "title": "The Third",
            "showtitle": "Show",
            "season": 1,
            "episode": 3,
            "file": "/tv/s01e03.mkv",
        }
    }

    def episode_details(params):
        if params["episodeid"] == 2:
            return {
                "result": {
                    "episodedetails": {
                        "tvshowid": 4,
                        "season": 1,
                        "episode": 2,
                        "file": "/tv/s01e02.mkv",
                        "playcount": 1,
                    }
                }
            }
        found = (next_details or details).get(params["episodeid"])
        return {"result": {"episodedetails": found}} if found else {}

    return FakeRpc(
        {
            "VideoLibrary.GetEpisodeDetails": episode_details,
            "VideoLibrary.GetEpisodes": {"result": {"episodes": rows}},
        }
    )


PLAYING = {"type": "episode", "id": 2, "tvshowid": 4, "season": 1, "episode": 2}


class FindLibrarySuccessorTests(unittest.TestCase):
    def test_returns_a_playable_description_of_the_next_episode(self):
        rpc = library_rpc()
        with patch.object(lookup, "jsonrpc", rpc):
            nxt = lookup.find_library_successor(PLAYING)
        self.assertEqual(
            nxt,
            {
                "source": lookup.SOURCE_LIBRARY,
                "episodeid": 3,
                "title": "The Third",
                "showtitle": "Show",
                "season": 1,
                "episode": 3,
                "file": "/tv/s01e03.mkv",
                "thumb": "",
            },
        )
        self.assertEqual(rpc.params_for("VideoLibrary.GetEpisodes")[0]["tvshowid"], 4)

    def test_nothing_without_a_show_id(self):
        rpc = library_rpc()
        with patch.object(lookup, "jsonrpc", rpc):
            self.assertIsNone(
                lookup.find_library_successor({"type": "unknown", "season": 1, "episode": 2})
            )
        self.assertEqual(rpc.params_for("VideoLibrary.GetEpisodes"), [])

    def test_last_episode_has_no_successor(self):
        rpc = library_rpc(rows=SEASON_ONE)
        item = dict(PLAYING, id=3, episode=3)
        with patch.object(lookup, "jsonrpc", rpc):
            self.assertIsNone(lookup.find_library_successor(item))

    def test_skip_watched_is_applied(self):
        rows = [ep(1, 1, 1), ep(2, 1, 2), ep(3, 1, 3, playcount=1), ep(4, 1, 4)]
        details = {4: {"episodeid": 4, "title": "Four", "season": 1, "episode": 4}}
        rpc = library_rpc(rows=rows, next_details=details)
        with patch.object(lookup, "jsonrpc", rpc):
            nxt = lookup.find_library_successor(PLAYING, skip_watched=True)
        self.assertEqual(nxt["episodeid"], 4)


def playlist_rpc(items, position=0, playlist_id=1):
    return FakeRpc(
        {
            "Player.GetActivePlayers": {"result": [{"playerid": 1, "type": "video"}]},
            "Player.GetProperties": {
                "result": {"playlistid": playlist_id, "position": position}
            },
            "Playlist.GetItems": {"result": {"items": items}},
        }
    )


class FindPlaylistSuccessorTests(unittest.TestCase):
    def test_next_playlist_item(self):
        rpc = playlist_rpc(
            [{"title": "Queued", "showtitle": "Show", "season": 2, "episode": 7, "file": "/q"}],
            position=3,
        )
        with patch.object(lookup, "jsonrpc", rpc):
            nxt = lookup.find_playlist_successor()
        self.assertEqual(nxt["source"], lookup.SOURCE_PLAYLIST)
        self.assertEqual((nxt["playerid"], nxt["playlistid"], nxt["position"]), (1, 1, 4))
        self.assertEqual(nxt["title"], "Queued")
        limits = rpc.params_for("Playlist.GetItems")[0]["limits"]
        self.assertEqual(limits, {"start": 4, "end": 5})

    def test_label_is_used_when_the_item_has_no_title(self):
        rpc = playlist_rpc([{"label": "From label"}])
        with patch.object(lookup, "jsonrpc", rpc):
            self.assertEqual(lookup.find_playlist_successor()["title"], "From label")

    def test_end_of_playlist_has_no_successor(self):
        with patch.object(lookup, "jsonrpc", playlist_rpc([])):
            self.assertIsNone(lookup.find_playlist_successor())

    def test_not_in_a_playlist(self):
        with patch.object(lookup, "jsonrpc", playlist_rpc([{"title": "x"}], position=-1)):
            self.assertIsNone(lookup.find_playlist_successor())
        with patch.object(lookup, "jsonrpc", playlist_rpc([{"title": "x"}], playlist_id=-1)):
            self.assertIsNone(lookup.find_playlist_successor())

    def test_no_video_player(self):
        with patch.object(lookup, "jsonrpc", FakeRpc({"Player.GetActivePlayers": {"result": []}})):
            self.assertIsNone(lookup.find_playlist_successor())

    def test_playlist_wins_over_the_library(self):
        rpc = playlist_rpc([{"title": "Queued"}])
        rpc.handlers["VideoLibrary.GetEpisodes"] = lambda p: self.fail("library asked")
        with patch.object(lookup, "jsonrpc", rpc):
            self.assertEqual(lookup.find_next_episode(PLAYING)["source"], "playlist")

    def test_library_is_used_when_the_playlist_has_nothing_next(self):
        rpc = library_rpc()
        rpc.handlers.update(playlist_rpc([]).handlers)
        with patch.object(lookup, "jsonrpc", rpc):
            self.assertEqual(lookup.find_next_episode(PLAYING)["source"], "library")


class EpisodeLabelTests(unittest.TestCase):
    def test_label_forms(self):
        label = lookup.episode_label
        self.assertEqual(label({"season": 1, "episode": 5, "title": "Pilot"}), "S01E05 \u00b7 Pilot")
        self.assertEqual(label({"season": 12, "episode": 103, "title": ""}), "S12E103")
        self.assertEqual(label({"season": None, "episode": None, "title": "Only"}), "Only")
        self.assertEqual(label({"season": -1, "episode": -1, "title": "Only"}), "Only")
        self.assertEqual(label({}), "")


class WindowTests(unittest.TestCase):
    def test_window_starts_lead_seconds_before_the_end(self):
        self.assertEqual(window_start(1500, 45), 1455)

    def test_clip_too_short_for_the_lead_never_prompts(self):
        self.assertIsNone(window_start(60, 45))
        self.assertIsNone(window_start(0, 45))
        self.assertIsNone(window_start(None, 45))
        self.assertIsNone(window_start(1500, 0))

    def test_window_bounds(self):
        self.assertFalse(in_prompt_window(1454.9, 1500, 45))
        self.assertTrue(in_prompt_window(1455.0, 1500, 45))
        self.assertTrue(in_prompt_window(1498.9, 1500, 45))
        self.assertFalse(in_prompt_window(1499.0, 1500, 45))
        self.assertFalse(in_prompt_window(10, 0, 45))

    def test_rearm_needs_a_clear_seek_back(self):
        state = NextEpisodeState(video="v", dismissed=True, started=True, failed=True)
        self.assertFalse(rearm_if_before_window(state, 1452, 1500, 45))
        self.assertTrue(state.dismissed)
        self.assertTrue(rearm_if_before_window(state, 1400, 1500, 45))
        self.assertFalse(state.dismissed or state.started or state.failed)
        self.assertFalse(rearm_if_before_window(state, 1400, 1500, 45))


LIBRARY_NEXT = {
    "source": "library",
    "episodeid": 3,
    "title": "The Third",
    "season": 1,
    "episode": 3,
}
PLAYLIST_NEXT = {"source": "playlist", "playerid": 1, "playlistid": 1, "position": 4}


class PlayNextTests(unittest.TestCase):
    def test_library_episode_is_opened_with_the_resume_choice(self):
        rpc = FakeRpc({"Player.Open": {"result": "OK"}})
        with patch.object(play, "jsonrpc", rpc):
            self.assertTrue(play.play_next(LIBRARY_NEXT, resume=False))
            self.assertTrue(play.play_next(LIBRARY_NEXT, resume=True))
        first, second = rpc.params_for("Player.Open")
        self.assertEqual(first, {"item": {"episodeid": 3}, "options": {"resume": False}})
        self.assertEqual(second["options"], {"resume": True})

    def test_playlist_item_is_reached_with_goto(self):
        rpc = FakeRpc({"Player.GoTo": {"result": "OK"}})
        with patch.object(play, "jsonrpc", rpc):
            self.assertTrue(play.play_next(PLAYLIST_NEXT))
        self.assertEqual(rpc.params_for("Player.GoTo"), [{"playerid": 1, "to": 4}])

    def test_refusal_and_unknown_sources_fail(self):
        with patch.object(play, "jsonrpc", FakeRpc({"Player.Open": {"error": {"code": -1}}})), patch.object(
            play, "log_error"
        ):
            self.assertFalse(play.play_next(LIBRARY_NEXT))
        with patch.object(play, "jsonrpc", FakeRpc({})), patch.object(play, "log_error"):
            self.assertFalse(play.play_next(LIBRARY_NEXT))
        self.assertFalse(play.play_next({"source": "plugin"}))


def playcount_rpc(count):
    return FakeRpc(
        {
            "VideoLibrary.GetEpisodeDetails": {
                "result": {"episodedetails": {"playcount": count}}
            },
            "VideoLibrary.SetEpisodeDetails": {"result": "OK"},
        }
    )


class MarkWatchedTests(unittest.TestCase):
    def test_marks_the_episode_when_kodi_did_not(self):
        rpc = playcount_rpc(1)
        with patch.object(play, "jsonrpc", rpc):
            self.assertTrue(play.mark_watched_if_needed(2, 1))
        params = rpc.params_for("VideoLibrary.SetEpisodeDetails")[0]
        self.assertEqual(params["episodeid"], 2)
        self.assertEqual(params["playcount"], 2)
        self.assertEqual(params["resume"], {"position": 0, "total": 0})
        self.assertTrue(re.match(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d$", params["lastplayed"]))

    def test_leaves_it_alone_when_kodi_already_counted_it(self):
        rpc = playcount_rpc(2)
        with patch.object(play, "jsonrpc", rpc):
            self.assertFalse(play.mark_watched_if_needed(2, 1))
        self.assertEqual(rpc.params_for("VideoLibrary.SetEpisodeDetails"), [])

    def test_nothing_to_do_without_ids_or_a_readable_count(self):
        rpc = FakeRpc({})
        with patch.object(play, "jsonrpc", rpc):
            self.assertFalse(play.mark_watched_if_needed(None, 1))
            self.assertFalse(play.mark_watched_if_needed(2, None))
            self.assertFalse(play.mark_watched_if_needed(2, 1))
        self.assertEqual(rpc.params_for("VideoLibrary.SetEpisodeDetails"), [])

    def test_schedule_marks_after_the_delay_and_respects_abort(self):
        class _Now:
            def __init__(self, target, *a, **k):
                self.target = target

            def start(self):
                self.target()

        for aborted, expected in ((False, 1), (True, 0)):
            monitor = types.SimpleNamespace(waitForAbort=lambda _s, a=aborted: a)
            rpc = playcount_rpc(1)
            with patch.object(play, "jsonrpc", rpc), patch.object(play.threading, "Thread", _Now):
                play.schedule_mark_watched(monitor, 2, 1)
            self.assertEqual(len(rpc.params_for("VideoLibrary.SetEpisodeDetails")), expected)

    def test_schedule_does_nothing_without_a_play_count(self):
        rpc = playcount_rpc(1)
        with patch.object(play, "jsonrpc", rpc), patch.object(play.threading, "Thread") as thread:
            play.schedule_mark_watched(MagicMock(), 2, None)
            play.schedule_mark_watched(MagicMock(), None, 1)
        thread.assert_not_called()


class ToastTests(unittest.TestCase):
    def addon(self):
        addon = MagicMock()
        addon.getAddonInfo = lambda key: "icon.png" if key == "icon" else "w:/addon"
        addon.getLocalizedString = lambda _id: ""
        return addon

    def test_texts_carry_the_episode_and_the_hint(self):
        heading, body = toast.build_toast_texts(
            self.addon(), {"season": 2, "episode": 4, "title": "A very long episode title"}
        )
        self.assertEqual(heading, "Play next episode?")
        self.assertEqual(body, "S02E04 \u00b7 A very long episode title \u00b7 Press OK to play")
        self.assertEqual(
            toast.build_toast_texts(self.addon(), {})[1], "Press OK to play"
        )

    def run_toast(self, result, head=1455.0):
        posted = []

        class _Keys:
            def __init__(self, *args):
                self.result = result

            def doModal(self):
                pass

            def close(self):
                pass

        player = types.SimpleNamespace(getTime=lambda: head)
        dialog = MagicMock()
        dialog.notification = lambda *a: posted.append(a)
        with patch.object(toast, "SkipToastKeys", _Keys), patch.object(
            toast, "_toast_keepalive", lambda *a, **k: None
        ), patch.object(toast, "_dismiss_toast") as dismiss, patch.object(
            toast.xbmcgui, "Dialog", lambda: dialog
        ):
            answer = toast.show_next_episode_toast(
                self.addon(), player, {"title": "T", "season": 1, "episode": 2}, 1455.0, 1500.0
            )
        return answer, posted, dismiss

    def test_the_toast_window_is_cleared_before_the_toast_is_posted(self):
        order = []

        class _Keys:
            def __init__(self, *args):
                self.result = True

            def doModal(self):
                pass

            def close(self):
                pass

        player = types.SimpleNamespace(getTime=lambda: 1455.0)
        dialog = MagicMock()
        dialog.notification = lambda *a: order.append("post")
        with patch.object(toast, "SkipToastKeys", _Keys), patch.object(
            toast, "_toast_keepalive", lambda *a, **k: None
        ), patch.object(toast, "_dismiss_toast"), patch.object(
            toast, "ready_toast_window", lambda: order.append("ready")
        ), patch.object(toast.xbmcgui, "Dialog", lambda: dialog):
            toast.show_next_episode_toast(
                self.addon(), player, {"title": "T", "season": 1, "episode": 2}, 1455.0, 1500.0
            )
        self.assertEqual(order, ["ready", "post"])

    def test_answers_are_passed_through(self):
        for result in (True, False, None):
            answer, _posted, dismiss = self.run_toast(result)
            self.assertIs(answer, result)
            dismiss.assert_called_once()

    def test_toast_lasts_until_the_end_and_is_not_shortened(self):
        _answer, posted, _dismiss = self.run_toast(True, head=1460.0)
        heading, body, icon, ms, sound = posted[0]
        self.assertEqual(ms, 40000)
        self.assertEqual(icon, "icon.png")
        self.assertFalse(sound)
        self.assertIn("S01E02", body)


class _Player:
    def __init__(self, total=1500.0):
        self.total = total

    def getTotalTime(self):
        return self.total


SETTINGS = {
    "next_episode_enabled": True,
    "next_episode_autoplay": False,
    "next_episode_lead_seconds": 45,
    "next_episode_still_watching": True,
    "next_episode_still_watching_after": 3,
    "next_episode_start_at_credits": False,
    "next_episode_hide_skip_dialogs": True,
    "next_episode_mark_watched": True,
    "next_episode_skip_watched": False,
    "next_episode_resume": True,
}


class HandlerTests(unittest.TestCase):
    def setUp(self):
        self.monitor = types.SimpleNamespace(next_episode_state=None)
        self.ctx = types.SimpleNamespace(monitor=self.monitor, player=_Player())
        self.settings = dict(SETTINGS)
        self.answers = []
        self.plays = []
        self.play_result = True
        self.marks = []
        self.upnext = False
        self.notes = []
        self.lookups = []
        self.now = 1000.0
        self.idle = None
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
                    self.settings.get("next_episode_popup_duration", 0),
                    self.settings.get("next_episode_popup_end_action", "Close"),
                ),
            ),
            patch.object(step, "_upnext_enabled", lambda: self.upnext),
            patch.object(step, "_idle_seconds", lambda: self.idle),
            patch.object(step, "show_next_episode_prompt", self._toast),
            patch.object(step, "play_next", self._play),
            patch.object(
                step, "schedule_mark_watched", lambda *a: self.marks.append(a[1:])
            ),
            patch.object(step, "notify_skippy", lambda *a, **k: self.notes.append(a)),
            patch.object(
                step, "_start_lookup", lambda *a, **k: self.lookups.append((a, k))
            ),
            patch.object(step.time, "monotonic", lambda: self.now),
            patch.object(step, "log"),
            patch.object(step, "log_error"),
        ]
        for p in stack:
            p.start()
            self.addCleanup(p.stop)
        self.toast_calls = []
        self.still_calls = []
        self.span_calls = []

    def _toast(
        self, addon, player, item, start, total, still_watching=False, timed=False, end_action="Close"
    ):
        self.toast_calls.append((item, start, total))
        self.still_calls.append(still_watching)
        self.span_calls.append((timed, end_action))
        return self.answers.pop(0) if self.answers else None

    def _play(self, item, resume=True):
        self.plays.append((item, resume))
        return self.play_result

    def found_state(self, video="ep.mkv", **kw):
        state = NextEpisodeState(
            video=video,
            lookup=LOOKUP_FOUND,
            next_item=LIBRARY_NEXT,
            current_episode_id=7,
            current_playcount=1,
            **kw
        )
        self.monitor.next_episode_state = state
        return state

    def tick(self, current_time, *, playback_type="episode", video="ep.mkv"):
        return step.handle_next_episode(
            self.ctx,
            video=video,
            playback_type=playback_type,
            current_time=current_time,
            player_item={"type": "episode", "id": 7},
        )

    def test_disabled_does_nothing(self):
        self.settings["next_episode_enabled"] = False
        self.found_state()
        self.assertEqual(self.tick(1470.0), step.IDLE_TICK)
        self.assertEqual((self.toast_calls, self.plays), ([], []))

    def test_only_episodes_and_movies_are_handled(self):
        self.found_state()
        for kind in ("", "musicvideo", "tvshow", "unknown"):
            self.assertEqual(self.tick(1470.0, playback_type=kind), step.IDLE_TICK, kind)
        self.assertEqual(self.toast_calls, [])

    def test_a_movie_is_not_handled_while_the_movie_setting_is_off(self):
        self.settings["next_episode_movies"] = False
        self.found_state()
        self.assertEqual(self.tick(1470.0, playback_type="movie"), step.IDLE_TICK)
        self.assertEqual((self.toast_calls, self.lookups), ([], []))

    def test_up_next_addon_keeps_the_prompt_off_and_is_announced_once(self):
        self.upnext = True
        self.found_state()
        for _ in range(3):
            self.assertEqual(self.tick(1470.0), step.IDLE_TICK)
        self.assertEqual(len(self.notes), 1)
        self.assertEqual(self.toast_calls, [])

    def test_first_tick_starts_the_lookup(self):
        self.assertEqual(self.tick(10.0), step.IDLE_TICK)
        self.assertEqual(len(self.lookups), 1)
        self.assertEqual(self.monitor.next_episode_state.video, "ep.mkv")

    def test_state_follows_the_video(self):
        self.found_state(video="old.mkv")
        self.tick(10.0, video="new.mkv")
        self.assertEqual(self.monitor.next_episode_state.video, "new.mkv")
        self.assertEqual(self.monitor.next_episode_state.lookup, LOOKUP_IDLE)

    def test_no_next_episode_leaves_skip_dialogs_alone(self):
        state = self.found_state()
        state.lookup = LOOKUP_NONE
        state.next_item = None
        self.assertEqual(self.tick(1470.0), step.IDLE_TICK)
        self.assertEqual(self.toast_calls, [])

    def test_before_the_window_nothing_happens(self):
        self.found_state()
        self.assertEqual(self.tick(1000.0), step.IDLE_TICK)
        self.assertEqual(self.toast_calls, [])

    def test_unknown_total_time_never_prompts(self):
        self.found_state()
        self.ctx.player = _Player(0.0)
        self.assertEqual(self.tick(1470.0), step.IDLE_TICK)

    def test_accepting_the_prompt_starts_the_next_episode(self):
        state = self.found_state()
        self.answers = [True]
        result = self.tick(1460.0)
        self.assertEqual(result, step.NextEpisodeTick(hide_skip_dialogs=True, switched=True))
        self.assertEqual(self.toast_calls, [(LIBRARY_NEXT, 1455.0, 1500.0)])
        self.assertEqual(self.plays, [(LIBRARY_NEXT, True)])
        self.assertEqual(self.marks, [(7, 1, "episode")])
        self.assertTrue(state.started)

    def test_nothing_is_started_twice(self):
        self.found_state()
        self.answers = [True]
        self.tick(1460.0)
        again = self.tick(1461.0)
        self.assertEqual(again, step.NextEpisodeTick(hide_skip_dialogs=True))
        self.assertEqual(len(self.plays), 1)
        self.assertEqual(len(self.toast_calls), 1)

    def test_dismissing_the_prompt_keeps_it_closed_but_skip_dialogs_hidden(self):
        state = self.found_state()
        self.answers = [False]
        first = self.tick(1460.0)
        self.assertEqual(first, step.NextEpisodeTick(hide_skip_dialogs=True))
        self.assertTrue(state.dismissed)
        self.now += 60
        self.assertEqual(self.tick(1465.0), step.NextEpisodeTick(hide_skip_dialogs=True))
        self.assertEqual(len(self.toast_calls), 1)
        self.assertEqual(self.plays, [])

    def test_a_prompt_that_closed_by_itself_comes_back_after_a_pause(self):
        state = self.found_state()
        self.answers = [None, None]
        self.tick(1460.0)
        self.assertFalse(state.dismissed)
        self.now += MIN_REPROMPT_S - 1
        self.tick(1461.0)
        self.assertEqual(len(self.toast_calls), 1)
        self.now += 2
        self.tick(1463.0)
        self.assertEqual(len(self.toast_calls), 2)

    def test_autoplay_starts_without_asking(self):
        self.settings["next_episode_autoplay"] = True
        self.found_state()
        result = self.tick(1456.0)
        self.assertEqual(result, step.NextEpisodeTick(hide_skip_dialogs=True, switched=True))
        self.assertEqual(self.toast_calls, [])
        self.assertEqual(self.plays, [(LIBRARY_NEXT, True)])

    def test_autoplay_waits_for_the_window(self):
        self.settings["next_episode_autoplay"] = True
        self.found_state()
        self.assertEqual(self.tick(1454.0), step.IDLE_TICK)
        self.assertEqual(self.plays, [])

    def test_the_lead_time_setting_moves_the_window(self):
        self.settings["next_episode_autoplay"] = True
        self.settings["next_episode_lead_seconds"] = 120
        self.found_state()
        self.assertEqual(self.tick(1370.0), step.IDLE_TICK)
        self.assertTrue(self.tick(1380.0).switched)

    # --- the prompt belongs to the end of its own episode ----------------------

    def _start_of_the_next_episode(self):
        """The first tick on a new video; its state starts fresh and its lookup is done."""
        self.assertEqual(self.tick(1.0, video="e2.mkv"), step.IDLE_TICK)
        state = self.monitor.next_episode_state
        self.assertEqual(state.video, "e2.mkv")
        self.assertFalse(state.started or state.dismissed or state.failed)
        state.lookup = LOOKUP_FOUND
        state.next_item = LIBRARY_NEXT
        return state

    def test_the_start_of_the_next_episode_is_never_held(self):
        self.found_state(video="e1.mkv")
        self.answers = [True]
        self.assertTrue(self.tick(1460.0, video="e1.mkv").switched)
        self._start_of_the_next_episode()
        for head in (0.0, 1.0, 5.0, 29.0, 60.0, 600.0, 1400.0):
            self.assertEqual(self.tick(head, video="e2.mkv"), step.IDLE_TICK, head)
        self.assertEqual(len(self.toast_calls), 1)

    def test_a_dismissed_prompt_does_not_hold_back_the_next_episode(self):
        self.found_state(video="e1.mkv")
        self.answers = [False]
        self.assertTrue(self.tick(1460.0, video="e1.mkv").hide_skip_dialogs)
        self._start_of_the_next_episode()
        for head in (0.0, 5.0, 90.0):
            self.assertFalse(self.tick(head, video="e2.mkv").hide_skip_dialogs, head)

    def test_a_hand_off_nobody_asked_for_does_not_hold_back_the_next_episode(self):
        self.settings["next_episode_autoplay"] = True
        self.found_state(video="e1.mkv")
        self.assertTrue(self.tick(1456.0, video="e1.mkv").switched)
        self._start_of_the_next_episode()
        for head in (0.0, 5.0, 90.0):
            self.assertFalse(self.tick(head, video="e2.mkv").hide_skip_dialogs, head)

    def test_credits_of_the_episode_before_do_not_open_the_window_at_the_start(self):
        self.settings["next_episode_start_at_credits"] = True
        self.monitor.current_segments = ["segments of the episode before"]
        self.found_state(video="e2.mkv")
        with patch.object(step, "credits_start_seconds", lambda segs, total: 1380.0):
            for head in (0.0, 10.0, 90.0, 1000.0):
                self.assertEqual(self.tick(head, video="e2.mkv"), step.IDLE_TICK, head)

    def test_a_refused_hand_off_is_not_retried(self):
        self.settings["next_episode_autoplay"] = True
        self.play_result = False
        state = self.found_state()
        self.assertFalse(self.tick(1456.0).switched)
        self.assertTrue(state.failed)
        self.assertFalse(self.tick(1457.0).switched)
        self.assertEqual(len(self.plays), 1)
        self.assertEqual(self.marks, [])

    def test_hiding_skip_dialogs_can_be_turned_off(self):
        self.settings["next_episode_hide_skip_dialogs"] = False
        self.found_state()
        self.answers = [False]
        self.assertEqual(self.tick(1460.0), step.IDLE_TICK)
        self.assertEqual(self.tick(1465.0), step.IDLE_TICK)

    def test_marking_watched_and_resume_follow_their_settings(self):
        self.settings["next_episode_autoplay"] = True
        self.settings["next_episode_mark_watched"] = False
        self.settings["next_episode_resume"] = False
        self.found_state()
        self.tick(1456.0)
        self.assertEqual(self.marks, [])
        self.assertEqual(self.plays, [(LIBRARY_NEXT, False)])

    def test_seeking_back_before_the_window_rearms_a_dismissed_prompt(self):
        state = self.found_state()
        self.answers = [False, False]
        self.tick(1460.0)
        self.assertTrue(state.dismissed)
        self.assertEqual(self.tick(1000.0), step.IDLE_TICK)
        self.assertFalse(state.dismissed)
        self.now += 60
        self.tick(1460.0)
        self.assertEqual(len(self.toast_calls), 2)

    def test_a_failing_step_never_raises_and_logs_once(self):
        self.found_state()

        def boom(*a, **k):
            raise RuntimeError("boom")

        with patch.object(step, "show_next_episode_prompt", boom), patch.object(
            step, "log_error"
        ) as log_error:
            for t in (1460.0, 1470.0, 1480.0):
                self.now += 10
                self.assertEqual(self.tick(t), step.IDLE_TICK)
        self.assertEqual(log_error.call_count, 1)

    # --- "still watching?" guard ---------------------------------------------

    def new_episode(self, video):
        """Start a fresh episode state the way the loop does, with the next one already found."""
        self.monitor.next_episode_state = None
        self.tick(10.0, video=video)
        state = self.monitor.next_episode_state
        state.lookup = LOOKUP_FOUND
        state.next_item = LIBRARY_NEXT
        state.current_episode_id = 7
        state.current_playcount = 1
        return state

    def finish_unattended(self, state, video, at=1456.0):
        """The viewer pressed nothing since the episode began: reach the prompt window."""
        self.now = state.created_mono + 1400.0
        self.idle = 1400.0
        return self.tick(at, video=video)

    def play_out(self, video):
        """Nobody answered the prompt and the episode played on to its last seconds."""
        self.now += 1.0
        self.tick(1497.0, video=video)

    def hand_off(self, video, after=4.0):
        """Kodi (play next video, a playlist) starts the next video by itself; the old state stays."""
        self.now += after
        self.tick(10.0, video=video)
        state = self.monitor.next_episode_state
        state.lookup = LOOKUP_FOUND
        state.next_item = LIBRARY_NEXT
        state.current_episode_id = 8
        state.current_playcount = 1
        return state

    def chain(self):
        return self.monitor.next_episode_chain

    def test_autoplay_counts_episodes_and_asks_at_the_limit(self):
        self.settings["next_episode_autoplay"] = True
        self.settings["next_episode_still_watching_after"] = 3
        results = []
        for video in ("e1.mkv", "e2.mkv", "e3.mkv"):
            state = self.new_episode(video)
            results.append(self.finish_unattended(state, video))
        self.assertEqual([r.switched for r in results], [True, True, False])
        self.assertEqual(len(self.plays), 2)
        self.assertEqual(self.still_calls, [True])
        self.assertEqual(self.chain().unattended, 3)

    def test_the_question_replaces_the_autoplay(self):
        self.settings["next_episode_autoplay"] = True
        state = self.new_episode("e1.mkv")
        self.chain().unattended = 2
        result = self.finish_unattended(state, "e1.mkv")
        self.assertEqual(result, step.NextEpisodeTick(hide_skip_dialogs=True, switched=False))
        self.assertEqual(self.plays, [])
        self.assertEqual(self.still_calls, [True])

    def test_continue_plays_the_next_episode_and_starts_the_count_over(self):
        self.settings["next_episode_autoplay"] = True
        state = self.new_episode("e1.mkv")
        self.chain().unattended = 2
        self.answers = [True]
        result = self.finish_unattended(state, "e1.mkv")
        self.assertTrue(result.switched)
        self.assertEqual(self.plays, [(LIBRARY_NEXT, True)])
        self.assertFalse(self.chain().autoplay_pending)
        self.new_episode("e2.mkv")
        self.assertEqual(self.chain().unattended, 0)

    def test_stop_keeps_the_next_episode_from_starting(self):
        self.settings["next_episode_autoplay"] = True
        state = self.new_episode("e1.mkv")
        self.chain().unattended = 2
        self.answers = [False]
        result = self.finish_unattended(state, "e1.mkv")
        self.assertFalse(result.switched)
        self.assertTrue(state.dismissed)
        self.assertEqual(self.plays, [])
        self.assertFalse(self.finish_unattended(state, "e1.mkv").switched)
        self.assertEqual(self.still_calls, [True])

    def test_a_button_press_during_the_episode_starts_the_count_over(self):
        self.settings["next_episode_autoplay"] = True
        state = self.new_episode("e1.mkv")
        self.chain().unattended = 2
        self.now = state.created_mono + 1400.0
        self.idle = 300.0
        result = self.tick(1456.0, video="e1.mkv")
        self.assertTrue(result.switched)
        self.assertEqual(self.chain().unattended, 0)
        self.assertEqual(self.still_calls, [])

    def test_an_unreadable_idle_clock_never_asks(self):
        self.settings["next_episode_autoplay"] = True
        state = self.new_episode("e1.mkv")
        self.chain().unattended = 9
        self.now = state.created_mono + 1400.0
        self.idle = None
        self.assertTrue(self.tick(1456.0, video="e1.mkv").switched)
        self.assertEqual(self.still_calls, [])

    def test_the_guard_can_be_turned_off(self):
        self.settings["next_episode_autoplay"] = True
        self.settings["next_episode_still_watching"] = False
        state = self.new_episode("e1.mkv")
        self.chain().unattended = 9
        self.assertTrue(self.finish_unattended(state, "e1.mkv").switched)
        self.assertEqual(self.still_calls, [])

    def test_the_guard_can_be_turned_off_without_autoplay_too(self):
        self.settings["next_episode_still_watching"] = False
        state = self.new_episode("e1.mkv")
        self.chain().unattended = 9
        self.finish_unattended(state, "e1.mkv")
        self.assertEqual(self.still_calls, [False])

    def test_without_autoplay_the_first_prompt_is_the_usual_one(self):
        state = self.new_episode("e1.mkv")
        self.finish_unattended(state, "e1.mkv")
        self.assertEqual(self.still_calls, [False])
        self.assertEqual(self.chain().unattended, 1)

    def test_without_autoplay_the_question_replaces_the_prompt_at_the_limit(self):
        state = self.new_episode("e1.mkv")
        self.chain().unattended = 2
        result = self.finish_unattended(state, "e1.mkv")
        self.assertEqual(self.still_calls, [True])
        self.assertEqual(result, step.NextEpisodeTick(hide_skip_dialogs=True, switched=False))
        self.assertEqual(self.plays, [])
        self.assertEqual(self.chain().unattended, 3)

    def test_without_autoplay_the_question_runs_to_the_end_of_the_file(self):
        self.settings["next_episode_popup_duration"] = 20
        self.settings["next_episode_popup_end_action"] = "Play"
        state = self.new_episode("e1.mkv")
        self.chain().unattended = 2
        self.finish_unattended(state, "e1.mkv")
        self.assertEqual(self.span_calls, [(False, "Close")])

    def test_without_autoplay_continue_plays_the_next_episode_and_starts_over(self):
        state = self.new_episode("e1.mkv")
        self.chain().unattended = 2
        self.answers = [True]
        result = self.finish_unattended(state, "e1.mkv")
        self.assertTrue(result.switched)
        self.assertEqual(self.plays, [(LIBRARY_NEXT, True)])
        self.assertFalse(self.chain().autoplay_pending)
        self.new_episode("e2.mkv")
        self.assertEqual(self.chain().unattended, 0)

    def test_without_autoplay_stop_keeps_the_next_episode_from_starting(self):
        state = self.new_episode("e1.mkv")
        self.chain().unattended = 2
        self.answers = [False]
        result = self.finish_unattended(state, "e1.mkv")
        self.assertFalse(result.switched)
        self.assertTrue(state.dismissed)
        self.assertEqual(self.plays, [])

    # --- episodes Kodi or a playlist starts by itself ------------------------

    def test_an_episode_kodi_starts_by_itself_is_counted(self):
        self.settings["next_episode_still_watching_after"] = 2
        state = self.new_episode("e1.mkv")
        self.finish_unattended(state, "e1.mkv")
        self.play_out("e1.mkv")
        self.assertEqual(self.still_calls, [False])
        state = self.hand_off("e2.mkv")
        self.assertEqual(self.chain().unattended, 1)
        self.finish_unattended(state, "e2.mkv")
        self.assertEqual(self.still_calls, [False, True])
        self.assertEqual(self.chain().unattended, 2)

    def test_a_video_started_after_a_long_gap_starts_the_count_over(self):
        state = self.new_episode("e1.mkv")
        self.finish_unattended(state, "e1.mkv")
        self.play_out("e1.mkv")
        self.hand_off("e2.mkv", after=HANDOFF_GAP_S + 5.0)
        self.assertEqual(self.chain().unattended, 0)

    def test_an_episode_left_before_its_end_starts_the_count_over(self):
        state = self.new_episode("e1.mkv")
        self.finish_unattended(state, "e1.mkv")
        self.hand_off("e2.mkv")
        self.assertEqual(self.chain().unattended, 0)

    def test_closing_the_prompt_counts_as_being_there(self):
        state = self.new_episode("e1.mkv")
        self.answers = [False]
        self.finish_unattended(state, "e1.mkv")
        self.play_out("e1.mkv")
        self.hand_off("e2.mkv")
        self.assertEqual(self.chain().unattended, 0)

    def test_play_now_counts_as_being_there_even_when_it_failed(self):
        self.play_result = False
        state = self.new_episode("e1.mkv")
        self.answers = [True]
        self.finish_unattended(state, "e1.mkv")
        self.assertTrue(state.answered)
        self.assertFalse(state.started)
        self.play_out("e1.mkv")
        self.hand_off("e2.mkv")
        self.assertEqual(self.chain().unattended, 0)

    def test_play_now_late_in_the_prompt_counts_as_being_there(self):
        state = self.new_episode("e1.mkv")
        self.answers = [True]
        self.finish_unattended(state, "e1.mkv", at=1497.0)
        self.hand_off("e2.mkv")
        self.assertEqual(self.chain().unattended, 0)

    def test_the_playhead_is_remembered_for_the_next_episode(self):
        state = self.new_episode("e1.mkv")
        self.now = 2000.0
        self.tick(900.0, video="e1.mkv")
        self.assertEqual((state.last_time, state.total, state.last_seen_mono), (900.0, 1500.0, 2000.0))

    def test_an_unreadable_playhead_is_ignored(self):
        state = self.found_state()
        step._note_progress(state, "x", 1500.0)
        step._note_progress(state, None, None)
        self.assertEqual((state.last_time, state.total, state.last_seen_mono), (0.0, 0.0, 0.0))

    def test_a_manual_start_ends_the_run(self):
        self.settings["next_episode_autoplay"] = True
        self.chain_with(2)
        self.new_episode("e5.mkv")
        self.assertEqual(self.chain().unattended, 0)

    def chain_with(self, unattended, pending=False):
        self.monitor.next_episode_chain = WatchChain(unattended, pending)

    def test_an_automatic_hand_off_keeps_the_run_going(self):
        self.chain_with(2, pending=True)
        self.new_episode("e5.mkv")
        self.assertEqual(self.chain().unattended, 2)
        self.assertFalse(self.chain().autoplay_pending)

    def test_the_decision_is_made_once_per_episode(self):
        self.settings["next_episode_autoplay"] = True
        state = self.new_episode("e1.mkv")
        self.chain().unattended = 2
        self.finish_unattended(state, "e1.mkv")
        self.now += MIN_REPROMPT_S + 1
        self.tick(1460.0, video="e1.mkv")
        self.assertEqual(self.chain().unattended, 3)
        self.assertEqual(self.still_calls, [True, True])

    def test_seeking_back_asks_again_later(self):
        self.settings["next_episode_autoplay"] = True
        state = self.new_episode("e1.mkv")
        self.chain().unattended = 2
        self.answers = [False]
        self.finish_unattended(state, "e1.mkv")
        self.assertTrue(state.dismissed)
        self.assertTrue(state.guard_checked)
        self.tick(600.0, video="e1.mkv")
        self.assertFalse(state.dismissed)
        self.assertFalse(state.guard_checked)
        self.assertFalse(state.guard_ask)

    def test_a_playlist_gets_a_watchdog_that_continue_stands_down(self):
        self.settings["next_episode_autoplay"] = True
        events = []

        def fake_watchdog(player, start, total):
            event = threading.Event()
            events.append((start, total, event))
            return event

        state = self.new_episode("e1.mkv")
        state.next_item = dict(PLAYLIST_NEXT)
        self.chain().unattended = 2
        self.answers = [True]
        with patch.object(step, "start_stop_watchdog", fake_watchdog):
            self.finish_unattended(state, "e1.mkv")
        self.assertEqual([(s, t) for s, t, _ in events], [(1455.0, 1500.0)])
        self.assertTrue(events[0][2].is_set())

    def test_a_library_episode_gets_a_watchdog_too(self):
        self.settings["next_episode_autoplay"] = True
        state = self.new_episode("e1.mkv")
        self.chain().unattended = 2
        with patch.object(step, "start_stop_watchdog") as watchdog:
            self.finish_unattended(state, "e1.mkv")
        watchdog.assert_called_once_with(self.ctx.player, 1455.0, 1500.0)

    def test_without_autoplay_the_question_gets_a_watchdog_and_continue_stands_it_down(self):
        events = []

        def fake_watchdog(player, start, total):
            event = threading.Event()
            events.append(event)
            return event

        state = self.new_episode("e1.mkv")
        self.chain().unattended = 2
        self.answers = [True]
        with patch.object(step, "start_stop_watchdog", fake_watchdog):
            self.finish_unattended(state, "e1.mkv")
        self.assertEqual(len(events), 1)
        self.assertTrue(events[0].is_set())

    def test_the_usual_prompt_needs_no_watchdog(self):
        state = self.new_episode("e1.mkv")
        with patch.object(step, "start_stop_watchdog") as watchdog:
            self.finish_unattended(state, "e1.mkv")
        watchdog.assert_not_called()

    def test_the_watchdog_outlives_stop_and_is_started_only_once(self):
        self.settings["next_episode_autoplay"] = True
        events = []

        def fake_watchdog(player, start, total):
            event = threading.Event()
            events.append(event)
            return event

        state = self.new_episode("e1.mkv")
        state.next_item = dict(PLAYLIST_NEXT)
        self.chain().unattended = 2
        self.answers = [None, False]
        with patch.object(step, "start_stop_watchdog", fake_watchdog):
            self.finish_unattended(state, "e1.mkv")
            self.now += MIN_REPROMPT_S + 1
            self.tick(1460.0, video="e1.mkv")
        self.assertEqual(len(events), 1)
        self.assertFalse(events[0].is_set())

    def test_a_new_video_stands_the_old_watchdog_down(self):
        self.settings["next_episode_autoplay"] = True
        state = self.new_episode("e1.mkv")
        event = threading.Event()
        state.guard_cancel = event
        self.tick(10.0, video="e2.mkv")
        self.assertTrue(event.is_set())
        self.assertEqual(self.monitor.next_episode_state.video, "e2.mkv")

    # --- start at the credits ------------------------------------------------

    def test_the_prompt_starts_at_the_credits_when_asked_to(self):
        self.settings["next_episode_start_at_credits"] = True
        self.found_state()
        with patch.object(step, "credits_start_seconds", lambda segs, total: 1200.0):
            self.assertEqual(self.tick(1199.0), step.IDLE_TICK)
            self.tick(1201.0)
        self.assertEqual(self.toast_calls, [(LIBRARY_NEXT, 1200.0, 1500.0)])

    def test_autoplay_starts_at_the_credits_too(self):
        self.settings["next_episode_autoplay"] = True
        self.settings["next_episode_start_at_credits"] = True
        self.found_state()
        with patch.object(step, "credits_start_seconds", lambda segs, total: 1200.0):
            self.assertEqual(self.tick(1100.0), step.IDLE_TICK)
            self.assertTrue(self.tick(1205.0).switched)

    def test_credits_are_ignored_unless_the_setting_is_on(self):
        self.found_state()
        with patch.object(step, "credits_start_seconds", lambda segs, total: 1200.0):
            self.assertEqual(self.tick(1300.0), step.IDLE_TICK)

    def test_without_a_credits_segment_the_usual_time_applies(self):
        self.settings["next_episode_start_at_credits"] = True
        self.found_state()
        with patch.object(step, "credits_start_seconds", lambda segs, total: None):
            self.assertEqual(self.tick(1300.0), step.IDLE_TICK)
            self.tick(1456.0)
        self.assertEqual(self.toast_calls, [(LIBRARY_NEXT, 1455.0, 1500.0)])

    def test_the_segments_of_the_playing_video_are_what_is_looked_at(self):
        self.settings["next_episode_start_at_credits"] = True
        self.monitor.current_segments = ["segments"]
        self.found_state()
        seen = []

        def fake(segs, total):
            seen.append((segs, total))
            return None

        with patch.object(step, "credits_start_seconds", fake):
            self.tick(100.0)
        self.assertEqual(seen, [(["segments"], 1500.0)])

    def test_seeking_back_before_the_credits_rearms_the_prompt(self):
        self.settings["next_episode_start_at_credits"] = True
        state = self.found_state()
        self.answers = [False]
        with patch.object(step, "credits_start_seconds", lambda segs, total: 1200.0):
            self.tick(1210.0)
            self.assertTrue(state.dismissed)
            self.tick(1100.0)
        self.assertFalse(state.dismissed)


class RunLookupTests(unittest.TestCase):
    def test_found(self):
        state = NextEpisodeState(video="v")
        current = {"id": 7, "playcount": 3}
        with patch.object(step, "describe_current_episode", return_value=current), patch.object(
            step, "find_next_episode", return_value=LIBRARY_NEXT
        ) as find, patch.object(step, "log"):
            step.run_lookup(state, {"id": 7}, True)
        self.assertEqual(state.lookup, LOOKUP_FOUND)
        self.assertEqual(state.next_item, LIBRARY_NEXT)
        self.assertEqual((state.current_episode_id, state.current_playcount), (7, 3))
        self.assertEqual(find.call_args.kwargs, {"skip_watched": True, "current": current})

    def test_none_found(self):
        state = NextEpisodeState(video="v")
        with patch.object(step, "describe_current_episode", return_value={}), patch.object(
            step, "find_next_episode", return_value=None
        ), patch.object(step, "log"):
            step.run_lookup(state, {}, False)
        self.assertEqual(state.lookup, LOOKUP_NONE)

    def test_a_failure_ends_as_none(self):
        state = NextEpisodeState(video="v")
        with patch.object(step, "describe_current_episode", side_effect=ValueError("x")), patch.object(
            step, "log_error"
        ) as log_error:
            step.run_lookup(state, {}, False)
        self.assertEqual(state.lookup, LOOKUP_NONE)
        log_error.assert_called_once()


class PlayerItemRequestTests(unittest.TestCase):
    def test_item_request_asks_for_the_show_id_and_numbering(self):
        import service_playback_context as context

        requests = []

        def fake_rpc(payload):
            import json

            data = json.loads(payload)
            requests.append(data)
            if data["method"] == "Player.GetActivePlayers":
                return json.dumps({"result": [{"playerid": 1, "type": "video"}]})
            return json.dumps({"result": {"item": {"title": "x", "file": "/a"}}})

        with patch.object(context.xbmc, "executeJSONRPC", fake_rpc):
            context._fetch_player_item_via_jsonrpc(lambda item: "episode", log_jsonrpc=False)
        item_request = [r for r in requests if r["method"] == "Player.GetItem"][0]
        properties = item_request["params"]["properties"]
        for needed in ("file", "title", "showtitle", "episode", "season", "tvshowid"):
            self.assertIn(needed, properties)


class SettingsDefinitionTests(unittest.TestCase):
    def category(self):
        tree = ET.parse(os.path.join(ROOT, "resources", "settings.xml"))
        for cat in tree.getroot().iter("category"):
            if cat.get("id") == "next_episode":
                return cat
        self.fail("category next_episode missing")

    def settings(self):
        return {s.get("id"): s for s in self.category().iter("setting")}

    def test_defaults_and_levels(self):
        expected = {
            "next_episode_enabled": ("false", "0"),
            "next_episode_autoplay": ("false", "0"),
            "next_episode_per_show": ("false", "0"),
            "settings_action_manage_next_episode_shows": (None, "0"),
            "settings_action_clear_next_episode_shows": (None, "0"),
            "next_episode_lead_seconds": ("45", "0"),
            "next_episode_still_watching": ("true", "1"),
            "next_episode_still_watching_after": ("3", "1"),
            "next_episode_start_at_credits": ("false", "0"),
            "next_episode_popup_duration": ("0", "1"),
            "next_episode_popup_end_action": ("Close", "1"),
            "next_episode_hide_skip_dialogs": ("true", "1"),
            "next_episode_mark_watched": ("true", "1"),
            "next_episode_movies": ("true", "1"),
            "next_episode_skip_watched": ("false", "2"),
            "next_episode_resume": ("true", "2"),
            "next_episode_use_provider_data": ("true", "2"),
            "next_episode_popup_style": ("Custom", "0"),
            "settings_action_customize_next_episode_popup": (None, "0"),
            "next_episode_popup_look": ("Default", "1"),
            "next_episode_popup_text_color": ("Look", "1"),
            "next_episode_popup_heading_color": ("Look", "2"),
            "next_episode_popup_all_caps": ("Look", "1"),
            "next_episode_popup_focus_style": ("Look", "1"),
            "next_episode_popup_bar_style": ("Look", "2"),
            "next_episode_popup_card_opacity": ("Look", "2"),
            "next_episode_popup_position": ("BottomRight", "1"),
            "next_episode_popup_size": ("Normal", "1"),
            "next_episode_popup_thumbnail": ("true", "1"),
            "next_episode_popup_countdown": ("true", "1"),
            "next_episode_popup_progress": ("true", "1"),
            "next_episode_popup_focus": ("Play", "2"),
        }
        found = self.settings()
        self.assertEqual(set(found), set(expected))
        for sid, (default, level) in expected.items():
            self.assertEqual(found[sid].findtext("default"), default, sid)
            self.assertEqual(found[sid].findtext("level"), level, sid)

    def test_lead_seconds_range(self):
        constraints = self.settings()["next_episode_lead_seconds"].find("constraints")
        self.assertEqual(
            (
                constraints.findtext("minimum"),
                constraints.findtext("maximum"),
                constraints.findtext("step"),
            ),
            ("10", "300", "5"),
        )

    def test_the_guard_settings_follow_autoplay_and_each_other(self):
        found = self.settings()

        def deps(sid):
            return {
                (d.get("setting"), d.text)
                for d in found[sid].iter("dependency")
                if d.get("type") == "visible"
            }

        def any_of(sid):
            return {
                (c.get("setting"), c.text)
                for d in found[sid].iter("dependency")
                if d.get("type") == "visible"
                for c in d.iter("condition")
            }

        # The question is independent of automatic play: Kodi's own play next video and playlists
        # reach it too, so both rows show whenever the feature is on.
        enabled = ("next_episode_enabled", "true")
        self.assertEqual(deps("next_episode_still_watching"), {enabled})
        self.assertEqual(
            deps("next_episode_still_watching_after"),
            {enabled, ("next_episode_still_watching", "true")},
        )
        self.assertEqual(any_of("next_episode_still_watching"), set())
        self.assertEqual(any_of("next_episode_still_watching_after"), set())
        self.assertNotIn(("next_episode_autoplay", "true"), deps("next_episode_start_at_credits"))
        constraints = found["next_episode_still_watching_after"].find("constraints")
        self.assertEqual(
            (constraints.findtext("minimum"), constraints.findtext("maximum")), ("1", "10")
        )
        self.assertEqual(
            found["next_episode_still_watching"].findtext("level"),
            found["next_episode_still_watching_after"].findtext("level"),
        )

    def test_everything_but_the_toggle_depends_on_it(self):
        for sid, setting in self.settings().items():
            deps = [
                (d.get("setting"), d.text)
                for d in setting.iter("dependency")
                if d.get("type") == "visible"
            ]
            if sid == "next_episode_enabled":
                self.assertEqual(deps, [])
            else:
                self.assertIn(("next_episode_enabled", "true"), deps, sid)

    def test_every_label_and_help_id_has_an_english_string(self):
        with open(
            os.path.join(ROOT, "resources", "language", "resource.language.en_gb", "strings.po"),
            encoding="utf-8",
        ) as handle:
            ids = set(re.findall(r'msgctxt "#(\d+)"', handle.read()))
        cat = self.category()
        wanted = {cat.get("label")}
        for setting in cat.iter("setting"):
            wanted.update((setting.get("label"), setting.get("help")))
        wanted.update({"47020", "47021", "47022", "47070", "47071", "47072", "47073"})
        self.assertEqual(sorted(w for w in wanted if w not in ids), [])


if __name__ == "__main__":
    unittest.main()
