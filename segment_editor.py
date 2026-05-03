# -*- coding: utf-8 -*-
"""Segment editor entry: remote discovery and optional direct run."""

import os

import xbmc
import xbmcgui
import xbmcvfs

from keymap_utils import install_editor_keymap
from settings_utils import skippy_notification_icon
from segment_editor_utils import (
    get_addon,
    log,
    log_always,
    set_editor_modal_open,
)

_CANCEL_ACTION_IDS = (10, 92, 216)
_KEYBOARD_CONFIRM_ACTION_IDS = (7, 100)
_KEYBOARD_CONFIRM_BUTTON_CODES = (13, 61453)


def _skippy_toast(addon, message, time_ms=3000):
    """Match Segment Marker: heading + addon icon so notifications show Skippy artwork."""
    icon = skippy_notification_icon(addon) if addon else ""
    xbmcgui.Dialog().notification("Skippy", message, icon, time_ms, sound=False)


_CEC_ACTION_TO_REMOTE_TAG = {
    1: "left",
    2: "right",
    3: "up",
    4: "down",
    7: "select",
    11: "info",
    12: "pause",
    13: "stop",
    14: "skipplus",
    15: "skipminus",
    68: "play",
    79: "rewind",
    80: "fastforward",
    117: "contextmenu",
}


class EditorButtonDiscoveryDialog(xbmcgui.WindowDialog):
    def __init__(self):
        super().__init__()
        self.button_code = None
        self.remote_tag = None
        self.action_id = None
        self.cancelled = False
        self._build_controls()

    def _addon_media_path(self, filename):
        addon = get_addon()
        if not addon:
            return filename
        path = os.path.join(
            addon.getAddonInfo("path"),
            "resources",
            "skins",
            "default",
            "media",
            filename,
        )
        return path if xbmcvfs.exists(path) else "black.png"

    def _build_controls(self):
        white_texture = self._addon_media_path("white.png")
        try:
            overlay = xbmcgui.ControlImage(0, 0, 1280, 720, white_texture)
            overlay.setColorDiffuse("80000000")
            self.addControl(overlay)
        except Exception:
            pass
        try:
            panel = xbmcgui.ControlImage(250, 220, 780, 280, white_texture)
            panel.setColorDiffuse("F0202020")
            self.addControl(panel)
        except Exception:
            pass

        self.addControl(
            xbmcgui.ControlLabel(
                280, 248, 720, 45, "Skippy — Editor remote discovery", "font30", "FFFFFFFF"
            )
        )
        self.addControl(
            xbmcgui.ControlLabel(
                280,
                312,
                720,
                35,
                "Press the remote button to use for Segment Editor.",
                "font14",
                "FFB0D4E8",
            )
        )
        self.addControl(
            xbmcgui.ControlLabel(
                280,
                352,
                720,
                35,
                "Bluetooth/raw remotes save as key:<code>.",
                "font14",
                "FFFFFFFF",
            )
        )
        self.addControl(
            xbmcgui.ControlLabel(
                280,
                392,
                720,
                35,
                "CEC remotes save as Kodi remote button names when possible.",
                "font14",
                "FFFFFFFF",
            )
        )
        self.addControl(
            xbmcgui.ControlLabel(
                280, 442, 720, 30, "Back/Esc cancels.", "font12", "FFB0B0B0"
            )
        )

    def onAction(self, action):
        try:
            action_id = action.getId()
            button_code = action.getButtonCode()
        except Exception:
            action_id = None
            button_code = None

        if action_id in _CANCEL_ACTION_IDS:
            self.cancelled = True
            self.close()
            return

        if button_code:
            try:
                button_code_int = int(button_code)
            except Exception:
                button_code_int = None
            if action_id in _KEYBOARD_CONFIRM_ACTION_IDS and button_code_int in _KEYBOARD_CONFIRM_BUTTON_CODES:
                log(
                    f"Ignoring keyboard confirm during editor discovery: action_id={action_id}, button_code={button_code}"
                )
                return
            self.action_id = action_id
            self.button_code = button_code
            self.close()
            return

        remote_tag = _CEC_ACTION_TO_REMOTE_TAG.get(action_id)
        if remote_tag:
            self.action_id = action_id
            self.remote_tag = remote_tag
            self.close()
            return

        log(
            f"Ignoring unmapped editor discovery input: action_id={action_id}, button_code={button_code}"
        )


def discover_editor_remote_button(addon):
    set_editor_modal_open(True)
    dialog = None
    button_code = None
    remote_tag = None
    action_id = None
    cancelled = False
    try:
        dialog = EditorButtonDiscoveryDialog()
        dialog.doModal()
        button_code = getattr(dialog, "button_code", None)
        remote_tag = getattr(dialog, "remote_tag", None)
        action_id = getattr(dialog, "action_id", None)
        cancelled = getattr(dialog, "cancelled", False)
    finally:
        try:
            if dialog:
                del dialog
        except Exception:
            pass
        set_editor_modal_open(False)

    if cancelled:
        _skippy_toast(addon, "Editor button discovery cancelled", 2500)
        return
    if remote_tag:
        addon.setSetting("segment_editor_remote_button", remote_tag)
        install_editor_keymap(addon, notify=False)
        _skippy_toast(addon, f"Editor remote set: {remote_tag}", 4500)
        log_always(
            f"CEC remote editor button: action_id={action_id}, remote_tag={remote_tag}"
        )
        return

    if not button_code:
        _skippy_toast(addon, "No editor remote button captured", 3500)
        log(f"Editor discovery: no button code; action_id={action_id}")
        return

    value = f"key:{button_code}"
    addon.setSetting("segment_editor_remote_button", value)
    install_editor_keymap(addon, notify=False)
    _skippy_toast(addon, f"Editor remote set: {value}", 4500)
    log_always(
        f"Remote editor button: action_id={action_id}, button_code={button_code}"
    )


def main():
    from segment_editor_session import open_segment_editor

    open_segment_editor()


if __name__ == "__main__":
    main()
