# -*- coding: utf-8 -*-
"""The **Looks…** menu of the Customize next episode popup screen.

Reset everything to the defaults, save the look on screen under a name, load a look saved
earlier or delete one. Everything works on the Customize draft, so nothing reaches the settings
until **Save** is pressed on that screen; only saving and deleting a named look write at once
(to the looks file), like the skip dialog's presets do.
"""

from __future__ import annotations

import xbmcgui

import next_episode_saved_looks as sl
from next_episode_appearance import DEFAULT_DRAFT
from settings_utils import get_localized, notify_skippy

_INPUT_ALPHANUM = getattr(xbmcgui, "INPUT_ALPHANUM", 0)

ID_BUTTON = 47128
ID_HEADING = 47129
ID_RESET = 47130
ID_SAVE = 47131
ID_DELETE = 47132
ID_NAME = 47133
ID_OVERWRITE = 47134
ID_SAVED = 47135
ID_SAVE_FAILED = 47136
ID_ALREADY_SAVED = 47137
ID_BUILTIN_LOOK = 47138
ID_NONE_TO_DELETE = 47139
ID_DELETE_ASK = 47140
ID_DELETED = 47141
ID_BUILTIN_NAME = 47142
ID_LIMIT = 47143

_DEFAULT_TEXT = {
    ID_BUTTON: "Looks…",
    ID_HEADING: "Popup looks",
    ID_RESET: "Reset to defaults",
    ID_SAVE: "Save this look…",
    ID_DELETE: "Delete a saved look…",
    ID_NAME: "Look name",
    ID_OVERWRITE: "A saved look named %s already exists. Overwrite it?",
    ID_SAVED: "Look saved: %s",
    ID_SAVE_FAILED: "Could not save the look.",
    ID_ALREADY_SAVED: "This look is already saved as %s.",
    ID_BUILTIN_LOOK: "This is the built-in look %s.",
    ID_NONE_TO_DELETE: "There are no saved looks to delete.",
    ID_DELETE_ASK: "Delete look %s?",
    ID_DELETED: "Look deleted: %s",
    ID_BUILTIN_NAME: "That name is used by a built-in look.",
    ID_LIMIT: "You can save up to %s looks. Delete one first.",
}


def _loc(addon, sid, *args):
    return get_localized(addon, sid, _DEFAULT_TEXT[sid], *args)


def _select(heading, items, preselect=-1):
    dialog = xbmcgui.Dialog()
    try:
        return dialog.select(heading, items, preselect=preselect)
    except TypeError:
        return dialog.select(heading, items)


def _toast(addon, message):
    notify_skippy(addon, message, title="Skippy", prefer_builtin=True)


def reset_to_defaults(draft) -> None:
    """Everything on the Customize screen back to its default (nothing is saved yet)."""
    draft.update(DEFAULT_DRAFT)


def _save_current(addon, draft) -> None:
    dialog = xbmcgui.Dialog()
    values = sl.snapshot(draft)
    builtin = sl.builtin_look_name(values)
    if builtin:
        dialog.ok("Skippy", _loc(addon, ID_BUILTIN_LOOK, builtin))
        return
    twin = sl.find_saved_look(values)
    if twin:
        dialog.ok("Skippy", _loc(addon, ID_ALREADY_SAVED, twin))
        return
    name = sl.clean_name(dialog.input(_loc(addon, ID_NAME), defaultt="", type=_INPUT_ALPHANUM))
    if not name:
        return
    if name.lower() in sl.builtin_names():
        dialog.ok("Skippy", _loc(addon, ID_BUILTIN_NAME))
        return
    if any(known.lower() == name.lower() for known in sl.load_user_looks()):
        if not dialog.yesno("Skippy", _loc(addon, ID_OVERWRITE, name)):
            return
    ok, code = sl.save_user_look(name, draft)
    if ok:
        _toast(addon, _loc(addon, ID_SAVED, name))
    elif code == sl.ERR_LIMIT:
        _toast(addon, _loc(addon, ID_LIMIT, sl.MAX_USER_LOOKS))
    else:
        _toast(addon, _loc(addon, ID_SAVE_FAILED))


def _delete_saved(addon) -> None:
    names = [name for name, _values in sl.list_user_looks()]
    if not names:
        _toast(addon, _loc(addon, ID_NONE_TO_DELETE))
        return
    pick = _select(_loc(addon, ID_DELETE), names)
    if pick < 0:
        return
    name = names[pick]
    if not xbmcgui.Dialog().yesno("Skippy", _loc(addon, ID_DELETE_ASK, name)):
        return
    if sl.delete_user_look(name):
        _toast(addon, _loc(addon, ID_DELETED, name))


def present_looks_menu(addon, draft) -> bool:
    """Show the menu and carry out the pick. True when the draft was changed (reset or load)."""
    saved = sl.list_user_looks()
    current = sl.detect_saved_look(draft)
    items = [_loc(addon, ID_RESET)]
    first_saved = len(items)
    names = [name for name, _values in saved]
    items.extend(("✓ " + name) if name == current else name for name in names)
    save_idx = len(items)
    items.append(_loc(addon, ID_SAVE))
    delete_idx = None
    if names:
        delete_idx = len(items)
        items.append(_loc(addon, ID_DELETE))
    preselect = first_saved + names.index(current) if current in names else -1
    pick = _select(_loc(addon, ID_HEADING), items, preselect)
    if pick < 0:
        return False
    if pick == 0:
        reset_to_defaults(draft)
        return True
    if pick == save_idx:
        _save_current(addon, draft)
        return False
    if delete_idx is not None and pick == delete_idx:
        _delete_saved(addon)
        return False
    name, values = saved[pick - first_saved]
    return sl.apply_look(draft, values)
