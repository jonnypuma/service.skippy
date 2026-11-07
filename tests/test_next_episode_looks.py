# -*- coding: utf-8 -*-
"""Saved popup looks and the Looks… menu of the Customize next episode popup screen."""

import json
import os
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import next_episode_appearance as app
import next_episode_customize_ui as cust
import next_episode_look as look_mod
import next_episode_looks_ui as ui
import next_episode_saved_looks as sl
import skippy_profile_backup as backup
import skippy_profile_store
from tests.test_next_episode_mock import _modal

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SKINS = os.path.join(ROOT, "resources", "skins", "default")

TEXT = look_mod.override_options(look_mod.KEY_TEXT_COLOR)[1]
BAR = look_mod.override_options(look_mod.KEY_BAR_STYLE)[1]


def draft(**changes):
    return dict(app.DEFAULT_DRAFT, **changes)


def glass(**changes):
    """A draft with a look chosen and a couple of parts changed on top of it."""
    values = {look_mod.KEY_LOOK: "Glass", look_mod.KEY_TEXT_COLOR: TEXT,
              look_mod.KEY_ALL_CAPS: look_mod.CAPS_ON}
    values.update(changes)
    return draft(**values)


class _ProfileTempDir(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        patcher = patch.object(skippy_profile_store, "profile_dir", return_value=self._tmp.name)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)

    def path(self):
        return os.path.join(self._tmp.name, sl.USER_LOOKS_FILE)

    def write_raw(self, payload):
        with open(self.path(), "w", encoding="utf-8") as fh:
            json.dump(payload, fh)


class ValueTests(unittest.TestCase):
    def test_a_name_is_trimmed_squeezed_and_capped(self):
        self.assertEqual(sl.clean_name("  My   look "), "My look")
        self.assertEqual(len(sl.clean_name("x" * 100)), sl.MAX_NAME_LEN)
        self.assertEqual(sl.clean_name(None), "")
        self.assertEqual(sl.clean_name("   "), "")

    def test_a_look_is_the_look_and_the_six_parts_changed_on_top_of_it(self):
        self.assertEqual(set(sl.LOOK_KEYS), {look_mod.KEY_LOOK, *look_mod.OVERRIDE_KEYS})
        self.assertEqual(len(sl.LOOK_KEYS), 7)

    def test_the_snapshot_leaves_out_placement_and_behaviour(self):
        shot = sl.snapshot(glass(**{app.KEY_POSITION: "TopLeft", app.KEY_THUMBNAIL: False,
                                    app.KEY_FOCUS: app.FOCUS_CLOSE}))
        self.assertEqual(set(shot), set(sl.LOOK_KEYS))
        self.assertEqual(shot[look_mod.KEY_LOOK], "Glass")
        self.assertEqual(shot[look_mod.KEY_TEXT_COLOR], TEXT)
        self.assertEqual(shot[look_mod.KEY_BAR_STYLE], look_mod.FOLLOW_LOOK)

    def test_an_unknown_look_gives_nothing(self):
        self.assertEqual(sl.sanitize_values({look_mod.KEY_LOOK: "Nope"}), {})
        self.assertEqual(sl.sanitize_values({}), {})
        self.assertEqual(sl.sanitize_values(None), {})
        self.assertEqual(sl.sanitize_values(["Glass"]), {})
        self.assertEqual(sl.snapshot(None), {})

    def test_a_part_that_is_not_understood_follows_the_look(self):
        values = sl.sanitize_values({look_mod.KEY_LOOK: "Glass", look_mod.KEY_TEXT_COLOR: "Nope",
                                     look_mod.KEY_BAR_STYLE: BAR})
        self.assertEqual(values[look_mod.KEY_TEXT_COLOR], look_mod.FOLLOW_LOOK)
        self.assertEqual(values[look_mod.KEY_HEADING_COLOR], look_mod.FOLLOW_LOOK)
        self.assertEqual(values[look_mod.KEY_BAR_STYLE], BAR)

    def test_spelling_and_case_do_not_matter_but_the_stored_form_is_used(self):
        values = sl.sanitize_values({look_mod.KEY_LOOK: "big bold"})
        self.assertEqual(values[look_mod.KEY_LOOK], "BigBold")
        self.assertEqual(sl.sanitize_values({look_mod.KEY_LOOK: " glass "})[look_mod.KEY_LOOK], "Glass")

    def test_a_built_in_look_is_a_look_with_nothing_changed_on_top(self):
        self.assertEqual(sl.builtin_look_name(sl.snapshot(draft())), "Default")
        self.assertEqual(
            sl.builtin_look_name(sl.snapshot(draft(**{look_mod.KEY_LOOK: look_mod.LOOK_SKIP_DIALOG}))),
            "Same as skip dialog",
        )
        self.assertEqual(sl.builtin_look_name(sl.snapshot(draft(**{look_mod.KEY_LOOK: "Glass"}))), "Glass")
        self.assertIsNone(sl.builtin_look_name(sl.snapshot(glass())))
        self.assertIsNone(sl.builtin_look_name({}))
        self.assertIsNone(sl.builtin_look_name(None))

    def test_the_names_of_the_built_in_looks_are_all_taken(self):
        taken = sl.builtin_names()
        self.assertIn("default", taken)
        self.assertIn("same as skip dialog", taken)
        self.assertIn("big & bold", taken)
        self.assertEqual(len(taken), len(look_mod.LOOK_LABELS))

    def test_applying_changes_the_look_parts_and_nothing_else(self):
        target = draft(**{app.KEY_POSITION: "TopLeft", app.KEY_PROGRESS: False,
                          app.KEY_FOCUS: app.FOCUS_CLOSE})
        before = dict(target)
        self.assertTrue(sl.apply_look(target, sl.snapshot(glass())))
        for key in sl.LOOK_KEYS:
            self.assertEqual(target[key], sl.snapshot(glass())[key], key)
        for key in set(before) - set(sl.LOOK_KEYS):
            self.assertEqual(target[key], before[key], key)

    def test_values_that_are_not_a_look_change_nothing(self):
        target = glass()
        before = dict(target)
        self.assertFalse(sl.apply_look(target, {look_mod.KEY_LOOK: "Nope"}))
        self.assertFalse(sl.apply_look(target, None))
        self.assertEqual(target, before)


class StoreTests(_ProfileTempDir):
    def test_a_saved_look_comes_back(self):
        self.assertEqual(sl.save_user_look("Evening", glass()), (True, sl.SAVED))
        self.assertEqual(sl.load_user_looks(), {"Evening": sl.snapshot(glass())})

    def test_the_file_holds_the_schema_and_only_the_look_parts(self):
        sl.save_user_look("Evening", glass(**{app.KEY_POSITION: "TopLeft"}))
        with open(self.path(), encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertEqual(data["schema"], sl.USER_LOOKS_SCHEMA)
        self.assertEqual(set(data["looks"]["Evening"]["values"]), set(sl.LOOK_KEYS))

    def test_the_file_is_written_with_a_backup_of_the_previous_one(self):
        with patch.object(sl, "write_json", return_value=True) as write:
            sl.save_user_look("Evening", glass())
        self.assertIs(write.call_args.kwargs.get("keep_backup"), True)

    def test_an_empty_name_is_refused(self):
        self.assertEqual(sl.save_user_look("   ", glass()), (False, sl.ERR_NAME))
        self.assertEqual(sl.save_user_look(None, glass()), (False, sl.ERR_NAME))
        self.assertFalse(os.path.exists(self.path()))

    def test_the_name_of_a_built_in_look_is_refused_in_any_case(self):
        for name in ("Glass", "glass", "DEFAULT", "Same as skip dialog", "big  &  bold"):
            self.assertEqual(sl.save_user_look(name, glass()), (False, sl.ERR_BUILTIN_NAME), name)
        self.assertFalse(os.path.exists(self.path()))

    def test_the_same_name_replaces_the_look_whatever_its_case(self):
        sl.save_user_look("Evening", glass())
        sl.save_user_look("evening", glass(**{look_mod.KEY_BAR_STYLE: BAR}))
        looks = sl.load_user_looks()
        self.assertEqual(list(looks), ["evening"])
        self.assertEqual(looks["evening"][look_mod.KEY_BAR_STYLE], BAR)

    def test_the_number_of_saved_looks_is_capped(self):
        with patch.object(sl, "MAX_USER_LOOKS", 2):
            self.assertTrue(sl.save_user_look("A", glass())[0])
            self.assertTrue(sl.save_user_look("B", glass())[0])
            self.assertEqual(sl.save_user_look("C", glass()), (False, sl.ERR_LIMIT))
            self.assertTrue(sl.save_user_look("a", glass(**{look_mod.KEY_BAR_STYLE: BAR}))[0])
        self.assertEqual(sorted(sl.load_user_looks()), ["B", "a"])

    def test_a_failed_write_is_reported_and_keeps_what_was_saved(self):
        sl.save_user_look("Evening", glass())
        with patch.object(sl, "write_json", return_value=False):
            self.assertEqual(sl.save_user_look("Other", glass()), (False, sl.ERR_WRITE))
        self.assertEqual(list(sl.load_user_looks()), ["Evening"])

    def test_a_draft_without_a_known_look_is_not_saved(self):
        self.assertEqual(sl.save_user_look("Odd", {look_mod.KEY_LOOK: "Nope"}), (False, sl.ERR_WRITE))
        self.assertFalse(os.path.exists(self.path()))

    def test_a_missing_or_broken_file_has_no_looks(self):
        self.assertEqual(sl.load_user_looks(), {})
        with open(self.path(), "w", encoding="utf-8") as fh:
            fh.write("{not json")
        self.assertEqual(sl.load_user_looks(), {})
        self.write_raw(["not", "a", "dict"])
        self.assertEqual(sl.load_user_looks(), {})
        self.write_raw({"looks": ["x"]})
        self.assertEqual(sl.load_user_looks(), {})

    def test_entries_that_cannot_be_used_are_skipped_on_load(self):
        good = {"values": sl.snapshot(glass())}
        self.write_raw({"looks": {
            "Good": good,
            "Unknown look": {"values": {look_mod.KEY_LOOK: "Nope"}},
            "Not a dict": "x",
            "Glass": good,  # the name of a built-in look
            "   ": good,
            "No values": {},
        }})
        self.assertEqual(sl.load_user_looks(), {"Good": sl.snapshot(glass())})

    def test_the_list_is_sorted_without_regard_to_case(self):
        for name in ("beta", "Alpha", "Gamma"):
            sl.save_user_look(name, glass())
        self.assertEqual([n for n, _v in sl.list_user_looks()], ["Alpha", "beta", "Gamma"])

    def test_a_look_is_found_by_its_values(self):
        sl.save_user_look("Evening", glass())
        self.assertEqual(sl.find_saved_look(sl.snapshot(glass())), "Evening")
        self.assertEqual(sl.detect_saved_look(glass()), "Evening")
        self.assertEqual(sl.detect_saved_look(glass(**{app.KEY_POSITION: "TopLeft"})), "Evening")
        self.assertIsNone(sl.detect_saved_look(glass(**{look_mod.KEY_BAR_STYLE: BAR})))
        self.assertIsNone(sl.detect_saved_look(draft()))
        self.assertIsNone(sl.find_saved_look({}))

    def test_deleting_removes_only_that_look(self):
        sl.save_user_look("A", glass())
        sl.save_user_look("B", glass(**{look_mod.KEY_BAR_STYLE: BAR}))
        self.assertTrue(sl.delete_user_look("A"))
        self.assertEqual(list(sl.load_user_looks()), ["B"])
        self.assertFalse(sl.delete_user_look("A"))
        self.assertFalse(sl.delete_user_look("nobody"))


class BackupTests(_ProfileTempDir):
    def blob(self, **looks):
        return {"schema": sl.USER_LOOKS_SCHEMA,
                "looks": {name: {"values": values} for name, values in looks.items()}}

    def test_the_export_holds_every_saved_look(self):
        sl.save_user_look("Evening", glass())
        self.assertEqual(sl.export_user_looks(), self.blob(Evening=sl.snapshot(glass())))

    def test_the_merge_adds_new_looks(self):
        sl.save_user_look("Mine", glass())
        other = sl.snapshot(glass(**{look_mod.KEY_BAR_STYLE: BAR}))
        self.assertEqual(sl.merge_user_looks_from_backup(self.blob(Theirs=other)), 1)
        self.assertEqual(sorted(sl.load_user_looks()), ["Mine", "Theirs"])

    def test_a_name_already_saved_is_kept_as_it_is(self):
        sl.save_user_look("Mine", glass())
        other = sl.snapshot(glass(**{look_mod.KEY_BAR_STYLE: BAR}))
        self.assertEqual(sl.merge_user_looks_from_backup(self.blob(mine=other)), 0)
        self.assertEqual(sl.load_user_looks(), {"Mine": sl.snapshot(glass())})

    def test_a_look_already_saved_under_another_name_is_not_added_again(self):
        sl.save_user_look("Mine", glass())
        self.assertEqual(sl.merge_user_looks_from_backup(self.blob(Copy=sl.snapshot(glass()))), 0)
        self.assertEqual(list(sl.load_user_looks()), ["Mine"])

    def test_two_identical_looks_in_one_backup_are_added_once(self):
        values = sl.snapshot(glass())
        self.assertEqual(sl.merge_user_looks_from_backup(self.blob(One=values, Two=values)), 1)

    def test_unusable_entries_are_skipped(self):
        values = sl.snapshot(glass())
        blob = self.blob(Glass=values, Odd={look_mod.KEY_LOOK: "Nope"})
        blob["looks"]["Plain"] = "x"
        blob["looks"]["  "] = {"values": values}
        self.assertEqual(sl.merge_user_looks_from_backup(blob), 0)
        self.assertFalse(os.path.exists(self.path()))

    def test_something_that_is_not_a_backup_adds_nothing(self):
        for blob in (None, [], "x", {}, {"looks": []}):
            self.assertEqual(sl.merge_user_looks_from_backup(blob), 0, blob)

    def test_the_merge_stops_at_the_limit(self):
        first = sl.snapshot(glass())
        second = sl.snapshot(glass(**{look_mod.KEY_BAR_STYLE: BAR}))
        with patch.object(sl, "MAX_USER_LOOKS", 1):
            self.assertEqual(sl.merge_user_looks_from_backup(self.blob(A=first, B=second)), 1)
        self.assertEqual(len(sl.load_user_looks()), 1)

    def test_a_failed_write_adds_nothing(self):
        with patch.object(sl, "write_json", return_value=False):
            self.assertEqual(sl.merge_user_looks_from_backup(self.blob(A=sl.snapshot(glass()))), 0)

    def test_the_profile_backup_carries_the_looks_to_another_profile(self):
        sl.save_user_look("Evening", glass())
        addon = MagicMock()
        addon.getAddonInfo.return_value = "x"
        dump = os.path.join(self._tmp.name, "backup.json")
        backup.export_to_path(addon, dump)
        with open(dump, encoding="utf-8") as fh:
            self.assertIn("Evening", fh.read())
        self.assertTrue(sl.delete_user_look("Evening"))
        summary, _note = backup.import_merge_from_path(addon, dump)
        self.assertEqual(summary["looks_added"], 1)
        self.assertEqual(sl.load_user_looks(), {"Evening": sl.snapshot(glass())})

    def test_an_older_backup_without_looks_restores_fine(self):
        addon = MagicMock()
        addon.getAddonInfo.return_value = "x"
        dump = os.path.join(self._tmp.name, "backup.json")
        backup.export_to_path(addon, dump)
        with open(dump, encoding="utf-8") as fh:
            data = json.load(fh)
        del data["next_episode_looks"]
        with open(dump, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        summary, _note = backup.import_merge_from_path(addon, dump)
        self.assertEqual(summary["looks_added"], 0)


class _MenuBase(_ProfileTempDir):
    """Runs the menu with scripted answers from the dialogs."""

    def run_menu(self, target, *, select=(-1,), inputs=(), yesno=()):
        self.dialog = MagicMock()
        self.dialog.select.side_effect = list(select)
        self.dialog.input.side_effect = list(inputs)
        self.dialog.yesno.side_effect = list(yesno)
        with patch.object(ui.xbmcgui, "Dialog", return_value=self.dialog), \
                patch.object(ui, "notify_skippy") as notify:
            self.notify = notify
            changed = ui.present_looks_menu(None, target)
        return changed

    def toasts(self):
        return [call.args[1] for call in self.notify.call_args_list]

    def menu_items(self):
        return self.dialog.select.call_args_list[0].args[1]


class MenuListTests(_MenuBase):
    def test_without_saved_looks_the_menu_offers_reset_and_save(self):
        self.run_menu(draft())
        self.assertEqual(self.menu_items(), ["Reset to defaults", "Save this look…"])
        self.assertEqual(self.dialog.select.call_args_list[0].args[0], "Popup looks")

    def test_saved_looks_are_listed_between_reset_and_save_with_a_delete_item(self):
        sl.save_user_look("beta", glass())
        sl.save_user_look("Alpha", glass(**{look_mod.KEY_BAR_STYLE: BAR}))
        self.run_menu(draft())
        self.assertEqual(self.menu_items(), ["Reset to defaults", "Alpha", "beta", "Save this look…",
                                             "Delete a saved look…"])

    def test_the_look_on_screen_is_ticked_and_preselected(self):
        sl.save_user_look("Alpha", glass(**{look_mod.KEY_BAR_STYLE: BAR}))
        sl.save_user_look("beta", glass())
        self.run_menu(glass())
        self.assertEqual(self.menu_items()[1:3], ["Alpha", "✓ beta"])
        self.assertEqual(self.dialog.select.call_args_list[0].kwargs.get("preselect"), 2)

    def test_nothing_is_preselected_when_the_look_is_not_saved(self):
        sl.save_user_look("beta", glass())
        self.run_menu(draft())
        self.assertEqual(self.dialog.select.call_args_list[0].kwargs.get("preselect"), -1)

    def test_closing_the_menu_changes_nothing(self):
        target = glass()
        before = dict(target)
        self.assertFalse(self.run_menu(target, select=(-1,)))
        self.assertEqual(target, before)


class ResetAndLoadTests(_MenuBase):
    def test_reset_puts_every_setting_of_the_screen_back_to_its_default(self):
        target = glass(**{app.KEY_POSITION: "TopLeft", app.KEY_THUMBNAIL: False,
                          app.KEY_PROGRESS: False, app.KEY_FOCUS: app.FOCUS_CLOSE,
                          app.KEY_STYLE: app.STYLE_NATIVE})
        self.assertTrue(self.run_menu(target, select=(0,)))
        self.assertEqual(target, app.DEFAULT_DRAFT)

    def test_reset_asks_nothing_and_writes_nothing_yet(self):
        sl.save_user_look("Keep", glass())
        self.run_menu(glass(), select=(0,))
        self.dialog.yesno.assert_not_called()
        self.assertEqual(list(sl.load_user_looks()), ["Keep"])
        self.assertEqual(self.toasts(), [])

    def test_reset_is_saved_by_the_normal_save_of_the_screen(self):
        original = glass(**{app.KEY_POSITION: "TopLeft"})
        target = dict(original)
        self.run_menu(target, select=(0,))
        self.assertEqual(
            cust.changed_payload(target, original),
            {k: v for k, v in app.draft_setting_payload(app.DEFAULT_DRAFT).items()
             if app.draft_setting_payload(original).get(k) != v},
        )
        self.assertIn(app.KEY_POSITION, cust.changed_payload(target, original))
        self.assertIn(look_mod.KEY_LOOK, cust.changed_payload(target, original))

    def test_a_saved_look_is_loaded_without_touching_placement_or_behaviour(self):
        sl.save_user_look("Evening", glass(**{look_mod.KEY_BAR_STYLE: BAR}))
        target = draft(**{app.KEY_POSITION: "TopLeft", app.KEY_PROGRESS: False})
        self.assertTrue(self.run_menu(target, select=(1,)))
        self.assertEqual(target[look_mod.KEY_LOOK], "Glass")
        self.assertEqual(target[look_mod.KEY_BAR_STYLE], BAR)
        self.assertEqual(target[look_mod.KEY_TEXT_COLOR], TEXT)
        self.assertEqual(target[app.KEY_POSITION], "TopLeft")
        self.assertFalse(target[app.KEY_PROGRESS])

    def test_loading_a_look_replaces_what_was_changed_on_top_of_the_old_look(self):
        sl.save_user_look("Plain glass", draft(**{look_mod.KEY_LOOK: "Glass", look_mod.KEY_BAR_STYLE: BAR}))
        target = glass()
        self.run_menu(target, select=(1,))
        self.assertEqual(target[look_mod.KEY_TEXT_COLOR], look_mod.FOLLOW_LOOK)
        self.assertEqual(target[look_mod.KEY_ALL_CAPS], look_mod.FOLLOW_LOOK)

    def test_the_second_saved_look_is_the_one_loaded_for_the_second_item(self):
        sl.save_user_look("A", glass())
        sl.save_user_look("B", draft(**{look_mod.KEY_LOOK: "Neon"}))
        target = draft()
        self.run_menu(target, select=(2,))
        self.assertEqual(target[look_mod.KEY_LOOK], "Neon")


class SaveFlowTests(_MenuBase):
    SAVE = 1  # no saved looks yet: Reset, Save

    def saved_ok(self):
        return [call.args[1] for call in self.dialog.ok.call_args_list]

    def test_a_new_look_is_saved_under_the_name_typed(self):
        changed = self.run_menu(glass(), select=(self.SAVE,), inputs=("  Evening  ",))
        self.assertFalse(changed)
        self.assertEqual(sl.load_user_looks(), {"Evening": sl.snapshot(glass())})
        self.assertEqual(self.toasts(), ["Look saved: Evening"])
        self.assertEqual(self.notify.call_args.kwargs.get("prefer_builtin"), True)

    def test_the_name_prompt_is_titled_and_starts_empty(self):
        self.run_menu(glass(), select=(self.SAVE,), inputs=("Evening",))
        call = self.dialog.input.call_args
        self.assertEqual(call.args[0], "Look name")
        self.assertEqual(call.kwargs.get("defaultt"), "")

    def test_no_name_saves_nothing(self):
        self.run_menu(glass(), select=(self.SAVE,), inputs=("   ",))
        self.assertEqual(sl.load_user_looks(), {})
        self.assertEqual(self.toasts(), [])

    def test_a_look_that_is_a_built_in_one_is_not_saved_and_is_named(self):
        self.run_menu(draft(**{look_mod.KEY_LOOK: "Glass"}), select=(self.SAVE,))
        self.dialog.input.assert_not_called()
        self.assertEqual(self.saved_ok(), ["This is the built-in look Glass."])
        self.assertEqual(sl.load_user_looks(), {})

    def test_a_look_already_saved_is_not_saved_again_and_the_old_name_is_shown(self):
        sl.save_user_look("Evening", glass())
        self.run_menu(glass(), select=(2,))  # Reset, Evening, Save, Delete
        self.dialog.input.assert_not_called()
        self.assertEqual(self.saved_ok(), ["This look is already saved as Evening."])
        self.assertEqual(list(sl.load_user_looks()), ["Evening"])

    def test_the_name_of_a_built_in_look_is_refused(self):
        self.run_menu(glass(), select=(self.SAVE,), inputs=("glass",))
        self.assertEqual(self.saved_ok(), ["That name is used by a built-in look."])
        self.assertEqual(sl.load_user_looks(), {})
        self.assertEqual(self.toasts(), [])

    def test_an_existing_name_is_only_overwritten_after_asking(self):
        sl.save_user_look("Evening", glass())
        other = glass(**{look_mod.KEY_BAR_STYLE: BAR})
        self.run_menu(other, select=(2,), inputs=("evening",), yesno=(True,))
        self.assertEqual(
            self.dialog.yesno.call_args.args[1],
            "A saved look named evening already exists. Overwrite it?",
        )
        self.assertEqual(sl.load_user_looks(), {"evening": sl.snapshot(other)})
        self.assertEqual(self.toasts(), ["Look saved: evening"])

    def test_declining_the_overwrite_keeps_the_old_look(self):
        sl.save_user_look("Evening", glass())
        other = glass(**{look_mod.KEY_BAR_STYLE: BAR})
        self.run_menu(other, select=(2,), inputs=("Evening",), yesno=(False,))
        self.assertEqual(sl.load_user_looks(), {"Evening": sl.snapshot(glass())})
        self.assertEqual(self.toasts(), [])

    def test_a_failed_write_says_so(self):
        with patch.object(sl, "write_json", return_value=False):
            self.run_menu(glass(), select=(self.SAVE,), inputs=("Evening",))
        self.assertEqual(self.toasts(), ["Could not save the look."])

    def test_the_limit_is_explained(self):
        with patch.object(sl, "MAX_USER_LOOKS", 1):
            sl.save_user_look("Evening", glass())
            self.run_menu(glass(**{look_mod.KEY_BAR_STYLE: BAR}), select=(2,), inputs=("Other",))
        self.assertEqual(self.toasts(), ["You can save up to 1 looks. Delete one first."])
        self.assertEqual(list(sl.load_user_looks()), ["Evening"])


class DeleteFlowTests(_MenuBase):
    def test_a_confirmed_delete_removes_the_look(self):
        sl.save_user_look("A", glass())
        sl.save_user_look("B", glass(**{look_mod.KEY_BAR_STYLE: BAR}))
        # Reset, A, B, Save, Delete -> item 4, then the second look in the delete list.
        self.run_menu(draft(), select=(4, 1), yesno=(True,))
        self.assertEqual(list(sl.load_user_looks()), ["A"])
        self.assertEqual(self.dialog.yesno.call_args.args[1], "Delete look B?")
        self.assertEqual(self.toasts(), ["Look deleted: B"])
        self.assertEqual(self.dialog.select.call_args_list[1].args[1], ["A", "B"])
        self.assertEqual(self.dialog.select.call_args_list[1].args[0], "Delete a saved look…")

    def test_declining_keeps_the_look(self):
        sl.save_user_look("A", glass())
        self.run_menu(draft(), select=(3, 0), yesno=(False,))
        self.assertEqual(list(sl.load_user_looks()), ["A"])
        self.assertEqual(self.toasts(), [])

    def test_leaving_the_delete_list_keeps_everything(self):
        sl.save_user_look("A", glass())
        self.run_menu(draft(), select=(3, -1))
        self.dialog.yesno.assert_not_called()
        self.assertEqual(list(sl.load_user_looks()), ["A"])

    def test_a_delete_that_fails_does_not_claim_success(self):
        sl.save_user_look("A", glass())
        with patch.object(sl, "delete_user_look", return_value=False):
            self.run_menu(draft(), select=(3, 0), yesno=(True,))
        self.assertEqual(self.toasts(), [])

    def test_the_draft_is_not_changed_by_a_delete(self):
        sl.save_user_look("A", glass())
        target = glass()
        before = dict(target)
        self.assertFalse(self.run_menu(target, select=(3, 0), yesno=(True,)))
        self.assertEqual(target, before)

    def test_delete_with_nothing_saved_says_so(self):
        with patch.object(ui, "notify_skippy") as notify:
            ui._delete_saved(None)
        self.assertEqual(notify.call_args.args[1], "There are no saved looks to delete.")


class CustomizeScreenTests(unittest.TestCase):
    def test_the_looks_button_sits_second_in_the_footer(self):
        self.assertEqual(cust.ID_LOOKS, 6023)
        self.assertEqual(cust.FOOTER_IDS, (cust.ID_PREVIEW, cust.ID_LOOKS, cust.ID_SAVE, cust.ID_CANCEL))

    def test_the_four_footer_buttons_fit_the_row_without_touching(self):
        edges = [(20 + cust._FOOTER_STEP * n, 20 + cust._FOOTER_STEP * n + cust._FOOTER_W)
                 for n in range(len(cust.FOOTER_IDS))]
        self.assertLessEqual(edges[-1][1], 20 + 520)
        for (_a, right), (left, _b) in zip(edges, edges[1:]):
            self.assertGreaterEqual(left - right, 10)

    def test_the_buttons_are_named_when_the_screen_opens(self):
        modal = _modal()
        modal._xml_layout = cust.XML_NAME
        modal.onInit()
        self.assertEqual(
            [modal.ctrls[cid].label for cid in cust.FOOTER_IDS], ["Preview", "Looks…", "Save", "Cancel"]
        )

    def test_the_buttons_are_placed_under_the_rows(self):
        modal = _modal()
        modal._refresh()
        _tops, footer, _h = cust.row_layout(app.customize_rows(modal._draft))
        for n, cid in enumerate(cust.FOOTER_IDS):
            ctrl = modal.ctrls[cid]
            self.assertEqual(ctrl.pos, (20 + cust._FOOTER_STEP * n, footer), cid)
            self.assertEqual((ctrl.width, ctrl.height), (cust._FOOTER_W, cust._FOOTER_H), cid)

    def test_both_skins_have_the_button_where_the_screen_puts_it(self):
        for res, factor in (("720p", 1.0), ("1080i", 1.5)):
            root = ET.parse(os.path.join(SKINS, res, "NextEpisodeCustomize.xml")).getroot()
            found = {int(c.get("id")): c for c in root.iter("control") if c.get("id")}
            self.assertIn(cust.ID_LOOKS, found, res)
            for n, cid in enumerate(cust.FOOTER_IDS):
                el = found[cid]
                self.assertEqual(int(el.findtext("left")), int((20 + cust._FOOTER_STEP * n) * factor + 0.5), (res, cid))
                self.assertEqual(int(el.findtext("width")), int(cust._FOOTER_W * factor + 0.5), (res, cid))
            self.assertEqual(found[cust.ID_LOOKS].findtext("label"), "Looks…")

    def test_the_button_looks_like_its_neighbours(self):
        root = ET.parse(os.path.join(SKINS, "720p", "NextEpisodeCustomize.xml")).getroot()
        found = {int(c.get("id")): c for c in root.iter("control") if c.get("id")}
        for tag in ("font", "texturefocus", "texturenofocus", "textcolor", "focusedcolor", "height", "top"):
            self.assertEqual(
                ET.tostring(found[cust.ID_LOOKS].find(tag)), ET.tostring(found[cust.ID_SAVE].find(tag)), tag
            )

    def test_left_and_right_move_along_all_four_buttons(self):
        modal = _modal()
        moves = []
        modal.setFocusId = moves.append
        for start, delta, expected in (
            (cust.ID_PREVIEW, 1, cust.ID_LOOKS),
            (cust.ID_LOOKS, 1, cust.ID_SAVE),
            (cust.ID_CANCEL, 1, cust.ID_PREVIEW),
            (cust.ID_PREVIEW, -1, cust.ID_CANCEL),
            (cust.ID_SAVE, -1, cust.ID_LOOKS),
        ):
            modal._focus_id = lambda start=start: start
            modal._move_footer(delta)
            self.assertEqual(moves[-1], expected, (start, delta))

    def test_up_and_down_treat_the_looks_button_like_preview(self):
        modal = _modal()
        moves = []
        modal.setFocusId = moves.append
        modal._focus_id = lambda: cust.ID_LOOKS
        ids = cust.nav_ids(modal._draft)
        modal._move_focus(1)
        modal._move_focus(-1)
        self.assertEqual(moves, [ids[0], ids[-2]])

    def test_clicking_looks_opens_the_menu_then_redraws_and_keeps_focus_there(self):
        modal = _modal()
        modal._refresh = MagicMock()
        moves = []
        modal.setFocusId = moves.append
        with patch.object(ui, "present_looks_menu") as menu:
            modal.onClick(cust.ID_LOOKS)
        menu.assert_called_once_with(modal.addon, modal._draft)
        modal._refresh.assert_called_once()
        self.assertEqual(moves, [cust.ID_LOOKS])

    def test_a_menu_that_fails_still_leaves_a_working_screen(self):
        modal = _modal()
        modal._refresh = MagicMock()
        modal.setFocusId = lambda cid: None
        with patch.object(ui, "present_looks_menu", side_effect=RuntimeError("boom")):
            modal.onClick(cust.ID_LOOKS)
        modal._refresh.assert_called_once()

    def test_reset_from_the_button_redraws_the_mockup_with_the_defaults(self):
        modal = _modal(glass(**{app.KEY_POSITION: "TopLeft"}))
        modal.setFocusId = lambda cid: None
        with patch.object(ui.xbmcgui, "Dialog") as dialog, patch.object(ui, "notify_skippy"):
            dialog.return_value.select.return_value = 0
            modal.onClick(cust.ID_LOOKS)
        self.assertEqual(modal._draft, app.DEFAULT_DRAFT)
        self.assertEqual(modal.ctrls[cust.ROW_IDS[look_mod.KEY_LOOK]].label2, "Default")

    def test_the_other_footer_buttons_still_work(self):
        modal = cust.NextEpisodeCustomize.__new__(cust.NextEpisodeCustomize)
        modal.addon = MagicMock()
        modal._saved = False
        modal.close = MagicMock()
        modal.onClick(cust.ID_CANCEL)
        modal.close.assert_called_once()
        modal._preview = MagicMock()
        modal.onClick(cust.ID_PREVIEW)
        modal._preview.assert_called_once()


class StringsTests(unittest.TestCase):
    IDS = range(47128, 47144)

    def packs(self):
        langs = os.path.join(ROOT, "resources", "language")
        for pack in sorted(os.listdir(langs)):
            path = os.path.join(langs, pack, "strings.po")
            if os.path.exists(path):
                with open(path, encoding="utf-8") as handle:
                    yield pack, handle.read()

    @staticmethod
    def entries(text):
        return {
            int(sid): (msgid, msgstr)
            for sid, msgid, msgstr in re.findall(
                r'msgctxt "#(\d+)"\nmsgid "(.*)"\nmsgstr "(.*)"', text
            )
        }

    def test_every_pack_has_every_string_with_the_same_placeholders(self):
        packs = list(self.packs())
        self.assertGreaterEqual(len(packs), 11)
        for pack, text in packs:
            entries = self.entries(text)
            for sid in self.IDS:
                self.assertIn(sid, entries, (pack, sid))
                msgid, msgstr = entries[sid]
                self.assertTrue(msgstr.strip(), (pack, sid))
                self.assertEqual(msgid.count("%s"), msgstr.count("%s"), (pack, sid))
                self.assertEqual(msgstr.count("%"), msgstr.count("%s"), (pack, sid))

    def test_the_translations_are_not_the_english_text(self):
        english = self.entries(dict(self.packs())["resource.language.en_gb"])
        for pack, text in self.packs():
            if pack.endswith("en_gb"):
                continue
            entries = self.entries(text)
            for sid in self.IDS:
                self.assertNotEqual(entries[sid][1], english[sid][1], (pack, sid))

    def test_the_menu_uses_the_ids_the_strings_have(self):
        english = self.entries(dict(self.packs())["resource.language.en_gb"])
        for sid, default in ui._DEFAULT_TEXT.items():
            self.assertEqual(english[sid][1], default, sid)
        self.assertEqual(set(ui._DEFAULT_TEXT), set(self.IDS))
        self.assertEqual(english[47128][1], "Looks…")


if __name__ == "__main__":
    unittest.main()
