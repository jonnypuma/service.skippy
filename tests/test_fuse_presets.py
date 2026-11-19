# -*- coding: utf-8 -*-
"""The Fuse presets (the looks of the skin Aeon Fuse), the card styles and the legacy labels."""
import os
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

from PIL import Image

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import next_episode_look as look_mod  # noqa: E402
import next_episode_saved_looks as saved_looks  # noqa: E402
import next_episode_view as view  # noqa: E402
import skip_dialog_appearance as appearance  # noqa: E402
import skip_dialog_card as card  # noqa: E402
import skip_dialog_customize_ui as customize  # noqa: E402
import skip_dialog_presets as sp  # noqa: E402
import skip_dialog_presets_ui as presets_ui  # noqa: E402
from tools import gen_fuse_preset_textures as textures  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SKINS = os.path.join(ROOT, "resources", "skins", "default")
MEDIA = os.path.join(SKINS, "media")
SKIP_DIALOG_FILES = (
    "SkipDialog_BottomLeft.xml", "SkipDialog_BottomRight.xml", "SkipDialog_TopLeft.xml",
    "SkipDialog_TopRight.xml", "SkipDialog.xml", "SkipDialogCustomize.xml",
)
FUSE_FULL = ("Fused Glass Dark", "Fused Glass Frost", "Fused Glass Clear", "Fused Glass style", "Aeon", "Aeon Glass")


def preset(name):
    return dict(sp.builtin_presets())[name]


def read(res, name):
    with open(os.path.join(SKINS, res, name), encoding="utf-8") as handle:
        return handle.read()


class CardStyleTests(unittest.TestCase):
    def test_flat_is_the_default_and_the_card_of_earlier_versions(self):
        self.assertEqual(card.normalize(None), card.STYLE_FLAT)
        self.assertEqual(card.normalize("junk"), card.STYLE_FLAT)
        self.assertEqual(card.texture("Flat"), "white.png")
        self.assertEqual(card.diffuse("Flat", 95), "F2000000")
        self.assertEqual(sp.BASE_LOOK["skip_card_style"], card.STYLE_FLAT)

    def test_normalize_forgives_case_and_spaces(self):
        self.assertEqual(card.normalize(" fused frost "), "FusedFrost")
        self.assertEqual(card.normalize("AEONGLASS"), "AeonGlass")

    def test_a_card_picture_keeps_its_colours_and_only_fades(self):
        for stored, _name, _picture in card.STYLES[1:]:
            self.assertEqual(card.diffuse(stored, 100), "FFFFFFFF", stored)
            self.assertEqual(card.diffuse(stored, 50), "80FFFFFF", stored)
            self.assertEqual(card.diffuse(stored, "junk"), "F2FFFFFF", stored)

    def test_every_card_picture_exists_and_holds_two_borders(self):
        self.assertEqual(len(card.picture_files()), len(card.STYLES) - 1)
        for name in card.picture_files():
            with Image.open(os.path.join(MEDIA, name)) as image:
                self.assertGreaterEqual(min(image.size), 2 * card.BORDER, name)

    def test_the_shortest_full_dialog_holds_two_borders(self):
        # 35 (bottom of the button row) + 14 below it, in 720p units
        self.assertLessEqual(2 * card.BORDER, 49)

    def test_a_round_card_leaves_room_under_the_bar(self):
        self.assertEqual(card.bottom_margin_720("Flat", 5), 5)
        self.assertEqual(card.bottom_margin_720("FusedStyle", 5), 5)
        for stored in ("Rounded", "FusedDark", "FusedFrost", "FusedClear", "AeonGlass"):
            self.assertEqual(card.bottom_margin_720(stored, 5), 10, stored)
        self.assertTrue(card.ROUND_STYLES <= {stored for stored, _name, _picture in card.STYLES})

    def test_the_textures_are_what_the_generator_draws(self):
        self.assertEqual(textures.stale(), [], "run python tools/gen_fuse_preset_textures.py")

    def test_the_settings_list_is_the_list_of_styles(self):
        root = ET.parse(os.path.join(ROOT, "resources", "settings.xml")).getroot()
        setting = next(s for s in root.iter("setting") if s.get("id") == card.SETTING_KEY)
        found = [(o.get("label"), o.text) for o in setting.iter("option")]
        self.assertEqual(found, card.options())
        self.assertEqual(setting.find("default").text, card.STYLE_FLAT)


class SkinTests(unittest.TestCase):
    def test_every_skip_dialog_has_the_picture_card_right_after_the_flat_one(self):
        for res in ("720p", "1080i"):
            for name in SKIP_DIALOG_FILES:
                text = read(res, name)
                ids = re.findall(r'<control type="image" id="(\d+)">', text)
                self.assertEqual(ids[ids.index("3081") + 1], "3084", (res, name))
                block = re.search(r'id="3084">.*?</control>', text, flags=re.S).group(0)
                self.assertIn('<texture border="%d">$INFO[Window.Property(skip_card_texture)]</texture>' % card.BORDER, block)
                self.assertIn("<visible>!String.IsEmpty(Window.Property(skip_card_texture))</visible>", block)
                flat = re.search(r'id="3081">.*?</control>', text, flags=re.S).group(0)
                self.assertIn("<texture>white.png</texture>", flat, (res, name))

    def test_the_popup_and_its_mock_have_the_picture_card_and_the_focus_text_colour(self):
        for res in ("720p", "1080i"):
            live = read(res, "NextEpisodeDialog.xml")
            mock = read(res, "NextEpisodeCustomize.xml")
            for text, cid in ((live, view.popup_ids().shaped), (mock, view.popup_ids(view.MOCK_ID_OFFSET).shaped)):
                block = re.search(r'id="%d">.*?</control>' % cid, text, flags=re.S).group(0)
                self.assertIn("Window.Property(next_ep_card_texture)", block, (res, cid))
                self.assertIn("Window.Property(next_ep_card_tint)", block, (res, cid))
            self.assertEqual(live.count("<focusedcolor>$INFO[Window.Property(next_ep_focus_text_color)]</focusedcolor>"), 2)
            self.assertEqual(mock.count("Window.Property(next_ep_mock_play_color)"), 1)
            self.assertEqual(mock.count("Window.Property(next_ep_mock_close_color)"), 1)


class DialogCardTests(unittest.TestCase):
    def test_the_dialog_diffuse_follows_the_style(self):
        flat = appearance.DictSettingsReader({"skip_card_opacity": 80})
        self.assertEqual(appearance.card_color_diffuse(flat), "CC000000")
        frost = appearance.DictSettingsReader({"skip_card_opacity": 80, "skip_card_style": "FusedFrost"})
        self.assertEqual(appearance.card_color_diffuse(frost), "CCFFFFFF")
        self.assertEqual(appearance.card_style_name(frost), "FusedFrost")

    def test_a_card_picture_stays_on_the_screen(self):
        self.assertEqual(appearance.card_top_on_screen(930, 120, 1080, 15), 930)
        self.assertEqual(appearance.card_top_on_screen(930, 159, 1080, 15), 906)
        self.assertEqual(appearance.card_top_on_screen(15, 159, 1080, 15), 15)
        self.assertEqual(appearance.card_top_on_screen(930, 2000, 1080, 15), 0)

    def test_a_button_gets_its_focused_colour_and_a_label_does_not(self):
        class Control:
            def __init__(self):
                self.kwargs = None

            def setLabel(self, label, **kwargs):
                self.kwargs = kwargs

        button, label = Control(), Control()
        appearance.set_skip_button_label(button, "Skip", "FFFFFFFF")
        appearance.set_skip_info_label(label, "Ends in", "FFFFFFFF")
        self.assertEqual(button.kwargs["focusedColor"], "0xFFFFFFFF")
        self.assertEqual(button.kwargs["textColor"], "0xFFFFFFFF")
        self.assertNotIn("focusedColor", label.kwargs)

    def test_the_new_focus_pictures_are_nine_sliced(self):
        for name in ("button_focus_fuse_square.png", "button_focus_fuse_glass.png", "button_focus_fuse_bar.png"):
            self.assertEqual(appearance.button_focus_nine_slice_border(name), "12,12,12,12", name)
            self.assertTrue(os.path.isfile(os.path.join(MEDIA, name)), name)


class PresetOrderTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        path = os.path.join(self._tmp.name, "skip_dialog_presets.json")
        patcher = patch.object(sp, "_store_path", lambda: path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)

    def test_the_fuse_presets_come_first_and_the_old_ones_are_legacy(self):
        names = [name for name, _values in sp.builtin_presets()]
        self.assertEqual(tuple(names[:6]), FUSE_FULL)
        first_legacy = names.index("Classic")
        self.assertTrue(all(not sp.is_legacy(n) for n in names[:first_legacy]))
        self.assertTrue(all(sp.is_legacy(n) for n in names[first_legacy:]))
        self.assertEqual(len(names) - first_legacy, 48)
        self.assertEqual(names[-1], "Minimal Coffee")

    def test_a_legacy_name_is_only_changed_where_it_is_shown(self):
        self.assertEqual(sp.display_name("Modern"), "Modern (legacy)")
        self.assertEqual(sp.display_name("Aeon"), "Aeon (legacy)")  # a card preset: the earlier options only
        self.assertEqual(sp.display_name("Stack card" + sp.LAYOUT_PRESET_SEP + "Aeon"), "Stack card" + sp.LAYOUT_PRESET_SEP + "Aeon")
        self.assertEqual(sp.display_name("My look"), "My look")
        self.assertIn("Modern", dict(sp.builtin_presets()))
        self.assertNotIn("Modern (legacy)", dict(sp.builtin_presets()))

    def test_a_saved_preset_cannot_take_a_built_in_name_in_either_form(self):
        for name in ("modern", "Modern (legacy)", "MODERN (LEGACY)", "aeon glass"):
            self.assertEqual(sp.save_user_preset(name, {}), (False, "builtin"), name)

    def test_saved_presets_sit_between_the_drawn_designs_and_the_card_presets(self):
        draft = {}
        sp.apply_preset(draft, preset("Modern"))
        draft["progress_bar_height"] = 9
        self.assertEqual(sp.save_user_preset("My look", draft), (True, ""))
        listed = [(name, builtin) for name, _values, builtin in sp.list_presets()]
        at = listed.index(("My look", False))
        # before it: the drawn designs; after it: the presets of the classic card, every one shown as legacy
        self.assertTrue(all(b and sp.display_name(n) == n for n, b in listed[:at]))
        self.assertTrue(all(b and sp.display_name(n).endswith(sp.LEGACY_SUFFIX) for n, b in listed[at + 1:]))
        self.assertEqual(listed[0][0], "Stack card" + sp.LAYOUT_PRESET_SEP + "Fused Glass Dark")  # the default leads
        self.assertEqual(listed[at + 1][0], "Fused Glass Dark")  # the Fuse cards, then the older ones

    def test_the_picker_and_the_preset_row_show_the_suffix(self):
        self.assertEqual(presets_ui._item_label(None, "Modern", True, None), "Modern (legacy)")
        self.assertEqual(presets_ui._item_label(None, "Aeon", True, "Aeon"), "✓ Aeon (legacy)")
        draft = {}
        sp.apply_preset(draft, preset("Modern"))
        self.assertEqual(presets_ui.preset_row_parts(None, draft), ("Preset", "Modern (legacy)"))
        sp.apply_preset(draft, preset("Fused Glass Frost"))
        self.assertEqual(presets_ui.preset_row_parts(None, draft), ("Preset", "Fused Glass Frost (legacy)"))

    def test_an_old_saved_preset_without_a_card_style_gets_the_flat_card(self):
        old = {k: v for k, v in preset("Modern").items() if k != "skip_card_style"}
        self.assertEqual(sp.sanitize_values(old)["skip_card_style"], card.STYLE_FLAT)
        self.assertEqual(sp.sanitize_values(dict(old, skip_card_style="nonsense"))["skip_card_style"], card.STYLE_FLAT)

    def test_no_legacy_preset_changed_its_look(self):
        for name, values in sp.builtin_presets():
            if sp.is_legacy(name) and values["skip_dialog_mode"] != "Minimal":
                self.assertEqual(values["skip_card_style"], card.STYLE_FLAT, name)

    def test_the_fuse_looks_use_their_own_card(self):
        self.assertEqual(preset("Fused Glass Dark")["skip_card_style"], "FusedDark")
        self.assertEqual(preset("Fused Glass Frost")["skip_card_style"], "FusedFrost")
        self.assertEqual(preset("Fused Glass Clear")["skip_card_style"], "FusedClear")
        self.assertEqual(preset("Fused Glass style")["skip_card_style"], "FusedStyle")
        self.assertEqual(preset("Aeon")["skip_card_style"], card.STYLE_FLAT)
        self.assertEqual(preset("Aeon Glass")["skip_card_style"], "AeonGlass")

    def test_the_bars_of_the_fuse_presets_are_as_high_as_the_track_picture(self):
        # Kodi's progress control scales the fill by the height of the track picture.
        with Image.open(os.path.join(MEDIA, "progress_background.png")) as track:
            track_h = track.size[1]
        for name, values in sp.builtin_presets():
            if sp.is_legacy(name) or values["skip_dialog_mode"] == "Minimal":
                continue
            with Image.open(os.path.join(MEDIA, values["progress_bar_style"])) as fill:
                self.assertEqual(fill.size[1], track_h, name)

    def test_text_on_a_white_focus_picture_is_black(self):
        white = {"button_focus_flat_white.png", "button_focus_fuse_square.png"}
        for name, values in sp.builtin_presets():
            if sp.is_legacy(name) or values["skip_dialog_mode"] == "Minimal":
                continue
            dark = look_mod.is_dark(values["skip_dialog_font_color"])
            self.assertEqual(dark, values["button_focus_style"] in white, name)


class PopupLookTests(unittest.TestCase):
    def test_the_legacy_lists_agree(self):
        legacy = [n for n, v in sp.builtin_presets() if sp.is_legacy(n) and v["skip_dialog_mode"] != "Minimal"]
        self.assertEqual(list(look_mod.LEGACY_PRESET_NAMES), legacy)
        self.assertEqual(look_mod.LEGACY_SUFFIX, sp.LEGACY_SUFFIX)
        for name in look_mod.LEGACY_PRESET_NAMES:
            self.assertEqual(look_mod.preset_label(name), sp.display_name(name), name)
        # the Fuse looks are looks of the popup of earlier versions and presets of the classic card: both
        # screens mark them as legacy, like every other one
        self.assertEqual(look_mod.preset_label("Fused Glass Dark"), "Fused Glass Dark (legacy)")
        self.assertEqual(sp.display_name("Fused Glass Dark"), "Fused Glass Dark (legacy)")

    def test_the_fuse_looks_lead_the_choices_and_legacy_tokens_stay(self):
        self.assertEqual(look_mod.LOOK_CHOICES[2], "FusedGlassDark")
        self.assertEqual(look_mod.LOOK_LABELS["FusedGlassDark"], "Fused Glass Dark (legacy)")
        self.assertEqual(look_mod.LOOK_LABELS["Modern"], "Modern (legacy)")
        self.assertEqual(look_mod.normalize_look("modern"), "Modern")

    def test_a_saved_look_cannot_take_a_built_in_name_in_either_form(self):
        taken = saved_looks.builtin_names()
        for name in ("modern", "modern (legacy)", "aeon glass"):
            self.assertIn(name, taken)

    def test_a_dark_font_colour_is_the_focus_text_and_the_card_text_stays_white(self):
        found = look_mod.resolve_look("FusedGlassFrost", None)
        self.assertEqual(found.focus_text_color, "FF000000")
        self.assertEqual((found.text_color, found.heading_color), ("FFFFFFFF", "FFFFFFFF"))
        self.assertEqual(found.card_style, "FusedFrost")
        self.assertEqual(found.card_color, "FFFFFFFF")
        legacy = look_mod.resolve_look("Modern", None)
        self.assertIsNone(legacy.focus_text_color)
        self.assertEqual(legacy.card_style, card.STYLE_FLAT)

    def test_is_dark(self):
        self.assertTrue(look_mod.is_dark("FF000000"))
        self.assertTrue(look_mod.is_dark("FF3D3D3D"))
        self.assertFalse(look_mod.is_dark("FFFFFFFF"))
        self.assertFalse(look_mod.is_dark("FFE5392F"))
        self.assertFalse(look_mod.is_dark("junk"))
        self.assertFalse(look_mod.is_dark(None))

    def test_another_focus_picture_drops_the_looks_focus_text(self):
        look = look_mod.resolve_popup_look(
            {look_mod.KEY_LOOK: "Aeon", look_mod.KEY_FOCUS_STYLE: "button_focus_flat_blue.png"}, None)
        self.assertIsNone(look.focus_text_color)
        self.assertEqual(look.text_color, "FFFFFFFF")

    def test_the_card_opacity_of_a_picture_card_fades_the_picture(self):
        look = look_mod.resolve_popup_look(
            {look_mod.KEY_LOOK: "AeonGlass", look_mod.KEY_CARD_OPACITY: "50"}, None)
        self.assertEqual(look.card_color, "80FFFFFF")

    def test_properties_of_a_picture_card(self):
        _look, _tiled, props = view.look_properties({look_mod.KEY_LOOK: "FusedGlassDark"}, None, 6, "FFFFFFFF")
        self.assertEqual(props["next_ep_card_color"], "00000000")
        self.assertEqual(props["next_ep_card_texture"], "skip_card_fgd.png")
        self.assertEqual(props["next_ep_card_tint"], "FFFFFFFF")
        self.assertEqual(props["skip_dialog_text_color"], "FFFFFFFF")
        self.assertEqual(props["next_ep_focus_text_color"], "FF000000")
        self.assertEqual(props["next_ep_button_shadow"], "00000000")

    def test_properties_of_the_flat_card_are_what_they_were(self):
        _look, _tiled, props = view.look_properties({look_mod.KEY_LOOK: "Modern"}, None, 6, "FFFFFFFF")
        self.assertEqual(props["next_ep_card_color"], look_mod.card_color(True, 70))
        self.assertEqual(props["next_ep_card_texture"], "")
        self.assertEqual(props["next_ep_focus_text_color"], props["skip_dialog_text_color"])
        self.assertEqual(props["next_ep_button_shadow"], "FF000000")

    def test_no_card_means_no_picture(self):
        _look, _tiled, props = view.look_properties({look_mod.KEY_LOOK: "AeonBare"}, None, 6, "FFFFFFFF")
        self.assertEqual(props["next_ep_card_texture"], "")
        self.assertEqual(props["next_ep_card_color"], "00000000")
        self.assertEqual(props["next_ep_focus_text_color"], "FF000000")
        self.assertEqual(props["next_ep_button_shadow"], "00000000")

    def test_the_picture_card_is_placed_like_the_flat_one(self):
        ids = view.popup_ids()
        from next_episode_appearance import popup_layout

        layout = popup_layout(thumbnail=True, countdown=True, progress=True)
        found = {p[0]: p[1:] for p in view.popup_placements(layout, ids)}
        self.assertEqual(found[ids.shaped], found[ids.backdrop])


class CustomizeCardRowTests(unittest.TestCase):
    def test_the_row_goes_from_off_through_every_style(self):
        self.assertEqual(customize.CARD_CHOICES[0], customize.CARD_OFF)
        self.assertEqual(list(customize.CARD_CHOICES[1:]), [stored for _name, stored in card.options()])

    def test_reading_and_storing_a_choice(self):
        draft = {"skip_card_enabled": True, "skip_card_style": "Rounded"}
        self.assertEqual(customize.card_choice(draft), "Rounded")
        customize.set_card_choice(draft, customize.CARD_OFF)
        self.assertEqual((draft["skip_card_enabled"], draft["skip_card_style"]), (False, "Rounded"))
        self.assertEqual(customize.card_choice(draft), customize.CARD_OFF)
        customize.set_card_choice(draft, "AeonGlass")
        self.assertEqual((draft["skip_card_enabled"], draft["skip_card_style"]), (True, "AeonGlass"))
        self.assertEqual(customize.card_choice({}), card.STYLE_FLAT)

    def test_the_draft_carries_the_card_style(self):
        self.assertIn("skip_card_style", customize.DRAFT_TEXT_KEYS)
        self.assertEqual(customize._TEXT_DEFAULTS["skip_card_style"], card.STYLE_FLAT)

    def test_the_new_textures_are_in_the_customize_lists(self):
        focus = dict(customize.BUTTON_FOCUS)
        self.assertEqual(focus["Fuse Square"], "button_focus_fuse_square.png")
        self.assertEqual(dict(customize.PROGRESS_STYLES)["Fuse Gold"], "progress_mid_fuse_gold.png")
        self.assertEqual(dict(customize.PROGRESS_STYLES)["Fuse White"], "progress_mid_fuse_white.png")
        plates = dict(customize.MINIMAL_PLATES)
        for key in ("Dark", "Frost", "Clear", "Square", "Grid", "Glass"):
            name = plates["Fuse %s" % key]
            self.assertTrue(os.path.isfile(os.path.join(MEDIA, name)), name)
            stem = os.path.splitext(name)[0]
            for width in appearance.MINIMAL_PLATE_WIDTHS_720:
                self.assertTrue(os.path.isfile(os.path.join(MEDIA, "plates", "%s_w%d.png" % (stem, width))), (name, width))


if __name__ == "__main__":
    unittest.main()
