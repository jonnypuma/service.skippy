# -*- coding: utf-8 -*-
"""Skip dialog font colour resolution and setLabel helpers."""

import unittest
from unittest.mock import MagicMock

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

from skipdialog import (
    _set_skip_button_label,
    _shadow_for_text,
    _skip_dialog_font_color_argb,
)
from skip_dialog_window_ui import _argb_to_kodi


class SkipDialogFontColorTests(unittest.TestCase):
    def test_white_hex_resolves(self):
        addon = MagicMock()
        with unittest.mock.patch(
            "skipdialog.addon_get_setting_text", return_value="FFFFFFFF"
        ):
            self.assertEqual(_skip_dialog_font_color_argb(addon), "FFFFFFFF")

    def test_white_label_resolves(self):
        addon = MagicMock()
        with unittest.mock.patch(
            "skipdialog.addon_get_setting_text", return_value="White"
        ):
            self.assertEqual(_skip_dialog_font_color_argb(addon), "FFFFFFFF")

    def test_white_index_resolves(self):
        addon = MagicMock()
        with unittest.mock.patch("skipdialog.addon_get_setting_text", return_value="0"):
            self.assertEqual(_skip_dialog_font_color_argb(addon), "FFFFFFFF")

    def test_argb_to_kodi_white(self):
        self.assertEqual(_argb_to_kodi("FFFFFFFF"), "0xFFFFFFFF")

    def test_shadow_for_white_text_is_dark(self):
        self.assertEqual(_shadow_for_text("FFFFFFFF"), "0xFF000000")

    def test_set_skip_button_label_passes_white(self):
        ctrl = MagicMock()
        _set_skip_button_label(ctrl, "Skip Recap", "FFFFFFFF", font="font16")
        ctrl.setLabel.assert_called_once()
        kw = ctrl.setLabel.call_args[1]
        if kw:
            self.assertEqual(kw.get("textColor"), "0xFFFFFFFF")
            self.assertEqual(kw.get("focusedColor"), "0xFFFFFFFF")
        else:
            args = ctrl.setLabel.call_args[0]
            self.assertEqual(args[0], "Skip Recap")
            self.assertEqual(args[2], "0xFFFFFFFF")


if __name__ == "__main__":
    unittest.main()
