# -*- coding: utf-8 -*-
"""The twelve looks of their own (Neon ... VHS) for the skip dialog layouts and the popup layouts."""
import os
import unittest

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import next_layouts as nl  # noqa: E402
import skip_dialog_presets as sp  # noqa: E402
import skip_layouts as sl  # noqa: E402
from tools import gen_skip_layouts as gen  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MEDIA = os.path.join(ROOT, "resources", "skins", "default", "media")


def luma(argb) -> float:
    r, g, b = (int(argb[i:i + 2], 16) for i in (2, 4, 6))
    return 0.299 * r + 0.587 * g + 0.114 * b


class OwnLookTests(unittest.TestCase):
    def test_there_are_twelve_after_the_six_of_the_skin(self):
        self.assertEqual(len(sl.FUSE_LOOKS), 6)
        self.assertEqual(sl.OWN_LOOKS, ("neon", "paper", "sunset", "ocean", "brutal", "term", "line", "luxe",
                                        "pastel", "gloss", "mono", "vhs"))
        self.assertEqual(sl.LOOKS, sl.FUSE_LOOKS + sl.OWN_LOOKS)
        self.assertEqual(sl.DEFAULT_LOOK, "fgf")

    def test_names_and_codes_are_read_back(self):
        for code, name in sl.LOOK_NAMES:
            self.assertEqual(sl.normalize_look(code), code)
            self.assertEqual(sl.normalize_look(name), code)
        self.assertEqual(sl.normalize_look("paper_o"), sl.DEFAULT_LOOK)  # a twin is not a choice

    def test_every_picture_exists_and_is_painted(self):
        self.assertEqual(set(gen.OWN) - set(sl.OWN_LOOKS), {"paper_o", "brutal_o", "pastel_o"})
        for code in sl.OWN_LOOKS:
            for bare in (False, True):
                for res in ("720p", "1080i"):
                    for name, value in sl.properties(code, res, bare).items():
                        if value.endswith(".png"):
                            self.assertTrue(os.path.isfile(os.path.join(MEDIA, value)), (code, name, value))

    def test_a_light_plate_has_a_twin_for_the_video(self):
        for code in ("paper", "brutal", "pastel"):
            self.assertLess(luma(sl.look(code).text), 90, code)  # dark ink on the plate
            self.assertGreater(luma(sl.look(code, True).text), 170, code)  # light on the video
            self.assertEqual(sl.variant(code, True), code + sl.OPEN)
            plate = sl.properties(code, "1080i", True)["skl_plate"]
            self.assertEqual(plate, "sl_%s_plate.png" % code)
            self.assertNotEqual(sl.properties(code, "1080i", True)["skl_button"], sl.properties(code)["skl_button"])
        for code in sl.LOOKS:
            if code not in ("paper", "brutal", "pastel"):
                self.assertEqual(sl.variant(code, True), code)
                self.assertGreater(luma(sl.look(code).text), 170, code)

    def test_text_on_a_picture_is_light_in_every_look(self):
        for code in sl.LOOKS:
            self.assertGreater(luma(sl.properties(code)["skl_pic_text"]), 170, code)

    def test_focus_text_differs_from_the_focus_plate(self):
        from PIL import Image

        for code in sl.OWN_LOOKS:
            for bare in (False, True):
                props = sl.properties(code, "1080i", bare)
                with Image.open(os.path.join(MEDIA, props["skl_focus"])) as picture:
                    r, g, b, a = picture.convert("RGBA").getpixel((picture.width // 2, picture.height // 2))
                self.assertGreater(a, 200, code)
                plate = 0.299 * r + 0.587 * g + 0.114 * b
                self.assertGreater(abs(plate - luma(props["skl_focus_text"])), 90, (code, bare))

    def test_which_layouts_are_bare(self):
        self.assertEqual(sl.BARE_LAYOUTS, ("Dial", "Band", "Float"))
        self.assertTrue(sl.is_bare("Float"))
        self.assertFalse(sl.is_bare("Slab"))
        self.assertEqual(nl.BARE_LAYOUTS, ("Ring", "Band", "Float", "Takeover"))

    def test_presets_of_own_looks_keep_their_own_bar(self):
        presets = dict(sp.layout_presets())
        self.assertEqual(len(presets), len(sl.NEW_LAYOUTS) * 18)
        self.assertEqual(presets["Dial" + sp.LAYOUT_PRESET_SEP + "Neon"][sl.KEY_BAR_COLOR], sl.BAR_LOOK)
        self.assertEqual(presets["Dial" + sp.LAYOUT_PRESET_SEP + "Aeon"][sl.KEY_BAR_COLOR], sl.BAR_TYPE)
        for name, values in presets.items():
            draft = {}
            sp.apply_preset(draft, values)
            self.assertEqual(sp.detect_preset(draft), name)

    def test_the_accent_follows_the_twin(self):
        self.assertEqual(sl.accent("brutal", sl.BAR_LOOK, "E8B04B"), "FF000000")
        self.assertEqual(sl.accent("brutal", sl.BAR_LOOK, "E8B04B", True), "FFFFDE21")
        self.assertEqual(sl.accent("brutal", sl.BAR_TYPE, "E8B04B", True), "FFE8B04B")


if __name__ == "__main__":
    unittest.main()
