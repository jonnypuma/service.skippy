# -*- coding: utf-8 -*-
"""Settings saved by a Customize screen while Kodi's add-on settings window is open.

When a script calls ``Addon.setSetting`` while the add-on's own settings window is open,
Kodi hands the value to that window instead of writing it to disk: the window shows it and
stores it when it is closed. A script that reads the setting before then (``getSetting``)
still gets the old value from disk. So a Customize screen opened a second time from the
settings window showed the values from before the first Save, as if the Save was lost.

Customize screens therefore keep what they saved in a Home window property while the
settings window is open, and read it back first. The property is cleared when the
settings window has been closed (the service's ``onSettingsChanged``), or the next time it
is read with no settings window open.
"""

from __future__ import annotations

import json

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
