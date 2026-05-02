# -*- coding: utf-8 -*-
"""Helpers for Skippy's user-configurable segment marker and segment editor keymaps."""
import os
import re
import xml.etree.ElementTree as ET

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs


ADDON_ID = "service.skippy"
SCRIPT_ACTION = "RunScript(service.skippy)"
EDITOR_SCRIPT_ACTION = "RunScript(service.skippy,open_segment_editor)"
KEYMAP_PATH = "special://profile/keymaps/skippy_marker.xml"
EDITOR_KEYMAP_PATH = "special://profile/keymaps/skippy_editor.xml"
DEFAULT_KEYBOARD_SHORTCUT = "ctrl+e"
DEFAULT_EDITOR_KEYBOARD_SHORTCUT = "ctrl+shift+e"
KEYBOARD_TARGET_SECTIONS = ("global", "FullscreenVideo", "VideoOSD", "VideoMenu")
REMOTE_TARGET_SECTIONS = ("FullscreenVideo", "VideoOSD", "VideoMenu")

_VALID_XML_TAG_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")


def _log(message):
    xbmc.log(f"[{ADDON_ID} - Keymap] {message}", xbmc.LOGINFO)


def get_addon():
    try:
        return xbmcaddon.Addon(ADDON_ID)
    except Exception:
        return None


def translate_path(path):
    translated = xbmcvfs.translatePath(path)
    if isinstance(translated, bytes):
        translated = translated.decode("utf-8", errors="replace")
    return translated


def get_user_keymap_path():
    return translate_path(KEYMAP_PATH)


def get_editor_keymap_path():
    return translate_path(EDITOR_KEYMAP_PATH)


def _setting_text(addon, setting_id, default=""):
    try:
        value = addon.getSetting(setting_id)
        if value is None or value == "":
            return default
        return value
    except Exception:
        return default


def _split_shortcut_token(token):
    token = token.strip().lower()
    if not token:
        return None, []
    if ":" in token:
        key, mods = token.split(":", 1)
        return key.strip().lower(), [m.strip().lower() for m in mods.split(",") if m.strip()]
    parts = [p.strip().lower() for p in re.split(r"[+,]", token) if p.strip()]
    if not parts:
        return None, []
    mods = [p for p in parts[:-1] if p]
    return parts[-1], mods


def _keyboard_press_mod(addon):
    value = ""
    if addon:
        value = _setting_text(addon, "segment_marker_keyboard_press_type", "normal")
    if (value or "").strip().lower() == "longpress":
        return "longpress"
    return ""


def _normalize_keyboard_shortcut(raw, press_mod="", default_shortcut=None):
    default_shortcut = default_shortcut or DEFAULT_KEYBOARD_SHORTCUT
    value = (raw or default_shortcut).strip()
    if value.lower() in ("none", "disabled", "off"):
        return None
    key, mods = _split_shortcut_token(value)
    if not key or not _VALID_XML_TAG_RE.match(key):
        _log(f"Ignoring invalid keyboard shortcut setting: {raw!r}")
        return None
    mods = [m for m in mods if m != "longpress"]
    if press_mod:
        mods.append(press_mod)
    seen = set()
    unique_mods = []
    for mod in mods:
        if mod and mod not in seen:
            seen.add(mod)
            unique_mods.append(mod)
    mods = ",".join(unique_mods)
    return key, mods


def _parse_remote_button(raw, context="marker"):
    value = (raw or "").strip()
    if not value:
        return None
    if value.lower().startswith("key:"):
        value = value.split(":", 1)[1].strip()
    if value.isdigit():
        return "key_id", value
    tag = value.lower()
    if not _VALID_XML_TAG_RE.match(tag):
        _log(f"Ignoring invalid remote {context} button setting: {raw!r}")
        return None
    return "remote_tag", tag


def _append_keyboard_binding(parent, hotkey, script_action):
    if not hotkey:
        return
    key, mods = hotkey
    el = ET.SubElement(parent, key)
    if mods:
        el.set("mod", mods)
    el.text = script_action


def _remote_press_mod(addon):
    value = ""
    if addon:
        value = _setting_text(addon, "segment_marker_remote_press_type", "normal")
    if (value or "").strip().lower() == "longpress":
        return "longpress"
    return ""


def _append_key_id_binding(parent, key_id, script_action, mod=""):
    el = ET.SubElement(parent, "key")
    el.set("id", str(key_id))
    if mod:
        el.set("mod", mod)
    el.text = script_action


def _append_remote_binding(parent, remote_tag, script_action, mod=""):
    el = ET.SubElement(parent, remote_tag)
    if mod:
        el.set("mod", mod)
    el.text = script_action


def build_keymap_tree(addon=None):
    addon = addon or get_addon()
    keyboard_shortcut = DEFAULT_KEYBOARD_SHORTCUT
    remote_button = ""
    if addon:
        keyboard_shortcut = _setting_text(
            addon,
            "segment_marker_keyboard_shortcut",
            "",
        )
        if not keyboard_shortcut:
            keyboard_shortcut = _setting_text(
                addon,
                "segment_marker_keyboard_hotkey",
                DEFAULT_KEYBOARD_SHORTCUT,
            )
        remote_button = _setting_text(addon, "segment_marker_remote_button", "")

    keyboard_binding = _normalize_keyboard_shortcut(
        keyboard_shortcut,
        _keyboard_press_mod(addon),
        default_shortcut=DEFAULT_KEYBOARD_SHORTCUT,
    )
    remote_binding = _parse_remote_button(remote_button)
    remote_mod = _remote_press_mod(addon)

    root = ET.Element("keymap")
    for window_name in KEYBOARD_TARGET_SECTIONS:
        window = ET.SubElement(root, window_name)
        keyboard = ET.SubElement(window, "keyboard")
        _append_keyboard_binding(keyboard, keyboard_binding, SCRIPT_ACTION)

        # Raw discovered button codes worked as <keyboard><key id="...">.
        # Keep that exact form and only add it in video windows, including OSD.
        if (
            remote_binding
            and remote_binding[0] == "key_id"
            and window_name in REMOTE_TARGET_SECTIONS
        ):
            _append_key_id_binding(keyboard, remote_binding[1], SCRIPT_ACTION, remote_mod)

        if (
            remote_binding
            and remote_binding[0] == "remote_tag"
            and window_name in REMOTE_TARGET_SECTIONS
        ):
            remote = ET.SubElement(window, "remote")
            _append_remote_binding(remote, remote_binding[1], SCRIPT_ACTION, remote_mod)

    return ET.ElementTree(root)


def _keyboard_press_mod_editor(addon):
    value = ""
    if addon:
        value = _setting_text(addon, "segment_editor_keyboard_press_type", "normal")
    if (value or "").strip().lower() == "longpress":
        return "longpress"
    return ""


def _remote_press_mod_editor(addon):
    value = ""
    if addon:
        value = _setting_text(addon, "segment_editor_remote_press_type", "normal")
    if (value or "").strip().lower() == "longpress":
        return "longpress"
    return ""


def build_editor_keymap_tree(addon=None):
    addon = addon or get_addon()
    keyboard_shortcut = DEFAULT_EDITOR_KEYBOARD_SHORTCUT
    remote_button = ""
    if addon:
        keyboard_shortcut = _setting_text(
            addon,
            "segment_editor_keyboard_shortcut",
            DEFAULT_EDITOR_KEYBOARD_SHORTCUT,
        )
        remote_button = _setting_text(addon, "segment_editor_remote_button", "")

    keyboard_binding = _normalize_keyboard_shortcut(
        keyboard_shortcut,
        _keyboard_press_mod_editor(addon),
        default_shortcut=DEFAULT_EDITOR_KEYBOARD_SHORTCUT,
    )
    remote_binding = _parse_remote_button(remote_button, context="editor")
    remote_mod = _remote_press_mod_editor(addon)

    root = ET.Element("keymap")
    for window_name in KEYBOARD_TARGET_SECTIONS:
        window = ET.SubElement(root, window_name)
        keyboard = ET.SubElement(window, "keyboard")
        _append_keyboard_binding(keyboard, keyboard_binding, EDITOR_SCRIPT_ACTION)

        if (
            remote_binding
            and remote_binding[0] == "key_id"
            and window_name in REMOTE_TARGET_SECTIONS
        ):
            _append_key_id_binding(
                keyboard, remote_binding[1], EDITOR_SCRIPT_ACTION, remote_mod
            )

        if (
            remote_binding
            and remote_binding[0] == "remote_tag"
            and window_name in REMOTE_TARGET_SECTIONS
        ):
            remote = ET.SubElement(window, "remote")
            _append_remote_binding(
                remote, remote_binding[1], EDITOR_SCRIPT_ACTION, remote_mod
            )

    return ET.ElementTree(root)


def install_editor_keymap(addon=None, notify=False):
    try:
        path = get_editor_keymap_path()
        directory = os.path.dirname(path)
        if directory and not xbmcvfs.exists(directory):
            xbmcvfs.mkdirs(directory)

        tree = build_editor_keymap_tree(addon)
        try:
            ET.indent(tree, space="  ")
        except AttributeError:
            pass
        xml_text = ET.tostring(tree.getroot(), encoding="unicode")
        xml_text = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_text + "\n"

        handle = xbmcvfs.File(path, "w")
        handle.write(xml_text)
        handle.close()

        xbmc.executebuiltin("Action(reloadkeymaps)")
        remote_value = _setting_text(addon, "segment_editor_remote_button", "") if addon else ""
        remote_press = (
            _setting_text(addon, "segment_editor_remote_press_type", "normal")
            if addon
            else "normal"
        )
        _log(
            "Installed segment editor keymap: "
            f"{path}; remote={remote_value!r}; remote_press={remote_press!r}"
        )
        if notify:
            xbmcgui.Dialog().notification(
                "Skippy",
                "Segment editor keymap updated",
                time=2500,
                sound=False,
            )
        return True
    except Exception as exc:
        _log(f"Failed to install segment editor keymap: {exc}")
        if notify:
            xbmcgui.Dialog().notification(
                "Skippy",
                "Could not update editor keymap",
                time=3500,
                sound=False,
            )
        return False


def install_marker_keymap(addon=None, notify=False):
    try:
        path = get_user_keymap_path()
        directory = os.path.dirname(path)
        if directory and not xbmcvfs.exists(directory):
            xbmcvfs.mkdirs(directory)

        tree = build_keymap_tree(addon)
        try:
            ET.indent(tree, space="  ")
        except AttributeError:
            pass
        xml_text = ET.tostring(tree.getroot(), encoding="unicode")
        xml_text = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_text + "\n"

        handle = xbmcvfs.File(path, "w")
        handle.write(xml_text)
        handle.close()

        xbmc.executebuiltin("Action(reloadkeymaps)")
        remote_value = _setting_text(addon, "segment_marker_remote_button", "") if addon else ""
        remote_press = _setting_text(addon, "segment_marker_remote_press_type", "normal") if addon else "normal"
        _log(
            "Installed segment marker keymap: "
            f"{path}; remote={remote_value!r}; remote_press={remote_press!r}; "
            f"keyboard_sections={KEYBOARD_TARGET_SECTIONS}; remote_sections={REMOTE_TARGET_SECTIONS}"
        )
        if notify:
            xbmcgui.Dialog().notification(
                "Skippy",
                "Segment marker keymap updated",
                time=2500,
                sound=False,
            )
        return True
    except Exception as exc:
        _log(f"Failed to install segment marker keymap: {exc}")
        if notify:
            xbmcgui.Dialog().notification(
                "Skippy",
                "Could not update marker keymap",
                time=3500,
                sound=False,
            )
        return False

