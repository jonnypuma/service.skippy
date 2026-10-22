# -*- coding: utf-8 -*-
"""Skip dialog presets."""

import os
import re
import tempfile
import unittest
from unittest.mock import patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import skip_dialog_presets as sp  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MEDIA = os.path.join(ROOT, "resources", "skins", "default", "media")


class PresetTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        path = os.path.join(self._tmp.name, "skip_dialog_presets.json")
        patcher = patch.object(sp, "_store_path", lambda: path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)


class BuiltinTests(PresetTestCase):
    def test_every_texture_exists(self):
        for name, values in sp.builtin_presets():
            for key in ("button_focus_style", "progress_bar_style", "minimal_button_style"):
                if key in values:
                    self.assertTrue(
                        os.path.isfile(os.path.join(MEDIA, values[key])),
                        "%s: %s missing" % (name, values[key]),
                    )

    def test_names_unique_and_values_complete(self):
        names = [n for n, _ in sp.builtin_presets()]
        self.assertEqual(len(names), len(set(names)))
        for name, values in sp.builtin_presets():
            self.assertEqual(
                set(values), set(sp.relevant_keys(values["skip_dialog_mode"])), name
            )
            self.assertEqual(values, sp.sanitize_values(values), name)

    def test_presets_do_not_touch_position_or_behaviour(self):
        for _n, values in sp.builtin_presets():
            for key in ("skip_dialog_position", "minimal_skip_dialog_position",
                        "skip_overlapping_segments", "progress_bar_countdown"):
                self.assertNotIn(key, values)

    def test_non_minimal_presets_hide_the_close_button(self):
        for name, values in sp.builtin_presets():
            if values["skip_dialog_mode"] != "Minimal":
                self.assertTrue(values["hide_close_button"], name)

    def test_apply_then_detect(self):
        for name, values in sp.builtin_presets():
            draft = {"skip_dialog_position": "TopLeft"}
            sp.apply_preset(draft, values)
            self.assertEqual(sp.detect_preset(draft), name)
            self.assertEqual(draft["skip_dialog_position"], "TopLeft")

    def test_modified_draft_is_not_a_preset(self):
        draft = {}
        sp.apply_preset(draft, dict(sp.builtin_presets())["Modern"])
        draft["progress_bar_height"] = 7
        self.assertIsNone(sp.detect_preset(draft))

    def test_cycle_wraps(self):
        names = [n for n, _ in sp.builtin_presets()]
        draft = {}
        sp.apply_preset(draft, dict(sp.builtin_presets())[names[-1]])
        self.assertEqual(sp.cycle_preset(draft, 1)[0], names[0])
        sp.apply_preset(draft, dict(sp.builtin_presets())[names[0]])
        self.assertEqual(sp.cycle_preset(draft, -1)[0], names[-1])


class UserPresetTests(PresetTestCase):
    def test_save_load_delete(self):
        draft = {}
        sp.apply_preset(draft, dict(sp.builtin_presets())["Modern"])
        draft["progress_bar_height"] = 9
        self.assertEqual(sp.save_user_preset("  My   look ", draft), (True, ""))
        self.assertIn("My look", sp.load_user_presets())
        self.assertEqual(sp.detect_preset(draft), "My look")
        self.assertEqual(
            [n for n, _v, b in sp.list_presets() if not b], ["My look"]
        )
        self.assertTrue(sp.delete_user_preset("My look"))
        self.assertEqual(sp.load_user_presets(), {})
        self.assertFalse(sp.delete_user_preset("My look"))

    def test_rejects_bad_names(self):
        self.assertEqual(sp.save_user_preset("   ", {}), (False, "name"))
        self.assertEqual(sp.save_user_preset("modern", {}), (False, "builtin"))

    def test_overwrite_is_case_insensitive(self):
        sp.save_user_preset("Evening", {"skip_dialog_font_color": "FF000000"})
        sp.save_user_preset("evening", {"skip_dialog_font_color": "FFE5392F"})
        user = sp.load_user_presets()
        self.assertEqual(list(user), ["evening"])
        self.assertEqual(user["evening"]["skip_dialog_font_color"], "FFE5392F")

    def test_minimal_snapshot_only_keeps_minimal_keys(self):
        draft = {"skip_dialog_mode": "Minimal", "minimal_button_style": "minimal_flat_blue_640.png"}
        sp.save_user_preset("Tiny", draft)
        vals = sp.load_user_presets()["Tiny"]
        self.assertEqual(set(vals), set(sp.relevant_keys("Minimal")))
        self.assertEqual(vals["minimal_button_style"], "minimal_flat_blue_640.png")

    def test_corrupt_entries_are_dropped(self):
        sp.write_json(sp._store_path(), {"presets": {
            "Bad": {"values": {"skip_card_opacity": "x"}},
            "Ok": {"values": {"skip_dialog_mode": "Full", "skip_card_opacity": 500}},
            "Modern": {"values": {"skip_dialog_mode": "Full"}},
        }})
        user = sp.load_user_presets()
        self.assertEqual(list(user), ["Ok"])
        self.assertEqual(user["Ok"]["skip_card_opacity"], 100)

    def test_backup_merge_keeps_existing(self):
        sp.save_user_preset("Mine", {"skip_dialog_font_color": "FF000000"})
        blob = {"presets": {
            "Mine": {"values": {"skip_dialog_mode": "Full", "skip_dialog_font_color": "FFFFFFFF"}},
            "New": {"values": {"skip_dialog_mode": "Full"}},
        }}
        self.assertEqual(sp.merge_user_presets_from_backup(blob), 1)
        user = sp.load_user_presets()
        self.assertEqual(user["Mine"]["skip_dialog_font_color"], "FF000000")
        self.assertIn("New", user)
        self.assertEqual(sp.merge_user_presets_from_backup("junk"), 0)


class TextureTests(unittest.TestCase):
    def test_new_flat_focus_textures_are_nine_sliced(self):
        from skip_dialog_appearance import button_focus_nine_slice_border

        for fn in os.listdir(MEDIA):
            if re.match(r"button_focus_(flat|glass|outline)_", fn):
                self.assertEqual(button_focus_nine_slice_border(fn), "12,12,12,12", fn)
        self.assertIsNone(button_focus_nine_slice_border("button_focus_underline_white.png"))


if __name__ == "__main__":
    unittest.main()
