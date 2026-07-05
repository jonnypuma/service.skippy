# -*- coding: utf-8 -*-
"""TV prefetch runs in a background thread (non-blocking main loop)."""

import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()


class _Monitor:
    prefetch_tv_scheduled_path = None
    prefetch_tv_lock = threading.Lock()
    prefetch_tv_result = None


class TvPrefetchThreadingTests(unittest.TestCase):
    @patch("service_segment_prefetch.get_addon")
    @patch("service_segment_prefetch.addon_get_bool", return_value=True)
    @patch("service_segment_prefetch.addon_get_setting_text", return_value="OnlineFirst")
    @patch("service_segment_prefetch._normalize_segment_source_priority", return_value="OnlineFirst")
    @patch("service_segment_prefetch.threading.Thread")
    @patch("service_segment_prefetch._prefetch_worker")
    def test_schedule_starts_thread_and_returns_immediately(
        self, mock_worker, mock_thread, *_mocks
    ):
        import service_segment_prefetch as mod

        monitor = _Monitor()
        mod.schedule_tv_successor_prefetch(monitor, "/ep1.mkv", "episode")
        mock_thread.assert_called_once()
        args, kwargs = mock_thread.call_args
        self.assertEqual(kwargs.get("name"), "skippy_tv_prefetch")
        self.assertTrue(kwargs.get("daemon"))
        self.assertEqual(monitor.prefetch_tv_scheduled_path, "/ep1.mkv")
        self.assertEqual(monitor.prefetch_tv_result, mod._PREFETCH_RUNNING)

    @patch("service_segment_prefetch.get_addon")
    @patch("service_segment_prefetch.addon_get_bool", return_value=True)
    @patch("service_segment_prefetch.addon_get_setting_text", return_value="OnlineFirst")
    @patch("service_segment_prefetch._normalize_segment_source_priority", return_value="OnlineFirst")
    @patch("service_segment_prefetch.threading.Thread")
    def test_duplicate_schedule_while_running_is_noop(self, mock_thread, *_mocks):
        import service_segment_prefetch as mod

        monitor = _Monitor()
        monitor.prefetch_tv_scheduled_path = "/ep1.mkv"
        monitor.prefetch_tv_result = mod._PREFETCH_RUNNING
        mod.schedule_tv_successor_prefetch(monitor, "/ep1.mkv", "episode")
        mock_thread.assert_not_called()


if __name__ == "__main__":
    unittest.main()
