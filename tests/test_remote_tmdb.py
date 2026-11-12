# -*- coding: utf-8 -*-
"""Finding TMDB and IMDb ids for a library title, which the online segment databases need."""

import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import remote_tmdb as tmdb  # noqa: E402


class _FakeApi:
    """Answers TMDB v3 requests by path; records every request."""

    def __init__(self, routes):
        self.routes = routes
        self.requests = []

    def __call__(self, url, _label):
        parsed = urlparse(url)
        path = parsed.path.replace("/3", "", 1)
        query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        self.requests.append((path, query))
        return self.routes.get(path)


class _Addon:
    def __init__(self, **settings):
        self.settings = settings

    def getSetting(self, key):
        return self.settings.get(key, "")

    def getSettingString(self, key):
        return self.settings.get(key, "")


class ApiKeyTests(unittest.TestCase):
    def test_skippys_own_key_wins(self):
        with patch.object(tmdb, "get_addon", lambda: _Addon(tv_tmdb_api_key=" own-key ")):
            self.assertEqual(tmdb._get_tmdb_api_key(), "own-key")

    def test_the_helper_key_is_used_when_allowed(self):
        helper = _Addon(tmdb_api_key="helper-key")
        with patch.object(tmdb, "get_addon", lambda: _Addon()), patch.object(
            tmdb.xbmcaddon, "Addon", lambda _id: helper
        ):
            self.assertEqual(tmdb._get_tmdb_api_key(), "helper-key")
        with patch.object(tmdb, "get_addon", lambda: _Addon(tv_tmdb_use_helper_api_key="false")), patch.object(
            tmdb.xbmcaddon, "Addon", lambda _id: helper
        ):
            self.assertIsNone(tmdb._get_tmdb_api_key())

    def test_no_helper_installed_means_no_key(self):
        def missing(_id):
            raise RuntimeError("not installed")

        with patch.object(tmdb, "get_addon", lambda: _Addon()), patch.object(tmdb.xbmcaddon, "Addon", missing):
            self.assertIsNone(tmdb._get_tmdb_api_key())
        with patch.object(tmdb, "get_addon", lambda: None):
            self.assertIsNone(tmdb._get_tmdb_api_key())


class TvIdTests(unittest.TestCase):
    def api(self, routes):
        fake = _FakeApi(routes)
        patcher = patch.object(tmdb, "fetch_remote_json", fake)
        patcher.start()
        self.addCleanup(patcher.stop)
        return fake

    def test_the_request_carries_the_key_and_the_query(self):
        api = self.api({"/search/tv": {"results": [{"id": "1396"}]}})
        self.assertEqual(tmdb._tmdb_search_tv_show_id("Breaking Bad", "k"), 1396)
        self.assertEqual(api.requests, [("/search/tv", {"api_key": "k", "query": "Breaking Bad"})])

    def test_no_result_no_title_or_no_key_gives_none(self):
        self.api({"/search/tv": {"results": []}})
        self.assertIsNone(tmdb._tmdb_search_tv_show_id("Nothing", "k"))
        self.assertIsNone(tmdb._tmdb_search_tv_show_id("", "k"))
        self.assertIsNone(tmdb._tmdb_search_tv_show_id("Show", ""))
        self.assertIsNone(tmdb._tmdb_api3_json("/x", None))

    def test_missing_ids_are_filled_from_the_show_and_the_episode(self):
        self.api(
            {
                "/search/tv": {"results": [{"id": 1396}]},
                "/tv/1396/external_ids": {"imdb_id": "tt0903747"},
                "/tv/1396/season/1/episode/2": {"external_ids": {"imdb_id": "959621"}},
            }
        )
        found = tmdb._tmdb_enrich_missing_ids({"showtitle": "Breaking Bad"}, 1, 2, None, None, None, "k")
        self.assertEqual(found, (1396, "tt0959621", "tt0903747"))

    def test_known_ids_are_kept_and_not_looked_up(self):
        api = self.api({})
        found = tmdb._tmdb_enrich_missing_ids({"showtitle": "X"}, 1, 2, 5, "tt1", "tt2", "k")
        self.assertEqual(found, (5, "tt1", "tt2"))
        self.assertEqual(api.requests, [])

    def test_nothing_found_returns_what_came_in(self):
        self.api({"/search/tv": {"results": []}})
        self.assertEqual(tmdb._tmdb_enrich_missing_ids({"title": "X"}, 1, 2, None, None, None, "k"), (None, None, None))


class SearchPickTests(unittest.TestCase):
    """The Office (2001, UK) and The Office (2005, US): the year must decide, not popularity."""

    OFFICE = [
        {"id": 2316, "name": "The Office", "first_air_date": "2005-03-24"},
        {"id": 2996, "name": "The Office", "first_air_date": "2001-07-09"},
        {"id": 9, "name": "The Office Mix", "first_air_date": "2001-01-01"},
    ]

    def api(self, routes):
        fake = _FakeApi(routes)
        patcher = patch.object(tmdb, "fetch_remote_json", fake)
        patcher.start()
        self.addCleanup(patcher.stop)
        return fake

    def test_the_year_picks_between_same_named_shows(self):
        api = self.api({"/search/tv": {"results": self.OFFICE}})
        self.assertEqual(tmdb._tmdb_search_tv_show_id("The Office", "k", 2001), 2996)
        self.assertEqual(api.requests[0][1]["first_air_date_year"], "2001")
        self.assertEqual(tmdb._tmdb_search_tv_show_id("The Office", "k", 2005), 2316)

    def test_a_year_in_the_title_is_used_and_left_out_of_the_query(self):
        api = self.api({"/search/tv": {"results": [{"id": 57243, "name": "Doctor Who", "first_air_date": "2005-03-26"}]}})
        self.assertEqual(tmdb._tmdb_search_tv_show_id("Doctor Who (2005)", "k"), 57243)
        self.assertEqual(api.requests[0][1], {"api_key": "k", "query": "Doctor Who", "first_air_date_year": "2005"})

    def test_an_exact_title_beats_a_more_popular_near_match(self):
        self.api({"/search/tv": {"results": [{"id": 1, "name": "Office Space"}, {"id": 2, "name": "The Office!"}]}})
        self.assertEqual(tmdb._tmdb_search_tv_show_id("the office", "k"), 2)

    def test_no_result_for_the_year_retries_without_it(self):
        class _Api(_FakeApi):
            def __call__(self, url, label):
                result = super().__call__(url, label)
                return {"results": []} if "first_air_date_year" in self.requests[-1][1] else result

        fake = _Api({"/search/tv": {"results": [{"id": 5, "name": "Show", "first_air_date": "2010-01-01"}]}})
        with patch.object(tmdb, "fetch_remote_json", fake):
            self.assertEqual(tmdb._tmdb_search_tv_show_id("Show", "k", 2011), 5)
        self.assertEqual(len(fake.requests), 2)

    def test_a_year_off_by_one_still_counts(self):
        rows = [{"id": 1, "title": "Dune", "release_date": "1984-12-14"}, {"id": 2, "title": "Dune", "release_date": "2021-09-15"}]
        self.api({"/search/movie": {"results": rows}})
        self.assertEqual(tmdb._tmdb_search_movie_id("Dune", "k", 2022), 2)
        self.assertEqual(tmdb._tmdb_search_movie_id("Dune", "k", 1984), 1)

    def test_the_movie_year_from_the_item_is_used(self):
        rows = [{"id": 1, "title": "Dune", "release_date": "1984-12-14"}, {"id": 2, "title": "Dune", "release_date": "2021-09-15"}]
        self.api({"/search/movie": {"results": rows}, "/movie/1/external_ids": {"imdb_id": "tt0087182"}})
        self.assertEqual(tmdb._tmdb_enrich_missing_movie_ids({"title": "Dune", "year": 1984}, None, None, "k"), (1, "tt0087182"))

    def test_title_and_year_helpers(self):
        self.assertEqual(tmdb.split_title_year("Doctor Who (2005)"), ("Doctor Who", 2005))
        self.assertEqual(tmdb.split_title_year("1917"), ("1917", None))
        self.assertEqual(tmdb.split_title_year(None), ("", None))
        self.assertEqual(tmdb._title_key("Amélie: The Movie!"), "amelie the movie")


class MovieIdTests(unittest.TestCase):
    def api(self, routes):
        fake = _FakeApi(routes)
        patcher = patch.object(tmdb, "fetch_remote_json", fake)
        patcher.start()
        self.addCleanup(patcher.stop)
        return fake

    def test_an_imdb_id_finds_the_movie_without_a_title_search(self):
        api = self.api({"/find/tt0133093": {"movie_results": [{"id": 603}]}})
        self.assertEqual(tmdb._tmdb_enrich_missing_movie_ids({"title": "The Matrix"}, None, "tt0133093", "k"), (603, "tt0133093"))
        self.assertEqual([path for path, _q in api.requests], ["/find/tt0133093"])
        self.assertEqual(api.requests[0][1]["external_source"], "imdb_id")

    def test_a_title_search_then_the_imdb_id(self):
        self.api(
            {
                "/search/movie": {"results": [{"id": 603}]},
                "/movie/603/external_ids": {"imdb_id": "tt0133093"},
            }
        )
        self.assertEqual(tmdb._tmdb_enrich_missing_movie_ids({"title": "The Matrix"}, None, None, "k"), (603, "tt0133093"))

    def test_nothing_found_returns_what_came_in(self):
        self.api({"/search/movie": {"results": []}})
        self.assertEqual(tmdb._tmdb_enrich_missing_movie_ids({"title": "X"}, "bad", None, "k"), ("bad", None))


if __name__ == "__main__":
    unittest.main()
