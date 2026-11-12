# -*- coding: utf-8 -*-
"""Every button in the settings reaches its own handler, and the marker hotkey reaches the marker."""

import os
import re
import sys
import unittest
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import skippy_runscript_entry as entry  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# command -> (module, function) it must call
HANDLERS = {
    "open_segment_editor": ("segment_editor_session", "open_segment_editor"),
    "discover_editor_button": ("segment_editor", "discover_editor_remote_button"),
    "install_editor_keymap": ("keymap_utils", "install_editor_keymap"),
    "discover_button": ("segment_marker", "discover_remote_button"),
    "install_keymap": ("keymap_utils", "install_marker_keymap"),
    "show_statistics": ("skippy_statistics_ui", "show_statistics_modal"),
    "show_diagnostics": ("skippy_diagnostics_ui", "show_diagnostics_modal"),
    "reset_statistics": ("skippy_statistics_ui", "confirm_and_reset_statistics"),
    "manage_show_overrides": ("per_show_overrides_ui", "show_manage_title_autoskip_modal"),
    "manage_next_episode_shows": ("next_episode_shows_ui", "show_manage_next_episode_shows_modal"),
    "clear_next_episode_shows": ("next_episode_shows", "clear_all"),
    "customize_skip_dialog": ("skip_dialog_customize_ui", "show_skip_dialog_customize"),
    "customize_next_episode_popup": ("next_episode_customize_ui", "show_next_episode_customize"),
    "label_width_probe": ("skip_label_width_probe", "run_label_width_probe"),
    "skip_dialog_presets": ("skip_dialog_presets_ui", "show_skip_dialog_presets_menu"),
    "edit_segment_types": ("segment_types_editor_ui", "show_segment_types_editor"),
    "clear_show_overrides": ("per_show_overrides", "clear_all_overrides"),
    "backup_settings": ("settings_backup", "run_backup_ui"),
    "restore_settings": ("settings_backup", "run_restore_ui"),
    "backup_profile_data": ("skippy_profile_backup", "run_backup_ui"),
    "restore_profile_data": ("skippy_profile_backup", "run_restore_ui"),
    "backup_upload_history": ("skippy_profile_backup", "run_backup_ui"),
    "restore_upload_history": ("skippy_profile_backup", "run_restore_ui"),
}


class DispatchTests(unittest.TestCase):
    def run_command(self, *argv):
        fakes = {}
        for module, _function in HANDLERS.values():
            fakes.setdefault(module, MagicMock(name=module))
        fakes["segment_marker"].get_addon.return_value = object()
        fakes["next_episode_shows"].clear_all.return_value = 2
        fakes["per_show_overrides"].clear_all_overrides.return_value = 0
        settings_utils = MagicMock(name="settings_utils")
        settings_utils.get_localized.side_effect = lambda _a, _i, default="", *args: default % args if args else default
        fakes["settings_utils"] = settings_utils
        with patch.dict(sys.modules, fakes), patch.object(sys, "argv", ["skippy_runscript_entry.py", *argv]), patch.object(
            entry, "_addon", lambda: object()
        ):
            entry.main()
        return fakes

    def test_each_command_calls_its_handler_and_not_the_marker(self):
        for command, (module, function) in HANDLERS.items():
            with self.subTest(command=command):
                fakes = self.run_command(command)
                getattr(fakes[module], function).assert_called_once()
                fakes["segment_marker"].main.assert_not_called()

    def test_commands_ignore_case_and_spaces(self):
        fakes = self.run_command("  Show_Statistics ")
        fakes["skippy_statistics_ui"].show_statistics_modal.assert_called_once_with()

    def test_no_argument_runs_the_marker(self):
        fakes = self.run_command()
        fakes["segment_marker"].main.assert_called_once_with()
        fakes = self.run_command("")
        fakes["segment_marker"].main.assert_called_once_with()

    def test_an_unknown_command_marks_nothing(self):
        for command in ("open_segment_editr", "something_new", "marker"):
            with self.subTest(command=command), patch.object(entry, "_log_unknown_command") as logged:
                fakes = self.run_command(command)
                fakes["segment_marker"].main.assert_not_called()
                logged.assert_called_once_with(command)

    def test_clearing_says_how_many_were_cleared(self):
        fakes = self.run_command("clear_next_episode_shows")
        message = fakes["settings_utils"].notify_skippy.call_args[0][1]
        self.assertEqual(message, "Cleared 2 saved autoplay choice(s).")
        fakes = self.run_command("clear_show_overrides")
        message = fakes["settings_utils"].notify_skippy.call_args[0][1]
        self.assertEqual(message, "No saved per-title choices to clear.")

    def test_every_settings_button_has_a_handler(self):
        with open(os.path.join(ROOT, "resources", "settings.xml"), encoding="utf-8") as handle:
            actions = set(re.findall(r"RunScript\(service\.skippy,\s*([a-z_]+)\)", handle.read()))
        self.assertTrue(actions)
        self.assertEqual(sorted(actions - set(HANDLERS)), [])


if __name__ == "__main__":
    unittest.main()
