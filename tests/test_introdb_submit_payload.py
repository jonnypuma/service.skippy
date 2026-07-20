# -*- coding: utf-8 -*-
"""IntroDB.app submit payload shape (floats + optional ids)."""

import unittest
from unittest.mock import patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()


class IntroDbSubmitPayloadTests(unittest.TestCase):
    def test_submit_sends_floats_and_optional_ids(self):
        import online_segment_upload as mod

        ctx = {
            "type": "tv",
            "season": 2,
            "episode": 10,
            "show_imdb_id": "tt26656917",
            "tmdb_id": 219971,
            "tvdb_id": 424321,
        }
        captured = {}

        def fake_post(url, headers, payload):
            captured["url"] = url
            captured["headers"] = headers
            captured["payload"] = payload
            return 200, {"ok": True}, None

        with patch.object(mod, "_http_post_json", side_effect=fake_post):
            ok, msg = mod._submit_introdb_app(
                ctx, "intro", 65.13, 127.56, "test-key"
            )

        self.assertTrue(ok)
        self.assertEqual(msg, "ok")
        self.assertEqual(captured["url"], mod.INTRODB_SUBMIT_URL)
        self.assertEqual(captured["headers"].get("X-API-Key"), "test-key")
        body = captured["payload"]
        self.assertEqual(body["imdb_id"], "tt26656917")
        self.assertEqual(body["segment_type"], "intro")
        self.assertEqual(body["season"], 2)
        self.assertEqual(body["episode"], 10)
        self.assertEqual(body["start_sec"], 65.1)
        self.assertEqual(body["end_sec"], 127.6)
        self.assertIsInstance(body["start_sec"], float)
        self.assertIsInstance(body["end_sec"], float)
        self.assertEqual(body["tmdb_id"], 219971)
        self.assertEqual(body["tvdb_id"], 424321)

    def test_submit_omits_missing_optional_ids(self):
        import online_segment_upload as mod

        ctx = {
            "type": "tv",
            "season": 1,
            "episode": 1,
            "show_imdb_id": "tt0903747",
            "tmdb_id": None,
            "tvdb_id": None,
        }
        captured = {}

        def fake_post(_url, _headers, payload):
            captured["payload"] = payload
            return 200, {"ok": True}, None

        with patch.object(mod, "_http_post_json", side_effect=fake_post):
            ok, _ = mod._submit_introdb_app(ctx, "recap", 2.5, 58.0, "k")

        self.assertTrue(ok)
        body = captured["payload"]
        self.assertEqual(body["start_sec"], 2.5)
        self.assertEqual(body["end_sec"], 58.0)
        self.assertNotIn("tmdb_id", body)
        self.assertNotIn("tvdb_id", body)


if __name__ == "__main__":
    unittest.main()
