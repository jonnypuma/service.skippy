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
    def test_1080i_when_windowed_near_hd(self, mock_gui):
        """Predator-style windowed GUI under 1920×1080 still requests 1080i."""
        mock_gui.getScreenWidth.return_value = 1902
        mock_gui.getScreenHeight.return_value = 973
        from addon_skin_resolution import SKIN_RES_1080I, get_addon_skin_resolution

        self.assertEqual(get_addon_skin_resolution(), SKIN_RES_1080I)

    @patch("addon_skin_resolution.xbmcgui")
    def test_720p_when_both_below_near_hd(self, mock_gui):
        mock_gui.getScreenWidth.return_value = 1280
        mock_gui.getScreenHeight.return_value = 720
        from addon_skin_resolution import SKIN_RES_720P, get_addon_skin_resolution

        self.assertEqual(get_addon_skin_resolution(), SKIN_RES_720P)

    @patch("addon_skin_resolution.xbmcgui")
    def test_720p_typical_laptop_1366(self, mock_gui):
        mock_gui.getScreenWidth.return_value = 1366
        mock_gui.getScreenHeight.return_value = 768
        from addon_skin_resolution import SKIN_RES_720P, get_addon_skin_resolution

        self.assertEqual(get_addon_skin_resolution(), SKIN_RES_720P)

    @patch("addon_skin_resolution.xbmcgui")
    def test_scale_skin_coord_uses_explicit_resolution(self, mock_gui):
        mock_gui.getScreenWidth.return_value = 1280
        mock_gui.getScreenHeight.return_value = 720
        from addon_skin_resolution import SKIN_RES_1080I, scale_skin_coord

        self.assertEqual(scale_skin_coord(100, SKIN_RES_1080I), 150)
        self.assertEqual(scale_skin_coord(100), 100)

    def test_infer_from_full_skip_panel_widths(self):
        from addon_skin_resolution import (
            SKIN_RES_1080I,
            SKIN_RES_720P,
            infer_skin_resolution_from_widths,
        )

        self.assertEqual(infer_skin_resolution_from_widths([645]), SKIN_RES_1080I)
        self.assertEqual(infer_skin_resolution_from_widths([430]), SKIN_RES_720P)
        self.assertEqual(infer_skin_resolution_from_widths([180]), SKIN_RES_1080I)
        self.assertEqual(infer_skin_resolution_from_widths([120]), SKIN_RES_720P)
        self.assertIsNone(infer_skin_resolution_from_widths([50]))

    def test_reconcile_relocks_when_kodi_loaded_1080i(self):
        from addon_skin_resolution import (
            SKIN_RES_1080I,
            SKIN_RES_720P,
            reconcile_window_xml_skin_resolution,
            scale_skin_coord,
        )

        panel = MagicMock()
        panel.getWidth.return_value = 645
        window = MagicMock()

        def get_control(cid):
            if int(cid) == 3080:
                return panel
            raise Exception("missing")

        window.getControl.side_effect = get_control
        locked = reconcile_window_xml_skin_resolution(
            window, SKIN_RES_720P, control_ids=(3080, 3090)
        )
        self.assertEqual(locked, SKIN_RES_1080I)
        # Right-corner panel X matches 1080i after re-lock
        self.assertEqual(scale_skin_coord(840, locked), 1260)

    def test_reconcile_keeps_requested_when_widths_match(self):
        from addon_skin_resolution import (
            SKIN_RES_720P,
            reconcile_window_xml_skin_resolution,
        )

        panel = MagicMock()
        panel.getWidth.return_value = 430
        window = MagicMock()
        window.getControl.return_value = panel
        locked = reconcile_window_xml_skin_resolution(
            window, SKIN_RES_720P, control_ids=(3080,)
        )
        self.assertEqual(locked, SKIN_RES_720P)


if __name__ == "__main__":
    unittest.main()
