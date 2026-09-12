# -*- coding: utf-8 -*-
import time
import unittest
from unittest.mock import patch

from tests.kodi_stubs import install_kodi_stubs


class SidecarProbeCacheTests(unittest.TestCase):
    def setUp(self):
        install_kodi_stubs()
        from unittest.mock import MagicMock

        self.monitor = MagicMock()
        self.monitor.sidecar_probe_cache = {}

    def test_listing_negative_skips_exists_and_file(self):
        from service_sidecar_probe_cache import resolve_sidecar_paths

        listed = (None, None, [], [], 12, 2)
        with patch(
            "service_sidecar_probe_cache.sidecar_hits_from_directory_listing",
            return_value=listed,
        ) as listing, patch(
            "service_sidecar_probe_cache.vfs_file_exists"
        ) as exists:
            video = "/media/show.mkv"
            first = resolve_sidecar_paths(video, self.monitor)
            self.assertTrue(first.probed)
            self.assertIsNone(first.chapter_path)
            self.assertIsNone(first.edl_path)
            exists.assert_not_called()

            second = resolve_sidecar_paths(video, self.monitor)
            self.assertIsNone(second.chapter_path)
            self.assertEqual(listing.call_count, 1)

    def test_relists_after_max_age(self):
        from service_sidecar_probe_cache import resolve_sidecar_paths

        listed = (None, None, [], [], 12, 2)
        with patch(
            "service_sidecar_probe_cache.sidecar_hits_from_directory_listing",
            return_value=listed,
        ) as listing:
            video = "/media/show.mkv"
            resolve_sidecar_paths(video, self.monitor, max_age_s=0.01)
            time.sleep(0.02)
            resolve_sidecar_paths(video, self.monitor, max_age_s=0.01)
            self.assertEqual(listing.call_count, 2)

    def test_confirmed_miss_uses_longer_ttl(self):
        from service_sidecar_probe_cache import resolve_sidecar_paths

        listed = (None, None, [], [], 12, 2)
        clock = {"t": 0.0}
        with patch(
            "service_sidecar_probe_cache.sidecar_hits_from_directory_listing",
            return_value=listed,
        ) as listing, patch(
            "service_sidecar_probe_cache.time.monotonic", side_effect=lambda: clock["t"]
        ):
            video = "/media/show.mkv"
            resolve_sidecar_paths(video, self.monitor)
            clock["t"] = 10.0
            resolve_sidecar_paths(video, self.monitor)
            self.assertEqual(listing.call_count, 1)
            clock["t"] = 61.0
            resolve_sidecar_paths(video, self.monitor)
            self.assertEqual(listing.call_count, 2)

    def test_hit_relists_after_five_seconds(self):
        from service_sidecar_probe_cache import resolve_sidecar_paths

        listed = ("/media/show_chapters.xml", "/media/show.edl", [], [], 12, 2)
        clock = {"t": 0.0}
        with patch(
            "service_sidecar_probe_cache.sidecar_hits_from_directory_listing",
            return_value=listed,
        ) as listing, patch(
            "service_sidecar_probe_cache.time.monotonic", side_effect=lambda: clock["t"]
        ):
            video = "/media/show.mkv"
            resolve_sidecar_paths(video, self.monitor)
            clock["t"] = 6.0
            resolve_sidecar_paths(video, self.monitor)
            self.assertEqual(listing.call_count, 2)

    def test_invalidation_on_clear(self):
        from service_sidecar_probe_cache import (
            clear_sidecar_probe_cache,
            resolve_sidecar_paths,
        )

        listed = (None, None, [], [], 1, 1)
        with patch(
            "service_sidecar_probe_cache.sidecar_hits_from_directory_listing",
            return_value=listed,
        ) as listing:
            video = "/media/show.mkv"
            resolve_sidecar_paths(video, self.monitor)
            clear_sidecar_probe_cache(self.monitor, video)
            resolve_sidecar_paths(video, self.monitor)
            self.assertEqual(listing.call_count, 2)

    def test_runscript_invalidation_clears_miss_cache(self):
        from service_sidecar_probe_cache import (
            consume_sidecar_probe_invalidation,
            request_sidecar_probe_invalidation,
            resolve_sidecar_paths,
        )

        listed = (None, None, [], [], 12, 2)
        props = {}

        class _Win:
            def __init__(self, *_a, **_k):
                pass

            def setProperty(self, key, value):
                props[key] = value

            def getProperty(self, key):
                return props.get(key, "")

            def clearProperty(self, key):
                props.pop(key, None)

        self.monitor.segment_parse_cache = {"path": "/media/show.mkv", "segments": []}
        with patch(
            "service_sidecar_probe_cache.sidecar_hits_from_directory_listing",
            return_value=listed,
        ) as listing, patch("xbmcgui.Window", _Win):
            video = "/media/show.mkv"
            resolve_sidecar_paths(video, self.monitor)
            self.assertEqual(listing.call_count, 1)
            request_sidecar_probe_invalidation(video)
            self.assertTrue(consume_sidecar_probe_invalidation(self.monitor))
            self.assertIsNone(self.monitor.segment_parse_cache)
            resolve_sidecar_paths(video, self.monitor)
            self.assertEqual(listing.call_count, 2)

    def test_listing_hit_used_without_exists_fallback(self):
        from service_sidecar_probe_cache import resolve_sidecar_paths

        listed = ("/media/show_chapters.xml", "/media/show.edl", [], [], 12, 2)
        with patch(
            "service_sidecar_probe_cache.sidecar_hits_from_directory_listing",
            return_value=listed,
        ), patch("service_sidecar_probe_cache.vfs_file_exists") as exists:
            result = resolve_sidecar_paths("/media/show.mkv", self.monitor)
            self.assertEqual(result.chapter_path, "/media/show_chapters.xml")
            self.assertEqual(result.edl_path, "/media/show.edl")
            exists.assert_not_called()


class DirectoryListingMatchTests(unittest.TestCase):
    def setUp(self):
        install_kodi_stubs()

    def test_existing_paths_from_listing_skips_unlisted(self):
        from service_sidecar_paths import existing_paths_from_listing

        def fake_listdir(parent):
            if parent.replace("\\", "/").endswith(".chapters"):
                return [], []
            return [".chapters"], ["show.mkv", "show.edl"]

        with patch("service_sidecar_paths.xbmcvfs.listdir", side_effect=fake_listdir):
            found, unknown = existing_paths_from_listing(
                [
                    "/media/show_chapters.xml",
                    "/media/show.edl",
                    "/media/.chapters/show.edl",
                ]
            )
        self.assertEqual(found, ["/media/show.edl"])
        self.assertEqual(unknown, [])

    def test_vfs_join_keeps_nfs_forward_slashes(self):
        from service_sidecar_paths import vfs_join, vfs_paths_match

        self.assertEqual(
            vfs_join("nfs://server/share", ".chapters", "show.edl"),
            "nfs://server/share/.chapters/show.edl",
        )
        self.assertTrue(
            vfs_paths_match(
                r"nfs://server/share/show.mkv",
                r"nfs://server/share\show.mkv",
            )
        )

    def test_nfs_jellyfin_sidecar_candidates_have_no_backslashes(self):
        from service_sidecar_paths import _chapter_xml_paths_to_try

        paths = _chapter_xml_paths_to_try("nfs://server/share/show.mkv")
        self.assertTrue(paths)
        self.assertTrue(all("\\" not in p for p in paths))
        self.assertIn("nfs://server/share/.chapters/show_chapters.xml", paths)


class ProbeInvalidationPathMatchTests(unittest.TestCase):
    def setUp(self):
        install_kodi_stubs()
        from unittest.mock import MagicMock

        self.monitor = MagicMock()
        self.monitor.sidecar_probe_cache = {}

    def test_invalidation_matches_backslash_variant(self):
        from service_sidecar_probe_cache import (
            consume_sidecar_probe_invalidation,
            request_sidecar_probe_invalidation,
            resolve_sidecar_paths,
        )

        listed = (None, None, [], [], 12, 2)
        props = {}

        class _Win:
            def __init__(self, *_a, **_k):
                pass

            def setProperty(self, key, value):
                props[key] = value

            def getProperty(self, key):
                return props.get(key, "")

            def clearProperty(self, key):
                props.pop(key, None)

        playback = "nfs://server/share/show.mkv"
        editor = r"nfs://server/share\show.mkv"
        self.monitor.segment_parse_cache = {"path": playback, "segments": []}
        with patch(
            "service_sidecar_probe_cache.sidecar_hits_from_directory_listing",
            return_value=listed,
        ) as listing, patch("xbmcgui.Window", _Win):
            resolve_sidecar_paths(playback, self.monitor)
            self.assertEqual(listing.call_count, 1)
            request_sidecar_probe_invalidation(editor)
            self.assertTrue(consume_sidecar_probe_invalidation(self.monitor))
            self.assertIsNone(self.monitor.segment_parse_cache)
            self.assertEqual(self.monitor.sidecar_probe_cache, {})
            resolve_sidecar_paths(playback, self.monitor)
            self.assertEqual(listing.call_count, 2)


if __name__ == "__main__":
    unittest.main()
