# -*- coding: utf-8 -*-
"""Identifying the playing title from Kodi's library, which online lookups and per-show choices use."""

import unittest
from unittest.mock import patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import remote_http  # noqa: E402
import remote_library as lib  # noqa: E402


class _Library:
    """Answers the few JSON-RPC calls the module makes, from small tables."""

    def __init__(self, shows=None, episodes=None, movies=None):
        self.shows = shows or {}
        self.episodes = episodes or {}
        self.movies = movies or {}
        self.calls = []

    def __call__(self, method, params=None, log_errors=True):
        self.calls.append(method)
        params = params or {}
        if method == "VideoLibrary.GetTVShowDetails":
            row = self.shows.get(params.get("tvshowid"))
            return {"result": {"tvshowdetails": row}} if row else {}
        if method == "VideoLibrary.GetEpisodeDetails":
            row = self.episodes.get(params.get("episodeid"))
            return {"result": {"episodedetails": row}} if row else {}
        if method == "VideoLibrary.GetMovieDetails":
            row = self.movies.get(params.get("movieid"))
            return {"result": {"moviedetails": row}} if row else {}
        return {}


class _LibraryTest(unittest.TestCase):
    def use(self, library, key=None, infolabels=None):
        stack = [
            patch.object(lib, "jsonrpc", library),
            patch.object(lib, "_get_tmdb_api_key", lambda: key),
            patch.object(lib, "_rlog"),
            patch.object(lib.xbmc, "getInfoLabel", lambda label: (infolabels or {}).get(label, ""), create=True),
        ]
        for p in stack:
            p.start()
            self.addCleanup(p.stop)


class TitleIdentityTests(_LibraryTest):
    def test_an_episode_is_identified_by_its_show(self):
        self.use(_Library(shows={7: {"uniqueid": {"tmdb": "1396", "imdb": "tt0903747"}}}))
        identity = lib.library_title_identity(
            {"type": "episode", "id": 70, "tvshowid": 7, "showtitle": "Breaking Bad", "title": "Pilot"}
        )
        self.assertEqual(
            identity, {"type": "episode", "tmdb_id": 1396, "imdb_id": "tt0903747", "title": "Breaking Bad"}
        )

    def test_the_show_is_found_through_the_episode_row(self):
        self.use(_Library(shows={7: {"uniqueid": {"tmdb": 1396}}}, episodes={70: {"tvshowid": 7}}))
        identity = lib.library_title_identity({"type": "episode", "id": 70, "showtitle": "BB"})
        self.assertEqual(identity["tmdb_id"], 1396)

    def test_a_thin_movie_item_gets_its_ids_from_the_movie_row(self):
        self.use(_Library(movies={3: {"uniqueid": {"tmdb": "603"}, "imdbnumber": "tt0133093"}}))
        identity = lib.library_title_identity({"type": "movie", "id": 3, "title": "The Matrix"})
        self.assertEqual(identity, {"type": "movie", "tmdb_id": 603, "imdb_id": "tt0133093", "title": "The Matrix"})

    def test_unknown_items_have_no_identity(self):
        self.use(_Library())
        self.assertIsNone(lib.library_title_identity(None))
        self.assertIsNone(lib.library_title_identity({"type": "musicvideo"}))


class MovieContextTests(_LibraryTest):
    def test_ids_from_the_item(self):
        self.use(_Library())
        ctx = lib.build_movie_context({"type": "movie", "uniqueid": {"tmdb": "603", "imdb": "tt0133093", "tvdb": "9"}})
        self.assertEqual(ctx, {"type": "movie", "tmdb_id": 603, "imdb_id": "tt0133093", "tvdb_id": 9})

    def test_missing_ids_are_looked_up_when_there_is_a_key(self):
        self.use(_Library(), key="k")
        with patch.object(lib, "get_addon", lambda: object()), patch.object(
            lib, "addon_get_bool", lambda _a, _k, default=False: default
        ), patch.object(lib, "_tmdb_enrich_missing_movie_ids", lambda item, t, i, k, year=None: (603, "tt0133093")) as _:
            ctx = lib.build_movie_context({"type": "movie", "title": "The Matrix"})
        self.assertEqual((ctx["tmdb_id"], ctx["imdb_id"]), (603, "tt0133093"))

    def test_no_ids_anywhere_means_no_lookup(self):
        self.use(_Library())
        self.assertIsNone(lib.build_movie_context({"type": "movie", "title": "Home video"}))
        self.assertIsNone(lib.build_movie_context({"type": "episode"}))


class TvContextTests(_LibraryTest):
    def test_season_and_episode_come_from_the_file_name_outside_the_library(self):
        self.use(_Library(), infolabels={"VideoPlayer.TvShow.UniqueID(tmdb)": "1396"})
        with patch.object(lib, "_tmdb_from_infolabels", lambda: 1396):
            ctx = lib.build_tv_episode_context({"type": "episode", "file": "/tv/Show/Show.S02E105.mkv"})
        self.assertEqual((ctx["season"], ctx["episode"], ctx["tmdb_id"]), (2, 105, 1396))

    def test_a_library_episode_without_numbers_is_skipped(self):
        self.use(_Library())
        self.assertIsNone(lib.build_tv_episode_context({"type": "episode", "id": 70, "file": "/tv/x.mkv"}))

    def test_the_episode_tmdb_id_is_replaced_by_the_shows(self):
        self.use(
            _Library(
                shows={7: {"uniqueid": {"tmdb": "1396", "tvdb": "81189"}, "imdbnumber": "tt0903747"}},
            )
        )
        ctx = lib.build_tv_episode_context(
            {
                "type": "episode",
                "id": 70,
                "tvshowid": 7,
                "season": 1,
                "episode": 2,
                "uniqueid": {"tmdb": "62085", "imdb": "tt0959621", "tvdb": "349232"},
            }
        )
        self.assertEqual(ctx["tmdb_id"], 1396)
        self.assertEqual(ctx["imdb_id"], "tt0959621")
        self.assertEqual(ctx["tvdb_episode_id"], 349232)

    def test_season_episode_pattern(self):
        cases = {
            "Show.S01E05.mkv": ("1", "5"),
            "show s1e5 x.mkv": ("1", "5"),
            "Show.S01E105.mkv": ("01", "105"),
            "Show.S2024E01.mkv": ("2024", "01"),
        }
        for name, (season, episode) in cases.items():
            match = remote_http._SXXEXX.search(name)
            self.assertIsNotNone(match, name)
            self.assertEqual((int(match.group(1)), int(match.group(2))), (int(season), int(episode)), name)
        self.assertIsNone(remote_http._SXXEXX.search("Show.S01E12345.mkv"))


class YearTests(_LibraryTest):
    def test_the_shows_first_year_comes_from_the_library(self):
        self.use(_Library(shows={7: {"year": 2005}, 8: {"premiered": "2001-07-09"}}))
        self.assertEqual(lib._show_year({"type": "episode", "tvshowid": 7}), 2005)
        self.assertEqual(lib._show_year({"type": "episode", "tvshowid": 8}), 2001)
        self.assertIsNone(lib._show_year({"type": "episode"}))

    def test_a_movies_year_comes_from_the_item_or_its_row(self):
        self.use(_Library(movies={3: {"year": 1999}}))
        self.assertEqual(lib._movie_year({"type": "movie", "year": 2021}), 2021)
        self.assertEqual(lib._movie_year({"type": "movie", "id": 3}), 1999)
        self.assertIsNone(lib._movie_year({"type": "movie"}))

    def test_the_show_year_reaches_the_tmdb_search(self):
        self.use(_Library(shows={7: {"year": 2005}}), key="k")
        seen = {}

        def enrich(item, season, episode, tmdb_id, imdb_id, show_imdb_id, key, year=None):
            seen["year"] = year
            return 2316, "tt1", "tt0386676"

        with patch.object(lib, "get_addon", lambda: object()), patch.object(
            lib, "addon_get_bool", lambda _a, _k, default=False: True
        ), patch.object(lib, "_tmdb_enrich_missing_ids", enrich), patch.object(
            lib, "_correct_show_imdb_from_series_external_ids", lambda show, *_a: show
        ):
            lib.build_tv_episode_context({"type": "episode", "tvshowid": 7, "season": 1, "episode": 1, "showtitle": "The Office"})
        self.assertEqual(seen["year"], 2005)


class PathTests(unittest.TestCase):
    def test_the_same_file_in_two_spellings(self):
        self.assertTrue(lib.paths_refer_to_same_video("/tv/a/../a/x.mkv", "/tv/a/x.mkv"))
        self.assertFalse(lib.paths_refer_to_same_video("/tv/a/x.mkv", "/tv/a/y.mkv"))
        self.assertFalse(lib.paths_refer_to_same_video("", "/tv/a/x.mkv"))


if __name__ == "__main__":
    unittest.main()
