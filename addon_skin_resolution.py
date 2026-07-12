# -*- coding: utf-8 -*-
"""Resolution helpers for Skippy dialogs — **read this before changing layout coords**.

Kodi has two unrelated dialog systems in this addon. Do not mix their coordinate spaces.

WindowXMLDialog (``720p`` / ``1080i`` skin folders)
    Segment editor, skip overlays, marker type picker.
    XML lives under ``resources/skins/default/<720p|1080i>/``.
    On GUI height >= 1080 **or** width >= 1920, ``get_addon_skin_resolution()`` returns ``1080i``
    and Kodi uses a **1920×1080** coordinate space (see ``1080i/SegmentEditorDialog.xml``).
    Python list-row geometry in ``segment_editor_dialog.py`` uses ``scale_skin_coord()``
    to match the active skin folder.

WindowDialog (Python ``xbmcgui.WindowDialog`` — **no skin folder**)
    Upload target picker, upload results, Yes/No, OK scroll, button discovery.
    Implemented in ``skippy_editor_modal_skin.py``, ``segment_marker.py``, ``segment_editor.py``.
    Kodi always places controls in a **1280×720** canvas on every GUI resolution, then
    upscales that canvas to the display. **Never** use ``1080i`` pixel values here —
    e.g. panel width 1755 extends past x=1280 and spills off the right on HD TVs.
    Use ``get_modal_dialog_layout()`` + ``get_modal_metrics()`` (720p table only).

Quick reference
    | Surface                         | API              | Coords on 1080 display |
    |---------------------------------|------------------|------------------------|
    | Segment editor, skip, picker    | WindowXMLDialog  | 1920×1080 via ``1080i`` |
    | Upload modals, yes/no, discovery| WindowDialog     | 1280×720 (Kodi upscales) |
"""
from __future__ import annotations

import os

import xbmcgui

SKIN_RES_720P = "720p"
SKIN_RES_1080I = "1080i"

_BASE_W_720 = 1280
_BASE_H_720 = 720
_BASE_W_1080 = 1920
_BASE_H_1080 = 1080

# WindowXML 1080i/SegmentEditorDialog.xml main group (1920×1080 space). Reference only —
# WindowDialog modals must use _EDITOR_MODAL_PANEL_720P instead (see module docstring).
_EDITOR_MODAL_PANEL_1080I = (75, 90, 1755, 878)
# WindowDialog panel box — same footprint as 720p/SegmentEditorDialog.xml main group.
_EDITOR_MODAL_PANEL_720P = (50, 60, 1170, 585)


class ModalDialogLayout:
    """``xbmcgui.WindowDialog`` canvas + panel box (720p coords only)."""

    __slots__ = (
        "canvas_w",
        "canvas_h",
        "panel_x",
        "panel_y",
        "panel_w",
        "panel_max_h",
    )

    def __init__(
        self,
        canvas_w,
        canvas_h,
        panel_x,
        panel_y,
        panel_w,
        panel_max_h,
    ):
        self.canvas_w = canvas_w
        self.canvas_h = canvas_h
        self.panel_x = panel_x
        self.panel_y = panel_y
        self.panel_w = panel_w
        self.panel_max_h = panel_max_h


class ModalMetrics:
    """Explicit pixel sizes for modal controls — no runtime scale multiplier."""

    __slots__ = (
        "inner_margin",
        "inner_gutter",
        "head_stripe_h",
        "head_stripe_h_fb",
        "label_pad",
        "label_inset",
        "title_h",
        "btn_w_wide",
        "btn_w_ok",
        "btn_h",
        "btn_bottom_pad",
        "stripe_pad",
        "section_gap",
        "body_min_h",
        "tight_gap",
        "btn_gap",
        "scroll_btn_w",
        "scroll_pair_gap",
        "scroll_action_gap",
        "opt_h",
        "opt_gap",
        "block_head_h",
        "pick_pad1",
        "pick_pad2",
        "pick_pad3",
        "title_y",
        "sub_y_off",
        "sub_label_h",
        "sub_y_after",
        "list_y_after",
        "pick_btn_inset",
        "pick_btn_side",
        "panel_bottom_pad",
        "disc_x",
        "disc_y",
        "disc_w",
        "disc_h",
        "disc_lx",
        "disc_lw",
        "disc_title_y",
        "disc_title_h",
        "disc_line2_y",
        "disc_line3_y",
        "disc_line4_y",
        "disc_line_h",
        "disc_foot_y",
        "disc_foot_h",
    )

    def __init__(
        self,
        inner_margin,
        inner_gutter,
        head_stripe_h,
        head_stripe_h_fb,
        label_pad,
        label_inset,
        title_h,
        btn_w_wide,
        btn_w_ok,
        btn_h,
        btn_bottom_pad,
        stripe_pad,
        section_gap,
        body_min_h,
        tight_gap,
        btn_gap,
        scroll_btn_w,
        scroll_pair_gap,
        scroll_action_gap,
        opt_h,
        opt_gap,
        block_head_h,
        pick_pad1,
        pick_pad2,
        pick_pad3,
        title_y,
        sub_y_off,
        sub_label_h,
        sub_y_after,
        list_y_after,
        pick_btn_inset,
        pick_btn_side,
        panel_bottom_pad,
        disc_x,
        disc_y,
        disc_w,
        disc_h,
        disc_lx,
        disc_lw,
        disc_title_y,
        disc_title_h,
        disc_line2_y,
        disc_line3_y,
        disc_line4_y,
        disc_line_h,
        disc_foot_y,
        disc_foot_h,
    ):
        self.inner_margin = inner_margin
        self.inner_gutter = inner_gutter
        self.head_stripe_h = head_stripe_h
        self.head_stripe_h_fb = head_stripe_h_fb
        self.label_pad = label_pad
        self.label_inset = label_inset
        self.title_h = title_h
        self.btn_w_wide = btn_w_wide
        self.btn_w_ok = btn_w_ok
        self.btn_h = btn_h
        self.btn_bottom_pad = btn_bottom_pad
        self.stripe_pad = stripe_pad
        self.section_gap = section_gap
        self.body_min_h = body_min_h
        self.tight_gap = tight_gap
        self.btn_gap = btn_gap
        self.scroll_btn_w = scroll_btn_w
        self.scroll_pair_gap = scroll_pair_gap
        self.scroll_action_gap = scroll_action_gap
        self.opt_h = opt_h
        self.opt_gap = opt_gap
        self.block_head_h = block_head_h
        self.pick_pad1 = pick_pad1
        self.pick_pad2 = pick_pad2
        self.pick_pad3 = pick_pad3
        self.title_y = title_y
        self.sub_y_off = sub_y_off
        self.sub_label_h = sub_label_h
        self.sub_y_after = sub_y_after
        self.list_y_after = list_y_after
        self.pick_btn_inset = pick_btn_inset
        self.pick_btn_side = pick_btn_side
        self.panel_bottom_pad = panel_bottom_pad
        self.disc_x = disc_x
        self.disc_y = disc_y
        self.disc_w = disc_w
        self.disc_h = disc_h
        self.disc_lx = disc_lx
        self.disc_lw = disc_lw
        self.disc_title_y = disc_title_y
        self.disc_title_h = disc_title_h
        self.disc_line2_y = disc_line2_y
        self.disc_line3_y = disc_line3_y
        self.disc_line4_y = disc_line4_y
        self.disc_line_h = disc_line_h
        self.disc_foot_y = disc_foot_y
        self.disc_foot_h = disc_foot_h


_MODAL_METRICS_720P = ModalMetrics(
    inner_margin=20,
    inner_gutter=40,
    head_stripe_h=48,
    head_stripe_h_fb=40,
    label_pad=8,
    label_inset=16,
    title_h=32,
    btn_w_wide=118,
    btn_w_ok=100,
    btn_h=30,
    btn_bottom_pad=14,
    stripe_pad=20,
    section_gap=10,
    body_min_h=120,
    tight_gap=8,
    btn_gap=14,
    scroll_btn_w=44,
    scroll_pair_gap=8,
    scroll_action_gap=12,
    opt_h=36,
    opt_gap=10,
    block_head_h=52,
    pick_pad1=20,
    pick_pad2=24,
    pick_pad3=36,
    title_y=10,
    sub_y_off=4,
    sub_label_h=28,
    sub_y_after=8,
    list_y_after=12,
    pick_btn_inset=24,
    pick_btn_side=12,
    panel_bottom_pad=28,
    disc_x=250,
    disc_y=220,
    disc_w=780,
    disc_h=280,
    disc_lx=280,
    disc_lw=720,
    disc_title_y=248,
    disc_title_h=45,
    disc_line2_y=312,
    disc_line3_y=352,
    disc_line4_y=392,
    disc_line_h=35,
    disc_foot_y=442,
    disc_foot_h=30,
)


def get_modal_dialog_layout() -> ModalDialogLayout:
    """``WindowDialog`` layout — always 1280×720 (Kodi's Python dialog coordinate space).

    Unlike ``WindowXML`` (which uses ``720p`` / ``1080i`` skin folders), ``xbmcgui.WindowDialog``
    controls are placed in a fixed 1280×720 canvas on all GUI resolutions. Kodi upscales that
    canvas to the screen. Using 1080i pixel coords (e.g. panel width 1755) overflows past x=1280
    and spills off the right edge on HD displays.
    """
    px, py, pw, ph = _EDITOR_MODAL_PANEL_720P
    return ModalDialogLayout(
        canvas_w=_BASE_W_720,
        canvas_h=_BASE_H_720,
        panel_x=px,
        panel_y=py,
        panel_w=pw,
        panel_max_h=ph,
    )


def get_modal_metrics(layout: ModalDialogLayout | None = None) -> ModalMetrics:
    """Pixel sizes for ``WindowDialog`` controls (720p table only)."""
    return _MODAL_METRICS_720P


def modal_base_size(resolution: str | None = None) -> tuple[int, int]:
    """Full-screen canvas for ``WindowDialog`` helpers."""
    lay = get_modal_dialog_layout()
    return lay.canvas_w, lay.canvas_h


def get_addon_skin_resolution() -> str:
    """Skin folder for ``WindowXMLDialog`` only — not used by ``WindowDialog`` modals."""
    try:
        w = int(xbmcgui.getScreenWidth())
        h = int(xbmcgui.getScreenHeight())
        # Width is often more reliable than height on Windows (fullscreen playback /
        # DPI scaling can report a reduced height while Kodi still loads 1080i XML).
        if w >= _BASE_W_1080 or h >= _BASE_H_1080:
            return SKIN_RES_1080I
    except Exception:
        pass
    return SKIN_RES_720P


def get_addon_skin_res_dir(addon_path: str, resolution: str | None = None) -> str:
    """Path to ``resources/skins/default/<720p|1080i>``."""
    res = resolution or get_addon_skin_resolution()
    return os.path.join(addon_path, "resources", "skins", "default", res)


def skin_layout_scale(resolution: str | None = None) -> float:
    """Scale factor for 1280×720-based WindowXML / editor list-row layouts on 1080i."""
    res = resolution or get_addon_skin_resolution()
    return 1.5 if res == SKIN_RES_1080I else 1.0


def scale_skin_coord(value, resolution: str | None = None) -> int:
    scale = skin_layout_scale(resolution)
    if scale == 1.0:
        return int(value)
    return int(round(float(value) * scale))


def init_window_xml_dialog(dialog_cls, args) -> str:
    """Initialize ``WindowXMLDialog`` with ``720p`` or ``1080i`` — never for ``WindowDialog``.

    Returns the skin folder name passed to Kodi. Callers must reuse this value for
    ``scale_skin_coord()`` so Python layout matches the loaded XML (``getScreenHeight()``
    can change between ``__init__`` and ``onInit`` on some platforms).
    """
    res = get_addon_skin_resolution()
    if len(args) >= 3:
        try:
            dialog_cls.__init__(args[0], args[1], args[2], res)
            return res
        except TypeError:
            pass
    dialog_cls.__init__(*args)
    return SKIN_RES_720P
