# -*- coding: utf-8 -*-
"""English strings.po ids and msgid text must exist in every language pack."""

import os
import re
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LANG_ROOT = os.path.join(ROOT, "resources", "language")


def _po_pairs(path):
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    pairs = {}
    blocks = re.split(r'\nmsgctxt\s+"#', text)
    for block in blocks[1:]:
        m_id = re.match(r'(\d+)"', block)
        m_str = re.search(r'^msgid\s+"(.*)"\s*$', block, re.M)
        if m_id and m_str:
            pairs[int(m_id.group(1))] = m_str.group(1)
    return pairs


class LanguagePackSyncTests(unittest.TestCase):
    def test_all_packs_match_english_ids_and_msgid(self):
        english = _po_pairs(os.path.join(LANG_ROOT, "English", "strings.po"))
        self.assertGreater(len(english), 100)
        langs = [
            name
            for name in os.listdir(LANG_ROOT)
            if os.path.isdir(os.path.join(LANG_ROOT, name))
        ]
        self.assertIn("English", langs)
        for name in langs:
            if name == "English":
                continue
            other = _po_pairs(os.path.join(LANG_ROOT, name, "strings.po"))
            missing = sorted(set(english) - set(other))
            extra = sorted(set(other) - set(english))
            msgid_diffs = sorted(
                sid
                for sid in english
                if sid in other and other[sid] != english[sid]
            )
            self.assertEqual(missing, [], "%s missing ids" % name)
            self.assertEqual(extra, [], "%s extra ids" % name)
            self.assertEqual(msgid_diffs, [], "%s msgid mismatches" % name)


if __name__ == "__main__":
    unittest.main()
