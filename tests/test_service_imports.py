# -*- coding: utf-8 -*-
"""Verify refactored service modules and entry point import without Kodi."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import patch

from tests.kodi_stubs import import_fresh, install_kodi_stubs

REFACTORED_LOOP_MODULES = (
    "service_loop_nested",
    "service_loop_playback",
    "service_loop_toast",
    "service_loop_skip",
    "service_playback_context",
    "service_sidecar_probe_cache",
    "service_main_loop",
)


class ServiceImportTests(unittest.TestCase):
    def test_refactored_loop_modules_import(self):
        install_kodi_stubs()
        for name in REFACTORED_LOOP_MODULES:
            with self.subTest(module=name):
                mod = import_fresh(name)
                self.assertIsNotNone(mod)

    def test_service_main_loop_exports_bindings(self):
        install_kodi_stubs()
        mod = import_fresh("service_main_loop")
        self.assertTrue(callable(mod.run_service_main_loop))
        self.assertTrue(hasattr(mod, "ServiceLoopBindings"))

    def test_service_entry_import_without_running_loop(self):
        """``service.py`` must import cleanly; main loop is not started in tests."""
        install_kodi_stubs()
        import_fresh("service_main_loop")
        with patch("service_main_loop.run_service_main_loop", lambda _ctx: None):
            mod = import_fresh("service")
        self.assertIn("service", sys.modules)
        self.assertTrue(hasattr(mod, "run_service_main_loop"))
        self.assertTrue(hasattr(mod, "ServiceLoopBindings"))


if __name__ == "__main__":
    unittest.main()
