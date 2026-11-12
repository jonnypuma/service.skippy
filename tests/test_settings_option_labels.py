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
