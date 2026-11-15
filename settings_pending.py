# -*- coding: utf-8 -*-
"""Settings saved by a Customize screen while Kodi's add-on settings window is open.

When a script calls ``Addon.setSetting`` while the add-on's own settings window is open,
Kodi hands the value to that window instead of writing it to disk: the window shows it and
stores it when it is closed. A script that reads the setting before then (``getSetting``)
still gets the old value from disk. So a Customize screen opened a second time from the
settings window showed the values from before the first Save, as if the Save was lost.

Worse, the settings window stores what it holds only when it is closed with **OK**. Closed
with Back or Cancel, Kodi reloads the settings from disk and everything the Customize screen
saved is gone (reported as "settings revert to the default teal every time").

So while the settings window is open, a Customize Save does three things: it hands the values
to the window as before (so **OK** stores them with the rest), it writes them straight into
``addon_data/service.skippy/settings.xml`` (so Back and Cancel reload them), and it keeps them in
a Home window property, read back first by a Customize screen opened again before the settings
window closes. The property is cleared when the settings window has been closed (the service's
``onSettingsChanged``), or the next time it is read with no settings window open.
"""

from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET

PENDING_PROP = "skippy.pending_settings.v1"


def _window():
    import xbmcgui

    return xbmcgui.Window(10000)


def addon_settings_open() -> bool:
    """True while an add-on settings window is open (under the Customize screen)."""
    try:
        import xbmc

        return bool(xbmc.getCondVisibility("Window.IsActive(addonsettings)"))
    except Exception:
        return False


def clear_pending() -> None:
    try:
        _window().clearProperty(PENDING_PROP)
    except Exception:
        pass


def read_pending() -> dict:
    """``{setting id: text}`` saved since the settings window opened; ``{}`` when it is closed."""
    if not addon_settings_open():
        clear_pending()
        return {}
    try:
        raw = _window().getProperty(PENDING_PROP)
        data = json.loads(raw) if raw else {}
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items() if isinstance(k, str)}


def note_pending(values) -> None:
    """Remember ``values`` (just passed to ``setSetting``) while the settings window holds them."""
    if not values or not addon_settings_open():
        return
    merged = read_pending()
    merged.update({str(k): str(v) for k, v in dict(values).items()})
    try:
        _window().setProperty(PENDING_PROP, json.dumps(merged, separators=(",", ":")))
    except Exception:
        pass


def drop_if_settings_closed(win=None) -> bool:
    """For the service loop: forget pending values once no settings window is open.

    The settings window can also be left without storing anything, and then Kodi sends no
    ``onSettingsChanged``. Returns True when something was dropped.
    """
    try:
        win = win or _window()
        if not win.getProperty(PENDING_PROP):
            return False
    except Exception:
        return False
    if addon_settings_open():
        return False
    try:
        win.clearProperty(PENDING_PROP)
    except Exception:
        return False
    return True


SETTINGS_FILE = "settings.xml"


def _settings_file():
    from skippy_profile_store import profile_path

    return profile_path(SETTINGS_FILE)


def write_settings_file(values, path=None) -> bool:
    """Put ``values`` into Kodi's stored settings file for this add-on; True when written.

    Only the given ids change; every other line is kept. A changed value loses Kodi's
    ``default="true"`` mark (it is the user's choice now). A missing file is created.
    """
    if not values:
        return True
    path = path or _settings_file()
    if not path:
        return False
    try:
        if os.path.isfile(path):
            tree = ET.parse(path)
            root = tree.getroot()
        else:
            root = ET.Element("settings", {"version": "2"})
            tree = ET.ElementTree(root)
        by_id = {el.get("id"): el for el in root.findall("setting")}
        for key, value in values.items():
            el = by_id.get(key)
            if el is None:
                el = ET.SubElement(root, "setting", {"id": str(key)})
            el.attrib.pop("default", None)
            el.text = str(value)
        try:
            ET.indent(tree, space="    ")
        except AttributeError:
            pass
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "wb") as handle:
            tree.write(handle, encoding="utf-8", xml_declaration=False, short_empty_elements=False)
        os.replace(tmp, path)
        return True
    except Exception:
        return False


class PendingSettingsAddon:
    """An ``xbmcaddon.Addon`` that reads values a Customize screen saved but Kodi has not stored yet.

    ``getSetting`` answers from those values first; ``setSetting`` writes through and records the
    value. Everything else goes to the real add-on object.
    """

    def __init__(self, addon, pending=None):
        self._addon = addon
        self._pending = dict(read_pending() if pending is None else pending)

    def getSetting(self, key):
        if key in self._pending:
            return self._pending[key]
        return self._addon.getSetting(key)

    def getSettingString(self, key):
        if key in self._pending:
            return self._pending[key]
        return self._addon.getSettingString(key)

    def setSetting(self, key, value):
        result = self._addon.setSetting(key, value)
        self._pending[key] = str(value)
        if addon_settings_open():
            # The open settings window holds the value until OK; Back or Cancel would drop it.
            write_settings_file({key: value})
        note_pending({key: value})
        return result

    def __getattr__(self, name):
        return getattr(self._addon, name)


def with_pending(addon):
    """``addon`` wrapped so unsaved Customize values are seen; ``addon`` itself when there are none
    to see and the settings window is closed, or when there is no add-on."""
    if addon is None or isinstance(addon, PendingSettingsAddon):
        return addon
    if not addon_settings_open():
        clear_pending()
        return addon
    return PendingSettingsAddon(addon)
