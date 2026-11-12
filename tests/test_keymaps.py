# -*- coding: utf-8 -*-
"""The keymap files Skippy writes into the user's profile for the marker and editor buttons.

A wrong file here can take over a key everywhere in Kodi, or make the button do nothing.
"""

import os
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import keymap_utils as km  # noqa: E402
from tests import fake_vfs  # noqa: E402


class _Addon:
    def __init__(self, **settings):
        self.settings = settings

    def getSetting(self, key):
        return self.settings.get(key, "")


def _bindings(tree):
    """``{(window, device): [(tag, attrs, action)]}`` of a keymap tree."""
    out = {}
    for window in tree.getroot():
        for device in window:
            out[(window.tag, device.tag)] = [(b.tag, dict(b.attrib), b.text) for b in device]
    return out


class ShortcutParsingTests(unittest.TestCase):
    def test_the_accepted_spellings(self):
        self.assertEqual(km._normalize_keyboard_shortcut("ctrl+e"), ("e", "ctrl"))
        self.assertEqual(km._normalize_keyboard_shortcut("Ctrl+Shift+E"), ("e", "ctrl,shift"))
        self.assertEqual(km._normalize_keyboard_shortcut("e:ctrl,alt"), ("e", "ctrl,alt"))
        self.assertEqual(km._normalize_keyboard_shortcut("f9"), ("f9", ""))
        self.assertEqual(km._normalize_keyboard_shortcut("", default_shortcut="ctrl+e"), ("e", "ctrl"))

    def test_long_press_is_one_modifier_and_never_doubled(self):
        self.assertEqual(km._normalize_keyboard_shortcut("ctrl+longpress+e", "longpress"), ("e", "ctrl,longpress"))
        self.assertEqual(km._normalize_keyboard_shortcut("ctrl+ctrl+e"), ("e", "ctrl"))

    def test_off_and_junk_give_no_shortcut(self):
        for raw in ("none", "Disabled", "off"):
            self.assertIsNone(km._normalize_keyboard_shortcut(raw), raw)
        with patch.object(km, "_log"):
            self.assertIsNone(km._normalize_keyboard_shortcut("ctrl+<script>"))
            self.assertIsNone(km._normalize_keyboard_shortcut("ctrl+1abc"))

    def test_remote_buttons(self):
        self.assertEqual(km._parse_remote_button("61448"), ("key_id", "61448"))
        self.assertEqual(km._parse_remote_button("key:61448"), ("key_id", "61448"))
        self.assertEqual(km._parse_remote_button("Red"), ("remote_tag", "red"))
        self.assertIsNone(km._parse_remote_button(""))
        with patch.object(km, "_log"):
            self.assertIsNone(km._parse_remote_button("red button"))


class MarkerKeymapTests(unittest.TestCase):
    def test_the_default_is_ctrl_e_in_every_section_and_no_remote(self):
        found = _bindings(km.build_keymap_tree(_Addon()))
        for section in km.KEYBOARD_TARGET_SECTIONS:
            self.assertEqual(found[(section, "keyboard")], [("e", {"mod": "ctrl"}, km.SCRIPT_ACTION)])
        self.assertNotIn(("FullscreenVideo", "remote"), found)

    def test_a_remote_button_name_binds_only_in_video_windows(self):
        addon = _Addon(segment_marker_remote_button="red", segment_marker_remote_press_type="longpress")
        found = _bindings(km.build_keymap_tree(addon))
        for section in km.REMOTE_TARGET_SECTIONS:
            self.assertEqual(found[(section, "remote")], [("red", {"mod": "longpress"}, km.SCRIPT_ACTION)])
        self.assertNotIn(("global", "remote"), found)

    def test_a_discovered_button_code_binds_as_a_keyboard_key_id(self):
        found = _bindings(km.build_keymap_tree(_Addon(segment_marker_remote_button="61448")))
        self.assertIn(("key", {"id": "61448"}, km.SCRIPT_ACTION), found[("VideoOSD", "keyboard")])
        self.assertNotIn(("key", {"id": "61448"}, km.SCRIPT_ACTION), found[("global", "keyboard")])

    def test_the_old_hotkey_setting_is_still_read(self):
        found = _bindings(km.build_keymap_tree(_Addon(segment_marker_keyboard_hotkey="f9")))
        self.assertEqual(found[("global", "keyboard")], [("f9", {}, km.SCRIPT_ACTION)])

    def test_a_turned_off_shortcut_leaves_the_sections_empty(self):
        found = _bindings(km.build_keymap_tree(_Addon(segment_marker_keyboard_shortcut="none")))
        self.assertEqual(found[("global", "keyboard")], [])


class EditorKeymapTests(unittest.TestCase):
    def test_the_editor_default_and_its_own_settings(self):
        found = _bindings(km.build_editor_keymap_tree(_Addon()))
        self.assertEqual(found[("global", "keyboard")], [("e", {"mod": "ctrl,shift"}, km.EDITOR_SCRIPT_ACTION)])
        addon = _Addon(
            segment_editor_keyboard_shortcut="f10",
            segment_editor_keyboard_press_type="longpress",
            segment_editor_remote_button="blue",
        )
        found = _bindings(km.build_editor_keymap_tree(addon))
        self.assertEqual(found[("global", "keyboard")], [("f10", {"mod": "longpress"}, km.EDITOR_SCRIPT_ACTION)])
        self.assertEqual(found[("FullscreenVideo", "remote")], [("blue", {}, km.EDITOR_SCRIPT_ACTION)])


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.vfs, self.folder = fake_vfs.install(self, km)
        self.marker = os.path.join(self.folder, "keymaps", "skippy_marker.xml")
        self.editor = os.path.join(self.folder, "keymaps", "skippy_editor.xml")
        self.builtins = []
        stack = [
            patch.object(km, "get_user_keymap_path", lambda: self.marker),
            patch.object(km, "get_editor_keymap_path", lambda: self.editor),
            patch.object(km.xbmc, "executebuiltin", self.builtins.append, create=True),
            patch.object(km, "_log"),
        ]
        for p in stack:
            p.start()
            self.addCleanup(p.stop)

    def test_installing_writes_valid_xml_and_reloads_the_keymaps(self):
        self.assertTrue(km.install_marker_keymap(_Addon()))
        self.assertTrue(km.install_editor_keymap(_Addon()))
        for path, action in ((self.marker, km.SCRIPT_ACTION), (self.editor, km.EDITOR_SCRIPT_ACTION)):
            root = ET.parse(path).getroot()
            self.assertEqual(root.tag, "keymap")
            self.assertEqual(root.find("global/keyboard/e").text, action)
        self.assertEqual(self.builtins, ["Action(reloadkeymaps)", "Action(reloadkeymaps)"])

    def test_a_write_failure_is_reported_not_raised(self):
        with patch.object(self.vfs, "File", side_effect=OSError("read-only profile")):
            self.assertFalse(km.install_marker_keymap(_Addon()))
            self.assertFalse(km.install_editor_keymap(_Addon()))


if __name__ == "__main__":
    unittest.main()
