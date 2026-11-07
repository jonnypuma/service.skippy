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


class OverrideChoiceTests(unittest.TestCase):
    def test_the_choice_lists_are_the_skip_dialogs_own(self):
        import skip_dialog_customize_ui as skip_ui

        self.assertEqual(look_mod.COLOR_PAIRS, tuple(skip_ui.FONT_COLORS))
        self.assertEqual(look_mod.FOCUS_PAIRS, tuple(skip_ui.BUTTON_FOCUS))
        self.assertEqual(look_mod.BAR_PAIRS, tuple(skip_ui.PROGRESS_STYLES))

    def test_every_override_starts_with_same_as_look(self):
        for key in look_mod.OVERRIDE_KEYS:
            pairs = look_mod.override_pairs(key)
            self.assertEqual(pairs[0], (look_mod.FOLLOW_LOOK_LABEL, look_mod.FOLLOW_LOOK), key)
            self.assertEqual(look_mod.override_options(key)[0], look_mod.FOLLOW_LOOK)
            values = [value for _label, value in pairs]
            self.assertEqual(len(set(values)), len(values), key)

    def test_the_stored_values_are_plain_ascii_without_spaces(self):
        for key in look_mod.OVERRIDE_KEYS:
            for value in look_mod.override_options(key):
                self.assertTrue(value.isascii() and " " not in value, (key, value))

    def test_every_texture_choice_points_at_a_file_that_exists(self):
        for key in (look_mod.KEY_FOCUS_STYLE, look_mod.KEY_BAR_STYLE):
            for value in look_mod.override_options(key)[1:]:
                self.assertTrue(os.path.isfile(os.path.join(MEDIA, value)), (key, value))
        for key in (look_mod.KEY_TEXT_COLOR, look_mod.KEY_HEADING_COLOR):
            for value in look_mod.override_options(key)[1:]:
                if value.endswith(".png"):
                    self.assertTrue(os.path.isfile(os.path.join(MEDIA, value)), (key, value))

    def test_the_opacity_choices_run_from_nothing_to_solid_in_fives(self):
        values = look_mod.override_options(look_mod.KEY_CARD_OPACITY)[1:]
        self.assertEqual(values, tuple(str(n) for n in range(0, 101, 5)))

    def test_normalize_override_accepts_case_and_falls_back_to_the_look(self):
        key = look_mod.KEY_FOCUS_STYLE
        self.assertEqual(
            look_mod.normalize_override(key, "BUTTON_FOCUS_FLAT_TEAL.PNG"), "button_focus_flat_teal.png"
        )
        self.assertEqual(look_mod.normalize_override(look_mod.KEY_ALL_CAPS, " on "), look_mod.CAPS_ON)
        self.assertEqual(look_mod.normalize_override(look_mod.KEY_CARD_OPACITY, "40"), "40")
        for junk in (None, "", "nonsense", 7, "150"):
            self.assertEqual(look_mod.normalize_override(key, junk), look_mod.FOLLOW_LOOK, junk)
        self.assertEqual(look_mod.normalize_override(look_mod.KEY_CARD_OPACITY, "150"), look_mod.FOLLOW_LOOK)

    def test_override_label_names_a_stored_choice(self):
        self.assertEqual(look_mod.override_label(look_mod.KEY_TEXT_COLOR, "FF1976D2"), "Blue")
        self.assertEqual(
            look_mod.override_label(look_mod.KEY_FOCUS_STYLE, look_mod.FOLLOW_LOOK), "Same as look"
        )
        self.assertEqual(look_mod.override_label(look_mod.KEY_CARD_OPACITY, "35"), "35%")


class OverrideLookTests(unittest.TestCase):
    base = look_mod.DEFAULT_LOOK

    def over(self, **values):
        return look_mod.look_with_overrides(self.base, values)

    def test_nothing_chosen_leaves_the_look_untouched(self):
        self.assertIs(look_mod.look_with_overrides(self.base, None), self.base)
        self.assertIs(look_mod.look_with_overrides(self.base, {}), self.base)
        everything_follows = {key: look_mod.FOLLOW_LOOK for key in look_mod.OVERRIDE_KEYS}
        self.assertIs(look_mod.look_with_overrides(self.base, everything_follows), self.base)

    def test_a_text_colour_replaces_the_follow_the_skip_dialog_default(self):
        found = self.over(**{look_mod.KEY_TEXT_COLOR: "FF1976D2"})
        self.assertEqual(found.text_color, "FF1976D2")
        self.assertEqual(found.heading_color, self.base.heading_color)

    def test_a_heading_colour_only_changes_the_heading(self):
        found = self.over(**{look_mod.KEY_HEADING_COLOR: "FFFFFFFF"})
        self.assertEqual(found.heading_color, "FFFFFFFF")
        self.assertEqual(found.text_color, self.base.text_color)

    def test_upper_case_can_be_forced_either_way(self):
        shouting = look_mod.resolve_look("Terminal", None)
        self.assertTrue(shouting.all_caps)
        self.assertFalse(look_mod.look_with_overrides(shouting, {look_mod.KEY_ALL_CAPS: "Off"}).all_caps)
        self.assertTrue(self.over(**{look_mod.KEY_ALL_CAPS: "On"}).all_caps)
        self.assertTrue(look_mod.look_with_overrides(shouting, {look_mod.KEY_ALL_CAPS: "Look"}).all_caps)

    def test_a_focus_texture_brings_the_matching_border(self):
        flat = self.over(**{look_mod.KEY_FOCUS_STYLE: "button_focus_flat_teal.png"})
        self.assertEqual(flat.focus_border, look_mod.BORDER_ALL)
        three_d = self.over(**{look_mod.KEY_FOCUS_STYLE: "button_focus_3d_cyan.png"})
        self.assertEqual(three_d.focus_texture, "button_focus_3d_cyan.png")
        self.assertEqual(three_d.focus_border, look_mod.BORDER_SIDES)
        plain = self.over(**{look_mod.KEY_FOCUS_STYLE: "button_focus.png"})
        self.assertEqual(plain.focus_border, look_mod.BORDER_NONE)

    def test_every_focus_choice_gets_a_known_border(self):
        for value in look_mod.override_options(look_mod.KEY_FOCUS_STYLE)[1:]:
            found = self.over(**{look_mod.KEY_FOCUS_STYLE: value})
            self.assertEqual(found.focus_texture, value)
            self.assertIn(
                found.focus_border, (look_mod.BORDER_ALL, look_mod.BORDER_SIDES, look_mod.BORDER_NONE), value
            )

    def test_a_bar_texture_replaces_the_looks_bar(self):
        found = self.over(**{look_mod.KEY_BAR_STYLE: "progress_mid_flat_blue.png"})
        self.assertEqual(found.bar_texture, "progress_mid_flat_blue.png")
        self.assertEqual(found.focus_texture, self.base.focus_texture)

    def test_card_opacity_uses_the_skip_dialogs_maths(self):
        for pct in (5, 35, 70, 100):
            found = self.over(**{look_mod.KEY_CARD_OPACITY: str(pct)})
            self.assertEqual(found.card_color, look_mod.card_color(True, pct), pct)

    def test_zero_percent_means_no_card_at_all(self):
        self.assertEqual(self.over(**{look_mod.KEY_CARD_OPACITY: "0"}).card_color, "00000000")

    def test_a_card_can_be_added_to_a_look_without_one(self):
        glass = look_mod.resolve_look("Glass", None)
        self.assertEqual(glass.card_color, "00000000")
        found = look_mod.look_with_overrides(glass, {look_mod.KEY_CARD_OPACITY: "60"})
        self.assertEqual(found.card_color, look_mod.card_color(True, 60))

    def test_unusable_values_change_nothing(self):
        junk = {key: "nonsense" for key in look_mod.OVERRIDE_KEYS}
        self.assertIs(look_mod.look_with_overrides(self.base, junk), self.base)

    def test_overrides_never_change_the_look_they_were_applied_to(self):
        self.over(**{look_mod.KEY_BAR_STYLE: "progress_mid_flat_blue.png"})
        self.assertEqual(self.base.bar_texture, "progress_mid_segmented_teal.png")

    def test_resolve_popup_look_puts_the_choices_on_top_of_the_chosen_look(self):
        values = {
            look_mod.KEY_LOOK: "Terminal",
            look_mod.KEY_TEXT_COLOR: "FF1976D2",
            look_mod.KEY_ALL_CAPS: "Off",
        }
        found = look_mod.resolve_popup_look(values, None)
        terminal = look_mod.resolve_look("Terminal", None)
        self.assertEqual(found.text_color, "FF1976D2")
        self.assertFalse(found.all_caps)
        self.assertEqual(found.bar_texture, terminal.bar_texture)
        self.assertEqual(found.card_color, terminal.card_color)

    def test_resolve_popup_look_copes_with_missing_values(self):
        self.assertEqual(look_mod.resolve_popup_look(None, None), look_mod.DEFAULT_LOOK)
        self.assertEqual(look_mod.resolve_popup_look({}, None), look_mod.DEFAULT_LOOK)

    def test_following_the_skip_dialog_still_takes_the_choices_on_top(self):
        addon = _Addon(skip_dialog_font_color="FFFFD54F", progress_bar_style="progress_mid_flat_blue.png")
        values = {look_mod.KEY_LOOK: look_mod.LOOK_SKIP_DIALOG, look_mod.KEY_BAR_STYLE: "progress_mid_flat_rose.png"}
        found = look_mod.resolve_popup_look(values, addon)
        self.assertEqual(found.text_color, "FFFFD54F")
        self.assertEqual(found.bar_texture, "progress_mid_flat_rose.png")


class OverrideDialogTests(unittest.TestCase):
    def test_the_dialog_draws_with_the_chosen_overrides(self):
        dialog = _dialog(_Addon(skip_dialog_font_color="FFEEEEEE"))
        dialog.draft.update(
            {
                look_mod.KEY_TEXT_COLOR: "FF1976D2",
                look_mod.KEY_HEADING_COLOR: "FFFFFFFF",
                look_mod.KEY_ALL_CAPS: "On",
                look_mod.KEY_FOCUS_STYLE: "button_focus_3d_cyan.png",
                look_mod.KEY_BAR_STYLE: "progress_mid_flat_blue.png",
                look_mod.KEY_CARD_OPACITY: "50",
            }
        )
        dialog._apply_look()
        self.assertEqual(dialog.props["skip_dialog_text_color"], "FF1976D2")
        self.assertEqual(dialog.props["next_ep_heading_color"], "FFFFFFFF")
        self.assertEqual(dialog.props["next_ep_focus_texture"], "button_focus_3d_cyan.png")
        self.assertEqual(dialog.props["next_ep_focus_border"], "sides")
        self.assertEqual(dialog.props["next_ep_bar_texture"], "progress_mid_flat_blue.png")
        self.assertEqual(dialog.props["next_ep_card_color"], look_mod.card_color(True, 50))
        self.assertEqual(dialog._caps("Play now"), "PLAY NOW")

    def test_a_flat_bar_choice_switches_the_bar_to_stretched(self):
        dialog = _dialog(_Addon())
        dialog.draft[look_mod.KEY_BAR_STYLE] = "progress_mid_flat_blue.png"
        dialog._apply_look()
        self.assertFalse(dialog._bar_tiled)
        self.assertEqual(dialog.props["next_ep_bar_tiled"], "false")

    def test_a_dialog_with_no_overrides_looks_exactly_as_before(self):
        plain = _dialog(_Addon())
        plain._apply_look()
        self.assertEqual(plain.props["next_ep_card_color"], "F0000000")
        self.assertEqual(plain.props["next_ep_bar_texture"], "progress_mid_segmented_teal.png")


class CustomizeOverrideTests(unittest.TestCase):
    def test_the_custom_style_lists_fourteen_rows_in_the_skip_dialog_order(self):
        self.assertEqual(
            app.customize_rows(app.DEFAULT_DRAFT),
            [
                app.KEY_STYLE,
                app.KEY_LOOK,
                look_mod.KEY_TEXT_COLOR,
                look_mod.KEY_HEADING_COLOR,
                look_mod.KEY_ALL_CAPS,
                look_mod.KEY_FOCUS_STYLE,
                look_mod.KEY_BAR_STYLE,
                look_mod.KEY_CARD_OPACITY,
                app.KEY_POSITION,
                app.KEY_SIZE,
                app.KEY_THUMBNAIL,
                app.KEY_COUNTDOWN,
                app.KEY_PROGRESS,
                app.KEY_FOCUS,
            ],
        )

    def test_the_bar_style_row_goes_away_with_the_progress_bar(self):
        draft = dict(app.DEFAULT_DRAFT, **{app.KEY_PROGRESS: False})
        rows = app.customize_rows(draft)
        self.assertNotIn(look_mod.KEY_BAR_STYLE, rows)
        self.assertEqual(len(rows), 13)
        self.assertIn(look_mod.KEY_FOCUS_STYLE, rows)

    def test_the_toast_style_hides_every_override_row(self):
        rows = app.customize_rows({app.KEY_STYLE: "Native"})
        for key in look_mod.OVERRIDE_KEYS:
            self.assertNotIn(key, rows)

    def test_every_override_has_a_row_control_and_three_label_strings(self):
        ids = list(cust.ROW_IDS.values())
        self.assertEqual(len(set(ids)), len(ids))
        for key in look_mod.OVERRIDE_KEYS:
            self.assertIn(key, cust.ROW_IDS)
            self.assertIn(key, cust.ROW_LABEL_IDS)
        self.assertEqual(
            [cust.ROW_LABEL_IDS[key][0] for key in look_mod.OVERRIDE_KEYS], list(range(47105, 47111))
        )

    def test_defaults_follow_the_look(self):
        for key in look_mod.OVERRIDE_KEYS:
            self.assertEqual(app.DEFAULT_DRAFT[key], look_mod.FOLLOW_LOOK)
            self.assertEqual(app.CHOICE_KEYS[key], look_mod.override_options(key))

    def test_each_row_cycles_through_its_choices_and_wraps(self):
        for key in look_mod.OVERRIDE_KEYS:
            options = look_mod.override_options(key)
            draft = dict(app.DEFAULT_DRAFT)
            seen = [draft[key]]
            for _ in range(len(options) - 1):
                cust.nudge(draft, key, 1)
                seen.append(draft[key])
            self.assertEqual(seen, list(options), key)
            cust.nudge(draft, key, 1)
            self.assertEqual(draft[key], look_mod.FOLLOW_LOOK, key)
            cust.nudge(draft, key, -1)
            self.assertEqual(draft[key], options[-1], key)

    def test_choosing_another_look_clears_what_was_changed_on_top(self):
        draft = dict(app.DEFAULT_DRAFT)
        for key in look_mod.OVERRIDE_KEYS:
            cust.nudge(draft, key, 1)
            self.assertNotEqual(draft[key], look_mod.FOLLOW_LOOK)
        cust.nudge(draft, app.KEY_LOOK, 1)
        for key in look_mod.OVERRIDE_KEYS:
            self.assertEqual(draft[key], look_mod.FOLLOW_LOOK, key)

    def test_changing_an_override_does_not_touch_the_look_or_the_others(self):
        draft = dict(app.DEFAULT_DRAFT, **{app.KEY_LOOK: "Modern"})
        cust.nudge(draft, look_mod.KEY_BAR_STYLE, 1)
        self.assertEqual(draft[app.KEY_LOOK], "Modern")
        self.assertNotEqual(draft[look_mod.KEY_BAR_STYLE], look_mod.FOLLOW_LOOK)
        self.assertEqual(draft[look_mod.KEY_TEXT_COLOR], look_mod.FOLLOW_LOOK)

    def test_the_value_text_names_each_choice(self):
        draft = dict(app.DEFAULT_DRAFT)
        for key in look_mod.OVERRIDE_KEYS:
            self.assertEqual(cust.value_text(None, draft, key), "Same as look", key)
        draft[look_mod.KEY_TEXT_COLOR] = "FF1976D2"
        draft[look_mod.KEY_FOCUS_STYLE] = "button_focus_flat_teal.png"
        draft[look_mod.KEY_BAR_STYLE] = "progress_mid_flat_blue.png"
        draft[look_mod.KEY_CARD_OPACITY] = "35"
        self.assertEqual(cust.value_text(None, draft, look_mod.KEY_TEXT_COLOR), "Blue")
        self.assertEqual(
            cust.value_text(None, draft, look_mod.KEY_FOCUS_STYLE),
            look_mod.override_label(look_mod.KEY_FOCUS_STYLE, "button_focus_flat_teal.png"),
        )
        self.assertEqual(
            cust.value_text(None, draft, look_mod.KEY_BAR_STYLE),
            look_mod.override_label(look_mod.KEY_BAR_STYLE, "progress_mid_flat_blue.png"),
        )
        self.assertEqual(cust.value_text(None, draft, look_mod.KEY_CARD_OPACITY), "35%")

    def test_upper_case_reads_yes_or_no(self):
        draft = dict(app.DEFAULT_DRAFT, **{look_mod.KEY_ALL_CAPS: "On"})
        self.assertEqual(cust.value_text(None, draft, look_mod.KEY_ALL_CAPS), "Yes")
        draft[look_mod.KEY_ALL_CAPS] = "Off"
        self.assertEqual(cust.value_text(None, draft, look_mod.KEY_ALL_CAPS), "No")

    def test_saving_writes_only_the_overrides_that_changed(self):
        original = dict(app.DEFAULT_DRAFT)
        draft = dict(original)
        draft[look_mod.KEY_BAR_STYLE] = "progress_mid_flat_blue.png"
        draft[look_mod.KEY_CARD_OPACITY] = "40"
        self.assertEqual(
            cust.changed_payload(draft, original),
            {
                look_mod.KEY_BAR_STYLE: "progress_mid_flat_blue.png",
                look_mod.KEY_CARD_OPACITY: "40",
            },
        )

    def test_going_back_to_same_as_look_is_saved_as_a_change(self):
        original = dict(app.DEFAULT_DRAFT, **{look_mod.KEY_TEXT_COLOR: "FF1976D2"})
        draft = dict(original, **{look_mod.KEY_TEXT_COLOR: look_mod.FOLLOW_LOOK})
        self.assertEqual(
            cust.changed_payload(draft, original), {look_mod.KEY_TEXT_COLOR: look_mod.FOLLOW_LOOK}
        )

    def test_the_stored_overrides_are_read_back_into_the_draft(self):
        addon = _Addon(
            **{
                look_mod.KEY_TEXT_COLOR: "ff1976d2",
                look_mod.KEY_ALL_CAPS: "on",
                look_mod.KEY_CARD_OPACITY: "45",
                look_mod.KEY_BAR_STYLE: "garbage",
            }
        )
        draft = app.load_popup_draft(addon)
        self.assertEqual(draft[look_mod.KEY_TEXT_COLOR], "FF1976D2")
        self.assertEqual(draft[look_mod.KEY_ALL_CAPS], "On")
        self.assertEqual(draft[look_mod.KEY_CARD_OPACITY], "45")
        self.assertEqual(draft[look_mod.KEY_BAR_STYLE], look_mod.FOLLOW_LOOK)
        self.assertEqual(draft[look_mod.KEY_HEADING_COLOR], look_mod.FOLLOW_LOOK)

    def test_the_preview_uses_the_draft_overrides(self):
        draft = dict(app.DEFAULT_DRAFT, **{look_mod.KEY_BAR_STYLE: "progress_mid_flat_blue.png"})
        dialog = _dialog(_Addon())
        dialog.draft = draft
        dialog._apply_look()
        self.assertEqual(dialog.props["next_ep_bar_texture"], "progress_mid_flat_blue.png")


class CustomizeSkinRowTests(unittest.TestCase):
    def controls(self, res):
        path = os.path.join(ROOT, "resources", "skins", "default", res, "NextEpisodeCustomize.xml")
        out = {}
        for ctrl in ET.parse(path).getroot().iter("control"):
            cid = ctrl.get("id")
            if cid is None:
                continue
            out[int(cid)] = {
                tag: int(ctrl.findtext(tag))
                for tag in ("top", "height", "width")
                if ctrl.findtext(tag) is not None
            }
        return out

    def test_every_row_exists_in_both_skins_with_the_computed_height(self):
        rows = app.customize_rows(app.DEFAULT_DRAFT)
        _step, height = cust.row_metrics(len(rows))
        for res, factor in (("720p", 1), ("1080i", 1.5)):
            found = self.controls(res)
            for key in rows:
                cid = cust.ROW_IDS[key]
                self.assertIn(cid, found, (res, key))
                self.assertEqual(found[cid]["height"], int(height * factor + 0.5), (res, key))

    def test_the_rows_fit_inside_the_screen(self):
        for count in (7, 12, 13, 14):
            tops, footer, panel_h = cust.row_layout(list(range(count)))
            self.assertLessEqual(panel_h, app.BASE_SCREEN_H, count)
            self.assertGreaterEqual(footer, tops[-1] + cust.row_metrics(count)[1])

    def test_rows_shrink_only_when_they_would_not_fit(self):
        self.assertEqual(cust.row_metrics(7), (cust._ROW_STEP, cust._ROW_H))
        step, height = cust.row_metrics(14)
        self.assertLess(step, cust._ROW_STEP)
        self.assertEqual(step - height, cust._ROW_STEP - cust._ROW_H)
        self.assertGreaterEqual(height, 30)

    def test_the_two_skin_resolutions_agree_on_row_tops(self):
        rows = app.customize_rows(app.DEFAULT_DRAFT)
        small, big = self.controls("720p"), self.controls("1080i")
        for key in rows:
            cid = cust.ROW_IDS[key]
            self.assertEqual(big[cid]["top"], int(small[cid]["top"] * 1.5 + 0.5), key)


class OverrideSettingsTests(unittest.TestCase):
    def settings(self):
        tree = ET.parse(os.path.join(ROOT, "resources", "settings.xml"))
        return {s.get("id"): s for s in tree.getroot().iter("setting")}

    def test_each_override_has_a_setting_that_lists_exactly_its_choices(self):
        found = self.settings()
        for key in look_mod.OVERRIDE_KEYS:
            setting = found[key]
            self.assertEqual(setting.findtext("default"), look_mod.FOLLOW_LOOK, key)
            options = [o.text for o in setting.iter("option")]
            self.assertEqual(options, list(look_mod.override_options(key)), key)

    def test_every_option_label_is_a_string_id_or_a_plain_name(self):
        found = self.settings()
        for key in look_mod.OVERRIDE_KEYS:
            labels = [o.get("label") for o in found[key].iter("option")]
            self.assertEqual(labels[0], "47111", key)
            self.assertTrue(all(label for label in labels), key)

    def test_all_overrides_are_hidden_with_the_toast_style(self):
        found = self.settings()
        for key in look_mod.OVERRIDE_KEYS:
            deps = {
                (d.get("setting"), d.text) for d in found[key].iter("dependency") if d.get("type") == "visible"
            }
            self.assertIn(("next_episode_popup_style", "Custom"), deps, key)

    def test_the_bar_style_also_needs_the_progress_bar(self):
        found = self.settings()
        deps = {
            (d.get("setting"), d.text)
            for d in found[look_mod.KEY_BAR_STYLE].iter("dependency")
            if d.get("type") == "visible"
        }
        self.assertIn(("next_episode_popup_progress", "true"), deps)
        for key in look_mod.OVERRIDE_KEYS:
            if key != look_mod.KEY_BAR_STYLE:
                other = {d.get("setting") for d in found[key].iter("dependency")}
                self.assertNotIn("next_episode_popup_progress", other, key)

    def test_the_overrides_sit_right_under_the_look_setting(self):
        order = [s.get("id") for s in ET.parse(os.path.join(ROOT, "resources", "settings.xml")).getroot().iter("setting")]
        start = order.index(look_mod.KEY_LOOK)
        self.assertEqual(order[start + 1 : start + 7], list(look_mod.OVERRIDE_KEYS))

    def test_the_override_labels_exist_in_every_language_pack(self):
        langs = os.path.join(ROOT, "resources", "language")
        for pack in sorted(os.listdir(langs)):
            text = open(os.path.join(langs, pack, "strings.po"), encoding="utf-8").read()
            for sid in range(47105, 47118):
                self.assertIn('msgctxt "#%d"' % sid, text, (pack, sid))


if __name__ == "__main__":
    unittest.main()
