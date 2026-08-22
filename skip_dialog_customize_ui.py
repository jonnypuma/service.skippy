# -*- coding: utf-8 -*-
"""Lazy-loaded Skip Dialog Customize modal (draft settings + frozen mockup)."""
from __future__ import annotations

import os

import xbmc
import xbmcgui
import xbmcvfs

from addon_skin_resolution import (
    init_window_xml_dialog,
    reconcile_window_xml_skin_resolution,
    scale_skin_coord,
)
from settings_utils import (
    addon_get_bool,
    addon_get_int,
    addon_get_setting_text,
    get_addon,
    get_localized,
)
from skip_dialog_appearance import (
    DIALOG_READY_PROP,
    ENDING_TEXT_ARGB,
    FULL_MOCK_W_720,
    FULL_SKIP_BUTTON_IDS,
    FULL_SKIP_PANEL_GROUP_ID,
    MINIMAL_MOCK_H_720,
    MINIMAL_MOCK_W_720,
    MINIMAL_PANEL_GROUP_ID,
    MINIMAL_SKIP_BUTTON_ID,
    MOCK_INTRO_END,
    MOCK_PLAYHEAD,
    MOCK_STAGE_H_720,
    MOCK_STAGE_W_720,
    DictSettingsReader,
    apply_full_skip_layout,
    apply_jump_label,
    apply_jump_properties,
    apply_mock_textures,
    apply_skip_dialog_caps,
    build_customize_mock_segment,
    build_skip_button_label,
    countdown_mmss,
    ending_text_for_segment,
    font_color_argb_from_settings,
    is_compact_combined,
    is_compact_full_mode,
    is_minimal_skip_mode,
    mock_corner_pos,
    set_skip_button_label,
    set_skip_info_label,
    skip_duration_for_playhead,
    skip_format_includes_duration,
)

ID_TITLE = 4090
ID_MODE = 4100
ID_HIDE_ENDING = 4101
ID_FONT = 4102
ID_OVERLAP = 4103
ID_ALL_CAPS = 4104
ID_FULL_HEADER = 4110
ID_PROGRESS = 4111
ID_COUNTDOWN = 4112
ID_HEIGHT = 4113
ID_PROGRESS_STYLE = 4114
ID_POSITION = 4115
ID_FOCUS_STYLE = 4116
ID_SKIP_FORMAT = 4117
ID_HIDE_CLOSE = 4118
ID_FOCUS_FRAME = 4119
ID_HIDE_ICONS = 4120
ID_COMBINED = 4121
ID_DURATION_FORMAT = 4122
ID_DURATION_CONTENT = 4123
ID_MIN_HEADER = 4130
ID_PLATE = 4131
ID_MIN_FORMAT = 4132
ID_MIN_POSITION = 4133
ID_SAVE = 4190
ID_CANCEL = 4191
ID_FANART = 4071
ID_CLOSE_MOCK = 3013

_CANCEL_ACTIONS = (10, 92, 216)
_MOVE_LEFT = getattr(xbmcgui, "ACTION_MOVE_LEFT", 1)
_MOVE_RIGHT = getattr(xbmcgui, "ACTION_MOVE_RIGHT", 2)
_MOVE_UP = getattr(xbmcgui, "ACTION_MOVE_UP", 3)
_MOVE_DOWN = getattr(xbmcgui, "ACTION_MOVE_DOWN", 4)

MODES = ("Full", "CompactFull", "Minimal")
MODE_LABELS = (
    ("Full", "Full"),
    ("Compact Full", "CompactFull"),
    ("Minimal", "Minimal"),
)
SKIP_FORMATS = ("Skip", "Skip + Type", "Skip + Type + Duration")
DURATION_FORMATS = (
    ("1m30s", "1m30s"),
    ("01:30", "mm:ss"),
)
DURATION_CONTENTS = (
    ("Total segment time", "total"),
    ("Elapsed (count up)", "elapsed_up"),
    ("Remaining (count down)", "elapsed_down"),
    ("Elapsed / Total", "elapsed_total"),
)
POSITIONS = (
    ("Bottom Right", "BottomRight"),
    ("Top Right", "TopRight"),
    ("Top Left", "TopLeft"),
    ("Bottom Left", "BottomLeft"),
)
FONT_COLORS = (
    ("White", "FFFFFFFF"),
    ("Light grey", "FF8E8E8E"),
    ("Grey", "FF6E6E6E"),
    ("Dark grey", "FF3D3D3D"),
    ("Black", "FF000000"),
    ("Blue", "FF1976D2"),
    ("Red", "FFE5392F"),
    ("Green", "FF43A047"),
    ("Aquamarine", "FF00ACC1"),
    ("Pink", "FFE91E63"),
    ("Purple", "FF8E24AA"),
    ("Peach", "FFFF8A65"),
    ("Orange", "FFEF6C00"),
    ("Yellow", "FFF9A825"),
)
BUTTON_FOCUS = (
    ("Default", "button_focus.png"),
    ("Aqua", "button_focus_aqua.png"),
    ("Aqua Bevel", "button_focus_aqua_bevel.png"),
    ("Aqua Dark", "button_focus_aqua_dark.png"),
    ("Aqua Vignette", "button_focus_aqua_vignette.png"),
    ("Aqua Rounded", "button_focus_aqua_rounded.png"),
    ("Blue", "button_focus_blue.png"),
    ("Blue Rectangular 3D", "button_focus_blue_rectangular_3d.png"),
    ("Blue Rounded 3D", "button_focus_blue_rounded_3d.png"),
    ("Gold Rectangular 3D", "button_focus_gold_rectangular_3d.png"),
    ("Green 3D", "button_focus_3d_green.png"),
    ("Pink 3D", "button_focus_3d_pink.png"),
    ("Light Pink 3D", "button_focus_3d_light_pink.png"),
    ("Cyan 3D", "button_focus_3d_cyan.png"),
    ("Silver 3D", "button_focus_3d_silver.png"),
    ("Orange 3D", "button_focus_3d_orange.png"),
    ("Violet 3D", "button_focus_3d_violet.png"),
    ("Graphite 3D", "button_focus_3d_graphite.png"),
    ("Ice 3D", "button_focus_3d_ice.png"),
)
MINIMAL_PLATES = (
    ("Rounded Gray", "minimal_rounded_gray_640.png"),
    ("Rectangular Aquamarine Blue", "minimal_rectangular_aquamarine-blue_640.png"),
    ("Rectangular Blue", "minimal_rectangular_blue_640.png"),
    ("Rectangular Yellow", "minimal_rectangular_yellow_640.png"),
    ("3D Blue", "minimal_3d_blue.png"),
    ("3D Glossy Blue", "minimal_3d_glossy_blue.png"),
    ("3D Red Glossy", "minimal_3d_red_glossy.png"),
    ("Black Beveled", "minimal_black_beveled.png"),
    ("Rounded Baby Purple", "minimal_rounded_baby-purple_640.png"),
    ("Rounded Blue Red Gradient", "minimal_rounded_blue-red-gradient_640.png"),
    ("Rounded Bright Aqua", "minimal_rounded_bright-aqua_640.png"),
    ("Rounded Bright Blue Sky", "minimal_rounded_bright-blue-sky_640.png"),
    ("Rounded Bright Cyan", "minimal_rounded_bright-cyan_640.png"),
    ("Rounded Burnt Pink", "minimal_rounded_burnt-pink_640.png"),
    ("Rounded Cranberry", "minimal_rounded_cranberry_640.png"),
    ("Rounded Deep Pink", "minimal_rounded_deep-pink_640.png"),
    ("Rounded Greyish Blue", "minimal_rounded_greyish-blue_640.png"),
    ("Rounded Languid Lavender", "minimal_rounded_languid-lavender_640.png"),
    ("Rounded Light Green 7284348", "minimal_rounded_light-green-7284348_640.png"),
    ("Rounded Light Grey", "minimal_rounded_light-grey_640.png"),
    ("Rounded Light Yellow", "minimal_rounded_light-yellow_640.png"),
    ("Rounded Minty Green", "minimal_rounded_minty-green_640.png"),
    ("Rounded Mustard Yellow", "minimal_rounded_mustard-yellow_640.png"),
    ("Rounded Pale Gold", "minimal_rounded_pale-gold_640.png"),
    ("Rounded Pale Sky Blue", "minimal_rounded_pale-sky-blue_640.png"),
    ("Rounded Pastel Green", "minimal_rounded_pastel-green_640.png"),
    ("Rounded Pattens Blue", "minimal_rounded_pattens-blue_640.png"),
    ("Rounded Peach Orange", "minimal_rounded_peach-orange_640.png"),
    ("Rounded Pink Daisy", "minimal_rounded_pink-daisy_640.png"),
    ("Rounded Pink Lemonade", "minimal_rounded_pink-lemonade_640.png"),
    ("Rounded Pinkish Orange", "minimal_rounded_pinkish-orange_640.png"),
    ("Rounded Sunset", "minimal_rounded_sunset_640.png"),
    ("Rounded White", "minimal_rounded_white_640.png"),
)
PROGRESS_STYLES = (
    ("Green (Default)", "progress_mid.png"),
    ("Blue/purple gradient", "progress_mid_blue_purple.png"),
    ("Dark yellow", "progress_mid_darkyellow.png"),
    ("Green/blue gradient", "progress_mid_green_blue.png"),
    ("Light blue", "progress_mid_lightblue.png"),
    ("Light green", "progress_mid_lightgreen.png"),
    ("Light yellow", "progress_mid_lightyellow.png"),
    ("Pink", "progress_mid_pink.png"),
    ("Pink/light blue gradient", "progress_mid_pink_lightblue.png"),
    ("Purple", "progress_mid_purple.png"),
    ("Yellow/red gradient", "progress_mid_yellow_red.png"),
    ("Cyan 3D", "progress_mid_3d_cyan.png"),
    ("Silver 3D", "progress_mid_3d_silver.png"),
    ("Orange 3D", "progress_mid_3d_orange.png"),
    ("Violet 3D", "progress_mid_3d_violet.png"),
    ("Graphite 3D", "progress_mid_3d_graphite.png"),
    ("Ice 3D", "progress_mid_3d_ice.png"),
)

DRAFT_BOOL_KEYS = (
    "hide_ending_text",
    "skip_overlapping_segments",
    "show_progress_bar",
    "progress_bar_countdown",
    "hide_close_button",
    "show_skip_button_focus_texture",
    "hide_skip_icon",
    "skip_dialog_all_caps",
    "smooth_progress_bar",
    "compact_full_combined",
)
DRAFT_TEXT_KEYS = (
    "skip_dialog_mode",
    "skip_dialog_font_color",
    "skip_dialog_position",
    "button_focus_style",
    "skip_button_format",
    "skip_duration_format",
    "skip_duration_content",
    "minimal_button_style",
    "minimal_skip_button_format",
    "minimal_skip_dialog_position",
    "progress_bar_style",
)
DRAFT_INT_KEYS = (("progress_bar_height", 16, 5, 32),)

_TEXT_DEFAULTS = {
    "skip_dialog_mode": "Full",
    "skip_dialog_font_color": "FFFFFFFF",
    "skip_dialog_position": "BottomRight",
    "button_focus_style": "button_focus.png",
    "skip_button_format": "Skip + Type + Duration",
    "skip_duration_format": "1m30s",
    "skip_duration_content": "total",
    "minimal_button_style": "minimal_rounded_gray_640.png",
    "minimal_skip_button_format": "Skip + Type",
    "minimal_skip_dialog_position": "BottomRight",
    "progress_bar_style": "progress_mid.png",
}
_BOOL_DEFAULTS = {
    "hide_ending_text": False,
    "skip_overlapping_segments": True,
    "show_progress_bar": True,
    "progress_bar_countdown": False,
    "hide_close_button": False,
    "show_skip_button_focus_texture": True,
    "hide_skip_icon": False,
    "skip_dialog_all_caps": False,
    "smooth_progress_bar": False,
    "compact_full_combined": False,
}


def load_skip_dialog_draft(addon) -> dict:
    draft = {}
    for key in DRAFT_TEXT_KEYS:
        draft[key] = (
            addon_get_setting_text(addon, key, _TEXT_DEFAULTS[key]) or _TEXT_DEFAULTS[key]
        ).strip()
    for key in DRAFT_BOOL_KEYS:
        draft[key] = addon_get_bool(addon, key, _BOOL_DEFAULTS[key])
    for key, default, minimum, maximum in DRAFT_INT_KEYS:
        draft[key] = addon_get_int(addon, key, default, minimum=minimum, maximum=maximum)
    return draft


def draft_setting_payload(draft: dict) -> dict:
    """Convert a draft dict to Kodi setSetting strings."""
    out = {}
    for key in DRAFT_TEXT_KEYS:
        out[key] = str(draft.get(key, _TEXT_DEFAULTS[key]))
    for key in DRAFT_BOOL_KEYS:
        out[key] = "true" if draft.get(key, _BOOL_DEFAULTS[key]) else "false"
    for key, default, minimum, maximum in DRAFT_INT_KEYS:
        val = int(draft.get(key, default))
        val = max(minimum, min(maximum, val))
        out[key] = str(val)
    return out


def _cycle(options, current, delta):
    items = list(options)
    if not items:
        return current
    try:
        idx = items.index(current)
    except ValueError:
        idx = 0
    return items[(idx + delta) % len(items)]


def _pair_label(pairs, stored):
    for label, value in pairs:
        if value == stored:
            return label
    return stored


def customize_nav_ids(draft: dict):
    """Visible left-pane control order. XML onup/ondown are self-bound so this is the only mover."""
    ids = [ID_MODE]
    mode = draft.get("skip_dialog_mode") or "Full"
    minimal = is_minimal_skip_mode(mode)
    compact = is_compact_full_mode(mode)
    combined = (not minimal) and bool(draft.get("compact_full_combined"))
    if not minimal and not compact:
        ids.append(ID_HIDE_ENDING)
    ids.extend([ID_FONT, ID_ALL_CAPS])
    if not minimal:
        ids.append(ID_OVERLAP)
        ids.append(ID_COMBINED)
        if not combined:
            ids.extend(
                [
                    ID_PROGRESS,
                    ID_COUNTDOWN,
                    ID_PROGRESS_STYLE,
                ]
            )
            if not compact:
                ids.append(ID_HEIGHT)
        else:
            ids.append(ID_COUNTDOWN)
        ids.extend(
            [
                ID_POSITION,
                ID_FOCUS_STYLE,
                ID_SKIP_FORMAT,
            ]
        )
        if skip_format_includes_duration(draft.get("skip_button_format") or "Skip + Type + Duration"):
            ids.extend([ID_DURATION_FORMAT, ID_DURATION_CONTENT])
        if not combined:
            ids.append(ID_HIDE_CLOSE)
            if not compact:
                ids.append(ID_HIDE_ICONS)
            if draft.get("hide_close_button"):
                ids.append(ID_FOCUS_FRAME)
        elif not compact:
            ids.append(ID_HIDE_ICONS)
    else:
        ids.extend([ID_PLATE, ID_MIN_FORMAT, ID_MIN_POSITION])
        if skip_format_includes_duration(draft.get("minimal_skip_button_format") or "Skip + Type"):
            ids.extend([ID_DURATION_FORMAT, ID_DURATION_CONTENT])
    ids.extend([ID_SAVE, ID_CANCEL])
    return ids


def customize_section_header_before(nav_ids):
    """Insert Full/Minimal section headers before these packed row ids.

    Combined sits with global options (after Ignore overlapping). The Full
    header must not land between those two rows, or Combined jumps under
    Full-mode options when the progress rows hide.
    """
    starts = set()
    if ID_PLATE in nav_ids:
        starts.add(ID_PLATE)
    if ID_PROGRESS in nav_ids:
        starts.add(ID_PROGRESS)
    elif ID_COUNTDOWN in nav_ids:
        starts.add(ID_COUNTDOWN)
    elif ID_POSITION in nav_ids:
        starts.add(ID_POSITION)
    return starts


def customize_left_pane_layout(nav_ids, sc):
    """Pack rows above pinned Save/Cancel. Shrink row height if the list would overlap."""
    ids = [cid for cid in nav_ids if cid not in (ID_SAVE, ID_CANCEL)]
    starts = customize_section_header_before(ids)
    n_headers = sum(1 for cid in ids if cid in starts)
    start_y = sc(52)
    header_h = sc(24)
    save_h = sc(36)
    pane_h = sc(688)
    save_y = pane_h - sc(16) - save_h
    gap = sc(8)
    default_row = sc(34)
    min_row = sc(26)
    budget = save_y - gap - start_y - n_headers * header_h
    row_h = default_row
    if ids:
        if budget > 0:
            row_h = min(default_row, max(min_row, budget // len(ids)))
        else:
            row_h = min_row
    content_bottom = start_y + n_headers * header_h + len(ids) * row_h
    return {
        "ids": ids,
        "starts": starts,
        "left": sc(16),
        "start_y": start_y,
        "header_h": header_h,
        "row_h": row_h,
        "save_y": save_y,
        "save_h": save_h,
        "save_w": sc(220),
        "cancel_x": sc(252),
        "gap": gap,
        "content_bottom": content_bottom,
    }


def _yes_no(addon, flag):
    return get_localized(addon, 44105, "Yes") if flag else get_localized(addon, 44106, "No")


class SkipDialogCustomize(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self._skin_resolution = init_window_xml_dialog(super(SkipDialogCustomize, self), args)
        self.addon = kwargs.get("addon") or get_addon()
        self._draft = kwargs.get("draft") or load_skip_dialog_draft(self.addon)
        self._original = dict(self._draft)
        self._saved = False
        self._closing = False

    def _sc(self, value):
        return scale_skin_coord(value, getattr(self, "_skin_resolution", None))

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

    def onInit(self):
        asked = getattr(self, "_skin_resolution", None)
        locked = reconcile_window_xml_skin_resolution(self, asked)
        if locked != asked:
            self._skin_resolution = locked
        self._set_label(ID_TITLE, get_localized(self.addon, 44102, "Customize skip dialog"))
        self._set_label(ID_SAVE, get_localized(self.addon, 44103, "Save"))
        self._set_label(ID_CANCEL, get_localized(self.addon, 44104, "Cancel"))
        self._set_label(ID_FULL_HEADER, get_localized(self.addon, 32021, "Full mode"))
        self._set_label(ID_MIN_HEADER, get_localized(self.addon, 32022, "Minimal mode"))
        self._load_fanart()
        self.refresh_mockup()
        try:
            self.setFocusId(ID_MODE)
        except Exception:
            pass

    def _load_fanart(self):
        ctrl = self._ctrl(ID_FANART)
        if not ctrl or not self.addon:
            return
        path = os.path.join(self.addon.getAddonInfo("path") or "", "fanart.png")
        if xbmcvfs.exists(path):
            try:
                ctrl.setImage(path)
            except Exception:
                pass

    def _nav_ids(self):
        return customize_nav_ids(self._draft)

    def _focus_id(self):
        try:
            return int(self.getFocusId())
        except Exception:
            return ID_MODE

    def _move_focus(self, delta):
        ids = self._nav_ids()
        current = self._focus_id()
        if current not in ids:
            current = ids[0]
        nxt = ids[(ids.index(current) + delta) % len(ids)]
        try:
            self.setFocusId(nxt)
        except Exception:
            pass

    def refresh_mockup(self):
        settings = DictSettingsReader(self._draft)
        addon = self.addon
        mode = settings.get_text("skip_dialog_mode", "Full").strip() or "Full"
        minimal = is_minimal_skip_mode(mode)
        compact = is_compact_full_mode(mode)
        combined = is_compact_combined(settings)
        self.setProperty("skippy_customize_mode", mode)
        self.setProperty("skippy_compact_full", "true" if compact else "false")
        hide_end = settings.get_bool("hide_ending_text", False)
        hide_close = True if combined else settings.get_bool("hide_close_button", False)
        hide_icon = settings.get_bool("hide_skip_icon", False)
        if compact:
            hide_end = True
            hide_icon = True
        self.setProperty(
            "skippy_customize_hide_close",
            "true" if hide_close else "false",
        )
        self.setProperty("hide_ending_text", "true" if hide_end else "false")
        self.setProperty("hide_close_button", "true" if hide_close else "false")
        self.setProperty("hide_skip_icon", "true" if hide_icon else "false")
        if compact:
            self._set_label(ID_FULL_HEADER, get_localized(addon, 32100, "Compact Full"))
        else:
            self._set_label(ID_FULL_HEADER, get_localized(addon, 32021, "Full mode"))

        segment = build_customize_mock_segment(settings.get_bool("skip_overlapping_segments", True))
        color = font_color_argb_from_settings(settings)
        self.setProperty("skip_dialog_text_color", color)
        duration_str = skip_duration_for_playhead(MOCK_PLAYHEAD, segment, settings)
        if minimal:
            fmt = settings.get_text("minimal_skip_button_format", "Skip + Type")
        else:
            fmt = settings.get_text("skip_button_format", "Skip + Type + Duration")
        self.setProperty(
            "skippy_customize_duration",
            "true" if skip_format_includes_duration(fmt) else "false",
        )
        skip_label = apply_skip_dialog_caps(
            build_skip_button_label(segment, fmt, duration_str, addon),
            settings.get_bool("skip_dialog_all_caps", False),
        )
        for cid in FULL_SKIP_BUTTON_IDS:
            set_skip_button_label(self._ctrl(cid), skip_label, color)
        set_skip_button_label(self._ctrl(MINIMAL_SKIP_BUTTON_ID), skip_label, color)
        close_lbl = apply_skip_dialog_caps(
            get_localized(addon, 40001, "Close"),
            settings.get_bool("skip_dialog_all_caps", False),
        )
        set_skip_button_label(self._ctrl(ID_CLOSE_MOCK), close_lbl, color)

        all_caps = settings.get_bool("skip_dialog_all_caps", False)
        self.setProperty(
            "ending_text",
            apply_skip_dialog_caps(ending_text_for_segment(addon, segment), all_caps),
        )
        remaining = MOCK_INTRO_END - MOCK_PLAYHEAD
        self.setProperty("countdown", countdown_mmss(remaining))
        apply_jump_properties(self, addon, segment, all_caps=all_caps)
        if self.getProperty("show_next_jump") == "true":
            apply_jump_label(self, self.getProperty("next_jump_label") or "")
        end_ctrl = self._ctrl(2)
        if end_ctrl and not hide_end:
            line = "%s %s" % (
                self.getProperty("ending_text") or "",
                self.getProperty("countdown") or "",
            )
            set_skip_info_label(end_ctrl, line.strip(), ENDING_TEXT_ARGB, font="font10")

        panel_h = self._sc(100)
        if not minimal:
            panel_h = apply_full_skip_layout(
                self,
                settings,
                playhead=MOCK_PLAYHEAD,
                segment=segment,
                scale_fn=self._sc,
            ) or panel_h

        stage_w = self._sc(MOCK_STAGE_W_720)
        stage_h = self._sc(MOCK_STAGE_H_720)
        if minimal:
            corner = settings.get_text("minimal_skip_dialog_position", "BottomRight")
            x, y = mock_corner_pos(
                corner,
                stage_w,
                stage_h,
                self._sc(MINIMAL_MOCK_W_720),
                self._sc(MINIMAL_MOCK_H_720),
            )
            grp = self._ctrl(MINIMAL_PANEL_GROUP_ID)
            if grp:
                grp.setPosition(x, y)
        else:
            corner = settings.get_text("skip_dialog_position", "BottomRight")
            x, y = mock_corner_pos(
                corner, stage_w, stage_h, self._sc(FULL_MOCK_W_720), int(panel_h)
            )
            grp = self._ctrl(FULL_SKIP_PANEL_GROUP_ID)
            if grp:
                grp.setPosition(x, y)

        apply_mock_textures(self, settings, minimal)
        self.setProperty(DIALOG_READY_PROP, "true")
        self._layout_left_pane()
        self._refresh_row_labels()

    def _layout_left_pane(self):
        """Pack visible setting rows so Minimal does not leave holes for Full-only options."""
        metrics = customize_left_pane_layout(self._nav_ids(), self._sc)
        left = metrics["left"]
        y = metrics["start_y"]
        row_h = metrics["row_h"]
        header_h = metrics["header_h"]
        ids = metrics["ids"]
        section_start = metrics["starts"]
        for cid in ids:
            if cid in section_start:
                header_id = ID_MIN_HEADER if cid == ID_PLATE else ID_FULL_HEADER
                header = self._ctrl(header_id)
                if header:
                    try:
                        header.setPosition(left, y)
                    except Exception:
                        pass
                y += header_h
            ctrl = self._ctrl(cid)
            if ctrl:
                try:
                    ctrl.setPosition(left, y)
                except Exception:
                    pass
                try:
                    ctrl.setHeight(row_h)
                except Exception:
                    pass
                try:
                    ctrl.setVisible(True)
                except Exception:
                    pass
            y += row_h
        save = self._ctrl(ID_SAVE)
        cancel = self._ctrl(ID_CANCEL)
        save_y = metrics["save_y"]
        save_h = metrics["save_h"]
        save_w = metrics["save_w"]
        if save:
            try:
                save.setPosition(left, save_y)
            except Exception:
                pass
            try:
                save.setWidth(save_w)
                save.setHeight(save_h)
            except Exception:
                pass
        if cancel:
            try:
                cancel.setPosition(metrics["cancel_x"], save_y)
            except Exception:
                pass
            try:
                cancel.setWidth(save_w)
                cancel.setHeight(save_h)
            except Exception:
                pass
        for cid in (
            ID_HIDE_ENDING,
            ID_OVERLAP,
            ID_PROGRESS,
            ID_COUNTDOWN,
            ID_PROGRESS_STYLE,
            ID_HEIGHT,
            ID_POSITION,
            ID_FOCUS_STYLE,
            ID_SKIP_FORMAT,
            ID_COMBINED,
            ID_DURATION_FORMAT,
            ID_DURATION_CONTENT,
            ID_HIDE_CLOSE,
            ID_HIDE_ICONS,
            ID_FOCUS_FRAME,
            ID_PLATE,
            ID_MIN_FORMAT,
            ID_MIN_POSITION,
        ):
            if cid not in ids:
                hidden = self._ctrl(cid)
                if hidden:
                    try:
                        hidden.setVisible(False)
                    except Exception:
                        pass

    def _refresh_row_labels(self):
        addon = self.addon
        d = self._draft
        self._set_label(
            ID_MODE,
            "%s: %s"
            % (get_localized(addon, 32020, "Skip dialog mode"), _pair_label(MODE_LABELS, d.get("skip_dialog_mode", "Full"))),
        )
        self._set_label(
            ID_HIDE_ENDING,
            "%s: %s"
            % (
                get_localized(addon, 32016, "Hide ending text"),
                _yes_no(addon, d.get("hide_ending_text")),
            ),
        )
        self._set_label(
            ID_FONT,
            "%s: %s"
            % (
                get_localized(addon, 32026, "Skip dialog font color"),
                _pair_label(FONT_COLORS, d.get("skip_dialog_font_color")),
            ),
        )
        self._set_label(
            ID_ALL_CAPS,
            "%s: %s"
            % (
                get_localized(addon, 32099, "Skip dialog text in ALL CAPS"),
                _yes_no(addon, d.get("skip_dialog_all_caps")),
            ),
        )
        self._set_label(
            ID_OVERLAP,
            "%s: %s"
            % (
                get_localized(addon, 31007, "Ignore overlapping segments"),
                _yes_no(addon, d.get("skip_overlapping_segments")),
            ),
        )
        self._set_label(
            ID_PROGRESS,
            "%s: %s"
            % (
                get_localized(addon, 32007, "Show Progress Bar in Skip Dialog"),
                _yes_no(addon, d.get("show_progress_bar")),
            ),
        )
        self._set_label(
            ID_COUNTDOWN,
            "%s: %s"
            % (
                get_localized(addon, 32027, "Progress bar shows remaining (countdown)"),
                _yes_no(addon, d.get("progress_bar_countdown")),
            ),
        )
        self._set_label(
            ID_PROGRESS_STYLE,
            "%s: %s"
            % (
                get_localized(addon, 32079, "Progress bar style"),
                _pair_label(PROGRESS_STYLES, d.get("progress_bar_style")),
            ),
        )
        self._set_label(
            ID_HEIGHT,
            "%s: %s"
            % (
                get_localized(addon, 32080, "Progress bar height (pixels)"),
                d.get("progress_bar_height", 16),
            ),
        )
        self._set_label(
            ID_POSITION,
            "%s: %s"
            % (
                get_localized(addon, 32009, "Skip Dialog Position"),
                _pair_label(POSITIONS, d.get("skip_dialog_position")),
            ),
        )
        self._set_label(
            ID_FOCUS_STYLE,
            "%s: %s"
            % (
                get_localized(addon, 32000, "Button Focus Style"),
                _pair_label(BUTTON_FOCUS, d.get("button_focus_style")),
            ),
        )
        self._set_label(
            ID_SKIP_FORMAT,
            "%s: %s"
            % (
                get_localized(addon, 32013, "Skip button format"),
                d.get("skip_button_format", "Skip + Type + Duration"),
            ),
        )
        self._set_label(
            ID_COMBINED,
            "%s: %s"
            % (
                get_localized(addon, 32101, "Combined skip and progress"),
                _yes_no(addon, d.get("compact_full_combined")),
            ),
        )
        self._set_label(
            ID_DURATION_FORMAT,
            "%s: %s"
            % (
                get_localized(addon, 32102, "Skip duration format"),
                _pair_label(DURATION_FORMATS, d.get("skip_duration_format", "1m30s")),
            ),
        )
        self._set_label(
            ID_DURATION_CONTENT,
            "%s: %s"
            % (
                get_localized(addon, 32103, "Skip duration content"),
                _pair_label(DURATION_CONTENTS, d.get("skip_duration_content", "total")),
            ),
        )
        self._set_label(
            ID_HIDE_CLOSE,
            "%s: %s"
            % (
                get_localized(addon, 32014, "Hide Close button"),
                _yes_no(addon, d.get("hide_close_button")),
            ),
        )
        self._set_label(
            ID_HIDE_ICONS,
            "%s: %s"
            % (
                get_localized(addon, 32015, "Hide Skip and Close Icons"),
                _yes_no(addon, d.get("hide_skip_icon")),
            ),
        )
        self._set_label(
            ID_FOCUS_FRAME,
            "%s: %s"
            % (
                get_localized(addon, 32081, "Show skip button focus frame"),
                _yes_no(addon, d.get("show_skip_button_focus_texture")),
            ),
        )
        self._set_label(
            ID_PLATE,
            "%s: %s"
            % (
                get_localized(addon, 32023, "Minimal plate style"),
                _pair_label(MINIMAL_PLATES, d.get("minimal_button_style")),
            ),
        )
        self._set_label(
            ID_MIN_FORMAT,
            "%s: %s"
            % (
                get_localized(addon, 32025, "Minimal skip label format"),
                d.get("minimal_skip_button_format", "Skip + Type"),
            ),
        )
        self._set_label(
            ID_MIN_POSITION,
            "%s: %s"
            % (
                get_localized(addon, 32024, "Minimal skip dialog position"),
                _pair_label(POSITIONS, d.get("minimal_skip_dialog_position")),
            ),
        )

    def _nudge(self, control_id, delta):
        d = self._draft
        if control_id == ID_MODE:
            d["skip_dialog_mode"] = _cycle(MODES, d.get("skip_dialog_mode", "Full"), delta)
        elif control_id == ID_HIDE_ENDING:
            d["hide_ending_text"] = not d.get("hide_ending_text")
        elif control_id == ID_FONT:
            stored = [pair[1] for pair in FONT_COLORS]
            d["skip_dialog_font_color"] = _cycle(
                stored, d.get("skip_dialog_font_color", "FFFFFFFF"), delta
            )
        elif control_id == ID_ALL_CAPS:
            d["skip_dialog_all_caps"] = not d.get("skip_dialog_all_caps")
        elif control_id == ID_OVERLAP:
            d["skip_overlapping_segments"] = not d.get("skip_overlapping_segments", True)
        elif control_id == ID_PROGRESS:
            d["show_progress_bar"] = not d.get("show_progress_bar", True)
        elif control_id == ID_COUNTDOWN:
            d["progress_bar_countdown"] = not d.get("progress_bar_countdown")
        elif control_id == ID_PROGRESS_STYLE:
            stored = [pair[1] for pair in PROGRESS_STYLES]
            d["progress_bar_style"] = _cycle(
                stored, d.get("progress_bar_style", "progress_mid.png"), delta
            )
        elif control_id == ID_HEIGHT:
            val = int(d.get("progress_bar_height", 16)) + delta
            d["progress_bar_height"] = max(5, min(32, val))
        elif control_id == ID_POSITION:
            stored = [pair[1] for pair in POSITIONS]
            d["skip_dialog_position"] = _cycle(
                stored, d.get("skip_dialog_position", "BottomRight"), delta
            )
        elif control_id == ID_FOCUS_STYLE:
            stored = [pair[1] for pair in BUTTON_FOCUS]
            d["button_focus_style"] = _cycle(
                stored, d.get("button_focus_style", "button_focus.png"), delta
            )
        elif control_id == ID_SKIP_FORMAT:
            d["skip_button_format"] = _cycle(
                SKIP_FORMATS, d.get("skip_button_format", "Skip + Type + Duration"), delta
            )
        elif control_id == ID_COMBINED:
            d["compact_full_combined"] = not d.get("compact_full_combined")
        elif control_id == ID_DURATION_FORMAT:
            stored = [pair[1] for pair in DURATION_FORMATS]
            d["skip_duration_format"] = _cycle(
                stored, d.get("skip_duration_format", "1m30s"), delta
            )
        elif control_id == ID_DURATION_CONTENT:
            stored = [pair[1] for pair in DURATION_CONTENTS]
            d["skip_duration_content"] = _cycle(
                stored, d.get("skip_duration_content", "total"), delta
            )
        elif control_id == ID_HIDE_CLOSE:
            d["hide_close_button"] = not d.get("hide_close_button")
        elif control_id == ID_HIDE_ICONS:
            d["hide_skip_icon"] = not d.get("hide_skip_icon")
        elif control_id == ID_FOCUS_FRAME:
            d["show_skip_button_focus_texture"] = not d.get(
                "show_skip_button_focus_texture", True
            )
        elif control_id == ID_PLATE:
            stored = [pair[1] for pair in MINIMAL_PLATES]
            d["minimal_button_style"] = _cycle(
                stored, d.get("minimal_button_style", "minimal_rounded_gray_640.png"), delta
            )
        elif control_id == ID_MIN_FORMAT:
            d["minimal_skip_button_format"] = _cycle(
                SKIP_FORMATS, d.get("minimal_skip_button_format", "Skip + Type"), delta
            )
        elif control_id == ID_MIN_POSITION:
            stored = [pair[1] for pair in POSITIONS]
            d["minimal_skip_dialog_position"] = _cycle(
                stored, d.get("minimal_skip_dialog_position", "BottomRight"), delta
            )
        else:
            return
        self.refresh_mockup()

    def _save_and_close(self):
        addon = self.addon
        if addon:
            payload = draft_setting_payload(self._draft)
            original = draft_setting_payload(self._original)
            for key, value in payload.items():
                if original.get(key) != value:
                    try:
                        addon.setSetting(key, value)
                    except Exception:
                        pass
        self._saved = True
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
        if cid == ID_SAVE:
            self._save_and_close()
            return
        if cid == ID_CANCEL:
            self._cancel_and_close()
            return
        if cid in (
            ID_MODE,
            ID_HIDE_ENDING,
            ID_FONT,
            ID_ALL_CAPS,
            ID_OVERLAP,
            ID_PROGRESS,
            ID_COUNTDOWN,
            ID_PROGRESS_STYLE,
            ID_HEIGHT,
            ID_POSITION,
            ID_FOCUS_STYLE,
            ID_SKIP_FORMAT,
            ID_COMBINED,
            ID_DURATION_FORMAT,
            ID_DURATION_CONTENT,
            ID_HIDE_CLOSE,
            ID_HIDE_ICONS,
            ID_FOCUS_FRAME,
            ID_PLATE,
            ID_MIN_FORMAT,
            ID_MIN_POSITION,
        ):
            self._nudge(cid, 1)

    def onAction(self, action):
        aid = action.getId()
        if aid in _CANCEL_ACTIONS:
            self._cancel_and_close()
            return
        if aid == _MOVE_DOWN:
            self._move_focus(1)
            return
        if aid == _MOVE_UP:
            self._move_focus(-1)
            return
        if aid in (_MOVE_LEFT, _MOVE_RIGHT):
            cid = self._focus_id()
            if cid in (ID_SAVE, ID_CANCEL):
                self._move_focus(1 if aid == _MOVE_RIGHT else -1)
                return
            self._nudge(cid, 1 if aid == _MOVE_RIGHT else -1)


def show_skip_dialog_customize():
    addon = get_addon()
    if not addon:
        return False
    path = addon.getAddonInfo("path")
    dialog = SkipDialogCustomize(
        "SkipDialogCustomize.xml", path, "default", addon=addon
    )
    dialog.doModal()
    saved = bool(getattr(dialog, "_saved", False))
    del dialog
    return saved
