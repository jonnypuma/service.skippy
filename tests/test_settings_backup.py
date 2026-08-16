# -*- coding: utf-8 -*-
"""Settings backup/restore vs resources/settings.xml."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from tests.kodi_stubs import install_kodi_stubs

ROOT = Path(__file__).resolve().parents[1]
SETTINGS_XML = ROOT / "resources" / "settings.xml"

install_kodi_stubs()


def _xml_setting_ids():
    tree = ET.parse(SETTINGS_XML)
    persisted = []
    actions = []
    all_ids = []
    for setting in tree.getroot().iter("setting"):
        sid = setting.get("id")
        stype = setting.get("type")
        if not sid:
            continue
        all_ids.append(sid)
        if stype == "action":
            actions.append(sid)
        else:
            persisted.append(sid)
    return persisted, actions, all_ids


class FakeAddon:
    """In-memory addon settings store pointing at the real add-on path."""

    def __init__(self, initial=None):
        self._store = dict(initial or {})
        self.path = str(ROOT)

    def getAddonInfo(self, key):
        if key == "path":
            return self.path
        if key == "version":
            return "5.3.4"
        return ""

    def getSetting(self, key):
        return self._store.get(key, "")

    def setSetting(self, key, value):
        self._store[key] = "" if value is None else str(value)

    def getLocalizedString(self, _key):
        return ""


class SettingsBackupCoverageTests(unittest.TestCase):
    def test_persisted_ids_match_settings_xml(self):
        import settings_backup as sb

        persisted, actions, _ = _xml_setting_ids()
        addon = FakeAddon()
        ids = sb.iter_persisted_setting_ids(addon)
        self.assertEqual(ids, persisted)
        self.assertGreaterEqual(len(ids), 80)
        for a in actions:
            self.assertNotIn(a, ids)

    def test_actions_excluded(self):
        import settings_backup as sb

        _, actions, _ = _xml_setting_ids()
        addon = FakeAddon()
        ids = set(sb.iter_persisted_setting_ids(addon))
        self.assertTrue(actions)
        self.assertTrue(set(actions).isdisjoint(ids))


class SettingsBackupRoundtripTests(unittest.TestCase):
    def test_export_includes_all_persisted_keys(self):
        import settings_backup as sb

        persisted, _, _ = _xml_setting_ids()
        values = {k: "val_%s" % i for i, k in enumerate(persisted)}
        # booleans / ints as Kodi stores them
        values["enable_verbose_logging"] = "true"
        values["rewind_threshold_seconds"] = "15"
        addon = FakeAddon(values)

        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "backup.json")
            n = sb.export_to_path(addon, dest)
            self.assertEqual(n, len(persisted))
            with open(dest, encoding="utf-8") as fp:
                data = json.load(fp)
            self.assertEqual(data["schema"], sb.SCHEMA)
            self.assertEqual(data["addon_id"], sb.ADDON_ID)
            self.assertEqual(data["setting_key_count"], len(persisted))
            self.assertEqual(set(data["settings"].keys()), set(persisted))
            self.assertEqual(data["settings"]["enable_verbose_logging"], "true")
            self.assertEqual(data["settings"]["rewind_threshold_seconds"], "15")

    def test_import_restores_overlapping_keys_and_skips_unknown(self):
        import settings_backup as sb

        persisted, _, _ = _xml_setting_ids()
        sample = persisted[:5]
        addon = FakeAddon({k: "old" for k in persisted})

        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "backup.json")
            payload = {
                "schema": sb.SCHEMA,
                "addon_id": sb.ADDON_ID,
                "addon_version_exported": "5.0.0",
                "settings": {
                    sample[0]: "new0",
                    sample[1]: "new1",
                    "not_a_real_setting_xyz": "nope",
                },
            }
            with open(dest, "w", encoding="utf-8") as fp:
                json.dump(payload, fp)

            applied, bad, note = sb.import_from_path(addon, dest)

        self.assertEqual(applied, 2)
        self.assertEqual(bad, 1)
        self.assertIn("5.0.0", note)
        self.assertEqual(addon.getSetting(sample[0]), "new0")
        self.assertEqual(addon.getSetting(sample[1]), "new1")
        # untouched keys stay
        self.assertEqual(addon.getSetting(sample[2]), "old")

    def test_roundtrip_preserves_values(self):
        import settings_backup as sb

        persisted, _, _ = _xml_setting_ids()
        original = {k: "v_%s" % k[-12:] for k in persisted}
        original["online_upload_theintrodb_api_key"] = "secret-tidb"
        original["tv_tmdb_api_key"] = "secret-tmdb"
        original["enable_skip_movies"] = "false"
        original["ask_dialog_debounce_ms"] = "400"

        src = FakeAddon(original)
        dst = FakeAddon({k: "RESET" for k in persisted})

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "rt.json")
            sb.export_to_path(src, path)
            applied, bad, _ = sb.import_from_path(dst, path)

        self.assertEqual(applied, len(persisted))
        self.assertEqual(bad, 0)
        for k in persisted:
            self.assertEqual(dst.getSetting(k), original[k], k)

    def test_rejects_wrong_schema(self):
        import settings_backup as sb

        addon = FakeAddon()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bad.json")
            with open(path, "w", encoding="utf-8") as fp:
                json.dump(
                    {
                        "schema": "other",
                        "addon_id": sb.ADDON_ID,
                        "settings": {},
                    },
                    fp,
                )
            with self.assertRaises(ValueError):
                sb.import_from_path(addon, path)

    def test_restore_browse_requires_json_file(self):
        import settings_backup as sb
        import xbmcvfs

        self.assertFalse(sb._restore_browse_result_is_json_file(""))
        self.assertFalse(sb._restore_browse_result_is_json_file("C:/foo"))
        self.assertFalse(sb._restore_browse_result_is_json_file("C:/foo.txt"))

        with tempfile.TemporaryDirectory() as tmp:
            jpath = os.path.join(tmp, "ok.json")
            with open(jpath, "w", encoding="utf-8") as fp:
                fp.write("{}")

            real_exists = xbmcvfs.exists
            xbmcvfs.exists = lambda p: os.path.exists(p)
            try:
                self.assertTrue(sb._restore_browse_result_is_json_file(jpath))
                self.assertFalse(sb._restore_browse_result_is_json_file(tmp))
            finally:
                xbmcvfs.exists = real_exists

    def test_gen_settings_ids_match_shipped_xml(self):
        import re

        gen_text = (ROOT / "tools" / "gen_settings_v1.py").read_text(encoding="utf-8")
        gen_ids = re.findall(
            r"(?:string_setting|bool_setting|int_setting|labelenum_setting|action_setting)"
            r"\(\s*g,\s*\"([a-z0-9_]+)\"",
            gen_text,
        )
        _, _, shipped_all = _xml_setting_ids()
        self.assertEqual(gen_ids, shipped_all)

    def test_all_button_focus_textures_are_settings_options(self):
        """Every button_focus*.png in media (except nofocus) must be a picker value."""
        media = ROOT / "resources" / "skins" / "default" / "media"
        on_disk = sorted(
            name
            for name in os.listdir(media)
            if name.startswith("button_focus") and name.endswith(".png")
        )
        tree = ET.parse(SETTINGS_XML)
        wired = []
        for setting in tree.getroot().iter("setting"):
            if setting.get("id") != "button_focus_style":
                continue
            for option in setting.iter("option"):
                if option.text:
                    wired.append(option.text.strip())
            break
        self.assertEqual(on_disk, sorted(wired))

    def test_all_progress_mid_textures_are_settings_options(self):
        media = ROOT / "resources" / "skins" / "default" / "media"
        on_disk = sorted(
            name
            for name in os.listdir(media)
            if name.startswith("progress_mid") and name.endswith(".png")
        )
        tree = ET.parse(SETTINGS_XML)
        wired = []
        for setting in tree.getroot().iter("setting"):
            if setting.get("id") != "progress_bar_style":
                continue
            for option in setting.iter("option"):
                if option.text:
                    wired.append(option.text.strip())
            break
        self.assertEqual(on_disk, sorted(wired))

    def test_integer_range_settings_use_spinner_not_slider(self):
        tree = ET.parse(SETTINGS_XML)
        ids = (
            "skip_jump_offset_seconds",
            "ask_dialog_debounce_ms",
            "progress_bar_height",
            "progress_bar_updates_per_second",
        )
        found = {sid: None for sid in ids}
        for setting in tree.getroot().iter("setting"):
            sid = setting.get("id")
            if sid in found:
                found[sid] = setting.find("control")
        for sid, ctrl in found.items():
            self.assertIsNotNone(ctrl, sid)
            self.assertEqual(ctrl.get("type"), "spinner", sid)
            self.assertEqual(ctrl.get("format"), "integer", sid)


if __name__ == "__main__":
    unittest.main()
