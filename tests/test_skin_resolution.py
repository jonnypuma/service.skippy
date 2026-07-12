# -*- coding: utf-8 -*-
"""WindowXML skin resolution helpers."""

import unittest
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()


class SkinResolutionTests(unittest.TestCase):
    @patch("addon_skin_resolution.xbmcgui")
    def test_1080i_when_width_1920_height_720(self, mock_gui):
        """Windows fullscreen can report reduced height while width stays 1920."""
        mock_gui.getScreenWidth.return_value = 1920
        mock_gui.getScreenHeight.return_value = 720
        from addon_skin_resolution import SKIN_RES_1080I, get_addon_skin_resolution

        self.assertEqual(get_addon_skin_resolution(), SKIN_RES_1080I)

    @patch("addon_skin_resolution.xbmcgui")
    def test_720p_when_both_below_threshold(self, mock_gui):
        mock_gui.getScreenWidth.return_value = 1280
        mock_gui.getScreenHeight.return_value = 720
        from addon_skin_resolution import SKIN_RES_720P, get_addon_skin_resolution

        self.assertEqual(get_addon_skin_resolution(), SKIN_RES_720P)

    @patch("addon_skin_resolution.xbmcgui")
    def test_scale_skin_coord_uses_explicit_resolution(self, mock_gui):
        mock_gui.getScreenWidth.return_value = 1280
        mock_gui.getScreenHeight.return_value = 720
        from addon_skin_resolution import SKIN_RES_1080I, scale_skin_coord

        self.assertEqual(scale_skin_coord(100, SKIN_RES_1080I), 150)
        self.assertEqual(scale_skin_coord(100), 100)


if __name__ == "__main__":
    unittest.main()
