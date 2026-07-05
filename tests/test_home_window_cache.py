# -*- coding: utf-8 -*-
"""Cached Kodi home window on monitor."""

import unittest
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()


class HomeWindowCacheTests(unittest.TestCase):
    @patch("segment_editor_utils.xbmcgui.Window")
    def test_get_home_window_caches_on_monitor(self, mock_window_cls):
        from segment_editor_utils import get_home_window

        win = MagicMock()
        mock_window_cls.return_value = win
        monitor = MagicMock()
        monitor._home_window = None
        a = get_home_window(monitor)
        b = get_home_window(monitor)
        self.assertIs(a, b)
        mock_window_cls.assert_called_once_with(10000)


if __name__ == "__main__":
    unittest.main()
