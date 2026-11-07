# -*- coding: utf-8 -*-
"""Skippy panel: a list or a message in the same look as the Customize screens.

Statistics, Manage saved auto-skips, Manage autoplay by show and the choices inside them use
this window: navy panel, tinted rows with a rounded teal highlight, the name of a row at the left
and its value at the right, and the Customize footer buttons. ``SkippyPanel.xml`` holds the look;
this module fills it and sizes the panel to what it shows. If the window cannot be opened, the
grey editor dialogs (``skippy_editor_modal_skin``) are the fallback, then Kodi's own dialogs.
"""

from __future__ import annotations

from dataclasses import dataclass

import xbmcgui

from addon_skin_resolution import (
    init_window_xml_dialog,
    probe_control_ids_for_xml,
    reconcile_window_xml_skin_resolution,
    scale_skin_coord,
)
from settings_utils import get_addon, get_localized, log

XML_NAME = "SkippyPanel.xml"

ID_PANEL = 7000
ID_BACKDROP = 7001
ID_TITLE = 7002
ID_SUBTITLE = 7003
ID_MESSAGE = 7004
ID_FOOTNOTE = 7005
ID_LIST = 7050
ID_SCROLL = 7060
FOOTER_IDS = (7090, 7091, 7092)

RESULT_CANCEL = "cancel"
RESULT_ROW = "row"
RESULT_BUTTON = "button"

# 720p units, the same numbers as Customize next episode popup.
PANEL_X = 360
PANEL_W = 560
INNER_X = 20
INNER_W = 520
ROW_TOP = 60
SUBTITLE_EXTRA = 16
ROW_H = 40
ROW_STEP = 44
FOOTER_H = 40
FOOTER_GAP = 10
BODY_TO_FOOTER = 10
BOTTOM_PAD = 20
FOOTNOTE_H = 26
FOOTNOTE_GAP = 4
SCREEN_H = 720
SCREEN_MARGIN = 20
MAX_PANEL_H = SCREEN_H - 2 * SCREEN_MARGIN
MIN_ROWS = 3
MESSAGE_LINE_H = 26
MESSAGE_CHARS_PER_LINE = 52

_CANCEL_ACTIONS = (10, 92, 216)
_MOVE_UP = getattr(xbmcgui, "ACTION_MOVE_UP", 3)
_MOVE_DOWN = getattr(xbmcgui, "ACTION_MOVE_DOWN", 4)
_PAGE_UP = getattr(xbmcgui, "ACTION_PAGE_UP", 5)
_PAGE_DOWN = getattr(xbmcgui, "ACTION_PAGE_DOWN", 6)


@dataclass(frozen=True)
class PanelRow:
    label: str
    label2: str = ""
    header: bool = False


def normalize_rows(rows) -> list:
    """Rows from strings, ``(name, value)`` pairs, dicts or ``PanelRow`` objects."""
    out = []
    for row in rows or ():
        if isinstance(row, PanelRow):
            out.append(row)
        elif isinstance(row, dict):
            out.append(
                PanelRow(
                    str(row.get("label") or ""),
                    str(row.get("label2") or ""),
                    bool(row.get("header")),
                )
            )
        elif isinstance(row, (tuple, list)):
            label = str(row[0]) if len(row) > 0 else ""
            label2 = str(row[1]) if len(row) > 1 else ""
            out.append(PanelRow(label, label2))
        else:
            out.append(PanelRow(str(row)))
    return out


def row_text(row: PanelRow) -> str:
    """One-line text of a row, for the fallback dialogs."""
    if row.label2:
        return "%s: %s" % (row.label, row.label2)
    return row.label


def message_line_count(message: str) -> int:
    lines = 0
    for line in (message or "").split("\n"):
        lines += max(1, -(-len(line) // MESSAGE_CHARS_PER_LINE))
    return lines


def panel_layout(n_rows, has_subtitle, message_lines, has_footnote, n_buttons) -> dict:
    """Geometry (720p units) of the panel for what it shows."""
    list_top = ROW_TOP + (SUBTITLE_EXTRA if has_subtitle else 0)
    footnote_h = (FOOTNOTE_H + FOOTNOTE_GAP) if has_footnote else 0
    below = footnote_h + BODY_TO_FOOTER + FOOTER_H + BOTTOM_PAD
    budget = MAX_PANEL_H - list_top - below
    if n_rows > 0:
        fit = max(MIN_ROWS, budget // ROW_STEP)
        visible = min(n_rows, fit)
        body_h = visible * ROW_STEP
    else:
        visible = 0
        body_h = max(MESSAGE_LINE_H, min(max(1, message_lines) * MESSAGE_LINE_H + 8, budget))
    body_bottom = list_top + body_h
    footer_top = body_bottom + footnote_h + BODY_TO_FOOTER
    panel_h = footer_top + FOOTER_H + BOTTOM_PAD
    count = max(1, min(3, int(n_buttons)))
    button_w = (INNER_W - FOOTER_GAP * (count - 1)) // count
    return {
        "list_top": list_top,
        "body_h": body_h,
        "visible_rows": visible,
        "scrolls": n_rows > visible,
        "footnote_top": body_bottom,
        "footer_top": footer_top,
        "panel_h": panel_h,
        "panel_y": max(SCREEN_MARGIN, (SCREEN_H - panel_h) // 2),
        "button_w": button_w,
        "button_xs": [INNER_X + (button_w + FOOTER_GAP) * n for n in range(count)],
        "button_ws": [button_w] * (count - 1) + [INNER_W - (button_w + FOOTER_GAP) * (count - 1)],
    }


def next_selectable(rows, position, direction) -> int:
    """The row to land on when ``position`` is a heading: one more step the way the user was
    going, else the nearest row the other way, else where it is."""
    for step in (direction, -direction):
        pos = position + step
        while 0 <= pos < len(rows):
            if not rows[pos].header:
                return pos
            pos += step
    return position


def first_selectable(rows, start=0) -> int:
    start = max(0, min(int(start or 0), len(rows) - 1)) if rows else 0
    if rows and not rows[start].header:
        return start
    for pos in range(start, len(rows)):
        if not rows[pos].header:
            return pos
    for pos in range(start - 1, -1, -1):
        if not rows[pos].header:
            return pos
    return start


class SkippyPanel(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self._skin_resolution = init_window_xml_dialog(super(SkippyPanel, self), args)
        self._xml_layout = args[0] if args else XML_NAME
        self.addon = kwargs.get("addon") or get_addon()
        self._heading = kwargs.get("heading") or ""
        self._subtitle = kwargs.get("subtitle") or ""
        self._rows = normalize_rows(kwargs.get("rows"))
        self._message = kwargs.get("message") or ""
        self._footnote = kwargs.get("footnote") or ""
        buttons = [str(b) for b in (kwargs.get("buttons") or ())][:3]
        self._buttons = buttons or [get_localized(self.addon, 40001, "Close")]
        self._preselect = kwargs.get("preselect") or 0
        self._focus_button = kwargs.get("focus_button") or 0
        self.outcome = (RESULT_CANCEL, -1)
        self._closing = False
        self.opened = False

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

    def _set_label(self, cid, text):
        ctrl = self._ctrl(cid)
        if ctrl is not None:
            try:
                ctrl.setLabel(text)
            except Exception:
                pass

    def onInit(self):
        self.opened = True
        asked = getattr(self, "_skin_resolution", None)
        locked = reconcile_window_xml_skin_resolution(
            self, asked, control_ids=probe_control_ids_for_xml(self._xml_layout)
        )
        if locked != asked:
            self._skin_resolution = locked
        self._set_label(ID_TITLE, self._heading)
        self._set_label(ID_SUBTITLE, self._subtitle)
        self._set_label(ID_FOOTNOTE, self._footnote)
        has_rows = bool(self._rows)
        for n, cid in enumerate(FOOTER_IDS):
            if n < len(self._buttons):
                self._set_label(cid, self._buttons[n])
            self._show(cid, n < len(self._buttons))
        self._show(ID_SUBTITLE, bool(self._subtitle))
        self._show(ID_FOOTNOTE, bool(self._footnote))
        self._show(ID_LIST, has_rows)
        self._show(ID_MESSAGE, not has_rows)
        if has_rows:
            self._fill_list()
        else:
            self._fill_message()
        layout = self._layout()
        self._show(ID_SCROLL, has_rows and layout["scrolls"])
        self._link_focus()
        self._focus_initial()

    def _layout(self):
        layout = panel_layout(
            len(self._rows),
            bool(self._subtitle),
            message_line_count(self._message),
            bool(self._footnote),
            len(self._buttons),
        )
        self._place(ID_PANEL, PANEL_X, layout["panel_y"], PANEL_W, layout["panel_h"])
        self._place(ID_BACKDROP, 0, 0, PANEL_W, layout["panel_h"])
        if self._rows:
            self._place(ID_LIST, INNER_X, layout["list_top"], INNER_W, layout["body_h"])
            self._place(ID_SCROLL, PANEL_W - 14, layout["list_top"], 6, layout["body_h"])
        else:
            self._place(ID_MESSAGE, INNER_X, layout["list_top"], INNER_W, layout["body_h"])
        if self._footnote:
            self._place(ID_FOOTNOTE, INNER_X, layout["footnote_top"], INNER_W, FOOTNOTE_H)
        for n in range(len(self._buttons)):
            self._place(
                FOOTER_IDS[n],
                layout["button_xs"][n],
                layout["footer_top"],
                layout["button_ws"][n],
                FOOTER_H,
            )
        return layout

    def _fill_list(self):
        lst = self._ctrl(ID_LIST)
        if lst is None:
            return
        try:
            lst.reset()
            for row in self._rows:
                item = xbmcgui.ListItem(row.label, row.label2)
                if row.header:
                    item.setProperty("header", "true")
                lst.addItem(item)
            lst.selectItem(first_selectable(self._rows, self._preselect))
        except Exception as exc:
            log("⚠ Skippy panel list failed: %s" % exc)

    def _fill_message(self):
        ctrl = self._ctrl(ID_MESSAGE)
        if ctrl is not None:
            try:
                ctrl.setText(self._message)
            except Exception:
                pass

    def _link_focus(self):
        """Up and down between the list and the buttons, left and right between the buttons."""
        ids = list(FOOTER_IDS[: len(self._buttons)])
        has_rows = bool(self._rows)

        def link(cid, up=None, down=None, left=None, right=None):
            ctrl = self._ctrl(cid)
            if ctrl is None:
                return
            for method, target in (
                ("controlUp", up),
                ("controlDown", down),
                ("controlLeft", left),
                ("controlRight", right),
            ):
                other = self._ctrl(target) if target else None
                if other is None:
                    continue
                try:
                    getattr(ctrl, method)(other)
                except Exception:
                    pass

        for n, cid in enumerate(ids):
            link(
                cid,
                up=ID_LIST if has_rows else cid,
                down=cid,
                left=ids[n - 1] if n > 0 else cid,
                right=ids[n + 1] if n + 1 < len(ids) else cid,
            )
        if has_rows:
            link(ID_LIST, up=ID_LIST, down=ids[0], left=ID_LIST, right=ID_LIST)

    def _focus_initial(self):
        try:
            if self._rows:
                self.setFocusId(ID_LIST)
            else:
                n = max(0, min(int(self._focus_button), len(self._buttons) - 1))
                self.setFocusId(FOOTER_IDS[n])
        except Exception:
            pass

    def _finish(self, kind, index):
        if self._closing:
            return
        self._closing = True
        self.outcome = (kind, index)
        try:
            self.close()
        except Exception:
            pass

    def _selected_row(self):
        lst = self._ctrl(ID_LIST)
        if lst is None:
            return -1
        try:
            return int(lst.getSelectedPosition())
        except Exception:
            return -1

    def onClick(self, controlId):
        try:
            cid = controlId.getId() if hasattr(controlId, "getId") else int(controlId)
        except Exception:
            return
        if cid == ID_LIST:
            pos = self._selected_row()
            if 0 <= pos < len(self._rows) and not self._rows[pos].header:
                self._finish(RESULT_ROW, pos)
        elif cid in FOOTER_IDS[: len(self._buttons)]:
            self._finish(RESULT_BUTTON, FOOTER_IDS.index(cid))

    def onAction(self, action):
        aid = action.getId()
        if aid in _CANCEL_ACTIONS:
            self._finish(RESULT_CANCEL, -1)
            return
        if aid in (_MOVE_UP, _MOVE_DOWN, _PAGE_UP, _PAGE_DOWN) and any(
            row.header for row in self._rows
        ):
            try:
                if self.getFocusId() != ID_LIST:
                    return
            except Exception:
                return
            pos = self._selected_row()
            if 0 <= pos < len(self._rows) and self._rows[pos].header:
                direction = 1 if aid in (_MOVE_DOWN, _PAGE_DOWN) else -1
                target = next_selectable(self._rows, pos, direction)
                lst = self._ctrl(ID_LIST)
                if lst is not None and target != pos:
                    try:
                        lst.selectItem(target)
                    except Exception:
                        pass


def show_panel(
    heading,
    rows=None,
    message="",
    subtitle="",
    footnote="",
    buttons=(),
    preselect=0,
    focus_button=0,
):
    """Open the panel. Returns ``("row", index)``, ``("button", index)`` or ``("cancel", -1)``."""
    addon = get_addon()
    if not addon:
        raise RuntimeError("no add-on")
    dialog = SkippyPanel(
        XML_NAME,
        addon.getAddonInfo("path"),
        "default",
        addon=addon,
        heading=heading,
        rows=rows,
        message=message,
        subtitle=subtitle,
        footnote=footnote,
        buttons=buttons,
        preselect=preselect,
        focus_button=focus_button,
    )
    dialog.doModal()
    opened = bool(getattr(dialog, "opened", False))
    outcome = tuple(getattr(dialog, "outcome", (RESULT_CANCEL, -1)))
    del dialog
    if not opened:
        # Kodi could not load the skin file: doModal returns at once and nothing was shown.
        raise RuntimeError("the panel window did not open")
    return outcome


def _label(addon, string_id, default):
    return get_localized(addon, string_id, default)


def show_panel_list_pick(heading, options, subtitle="", preselect=0, cancel_label=None) -> int:
    """Pick one row. Returns its index, or -1 when the user closes the window."""
    addon = get_addon()
    rows = normalize_rows(options)
    cancel = cancel_label or _label(addon, 35019, "Cancel")
    try:
        kind, index = show_panel(
            heading, rows=rows, subtitle=subtitle, buttons=[cancel], preselect=preselect
        )
        return int(index) if kind == RESULT_ROW else -1
    except Exception as exc:
        log("⚠ Skippy panel list failed (%s) — using the editor list" % exc)
    texts = [row_text(row) for row in rows]
    try:
        from skippy_editor_modal_skin import show_editor_list_pick

        return show_editor_list_pick(
            heading, texts, subtitle=subtitle, preselect=preselect, cancel_label=cancel
        )
    except Exception as exc:
        log("⚠ Editor list failed (%s) — using the stock select" % exc)
    try:
        return int(xbmcgui.Dialog().select(heading, texts))
    except Exception:
        return -1


def show_panel_rows(heading, rows, close_label=None, footnote="") -> None:
    """Show rows to read (name at the left, value at the right) with a Close button."""
    addon = get_addon()
    rows = normalize_rows(rows)
    close = close_label or _label(addon, 40001, "Close")
    try:
        show_panel(heading, rows=rows, footnote=footnote, buttons=[close])
        return
    except Exception as exc:
        log("⚠ Skippy panel rows failed (%s) — using the editor message" % exc)
    body = "\n".join(
        row_text(row) if not row.header else "\n%s" % row.label for row in rows
    )
    if footnote:
        body = "%s\n\n%s" % (body, footnote)
    show_panel_message(heading, body, close, _panel=False)


def show_panel_message(heading, message, ok_label=None, _panel=True) -> None:
    """A message with one button."""
    addon = get_addon()
    ok = ok_label or _label(addon, 40001, "Close")
    if _panel:
        try:
            show_panel(heading, message=message, buttons=[ok])
            return
        except Exception as exc:
            log("⚠ Skippy panel message failed (%s) — using the editor message" % exc)
    try:
        from skippy_editor_modal_skin import show_editor_ok

        show_editor_ok(heading, message, ok)
        return
    except Exception as exc:
        log("⚠ Editor message failed (%s) — using the stock dialog" % exc)
    try:
        xbmcgui.Dialog().ok(heading, message)
    except Exception:
        pass


def show_panel_yesno(heading, message, yes_label, no_label) -> bool:
    """A question with two buttons; True when the first is chosen."""
    try:
        kind, index = show_panel(heading, message=message, buttons=[yes_label, no_label])
        return kind == RESULT_BUTTON and index == 0
    except Exception as exc:
        log("⚠ Skippy panel question failed (%s) — using the editor question" % exc)
    try:
        from skippy_editor_modal_skin import sidecar_overwrite_yesno_show

        return bool(sidecar_overwrite_yesno_show(heading, message, yes_label, no_label))
    except Exception as exc:
        log("⚠ Editor question failed (%s) — using the stock yes/no" % exc)
    try:
        return bool(
            xbmcgui.Dialog().yesno(heading, message, nolabel=no_label, yeslabel=yes_label)
        )
    except Exception:
        return False
