# -*- coding: utf-8 -*-
"""Every default written in the code matches the default in resources/settings.xml.

The code default is what Skippy uses when it cannot read a setting (the add-on handle is
gone during an update, or the value is empty). A different value there flips behaviour at
exactly those moments. An empty text default is allowed: the caller then picks its own value.
"""

import glob
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_CALL = re.compile(
    r"(addon_get_bool|addon_get_int|addon_get_setting_text)\(\s*"
    r"([^,()]+(?:\([^()]*\))?)\s*,\s*[\"']([a-z0-9_]+)[\"']\s*(?:,\s*([^,\)]+))?\s*[,\)]"
)


def _xml_defaults():
    with open(os.path.join(ROOT, "resources", "settings.xml"), encoding="utf-8") as handle:
        text = handle.read()
    out = {}
    for match in re.finditer(r'<setting id="([^"]+)" type="([^"]+)"(.*?)</setting>', text, re.S):
        default = re.search(r"<default>(.*?)</default>", match.group(3), re.S)
        out[match.group(1)] = (match.group(2), default.group(1).strip() if default else "")
    return out


def _mismatches():
    defaults = _xml_defaults()
    found = []
    for path in sorted(glob.glob(os.path.join(ROOT, "*.py"))):
        if path.endswith("-Jon.py"):
            continue
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        for match in _CALL.finditer(text):
            reader, key, code = match.group(1), match.group(3), (match.group(4) or "").strip()
            if key not in defaults:
                continue
            kind, xml = defaults[key]
            where = "%s:%d %s" % (os.path.basename(path), text[: match.start()].count("\n") + 1, key)
            if reader == "addon_get_bool" and kind == "boolean":
                value = {"True": "true", "False": "false", "": "false"}.get(code)
                if value is not None and value != xml:
                    found.append("%s: code %s, settings.xml %s" % (where, code or "(none)", xml))
            elif reader == "addon_get_int" and kind == "integer":
                if re.fullmatch(r"-?\d+", code or "0") and (code or "0") != xml:
                    found.append("%s: code %s, settings.xml %s" % (where, code or "0", xml))
            elif reader == "addon_get_setting_text" and kind == "string":
                literal = re.fullmatch(r"[\"'](.*)[\"']", code)
                if literal and literal.group(1) and literal.group(1) != xml:
                    found.append("%s: code %r, settings.xml %r" % (where, literal.group(1), xml))
    return found


class SettingDefaultsTests(unittest.TestCase):
    def test_code_defaults_match_settings_xml(self):
        self.assertEqual(_mismatches(), [])

    def test_the_scan_sees_the_reads(self):
        # Guards the regular expression: it must find a known read and its default.
        defaults = _xml_defaults()
        self.assertEqual(defaults["show_toast_for_skipped_segment"], ("boolean", "true"))
        with open(os.path.join(ROOT, "service_loop_skip.py"), encoding="utf-8") as handle:
            text = handle.read()
        keys = [m.group(3) for m in _CALL.finditer(text)]
        self.assertIn("show_toast_for_skipped_segment", keys)


if __name__ == "__main__":
    unittest.main()
