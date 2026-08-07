# -*- coding: utf-8 -*-
"""Hot-path logging should not spam on every is_active call."""

import sys
import unittest
from unittest.mock import patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import settings_utils
from segment_item import SegmentItem


class HotPathLoggingTests(unittest.TestCase):
    @patch("segment_item.log_segment_detail")
    def test_is_active_does_not_log(self, mock_detail):
        seg = SegmentItem(0.0, 60.0, "intro", source="xml")
        for t in range(100):
            seg.is_active(float(t))
        mock_detail.assert_not_called()

    @patch("segment_item.log_segment_detail")
    def test_get_duration_does_not_log(self, mock_detail):
        seg = SegmentItem(0.0, 60.0, "intro", source="xml")
        for _ in range(50):
            seg.get_duration()
        mock_detail.assert_not_called()


class SettingsCacheTests(unittest.TestCase):
    def tearDown(self):
        settings_utils.invalidate_settings_cache()

    def test_get_addon_reuses_handle_within_ttl(self):
        settings_utils.invalidate_settings_cache()
        xbmcaddon = sys.modules["xbmcaddon"]
        original = xbmcaddon.Addon
        built = []

        def _counting(addon_id):
            built.append(addon_id)
            return original(addon_id)

        xbmcaddon.Addon = _counting
        try:
            first = settings_utils.get_addon()
            for _ in range(20):
                self.assertIs(settings_utils.get_addon(), first)
        finally:
            xbmcaddon.Addon = original
        self.assertEqual(len(built), 1)

    def test_invalidate_forces_a_fresh_handle(self):
        settings_utils.invalidate_settings_cache()
        xbmcaddon = sys.modules["xbmcaddon"]
        original = xbmcaddon.Addon
        built = []

        def _counting(addon_id):
            built.append(addon_id)
            return original(addon_id)

        xbmcaddon.Addon = _counting
        try:
            settings_utils.get_addon()
            settings_utils.invalidate_settings_cache()
            settings_utils.get_addon()
        finally:
            xbmcaddon.Addon = original
        self.assertEqual(len(built), 2)

    def test_skip_mode_keyword_sets_are_memoized(self):
        settings_utils.invalidate_settings_cache()
        values = {
            "segment_always_skip": "ad,ads",
            "segment_ask_skip": "intro,recap",
            "segment_never_skip": "credits",
        }
        addon = type("_A", (), {"getSetting": lambda _self, key: values.get(key, "")})()
        first = settings_utils._skip_mode_keyword_sets(addon)
        self.assertIs(settings_utils._skip_mode_keyword_sets(addon), first)

        values["segment_ask_skip"] = "intro,recap,preview"
        second = settings_utils._skip_mode_keyword_sets(addon)
        self.assertIsNot(second, first)
        self.assertIn("preview", second[1])


if __name__ == "__main__":
    unittest.main()
