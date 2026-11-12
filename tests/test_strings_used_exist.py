# -*- coding: utf-8 -*-
"""Every string id the code asks for exists in every language pack, with the same placeholders."""

import glob
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# get_localized(addon, 12345, ...), _t(12345, ...), getLocalizedString(12345)
_USES = re.compile(r"(?:get_localized\(\s*[^,()]+(?:\([^()]*\))?\s*,|\b_t\(|getLocalizedString\()\s*(\d{5})\b")
_PLACEHOLDER = re.compile(r"%[-+ 0#]*\d*(?:\.\d+)?[sdif]")


def _entries(path):
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    return {
        m.group(1): (m.group(2), m.group(3))
        for m in re.finditer(
            r'msgctxt "#(\d+)"\s*\nmsgid "((?:[^"\\]|\\.)*)"\s*\nmsgstr "((?:[^"\\]|\\.)*)"', text
        )
    }


class StringsUsedTests(unittest.TestCase):
    def test_every_id_in_the_code_is_in_every_language(self):
        used = set()
        for path in glob.glob(os.path.join(ROOT, "*.py")):
            if path.endswith("-Jon.py"):
                continue
            with open(path, encoding="utf-8") as handle:
                used.update(_USES.findall(handle.read()))
        self.assertGreater(len(used), 150)  # guards the pattern itself
        for path in sorted(glob.glob(os.path.join(ROOT, "resources", "language", "*", "strings.po"))):
            with self.subTest(language=os.path.basename(os.path.dirname(path))):
                self.assertEqual(sorted(used - set(_entries(path))), [])

    def test_translations_keep_the_placeholders(self):
        english = _entries(os.path.join(ROOT, "resources", "language", "resource.language.en_gb", "strings.po"))
        for path in sorted(glob.glob(os.path.join(ROOT, "resources", "language", "*", "strings.po"))):
            for sid, (msgid, msgstr) in _entries(path).items():
                if not msgstr:
                    continue
                with self.subTest(language=os.path.basename(os.path.dirname(path)), id=sid):
                    self.assertEqual(sorted(_PLACEHOLDER.findall(msgid)), sorted(_PLACEHOLDER.findall(msgstr)))
                    self.assertEqual(msgid, english.get(sid, (msgid,))[0])


if __name__ == "__main__":
    unittest.main()
