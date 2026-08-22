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
        self.assertEqual([p.replace("\\", "/") for p in found], ["/media/show.edl"])
        self.assertEqual(unknown, [])


if __name__ == "__main__":
    unittest.main()
