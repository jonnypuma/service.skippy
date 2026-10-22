# -*- coding: utf-8 -*-
"""TheIntroDB.org v4 submit payload (exactly one media id)."""

import unittest
from unittest.mock import patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()


class TheIntroDbSubmitPayloadTests(unittest.TestCase):
    def test_submit_sends_single_tvdb_id(self):
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
        self.assertEqual(body["tvdb_id"], 424321)
        self.assertNotIn("tmdb_id", body)
        self.assertEqual(body["type"], "tv")
        self.assertEqual(body["segment"], "intro")
        self.assertEqual(body["season"], 2)
        self.assertEqual(body["episode"], 10)
        # v4 resolves tvdb -> tmdb -> imdb, so only one id may be sent (TVDB wins).
        self.assertNotIn("imdb_id", body)
        self.assertIn("/v4/submit", captured["url"])

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
        self.assertEqual(body["tmdb_id"], 1396)  # no TVDB id -> TMDB fallback

    def test_submit_falls_back_to_tvdb_then_imdb(self):
        import online_segment_upload as mod

        seen = []

        def fake_post(_url, _headers, payload):
            seen.append(payload)
            return 200, {"ok": True, "submissions": [{"id": "x"}]}, None

        base = {"type": "movie", "playback_duration_seconds": 7200.0}
        with patch.object(mod, "_http_post_json", side_effect=fake_post):
            mod._submit_theintrodb(dict(base, tvdb_id=169, imdb_id="tt0111161"), "intro", 10.0, 60.0, "k")
            mod._submit_theintrodb(dict(base, imdb_id="tt0111161"), "intro", 10.0, 60.0, "k")
            ok, _ = mod._submit_theintrodb(dict(base), "intro", 10.0, 60.0, "k")
        self.assertEqual(seen[0]["tvdb_id"], 169)
        self.assertNotIn("imdb_id", seen[0])
        self.assertEqual(seen[1]["imdb_id"], "tt0111161")
        self.assertFalse(ok)
        self.assertEqual(len(seen), 2)

    def test_tv_with_series_and_episode_tvdb_ids_pins_the_episode(self):
        import online_segment_upload as mod

        seen = []

        def fake_post(_url, _headers, payload):
            seen.append(payload)
            return 200, {"ok": True, "submissions": [{"id": "x"}]}, None

        ctx = {
            "type": "tv", "season": 2, "episode": 3, "tmdb_id": 1396,
            "tvdb_id": 81189, "tvdb_episode_id": 349232,
            "playback_duration_seconds": 3000.0,
        }
        with patch.object(mod, "_http_post_json", side_effect=fake_post):
            ok, _ = mod._submit_theintrodb(ctx, "intro", 10.0, 60.0, "k")
        self.assertTrue(ok)
        self.assertEqual(seen[0]["tvdb_id"], 81189)
        self.assertEqual(seen[0]["tvdb_episode_id"], 349232)
        self.assertNotIn("tmdb_id", seen[0])

    def test_lookup_query_pins_episode_when_both_tvdb_ids_known(self):
        import remote_lookup as rl

        q = rl._theintrodb_id_query(
            {"type": "tv", "tmdb_id": 1, "tvdb_id": 81189, "tvdb_episode_id": 349232}
        )
        self.assertEqual(q, {"tvdb_id": 81189, "tvdb_episode_id": 349232})
        self.assertEqual(rl._theintrodb_id_query({"type": "tv", "tmdb_id": 1, "tvdb_id": 5}), {"tvdb_id": 5})
        self.assertEqual(rl._theintrodb_id_query({"type": "tv", "tmdb_id": 1}), {"tmdb_id": 1})
        self.assertEqual(rl._theintrodb_id_query({"type": "movie", "tvdb_id": 169, "tvdb_episode_id": 9}), {"tvdb_id": 169})

    def test_introdb_app_lookup_movie_and_specials(self):
        import remote_lookup as rl

        urls = []

        def fake_fetch(url, *_a, **_k):
            urls.append(url)
            return {"outro": {"start_ms": 7000000, "end_ms": 7200000}, "intro": None}

        with patch.object(rl, "fetch_remote_json", side_effect=fake_fetch):
            segs = rl.fetch_introdb_segments({"type": "movie", "imdb_id": "tt0111161"}, 7300.0)
            self.assertIn("is_movie=true", urls[0])
            self.assertIn("imdb_id=tt0111161", urls[0])
            self.assertNotIn("season", urls[0])
            self.assertEqual([s.segment_type_label for s in segs], ["credits"])
            n = len(urls)
            rl.fetch_introdb_segments(
                {"type": "tv", "show_imdb_id": "tt1", "season": 0, "episode": 1}, 1000.0
            )
            self.assertEqual(len(urls), n)  # specials are not looked up


if __name__ == "__main__":
    unittest.main()
