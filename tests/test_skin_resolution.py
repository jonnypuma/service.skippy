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

    def test_probe_ids_match_xml_kind(self):
        from addon_skin_resolution import (
            EDITOR_LIST_PROBE_ID,
            FULL_SKIP_PROBE_ID,
            MINIMAL_SKIP_PROBE_ID,
            SEGMENT_TYPES_LIST_PROBE_ID,
            probe_control_ids_for_xml,
        )

        self.assertEqual(
            probe_control_ids_for_xml("SkipDialog_BottomRight.xml"),
            (FULL_SKIP_PROBE_ID,),
        )
        self.assertEqual(
            probe_control_ids_for_xml("SkipDialogCustomize.xml"),
            (FULL_SKIP_PROBE_ID,),
        )
        self.assertEqual(
            probe_control_ids_for_xml("Minimal_Skip_Dialog_BottomRight.xml"),
            (MINIMAL_SKIP_PROBE_ID,),
        )
        self.assertEqual(
            probe_control_ids_for_xml("SegmentEditorDialog.xml"),
            (EDITOR_LIST_PROBE_ID,),
        )
        self.assertEqual(
            probe_control_ids_for_xml("SegmentTypesEditor.xml"),
            (SEGMENT_TYPES_LIST_PROBE_ID,),
        )
        self.assertEqual(probe_control_ids_for_xml("other.xml"), ())

    def test_reconcile_relocks_when_kodi_loaded_1080i(self):
        from addon_skin_resolution import (
            FULL_SKIP_PROBE_ID,
            SKIN_RES_1080I,
            SKIN_RES_720P,
            reconcile_window_xml_skin_resolution,
            scale_skin_coord,
        )

        panel = MagicMock()
        panel.getWidth.return_value = 645
        window = MagicMock()

        def get_control(cid):
            if int(cid) == FULL_SKIP_PROBE_ID:
                return panel
            raise Exception("missing")

        window.getControl.side_effect = get_control
        locked = reconcile_window_xml_skin_resolution(
            window, SKIN_RES_720P, control_ids=(FULL_SKIP_PROBE_ID,)
        )
        self.assertEqual(locked, SKIN_RES_1080I)
        # Right-corner panel X matches 1080i after re-lock
        self.assertEqual(scale_skin_coord(840, locked), 1260)

    def test_reconcile_keeps_requested_when_widths_match(self):
        from addon_skin_resolution import (
            FULL_SKIP_PROBE_ID,
            SKIN_RES_720P,
            reconcile_window_xml_skin_resolution,
        )

        panel = MagicMock()
        panel.getWidth.return_value = 430
        window = MagicMock()
        window.getControl.return_value = panel
        locked = reconcile_window_xml_skin_resolution(
            window, SKIN_RES_720P, control_ids=(FULL_SKIP_PROBE_ID,)
        )
        self.assertEqual(locked, SKIN_RES_720P)

    def test_reconcile_without_ids_does_not_call_get_control(self):
        from addon_skin_resolution import (
            SKIN_RES_720P,
            reconcile_window_xml_skin_resolution,
        )

        window = MagicMock()
        locked = reconcile_window_xml_skin_resolution(window, SKIN_RES_720P)
        self.assertEqual(locked, SKIN_RES_720P)
        window.getControl.assert_not_called()

    @patch("addon_skin_resolution.xbmcgui")
    def test_init_typeerror_fallback_keeps_heuristic_res(self, mock_gui):
        mock_gui.getScreenWidth.return_value = 1902
        mock_gui.getScreenHeight.return_value = 973
        from addon_skin_resolution import SKIN_RES_1080I, init_window_xml_dialog

        calls = []

        class FakeSuper:
            def __init__(self, *args):
                calls.append(args)
                if len(args) == 4:
                    raise TypeError("no defaultRes")

        proxy = FakeSuper.__new__(FakeSuper)
        out = init_window_xml_dialog(
            proxy, ("SkipDialog_BottomRight.xml", "/addon", "default")
        )
        self.assertEqual(out, SKIN_RES_1080I)
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(calls[0]), 4)
        self.assertEqual(calls[1], ("SkipDialog_BottomRight.xml", "/addon", "default"))

    def test_editor_720p_xml_uses_1280_canvas(self):
        import os

        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        path = os.path.join(
            root, "resources", "skins", "default", "720p", "SegmentEditorDialog.xml"
        )
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        coord = text.split("</coordinates>", 1)[0]
        self.assertIn("<width>1280</width>", coord)
        self.assertIn("<height>720</height>", coord)
        self.assertNotIn("<width>1920</width>", text)
        overlay = text.split("<control type=\"image\">", 1)[1]
        overlay = overlay.split("</control>", 1)[0]
        self.assertIn("<width>1280</width>", overlay)
        self.assertIn("<height>720</height>", overlay)


if __name__ == "__main__":
    unittest.main()
