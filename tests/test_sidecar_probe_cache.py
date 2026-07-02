# -*- coding: utf-8 -*-
import sys
import types
import unittest
from unittest.mock import MagicMock, patch


def _install_xbmc_stubs():
    if "xbmcvfs" in sys.modules and hasattr(sys.modules.get("xbmc"), "getCondVisibility"):
        return
    xbmcvfs = types.ModuleType("xbmcvfs")

    def exists(path):
        return path in _EXISTING

    xbmcvfs.exists = exists
    sys.modules["xbmcvfs"] = xbmcvfs

    xbmc = types.ModuleType("xbmc")
    xbmc.getCondVisibility = lambda cond: False
    sys.modules["xbmc"] = xbmc

    xbmcaddon = types.ModuleType("xbmcaddon")
    xbmcaddon.Addon = lambda _id: None
    sys.modules["xbmcaddon"] = xbmcaddon
    sys.modules["xbmcgui"] = types.ModuleType("xbmcgui")


_EXISTING = set()


class SidecarProbeCacheTests(unittest.TestCase):
    def setUp(self):
        _install_xbmc_stubs()
        _EXISTING.clear()
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
