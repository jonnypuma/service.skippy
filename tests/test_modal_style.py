# -*- coding: utf-8 -*-
"""The look of Skippy's own windows: the Window style setting, its textures and the per-look XML copies."""
import os
import re
import unittest
import xml.etree.ElementTree as ET

import segment_editor_layout as editor_layout
import skippy_modal_style as style
from tools import gen_modal_style_textures as textures
from tools import gen_modal_style_variants as variants

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SKINS = os.path.join(ROOT, "resources", "skins", "default")
MEDIA = os.path.join(SKINS, "media")


class FakeAddon:
    def __init__(self, value):
        self.value = value

    def getSetting(self, key):
        assert key == style.SETTING_KEY
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


class FakeWindow:
    def __init__(self, fail=False):
        self.props = {}
        self.fail = fail

    def setProperty(self, name, value):
        if self.fail:
            raise RuntimeError("window is gone")
        self.props[name] = value


class StyleChoiceTests(unittest.TestCase):
    def test_five_looks_and_frost_is_the_default(self):
        self.assertEqual(list(style.STYLE_CODES), ["fg_dark", "fg_frost", "fg_clear", "aeon", "aeon_glass"])
        self.assertEqual(style.DEFAULT_STYLE, "fg_frost")
        self.assertEqual(style.STYLE_NAMES["fg_frost"], "Fused Glass - Frost")
        self.assertEqual(set(style.STYLE_NAMES), set(style.STYLE_CODES))

    def test_the_setting_is_read_and_anything_else_is_the_default(self):
        self.assertEqual(style.current_style(FakeAddon("aeon_glass")), "aeon_glass")
        self.assertEqual(style.current_style(FakeAddon(" Aeon ")), "aeon")
        for bad in ("", None, "glass", "fgd", 3):
            self.assertEqual(style.current_style(FakeAddon(bad)), "fg_frost", bad)
        self.assertEqual(style.current_style(FakeAddon(RuntimeError("no settings"))), "fg_frost")

    def test_the_settings_file_offers_the_five_looks_in_order(self):
        root = ET.parse(os.path.join(ROOT, "resources", "settings.xml")).getroot()
        setting = [s for s in root.iter("setting") if s.get("id") == style.SETTING_KEY][0]
        self.assertEqual(setting.findtext("default"), style.DEFAULT_STYLE)
        options = setting.find("constraints").find("options").findall("option")
        self.assertEqual([o.text for o in options], list(style.STYLE_CODES))
        self.assertEqual([o.get("label") for o in options], [style.STYLE_NAMES[k] for k in style.STYLE_CODES])


class FileNameTests(unittest.TestCase):
    def test_the_default_look_keeps_the_file_name(self):
        for base in style.STYLED_WINDOWS:
            self.assertEqual(style.xml_name(base, "fg_frost"), base)
            self.assertEqual(style.xml_name(base, addon=FakeAddon("")), base)

    def test_the_other_looks_get_their_code_before_the_extension(self):
        self.assertEqual(style.xml_name("SkippyPanel.xml", "fg_dark"), "SkippyPanel_fgd.xml")
        self.assertEqual(style.xml_name("SkippyPanel.xml", "fg_clear"), "SkippyPanel_fgc.xml")
        self.assertEqual(style.xml_name("SegmentEditorDialog.xml", addon=FakeAddon("aeon")), "SegmentEditorDialog_aeo.xml")
        self.assertEqual(style.xml_name("SourcePicker.xml", "aeon_glass"), "SourcePicker_agl.xml")

    def test_windows_without_copies_are_left_alone(self):
        for name in ("SkipDialog.xml", "NextEpisodeDialog.xml", "Minimal_Skip_Dialog_TopLeft.xml"):
            self.assertEqual(style.xml_name(name, "aeon"), name)

    def test_every_styled_window_is_opened_through_xml_name(self):
        openers = {
            "SegmentEditorDialog.xml": "segment_editor_session.py",
            "SegmentMarkerTypePicker.xml": "segment_marker.py",
            "SegmentTypesEditor.xml": "segment_types_editor_ui.py",
            "SourcePicker.xml": "skip_source_picker_ui.py",
            "SkippyPanel.xml": "skippy_panel_ui.py",
            "SkipDialogCustomize.xml": "skip_dialog_customize_ui.py",
            "NextEpisodeCustomize.xml": "next_episode_customize_ui.py",
        }
        for base, module in openers.items():
            with open(os.path.join(ROOT, module), encoding="utf-8") as handle:
                source = handle.read()
            self.assertIn("skippy_modal_style.xml_name(", source, module)
            if module != "segment_editor_session.py":  # its window class lives in segment_editor_dialog.py
                self.assertIn("skippy_modal_style.apply(self", source, module)  # with or without a named look
            self.assertNotRegex(source, r'\(\s*"%s"\s*,\s*(addon\.getAddonInfo|path)' % re.escape(base), module)
        with open(os.path.join(ROOT, "segment_editor_dialog.py"), encoding="utf-8") as handle:
            self.assertIn("skippy_modal_style.apply(self, style=self._style)", handle.read())  # a layout may fix its look


class PropertyTests(unittest.TestCase):
    def test_every_look_sets_the_same_properties(self):
        keys = None
        for key in style.STYLE_CODES:
            props = style.properties(key)
            self.assertEqual(props["ms_style"], key)
            for name in style.COLOR_KEYS:
                self.assertRegex(props[name], r"^[0-9A-F]{8}$", (key, name))
            for part in style.TEXTURE_PARTS:
                self.assertEqual(props["ms_tex_%s" % part], style.texture(part, key))
            keys = keys or set(props)
            self.assertEqual(set(props), keys, key)

    def test_text_on_a_white_focus_row_is_dark_and_on_the_glass_row_white(self):
        for key in ("fg_dark", "fg_frost", "fg_clear", "aeon"):
            self.assertLess(int(style.color("ms_text_focus", key)[2:4], 16), 0x40, key)
        self.assertEqual(style.color("ms_text_focus", "aeon_glass"), "FFFFFFFF")

    def test_apply_sets_every_property_and_survives_a_dead_window(self):
        window = FakeWindow()
        self.assertEqual(style.apply(window, addon=FakeAddon("fg_clear")), "fg_clear")
        self.assertEqual(window.props, style.properties("fg_clear"))
        self.assertEqual(style.apply(FakeWindow(fail=True), "aeon"), "aeon")

    def test_unknown_texture_part_is_an_error(self):
        with self.assertRaises(ValueError):
            style.texture("corner", "aeon")


class TextureTests(unittest.TestCase):
    def test_every_look_has_its_four_textures(self):
        for key, code in style.STYLE_CODES.items():
            for part in style.TEXTURE_PARTS:
                name = style.texture(part, key)
                self.assertEqual(name, "ms_%s_%s.png" % (code, part))
                self.assertTrue(os.path.isfile(os.path.join(MEDIA, name)), name)

    def test_the_generator_draws_exactly_those_and_corners_fit_the_borders(self):
        built = textures.build()
        wanted = {style.texture(part, key) for key in style.STYLE_CODES for part in style.TEXTURE_PARTS}
        wanted |= {"seg_%s.png" % key for key in editor_layout.CHIP_COLORS}  # the segment type chips
        wanted.add("seg_frame.png")  # the frame round the highlighted segment on the timeline
        wanted |= {"segb_%s.png" % key for key in editor_layout.CHIP_COLORS}  # the rounded blocks of the timeline
        wanted |= {"seg_tag.png", "seg_flat.png", "seg_head.png"}  # a flat chip, a flat fill, the playhead's marker
        self.assertEqual(set(built), wanted)
        for code, look in textures.LOOKS.items():
            self.assertLessEqual(look["r"], style.PANEL_BORDER, code)
            self.assertLessEqual(look["ri"], style.ROW_BORDER, code)
            panel = built["ms_%s_panel.png" % code]
            self.assertGreaterEqual(min(panel.size), 2 * style.PANEL_BORDER + 1, code)
            self.assertGreaterEqual(min(built["ms_%s_row.png" % code].size), 2 * style.ROW_BORDER + 1, code)
            self.assertEqual(built["ms_%s_dim.png" % code].getpixel((3, 3)), look["dim"], code)

    def test_square_looks_have_filled_corners_and_round_looks_do_not(self):
        built = textures.build()
        self.assertGreater(built["ms_aeo_panel.png"].getpixel((0, 0))[3], 200)
        for code in ("fgd", "fgf", "fgc", "agl"):
            self.assertEqual(built["ms_%s_panel.png" % code].getpixel((0, 0))[3], 0, code)
            self.assertEqual(built["ms_%s_focus.png" % code].getpixel((0, 0))[3], 0, code)


class SkinFileTests(unittest.TestCase):
    def test_base_files_use_the_frost_textures_with_the_right_borders(self):
        for res in variants.RESOLUTIONS:
            for base in style.STYLED_WINDOWS:
                with open(os.path.join(SKINS, res, base), encoding="utf-8") as handle:
                    text = handle.read()
                self.assertIn("ms_fgf_panel.png", text, (res, base))
                for border, part in re.findall(r'border="([^"]*)">ms_fgf_(\w+)\.png', text):
                    expected = {"panel": style.PANEL_BORDER, "dim": 0}.get(part, style.ROW_BORDER)
                    self.assertEqual(border, str(expected), (res, base, part))
                self.assertEqual(len(re.findall(r"ms_fgf_\w+\.png", text)), len(re.findall(r'border="\d+">ms_fgf_', text)), (res, base))
                for code in style.STYLE_CODES.values():
                    if code != style.DEFAULT_CODE:
                        self.assertNotIn("ms_%s_" % code, text, (res, base))

    def test_the_copies_are_up_to_date(self):
        self.assertEqual(variants.stale(), [], "run python3 tools/gen_modal_style_variants.py")

    def test_a_copy_differs_only_in_the_texture_prefix(self):
        with open(os.path.join(SKINS, "720p", "SkippyPanel.xml"), encoding="utf-8") as handle:
            base = handle.read()
        with open(os.path.join(SKINS, "720p", "SkippyPanel_aeo.xml"), encoding="utf-8") as handle:
            copy = handle.read()
        self.assertNotIn("ms_fgf_", copy)
        self.assertEqual(copy.replace("ms_aeo_", "ms_fgf_"), base)

    def test_colours_come_from_the_window_properties_this_module_sets(self):
        known = set(style.properties("fg_frost"))
        for res in variants.RESOLUTIONS:
            for base in style.STYLED_WINDOWS:
                with open(os.path.join(SKINS, res, base), encoding="utf-8") as handle:
                    used = set(re.findall(r"Window\.Property\((ms_\w+)\)", handle.read()))
                self.assertTrue(used, (res, base))
                self.assertLessEqual(used, known, (res, base))

    def test_buttons_take_no_texture_from_a_property(self):
        # Kodi does not draw a button's focus texture when it comes from $INFO / $VAR.
        for res in variants.RESOLUTIONS:
            for base in style.STYLED_WINDOWS:
                with open(os.path.join(SKINS, res, base), encoding="utf-8") as handle:
                    text = handle.read()
                self.assertNotRegex(text, r"<texture(no)?focus[^>]*>\s*\$", (res, base))


if __name__ == "__main__":
    unittest.main()
