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
    BAR_H,
    BOOL_KEYS,
    CHOICE_KEYS,
    FOCUS_LABELS,
    KEY_COUNTDOWN,
    KEY_FOCUS,
    KEY_LOOK,
    KEY_POSITION,
    KEY_PROGRESS,
    KEY_SIZE,
    KEY_STYLE,
    KEY_THUMBNAIL,
    POSITION_LABELS,
    SIZE_LARGE,
    STYLE_LABELS,
    customize_rows,
    cycle_choice,
    draft_setting_payload,
    is_native_style,
    load_popup_draft,
    popup_layout,
    popup_origin,
    seconds_left,
    window_fraction_left,
    zoom_corner,
)
from next_episode_dialog import mock_episode
from next_episode_look import (
    CAPS_ON,
    FOLLOW_LOOK,
    KEY_ALL_CAPS,
    KEY_BAR_STYLE,
    KEY_CARD_OPACITY,
    KEY_FOCUS_STYLE,
    KEY_HEADING_COLOR,
    KEY_TEXT_COLOR,
    LOOK_LABELS,
    OVERRIDE_KEYS,
    override_label,
)
from next_episode_toast import build_toast_texts
from next_episode_view import (
    MOCK_ID_OFFSET,
    countdown_mode,
    countdown_settings,
    countdown_text,
    fill_width,
    focus_is_close,
    look_properties,
    popup_ids,
    popup_placements,
    popup_texts,
    skip_text_color,
)
from settings_utils import get_addon, get_localized, log

XML_NAME = "NextEpisodeCustomize.xml"

ID_PANEL = 6000
ID_BACKDROP = 6001
ID_TITLE = 6002
ID_PREVIEW = 6020
ID_SAVE = 6021
ID_CANCEL = 6022
ID_LOOKS = 6023
ROW_IDS = {
    KEY_STYLE: 6011,
    KEY_POSITION: 6012,
    KEY_SIZE: 6036,
    KEY_THUMBNAIL: 6013,
    KEY_COUNTDOWN: 6014,
    KEY_PROGRESS: 6015,
    KEY_FOCUS: 6016,
    KEY_LOOK: 6017,
    KEY_TEXT_COLOR: 6030,
    KEY_HEADING_COLOR: 6031,
    KEY_ALL_CAPS: 6032,
    KEY_FOCUS_STYLE: 6033,
    KEY_BAR_STYLE: 6034,
    KEY_CARD_OPACITY: 6035,
}
# Left to right; the order is the order of the buttons on screen.
FOOTER_IDS = (ID_PREVIEW, ID_LOOKS, ID_SAVE, ID_CANCEL)

# Row names are the setting labels, so the modal and the settings page agree.
ROW_LABEL_IDS = {
    KEY_STYLE: (47030, "Popup style"),
    KEY_LOOK: (47080, "Popup look"),
    KEY_POSITION: (47034, "Popup position"),
    KEY_SIZE: (47151, "Popup size"),
    KEY_THUMBNAIL: (47036, "Show episode picture"),
    KEY_COUNTDOWN: (47038, "Show time left"),
    KEY_PROGRESS: (47040, "Show progress bar"),
    KEY_FOCUS: (47042, "Default button"),
    KEY_TEXT_COLOR: (47105, "Text colour"),
    KEY_HEADING_COLOR: (47106, "Heading colour"),
    KEY_ALL_CAPS: (47107, "All caps"),
    KEY_FOCUS_STYLE: (47108, "Button highlight"),
    KEY_BAR_STYLE: (47109, "Progress bar style"),
    KEY_CARD_OPACITY: (47110, "Card opacity"),
}

_PANEL_X = 16
_PANEL_Y = 41
_PANEL_W = 560
# The mockup: a stage the popup is drawn on, at the right of the panel (720p units).
ID_STAGE = 6100
MOCK_IDS = popup_ids(MOCK_ID_OFFSET)
_STAGE_X = 592
_STAGE_Y = 41
_STAGE_W = 672
_STAGE_H = 504
_MOCK_MARGIN = 20
# The example the mockup shows: 31 seconds left of a 45 second window.
MOCK_WINDOW_S = 45.0
MOCK_HEAD_S = 14.0


def mock_countdown_text(addon, caps_on) -> str:
    """The mockup's countdown line, as the saved "Show the prompt for" and "When the countdown ends" read.

    The bar stands where it always does (31 of 45 left); a prompt that stays up for a fixed time
    shows the same share of that time.
    """
    duration, action = countdown_settings(addon)
    left = seconds_left(MOCK_HEAD_S, MOCK_WINDOW_S)
    if duration > 0:
        left = int(round(duration * left / MOCK_WINDOW_S))
    return countdown_text(addon, caps_on, left, countdown_mode(action, duration > 0))
_ROW_TOP = 60
_ROW_H = 40
_ROW_STEP = 44
# The rows never take more than this (720p units), so the panel always fits the screen:
# with more rows than fit at the full step they sit closer together.
_ROWS_MAX_H = 510
_ROW_GAP = _ROW_STEP - _ROW_H
_FOOTER_H = 40
# Four buttons share the 520 px of a row: 122 px wide with 10 px between them.
_FOOTER_W = 122
_FOOTER_STEP = 132
_PANEL_BOTTOM_PAD = 20
_CANCEL_ACTIONS = (10, 92, 216)
_MOVE_LEFT = getattr(xbmcgui, "ACTION_MOVE_LEFT", 1)
_MOVE_RIGHT = getattr(xbmcgui, "ACTION_MOVE_RIGHT", 2)
_MOVE_UP = getattr(xbmcgui, "ACTION_MOVE_UP", 3)
_MOVE_DOWN = getattr(xbmcgui, "ACTION_MOVE_DOWN", 4)


def row_metrics(count):
    """``(distance between row tops, row height)`` in 720p units for this many rows."""
    step = min(_ROW_STEP, _ROWS_MAX_H // count) if count else _ROW_STEP
    return step, step - _ROW_GAP


def row_layout(rows):
    """``(row tops, footer top, panel height)`` in 720p units for the visible rows."""
    step, _height = row_metrics(len(rows))
    tops = [_ROW_TOP + step * n for n in range(len(rows))]
    footer_top = _ROW_TOP + step * len(rows) + 10
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
    if key == KEY_LOOK:
        return LOOK_LABELS[value]
    if key in OVERRIDE_KEYS:
        if value == FOLLOW_LOOK:
            return get_localized(addon, 47111, "Same as look")
        if key == KEY_ALL_CAPS:
            return (
                get_localized(addon, 44105, "Yes")
                if value == CAPS_ON
                else get_localized(addon, 44106, "No")
            )
        return override_label(key, value)
    if key == KEY_POSITION:
        return POSITION_LABELS[value]
    if key == KEY_SIZE:
        if value == SIZE_LARGE:
            return get_localized(addon, 47154, "Large")
        return get_localized(addon, 47153, "Normal")
    return FOCUS_LABELS[value]


def nudge(draft, key, delta) -> None:
    """Change one value in place: a toggle flips, a choice moves along its options."""
    if key in BOOL_KEYS:
        draft[key] = not draft.get(key)
    elif key in CHOICE_KEYS:
        draft[key] = cycle_choice(key, draft.get(key), delta)
        if key == KEY_LOOK:
            # A new look starts clean, like applying a preset in the skip dialog: what was
            # changed on top of the old look no longer applies.
            for override in OVERRIDE_KEYS:
                draft[override] = FOLLOW_LOOK


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

    def _show(self, cid, visible):
        ctrl = self._ctrl(cid)
        if ctrl is not None:
            try:
                ctrl.setVisible(bool(visible))
            except Exception:
                pass

    def _set_prop(self, name, value):
        try:
            self.setProperty(name, value)
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
            (ID_LOOKS, get_localized(addon, 47128, "Looks…")),
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
        _step, row_h = row_metrics(len(shown))
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
            self._place(cid, 20, tops[shown.index(key)], 520, row_h)
        for n, cid in enumerate(FOOTER_IDS):
            self._place(cid, 20 + _FOOTER_STEP * n, footer_top, _FOOTER_W, _FOOTER_H)
        self._place(ID_BACKDROP, 0, 0, _PANEL_W, panel_h)
        self._place(ID_PANEL, _PANEL_X, _PANEL_Y, _PANEL_W, panel_h)
        self._refresh_mock()

    def _refresh_mock(self):
        """Redraw the mockup after every change; a failure leaves the rows working."""
        try:
            self._draw_mock()
        except Exception as exc:
            log("Next episode customize: drawing the mockup failed: %s" % exc)

    def _draw_mock(self):
        """The popup (or the toast) as the draft would show it, on the stage."""
        addon, draft = self.addon, self._draft
        episode = mock_episode(addon)
        self._set_prop("next_ep_mock_backdrop", episode.get("thumb") or "")
        native = is_native_style(draft)
        self._set_prop("next_ep_mock_native", "true" if native else "false")
        if native:
            heading, body = build_toast_texts(addon, episode)
            self._set_prop("next_ep_mock_toast_heading", heading)
            self._set_prop("next_ep_mock_toast_body", body)
            icon = (addon.getAddonInfo("icon") if addon else "") or ""
            self._set_prop("next_ep_mock_icon", icon)
            self._set_prop("next_ep_mock_ready", "true")
            return
        ids = MOCK_IDS
        show_thumb = bool(draft.get(KEY_THUMBNAIL)) and bool(episode.get("thumb"))
        layout = popup_layout(
            thumbnail=show_thumb,
            countdown=bool(draft.get(KEY_COUNTDOWN)),
            progress=bool(draft.get(KEY_PROGRESS)),
        )
        look, _tiled, props = look_properties(
            draft, addon, self._sc(BAR_H), skip_text_color(addon)
        )
        for name, value in props.items():
            self._set_prop(name, value)
        self._set_prop("next_ep_mock_focus", "close" if focus_is_close(draft) else "play")
        # The size: the skin grows the mock popup from the corner it sits in.
        self._set_prop("next_ep_zoom", zoom_corner(draft))
        texts = popup_texts(addon, look.all_caps, episode)
        self._set_prop("next_ep_heading", texts["heading"])
        self._set_prop("next_ep_label", texts["label"])
        self._set_prop("next_ep_thumb", episode.get("thumb") or "")
        self._set_prop("next_ep_has_thumb", "true" if show_thumb else "false")
        has_countdown = layout.countdown_y is not None
        has_bar = layout.bar_y is not None
        self._set_prop("next_ep_has_bar", "true" if has_bar else "false")
        if has_countdown:
            self._set_prop(
                "next_ep_countdown", mock_countdown_text(addon, look.all_caps)
            )
        x, y = popup_origin(
            draft.get(KEY_POSITION),
            layout.panel_w,
            layout.panel_h,
            screen_w=_STAGE_W,
            screen_h=_STAGE_H,
            margin_x=_MOCK_MARGIN,
            margin_y=_MOCK_MARGIN,
        )
        self._place(ids.panel, x, y, layout.panel_w, layout.panel_h)
        for cid, px, py, pw, ph in popup_placements(layout, ids):
            self._place(cid, px, py, pw, ph)
        self._show(ids.countdown, has_countdown)
        self._show(ids.bar_bg, has_bar)
        for cid, text in ((ids.play, texts["play"]), (ids.close, texts["close"])):
            ctrl = self._ctrl(cid)
            if ctrl is not None:
                try:
                    ctrl.setLabel(text)
                except Exception:
                    pass
        if has_bar:
            fraction = window_fraction_left(MOCK_HEAD_S, 0.0, MOCK_WINDOW_S)
            bar_w, bar_h = self._sc(layout.bar_w), self._sc(BAR_H)
            for cid, tiled in ((ids.bar_fill, True), (ids.bar_fill_stretch, False)):
                ctrl = self._ctrl(cid)
                if ctrl is not None:
                    try:
                        ctrl.setWidth(fill_width(tiled, fraction, bar_w, bar_h))
                    except Exception:
                        pass
        self._set_prop("next_ep_mock_ready", "true")

    def _focus_id(self):
        try:
            return int(self.getFocusId())
        except Exception:
            return ROW_IDS[KEY_STYLE]

    def _move_focus(self, delta):
        ids = nav_ids(self._draft)
        current = self._focus_id()
        if current in FOOTER_IDS:
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

    def _open_looks_menu(self):
        """Reset / save / load / delete a look, then redraw the rows and the mockup."""
        from next_episode_looks_ui import present_looks_menu

        try:
            present_looks_menu(self.addon, self._draft)
        except Exception as exc:
            log("Next episode customize: the looks menu failed: %s" % exc)
        self._refresh()
        try:
            self.setFocusId(ID_LOOKS)
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
        elif cid == ID_LOOKS:
            self._open_looks_menu()
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
