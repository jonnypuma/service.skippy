# -*- coding: utf-8 -*-
"""Offline tests for settings_utils.get_localized."""
import unittest

from tests.kodi_stubs import install_kodi_stubs


class TestGetLocalized(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        install_kodi_stubs()

    def test_fallback_default(self):
        from settings_utils import get_localized

        class _Addon:
            def getLocalizedString(self, _sid):
                return ""

        self.assertEqual(get_localized(_Addon(), 40000, "Skip"), "Skip")

    def test_format_args(self):
        from settings_utils import get_localized

        class _Addon:
            def getLocalizedString(self, _sid):
                return "Skip %s (%s)"

        self.assertEqual(
            get_localized(_Addon(), 40003, "Skip %s (%s)", "Intro", "1m"),
            "Skip Intro (1m)",
        )

    def test_none_addon_uses_default(self):
        from settings_utils import get_localized

        self.assertEqual(get_localized(None, 43000, "Skippy"), "Skippy")


if __name__ == "__main__":
    unittest.main()
