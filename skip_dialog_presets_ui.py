# -*- coding: utf-8 -*-
"""Preset menu for the skip dialog: choose, save-as and delete (Custom mode looks)."""
from __future__ import annotations

import json
import time

import xbmcgui
import xbmcvfs

import skip_dialog_presets as sp
from settings_utils import get_addon, get_localized, notify_skippy

_INPUT_ALPHANUM = getattr(xbmcgui, "INPUT_ALPHANUM", 0)


def _loc(addon, sid, default, *args):
    return get_localized(addon, sid, default, *args)


def preset_row_label(addon, draft) -> str:
    name = sp.detect_preset(draft)
    return "%s: %s" % (
        _loc(addon, 46015, "Preset"),
        name if name else _loc(addon, 46016, "Custom"),
    )


def _select(heading, items, preselect=-1):
    dlg = xbmcgui.Dialog()
    try:
        return dlg.select(heading, items, preselect=preselect)
    except TypeError:
        return dlg.select(heading, items)


def _item_label(addon, name, builtin, current):
    label = name if builtin else _loc(addon, 46025, "%s (saved)", name)
    return ("✓ " + label) if name == current else label


def prompt_save_preset(addon, draft, suggested=""):
    """Ask for a name and store the draft as a user preset."""
    _save_current(addon, draft, suggested)


def _save_current(addon, draft, suggested=""):
    dlg = xbmcgui.Dialog()
    name = dlg.input(
        _loc(addon, 46019, "Preset name"), defaultt=suggested or "", type=_INPUT_ALPHANUM
    )
    name = sp.clean_name(name)
    if not name:
        return
    if name.lower() in {b.lower() for b in sp.builtin_names()}:
        dlg.ok("Skippy", _loc(addon, 46028, "That name is used by a built-in preset."))
        return
    if any(n.lower() == name.lower() for n in sp.load_user_presets()):
        if not dlg.yesno(
            "Skippy", _loc(addon, 46021, "A saved preset named %s already exists. Overwrite it?", name)
        ):
            return
    ok, _err = sp.save_user_preset(name, draft)
    notify_skippy(
        addon,
        _loc(addon, 46020, "Preset saved: %s", name)
        if ok
        else _loc(addon, 46026, "Could not save the preset."),
        title="Skippy",
        prefer_builtin=True,
    )


def _delete_saved(addon):
    user = sorted(sp.load_user_presets(), key=str.lower)
    if not user:
        notify_skippy(
            addon,
            _loc(addon, 46029, "There are no saved presets to delete."),
            title="Skippy",
            prefer_builtin=True,
        )
        return
    pick = _select(_loc(addon, 46018, "Delete a saved preset…"), user)
    if pick < 0:
        return
    name = user[pick]
    if not xbmcgui.Dialog().yesno(
        "Skippy", _loc(addon, 46022, "Delete preset %s?", name)
    ):
        return
    if sp.delete_user_preset(name):
        notify_skippy(
            addon,
            _loc(addon, 46023, "Preset deleted: %s", name),
            title="Skippy",
            prefer_builtin=True,
        )


PRESETS_FILE_PREFIX = "skippy-presets"


def _export_saved(addon):
    blob = sp.export_user_presets()
    if not blob.get("presets"):
        notify_skippy(addon, _loc(addon, 46041, "There are no saved presets to export."),
                      title="Skippy", prefer_builtin=True)
        return
    from settings_backup import _join_writable_folder_file

    folder = xbmcgui.Dialog().browse(
        3, _loc(addon, 46037, "Export saved presets…"), "files", "", False, False, ""
    )
    if not folder or not str(folder).strip():
        return
    name = "%s-%s.json" % (PRESETS_FILE_PREFIX, time.strftime("%Y%m%d-%H%M%S"))
    dest = _join_writable_folder_file(folder, name)
    handle = None
    try:
        handle = xbmcvfs.File(dest, "w")
        ok = bool(handle.write(json.dumps(blob, indent=2, ensure_ascii=False)))
    except Exception:
        ok = False
    finally:
        if handle is not None:
            handle.close()
    notify_skippy(
        addon,
        _loc(addon, 46039, "Presets exported: %s", name) if ok
        else _loc(addon, 46026, "Could not save the preset."),
        title="Skippy",
        prefer_builtin=True,
    )


def _import_presets(addon):
    from settings_backup import _restore_browse_result_is_json_file

    path = xbmcgui.Dialog().browse(
        1, _loc(addon, 46038, "Import presets…"), "files", ".json", False, False, ""
    )
    if not _restore_browse_result_is_json_file(path):
        return
    blob = None
    handle = None
    try:
        handle = xbmcvfs.File(path)
        blob = json.loads(handle.read())
    except Exception:
        blob = None
    finally:
        if handle is not None:
            handle.close()
    added = sp.merge_user_presets_from_backup(blob)
    notify_skippy(
        addon,
        _loc(addon, 46040, "Presets imported: %s", added) if added
        else _loc(addon, 46042, "No new presets were imported (the file has none, or the names already exist)."),
        title="Skippy",
        prefer_builtin=True,
    )


def present_preset_menu(addon, draft):
    """Pick / save / delete. Returns the applied preset's name, else None."""
    presets = sp.list_presets()
    current = sp.detect_preset(draft)
    items = [_item_label(addon, n, b, current) for n, _v, b in presets]
    names = [n for n, _v, _b in presets]
    save_idx = len(items)
    items.append(_loc(addon, 46017, "Save current look as preset…"))
    delete_idx = None
    if any(not b for _n, _v, b in presets):
        delete_idx = len(items)
        items.append(_loc(addon, 46018, "Delete a saved preset…"))
    export_idx = len(items)
    items.append(_loc(addon, 46037, "Export saved presets…"))
    import_idx = len(items)
    items.append(_loc(addon, 46038, "Import presets…"))
    pre = names.index(current) if current in names else -1
    pick = _select(_loc(addon, 46024, "Choose a preset"), items, pre)
    if pick < 0:
        return None
    if pick == save_idx:
        _save_current(addon, draft, current or "")
        return None
    if delete_idx is not None and pick == delete_idx:
        _delete_saved(addon)
        return None
    if pick == export_idx:
        _export_saved(addon)
        return None
    if pick == import_idx:
        _import_presets(addon)
        return None
    name, values, _builtin = presets[pick]
    sp.apply_preset(draft, values)
    return name


def show_skip_dialog_presets_menu():
    """Settings action: pick a preset, then preview it in the Customize screen.

    Nothing is stored until **Save** is pressed there; Cancel keeps the old look.
    """
    addon = get_addon()
    if not addon:
        return False
    from skip_dialog_customize_ui import load_skip_dialog_draft, show_skip_dialog_customize

    saved = load_skip_dialog_draft(addon)
    draft = dict(saved)
    if not present_preset_menu(addon, draft):
        return False
    return show_skip_dialog_customize(draft=draft, original=saved)
