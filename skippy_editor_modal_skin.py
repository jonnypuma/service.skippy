# -*- coding: utf-8 -*-
"""Reusable editor-styled WindowDialog helpers (stripes, buttons) for Skippy modals."""
from __future__ import annotations

import os

import xbmc
import xbmcgui
import xbmcvfs

from settings_utils import get_addon

# Match SegmentEditorDialog.xml bottom button row darkening (white.png + colordiffuse).
EDITOR_STRIPE_DIFFUSE = "E0000000"
EDITOR_PANEL_DIFFUSE = "F0222222"
EDITOR_DIM_OVERLAY = "D0000000"

_MODAL_W = 1280
_MODAL_H = 720

_CANCEL_ACTION_IDS = (10, 92, 216)
_MOVE_LEFT = getattr(xbmcgui, "ACTION_MOVE_LEFT", 1)
_MOVE_RIGHT = getattr(xbmcgui, "ACTION_MOVE_RIGHT", 2)
_MOVE_UP = getattr(xbmcgui, "ACTION_MOVE_UP", 3)
_MOVE_DOWN = getattr(xbmcgui, "ACTION_MOVE_DOWN", 4)
_SELECT_ACTIONS = (
    getattr(xbmcgui, "ACTION_SELECT_ITEM", 7),
    11,
    13,
    100,
    101,
)
_PAGE_UP = getattr(xbmcgui, "ACTION_PAGE_UP", 5)
_PAGE_DOWN = getattr(xbmcgui, "ACTION_PAGE_DOWN", 6)
# ControlTextBox often does not take focus in WindowDialog; scroll via API while buttons are focused.
_BODY_SCROLL_LINE = 1
_BODY_SCROLL_PAGE = 8
_SCROLL_BTN_W = 44
_SCROLL_BTN_PAIR_GAP = 8
_SCROLL_TO_ACTION_GAP = 12


def addon_skin_media(filename: str) -> str:
    addon = get_addon()
    if not addon:
        return filename
    full = os.path.join(
        addon.getAddonInfo("path"),
        "resources",
        "skins",
        "default",
        "media",
        filename,
    )
    return full if xbmcvfs.exists(full) else "-"


def segment_style_push_button(x, y, w, h, label, tex_focus):
    """ControlButton matching Segment Editor list-row actions."""
    try:
        al = xbmcgui.ALIGN_CENTER
    except AttributeError:
        al = 6
    try:
        return xbmcgui.ControlButton(
            x,
            y,
            w,
            h,
            label,
            tex_focus,
            "-",
            0,
            0,
            al,
            font="font10",
            textColor="0xFFC0C0C0",
            focusedColor="0xFFFFFFFF",
            shadowColor="0xFF000000",
        )
    except (TypeError, ValueError):
        pass
    try:
        return xbmcgui.ControlButton(
            x,
            y,
            w,
            h,
            label,
            tex_focus,
            "-",
            0,
            0,
            al,
            "font10",
            "0xFFC0C0C0",
            "0xFF808080",
        )
    except (TypeError, ValueError):
        pass
    b = xbmcgui.ControlButton(x, y, w, h, label, tex_focus, "-")
    try:
        b.setLabel(
            label,
            "font10",
            "0xFFC0C0C0",
            "0xFF808080",
            "0xFF000000",
            "0xFFFFFFFF",
        )
    except Exception:
        try:
            b.setLabel(label, "font10")
        except Exception:
            pass
    return b


class EditorTallYesNoDialog(xbmcgui.WindowDialog):
    """
    Scrollable body + ▲/▼ scroll + Yes / Cancel; top and bottom dark stripes
    (editor button-row style). Layout 1280×720, top-left panel.
    """

    def __init__(self, heading, message, yes_label="Yes", cancel_label="Cancel"):
        super().__init__()
        self.result = False
        tex = addon_skin_media("white.png")
        tex_focus = addon_skin_media("button_focus.png")
        try:
            bg = xbmcgui.ControlImage(0, 0, _MODAL_W, _MODAL_H, tex)
            bg.setColorDiffuse(EDITOR_DIM_OVERLAY)
            self.addControl(bg)
        except Exception:
            pass
        p_x, p_y = 36, 28
        p_w = _MODAL_W - 72
        p_h = _MODAL_H - 56
        panel = xbmcgui.ControlImage(p_x, p_y, p_w, p_h, tex)
        panel.setColorDiffuse(EDITOR_PANEL_DIFFUSE)
        self.addControl(panel)
        inner_x = p_x + 20
        inner_w = p_w - 40
        head_stripe_h = 48
        head_stripe_y = p_y
        try:
            hs = xbmcgui.ControlImage(
                p_x, head_stripe_y, p_w, head_stripe_h, tex
            )
            hs.setColorDiffuse(EDITOR_STRIPE_DIFFUSE)
            self.addControl(hs)
        except Exception:
            head_stripe_h = 40
        self.addControl(
            xbmcgui.ControlLabel(
                inner_x + 8,
                head_stripe_y + 8,
                inner_w - 16,
                32,
                heading or "",
                "font16",
                "FFFFFFFF",
            )
        )
        btn_w, btn_h = 118, 30
        btn_y = p_y + p_h - btn_h - 14
        bottom_stripe_h = btn_h + 20
        bottom_stripe_y = p_y + p_h - bottom_stripe_h
        try:
            bs = xbmcgui.ControlImage(
                p_x, bottom_stripe_y, p_w, bottom_stripe_h, tex
            )
            bs.setColorDiffuse(EDITOR_STRIPE_DIFFUSE)
            self.addControl(bs)
        except Exception:
            pass
        tb_top = head_stripe_y + head_stripe_h + 10
        tb_h = max(120, bottom_stripe_y - 8 - tb_top)
        self._body = xbmcgui.ControlTextBox(
            inner_x, tb_top, inner_w, tb_h, "font13", "FFE8E8E8"
        )
        self.addControl(self._body)
        self._body.setText(message or "")
        self._body_scroll_pos = 0
        ylbl = (yes_label or "Yes").strip() or "Yes"
        clbl = (cancel_label or "Cancel").strip() or "Cancel"
        btn_gap = 14
        sw = _SCROLL_BTN_W
        sg = _SCROLL_BTN_PAIR_GAP
        g0 = _SCROLL_TO_ACTION_GAP
        total_bw = sw * 2 + sg + g0 + btn_w * 2 + btn_gap
        row_left = inner_x + max(0, (inner_w - total_bw) // 2)
        sx0 = row_left
        sx1 = sx0 + sw + sg
        yes_x = sx1 + sw + g0
        self._btn_scroll_up = segment_style_push_button(
            sx0, btn_y, sw, btn_h, "\u25b2", tex_focus
        )
        self._btn_scroll_down = segment_style_push_button(
            sx1, btn_y, sw, btn_h, "\u25bc", tex_focus
        )
        self._btn_yes = segment_style_push_button(
            yes_x, btn_y, btn_w, btn_h, ylbl, tex_focus
        )
        self._btn_cancel = segment_style_push_button(
            yes_x + btn_w + btn_gap, btn_y, btn_w, btn_h, clbl, tex_focus
        )
        self.addControl(self._btn_scroll_up)
        self.addControl(self._btn_scroll_down)
        self.addControl(self._btn_yes)
        self.addControl(self._btn_cancel)
        self._scroll_up_id = self._btn_scroll_up.getId()
        self._scroll_down_id = self._btn_scroll_down.getId()
        self._yes_id = self._btn_yes.getId()
        self._cancel_id = self._btn_cancel.getId()
        self._body_id = self._body.getId()
        self._choice_yes = True
        try:
            su = self._btn_scroll_up
            sd = self._btn_scroll_down
            by = self._btn_yes
            bc = self._btn_cancel
            su.setNavigation(su, su, su, sd)
            sd.setNavigation(sd, sd, su, by)
            by.setNavigation(by, by, sd, bc)
            bc.setNavigation(bc, bc, by, bc)
        except Exception:
            pass

    def _scroll_body(self, delta_lines):
        self._body_scroll_pos = max(0, self._body_scroll_pos + int(delta_lines))
        try:
            self._body.scroll(self._body_scroll_pos)
        except Exception:
            pass

    @staticmethod
    def _scroll_click_step():
        return _BODY_SCROLL_PAGE

    def onInit(self):
        try:
            self.setFocus(self._btn_yes)
            self._choice_yes = True
        except Exception:
            pass

    def onClick(self, controlId):
        try:
            cid = (
                controlId.getId()
                if hasattr(controlId, "getId")
                else int(controlId)
            )
            step = self._scroll_click_step()
            if cid == self._scroll_up_id:
                self._scroll_body(-step)
            elif cid == self._scroll_down_id:
                self._scroll_body(step)
            elif cid == self._yes_id:
                self.result = True
                self.close()
            elif cid == self._cancel_id:
                self.result = False
                self.close()
        except Exception:
            pass

    def onControl(self, control):
        try:
            cid = control.getId()
            if cid == self._yes_id:
                self.result = True
                self.close()
            elif cid == self._cancel_id:
                self.result = False
                self.close()
        except Exception:
            pass

    def onAction(self, action):
        try:
            aid = action.getId()
        except Exception:
            return
        if aid in _CANCEL_ACTION_IDS:
            self.result = False
            self.close()
            return
        try:
            _fid = self.getFocusId()
        except Exception:
            _fid = None
        scroll_ids = (
            self._scroll_up_id,
            self._scroll_down_id,
            self._yes_id,
            self._cancel_id,
        )
        if aid in (_PAGE_UP, _PAGE_DOWN):
            if _fid in scroll_ids:
                step = -_BODY_SCROLL_PAGE if aid == _PAGE_UP else _BODY_SCROLL_PAGE
                self._scroll_body(step)
            return
        if aid == _MOVE_UP:
            if _fid in scroll_ids:
                self._scroll_body(-_BODY_SCROLL_LINE)
            return
        if aid == _MOVE_DOWN:
            if _fid in scroll_ids:
                self._scroll_body(_BODY_SCROLL_LINE)
            return
        if aid in _SELECT_ACTIONS:
            fid = _fid
            if fid == self._body_id:
                return
            step = self._scroll_click_step()
            if fid == self._scroll_up_id:
                self._scroll_body(-step)
                return
            if fid == self._scroll_down_id:
                self._scroll_body(step)
                return
            if fid == self._yes_id:
                self.result = True
                self.close()
            elif fid == self._cancel_id:
                self.result = False
                self.close()
            else:
                self.result = bool(self._choice_yes)
                self.close()


class EditorOkScrollDialog(xbmcgui.WindowDialog):
    """Heading + scrollable body + ▲/▼ + OK; top/bottom stripes."""

    def __init__(self, heading, message, ok_label="OK"):
        super().__init__()
        tex = addon_skin_media("white.png")
        tex_focus = addon_skin_media("button_focus.png")
        try:
            bg = xbmcgui.ControlImage(0, 0, _MODAL_W, _MODAL_H, tex)
            bg.setColorDiffuse(EDITOR_DIM_OVERLAY)
            self.addControl(bg)
        except Exception:
            pass
        p_x, p_y = 36, 28
        p_w = _MODAL_W - 72
        p_h = _MODAL_H - 56
        panel = xbmcgui.ControlImage(p_x, p_y, p_w, p_h, tex)
        panel.setColorDiffuse(EDITOR_PANEL_DIFFUSE)
        self.addControl(panel)
        inner_x = p_x + 20
        inner_w = p_w - 40
        head_stripe_h = 48
        head_stripe_y = p_y
        try:
            hs = xbmcgui.ControlImage(
                p_x, head_stripe_y, p_w, head_stripe_h, tex
            )
            hs.setColorDiffuse(EDITOR_STRIPE_DIFFUSE)
            self.addControl(hs)
        except Exception:
            head_stripe_h = 40
        self.addControl(
            xbmcgui.ControlLabel(
                inner_x + 8,
                head_stripe_y + 8,
                inner_w - 16,
                32,
                heading or "",
                "font16",
                "FFFFFFFF",
            )
        )
        btn_w, btn_h = 100, 30
        btn_y = p_y + p_h - btn_h - 14
        bottom_stripe_h = btn_h + 20
        bottom_stripe_y = p_y + p_h - bottom_stripe_h
        try:
            bs = xbmcgui.ControlImage(
                p_x, bottom_stripe_y, p_w, bottom_stripe_h, tex
            )
            bs.setColorDiffuse(EDITOR_STRIPE_DIFFUSE)
            self.addControl(bs)
        except Exception:
            pass
        tb_top = head_stripe_y + head_stripe_h + 10
        tb_h = max(120, bottom_stripe_y - 8 - tb_top)
        self._body = xbmcgui.ControlTextBox(
            inner_x, tb_top, inner_w, tb_h, "font13", "FFE8E8E8"
        )
        self.addControl(self._body)
        self._body.setText(message or "")
        self._body_scroll_pos = 0
        ol = (ok_label or "OK").strip() or "OK"
        sw = _SCROLL_BTN_W
        sg = _SCROLL_BTN_PAIR_GAP
        g0 = _SCROLL_TO_ACTION_GAP
        total_bw = sw * 2 + sg + g0 + btn_w
        row_left = inner_x + max(0, (inner_w - total_bw) // 2)
        sx0 = row_left
        sx1 = sx0 + sw + sg
        ok_x = sx1 + sw + g0
        self._btn_scroll_up = segment_style_push_button(
            sx0, btn_y, sw, btn_h, "\u25b2", tex_focus
        )
        self._btn_scroll_down = segment_style_push_button(
            sx1, btn_y, sw, btn_h, "\u25bc", tex_focus
        )
        self._btn_ok = segment_style_push_button(
            ok_x, btn_y, btn_w, btn_h, ol, tex_focus
        )
        self.addControl(self._btn_scroll_up)
        self.addControl(self._btn_scroll_down)
        self.addControl(self._btn_ok)
        self._scroll_up_id = self._btn_scroll_up.getId()
        self._scroll_down_id = self._btn_scroll_down.getId()
        self._ok_id = self._btn_ok.getId()
        self._body_id = self._body.getId()
        try:
            su = self._btn_scroll_up
            sd = self._btn_scroll_down
            ok = self._btn_ok
            su.setNavigation(su, su, su, sd)
            sd.setNavigation(sd, sd, su, ok)
            ok.setNavigation(ok, ok, sd, ok)
        except Exception:
            pass

    def _scroll_body(self, delta_lines):
        self._body_scroll_pos = max(0, self._body_scroll_pos + int(delta_lines))
        try:
            self._body.scroll(self._body_scroll_pos)
        except Exception:
            pass

    @staticmethod
    def _scroll_click_step():
        return _BODY_SCROLL_PAGE

    def onInit(self):
        try:
            self.setFocus(self._btn_ok)
        except Exception:
            pass

    def onClick(self, controlId):
        try:
            cid = (
                controlId.getId()
                if hasattr(controlId, "getId")
                else int(controlId)
            )
            step = self._scroll_click_step()
            if cid == self._scroll_up_id:
                self._scroll_body(-step)
            elif cid == self._scroll_down_id:
                self._scroll_body(step)
            elif cid == self._ok_id:
                self.close()
        except Exception:
            pass

    def onControl(self, control):
        try:
            if control.getId() == self._ok_id:
                self.close()
        except Exception:
            pass

    def onAction(self, action):
        try:
            aid = action.getId()
        except Exception:
            return
        if aid in _CANCEL_ACTION_IDS:
            self.close()
            return
        try:
            _fid = self.getFocusId()
        except Exception:
            _fid = None
        scroll_ids = (self._scroll_up_id, self._scroll_down_id, self._ok_id)
        if aid in (_PAGE_UP, _PAGE_DOWN):
            if _fid in scroll_ids:
                step = -_BODY_SCROLL_PAGE if aid == _PAGE_UP else _BODY_SCROLL_PAGE
                self._scroll_body(step)
            return
        if aid == _MOVE_UP:
            if _fid in scroll_ids:
                self._scroll_body(-_BODY_SCROLL_LINE)
            return
        if aid == _MOVE_DOWN:
            if _fid in scroll_ids:
                self._scroll_body(_BODY_SCROLL_LINE)
            return
        if aid in _SELECT_ACTIONS:
            fid = None
            try:
                fid = self.getFocusId()
            except Exception:
                pass
            if fid == self._body_id:
                return
            step = self._scroll_click_step()
            if fid == self._scroll_up_id:
                self._scroll_body(-step)
                return
            if fid == self._scroll_down_id:
                self._scroll_body(step)
                return
            self.close()


class EditorListPickDialog(xbmcgui.WindowDialog):
    """Vertical option buttons + Cancel on striped footer; ``selected_index`` or -1."""

    def __init__(
        self,
        heading,
        options,
        subtitle="",
        preselect=0,
        cancel_label="Cancel",
    ):
        super().__init__()
        self.selected_index = -1
        self._options = list(options or [])
        tex = addon_skin_media("white.png")
        tex_focus = addon_skin_media("button_focus.png")
        try:
            bg = xbmcgui.ControlImage(0, 0, _MODAL_W, _MODAL_H, tex)
            bg.setColorDiffuse(EDITOR_DIM_OVERLAY)
            self.addControl(bg)
        except Exception:
            pass
        p_x, p_y = 36, 28
        p_w = _MODAL_W - 72
        n = len(self._options)
        opt_h = 36
        gap = 10
        head_h = 52
        sub_h = 36 if (subtitle or "").strip() else 0
        foot_h = 52
        p_h = (
            head_h
            + sub_h
            + 20
            + n * opt_h
            + max(0, n - 1) * gap
            + 24
            + foot_h
            + 36
        )
        p_h = min(p_h, _MODAL_H - 56)
        panel = xbmcgui.ControlImage(p_x, p_y, p_w, p_h, tex)
        panel.setColorDiffuse(EDITOR_PANEL_DIFFUSE)
        self.addControl(panel)
        inner_x = p_x + 20
        inner_w = p_w - 40
        head_stripe_h = 52
        head_stripe_y = p_y
        try:
            hs = xbmcgui.ControlImage(
                p_x, head_stripe_y, p_w, head_stripe_h, tex
            )
            hs.setColorDiffuse(EDITOR_STRIPE_DIFFUSE)
            self.addControl(hs)
        except Exception:
            pass
        y = head_stripe_y + head_stripe_h
        self.addControl(
            xbmcgui.ControlLabel(
                inner_x + 8,
                head_stripe_y + 10,
                inner_w - 16,
                32,
                heading or "",
                "font16",
                "FFFFFFFF",
            )
        )
        if sub_h:
            self.addControl(
                xbmcgui.ControlLabel(
                    inner_x + 8,
                    y + 4,
                    inner_w - 16,
                    28,
                    subtitle,
                    "font14",
                    "FFB0D4E8",
                )
            )
            y += sub_h + 8
        y += 12
        btn_w = inner_w - 24
        self._option_buttons = []
        for label in self._options:
            b = segment_style_push_button(
                inner_x + 12, y, btn_w, opt_h, label, tex_focus
            )
            self.addControl(b)
            self._option_buttons.append(b)
            y += opt_h + gap
        cancel_h = 30
        btn_y = p_y + p_h - cancel_h - 14
        bottom_stripe_h = cancel_h + 20
        bottom_stripe_y = p_y + p_h - bottom_stripe_h
        try:
            bs = xbmcgui.ControlImage(
                p_x, bottom_stripe_y, p_w, bottom_stripe_h, tex
            )
            bs.setColorDiffuse(EDITOR_STRIPE_DIFFUSE)
            self.addControl(bs)
        except Exception:
            pass
        cw = 118
        cl = (cancel_label or "Cancel").strip() or "Cancel"
        self._btn_cancel = segment_style_push_button(
            inner_x + max(0, (inner_w - cw) // 2),
            btn_y,
            cw,
            cancel_h,
            cl,
            tex_focus,
        )
        self.addControl(self._btn_cancel)
        self._cancel_id = self._btn_cancel.getId()
        self._preselect = max(0, min(preselect, len(self._option_buttons) - 1))
        try:
            for i, b in enumerate(self._option_buttons):
                up = self._option_buttons[i - 1] if i > 0 else b
                down = (
                    self._option_buttons[i + 1]
                    if i < len(self._option_buttons) - 1
                    else self._btn_cancel
                )
                b.setNavigation(up, down, b, b)
            if self._option_buttons:
                last = self._option_buttons[-1]
                self._btn_cancel.setNavigation(
                    last, self._btn_cancel, self._btn_cancel, self._btn_cancel
                )
        except Exception:
            pass

    def onInit(self):
        try:
            if self._option_buttons and 0 <= self._preselect < len(self._option_buttons):
                self.setFocus(self._option_buttons[self._preselect])
            else:
                self.setFocus(self._btn_cancel)
        except Exception:
            pass

    def onClick(self, controlId):
        try:
            cid = (
                controlId.getId()
                if hasattr(controlId, "getId")
                else int(controlId)
            )
            if cid == self._cancel_id:
                self.selected_index = -1
                self.close()
                return
            for i, b in enumerate(self._option_buttons):
                if cid == b.getId():
                    self.selected_index = i
                    self.close()
                    return
        except Exception:
            pass

    def onControl(self, control):
        try:
            cid = control.getId()
            if cid == self._cancel_id:
                self.selected_index = -1
                self.close()
                return
            for i, b in enumerate(self._option_buttons):
                if cid == b.getId():
                    self.selected_index = i
                    self.close()
                    return
        except Exception:
            pass

    def onAction(self, action):
        try:
            aid = action.getId()
        except Exception:
            return
        if aid in _CANCEL_ACTION_IDS:
            self.selected_index = -1
            self.close()
            return
        if aid in _SELECT_ACTIONS:
            fid = None
            try:
                fid = self.getFocusId()
            except Exception:
                pass
            if fid == self._cancel_id:
                self.selected_index = -1
            else:
                matched = False
                for i, b in enumerate(self._option_buttons):
                    if fid == b.getId():
                        self.selected_index = i
                        matched = True
                        break
                if not matched and self._option_buttons:
                    self.selected_index = self._preselect
            self.close()


def show_editor_ok(heading: str, message: str, ok_label: str | None = None) -> None:
    lbl = (ok_label or "OK").strip() or "OK"
    dlg = EditorOkScrollDialog(heading, message or "", ok_label=lbl)
    dlg.show()
    xbmc.sleep(50)
    try:
        dlg.setFocus(dlg._btn_ok)
    except Exception:
        pass
    dlg.doModal()
    try:
        del dlg
    except Exception:
        pass


def show_editor_list_pick(
    heading: str,
    options: list,
    subtitle: str = "",
    preselect: int = 0,
    cancel_label: str | None = None,
) -> int:
    cl = cancel_label
    if cl is None:
        try:
            addon = get_addon()
            if addon:
                cl = addon.getLocalizedString(35019)
        except Exception:
            cl = None
        if not (cl or "").strip():
            cl = "Cancel"
    dlg = EditorListPickDialog(
        heading,
        options,
        subtitle=subtitle or "",
        preselect=preselect,
        cancel_label=cl,
    )
    dlg.show()
    xbmc.sleep(50)
    try:
        if dlg._option_buttons and 0 <= dlg._preselect < len(dlg._option_buttons):
            dlg.setFocus(dlg._option_buttons[dlg._preselect])
        else:
            dlg.setFocus(dlg._btn_cancel)
    except Exception:
        pass
    dlg.doModal()
    out = int(getattr(dlg, "selected_index", -1))
    try:
        del dlg
    except Exception:
        pass
    return out


def sidecar_overwrite_yesno_show(
    heading: str,
    message: str,
    yes_label: str,
    cancel_label: str,
) -> bool:
    dlg = EditorTallYesNoDialog(
        heading,
        message or "",
        yes_label=yes_label,
        cancel_label=cancel_label,
    )
    dlg.show()
    xbmc.sleep(50)
    try:
        dlg.setFocus(dlg._btn_yes)
    except Exception:
        pass
    dlg.doModal()
    out = bool(dlg.result)
    try:
        del dlg
    except Exception:
        pass
    return out
