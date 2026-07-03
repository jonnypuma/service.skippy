# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch

from tests.kodi_stubs import install_kodi_stubs


class SidecarProbeCacheTests(unittest.TestCase):
    def setUp(self):
        install_kodi_stubs()
        from unittest.mock import MagicMock

        self.monitor = MagicMock()
        self.monitor.sidecar_probe_cache = {}

    @patch("service_sidecar_probe_cache.xbmcvfs")
    @patch("service_sidecar_probe_cache.log")
    @patch("service_sidecar_probe_cache._chapter_xml_paths_to_try")
    @patch("service_sidecar_probe_cache._edl_paths_to_try")
    def test_negative_cache_skips_reprobe(
        self, mock_edl, mock_chapter, _log, mock_vfs
    ):
        from service_sidecar_probe_cache import resolve_sidecar_paths

        mock_chapter.return_value = ["/media/show-chapters.xml", "/media/show.xml"]
        mock_edl.return_value = ["/media/show.edl"]
        mock_vfs.exists.return_value = False
        video = "/media/show.mkv"

        first = resolve_sidecar_paths(video, self.monitor)
        self.assertTrue(first.probed)
        self.assertIsNone(first.chapter_path)
        self.assertIsNone(first.edl_path)

        mock_vfs.exists.return_value = True
        calls_after_first = mock_vfs.exists.call_count
        second = resolve_sidecar_paths(video, self.monitor)
        self.assertIsNone(second.chapter_path)
        self.assertEqual(mock_vfs.exists.call_count, calls_after_first)

    @patch("service_sidecar_probe_cache.xbmcvfs")
    @patch("service_sidecar_probe_cache.log")
    @patch("service_sidecar_probe_cache._chapter_xml_paths_to_try")
    @patch("service_sidecar_probe_cache._edl_paths_to_try")
    def test_invalidation_on_clear(self, mock_edl, mock_chapter, _log, mock_vfs):
        from service_sidecar_probe_cache import (
            clear_sidecar_probe_cache,
            resolve_sidecar_paths,
        )

        mock_chapter.return_value = ["/v/a-chapters.xml"]
        mock_edl.return_value = ["/v/a.edl"]
        mock_vfs.exists.side_effect = lambda p: p == "/v/a.edl"
        video = "/v/a.mkv"

        resolve_sidecar_paths(video, self.monitor)
        clear_sidecar_probe_cache(self.monitor, video)
        mock_vfs.reset_mock()
        mock_vfs.exists.side_effect = lambda p: p == "/v/a.edl"

        result = resolve_sidecar_paths(video, self.monitor, force=True)
        self.assertEqual(result.edl_path, "/v/a.edl")


if __name__ == "__main__":
    unittest.main()
