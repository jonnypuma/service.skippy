# -*- coding: utf-8 -*-
"""Programmatic Skip dialog layout (``WindowDialog``, 1280×720 canvas)."""

from __future__ import annotations

import xbmcgui

from settings_utils import addon_get_bool, addon_get_setting_text
from skippy_editor_modal_skin import addon_skin_media

FULL_PANEL_W = 430
FULL_PANEL_H = 100
MINIMAL_PANEL_W = 120
MINIMAL_PANEL_H = 46

FULL_LAYOUT_POS = {
    "BottomRight": (895, 620),
    "BottomLeft": (10, 620),
    "TopRight": (895, 0),
    "TopLeft": (10, 0),
}
MINIMAL_LAYOUT_POS = {
    "BottomRight": (1045, 674),
    "BottomLeft": (10, 674),
    "TopRight": (1045, 0),
    "TopLeft": (10, 0),
}

FULL_SKIP_PROGRESS_BAR_WIDTH = 370


def _layout_pos(minimal, layout_suffix):
    key = (layout_suffix or "BottomRight").replace(" ", "")
    table = MINIMAL_LAYOUT_POS if minimal else FULL_LAYOUT_POS
    return table.get(key, table["BottomRight"])


def _argb_to_kodi(argb):
    s = (argb or "FF6E6E6E").strip().upper()
    if len(s) == 8:
        return f"0x{s}"
    if len(s) == 6:
        return f"0xFF{s}"
    return "0xFF6E6E6E"


def _resolve_focus_texture(addon, hide_close):
    raw = (addon_get_setting_text(addon, "button_focus_style", "") or "").strip()
    if not raw:
        raw = "button_focus.png"
    if hide_close and not addon_get_bool(addon, "show_skip_button_focus_texture", True):
        return "-"
    return addon_skin_media(raw)


def _resolve_progress_textures(addon):
    mid = (addon_get_setting_text(addon, "progress_bar_style", "") or "").strip()
    if not mid:
        mid = "progress_mid.png"
    bg = addon_skin_media("progress_background.png")
    return bg, addon_skin_media(mid)


def _skip_button(x, y, w, h, label, tex_focus, text_argb):
    tc = _argb_to_kodi(text_argb)
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
            font="font16",
            textColor=tc,
            focusedColor=tc,
            shadowColor="0xFF000000",
        )
    except (TypeError, ValueError):
        pass
    b = xbmcgui.ControlButton(x, y, w, h, label, tex_focus, "-")
    try:
        b.setLabel(label, "font16", tc, tc, "0xFF000000", tc)
    except Exception:
        try:
            b.setLabel(label, "font16")
        except Exception:
            pass
    return b


def build_skip_dialog_controls(minimal, layout_suffix, addon, text_color_argb):
    """
    Build skip dialog controls on the 1280×720 canvas.

    Returns ``(controls, control_map)`` with logical ids (3012, 3080, …).
    """
    px, py = _layout_pos(minimal, layout_suffix)
    controls = []
    cmap = {}

    def reg(cid, ctrl):
        cmap[cid] = ctrl
        controls.append(ctrl)

    tex = addon_skin_media("white.png")

    if minimal:
        plate_name = (addon_get_setting_text(addon, "minimal_button_style", "") or "").strip()
        if not plate_name.endswith(".png"):
            plate_name = "minimal_rounded_gray_640.png"
        plate_tex = addon_skin_media(plate_name)
        reg(3021, xbmcgui.ControlImage(px, py, MINIMAL_PANEL_W, MINIMAL_PANEL_H, plate_tex))
        reg(
            3012,
            _skip_button(
                px,
                py,
                MINIMAL_PANEL_W,
                MINIMAL_PANEL_H,
                "Skip",
                plate_tex,
                text_color_argb,
            ),
        )
        reg(3080, None)
        return controls, cmap

    focus_tex = _resolve_focus_texture(addon, hide_close=False)
    prog_bg, prog_mid = _resolve_progress_textures(addon)
    panel_x, panel_y = px, py

    sizer = xbmcgui.ControlImage(panel_x, panel_y, FULL_PANEL_W, FULL_PANEL_H, tex)
    sizer.setColorDiffuse("00000000")
    reg(3080, sizer)
    backdrop = xbmcgui.ControlImage(panel_x, panel_y, FULL_PANEL_W, FULL_PANEL_H, tex)
    backdrop.setColorDiffuse("F0000000")
    reg(3081, backdrop)

    reg(
        "_skip_icon",
        xbmcgui.ControlImage(panel_x + 5, panel_y + 13, 20, 20, addon_skin_media("icon_skip.png")),
    )
    reg(
        "_close_icon",
        xbmcgui.ControlImage(panel_x + 280, panel_y + 13, 20, 20, addon_skin_media("icon_close.png")),
    )

    reg(
        3012,
        _skip_button(panel_x + 35, panel_y + 10, 240, 25, "Skip", focus_tex, text_color_argb),
    )
    reg(
        3015,
        _skip_button(panel_x + 30, panel_y + 10, 350, 25, "Skip", focus_tex, text_color_argb),
    )
    reg(
        3016,
        _skip_button(panel_x + 5, panel_y + 10, 350, 25, "Skip", focus_tex, text_color_argb),
    )
    reg(
        3013,
        _skip_button(panel_x + 300, panel_y + 10, 80, 25, "Close", focus_tex, text_color_argb),
    )

    tc = _argb_to_kodi(text_color_argb)
    reg(
        3011,
        xbmcgui.ControlLabel(panel_x + 5, panel_y + 41, 360, 20, "", "font11", tc[2:]),
    )
    reg(
        2,
        xbmcgui.ControlLabel(panel_x + 5, panel_y + 66, 360, 20, "", "font10", tc[2:]),
    )

    prog_x = panel_x + 5
    prog_y = panel_y + 90
    prog_w = FULL_SKIP_PROGRESS_BAR_WIDTH
    prog_h = 16
    prog_left = addon_skin_media("progress_left.png")
    prog_right = addon_skin_media("progress_right.png")
    reg(
        3014,
        xbmcgui.ControlProgress(
            prog_x,
            prog_y,
            prog_w,
            prog_h,
            prog_bg,
            prog_left,
            prog_mid,
            prog_right,
        ),
    )
    reg(3030, xbmcgui.ControlImage(prog_x, prog_y, prog_w, prog_h, prog_bg))
    reg(3031, xbmcgui.ControlImage(prog_x, prog_y, 0, prog_h, prog_mid))

    return controls, cmap
