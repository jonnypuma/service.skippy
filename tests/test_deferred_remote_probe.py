# -*- coding: utf-8 -*-
"""Deferred remote probe lifecycle."""

import threading
import unittest
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()


class DeferredRemoteProbeTests(unittest.TestCase):
    @patch("service_deferred_remote_probe.threading.Thread")
    @patch("service_deferred_remote_probe._deferred_probe_already_satisfied", return_value=False)
    def test_schedule_starts_daemon_thread(self, _sat, mock_thread):
        import service_deferred_remote_probe as mod

        monitor = MagicMock()
        monitor.deferred_remote_probe_lock = threading.Lock()
        monitor.deferred_remote_probe_path = None
        monitor.deferred_remote_probe_result = None
        player = MagicMock()
        mod.schedule_deferred_remote_probe(
            monitor, "/v.mkv", "episode", [], False, player
        )
        mock_thread.assert_called_once()
        kwargs = mock_thread.call_args[1]
        self.assertTrue(kwargs.get("daemon"))
        self.assertEqual(kwargs.get("name"), "skippy_remote_probe")

    def test_clear_clears_processed_cache_companion(self):
        from service_deferred_remote_probe import clear_deferred_remote_probe_state
        from service_segment_processed_cache import clear_segment_processed_cache

        monitor = MagicMock()
        monitor.deferred_remote_probe_lock = threading.Lock()
        monitor.segment_processed_cache = {"key": "x"}
        clear_deferred_remote_probe_state(monitor)
        clear_segment_processed_cache(monitor)
        self.assertIsNone(monitor.segment_processed_cache)


if __name__ == "__main__":
    unittest.main()
