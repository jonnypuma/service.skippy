# -*- coding: utf-8 -*-
"""Segment types catalog, migration, skip/EDL maps, editor draft save."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from xml.etree import ElementTree as ET

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

from segment_types import (
    SCHEMA,
    add_alias,
    add_custom_type,
    catalog_stamp,
    clone_types,
    delete_custom_type,
    edl_write_action,
    ensure_catalog,
    export_catalog,
    get_edl_label_to_action_map,
    get_edl_type_map,
    get_user_skip_mode,
    merge_catalog_from_backup,
    migrate_from_legacy_settings,
    resolve_segment_type,
    save_catalog,
    seeded_builtin_types,
    set_catalog_for_tests,
    set_edl_action,
    validate_types,
)


class _LegacyAddon:
    def __init__(self, values):
        self._values = values

    def getSetting(self, key):
        return self._values.get(key, "")


class CatalogSeedTests(unittest.TestCase):
    def tearDown(self):
        set_catalog_for_tests(None)

    def test_builtin_skip_and_edl_defaults(self):
        types = seeded_builtin_types()
        by_id = {t["id"]: t for t in types}
        self.assertEqual(by_id["intro"]["skip_mode"], "ask")
        self.assertEqual(by_id["intro"]["edl_action"], 5)
        self.assertEqual(by_id["commercial"]["skip_mode"], "auto")
        self.assertEqual(by_id["commercial"]["edl_action"], 7)
        self.assertEqual(by_id["credits"]["skip_mode"], "never")
        self.assertEqual(sorted(by_id["commercial"]["edl_read_aliases"]), [6, 16])
        self.assertIn("outro", [a.lower() for a in by_id["credits"]["aliases"]])
        self.assertIn("cold open", [a.lower() for a in by_id["prologue"]["aliases"]])

    def test_alias_exclusivity(self):
        types = seeded_builtin_types()
        err = add_alias(types, "intro", "recap")
        self.assertIn("already used", err)
        err = add_alias(types, "intro", "opening credits extra")
        self.assertIsNone(err)

    def test_edl_collision(self):
        types = seeded_builtin_types()
        err = set_edl_action(types, "intro", 7)
        self.assertIn("already used", err)
        err = set_edl_action(types, "intro", 6)
        self.assertIn("already used", err)
        err = set_edl_action(types, "intro", 42)
        self.assertIsNone(err)
        self.assertEqual(next(t["edl_action"] for t in types if t["id"] == "intro"), 42)

    def test_unmatched_never(self):
        set_catalog_for_tests(seeded_builtin_types())
        self.assertEqual(get_user_skip_mode("not-a-real-type"), "never")
        self.assertIsNone(resolve_segment_type("mystery chapter"))

    def test_resolve_aliases(self):
        set_catalog_for_tests(seeded_builtin_types())
        self.assertEqual(resolve_segment_type("opening")["id"], "intro")
        self.assertEqual(resolve_segment_type("ads")["id"], "commercial")
        self.assertEqual(resolve_segment_type("cold open")["id"], "prologue")
        self.assertEqual(resolve_segment_type("outro")["id"], "credits")


class MigrationTests(unittest.TestCase):
    def test_legacy_comma_settings(self):
        addon = _LegacyAddon(
            {
                "segment_always_skip": "ads,commercial",
                "segment_ask_skip": "intro,cold open",
                "segment_never_skip": "outro,credits",
                "custom_segment_keywords": "intro,outro,ads,cold open,myhook",
                "edl_action_mapping": "20:myhook",
            }
        )
        types = migrate_from_legacy_settings(addon)
        by_id = {t["id"]: t for t in types}
        self.assertEqual(by_id["commercial"]["skip_mode"], "auto")
        self.assertEqual(by_id["intro"]["skip_mode"], "ask")
        self.assertEqual(by_id["credits"]["skip_mode"], "never")
        self.assertEqual(by_id["prologue"]["skip_mode"], "ask")
        self.assertIn("myhook", by_id)
        self.assertFalse(by_id["myhook"]["builtin"])
        self.assertEqual(by_id["myhook"]["skip_mode"], "never")
        self.assertEqual(by_id["myhook"]["edl_action"], 20)


class CatalogApiTests(unittest.TestCase):
    def tearDown(self):
        set_catalog_for_tests(None)

    def test_skip_and_edl_maps(self):
        set_catalog_for_tests(seeded_builtin_types())
        self.assertEqual(get_user_skip_mode("commercial"), "auto")
        self.assertEqual(get_user_skip_mode("intro"), "ask")
        self.assertEqual(get_user_skip_mode("credits"), "never")
        self.assertEqual(get_user_skip_mode("opening"), "ask")
        type_map = get_edl_type_map()
        self.assertEqual(type_map[7], "commercial")
        self.assertEqual(type_map[6], "commercial")
        self.assertEqual(type_map[16], "commercial")
        self.assertEqual(type_map[13], "credits")
        self.assertEqual(type_map[17], "prologue")
        labels = get_edl_label_to_action_map()
        self.assertEqual(labels["ads"], 7)
        self.assertEqual(labels["outro"], 8)
        self.assertEqual(labels["cold_open"], 10)
        self.assertEqual(edl_write_action("ad"), 7)
        self.assertEqual(edl_write_action("credits", 13), 8)

    def test_editor_save_writes_cancel_does_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "segment_types.json")
            with patch("segment_types.catalog_path", return_value=path):
                set_catalog_for_tests(None)
                types = seeded_builtin_types()
                self.assertTrue(save_catalog(types))
                self.assertTrue(os.path.isfile(path))
                draft = clone_types(ensure_catalog())
                row, err = add_custom_type(draft, "Hook")
                self.assertIsNone(err)
                self.assertIsNotNone(row)
                with open(path, encoding="utf-8") as handle:
                    reloaded = json.loads(handle.read())
                ids = [t["id"] for t in reloaded["types"]]
                self.assertNotIn("hook", ids)
                self.assertTrue(save_catalog(draft))
                with open(path, encoding="utf-8") as handle:
                    reloaded = json.loads(handle.read())
                self.assertEqual(reloaded["schema"], SCHEMA)
                self.assertIn("hook", [t["id"] for t in reloaded["types"]])
                self.assertIsNone(validate_types(draft))
                self.assertIsNotNone(delete_custom_type(seeded_builtin_types(), "intro"))

    def test_classify_uses_catalog_online_bucket(self):
        set_catalog_for_tests(seeded_builtin_types())
        from online_segment_upload import classify_segment_label_normalized

        self.assertEqual(
            classify_segment_label_normalized("opening")[0], "intro"
        )
        self.assertEqual(classify_segment_label_normalized("outro")[0], "credits")
        self.assertIsNone(classify_segment_label_normalized("cold open"))
        self.assertIsNone(classify_segment_label_normalized("ads"))


class OverrideAndStampTests(unittest.TestCase):
    def tearDown(self):
        set_catalog_for_tests(None)

    def test_override_lookup_by_alias(self):
        set_catalog_for_tests(seeded_builtin_types())
        from per_show_overrides import MODE_AUTO, lookup_override, save_override
        import skippy_profile_store

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(skippy_profile_store, "profile_dir", return_value=tmp):
                import per_show_overrides as ov

                ov.clear_cache()
                self.assertTrue(save_override("tv_tmdb_1", "opening", MODE_AUTO, "Show"))
                self.assertEqual(lookup_override("tv_tmdb_1", "intro"), MODE_AUTO)
                self.assertEqual(lookup_override("tv_tmdb_1", "opening"), MODE_AUTO)
                path = os.path.join(tmp, "show_overrides", "tv_tmdb_1.json")
                with open(path, encoding="utf-8") as handle:
                    data = json.loads(handle.read())
                self.assertIn("intro", data["segments"])
                self.assertNotIn("opening", data["segments"])

    def test_catalog_stamp_includes_skip_mode(self):
        types = seeded_builtin_types()
        set_catalog_for_tests(types)
        first = catalog_stamp()
        types[0]["skip_mode"] = "never" if types[0]["skip_mode"] != "never" else "ask"
        set_catalog_for_tests(types)
        self.assertNotEqual(catalog_stamp(), first)


class BackupAndSkinTests(unittest.TestCase):
    def tearDown(self):
        set_catalog_for_tests(None)

    def test_profile_backup_includes_segment_types(self):
        from skippy_profile_backup import export_to_path, import_merge_from_path
        import skippy_profile_store
        import skippy_stats
        import per_show_overrides

        with tempfile.TemporaryDirectory() as tmp:
            prof = os.path.join(tmp, "profile")
            os.makedirs(prof)
            backup_path = os.path.join(tmp, "backup.json")
            with patch.object(skippy_profile_store, "profile_dir", return_value=prof):
                with patch(
                    "online_segment_upload._history_path",
                    return_value=os.path.join(prof, "online_upload_submissions.json"),
                ):
                    set_catalog_for_tests(None)
                    skippy_stats.clear_cache()
                    per_show_overrides.clear_cache()
                    types = seeded_builtin_types()
                    self.assertTrue(save_catalog(types))
                    addon = MagicMock()
                    addon.getAddonInfo.side_effect = lambda k: {
                        "version": "7.0.0",
                        "profile": prof,
                    }.get(k, "")
                    counts = export_to_path(addon, backup_path)
                    self.assertGreaterEqual(counts["segment_types"], 11)
                    with open(backup_path, encoding="utf-8") as fp:
                        payload = json.load(fp)
                    self.assertIn("segment_types", payload)
                    self.assertEqual(payload["segment_types"]["schema"], SCHEMA)
                    payload["segment_types"]["types"] = [
                        t
                        for t in payload["segment_types"]["types"]
                        if t["id"] != "featurette"
                    ]
                    payload["segment_types"]["types"].append(
                        {
                            "id": "hook",
                            "label": "Hook",
                            "skip_mode": "ask",
                            "edl_action": 40,
                            "aliases": ["Hook"],
                            "builtin": False,
                        }
                    )
                    with open(backup_path, "w", encoding="utf-8") as fp:
                        json.dump(payload, fp)
                    summary, _ = import_merge_from_path(addon, backup_path)
                    self.assertTrue(summary["segment_types_merged"])
                    live = {t["id"] for t in ensure_catalog()}
                    self.assertIn("hook", live)
                    self.assertIn("featurette", live)

    def test_editor_xml_ids(self):
        root = os.path.dirname(os.path.dirname(__file__))
        needed = {"5200", "5201", "5210", "5220", "5221", "5222", "5223", "5230", "5231", "5232"}
        for folder in ("720p", "1080i"):
            path = os.path.join(
                root, "resources", "skins", "default", folder, "SegmentTypesEditor.xml"
            )
            tree = ET.parse(path)
            ids = {el.get("id") for el in tree.iter("control") if el.get("id")}
            self.assertTrue(needed.issubset(ids), folder)


if __name__ == "__main__":
    unittest.main()
