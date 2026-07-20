# -*- coding: utf-8 -*-
"""TheIntroDB.org v3 submit payload (optional tvdb_id)."""

import unittest
from unittest.mock import patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()


class TheIntroDbSubmitPayloadTests(unittest.TestCase):
    def test_submit_includes_optional_tvdb_id(self):
        import online_segment_upload as mod

        ctx = {
            "type": "tv",
            "season": 2,
            "episode": 10,
            "tmdb_id": 219971,
            "tvdb_id": 424321,
            "show_imdb_id": "tt26656917",
            "playback_duration_seconds": 3600.0,
        }
        captured = {}

        def fake_post(url, headers, payload):
            captured["url"] = url
            captured["headers"] = headers
            captured["payload"] = payload
            return 200, {"ok": True, "submissions": [{"id": "abc"}]}, None

        with patch.object(mod, "_http_post_json", side_effect=fake_post):
            ok, msg = mod._submit_theintrodb(
                ctx, "intro", 65.0, 127.0, "test-key"
            )

        self.assertTrue(ok)
        self.assertEqual(msg, "ok")
        self.assertEqual(captured["url"], mod.THEINTRODB_SUBMIT_URL)
        self.assertEqual(
            captured["headers"].get("Authorization"), "Bearer test-key"
        )
        body = captured["payload"]
        self.assertEqual(body["tmdb_id"], 219971)
        self.assertEqual(body["type"], "tv")
        self.assertEqual(body["segment"], "intro")
        self.assertEqual(body["season"], 2)
        self.assertEqual(body["episode"], 10)
        self.assertEqual(body["tvdb_id"], 424321)
        self.assertEqual(body["imdb_id"], "tt26656917")

    def test_submit_omits_missing_tvdb_id(self):
        import online_segment_upload as mod

        ctx = {
            "type": "tv",
            "season": 1,
            "episode": 1,
            "tmdb_id": 1396,
            "tvdb_id": None,
            "show_imdb_id": "tt0903747",
            "playback_duration_seconds": 3600.0,
        }
        captured = {}

        def fake_post(_url, _headers, payload):
            captured["payload"] = payload
            return 200, {"ok": True, "submissions": [{"id": "x"}]}, None

        with patch.object(mod, "_http_post_json", side_effect=fake_post):
            ok, _ = mod._submit_theintrodb(ctx, "recap", 2.5, 58.0, "k")

        self.assertTrue(ok)
        body = captured["payload"]
        self.assertNotIn("tvdb_id", body)
        self.assertEqual(body["tmdb_id"], 1396)


if __name__ == "__main__":
    unittest.main()
