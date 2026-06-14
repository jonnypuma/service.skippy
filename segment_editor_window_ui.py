# -*- coding: utf-8 -*-
"""Programmatic Segment Editor layout (``WindowDialog``, 1280×720 canvas)."""

from __future__ import annotations

import xbmcgui

from addon_skin_resolution import get_modal_dialog_layout
from skippy_editor_modal_skin import (
    EDITOR_DIM_OVERLAY,
    EDITOR_PANEL_DIFFUSE,
    EDITOR_STRIPE_DIFFUSE,
    addon_skin_media,
    segment_style_push_button,
)

# Logical control IDs (match legacy WindowXML skin).
CID_LIST = 5000
CID_TIME = 5001
CID_STATUS = 5008

LIST_TOP_REL = 110
LIST_HEIGHT = 290
LIST_ITEM_HEIGHT = 50
BTN_H = 30

# List-row action buttons (Y set dynamically in Python).
LIST_ROW_BTNS = (
    (5037, 425, 105, "Start@Curr"),
    (5038, 532, 91, "End@Curr"),
    (5027, 625, 95, "Snap Start"),
    (5028, 722, 97, "Snap End"),
    (5041, 821, 75, "Merge"),
    (5042, 898, 53, "Split"),
    (5043, 953, 85, "Fix Ovl"),
    (5021, 1040, 53, "Edit"),
    (5022, 1095, 55, "Del"),
)

# (id, x, y, w, label) — 720p; keep in sync with tools/repack_segment_editor_toolbar.py
TOOLBAR_BTNS = (
    (5031, 6, 450, 77, "-10m"),
    (5032, 85, 450, 73, "-5m"),
    (5033, 160, 450, 73, "-1m"),
    (5011, 235, 450, 77, "-30s"),
    (5010, 314, 450, 77, "-10s"),
    (5009, 393, 450, 73, "-5s"),
    (5019, 468, 450, 73, "-1s"),
    (5018, 543, 450, 83, "Pause"),
    (5020, 628, 450, 73, "+1s"),
    (5012, 703, 450, 73, "+5s"),
    (5013, 778, 450, 77, "+10s"),
    (5014, 857, 450, 77, "+30s"),
    (5034, 936, 450, 73, "+1m"),
    (5035, 1011, 450, 73, "+5m"),
    (5036, 1086, 450, 77, "+10m"),
    (5015, 0, 490, 128, "Set as Start"),
    (5029, 130, 490, 194, "Set to Start of File"),
    (5016, 326, 490, 120, "Set as End"),
    (5030, 448, 490, 184, "Set to End of File"),
    (5017, 634, 490, 88, "Create"),
    (5023, 724, 490, 222, "Start at End of Segment"),
    (5024, 948, 490, 222, "End at Start of Segment"),
    (5025, 2, 530, 118, "Jump To"),
    (5005, 122, 530, 268, "Add Current + User Set Time"),
    (5002, 392, 530, 238, "Manual Start + End Times"),
    (5004, 632, 530, 128, "Delete All"),
    (5040, 762, 530, 98, "Undo"),
    (5026, 862, 530, 112, "Upload"),
    (5006, 976, 530, 96, "Save"),
    (5007, 1074, 530, 94, "Exit"),
)


def panel_abs(lay, rx, ry):
    return lay.panel_x + rx, lay.panel_y + ry


def build_segment_editor_controls(enable_overlay=True):
    """
    Build Segment Editor controls for ``WindowDialog``.

    Returns ``(controls_list, control_map, layout_info)`` where ``control_map`` maps
    logical IDs (5000, …) to control instances.
    """
    lay = get_modal_dialog_layout()
    tex = addon_skin_media("white.png")
    tex_focus = addon_skin_media("button_focus.png")
    banner = addon_skin_media("segment_editor_banner.png")
    controls = []
    cmap = {}

    def add(ctrl):
        controls.append(ctrl)

    def reg(cid, ctrl):
        cmap[cid] = ctrl
        add(ctrl)

    # Full-screen dim overlay
    try:
        ov = xbmcgui.ControlImage(0, 0, lay.canvas_w, lay.canvas_h, tex)
        ov.setColorDiffuse(EDITOR_DIM_OVERLAY if enable_overlay else "00000000")
        reg("_overlay", ov)
    except Exception:
        reg("_overlay", None)

    px, py, pw, ph = lay.panel_x, lay.panel_y, lay.panel_w, lay.panel_max_h
    panel = xbmcgui.ControlImage(px, py, pw, ph, tex)
    panel.setColorDiffuse(EDITOR_PANEL_DIFFUSE)
    add(panel)

    try:
        stripe = xbmcgui.ControlImage(px, py + 445, pw, 140, tex)
        stripe.setColorDiffuse(EDITOR_STRIPE_DIFFUSE)
        add(stripe)
    except Exception:
        pass

    bx, by = panel_abs(lay, 20, 20)
    try:
        add(xbmcgui.ControlImage(bx, by, 229, 40, banner))
    except Exception:
        pass

    tx, ty = panel_abs(lay, 20, 70)
    reg(
        CID_TIME,
        xbmcgui.ControlLabel(
            tx, ty, 480, 30, "Current Time: --:--:--", "font16", "FFB0D4E8"
        ),
    )
    sx, sy = panel_abs(lay, 520, 70)
    reg(CID_STATUS, xbmcgui.ControlLabel(sx, sy, 460, 30, "", "font14", "FFFFAA00"))

    lx, ly = panel_abs(lay, 20, LIST_TOP_REL)
    reg(CID_LIST, xbmcgui.ControlList(lx, ly, 1140, LIST_HEIGHT))

    for cid, rx, rw, label in LIST_ROW_BTNS:
        bx, by = panel_abs(lay, rx, LIST_TOP_REL)
        reg(cid, segment_style_push_button(bx, by, rw, BTN_H, label, tex_focus))

    for cid, rx, ry, rw, label in TOOLBAR_BTNS:
        bx, by = panel_abs(lay, rx, ry)
        reg(cid, segment_style_push_button(bx, by, rw, BTN_H, label, tex_focus))

    layout_info = {
        "panel_x": lay.panel_x,
        "panel_y": lay.panel_y,
        "list_top": lay.panel_y + LIST_TOP_REL,
        "list_item_height": LIST_ITEM_HEIGHT,
        "list_height": LIST_HEIGHT,
        "edit_delete_btn_height": BTN_H,
        "start_curr_btn_left": lay.panel_x + 470,
        "end_curr_btn_left": lay.panel_x + 572,
        "snap_start_btn_left": lay.panel_x + 660,
        "snap_end_btn_left": lay.panel_x + 752,
        "merge_btn_left": lay.panel_x + 846,
        "split_btn_left": lay.panel_x + 918,
        "fix_btn_left": lay.panel_x + 968,
        "edit_btn_left": lay.panel_x + 1050,
        "delete_btn_left": lay.panel_x + 1100,
    }
    return controls, cmap, layout_info
