# -*- coding: utf-8 -*-
"""Next episode popup looks: the default, the skip dialog's own look and its presets."""

import os
import threading
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import next_episode_appearance as app
import next_episode_customize_ui as cust
import next_episode_dialog as dlg_mod
import next_episode_look as look_mod
import skip_dialog_appearance as skip_app
import skip_dialog_presets as presets

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MEDIA = os.path.join(ROOT, "resources", "skins", "default", "media")


class _Addon:
    """Just enough of xbmcaddon.Addon for the settings readers."""

    def __init__(self, **values):
        self.values = {k: ("true" if v is True else "false" if v is False else str(v))
                       for k, v in values.items()}

    def getSetting(self, key):
        return self.values.get(key, "")

    def getSettingString(self, key):
        return self.values.get(key, "")


class LookChoiceTests(unittest.TestCase):
    def test_the_presets_are_the_skip_dialogs_full_and_compact_ones(self):
        names = [n for n, v in presets.builtin_presets() if v.get("skip_dialog_mode") != "Minimal"]
        self.assertEqual(list(look_mod.PRESET_NAMES), names)

    def test_tokens_are_unique_and_survive_a_round_trip(self):
        tokens = [look_mod.preset_token(n) for n in look_mod.PRESET_NAMES]
        self.assertEqual(len(set(tokens)), len(tokens))
        for token in look_mod.LOOK_CHOICES:
            self.assertEqual(look_mod.normalize_look(token), token)
        self.assertEqual(look_mod.preset_token("Big & Bold"), "BigBold")
        self.assertEqual(look_mod.LOOK_LABELS["BigBold"], "Big & Bold")

    def test_default_comes_first_and_is_the_default(self):
        self.assertEqual(look_mod.LOOK_CHOICES[0], look_mod.LOOK_DEFAULT)
        self.assertEqual(look_mod.LOOK_CHOICES[1], look_mod.LOOK_SKIP_DIALOG)
        self.assertEqual(app.DEFAULT_DRAFT[app.KEY_LOOK], look_mod.LOOK_DEFAULT)

    def test_normalize_look_forgives_case_spaces_and_junk(self):
        self.assertEqual(look_mod.normalize_look("neon pink"), "NeonPink")
        self.assertEqual(look_mod.normalize_look(" SKIPDIALOG "), look_mod.LOOK_SKIP_DIALOG)
        for junk in (None, "", "nonsense", 7):
            self.assertEqual(look_mod.normalize_look(junk), look_mod.LOOK_DEFAULT)

    def test_the_settings_page_lists_exactly_these_choices(self):
        tree = ET.parse(os.path.join(ROOT, "resources", "settings.xml"))
        setting = [s for s in tree.getroot().iter("setting") if s.get("id") == look_mod.KEY_LOOK][0]
        options = [(o.get("label"), o.text) for o in setting.iter("option")]
        self.assertEqual(
            options, [(look_mod.LOOK_LABELS[c], c) for c in look_mod.LOOK_CHOICES]
        )
        self.assertEqual(setting.findtext("default"), look_mod.LOOK_DEFAULT)


class LookValueTests(unittest.TestCase):
    def test_the_card_colour_uses_the_skip_dialogs_maths(self):
        for pct in (0, 37, 70, 95, 100):
            settings = MagicMock()
            settings.get_int.return_value = pct
            self.assertEqual(
                look_mod.card_color(True, pct), skip_app.card_color_diffuse(settings), pct
            )

    def test_no_card_means_a_fully_transparent_one(self):
        self.assertEqual(look_mod.card_color(False, 95), "00000000")
        self.assertEqual(look_mod.card_color(True, "junk"), "F2000000")
        self.assertEqual(look_mod.card_color(True, 500), "FF000000")

    def test_every_preset_look_points_at_textures_that_exist(self):
        for name, values in presets.builtin_presets():
            if values.get("skip_dialog_mode") == "Minimal":
                continue
            found = look_mod.look_from_values(values)
            for texture in (found.focus_texture, found.bar_texture):
                self.assertTrue(os.path.isfile(os.path.join(MEDIA, texture)), (name, texture))

    def test_the_default_look_points_at_textures_that_exist(self):
        for texture in (look_mod.DEFAULT_LOOK.focus_texture, look_mod.DEFAULT_LOOK.bar_texture):
            self.assertTrue(os.path.isfile(os.path.join(MEDIA, texture)), texture)

    def test_the_focus_border_follows_the_skip_dialogs_table(self):
        self.assertEqual(look_mod.focus_border("button_focus_flat_teal.png"), look_mod.BORDER_ALL)
        self.assertEqual(look_mod.focus_border("button_focus_3d_cyan.png"), look_mod.BORDER_SIDES)
        self.assertEqual(look_mod.focus_border("button_focus.png"), look_mod.BORDER_NONE)
        for name in skip_app.BUTTON_FOCUS_NINE_SLICE_BORDERS:
            self.assertIn(look_mod.focus_border(name), (look_mod.BORDER_ALL, look_mod.BORDER_SIDES))

    def test_the_default_look_is_what_the_popup_always_showed(self):
        found = look_mod.DEFAULT_LOOK
        self.assertEqual(found.card_color, "F0000000")
        self.assertEqual(found.heading_color, "FFB0D4E8")
        self.assertIsNone(found.text_color)
        self.assertFalse(found.all_caps)
        self.assertEqual(found.focus_texture, "button_focus_flat_teal.png")
        self.assertEqual(found.bar_texture, "progress_mid_segmented_teal.png")

    def test_a_preset_look_takes_its_colour_caps_and_card(self):
        found = look_mod.resolve_look("Terminal", None)
        self.assertEqual(found.text_color, "FF39FF14")
        self.assertTrue(found.all_caps)
        self.assertEqual(found.card_color, "FF000000")
        self.assertEqual(found.focus_texture, "button_focus_bracket_green.png")
        self.assertEqual(found.bar_texture, "progress_mid_flat_green.png")

    def test_a_preset_without_a_card_has_no_card(self):
        self.assertEqual(look_mod.resolve_look("Glass", None).card_color, "00000000")

    def test_the_skip_dialog_look_follows_its_current_settings(self):
        addon = _Addon(
            skip_dialog_font_color="FFFFD54F",
            skip_dialog_all_caps=True,
            progress_bar_style="progress_mid_flat_blue.png",
            button_focus_style="button_focus_3d_orange.png",
            skip_card_enabled=True,
            skip_card_opacity=50,
        )
        found = look_mod.resolve_look(look_mod.LOOK_SKIP_DIALOG, addon)
        self.assertEqual(found.text_color, "FFFFD54F")
        self.assertTrue(found.all_caps)
        self.assertEqual(found.bar_texture, "progress_mid_flat_blue.png")
        self.assertEqual(found.focus_texture, "button_focus_3d_orange.png")
        self.assertEqual(found.focus_border, look_mod.BORDER_SIDES)
        self.assertEqual(found.card_color, "80000000")

    def test_the_skip_dialog_look_falls_back_to_its_own_defaults(self):
        found = look_mod.resolve_look(look_mod.LOOK_SKIP_DIALOG, _Addon())
        base = presets.BASE_LOOK
        self.assertEqual(found.bar_texture, base["progress_bar_style"])
        self.assertEqual(found.focus_texture, base["button_focus_style"])
        self.assertEqual(found.card_color, look_mod.card_color(True, base["skip_card_opacity"]))

    def test_anything_unusable_gives_the_default_look(self):
        self.assertIs(look_mod.resolve_look("nonsense", None), look_mod.DEFAULT_LOOK)
        self.assertIs(look_mod.resolve_look(None, None), look_mod.DEFAULT_LOOK)

        class _Broken:
            def getSetting(self, key):
                raise RuntimeError("no settings")

            getSettingString = getSetting

        found = look_mod.resolve_look(look_mod.LOOK_SKIP_DIALOG, _Broken())
        self.assertIsInstance(found, look_mod.PopupLook)


def _dialog(addon=None, look=look_mod.LOOK_DEFAULT, **kw):
    dialog = dlg_mod.NextEpisodeDialog.__new__(dlg_mod.NextEpisodeDialog)
    dialog.addon = addon
    dialog.draft = dict(app.DEFAULT_DRAFT, **{app.KEY_LOOK: look})
    dialog.window_start = 1455.0
    dialog.total = 1500.0
    dialog._look = None
    dialog._bar_tiled = True
    dialog._last_fill_w = None
    dialog._closing = False
    dialog._stop = threading.Event()
    dialog.props = {}
    dialog.setProperty = lambda k, v: dialog.props.__setitem__(k, v)
    for key, value in kw.items():
        setattr(dialog, key, value)
    return dialog


class DialogLookTests(unittest.TestCase):
    def test_the_default_look_sets_the_properties_the_popup_always_had(self):
        dialog = _dialog(_Addon(skip_dialog_font_color="FFEEEEEE"))
        dialog._apply_look()
        self.assertEqual(dialog.props["skip_dialog_text_color"], "FFEEEEEE")
        self.assertEqual(dialog.props["next_ep_card_color"], "F0000000")
        self.assertEqual(dialog.props["next_ep_heading_color"], "FFB0D4E8")
        self.assertEqual(dialog.props["next_ep_focus_texture"], "button_focus_flat_teal.png")
        self.assertEqual(dialog.props["next_ep_focus_border"], "all")
        self.assertEqual(dialog.props["next_ep_bar_tiled"], "true")
        self.assertEqual(
            dialog.props["next_ep_bar_tiled_texture"], "progress_tiled_segmented_teal_h10.png"
        )
        self.assertTrue(dialog._bar_tiled)

    def test_a_preset_brings_its_own_text_colour(self):
        dialog = _dialog(_Addon(skip_dialog_font_color="FFEEEEEE"), look="Terminal")
        dialog._apply_look()
        self.assertEqual(dialog.props["skip_dialog_text_color"], "FF39FF14")
        self.assertEqual(dialog.props["next_ep_heading_color"], "FF39FF14")

    def test_a_segmented_texture_is_tiled_and_a_flat_one_is_stretched(self):
        segments = _dialog(_Addon(), look="Segments")
        segments._apply_look()
        self.assertTrue(segments._bar_tiled)
        self.assertEqual(segments.props["next_ep_bar_tiled"], "true")
        modern = _dialog(_Addon(), look="Modern")
        modern._apply_look()
        self.assertFalse(modern._bar_tiled)
        self.assertEqual(modern.props["next_ep_bar_tiled"], "false")
        self.assertEqual(modern.props["next_ep_bar_tiled_texture"], "")
        self.assertEqual(modern.props["next_ep_bar_texture"], "progress_mid_flat_blue.png")

    def test_the_tiled_texture_height_follows_the_skin_resolution(self):
        dialog = _dialog(_Addon(), look="Segments", _skin_resolution="1080i")
        dialog._apply_look()
        self.assertEqual(
            dialog.props["next_ep_bar_tiled_texture"], "progress_tiled_segmented_teal_h15.png"
        )

    def test_upper_case_only_applies_when_the_look_asks_for_it(self):
        plain = _dialog(_Addon())
        plain._apply_look()
        self.assertEqual(plain._caps("Play now"), "Play now")
        shouting = _dialog(_Addon(), look="Terminal")
        shouting._apply_look()
        self.assertEqual(shouting._caps("Play now"), "PLAY NOW")
        self.assertEqual(_dialog(_Addon())._caps("Play now"), "Play now")

    def test_a_stretched_bar_is_sized_exactly_not_in_whole_segments(self):
        dialog = _dialog(_Addon(), look="Modern")
        dialog._apply_look()
        dialog._layout = app.popup_layout(thumbnail=False, countdown=True, progress=True)
        dialog._sc = lambda v: v
        stretched, tiled = MagicMock(), MagicMock()
        dialog._ctrl = lambda cid: {
            dlg_mod.ID_BAR_FILL_STRETCH: stretched, dlg_mod.ID_BAR_FILL: tiled
        }.get(cid)
        dialog._update_countdown(1477.5)
        stretched.setWidth.assert_called_once_with(250)
        tiled.setWidth.assert_not_called()

    def test_countdown_text_follows_upper_case(self):
        dialog = _dialog(_Addon(), look="Terminal")
        dialog._apply_look()
        dialog._layout = app.popup_layout(thumbnail=False, countdown=True, progress=False)
        dialog._update_countdown(1470.0)
        self.assertEqual(dialog.props["next_ep_countdown"], dialog.props["next_ep_countdown"].upper())
        self.assertIn("00:30", dialog.props["next_ep_countdown"])


class CustomizeLookTests(unittest.TestCase):
    def test_the_look_row_has_a_label_a_control_and_a_value_text(self):
        self.assertIn(app.KEY_LOOK, cust.ROW_IDS)
        self.assertEqual(len(set(cust.ROW_IDS.values())), len(cust.ROW_IDS))
        self.assertEqual(cust.ROW_LABEL_IDS[app.KEY_LOOK][0], 47080)
        draft = dict(app.DEFAULT_DRAFT)
        self.assertEqual(cust.value_text(None, draft, app.KEY_LOOK), "Default")
        draft[app.KEY_LOOK] = "NeonPink"
        self.assertEqual(cust.value_text(None, draft, app.KEY_LOOK), "Neon Pink")

    def test_the_look_row_sits_right_under_the_style_row(self):
        rows = app.customize_rows(app.DEFAULT_DRAFT)
        self.assertEqual(rows[:2], [app.KEY_STYLE, app.KEY_LOOK])
        self.assertNotIn(app.KEY_LOOK, app.customize_rows({app.KEY_STYLE: "Native"}))

    def test_nudging_walks_through_every_look_and_wraps(self):
        draft = dict(app.DEFAULT_DRAFT)
        seen = [draft[app.KEY_LOOK]]
        for _ in range(len(look_mod.LOOK_CHOICES) - 1):
            cust.nudge(draft, app.KEY_LOOK, 1)
            seen.append(draft[app.KEY_LOOK])
        self.assertEqual(seen, list(look_mod.LOOK_CHOICES))
        cust.nudge(draft, app.KEY_LOOK, 1)
        self.assertEqual(draft[app.KEY_LOOK], look_mod.LOOK_DEFAULT)
        cust.nudge(draft, app.KEY_LOOK, -1)
        self.assertEqual(draft[app.KEY_LOOK], look_mod.LOOK_CHOICES[-1])

    def test_saving_only_writes_the_look_when_it_changed(self):
        original = dict(app.DEFAULT_DRAFT)
        draft = dict(original)
        self.assertEqual(cust.changed_payload(draft, original), {})
        draft[app.KEY_LOOK] = "Modern"
        self.assertEqual(cust.changed_payload(draft, original), {app.KEY_LOOK: "Modern"})

    def test_a_stored_look_is_read_back_into_the_draft(self):
        addon = _Addon(**{app.KEY_LOOK: "neon pink", "next_episode_popup_style": "Custom"})
        self.assertEqual(app.load_popup_draft(addon)[app.KEY_LOOK], "NeonPink")
        self.assertEqual(app.load_popup_draft(_Addon())[app.KEY_LOOK], look_mod.LOOK_DEFAULT)


if __name__ == "__main__":
    unittest.main()
