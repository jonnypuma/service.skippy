# -*- coding: utf-8 -*-
"""Editor-styled ``xbmcgui.WindowDialog`` helpers (upload modals, yes/no, list pick).

These dialogs use **1280×720** coordinates via ``get_modal_dialog_layout()`` — see the
module docstring in ``addon_skin_resolution.py`` (WindowDialog vs WindowXML). Do not
copy coords from ``1080i/*.xml``; they will spill off-screen.
"""
from __future__ import annotations

import os

import xbmc
import xbmcgui
import xbmcvfs

from addon_skin_resolution import get_modal_dialog_layout, get_modal_metrics
from settings_utils import get_addon


def _modal_full_panel_height(lay, computed=None):
    m = get_modal_metrics(lay)
    max_h = min(
        lay.panel_max_h,
        lay.canvas_h - lay.panel_y - m.panel_bottom_pad,
    )
    if computed is None:
        return max_h
    return min(computed, max_h)

# Match SegmentEditorDialog.xml bottom button row darkening (white.png + colordiffuse).
EDITOR_STRIPE_DIFFUSE = "E0000000"
EDITOR_PANEL_DIFFUSE = "F0222222"
EDITOR_DIM_OVERLAY = "D0000000"

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
    (editor button-row style). Always 1280×720 — Kodi upscales ``WindowDialog`` to the screen.
    """

    def __init__(self, heading, message, yes_label="Yes", cancel_label="Cancel"):
        super().__init__()
        self.result = False
        tex = addon_skin_media("white.png")
        tex_focus = addon_skin_media("button_focus.png")
        lay = get_modal_dialog_layout()
        m = get_modal_metrics(lay)
        mw, mh = lay.canvas_w, lay.canvas_h
        try:
            bg = xbmcgui.ControlImage(0, 0, mw, mh, tex)
            bg.setColorDiffuse(EDITOR_DIM_OVERLAY)
            self.addControl(bg)
        except Exception:
            pass
        p_x, p_y = lay.panel_x, lay.panel_y
        p_w = lay.panel_w
        p_h = _modal_full_panel_height(lay)
        panel = xbmcgui.ControlImage(p_x, p_y, p_w, p_h, tex)
        panel.setColorDiffuse(EDITOR_PANEL_DIFFUSE)
        self.addControl(panel)
        inner_x = p_x + m.inner_margin
        inner_w = p_w - m.inner_gutter
        head_stripe_h = m.head_stripe_h
        head_stripe_y = p_y
        try:
            hs = xbmcgui.ControlImage(
                p_x, head_stripe_y, p_w, head_stripe_h, tex
            )
            hs.setColorDiffuse(EDITOR_STRIPE_DIFFUSE)
            self.addControl(hs)
        except Exception:
            head_stripe_h = m.head_stripe_h_fb
        self.addControl(
            xbmcgui.ControlLabel(
                inner_x + m.label_pad,
                head_stripe_y + m.label_pad,
                inner_w - m.label_inset,
                m.title_h,
                heading or "",
                "font16",
                "FFFFFFFF",
            )
        )
        btn_w, btn_h = m.btn_w_wide, m.btn_h
        btn_y = p_y + p_h - btn_h - m.btn_bottom_pad
        bottom_stripe_h = btn_h + m.stripe_pad
        bottom_stripe_y = p_y + p_h - bottom_stripe_h
        try:
            bs = xbmcgui.ControlImage(
                p_x, bottom_stripe_y, p_w, bottom_stripe_h, tex
            )
            bs.setColorDiffuse(EDITOR_STRIPE_DIFFUSE)
            self.addControl(bs)
        except Exception:
            pass
        tb_top = head_stripe_y + head_stripe_h + m.section_gap
        tb_h = max(m.body_min_h, bottom_stripe_y - m.tight_gap - tb_top)
        self._body = xbmcgui.ControlTextBox(
            inner_x, tb_top, inner_w, tb_h, "font13", "FFE8E8E8"
        )
        self.addControl(self._body)
        self._body.setText(message or "")
        self._body_scroll_pos = 0
        ylbl = (yes_label or "Yes").strip() or "Yes"
        clbl = (cancel_label or "Cancel").strip() or "Cancel"
        btn_gap = m.btn_gap
        sw = m.scroll_btn_w
        sg = m.scroll_pair_gap
        g0 = m.scroll_action_gap
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
        lay = get_modal_dialog_layout()
        m = get_modal_metrics(lay)
        mw, mh = lay.canvas_w, lay.canvas_h
        try:
            bg = xbmcgui.ControlImage(0, 0, mw, mh, tex)
            bg.setColorDiffuse(EDITOR_DIM_OVERLAY)
            self.addControl(bg)
        except Exception:
            pass
        p_x, p_y = lay.panel_x, lay.panel_y
        p_w = lay.panel_w
        p_h = _modal_full_panel_height(lay)
        panel = xbmcgui.ControlImage(p_x, p_y, p_w, p_h, tex)
        panel.setColorDiffuse(EDITOR_PANEL_DIFFUSE)
        self.addControl(panel)
        inner_x = p_x + m.inner_margin
        inner_w = p_w - m.inner_gutter
        head_stripe_h = m.head_stripe_h
        head_stripe_y = p_y
        try:
            hs = xbmcgui.ControlImage(
                p_x, head_stripe_y, p_w, head_stripe_h, tex
            )
            hs.setColorDiffuse(EDITOR_STRIPE_DIFFUSE)
            self.addControl(hs)
        except Exception:
            head_stripe_h = m.head_stripe_h_fb
        self.addControl(
            xbmcgui.ControlLabel(
                inner_x + m.label_pad,
                head_stripe_y + m.label_pad,
                inner_w - m.label_inset,
                m.title_h,
                heading or "",
                "font16",
                "FFFFFFFF",
            )
        )
        btn_w, btn_h = m.btn_w_ok, m.btn_h
        btn_y = p_y + p_h - btn_h - m.btn_bottom_pad
        bottom_stripe_h = btn_h + m.stripe_pad
        bottom_stripe_y = p_y + p_h - bottom_stripe_h
        try:
            bs = xbmcgui.ControlImage(
                p_x, bottom_stripe_y, p_w, bottom_stripe_h, tex
            )
            bs.setColorDiffuse(EDITOR_STRIPE_DIFFUSE)
            self.addControl(bs)
        except Exception:
            pass
        tb_top = head_stripe_y + head_stripe_h + m.section_gap
        tb_h = max(m.body_min_h, bottom_stripe_y - m.tight_gap - tb_top)
        self._body = xbmcgui.ControlTextBox(
            inner_x, tb_top, inner_w, tb_h, "font13", "FFE8E8E8"
        )
        self.addControl(self._body)
        self._body.setText(message or "")
        self._body_scroll_pos = 0
        ol = (ok_label or "OK").strip() or "OK"
        sw = m.scroll_btn_w
        sg = m.scroll_pair_gap
        g0 = m.scroll_action_gap
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
        lay = get_modal_dialog_layout()
        m = get_modal_metrics(lay)
        mw, mh = lay.canvas_w, lay.canvas_h
        try:
            bg = xbmcgui.ControlImage(0, 0, mw, mh, tex)
            bg.setColorDiffuse(EDITOR_DIM_OVERLAY)
            self.addControl(bg)
        except Exception:
            pass
        p_x, p_y = lay.panel_x, lay.panel_y
        p_w = lay.panel_w
        n = len(self._options)
        opt_h = m.opt_h
        gap = m.opt_gap
        head_h = m.block_head_h
        sub_h = m.opt_h if (subtitle or "").strip() else 0
        foot_h = m.block_head_h
        p_h = (
            head_h
            + sub_h
            + m.pick_pad1
            + n * opt_h
            + max(0, n - 1) * gap
            + m.pick_pad2
            + foot_h
            + m.pick_pad3
        )
        p_h = _modal_full_panel_height(lay, p_h)
        panel = xbmcgui.ControlImage(p_x, p_y, p_w, p_h, tex)
        panel.setColorDiffuse(EDITOR_PANEL_DIFFUSE)
        self.addControl(panel)
        inner_x = p_x + m.inner_margin
        inner_w = p_w - m.inner_gutter
        head_stripe_h = m.block_head_h
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
                inner_x + m.label_pad,
                head_stripe_y + m.title_y,
                inner_w - m.label_inset,
                m.title_h,
                heading or "",
                "font16",
                "FFFFFFFF",
            )
        )
        if sub_h:
            self.addControl(
                xbmcgui.ControlLabel(
                    inner_x + m.label_pad,
                    y + m.sub_y_off,
                    inner_w - m.label_inset,
                    m.sub_label_h,
                    subtitle,
                    "font14",
                    "FFB0D4E8",
                )
            )
            y += sub_h + m.sub_y_after
        y += m.list_y_after
        btn_w = inner_w - m.pick_btn_inset
        self._option_buttons = []
        for label in self._options:
            b = segment_style_push_button(
                inner_x + m.pick_btn_side, y, btn_w, opt_h, label, tex_focus
            )
            self.addControl(b)
            self._option_buttons.append(b)
            y += opt_h + gap
        cancel_h = m.btn_h
        btn_y = p_y + p_h - cancel_h - m.btn_bottom_pad
        bottom_stripe_h = cancel_h + m.stripe_pad
        bottom_stripe_y = p_y + p_h - bottom_stripe_h
        try:
            bs = xbmcgui.ControlImage(
                p_x, bottom_stripe_y, p_w, bottom_stripe_h, tex
            )
            bs.setColorDiffuse(EDITOR_STRIPE_DIFFUSE)
            self.addControl(bs)
        except Exception:
            pass
        cw = m.btn_w_wide
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
