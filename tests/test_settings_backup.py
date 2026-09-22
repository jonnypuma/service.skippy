# -*- coding: utf-8 -*-
"""Settings backup/restore vs resources/settings.xml."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

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
            self.assertEqual(data["segment_types"]["schema"], "skippy_segment_types_v1")
            self.assertGreaterEqual(len(data["segment_types"]["types"]), 11)
            for retired in (
                "segment_always_skip",
                "segment_ask_skip",
                "segment_never_skip",
                "custom_segment_keywords",
                "edl_action_mapping",
            ):
                self.assertNotIn(retired, data["settings"])

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

            def _profile_path(*parts):
                return os.path.join(tmp, *parts)

            with patch("segment_types.profile_path", side_effect=_profile_path):
                from segment_types import set_catalog_for_tests

                set_catalog_for_tests(None)
                sb.export_to_path(src, path)
                applied, bad, _ = sb.import_from_path(dst, path)

        self.assertEqual(applied, len(persisted))
        self.assertEqual(bad, 0)
        for k in persisted:
            self.assertEqual(dst.getSetting(k), original[k], k)

    def test_settings_backup_roundtrips_segment_catalog(self):
        import settings_backup as sb
        from segment_types import (
            ensure_catalog,
            get_user_skip_mode,
            save_catalog,
            seeded_builtin_types,
            set_catalog_for_tests,
            set_skip_mode,
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "settings.json")

            def _profile_path(*parts):
                return os.path.join(tmp, *parts)

            with patch("segment_types.profile_path", side_effect=_profile_path):
                set_catalog_for_tests(None)
                types = seeded_builtin_types()
                self.assertIsNone(set_skip_mode(types, "intro", "never"))
                types.append(
                    {
                        "id": "hook",
                        "label": "Hook",
                        "skip_mode": "ask",
                        "edl_action": 40,
                        "aliases": ["Hook"],
                        "builtin": False,
                        "online_bucket": None,
                        "edl_read_aliases": [],
                    }
                )
                self.assertTrue(save_catalog(types))
                addon = FakeAddon({"enable_verbose_logging": "true"})
                sb.export_to_path(addon, path)

                # Other device: stock catalog plus a custom type the backup does not have.
                fresh = seeded_builtin_types()
                fresh.append(
                    {
                        "id": "only here",
                        "label": "Only here",
                        "skip_mode": "never",
                        "edl_action": 41,
                        "aliases": ["Only here"],
                        "builtin": False,
                        "online_bucket": None,
                        "edl_read_aliases": [],
                    }
                )
                self.assertTrue(save_catalog(fresh))
                applied, bad, note = sb.import_from_path(addon, path)
                set_catalog_for_tests(None)
                live = {t["id"]: t for t in ensure_catalog()}
                self.assertEqual(bad, 0)
                self.assertIn("Segment types merged", note)
                self.assertGreater(applied, 0)
                self.assertEqual(live["intro"]["skip_mode"], "never")
                self.assertEqual(get_user_skip_mode("opening"), "never")
                self.assertEqual(live["hook"]["edl_action"], 40)
                self.assertIn("only here", live)

    def test_pre_7_settings_backup_applies_skip_lists_to_catalog(self):
        import settings_backup as sb
        from segment_types import ensure_catalog, save_catalog, seeded_builtin_types, set_catalog_for_tests

        persisted, _, _ = _xml_setting_ids()
        sample = persisted[0]
        addon = FakeAddon({k: "old" for k in persisted})

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "legacy-settings.json")

            def _profile_path(*parts):
                return os.path.join(tmp, *parts)

            with patch("segment_types.profile_path", side_effect=_profile_path):
                set_catalog_for_tests(None)
                types = seeded_builtin_types()
                types.append(
                    {
                        "id": "localhook",
                        "label": "Localhook",
                        "skip_mode": "ask",
                        "edl_action": 30,
                        "aliases": ["Localhook"],
                        "builtin": False,
                        "online_bucket": None,
                        "edl_read_aliases": [],
                    }
                )
                self.assertTrue(save_catalog(types))
                payload = {
                    "schema": sb.SCHEMA,
                    "addon_id": sb.ADDON_ID,
                    "addon_version_exported": "6.9.0",
                    "settings": {
                        sample: "new-value",
                        "segment_always_skip": "intro",
                        "segment_ask_skip": "cold open",
                        "custom_segment_keywords": "myhook",
                        "edl_action_mapping": "21:myhook",
                        "not_a_real_setting_xyz": "nope",
                    },
                }
                with open(path, "w", encoding="utf-8") as fp:
                    json.dump(payload, fp)
                applied, bad, note = sb.import_from_path(addon, path)
                live = {t["id"]: t for t in ensure_catalog()}

        self.assertEqual(addon.getSetting(sample), "new-value")
        self.assertNotIn("segment_always_skip", addon._store)
        self.assertEqual(bad, 1)
        self.assertGreaterEqual(applied, 5)
        self.assertIn("Legacy skip lists applied", note)
        self.assertEqual(live["intro"]["skip_mode"], "auto")
        self.assertEqual(live["prologue"]["skip_mode"], "ask")
        self.assertEqual(live["myhook"]["edl_action"], 21)
        self.assertEqual(live["localhook"]["skip_mode"], "ask")
        self.assertEqual(live["recap"]["skip_mode"], "ask")

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

    def test_all_minimal_plate_textures_are_settings_options(self):
        """Every minimal_*.png / .jpg in media must be a Minimal plate picker value."""
        media = ROOT / "resources" / "skins" / "default" / "media"
        on_disk = sorted(
            name
            for name in os.listdir(media)
            if name.startswith("minimal_")
            and name.lower().endswith((".png", ".jpg", ".jpeg"))
        )
        tree = ET.parse(SETTINGS_XML)
        wired = []
        for setting in tree.getroot().iter("setting"):
            if setting.get("id") != "minimal_button_style":
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
