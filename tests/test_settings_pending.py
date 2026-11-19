# -*- coding: utf-8 -*-
"""Customize Save while Kodi's settings window is open: the next Customize must see it.

Kodi hands ``setSetting`` values to an open add-on settings window instead of writing them to
disk, so ``getSetting`` keeps answering the old value until that window is closed. The fake
add-on below behaves the same way.
"""

import os
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import import_fresh, install_kodi_stubs

install_kodi_stubs()

import settings_pending as pending  # noqa: E402
from tests import fake_gui  # noqa: E402


class _Win:
    def __init__(self):
        self.props = {}

    def setProperty(self, key, value):
        self.props[key] = value

    def getProperty(self, key):
        return self.props.get(key, "")

    def clearProperty(self, key):
        self.props.pop(key, None)


class _KodiAddon:
    """Kodi's add-on settings, stored in a real settings.xml.

    While the settings window is open, ``setSetting`` only reaches the window. Closing it with
    OK stores the window's values; Back or Cancel reloads the file and drops them.
    """

    def __init__(self, test):
        self.test = test
        self.path = test.settings_path
        self.window_values = {}

    @property
    def disk(self):
        if not os.path.isfile(self.path):
            return {}
        return {el.get("id"): el.text or "" for el in ET.parse(self.path).getroot().iter("setting")}

    def getSetting(self, key):
        return self.disk.get(key, "")

    def setSetting(self, key, value):
        if self.test.settings_open:
            self.window_values[key] = value
        else:
            pending.write_settings_file({key: value}, self.path)

    def close_settings_window(self, ok=True):
        if ok:
            pending.write_settings_file(self.window_values, self.path)
        self.window_values = {}
        self.test.settings_open = False

    def getLocalizedString(self, _sid):
        return ""

    def getAddonInfo(self, key):
        return "/addon" if key == "path" else ""


class _Base(unittest.TestCase):
    def setUp(self):
        self.settings_open = True
        self.win = _Win()
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.settings_path = os.path.join(self.tmp, "settings.xml")
        file_patch = patch.object(pending, "_settings_file", return_value=self.settings_path)
        file_patch.start()
        self.addCleanup(file_patch.stop)
        for target, kwargs in (
            (pending, {"_window": MagicMock(return_value=self.win)}),
            (pending, {"addon_settings_open": MagicMock(side_effect=lambda: self.settings_open)}),
        ):
            patcher = patch.multiple(target, **kwargs)
            patcher.start()
            self.addCleanup(patcher.stop)


class PendingTests(_Base):
    def test_saved_values_are_read_back_while_the_window_is_open(self):
        addon = _KodiAddon(self)
        first = pending.with_pending(addon)
        first.setSetting("next_episode_popup_position", "TopLeft")
        self.assertEqual(addon.window_values["next_episode_popup_position"], "TopLeft")
        again = pending.with_pending(addon)
        self.assertEqual(again.getSetting("next_episode_popup_position"), "TopLeft")
        self.assertEqual(again.getSetting("other"), "")
        self.assertEqual(again.getAddonInfo("path"), "/addon")

    def test_closed_window_forgets_and_reads_disk(self):
        addon = _KodiAddon(self)
        pending.with_pending(addon).setSetting("k", "v")
        addon.close_settings_window()
        self.assertIs(pending.with_pending(addon), addon)
        self.assertEqual(self.win.props, {})
        self.assertEqual(addon.getSetting("k"), "v")

    def test_nothing_recorded_when_no_settings_window(self):
        self.settings_open = False
        addon = _KodiAddon(self)
        plain = pending.with_pending(addon)
        self.assertIs(plain, addon)
        pending.note_pending({"k": "v"})
        self.assertEqual(self.win.props, {})
        self.assertIsNone(pending.with_pending(None))

    def test_service_loop_drops_values_once_the_window_is_gone(self):
        pending.note_pending({"k": "v"})
        self.assertFalse(pending.drop_if_settings_closed(self.win))
        self.settings_open = False
        self.assertTrue(pending.drop_if_settings_closed(self.win))
        self.assertFalse(pending.drop_if_settings_closed(self.win))

    def test_bad_property_reads_as_nothing(self):
        self.win.props[pending.PENDING_PROP] = "not json"
        self.assertEqual(pending.read_pending(), {})
        self.win.props[pending.PENDING_PROP] = "[1]"
        self.assertEqual(pending.read_pending(), {})


class SettingsFileTests(_Base):
    def test_updates_only_the_given_ids_and_drops_the_default_mark(self):
        with open(self.settings_path, "w", encoding="utf-8") as handle:
            handle.write('<settings version="2">\n'
                         '    <setting id="next_episode_popup_look" default="true">Default</setting>\n'
                         '    <setting id="other">keep</setting>\n'
                         '</settings>\n')
        self.assertTrue(pending.write_settings_file(
            {"next_episode_popup_look": "Neon", "next_episode_popup_focus_style": "x.png"}))
        root = ET.parse(self.settings_path).getroot()
        self.assertEqual(root.get("version"), "2")
        rows = {el.get("id"): (el.text, el.get("default")) for el in root.iter("setting")}
        self.assertEqual(rows["next_episode_popup_look"], ("Neon", None))
        self.assertEqual(rows["other"], ("keep", None))
        self.assertEqual(rows["next_episode_popup_focus_style"], ("x.png", None))
        self.assertFalse(os.path.exists(self.settings_path + ".tmp"))

    def test_creates_a_missing_file_and_refuses_a_broken_one(self):
        self.assertTrue(pending.write_settings_file({"k": "v"}))
        self.assertEqual(ET.parse(self.settings_path).getroot().find("setting").text, "v")
        with open(self.settings_path, "w", encoding="utf-8") as handle:
            handle.write("<settings><broken")
        self.assertFalse(pending.write_settings_file({"k": "w"}))
        self.assertTrue(pending.write_settings_file({}))

    def test_save_survives_back_and_ok(self):
        """The report: leaving the settings with Back dropped every Customize change."""
        for ok in (False, True):
            self.settings_open = True
            addon = _KodiAddon(self)
            pending.with_pending(addon).setSetting("next_episode_popup_focus_style", "neon_%s.png" % ok)
            addon.close_settings_window(ok=ok)
            self.assertEqual(addon.getSetting("next_episode_popup_focus_style"), "neon_%s.png" % ok)

    def test_no_file_write_when_the_settings_window_is_closed(self):
        self.settings_open = False
        addon = MagicMock()
        proxy = pending.PendingSettingsAddon(addon, {})
        with patch.object(pending, "write_settings_file") as write:
            proxy.setSetting("k", "v")
        write.assert_not_called()
        addon.setSetting.assert_called_once_with("k", "v")


class NextEpisodeCustomizeTests(_Base):
    """The reported bug: Save, open Customize again from the settings window, old values back."""

    def open_customize(self, m, addon):
        dialog = m.NextEpisodeCustomize("NextEpisodeCustomize.xml", "/addon", "default",
                                        addon=pending.with_pending(addon))
        for cid in list(m.ROW_IDS.values()) + list(m.FOOTER_IDS) + [m.ID_TITLE]:
            dialog.addControl(fake_gui.with_id(fake_gui.ControlButton(0, 0, 10, 10, ""), cid))
        return dialog

    def test_second_open_shows_what_the_first_saved(self):
        fake_gui.reset()
        m = fake_gui.load("next_episode_customize_ui", self)
        addon = _KodiAddon(self)
        first = self.open_customize(m, addon)
        first._nudge(m.ROW_IDS[m.KEY_POSITION], 1)
        first._nudge(m.ROW_IDS[m.KEY_THUMBNAIL], -1)  # the picture row: one step back from Episode picture is Off
        first.onClick(m.ID_SAVE)
        self.assertEqual(addon.window_values["next_episode_popup_position"], "TopRight")
        second = self.open_customize(m, addon)
        self.assertEqual(second._draft[m.KEY_POSITION], "TopRight")
        self.assertFalse(second._draft[m.KEY_THUMBNAIL])
        # A second Save compares against what is really there now, so it changes only one thing.
        second._nudge(m.ROW_IDS[m.KEY_SIZE], 1)
        second.onClick(m.ID_SAVE)
        addon.close_settings_window()
        self.assertEqual(addon.disk["next_episode_popup_position"], "TopRight")
        self.assertEqual(addon.disk["next_episode_popup_thumbnail"], "false")
        self.assertEqual(addon.disk["next_episode_popup_size"], "Large")

    def test_entry_point_wraps_the_addon(self):
        fake_gui.reset()
        m = fake_gui.load("next_episode_customize_ui", self)
        addon = _KodiAddon(self)
        seen = []
        fake_gui.on_modal = lambda w: seen.append(w.addon)
        self.addCleanup(fake_gui.reset)
        with patch.object(m, "get_addon", return_value=addon):
            m.show_next_episode_customize()
        self.assertIsInstance(seen[0], pending.PendingSettingsAddon)


class SkipDialogCustomizeTests(_Base):
    def test_skip_dialog_draft_reads_pending_values(self):
        from skip_dialog_customize_ui import load_skip_dialog_draft

        addon = _KodiAddon(self)
        before = load_skip_dialog_draft(addon)
        key = "skip_dialog_all_caps"
        pending.with_pending(addon).setSetting(key, "false" if before[key] else "true")
        self.assertEqual(load_skip_dialog_draft(pending.with_pending(addon))[key], not before[key])


class ServiceTests(unittest.TestCase):
    def test_settings_changed_clears_pending(self):
        install_kodi_stubs()
        with patch("service_main_loop.run_service_main_loop", lambda _ctx: None):
            service = import_fresh("service")
        with patch("settings_pending.clear_pending") as clear:
            service.PlayerMonitor().onSettingsChanged()
        clear.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
