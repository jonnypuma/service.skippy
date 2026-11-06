# -*- coding: utf-8 -*-
"""English strings.po ids and msgid text must exist in every language pack."""

import os
import re
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LANG_ROOT = os.path.join(ROOT, "resources", "language")
# Kodi looks for ``resources/language/<language add-on id>/strings.po``. Kodi 23 nightlies no
# longer fall back to the old English-name folders ("English", "German", ...), so a pack in
# such a folder is never loaded and every settings label comes up blank.
SOURCE_PACK = "resource.language.en_gb"
EXPECTED_PACKS = {
    "resource.language.en_gb",
    "resource.language.da_dk",
    "resource.language.de_de",
    "resource.language.el_gr",
    "resource.language.es_es",
    "resource.language.fr_fr",
    "resource.language.it_it",
    "resource.language.nb_no",
    "resource.language.nl_nl",
    "resource.language.pt_br",
    "resource.language.sv_se",
}


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
        english = _po_pairs(os.path.join(LANG_ROOT, SOURCE_PACK, "strings.po"))
        self.assertGreater(len(english), 100)
        langs = [
            name
            for name in os.listdir(LANG_ROOT)
            if os.path.isdir(os.path.join(LANG_ROOT, name))
        ]
        self.assertIn(SOURCE_PACK, langs)
        for name in langs:
            if name == SOURCE_PACK:
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

    def test_pack_folders_use_kodi_language_addon_ids(self):
        langs = {
            name
            for name in os.listdir(LANG_ROOT)
            if os.path.isdir(os.path.join(LANG_ROOT, name))
        }
        self.assertEqual(
            langs,
            EXPECTED_PACKS,
            "language folders must be named after Kodi's resource.language.<locale> add-ons",
        )
        for name in sorted(langs):
            self.assertTrue(
                os.path.isfile(os.path.join(LANG_ROOT, name, "strings.po")),
                "%s has no strings.po" % name,
            )

    def test_every_settings_label_and_help_id_is_in_english(self):
        """A numeric label/help id with no string shows up blank in Kodi's settings."""
        english = _po_pairs(os.path.join(LANG_ROOT, SOURCE_PACK, "strings.po"))
        with open(os.path.join(ROOT, "resources", "settings.xml"), encoding="utf-8") as fh:
            xml = fh.read()
        wanted = {int(x) for x in re.findall(r'\b(?:label|help)="(\d+)"', xml)}
        self.assertGreater(len(wanted), 100)
        self.assertEqual(sorted(wanted - set(english)), [])


if __name__ == "__main__":
    unittest.main()
