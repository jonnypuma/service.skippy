# -*- coding: utf-8 -*-
"""Full skip-dialog texturefocus 9-slice border patching."""

import unittest
import xml.etree.ElementTree as ET

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

from service_skip_dialog_skin import _set_button_texturefocus


class TextureFocusBorderTests(unittest.TestCase):
    def test_sets_and_clears_border(self):
        control = ET.Element("control", {"type": "button", "id": "3012"})
        tf = ET.SubElement(control, "texturefocus")
        tf.text = "button_focus.png"
        _set_button_texturefocus(control, "button_focus_3d_green.png", "12,0,12,0")
        el = control.find("texturefocus")
        self.assertEqual(el.text, "button_focus_3d_green.png")
        self.assertEqual(el.get("border"), "12,0,12,0")
        _set_button_texturefocus(control, "button_focus.png", None)
        self.assertEqual(el.text, "button_focus.png")
        self.assertIsNone(el.get("border"))

    def test_creates_texturefocus_when_missing(self):
        control = ET.Element("control", {"type": "button", "id": "3013"})
        _set_button_texturefocus(control, "button_focus_gold_rectangular_3d.png", "12,0,12,0")
        el = control.find("texturefocus")
        self.assertIsNotNone(el)
        self.assertEqual(el.text, "button_focus_gold_rectangular_3d.png")
        self.assertEqual(el.get("border"), "12,0,12,0")


if __name__ == "__main__":
    unittest.main()
