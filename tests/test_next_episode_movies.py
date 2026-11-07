# -*- coding: utf-8 -*-
"""The next movie of a Kodi collection: lookup, hand-off, texts and the service step."""

import os
import re
import types
import unittest
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import next_episode_appearance as app
import next_episode_dialog as dlg_mod
import next_episode_lookup as lookup
import next_episode_play as play
import next_episode_toast as toast
import next_episode_view as view
import service_loop_next_episode as step
from next_episode_state import LOOKUP_FOUND, LOOKUP_NONE, NextEpisodeState
from tests.test_next_episode import FakeRpc
from tests.test_next_episode_popup import _dialog

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def mv(movie_id, title, year, playcount=0, file=None, sorttitle=None, **extra):
    row = {
        "movieid": movie_id,
        "title": title,
        "year": year,
        "playcount": playcount,
        "file": file if file is not None else "/movies/%s.mkv" % movie_id,
    }
    if sorttitle is not None:
        row["sorttitle"] = sorttitle
    row.update(extra)
    return row


TRILOGY = [mv(1, "Part One", 2001), mv(2, "Part Two", 2003), mv(3, "Part Three", 2005)]
CURRENT = {"id": 2, "file": "/movies/2.mkv"}

MOVIE_NEXT = {
    "source": "movie",
    "movieid": 3,
    "title": "Part Three",
    "year": 2005,
    "season": None,
    "episode": None,
    "thumb": "",
}


class PickNextMovieTests(unittest.TestCase):
    def pick(self, rows, current=None, **kw):
        row = lookup.pick_next_movie(rows, CURRENT if current is None else current, **kw)
        return row["movieid"] if row else None

    def test_the_next_movie_by_year(self):
        self.assertEqual(self.pick(TRILOGY), 3)

    def test_input_order_does_not_matter(self):
        self.assertEqual(self.pick(list(reversed(TRILOGY))), 3)

    def test_the_last_movie_has_no_successor(self):
        self.assertIsNone(self.pick(TRILOGY, {"id": 3, "file": "/movies/3.mkv"}))

    def test_the_first_movie_is_followed_by_the_second(self):
        self.assertEqual(self.pick(TRILOGY, {"id": 1}), 2)

    def test_the_same_year_is_ordered_by_sort_title_then_title(self):
        rows = [
            mv(1, "B", 2000, sorttitle="a-first"),
            mv(2, "A", 2000, sorttitle="b-second"),
            mv(3, "C", 2000),
        ]
        self.assertEqual(self.pick(rows, {"id": 1}), 2)
        self.assertEqual(self.pick(rows, {"id": 2}), 3)

    def test_movies_without_a_year_come_last(self):
        rows = [mv(1, "Old", 1999), mv(2, "Unknown", 0), mv(3, "New", 2020), mv(4, "Nothing", None)]
        self.assertEqual(self.pick(rows, {"id": 1}), 3)
        self.assertEqual(self.pick(rows, {"id": 3}), 4)  # no year: by title, after every dated movie
        self.assertEqual(self.pick(rows, {"id": 4}), 2)
        self.assertIsNone(self.pick(rows, {"id": 2}))

    def test_a_movie_that_is_not_in_the_collection_gets_nothing(self):
        self.assertIsNone(self.pick(TRILOGY, {"id": 99, "file": "/other.mkv"}))
        self.assertIsNone(self.pick(TRILOGY, {}))

    def test_the_current_movie_is_found_by_its_file_when_the_id_is_unknown(self):
        self.assertEqual(self.pick(TRILOGY, {"id": None, "file": "/movies/1.mkv"}), 2)

    def test_watched_movies_are_skipped_on_request(self):
        rows = [mv(1, "One", 2001), mv(2, "Two", 2002, playcount=2), mv(3, "Three", 2003)]
        self.assertEqual(self.pick(rows, {"id": 1}), 2)
        self.assertEqual(self.pick(rows, {"id": 1}, skip_watched=True), 3)
        rows = [mv(1, "One", 2001), mv(2, "Two", 2002, playcount=1)]
        self.assertIsNone(self.pick(rows, {"id": 1}, skip_watched=True))

    def test_a_row_that_shares_the_current_file_is_skipped(self):
        rows = [mv(1, "One", 2001, file="/x.mkv"), mv(2, "Cut", 2002, file="/x.mkv"), mv(3, "Two", 2003)]
        self.assertEqual(self.pick(rows, {"id": 1, "file": "/x.mkv"}), 3)

    def test_unusable_rows_are_ignored(self):
        rows = [None, "x", {"title": "no id"}, mv(0, "zero", 2000), mv(1, "One", 2001), mv(2, "Two", 2002)]
        self.assertEqual(self.pick(rows, {"id": 1}), 2)
        self.assertIsNone(self.pick(None))
        self.assertIsNone(self.pick([]))


class DescribeCurrentMovieTests(unittest.TestCase):
    def test_a_library_movie_is_read_for_its_collection_and_play_count(self):
        rpc = FakeRpc({
            "VideoLibrary.GetMovieDetails": {
                "result": {"moviedetails": {"setid": 5, "year": 2003, "file": "/m/2.mkv", "playcount": 1}}
            }
        })
        with patch.object(lookup, "jsonrpc", rpc):
            current = lookup.describe_current_movie({"type": "movie", "id": 2})
        self.assertEqual(
            current,
            {"kind": "movie", "id": 2, "setid": 5, "year": 2003, "file": "/m/2.mkv", "playcount": 1},
        )
        method, params = rpc.calls[0]
        self.assertEqual(method, "VideoLibrary.GetMovieDetails")
        self.assertEqual(params["movieid"], 2)
        self.assertIn("setid", params["properties"])
        self.assertIn("playcount", params["properties"])

    def test_what_the_player_already_said_is_kept(self):
        rpc = FakeRpc({
            "VideoLibrary.GetMovieDetails": {"result": {"moviedetails": {"setid": 9, "year": 1999, "file": "/o"}}}
        })
        with patch.object(lookup, "jsonrpc", rpc):
            current = lookup.describe_current_movie(
                {"type": "movie", "id": 2, "setid": 5, "year": 2003, "file": "/m/2.mkv"}
            )
        self.assertEqual((current["setid"], current["year"], current["file"]), (5, 2003, "/m/2.mkv"))

    def test_a_file_that_is_not_in_the_library_costs_no_call(self):
        rpc = FakeRpc({})
        with patch.object(lookup, "jsonrpc", rpc):
            for item in ({"type": "movie", "file": "/x.mkv"}, {"type": "movie", "id": -1}, {"type": "episode", "id": 4}, None):
                current = lookup.describe_current_movie(item)
                self.assertIsNone(current["id"])
        self.assertEqual(rpc.calls, [])

    def test_an_answer_without_details_leaves_the_rest_unknown(self):
        with patch.object(lookup, "jsonrpc", FakeRpc({})):
            current = lookup.describe_current_movie({"type": "movie", "id": 2})
        self.assertEqual((current["id"], current["setid"], current["playcount"]), (2, None, None))


def set_rpc(rows, details=None):
    return FakeRpc({
        "VideoLibrary.GetMovieDetails": {
            "result": {"moviedetails": details or {"setid": 5, "year": 2003, "file": "/movies/2.mkv", "playcount": 1}}
        },
        "VideoLibrary.GetMovieSetDetails": {"result": {"setdetails": {"movies": rows}}},
    })


class FindMovieSuccessorTests(unittest.TestCase):
    def find(self, rpc, item=None, **kw):
        with patch.object(lookup, "jsonrpc", rpc):
            return lookup.find_movie_successor(item or {"type": "movie", "id": 2}, **kw)

    def test_the_next_movie_of_the_collection_is_described(self):
        rows = TRILOGY[:2] + [mv(3, "Part Three", 2005, art={"poster": "p.jpg", "landscape": "l.jpg", "fanart": "f.jpg", "thumb": "t.jpg"})]
        found = self.find(set_rpc(rows))
        self.assertEqual(found["source"], "movie")
        self.assertEqual(found["movieid"], 3)
        self.assertEqual((found["title"], found["year"]), ("Part Three", 2005))
        self.assertEqual((found["season"], found["episode"], found["showtitle"]), (None, None, ""))
        self.assertEqual(found["thumb"], "l.jpg")
        self.assertEqual(found["file"], "/movies/3.mkv")

    def test_the_picture_is_wide_never_the_poster(self):
        rows = TRILOGY[:2] + [mv(3, "Part Three", 2005, art={"poster": "p.jpg", "thumb": "t.jpg", "fanart": "f.jpg"})]
        self.assertEqual(self.find(set_rpc(rows))["thumb"], "f.jpg")
        rows = TRILOGY[:2] + [mv(3, "Part Three", 2005, art={"poster": "p.jpg", "thumb": "t.jpg"})]
        self.assertEqual(self.find(set_rpc(rows))["thumb"], "")

    def test_the_collection_is_asked_for_by_id(self):
        rpc = set_rpc(TRILOGY)
        self.find(rpc)
        params = rpc.params_for("VideoLibrary.GetMovieSetDetails")[0]
        self.assertEqual(params["setid"], 5)
        for needed in ("title", "sorttitle", "year", "file", "playcount", "art"):
            self.assertIn(needed, params["movies"]["properties"])

    def test_a_movie_outside_any_collection_has_no_successor_and_asks_nothing_more(self):
        rpc = set_rpc(TRILOGY, details={"setid": 0, "file": "/movies/2.mkv"})
        self.assertIsNone(self.find(rpc))
        self.assertEqual(rpc.params_for("VideoLibrary.GetMovieSetDetails"), [])

    def test_a_file_that_is_not_in_the_library_has_no_successor(self):
        rpc = set_rpc(TRILOGY)
        self.assertIsNone(self.find(rpc, {"type": "movie", "file": "/x.mkv"}))
        self.assertEqual(rpc.params_for("VideoLibrary.GetMovieSetDetails"), [])

    def test_the_last_movie_has_no_successor(self):
        self.assertIsNone(self.find(set_rpc(TRILOGY, details={"setid": 5, "file": "/movies/3.mkv"}), {"type": "movie", "id": 3}))

    def test_no_answer_means_no_successor(self):
        rpc = FakeRpc({"VideoLibrary.GetMovieDetails": {"result": {"moviedetails": {"setid": 5}}}})
        self.assertIsNone(self.find(rpc))

    def test_watched_movies_are_skipped_when_asked(self):
        rows = [mv(1, "One", 2001), mv(2, "Two", 2003), mv(3, "Three", 2005, playcount=1), mv(4, "Four", 2007)]
        self.assertEqual(self.find(set_rpc(rows), skip_watched=True)["movieid"], 4)
        self.assertEqual(self.find(set_rpc(rows))["movieid"], 3)

    def test_a_given_current_is_not_read_again(self):
        rpc = set_rpc(TRILOGY)
        current = {"kind": "movie", "id": 2, "setid": 5, "file": "/movies/2.mkv"}
        with patch.object(lookup, "jsonrpc", rpc):
            found = lookup.find_movie_successor({"type": "movie", "id": 2}, current=current)
        self.assertEqual(found["movieid"], 3)
        self.assertEqual(rpc.params_for("VideoLibrary.GetMovieDetails"), [])


class FindNextTests(unittest.TestCase):
    def test_a_movie_looks_in_its_collection_after_the_playlist(self):
        with patch.object(lookup, "find_playlist_successor", return_value=None), patch.object(
            lookup, "find_movie_successor", return_value=MOVIE_NEXT
        ) as movie, patch.object(lookup, "find_library_successor") as library:
            self.assertEqual(lookup.find_next_episode({"type": "movie", "id": 2}, skip_watched=True), MOVIE_NEXT)
        self.assertEqual(movie.call_args.kwargs, {"skip_watched": True, "current": None})
        library.assert_not_called()

    def test_the_playlist_wins_over_the_collection(self):
        queued = {"source": "playlist", "title": "Queued"}
        with patch.object(lookup, "find_playlist_successor", return_value=queued), patch.object(
            lookup, "find_movie_successor"
        ) as movie:
            self.assertEqual(lookup.find_next_episode({"type": "movie", "id": 2}), queued)
        movie.assert_not_called()

    def test_an_episode_still_looks_in_the_show(self):
        with patch.object(lookup, "find_playlist_successor", return_value=None), patch.object(
            lookup, "find_library_successor", return_value={"source": "library"}
        ) as library, patch.object(lookup, "find_movie_successor") as movie:
            lookup.find_next_episode({"type": "episode", "id": 2})
        library.assert_called_once()
        movie.assert_not_called()

    def test_the_kind_of_a_given_current_decides_too(self):
        with patch.object(lookup, "find_playlist_successor", return_value=None), patch.object(
            lookup, "find_movie_successor", return_value=MOVIE_NEXT
        ):
            self.assertEqual(lookup.find_next_episode({}, current={"kind": "movie"}), MOVIE_NEXT)


class LabelTests(unittest.TestCase):
    def test_a_movie_shows_its_title_and_year(self):
        self.assertEqual(lookup.episode_label(MOVIE_NEXT), "Part Three (2005)")

    def test_a_movie_without_a_year_shows_the_title(self):
        self.assertEqual(lookup.episode_label(dict(MOVIE_NEXT, year=None)), "Part Three")
        self.assertEqual(lookup.episode_label(dict(MOVIE_NEXT, year=0)), "Part Three")

    def test_a_movie_without_a_title_has_no_label(self):
        self.assertEqual(lookup.episode_label(dict(MOVIE_NEXT, title=" ")), "")

    def test_an_episode_is_labelled_as_before(self):
        self.assertEqual(lookup.episode_label({"season": 1, "episode": 5, "title": "Pilot"}), "S01E05 · Pilot")
        self.assertEqual(lookup.episode_label({"title": "Pilot", "year": 2005}), "Pilot")

    def test_which_things_are_movies(self):
        self.assertTrue(lookup.is_movie_item(MOVIE_NEXT))
        self.assertFalse(lookup.is_movie_item({"source": "library"}))
        self.assertFalse(lookup.is_movie_item(None))
        self.assertTrue(lookup.is_movie_playback({"type": "Movie"}))
        self.assertFalse(lookup.is_movie_playback({"type": "episode"}))
        self.assertFalse(lookup.is_movie_playback(None))


class PlayTests(unittest.TestCase):
    def test_the_next_movie_is_opened_by_its_id(self):
        rpc = FakeRpc({"Player.Open": {"result": "OK"}})
        with patch.object(play, "jsonrpc", rpc):
            self.assertTrue(play.play_next(MOVIE_NEXT, resume=False))
        self.assertEqual(
            rpc.calls, [("Player.Open", {"item": {"movieid": 3}, "options": {"resume": False}})]
        )

    def test_resume_follows_the_setting(self):
        rpc = FakeRpc({"Player.Open": {"result": "OK"}})
        with patch.object(play, "jsonrpc", rpc):
            play.play_next(MOVIE_NEXT, resume=True)
        self.assertTrue(rpc.calls[0][1]["options"]["resume"])

    def test_a_refusal_is_reported(self):
        with patch.object(play, "jsonrpc", FakeRpc({"Player.Open": {"error": {"code": -1}}})), patch.object(
            play, "log_error"
        ):
            self.assertFalse(play.play_next(MOVIE_NEXT))


class MarkWatchedTests(unittest.TestCase):
    def test_a_movie_that_kodi_did_not_count_is_marked_watched(self):
        rpc = FakeRpc({
            "VideoLibrary.GetMovieDetails": {"result": {"moviedetails": {"playcount": 1}}},
            "VideoLibrary.SetMovieDetails": {"result": "OK"},
        })
        with patch.object(play, "jsonrpc", rpc), patch.object(play, "log"):
            self.assertTrue(play.mark_watched_if_needed(2, 1, "movie"))
        method, params = rpc.calls[-1]
        self.assertEqual(method, "VideoLibrary.SetMovieDetails")
        self.assertEqual((params["movieid"], params["playcount"]), (2, 2))
        self.assertNotIn("episodeid", params)
        self.assertEqual(rpc.params_for("VideoLibrary.GetMovieDetails")[0]["movieid"], 2)

    def test_a_movie_kodi_already_counted_is_left_alone(self):
        rpc = FakeRpc({"VideoLibrary.GetMovieDetails": {"result": {"moviedetails": {"playcount": 2}}}})
        with patch.object(play, "jsonrpc", rpc):
            self.assertFalse(play.mark_watched_if_needed(2, 1, "movie"))
        self.assertEqual(rpc.params_for("VideoLibrary.SetMovieDetails"), [])

    def test_an_episode_still_uses_the_episode_calls(self):
        rpc = FakeRpc({
            "VideoLibrary.GetEpisodeDetails": {"result": {"episodedetails": {"playcount": 1}}},
            "VideoLibrary.SetEpisodeDetails": {"result": "OK"},
        })
        with patch.object(play, "jsonrpc", rpc), patch.object(play, "log"):
            self.assertTrue(play.mark_watched_if_needed(2, 1))
        self.assertEqual(rpc.calls[-1][0], "VideoLibrary.SetEpisodeDetails")
        self.assertEqual(rpc.calls[-1][1]["episodeid"], 2)

    def test_the_kind_travels_through_the_scheduler(self):
        monitor = MagicMock()
        monitor.waitForAbort.return_value = False
        done = []
        with patch.object(play, "mark_watched_if_needed", lambda *a: done.append(a)), patch.object(
            play.threading, "Thread", lambda target, daemon: types.SimpleNamespace(start=target)
        ):
            play.schedule_mark_watched(monitor, 2, 1, "movie")
        self.assertEqual(done, [(2, 1, "movie")])


class RunLookupTests(unittest.TestCase):
    def test_a_movie_is_described_and_looked_up_as_a_movie(self):
        state = NextEpisodeState(video="v")
        current = {"kind": "movie", "id": 2, "playcount": 3}
        with patch.object(step, "describe_current_movie", return_value=current) as describe, patch.object(
            step, "describe_current_episode"
        ) as episode, patch.object(step, "find_next_episode", return_value=MOVIE_NEXT) as find, patch.object(
            step, "_resolve_show"
        ) as resolve, patch.object(step, "log"):
            step.run_lookup(state, {"type": "movie", "id": 2}, True, True)
        self.assertEqual(state.lookup, LOOKUP_FOUND)
        self.assertEqual(state.next_item, MOVIE_NEXT)
        self.assertEqual((state.current_kind, state.current_episode_id, state.current_playcount), ("movie", 2, 3))
        describe.assert_called_once()
        episode.assert_not_called()
        resolve.assert_not_called()
        self.assertEqual(find.call_args.kwargs, {"skip_watched": True, "current": current})

    def test_an_episode_is_still_an_episode(self):
        state = NextEpisodeState(video="v")
        current = {"id": 7, "playcount": 1}
        with patch.object(step, "describe_current_episode", return_value=current), patch.object(
            step, "describe_current_movie"
        ) as movie, patch.object(step, "find_next_episode", return_value=None), patch.object(
            step, "_resolve_show"
        ) as resolve, patch.object(step, "log"):
            step.run_lookup(state, {"type": "episode", "id": 7}, False, True)
        self.assertEqual(state.current_kind, "episode")
        self.assertEqual(state.lookup, LOOKUP_NONE)
        movie.assert_not_called()
        resolve.assert_called_once()

    def test_a_new_state_starts_as_an_episode(self):
        self.assertEqual(NextEpisodeState(video="v").current_kind, "episode")


SETTINGS = {
    "next_episode_enabled": True,
    "next_episode_movies": True,
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


class _Player:
    def getTotalTime(self):
        return 1500.0

    def isPlayingVideo(self):
        return True


class HandlerTests(unittest.TestCase):
    """The service step for a movie of a collection; the lookup and the player are faked."""

    def setUp(self):
        self.monitor = types.SimpleNamespace(next_episode_state=None)
        self.ctx = types.SimpleNamespace(monitor=self.monitor, player=_Player(), icon_path="")
        self.settings = dict(SETTINGS)
        self.answers = []
        self.prompts = []
        self.plays = []
        self.marks = []
        self.lookups = []
        self.now = 1000.0
        stack = [
            patch.object(step, "get_addon", lambda: object()),
            patch.object(step, "addon_get_bool", lambda _a, key, default=False: self.settings.get(key, default)),
            patch.object(
                step,
                "addon_get_int",
                lambda _a, key, default=0, minimum=None, maximum=None: self.settings.get(key, default),
            ),
            patch.object(step, "countdown_settings", lambda _a: (0, "Close")),
            patch.object(step, "per_show_autoplay_enabled", lambda _a: True),
            patch.object(step, "lookup_mode", lambda key: None),
            patch.object(step, "_upnext_enabled", lambda: False),
            patch.object(step, "_still_watching_due", lambda *_a: False),
            patch.object(step, "show_next_episode_prompt", self._prompt),
            patch.object(step, "play_next", self._play),
            patch.object(step, "schedule_mark_watched", lambda *a: self.marks.append(a[1:])),
            patch.object(step, "_start_lookup", lambda *a, **k: self.lookups.append((a, k))),
            patch.object(step.time, "monotonic", lambda: self.now),
            patch.object(step, "log"),
            patch.object(step, "log_error"),
        ]
        for p in stack:
            p.start()
            self.addCleanup(p.stop)

    def _prompt(self, addon, player, item, start, total, still_watching=False, timed=False, end_action="Close"):
        self.prompts.append(item)
        return self.answers.pop(0) if self.answers else None

    def _play(self, item, resume=True):
        self.plays.append(item)
        return True

    def found_state(self):
        state = NextEpisodeState(
            video="film.mkv",
            lookup=LOOKUP_FOUND,
            next_item=MOVIE_NEXT,
            current_episode_id=2,
            current_playcount=1,
            current_kind="movie",
        )
        self.monitor.next_episode_state = state
        return state

    def tick(self, current_time, video="film.mkv"):
        return step.handle_next_episode(
            self.ctx,
            video=video,
            playback_type="movie",
            current_time=current_time,
            player_item={"type": "movie", "id": 2},
        )

    def test_the_first_tick_starts_the_lookup_with_the_movie_item(self):
        self.tick(10.0)
        self.assertEqual(len(self.lookups), 1)
        self.assertEqual(self.lookups[0][0][1], {"type": "movie", "id": 2})

    def test_the_prompt_is_shown_for_the_next_movie_inside_the_window(self):
        self.found_state()
        self.answers = [False]
        result = self.tick(1460.0)
        self.assertEqual(self.prompts, [MOVIE_NEXT])
        self.assertTrue(result.hide_skip_dialogs)

    def test_nothing_is_shown_before_the_window(self):
        self.found_state()
        self.tick(1000.0)
        self.assertEqual(self.prompts, [])

    def test_play_now_starts_the_movie_and_marks_the_old_one_as_a_movie(self):
        self.found_state()
        self.answers = [True]
        self.assertTrue(self.tick(1460.0).switched)
        self.assertEqual(self.plays, [MOVIE_NEXT])
        self.assertEqual(self.marks, [(2, 1, "movie")])

    def test_automatic_play_applies_to_movies_too(self):
        self.settings["next_episode_autoplay"] = True
        self.found_state()
        self.assertTrue(self.tick(1460.0).switched)
        self.assertEqual((self.prompts, self.plays), ([], [MOVIE_NEXT]))

    def test_the_per_show_question_is_never_queued_for_a_movie(self):
        self.found_state()
        self.answers = [True]
        self.tick(1460.0)
        self.assertFalse(getattr(self.monitor, "next_episode_remember", None))

    def test_turning_movies_off_stops_the_prompt(self):
        self.found_state()
        self.settings["next_episode_movies"] = False
        self.assertEqual(self.tick(1460.0), step.IDLE_TICK)
        self.assertEqual(self.prompts, [])

    def test_turning_the_feature_off_stops_it_too(self):
        self.found_state()
        self.settings["next_episode_enabled"] = False
        self.assertEqual(self.tick(1460.0), step.IDLE_TICK)

    def test_movies_default_to_on_when_the_setting_is_missing(self):
        del self.settings["next_episode_movies"]
        self.found_state()
        self.answers = [False]
        self.tick(1460.0)
        self.assertEqual(self.prompts, [MOVIE_NEXT])


class TextTests(unittest.TestCase):
    def test_the_popup_asks_about_the_next_movie(self):
        texts = view.popup_texts(None, False, MOVIE_NEXT)
        self.assertEqual(texts["heading"], "Play next movie?")
        self.assertEqual(texts["label"], "Part Three (2005)")
        self.assertEqual((texts["play"], texts["close"]), ("Play now", "Close"))

    def test_all_caps_applies_to_the_movie_texts(self):
        texts = view.popup_texts(None, True, MOVIE_NEXT)
        self.assertEqual((texts["heading"], texts["label"]), ("PLAY NEXT MOVIE?", "PART THREE (2005)"))

    def test_the_still_watching_question_stays_the_same_for_a_movie(self):
        texts = view.popup_texts(None, False, MOVIE_NEXT, still_watching=True)
        self.assertEqual(texts["heading"], "Still watching?")

    def test_an_episode_keeps_its_wording(self):
        texts = view.popup_texts(None, False, {"season": 1, "episode": 2, "title": "X"})
        self.assertEqual(texts["heading"], "Play next episode?")

    def test_the_countdown_lines_for_a_movie(self):
        for mode, expected in (
            (view.COUNTDOWN_ENDS, "Movie ends in 00:42"),
            (view.COUNTDOWN_PLAYS, "Next movie starts in 00:42"),
            (view.COUNTDOWN_CLOSES, "Closing in 00:42"),
        ):
            self.assertEqual(view.countdown_text(None, False, 42, mode, movie=True), expected, mode)

    def test_the_countdown_lines_for_an_episode_are_unchanged(self):
        self.assertEqual(view.countdown_text(None, False, 42), "Episode ends in 00:42")
        self.assertEqual(view.countdown_text(None, False, 42, view.COUNTDOWN_PLAYS), "Next episode starts in 00:42")

    def test_the_toast_asks_about_the_next_movie(self):
        heading, body = toast.build_toast_texts(None, MOVIE_NEXT)
        self.assertEqual(heading, "Play next movie?")
        self.assertEqual(body, "Part Three (2005) · Press OK to play")

    def test_the_toast_for_an_episode_is_unchanged(self):
        heading, _body = toast.build_toast_texts(None, {"season": 1, "episode": 2, "title": "X"})
        self.assertEqual(heading, "Play next episode?")

    def test_the_popup_counts_down_with_the_movie_line(self):
        dialog = _dialog(next_episode=MOVIE_NEXT)
        dialog._layout = app.popup_layout(thumbnail=False, countdown=True, progress=False)
        dialog.addon = None
        props = {}
        dialog.setProperty = lambda k, v: props.__setitem__(k, v)
        dialog._ctrl = lambda cid: None
        dialog._sc = lambda v: v
        dialog._update_countdown(1477.5)
        self.assertEqual(props["next_ep_countdown"], "Movie ends in 00:22")

    def test_the_popup_for_an_episode_keeps_the_episode_line(self):
        dialog = _dialog(next_episode={"season": 1, "episode": 2, "title": "X"})
        dialog._layout = app.popup_layout(thumbnail=False, countdown=True, progress=False)
        dialog.addon = None
        props = {}
        dialog.setProperty = lambda k, v: props.__setitem__(k, v)
        dialog._ctrl = lambda cid: None
        dialog._sc = lambda v: v
        dialog._update_countdown(1477.5)
        self.assertEqual(props["next_ep_countdown"], "Episode ends in 00:22")


def _po_entries(pack):
    path = os.path.join(ROOT, "resources", "language", pack, "strings.po")
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    return {
        int(sid): msgstr
        for sid, msgstr in re.findall(r'msgctxt "#(\d+)"\nmsgid ".*"\nmsgstr "(.*)"', text)
    }


class StringsAndSettingsTests(unittest.TestCase):
    IDS = range(47146, 47151)

    def packs(self):
        langs = os.path.join(ROOT, "resources", "language")
        return sorted(p for p in os.listdir(langs) if os.path.exists(os.path.join(langs, p, "strings.po")))

    def test_every_pack_has_the_strings_with_the_same_placeholders(self):
        english = _po_entries("resource.language.en_gb")
        for pack in self.packs():
            entries = _po_entries(pack)
            for sid in self.IDS:
                self.assertTrue(entries.get(sid, "").strip(), (pack, sid))
                self.assertEqual(entries[sid].count("%s"), english[sid].count("%s"), (pack, sid))
                self.assertEqual(entries[sid].count("%"), entries[sid].count("%s"), (pack, sid))
                if not pack.endswith("en_gb"):
                    self.assertNotEqual(entries[sid], english[sid], (pack, sid))

    def test_the_two_countdown_lines_end_in_a_time(self):
        for pack in self.packs():
            entries = _po_entries(pack)
            for sid in (47147, 47148):
                self.assertEqual(entries[sid].count("%s"), 1, (pack, sid))

    def test_the_skip_watched_help_mentions_movies_in_every_pack(self):
        english = _po_entries("resource.language.en_gb")[47012]
        self.assertIn("movie", english)
        for pack in self.packs():
            self.assertGreater(len(_po_entries(pack)[47012]), 40, pack)

    def test_the_texts_use_the_string_ids_that_say_the_same_thing(self):
        english = _po_entries("resource.language.en_gb")
        for mode, (string_id, fallback) in view._COUNTDOWN_STRINGS_MOVIE.items():
            self.assertEqual(english[string_id], fallback, mode)
        asked = []

        def spy(_addon, string_id, fallback, *args):
            asked.append((string_id, fallback))
            return fallback % args if args else fallback

        for module in (view, toast):
            with patch.object(module, "get_localized", spy):
                asked.clear()
                module_texts = (
                    view.popup_texts(None, False, MOVIE_NEXT)
                    if module is view
                    else toast.build_toast_texts(None, MOVIE_NEXT)
                )
                self.assertIn((47146, "Play next movie?"), asked, module.__name__)
                self.assertEqual(english[47146], "Play next movie?")
                self.assertTrue(module_texts)

    def test_the_setting_is_defined_with_its_strings(self):
        import xml.etree.ElementTree as ET

        tree = ET.parse(os.path.join(ROOT, "resources", "settings.xml"))
        found = {s.get("id"): s for s in tree.getroot().iter("setting")}
        setting = found["next_episode_movies"]
        self.assertEqual((setting.findtext("default"), setting.findtext("level")), ("true", "1"))
        self.assertEqual((setting.get("label"), setting.get("help")), ("47149", "47150"))
        deps = [(d.get("setting"), d.text) for d in setting.iter("dependency")]
        self.assertIn(("next_episode_enabled", "true"), deps)
        self.assertEqual(step.KEY_MOVIES, "next_episode_movies")


if __name__ == "__main__":
    unittest.main()
