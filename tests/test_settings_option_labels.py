# -*- coding: utf-8 -*-
"""Settings choices that are words are translated; style, colour and texture names are not.

A spinner option whose label is plain text shows that text in every language. The choices
people read as words (positions, save policies, formats, modes) use string ids, which every
language pack must define.
"""

import glob
import os
import re
import unittest
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Names of looks, colours, textures and services, kept in English on purpose.
NAME_SETTINGS = {
    "button_focus_style",
    "progress_bar_style",
    "minimal_button_style",
    "skip_dialog_font_color",
    "next_episode_popup_look",
    "next_episode_popup_focus_style",
    "next_episode_popup_bar_style",
    "next_episode_popup_text_color",
    "next_episode_popup_heading_color",
    "online_upload_default_target",
    "modal_style",
    "skip_card_style",
    "skip_dialog_layout",
    "skip_layout_look",
    "next_episode_popup_layout",
    "next_episode_popup_layout_look",
}


def _settings():
    tree = ET.parse(os.path.join(ROOT, "resources", "settings.xml"))
    return {s.get("id"): s for s in tree.getroot().iter("setting")}


def _ids(path):
    with open(path, encoding="utf-8") as handle:
        return set(re.findall(r'msgctxt "#(\d+)"', handle.read()))


class OptionLabelTests(unittest.TestCase):
    def test_word_choices_use_string_ids(self):
        english = []
        for sid, setting in _settings().items():
            if sid in NAME_SETTINGS:
                continue
            for option in setting.iter("option"):
                label = option.get("label") or ""
                if re.search(r"[A-Za-z]{2,}", label):
                    english.append("%s: %s" % (sid, label))
        self.assertEqual(english, [])

    def test_no_setting_mixes_string_ids_and_plain_labels(self):
        """Kodi then accepts only the string-id options: every other choice is refused silently
        (CSettingString::CheckValidity), and the setting stays at its default (issue #5)."""
        mixed = []
        for sid, setting in _settings().items():
            labels = [option.get("label") or "" for option in setting.iter("option")]
            numeric = sum(label.isdigit() for label in labels)
            if numeric and numeric != len(labels):
                mixed.append(sid)
        self.assertEqual(mixed, [])

    def test_every_value_the_customize_screens_save_is_an_option(self):
        """What Customize next episode popup can store must be a choice Kodi accepts."""
        import sys

        from tests.kodi_stubs import install_kodi_stubs

        install_kodi_stubs()
        sys.path.insert(0, ROOT)
        from next_episode_appearance import CHOICE_KEYS

        settings = _settings()
        for key, choices in CHOICE_KEYS.items():
            with self.subTest(setting=key):
                options = [o.text for o in settings[key].iter("option")]
                self.assertEqual(sorted(set(choices) - set(options)), [])

    def test_every_language_defines_every_option_string(self):
        used = set()
        for setting in _settings().values():
            for option in setting.iter("option"):
                if (option.get("label") or "").isdigit():
                    used.add(option.get("label"))
        self.assertGreater(len(used), 50)
        for path in sorted(glob.glob(os.path.join(ROOT, "resources", "language", "*", "strings.po"))):
            with self.subTest(language=os.path.basename(os.path.dirname(path))):
                self.assertEqual(sorted(used - _ids(path)), [])


if __name__ == "__main__":
    unittest.main()
