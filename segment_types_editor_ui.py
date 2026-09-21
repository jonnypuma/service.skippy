# -*- coding: utf-8 -*-
"""WindowXML editor for the segment-types catalog (draft until Save)."""
from __future__ import annotations

import xbmcgui

from addon_skin_resolution import (
    SEGMENT_TYPES_LIST_PROBE_ID,
    init_window_xml_dialog,
    reconcile_window_xml_skin_resolution,
)
from segment_types import (
    SKIP_CYCLE,
    add_alias,
    add_custom_type,
    clone_types,
    delete_custom_type,
    ensure_catalog,
    remove_alias,
    save_catalog,
    set_edl_action,
    set_skip_mode,
    skip_mode_label,
    unused_edl_actions,
    validate_types,
)
from settings_utils import get_addon, get_localized, log, notify_skippy

ID_TITLE = 5200
ID_SUBTITLE = 5201
ID_LIST = 5210
ID_SKIP = 5220
ID_EDL = 5221
ID_ALIASES = 5222
ID_DELETE = 5223
ID_ADD = 5230
ID_SAVE = 5231
ID_CANCEL = 5232

_CANCEL_ACTIONS = (10, 92, 216)


class SegmentTypesEditor(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self._skin_resolution = init_window_xml_dialog(
            super(SegmentTypesEditor, self), args
        )
        self.addon = kwargs.get("addon") or get_addon()
        self._original = clone_types(kwargs.get("types") or ensure_catalog())
        self._draft = clone_types(self._original)
        self._saved = False
        self._closing = False
        self._selected_id = self._draft[0]["id"] if self._draft else ""

    def _T(self, string_id, default, *fmt):
        return get_localized(self.addon, string_id, default, *fmt)

    def _ctrl(self, cid):
        try:
            return self.getControl(cid)
        except Exception:
            return None

    def _set_label(self, cid, text):
        ctrl = self._ctrl(cid)
        if ctrl:
            try:
                ctrl.setLabel(text)
            except Exception:
                pass

    def _selected_type(self):
        needle = self._selected_id
        for type_row in self._draft:
            if type_row.get("id") == needle:
                return type_row
        return self._draft[0] if self._draft else None

    def _refresh_list(self):
        lst = self._ctrl(ID_LIST)
        if lst is None:
            return
        try:
            lst.reset()
        except Exception:
            return
        selected = 0
        for i, type_row in enumerate(self._draft):
            skip = skip_mode_label(type_row.get("skip_mode"))
            label2 = "%s  ·  EDL %s" % (skip, type_row.get("edl_action"))
            item = xbmcgui.ListItem(type_row.get("label") or type_row["id"], label2)
            try:
                item.setProperty("skippy_type_id", type_row["id"])
            except Exception:
                pass
            lst.addItem(item)
            if type_row["id"] == self._selected_id:
                selected = i
        try:
            if self._draft:
                lst.selectItem(selected)
        except Exception:
            pass
        type_row = self._selected_type()
        delete_ctrl = self._ctrl(ID_DELETE)
        if delete_ctrl is not None and type_row is not None:
            try:
                delete_ctrl.setEnabled(not bool(type_row.get("builtin")))
            except Exception:
                pass

    def onInit(self):
        asked = getattr(self, "_skin_resolution", None)
        locked = reconcile_window_xml_skin_resolution(
            self, asked, control_ids=(SEGMENT_TYPES_LIST_PROBE_ID,)
        )
        if locked != asked:
            self._skin_resolution = locked
        self._set_label(ID_TITLE, self._T(32106, "Segment types and skip behavior"))
        self._set_label(
            ID_SUBTITLE,
            self._T(
                45001,
                "Always / Ask / Never and EDL number for each type. Built-ins cannot be deleted.",
            ),
        )
        self._set_label(ID_SKIP, self._T(45019, "Skip mode"))
        self._set_label(ID_EDL, self._T(45005, "EDL"))
        self._set_label(ID_ALIASES, self._T(45006, "Aliases"))
        self._set_label(ID_DELETE, self._T(45007, "Delete"))
        self._set_label(ID_ADD, self._T(45008, "Add type"))
        self._set_label(ID_SAVE, self._T(44103, "Save"))
        self._set_label(ID_CANCEL, self._T(44104, "Cancel"))
        self._refresh_list()
        try:
            self.setFocusId(ID_LIST)
        except Exception:
            pass

    def _sync_selection_from_list(self):
        lst = self._ctrl(ID_LIST)
        if lst is None or not self._draft:
            return
        try:
            pos = int(lst.getSelectedPosition())
        except Exception:
            return
        if 0 <= pos < len(self._draft):
            self._selected_id = self._draft[pos]["id"]
            type_row = self._draft[pos]
            delete_ctrl = self._ctrl(ID_DELETE)
            if delete_ctrl is not None:
                try:
                    delete_ctrl.setEnabled(not bool(type_row.get("builtin")))
                except Exception:
                    pass

    def _cycle_skip(self):
        self._sync_selection_from_list()
        type_row = self._selected_type()
        if type_row is None:
            return
        nxt = SKIP_CYCLE[
            (SKIP_CYCLE.index(type_row.get("skip_mode") or "never") + 1) % 3
        ]
        set_skip_mode(self._draft, type_row["id"], nxt)
        self._refresh_list()

    def _pick_edl(self):
        self._sync_selection_from_list()
        type_row = self._selected_type()
        if type_row is None:
            return
        current = int(type_row["edl_action"])
        options = [current] + [n for n in unused_edl_actions(self._draft) if n != current]
        labels = [str(n) for n in options]
        idx = xbmcgui.Dialog().select(self._T(45020, "Choose EDL number"), labels)
        if idx < 0:
            return
        err = set_edl_action(self._draft, type_row["id"], options[idx])
        if err:
            xbmcgui.Dialog().ok(self._T(32106, "Segment types and skip behavior"), err)
            return
        self._refresh_list()

    def _edit_aliases(self):
        self._sync_selection_from_list()
        type_row = self._selected_type()
        if type_row is None:
            return
        heading = self._T(45018, "Edit aliases")
        while True:
            aliases = list(type_row.get("aliases") or [])
            options = [self._T(45016, "Add alias")] + aliases
            idx = xbmcgui.Dialog().select(heading, options)
            if idx < 0:
                break
            if idx == 0:
                phrase = xbmcgui.Dialog().input(self._T(45016, "Add alias"))
                if not phrase:
                    continue
                err = add_alias(self._draft, type_row["id"], phrase)
                if err:
                    xbmcgui.Dialog().ok(heading, err)
                type_row = self._selected_type()
                continue
            phrase = aliases[idx - 1]
            if xbmcgui.Dialog().yesno(
                heading, self._T(45017, "Remove alias") + "\n" + phrase
            ):
                remove_alias(self._draft, type_row["id"], phrase)
                type_row = self._selected_type()
        self._refresh_list()

    def _add_type(self):
        name = xbmcgui.Dialog().input(self._T(45011, "Type name"))
        if not name:
            return
        row, err = add_custom_type(self._draft, name)
        if err:
            xbmcgui.Dialog().ok(self._T(32106, "Segment types and skip behavior"), err)
            return
        if row:
            self._selected_id = row["id"]
        self._refresh_list()

    def _delete_type(self):
        self._sync_selection_from_list()
        type_row = self._selected_type()
        if type_row is None:
            return
        if type_row.get("builtin"):
            xbmcgui.Dialog().ok(
                self._T(32106, "Segment types and skip behavior"),
                self._T(45012, "Built-in types cannot be deleted."),
            )
            return
        if not xbmcgui.Dialog().yesno(
            self._T(45007, "Delete"),
            self._T(45013, "Delete this custom type?"),
        ):
            return
        err = delete_custom_type(self._draft, type_row["id"])
        if err:
            xbmcgui.Dialog().ok(self._T(32106, "Segment types and skip behavior"), err)
            return
        self._selected_id = self._draft[0]["id"] if self._draft else ""
        self._refresh_list()

    def _save_and_close(self):
        err = validate_types(self._draft)
        if err:
            xbmcgui.Dialog().ok(self._T(32106, "Segment types and skip behavior"), err)
            return
        if not save_catalog(self._draft):
            xbmcgui.Dialog().ok(
                self._T(32106, "Segment types and skip behavior"),
                self._T(45022, "Could not save segment types."),
            )
            return
        self._saved = True
        notify_skippy(
            self.addon,
            self._T(45023, "Segment types saved."),
            title=self._T(43000, "Skippy"),
        )
        self._closing = True
        self.close()

    def _cancel_and_close(self):
        self._saved = False
        self._closing = True
        self.close()

    def onClick(self, controlId):
        try:
            cid = int(controlId)
        except (TypeError, ValueError):
            return
        if cid == ID_LIST:
            self._sync_selection_from_list()
            self._edit_aliases()
            return
        if cid == ID_SKIP:
            self._cycle_skip()
            return
        if cid == ID_EDL:
            self._pick_edl()
            return
        if cid == ID_ALIASES:
            self._edit_aliases()
            return
        if cid == ID_DELETE:
            self._delete_type()
            return
        if cid == ID_ADD:
            self._add_type()
            return
        if cid == ID_SAVE:
            self._save_and_close()
            return
        if cid == ID_CANCEL:
            self._cancel_and_close()

    def onAction(self, action):
        aid = action.getId()
        if aid in _CANCEL_ACTIONS:
            self._cancel_and_close()


def show_segment_types_editor():
    addon = get_addon()
    if not addon:
        return False
    path = addon.getAddonInfo("path")
    dialog = SegmentTypesEditor(
        "SegmentTypesEditor.xml", path, "default", addon=addon
    )
    dialog.doModal()
    saved = bool(getattr(dialog, "_saved", False))
    del dialog
    log("Segment types editor closed (saved=%s)" % saved)
    return saved
