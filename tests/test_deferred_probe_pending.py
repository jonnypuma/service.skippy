# -*- coding: utf-8 -*-
"""Deferred remote probe pending helper."""

import threading
import unittest

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()


class DeferredProbePendingTests(unittest.TestCase):
    def test_pending_while_running_for_same_path(self):
        from service_deferred_remote_probe import (
            _PROBE_RUNNING,
            is_deferred_remote_probe_pending,
        )

        monitor = MagicMockShim()
        monitor.deferred_remote_probe_lock = threading.Lock()
        monitor.deferred_remote_probe_path = "/v.mkv"
        monitor.deferred_remote_probe_result = _PROBE_RUNNING
        self.assertTrue(is_deferred_remote_probe_pending(monitor, "/v.mkv"))

    def test_not_pending_for_other_path(self):
        from service_deferred_remote_probe import (
            _PROBE_RUNNING,
            is_deferred_remote_probe_pending,
        )

        monitor = MagicMockShim()
        monitor.deferred_remote_probe_lock = threading.Lock()
        monitor.deferred_remote_probe_path = "/other.mkv"
        monitor.deferred_remote_probe_result = _PROBE_RUNNING
        self.assertFalse(is_deferred_remote_probe_pending(monitor, "/v.mkv"))


class MagicMockShim:
    pass


if __name__ == "__main__":
    unittest.main()
