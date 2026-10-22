# -*- coding: utf-8 -*-
"""Card opacity, new texture options and Customize modal wiring."""

import os
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

from skip_dialog_appearance import (  # noqa: E402
    DictSettingsReader,
    apply_full_skip_layout,
    card_color_diffuse,
)
from skip_dialog_customize_ui import (  # noqa: E402
    BUTTON_FOCUS,
    MINIMAL_PLATES,
    PROGRESS_STYLES,
    customize_left_pane_layout,
    customize_nav_ids,
)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MEDIA = os.path.join(ROOT, "resources", "skins", "default", "media")


def _settings_options(setting_id):
    root = ET.parse(os.path.join(ROOT, "resources", "settings.xml")).getroot()
    for st in root.iter("setting"):
        if st.get("id") == setting_id:
            return [(o.get("label"), o.text) for o in st.iter("option")]
    raise AssertionError(setting_id)


class CardOpacityTests(unittest.TestCase):
    def test_colour_from_percent(self):
        self.assertEqual(card_color_diffuse(DictSettingsReader({"skip_card_opacity": 100})), "FF000000")
        self.assertEqual(card_color_diffuse(DictSettingsReader({"skip_card_opacity": 0})), "00000000")
        self.assertEqual(card_color_diffuse(DictSettingsReader({"skip_card_opacity": 95})), "F2000000")
        self.assertEqual(card_color_diffuse(DictSettingsReader({"skip_card_opacity": 999})), "FF000000")
        self.assertEqual(card_color_diffuse(DictSettingsReader({})), "F2000000")

    def _layout(self, **data):
        window = MagicMock()
        window.getProperty.return_value = ""
        backdrop = MagicMock()
        window.getControl.side_effect = lambda cid: backdrop if cid == 3081 else MagicMock()
        apply_full_skip_layout(
            window,
            DictSettingsReader(dict({"skip_dialog_mode": "Full"}, **data)),
            playhead=10.0,
            segment=MagicMock(start_seconds=0.0, end_seconds=60.0),
            scale_fn=lambda v: v,
        )
        return backdrop

    def test_card_visible_with_colour(self):
        card = self._layout(skip_card_opacity=70)
        card.setColorDiffuse.assert_called_with("B2000000")
        card.setVisible.assert_called_with(True)

    def test_card_can_be_switched_off(self):
        card = self._layout(skip_card_enabled=False)
        card.setVisible.assert_called_with(False)

    def test_compact_never_shows_card(self):
        card = self._layout(skip_dialog_mode="CompactFull")
        card.setVisible.assert_called_with(False)


class StyleOptionTests(unittest.TestCase):
    def test_python_lists_match_settings_xml(self):
        for setting, pairs in (
            ("button_focus_style", BUTTON_FOCUS),
            ("progress_bar_style", PROGRESS_STYLES),
            ("minimal_button_style", MINIMAL_PLATES),
        ):
            xml_opts = _settings_options(setting)
            self.assertEqual([v for _l, v in xml_opts], [v for _l, v in pairs], setting)
            self.assertEqual([l for l, _v in xml_opts], [l for l, _v in pairs], setting)

    def test_every_option_file_exists_and_label_not_numeric(self):
        for pairs in (BUTTON_FOCUS, PROGRESS_STYLES, MINIMAL_PLATES):
            for label, filename in pairs:
                self.assertTrue(os.path.isfile(os.path.join(MEDIA, filename)), filename)
                self.assertFalse(label[:1].isdigit(), label)

    def test_custom_only_settings_hidden_in_native(self):
        root = ET.parse(os.path.join(ROOT, "resources", "settings.xml")).getroot()
        hidden = set()
        for st in root.iter("setting"):
            for dep in st.iter("dependency"):
                if dep.get("type") != "visible":
                    continue
                if dep.get("setting") == "skip_dialog_type" and dep.text == "Custom":
                    hidden.add(st.get("id"))
                for cond in dep.iter("condition"):
                    if (
                        cond.get("setting") == "skip_dialog_type"
                        and cond.get("operator") == "!is"
                        and cond.text == "Native"
                    ):
                        hidden.add(st.get("id"))
        for sid in ("skip_card_enabled", "skip_card_opacity", "settings_action_skip_presets"):
            self.assertIn(sid, hidden)


class ModeVisibilityTests(unittest.TestCase):
    """Settings page shows only the options that apply to the chosen skip dialog mode."""

    @staticmethod
    def _modes_for(setting_id):
        root = ET.parse(os.path.join(ROOT, "resources", "settings.xml")).getroot()
        for st in root.iter("setting"):
            if st.get("id") != setting_id:
                continue
            modes = None
            for dep in st.iter("dependency"):
                if dep.get("type") != "visible":
                    continue
                found = set()
                if dep.get("setting") == "skip_dialog_mode":
                    found.add(dep.text.strip())
                for cond in dep.iter("condition"):
                    if cond.get("setting") == "skip_dialog_mode":
                        found.add(cond.text.strip())
                if found:
                    modes = found if modes is None else modes & found
            return modes
        raise AssertionError(setting_id)

    def test_minimal_options_only_in_minimal(self):
        for sid in ("minimal_button_style", "minimal_skip_button_format", "minimal_skip_dialog_position"):
            self.assertEqual(self._modes_for(sid), {"Minimal"}, sid)

    def test_full_only_options(self):
        for sid in ("progress_bar_height", "hide_skip_icon", "hide_ending_text", "skip_card_enabled", "skip_card_opacity"):
            self.assertEqual(self._modes_for(sid), {"Full"}, sid)

    def test_compact_gets_a_reduced_set(self):
        for sid in ("show_progress_bar", "button_focus_style", "skip_button_format", "hide_close_button"):
            self.assertEqual(self._modes_for(sid), {"Full", "CompactFull"}, sid)

    def test_shared_options_not_mode_limited(self):
        for sid in ("skip_dialog_font_color", "skip_dialog_all_caps"):
            self.assertIsNone(self._modes_for(sid), sid)

    def test_duration_rows_need_a_duration_button_format(self):
        for sid in ("skip_duration_format", "skip_duration_content"):
            self.assertEqual(self._modes_for(sid), {"Full", "CompactFull", "Minimal"}, sid)
            setting = next(
                s for s in ET.parse(os.path.join(ROOT, "resources", "settings.xml")).getroot().iter("setting")
                if s.get("id") == sid
            )
            refs = {c.get("setting") for c in setting.iter("condition")}
            self.assertIn("skip_button_format", refs, sid)
            self.assertIn("minimal_skip_button_format", refs, sid)


class ModalWiringTests(unittest.TestCase):
    def test_modal_xml_has_new_rows_in_both_resolutions(self):
        for res in ("720p", "1080i"):
            path = os.path.join(ROOT, "resources", "skins", "default", res, "SkipDialogCustomize.xml")
            root = ET.parse(path).getroot()
            ids = {c.get("id") for c in root.iter("control")}
            for cid in ("4140", "4141", "4142"):
                self.assertIn(cid, ids, (res, cid))
            self.assertEqual(root.find("defaultcontrol").text, "4140")

    def test_full_mode_rows_still_fit_the_pane(self):
        draft = {
            "skip_dialog_mode": "Full",
            "hide_close_button": True,
            "skip_button_format": "Skip + Type + Duration",
        }
        ids = customize_nav_ids(draft)
        m = customize_left_pane_layout(ids, lambda v: v)
        self.assertLessEqual(m["content_bottom"], m["save_y"])


if __name__ == "__main__":
    unittest.main()
