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


class SidecarSignatureWatchPathTests(unittest.TestCase):
    def setUp(self):
        install_kodi_stubs()

    def test_stats_probe_path_when_listdir_spelling_differs(self):
        import types
        from unittest.mock import MagicMock

        from service_sidecar_paths import _sidecar_signature
        from service_sidecar_probe_cache import SidecarProbeResult

        listed = "nfs://server/share/Show_chapters.xml"
        probe = SidecarProbeResult(chapter_path=listed, edl_path=None, probed=True)
        stat_paths = []

        def fake_stat(path):
            stat_paths.append(path)
            return types.SimpleNamespace(st_mtime=lambda: 1, st_size=lambda: 2)

        with patch(
            "service_sidecar_probe_cache.resolve_sidecar_paths", return_value=probe
        ), patch("service_sidecar_paths.xbmcvfs.Stat", side_effect=fake_stat), patch(
            "service_sidecar_paths.xbmcvfs.exists"
        ) as exists:
            sig = _sidecar_signature("nfs://server/share/show.mkv", MagicMock())
        exists.assert_not_called()
        self.assertEqual(stat_paths, [listed])
        self.assertEqual(sig[0][0], listed)


class ParseCachePathMatchTests(unittest.TestCase):
    def setUp(self):
        install_kodi_stubs()

    def test_cache_hit_slash_normalized_path(self):
        import time
        from unittest.mock import MagicMock

        from segment_item import SegmentItem
        from service_segment_sources import get_cached_source_segments

        monitor = MagicMock()
        seg = SegmentItem(0.0, 10.0, "intro", source="xml")
        monitor.segment_parse_cache = {
            "path": r"nfs://server/share\show.mkv",
            "playback_type": "episode",
            "settings_signature": ("sig",),
            "last_sidecar_check": time.time(),
            "segment_file_found": True,
            "segments": [seg],
        }
        with patch(
            "service_segment_sources.get_addon", return_value=MagicMock()
        ), patch(
            "service_segment_sources._source_settings_signature", return_value=("sig",)
        ), patch(
            "service_segment_sources._sidecar_signature"
        ) as sig:
            result = get_cached_source_segments(
                "nfs://server/share/show.mkv",
                "episode",
                segment_monitor=monitor,
                segment_player=MagicMock(),
                on_remote_segments_saved=lambda *a, **k: None,
                sidecar_mtime_check_interval=5.0,
            )
        sig.assert_not_called()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].start_seconds, 0.0)
        self.assertTrue(monitor.segment_file_found)


if __name__ == "__main__":
    unittest.main()
