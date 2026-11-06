# -*- coding: utf-8 -*-
"""Customize next episode popup: pick the look, preview it, save."""

from __future__ import annotations

import xbmcgui

from addon_skin_resolution import (
    init_window_xml_dialog,
    probe_control_ids_for_xml,
    reconcile_window_xml_skin_resolution,
    scale_skin_coord,
)
from next_episode_appearance import (
    BASE_SCREEN_H,
    BASE_SCREEN_W,
    BOOL_KEYS,
    CHOICE_KEYS,
    FOCUS_LABELS,
    KEY_COUNTDOWN,
    KEY_FOCUS,
    KEY_POSITION,
    KEY_PROGRESS,
    KEY_STYLE,
    KEY_THUMBNAIL,
    POSITION_LABELS,
    STYLE_LABELS,
    customize_rows,
    cycle_choice,
    draft_setting_payload,
    is_native_style,
    load_popup_draft,
)
from settings_utils import get_addon, get_localized

XML_NAME = "NextEpisodeCustomize.xml"

ID_PANEL = 6000
ID_BACKDROP = 6001
ID_TITLE = 6002
ID_PREVIEW = 6020
ID_SAVE = 6021
ID_CANCEL = 6022
ROW_IDS = {
    KEY_STYLE: 6011,
    KEY_POSITION: 6012,
    KEY_THUMBNAIL: 6013,
    KEY_COUNTDOWN: 6014,
    KEY_PROGRESS: 6015,
    KEY_FOCUS: 6016,
}
FOOTER_IDS = (ID_PREVIEW, ID_SAVE, ID_CANCEL)

# Row names are the setting labels, so the modal and the settings page agree.
ROW_LABEL_IDS = {
    KEY_STYLE: (47030, "Popup style"),
    KEY_POSITION: (47034, "Popup position"),
    KEY_THUMBNAIL: (47036, "Show episode picture"),
    KEY_COUNTDOWN: (47038, "Show time left"),
    KEY_PROGRESS: (47040, "Show progress bar"),
    KEY_FOCUS: (47042, "Default button"),
}

_PANEL_W = 560
_ROW_TOP = 60
_ROW_H = 40
_ROW_STEP = 44
_FOOTER_H = 40
_PANEL_BOTTOM_PAD = 20
_CANCEL_ACTIONS = (10, 92, 216)
_MOVE_LEFT = getattr(xbmcgui, "ACTION_MOVE_LEFT", 1)
_MOVE_RIGHT = getattr(xbmcgui, "ACTION_MOVE_RIGHT", 2)
_MOVE_UP = getattr(xbmcgui, "ACTION_MOVE_UP", 3)
_MOVE_DOWN = getattr(xbmcgui, "ACTION_MOVE_DOWN", 4)


def row_layout(rows):
    """``(row tops, footer top, panel height)`` in 720p units for the visible rows."""
    tops = [_ROW_TOP + _ROW_STEP * n for n in range(len(rows))]
    footer_top = _ROW_TOP + _ROW_STEP * len(rows) + 10
    return tops, footer_top, footer_top + _FOOTER_H + _PANEL_BOTTOM_PAD


def nav_ids(draft):
    """Focus order, top to bottom: the visible rows, then the footer (Preview first)."""
    return [ROW_IDS[key] for key in customize_rows(draft)] + [ID_PREVIEW]


def changed_payload(draft, original) -> dict:
    """Only the settings whose stored text differs, so Save never rewrites the rest."""
    new, old = draft_setting_payload(draft), draft_setting_payload(original)
    return {key: value for key, value in new.items() if old.get(key) != value}


def value_text(addon, draft, key) -> str:
    value = draft.get(key)
    if key in BOOL_KEYS:
        return get_localized(addon, 44105, "Yes") if value else get_localized(addon, 44106, "No")
    if key == KEY_STYLE:
        return STYLE_LABELS[value]
    if key == KEY_POSITION:
        return POSITION_LABELS[value]
    return FOCUS_LABELS[value]


def nudge(draft, key, delta) -> None:
    """Change one value in place: a toggle flips, a choice moves along its options."""
    if key in BOOL_KEYS:
        draft[key] = not draft.get(key)
    elif key in CHOICE_KEYS:
        draft[key] = cycle_choice(key, draft.get(key), delta)


class NextEpisodeCustomize(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self._skin_resolution = init_window_xml_dialog(super(NextEpisodeCustomize, self), args)
        self._xml_layout = args[0] if args else XML_NAME
        self.addon = kwargs.get("addon") or get_addon()
        self._draft = dict(kwargs.get("draft") or load_popup_draft(self.addon))
        self._original = dict(kwargs.get("original") or self._draft)
        self._saved = False

    def _sc(self, value):
        return scale_skin_coord(value, getattr(self, "_skin_resolution", None))

    def _ctrl(self, cid):
        try:
            return self.getControl(cid)
        except Exception:
            return None

    def _place(self, cid, x, y, w=None, h=None):
        ctrl = self._ctrl(cid)
        if ctrl is None:
            return
        try:
            ctrl.setPosition(self._sc(x), self._sc(y))
            if w is not None:
                ctrl.setWidth(self._sc(w))
            if h is not None:
                ctrl.setHeight(self._sc(h))
        except Exception:
            pass

    def onInit(self):
        asked = getattr(self, "_skin_resolution", None)
        locked = reconcile_window_xml_skin_resolution(
            self, asked, control_ids=probe_control_ids_for_xml(self._xml_layout)
        )
        if locked != asked:
            self._skin_resolution = locked
        addon = self.addon
        for cid, text in (
            (ID_TITLE, get_localized(addon, 47032, "Customize next episode popup")),
            (ID_PREVIEW, get_localized(addon, 47052, "Preview")),
            (ID_SAVE, get_localized(addon, 44103, "Save")),
            (ID_CANCEL, get_localized(addon, 44104, "Cancel")),
        ):
            ctrl = self._ctrl(cid)
            if ctrl is not None:
                try:
                    ctrl.setLabel(text)
                except Exception:
                    pass
        self._refresh()
        try:
            self.setFocusId(ROW_IDS[KEY_STYLE])
        except Exception:
            pass

    def _refresh(self):
        """Labels for every row, only the rows that apply, and the footer right below them."""
        addon = self.addon
        shown = customize_rows(self._draft)
        tops, footer_top, panel_h = row_layout(shown)
        for key, cid in ROW_IDS.items():
            ctrl = self._ctrl(cid)
            if ctrl is None:
                continue
            visible = key in shown
            try:
                ctrl.setVisible(visible)
            except Exception:
                pass
            if not visible:
                continue
            name = get_localized(addon, *ROW_LABEL_IDS[key])
            try:
                ctrl.setLabel(label=name, label2=value_text(addon, self._draft, key))
            except Exception:
                pass
            self._place(cid, 20, tops[shown.index(key)], 520, _ROW_H)
        for n, cid in enumerate(FOOTER_IDS):
            self._place(cid, 20 + 180 * n, footer_top, 160, _FOOTER_H)
        self._place(ID_BACKDROP, 0, 0, _PANEL_W, panel_h)
        self._place(
            ID_PANEL,
            (BASE_SCREEN_W - _PANEL_W) // 2,
            (BASE_SCREEN_H - panel_h) // 2,
            _PANEL_W,
            panel_h,
        )

    def _focus_id(self):
        try:
            return int(self.getFocusId())
        except Exception:
            return ROW_IDS[KEY_STYLE]

    def _move_focus(self, delta):
        ids = nav_ids(self._draft)
        current = self._focus_id()
        if current in (ID_SAVE, ID_CANCEL):
            current = ID_PREVIEW
        if current not in ids:
            current = ids[0]
        try:
            self.setFocusId(ids[(ids.index(current) + delta) % len(ids)])
        except Exception:
            pass

    def _move_footer(self, delta):
        current = self._focus_id()
        if current in FOOTER_IDS:
            try:
                self.setFocusId(FOOTER_IDS[(FOOTER_IDS.index(current) + delta) % len(FOOTER_IDS)])
            except Exception:
                pass

    def _key_for(self, cid):
        for key, row_id in ROW_IDS.items():
            if row_id == cid:
                return key
        return None

    def _nudge(self, cid, delta):
        key = self._key_for(cid)
        if key is None:
            return
        nudge(self._draft, key, delta)
        self._refresh()
        try:
            self.setFocusId(cid)
        except Exception:
            pass

    def _preview(self):
        from next_episode_dialog import show_preview
        from next_episode_toast import build_toast_texts

        addon = self.addon
        if is_native_style(self._draft):
            from next_episode_dialog import mock_episode

            heading, body = build_toast_texts(addon, mock_episode(addon))
            try:
                xbmcgui.Dialog().notification(
                    heading, body, addon.getAddonInfo("icon") or "", 6000, False
                )
            except Exception:
                pass
            return
        show_preview(addon, self._draft)
        try:
            self.setFocusId(ID_PREVIEW)
        except Exception:
            pass

    def _save_and_close(self):
        addon = self.addon
        changes = changed_payload(self._draft, self._original)
        if addon:
            for key, value in changes.items():
                try:
                    addon.setSetting(key, value)
                except Exception:
                    pass
        self._saved = True
        self.close()

    def onClick(self, controlId):
        try:
            cid = int(controlId)
        except (TypeError, ValueError):
            return
        if cid == ID_SAVE:
            self._save_and_close()
        elif cid == ID_CANCEL:
            self.close()
        elif cid == ID_PREVIEW:
            self._preview()
        elif cid in ROW_IDS.values():
            self._nudge(cid, 1)

    def onAction(self, action):
        aid = action.getId()
        if aid in _CANCEL_ACTIONS:
            self.close()
        elif aid == _MOVE_DOWN:
            self._move_focus(1)
        elif aid == _MOVE_UP:
            self._move_focus(-1)
        elif aid in (_MOVE_LEFT, _MOVE_RIGHT):
            delta = 1 if aid == _MOVE_RIGHT else -1
            cid = self._focus_id()
            if cid in FOOTER_IDS:
                self._move_footer(delta)
            else:
                self._nudge(cid, delta)


def show_next_episode_customize(draft=None, original=None):
    """Open the Customize modal. Returns True when the user saved."""
    addon = get_addon()
    if not addon:
        return False
    kwargs = {"addon": addon}
    if draft is not None:
        kwargs["draft"] = draft
        kwargs["original"] = original or load_popup_draft(addon)
    dialog = NextEpisodeCustomize(XML_NAME, addon.getAddonInfo("path"), "default", **kwargs)
    dialog.doModal()
    saved = bool(getattr(dialog, "_saved", False))
    del dialog
    return saved
