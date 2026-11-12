# -*- coding: utf-8 -*-
"""Online requests: answers, failures, back-off after errors, and keeping API keys out of the log."""

import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import remote_http as http  # noqa: E402


class _Response(io.BytesIO):
    def close(self):
        pass


class _Addon:
    def __init__(self, cooldown="120"):
        self.cooldown = cooldown

    def getSetting(self, key):
        return self.cooldown if key == "remote_api_failure_cooldown_seconds" else ""

    def getSettingString(self, key):
        return self.getSetting(key)

    def getAddonInfo(self, _key):
        return "7.11.6"


class FetchTests(unittest.TestCase):
    def setUp(self):
        http._REMOTE_FETCH_COOL_UNTIL.clear()
        http._REMOTE_FETCH_FAILURE_STREAK.clear()
        self.addCleanup(http._REMOTE_FETCH_COOL_UNTIL.clear)
        self.addCleanup(http._REMOTE_FETCH_FAILURE_STREAK.clear)
        self.addon = _Addon()
        self.logged = []
        self.requests = []
        self.replies = []
        self.now = 1000.0
        stack = [
            patch.object(http, "get_addon", lambda: self.addon),
            patch.object(http, "urlopen", self._urlopen),
            patch.object(http, "_rlog", self.logged.append),
            patch.object(http.time, "monotonic", lambda: self.now),
        ]
        for p in stack:
            p.start()
            self.addCleanup(p.stop)

    def _urlopen(self, request, timeout):
        self.requests.append((request, timeout))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return _Response(reply)

    def _http_error(self, code, headers=None):
        return HTTPError("https://x", code, "err", headers or {}, None)

    def test_a_json_answer_is_returned_with_our_user_agent(self):
        self.replies = [json.dumps({"ok": True}).encode()]
        data = http.fetch_remote_json("https://api.example/x?api_key=SECRET", "TheIntroDB", {"X-Key": " k ", "Empty": None})
        self.assertEqual(data, {"ok": True})
        request, timeout = self.requests[0]
        self.assertEqual(timeout, http.REMOTE_LOOKUP_TIMEOUT)
        self.assertEqual(request.get_header("User-agent"), "service.skippy/7.11.6")
        self.assertEqual(request.get_header("X-key"), "k")
        self.assertIsNone(request.get_header("Empty"))

    def test_the_api_key_never_reaches_the_log(self):
        self.replies = [b"{}"]
        http.fetch_remote_json("https://api.example/x?api_key=SECRET&query=a", "TMDB")
        self.assertTrue(self.logged)
        self.assertFalse(any("SECRET" in line for line in self.logged))
        self.assertEqual(http._safe_log_url("https://a/b?api_key=K1&x=2"), "https://a/b?api_key=***&x=2")
        self.assertEqual(http._safe_log_url("https://a/b"), "https://a/b")

    def test_404_means_no_match_and_no_back_off(self):
        self.replies = [self._http_error(404), b"{}"]
        self.assertEqual(http.fetch_remote_json("https://x", "TMDB"), {})
        self.assertEqual(http.fetch_remote_json("https://x", "TMDB"), {})
        self.assertEqual(len(self.requests), 2)

    def test_an_error_pauses_that_service_only(self):
        self.replies = [self._http_error(500), b"{}"]
        self.assertIsNone(http.fetch_remote_json("https://x", "TMDB"))
        self.assertIsNone(http.fetch_remote_json("https://x", "TMDB"))  # skipped: cooling down
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(http.fetch_remote_json("https://y", "TheIntroDB"), {})  # another service still works
        self.now += 121
        self.replies = [b"{}"]
        self.assertEqual(http.fetch_remote_json("https://x", "TMDB"), {})

    def test_repeated_errors_back_off_longer_up_to_a_cap(self):
        delays = []
        for _ in range(8):
            self.replies = [URLError("down")]
            http.fetch_remote_json("https://x", "IntroDB.app")
            delays.append(http._REMOTE_FETCH_COOL_UNTIL["introdb"] - self.now)
            self.now = http._REMOTE_FETCH_COOL_UNTIL["introdb"]
        self.assertEqual(delays[:3], [120, 240, 480])
        self.assertTrue(all(b >= a for a, b in zip(delays, delays[1:])))
        self.assertLessEqual(max(delays), http._REMOTE_BACKOFF_CAP_SECONDS)

    def test_a_success_resets_the_back_off(self):
        self.replies = [URLError("down")]
        http.fetch_remote_json("https://x", "TMDB")
        self.now += 200
        self.replies = [b"{}", URLError("down")]
        http.fetch_remote_json("https://x", "TMDB")
        http.fetch_remote_json("https://x", "TMDB")
        self.assertEqual(http._REMOTE_FETCH_COOL_UNTIL["tmdb"] - self.now, 120)

    def test_retry_after_is_honoured(self):
        self.replies = [self._http_error(429, {"Retry-After": "600"})]
        http.fetch_remote_json("https://x", "TMDB")
        self.assertEqual(http._REMOTE_FETCH_COOL_UNTIL["tmdb"] - self.now, 600)

    def test_a_bad_answer_counts_as_a_failure(self):
        self.replies = [b"<html>not json</html>"]
        self.assertIsNone(http.fetch_remote_json("https://x", "TMDB"))
        self.assertIn("tmdb", http._REMOTE_FETCH_COOL_UNTIL)

    def test_a_cooldown_of_zero_turns_the_pause_off(self):
        self.addon.cooldown = "0"
        self.replies = [URLError("down"), b"{}"]
        http.fetch_remote_json("https://x", "TMDB")
        self.assertEqual(http.fetch_remote_json("https://x", "TMDB"), {})
        self.addon.cooldown = "nonsense"
        self.assertEqual(http._remote_failure_cooldown_seconds(), 120)
        self.addon.cooldown = "99999"
        self.assertEqual(http._remote_failure_cooldown_seconds(), 3600)


class JsonRpcTests(unittest.TestCase):
    def test_the_answer_is_decoded_and_errors_give_a_dict(self):
        with patch.object(http.xbmc, "executeJSONRPC", lambda payload: json.dumps({"result": json.loads(payload)}), create=True):
            data = http.jsonrpc("Player.GetItem", {"playerid": 1})
        self.assertEqual(data["result"]["method"], "Player.GetItem")
        self.assertEqual(data["result"]["params"], {"playerid": 1})
        with patch.object(http.xbmc, "executeJSONRPC", lambda payload: "not json", create=True), patch.object(http, "_rlog"):
            self.assertEqual(http.jsonrpc("X"), {})
        with patch.object(http.xbmc, "executeJSONRPC", lambda payload: json.dumps({"error": {"code": -32601}}), create=True), patch.object(
            http, "_rlog"
        ) as logged:
            self.assertEqual(http.jsonrpc("X"), {"error": {"code": -32601}})
            logged.assert_called_once()


class IdTests(unittest.TestCase):
    def test_ids(self):
        self.assertEqual(http.normalize_imdb_id("tt0903747"), "tt0903747")
        self.assertEqual(http.normalize_imdb_id(903747), "tt0903747")
        self.assertEqual(http.normalize_imdb_id("903747.0"), "tt0903747")
        for bad in (None, "", "abc", 0, -5):
            self.assertIsNone(http.normalize_imdb_id(bad), bad)
        self.assertEqual(http.normalize_numeric_id("1396"), 1396)
        self.assertIsNone(http.normalize_numeric_id("tt1"))
        self.assertIsNone(http.normalize_numeric_id(""))
        self.assertEqual(http.parse_int("7"), 7)
        self.assertIsNone(http.parse_int(-1))
        self.assertIsNone(http.parse_int("x"))


if __name__ == "__main__":
    unittest.main()
