# -*- coding: utf-8 -*-
"""Skip-dialog labels, colours, and Full-mode layout — shared by playback and Customize.

Playback reads addon settings; the Customize mockup reads an in-memory draft.
Neither path patches production SkipDialog XML.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Optional

from segment_relations import (
    JUMP_KIND_NAMED,
    JUMP_KIND_REMAINING,
    jump_info_nested,
    parse_jump_info,
)
from settings_utils import (
    addon_get_bool,
    addon_get_int,
    addon_get_setting_text,
    compute_skip_seek_destination_seconds,
    get_localized,
)
from skip_dialog_window_ui import _argb_to_kodi
from time_format import format_jump_clock

FULL_SKIP_BUTTON_IDS = (3012, 3015, 3016)

FULL_SKIP_PANEL_GROUP_ID = 3080
FULL_SKIP_PANEL_BACKDROP_ID = 3081
# 9-slice focus overlays — only in SkipDialogCustomize.xml, not live SkipDialog_*.xml
CUSTOMIZE_SKIP_FOCUS_OVERLAY_IDS = (3040, 3042, 3041, 3043)
FULL_SKIP_PANEL_W_720 = 430
FULL_SKIP_MARGIN_720 = 5
FULL_SKIP_PROGRESS_BAR_WIDTH = FULL_SKIP_PANEL_W_720 - (FULL_SKIP_MARGIN_720 * 2)
# Dialog width follows the skip label. Each label format has its own ladder of
# fixed widths; the label's estimated size picks the first rung that fits, so a
# plain "Skip" stays narrow while a long type name or duration still fits.
SKIP_BTN_TEXT_PAD_720 = 40
SKIP_BTN_MAX_TEXT_W_720 = 420
SKIP_ICON_SLOT_720 = 30
SKIP_CLOSE_ICON_SLOT_720 = 20
SKIP_CLOSE_BTN_W_720 = 80
SKIP_CLOSE_ICON_ID = 3083
SKIP_WIDTH_STEPS_720 = {
    "Skip": (96, 120),
    "Skip + Type": (150, 190, 240, 300, 360),
    "Skip + Type + Duration": (230, 270, 320, 380, 420),
}
SKIP_ROWS_MIN_CONTENT_W_720 = {"jump": 280, "ending": 190}
SKIP_DIALOG_CANVAS_W_720 = 1280
SKIP_DIALOG_SCREEN_MARGIN_720 = 10
SKIP_DIALOG_MODE_FULL = "Full"
SKIP_DIALOG_MODE_COMPACT = "CompactFull"
SKIP_DIALOG_MODE_MINIMAL = "Minimal"
COMPACT_SKIP_CONTENT_W_720 = 300
COMPACT_SKIP_BTN_TOP_720 = 4
COMPACT_SKIP_BTN_H_720 = 25
COMPACT_SKIP_CLOSE_W_720 = 72
COMPACT_SKIP_GAP_720 = 8
COMPACT_PROGRESS_H_720 = 4
COMBINED_TRACK_ID = 3050
COMBINED_FILL_STRETCH_ID = 3051
COMBINED_FILL_SLICE_ID = 3052
COMBINED_TRACK_SLICE_ID = 3053
COMBINED_SLICE_MIN_W = 24
DURATION_FORMAT_1M30S = "1m30s"
DURATION_FORMAT_MMSS = "mm:ss"
DURATION_CONTENT_TOTAL = "total"
DURATION_CONTENT_ELAPSED_UP = "elapsed_up"
DURATION_CONTENT_ELAPSED_DOWN = "elapsed_down"
DURATION_CONTENT_ELAPSED_TOTAL = "elapsed_total"
SMOOTH_PROGRESS_BG_ID = 3030
SMOOTH_PROGRESS_FILL_ID = 3031
SMOOTH_BAR_WINDOW_PROP = "skippy_smooth_bar"
DIALOG_READY_PROP = "skippy_dialog_ready"

MINIMAL_PANEL_GROUP_ID = 5090
MINIMAL_PLATE_IMAGE_ID = 5021
MINIMAL_SKIP_BUTTON_ID = 5012

MOCK_INTRO_START = 0.0
MOCK_INTRO_END = 90.0
MOCK_RECAP_START = 30.0
MOCK_RECAP_END = 50.0
MOCK_PLAYHEAD = 22.5
JUMP_LABEL_ARGB = "FFB0D4E8"
JUMP_LABEL_FONT = "font11"
ENDING_TEXT_ARGB = "FFFFFFFF"
# Kodi 9-slice on texturefocus / ControlImage: left,top,right,bottom in source pixels.
BUTTON_FOCUS_NINE_SLICE_BORDERS = {
    "button_focus_aqua_bevel.png": "12,0,12,0",
    "button_focus_aqua_rounded.png": "12,0,12,0",
    "button_focus_blue_rounded_3d.png": "12,0,12,0",
    "button_focus_gold_rectangular_3d.png": "12,0,12,0",
    "button_focus_3d_green.png": "12,0,12,0",
    "button_focus_3d_pink.png": "12,0,12,0",
    "button_focus_3d_light_pink.png": "12,0,12,0",
    "button_focus_3d_cyan.png": "12,0,12,0",
    "button_focus_3d_silver.png": "12,0,12,0",
    "button_focus_3d_orange.png": "12,0,12,0",
    "button_focus_3d_violet.png": "12,0,12,0",
    "button_focus_3d_graphite.png": "12,0,12,0",
    "button_focus_3d_ice.png": "12,0,12,0",
    "button_focus_flat_blue.png": "12,12,12,12",
    "button_focus_flat_teal.png": "12,12,12,12",
    "button_focus_flat_green.png": "12,12,12,12",
    "button_focus_flat_rose.png": "12,12,12,12",
    "button_focus_flat_orange.png": "12,12,12,12",
    "button_focus_flat_violet.png": "12,12,12,12",
    "button_focus_flat_slate.png": "12,12,12,12",
    "button_focus_flat_white.png": "12,12,12,12",
    "button_focus_glass_white.png": "12,12,12,12",
    "button_focus_glass_blue.png": "12,12,12,12",
    "button_focus_glass_dark.png": "12,12,12,12",
    "button_focus_outline_white.png": "12,12,12,12",
    "button_focus_outline_cyan.png": "12,12,12,12",
    "button_focus_frosted_white.png": "12,12,12,12",
    "button_focus_steel.png": "12,12,12,12",
    "button_focus_neon_cyan.png": "12,12,12,12",
    "button_focus_neon_magenta.png": "12,12,12,12",
    "button_focus_gold.png": "12,12,12,12",
    "button_focus_pastel_mint.png": "12,12,12,12",
    "button_focus_pastel_peach.png": "12,12,12,12",
    "button_focus_pastel_lavender.png": "12,12,12,12",
    "button_focus_bracket_white.png": "12,12,12,12",
    "button_focus_bracket_cyan.png": "12,12,12,12",
    "button_focus_bracket_green.png": "12,12,12,12",
}


def button_focus_nine_slice_border(filename: str) -> Optional[str]:
    """Return Kodi ``border`` for 3D focus art, or None to stretch the whole image."""
    name = (filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    return BUTTON_FOCUS_NINE_SLICE_BORDERS.get(name)


def card_color_diffuse(settings) -> str:
    """AARRGGBB black for the Full-mode card; opacity setting is 0-100 percent."""
    pct = settings.get_int("skip_card_opacity", 95, minimum=0, maximum=100)
    return "%02X000000" % int(round(max(0, min(100, pct)) * 255 / 100.0))


def skip_dialog_mode_name(raw: Optional[str]) -> str:
    """Normalize stored skip_dialog_mode to Full, CompactFull, or Minimal."""
    mode = (raw or SKIP_DIALOG_MODE_FULL).strip()
    if mode in (SKIP_DIALOG_MODE_COMPACT, "Compact Full"):
        return SKIP_DIALOG_MODE_COMPACT
    if mode == SKIP_DIALOG_MODE_MINIMAL:
        return SKIP_DIALOG_MODE_MINIMAL
    return SKIP_DIALOG_MODE_FULL


def is_minimal_skip_mode(raw: Optional[str]) -> bool:
    return skip_dialog_mode_name(raw) == SKIP_DIALOG_MODE_MINIMAL


def is_compact_full_mode(raw: Optional[str]) -> bool:
    return skip_dialog_mode_name(raw) == SKIP_DIALOG_MODE_COMPACT


def is_combined_skip_progress(settings) -> bool:
    """True when Combined fill is on for Full or Compact Full (not Minimal)."""
    mode = skip_dialog_mode_name(settings.get_text("skip_dialog_mode", SKIP_DIALOG_MODE_FULL))
    if mode == SKIP_DIALOG_MODE_MINIMAL:
        return False
    return settings.get_bool("compact_full_combined", False)


def is_compact_combined(settings) -> bool:
    """Back-compat alias for Combined skip+progress (Full and Compact Full)."""
    return is_combined_skip_progress(settings)


def skip_dialog_align_right(settings) -> bool:
    corner = (settings.get_text("skip_dialog_position", "BottomRight") or "BottomRight").replace(
        " ", ""
    )
    return corner.endswith("Right")


def skip_dialog_panel_left_720(align_right: bool) -> int:
    """720p X of group 3080. Right corners keep the same 10px inset as the left."""
    if align_right:
        return SKIP_DIALOG_CANVAS_W_720 - FULL_SKIP_PANEL_W_720 - SKIP_DIALOG_SCREEN_MARGIN_720
    return SKIP_DIALOG_SCREEN_MARGIN_720


def skip_progress_bar_width_720(settings) -> int:
    if is_compact_full_mode(settings.get_text("skip_dialog_mode", SKIP_DIALOG_MODE_FULL)):
        return COMPACT_SKIP_CONTENT_W_720
    return FULL_SKIP_PROGRESS_BAR_WIDTH


MOCK_STAGE_W_720 = 720
MOCK_STAGE_H_720 = 540
FULL_MOCK_W_720 = 430
MINIMAL_MOCK_W_720 = 120
MINIMAL_MOCK_H_720 = 46

_SKIP_DIALOG_FONT_COLOR_ARGB = {
    "white": "FFFFFFFF",
    "light grey": "FF8E8E8E",
    "light gray": "FF8E8E8E",
    "grey": "FF6E6E6E",
    "gray": "FF6E6E6E",
    "dark grey": "FF3D3D3D",
    "dark gray": "FF3D3D3D",
    "black": "FF000000",
    "blue": "FF1976D2",
    "red": "FFE5392F",
    "green": "FF43A047",
    "aquamarine": "FF00ACC1",
    "pink": "FFE91E63",
    "purple": "FF8E24AA",
    "peach": "FFFF8A65",
    "orange": "FFEF6C00",
    "yellow": "FFF9A825",
}

_SKIP_DIALOG_FONT_COLOR_INDEXED = (
    "FFFFFFFF",
    "FF8E8E8E",
    "FF6E6E6E",
    "FF3D3D3D",
    "FF000000",
    "FF1976D2",
    "FFE5392F",
    "FF43A047",
    "FF00ACC1",
    "FFE91E63",
    "FF8E24AA",
    "FFFF8A65",
    "FFEF6C00",
    "FFF9A825",
)


class AddonSettingsReader:
    """Read skip-dialog settings from a Kodi addon handle."""

    def __init__(self, addon: Any):
        self.addon = addon

    def get_text(self, key: str, default: str = "") -> str:
        if not self.addon:
            return default
        return addon_get_setting_text(self.addon, key, default) or default

    def get_bool(self, key: str, default: bool = False) -> bool:
        if not self.addon:
            return default
        return addon_get_bool(self.addon, key, default)

    def get_int(
        self,
        key: str,
        default: int = 0,
        minimum: Optional[int] = None,
        maximum: Optional[int] = None,
    ) -> int:
        if not self.addon:
            return default
        return addon_get_int(self.addon, key, default, minimum=minimum, maximum=maximum)


class DictSettingsReader:
    """Read skip-dialog settings from an in-memory draft dict."""

    def __init__(self, data: dict):
        self.data = data or {}

    def get_text(self, key: str, default: str = "") -> str:
        val = self.data.get(key, default)
        if val is None:
            return default
        return str(val)

    def get_bool(self, key: str, default: bool = False) -> bool:
        val = self.data.get(key, default)
        if isinstance(val, bool):
            return val
        if val is None:
            return default
        return str(val).strip().lower() in ("true", "1", "yes")

    def get_int(
        self,
        key: str,
        default: int = 0,
        minimum: Optional[int] = None,
        maximum: Optional[int] = None,
    ) -> int:
        raw = self.data.get(key, default)
        try:
            v = int(str(raw).strip())
        except (TypeError, ValueError):
            v = default
        if minimum is not None:
            v = max(minimum, v)
        if maximum is not None:
            v = min(maximum, v)
        return v


# Longest common type name, so the Customize preview shows the width worst case.
MOCK_SEGMENT_LABEL = "commercial"


class MockSegment:
    """Minimal segment object for Customize preview (no parse / player)."""

    def __init__(
        self,
        start_seconds,
        end_seconds,
        label="intro",
        next_segment_start=None,
        next_segment_info=None,
    ):
        self.start_seconds = float(start_seconds)
        self.end_seconds = float(end_seconds)
        self.segment_type_label = label
        self.next_segment_start = next_segment_start
        self.next_segment_info = next_segment_info


def build_customize_mock_segment(skip_overlapping: bool) -> MockSegment:
    recap = MockSegment(MOCK_RECAP_START, MOCK_RECAP_END, "recap")
    if skip_overlapping:
        return MockSegment(MOCK_INTRO_START, MOCK_INTRO_END, MOCK_SEGMENT_LABEL)
    return MockSegment(
        MOCK_INTRO_START,
        MOCK_INTRO_END,
        MOCK_SEGMENT_LABEL,
        next_segment_start=MOCK_RECAP_START,
        next_segment_info=jump_info_nested(recap),
    )


def duration_label(seconds) -> str:
    duration = int(round(float(seconds or 0)))
    m, s = divmod(max(duration, 0), 60)
    return "%dm%ds" % (m, s) if m else "%ds" % s


def format_skip_duration(seconds, style: str) -> str:
    """Format a duration for the skip button: ``1m30s`` or ``01:30`` / ``1:30:00``."""
    sec = max(0, int(round(float(seconds or 0))))
    if (style or "").strip() == DURATION_FORMAT_MMSS:
        if sec >= 3600:
            hours, rem = divmod(sec, 3600)
            minutes, secs = divmod(rem, 60)
            return "%d:%02d:%02d" % (hours, minutes, secs)
        minutes, secs = divmod(sec, 60)
        return "%02d:%02d" % (minutes, secs)
    return duration_label(sec)


def skip_button_duration_text(elapsed, remaining, total, style, content) -> str:
    kind = (content or DURATION_CONTENT_TOTAL).strip()
    fmt = (style or DURATION_FORMAT_1M30S).strip()
    if kind == DURATION_CONTENT_ELAPSED_UP:
        return format_skip_duration(elapsed, fmt)
    if kind == DURATION_CONTENT_ELAPSED_DOWN:
        return format_skip_duration(remaining, fmt)
    if kind == DURATION_CONTENT_ELAPSED_TOTAL:
        return "%s / %s" % (
            format_skip_duration(elapsed, fmt),
            format_skip_duration(total, fmt),
        )
    return format_skip_duration(total, fmt)


def skip_duration_for_playhead(playhead, segment, settings) -> str:
    start = float(getattr(segment, "start_seconds", 0) or 0)
    end = float(getattr(segment, "end_seconds", 0) or 0)
    total = max(0.0, end - start)
    head = float(playhead if playhead is not None else start)
    elapsed = max(0.0, min(total, head - start))
    total_i = max(0, int(round(total)))
    elapsed_i = max(0, min(total_i, int(elapsed)))
    remaining_i = max(0, total_i - elapsed_i)
    return skip_button_duration_text(
        elapsed_i,
        remaining_i,
        total_i,
        settings.get_text("skip_duration_format", DURATION_FORMAT_1M30S),
        settings.get_text("skip_duration_content", DURATION_CONTENT_TOTAL),
    )


def skip_format_includes_duration(format_setting) -> bool:
    return "Duration" in (format_setting or "")


def countdown_mmss(remaining_seconds) -> str:
    remaining = int(max(remaining_seconds, 0))
    m, s = divmod(remaining, 60)
    return "%02d:%02d" % (m, s)


def display_segment_label(label):
    """Catalog display name when the label is a known type; otherwise a readable fallback."""
    from settings_utils import format_segment_label_for_ui

    shown = format_segment_label_for_ui(label)
    if shown:
        return shown
    return (label or "").strip()


def format_next_jump_label(addon, next_segment_info, next_segment_start):
    """Build Ask-dialog subtext for the skip landing (or None if no jump target)."""
    if next_segment_start is None:
        return None
    time_str = format_jump_clock(next_segment_start)
    kind, label = parse_jump_info(next_segment_info)

    if kind == JUMP_KIND_REMAINING:
        return get_localized(
            addon,
            40007,
            "Skip to remaining %s at %s",
            display_segment_label(label),
            time_str,
        )
    if kind == JUMP_KIND_NAMED:
        return get_localized(
            addon,
            40005,
            "Skip to %s at %s",
            display_segment_label(label),
            time_str,
        )
    return get_localized(addon, 40006, "Skip to next segment at %s", time_str)


def resolve_font_color_argb(raw, fallback="FF6E6E6E"):
    """Resolve a stored font-color setting to AARRGGBB."""
    text = (raw or "").strip()
    if not text:
        return fallback
    if len(text) == 8 and all(c in "0123456789ABCDEFabcdef" for c in text):
        return text.upper()
    if len(text) == 6 and all(c in "0123456789ABCDEFabcdef" for c in text):
        return "FF%s" % text.upper()
    key = text.lower()
    if key in _SKIP_DIALOG_FONT_COLOR_ARGB:
        return _SKIP_DIALOG_FONT_COLOR_ARGB[key]
    if text.isdigit():
        idx = int(text)
        if 0 <= idx < len(_SKIP_DIALOG_FONT_COLOR_INDEXED):
            return _SKIP_DIALOG_FONT_COLOR_INDEXED[idx]
    return fallback


def font_color_argb_from_settings(settings) -> str:
    return resolve_font_color_argb(
        settings.get_text("skip_dialog_font_color", "FFFFFFFF")
    )


_DURATION_HMS_RE = re.compile(r"(\d+)H(\d+)M(\d+)S")
_DURATION_MS_RE = re.compile(r"(\d+)M(\d+)S")
_DURATION_H_RE = re.compile(r"(\d+)H\b")
_DURATION_M_RE = re.compile(r"(\d+)M\b")
_DURATION_S_RE = re.compile(r"(\d+)S\b")


def apply_skip_dialog_caps(text, enabled: bool) -> str:
    """Uppercase skip-dialog copy, keeping duration units as ``h`` / ``m`` / ``s``."""
    if not enabled or not text:
        return text or ""
    out = str(text).upper()
    out = _DURATION_HMS_RE.sub(r"\1h\2m\3s", out)
    out = _DURATION_MS_RE.sub(r"\1m\2s", out)
    out = _DURATION_H_RE.sub(r"\1h", out)
    out = _DURATION_M_RE.sub(r"\1m", out)
    out = _DURATION_S_RE.sub(r"\1s", out)
    return out


def shadow_for_text(text_argb):
    """Dark halo on light text; soft light halo on dark text."""
    s = (text_argb or "").strip().upper()
    if len(s) == 8:
        r, g, b = int(s[2:4], 16), int(s[4:6], 16), int(s[6:8], 16)
    elif len(s) == 6:
        r, g, b = int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
    else:
        return "0xFF000000"
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    if lum >= 140:
        return "0xFF000000"
    return "0x66FFFFFF"


def _set_control_label(control, label, text_argb, font):
    """Apply text + colour on WindowXML buttons and labels.

    ControlLabel rejects ``focusedColor``; falling through to ``setLabel(text, font)``
    resets skin/$INFO colour to white. Try label-safe kwargs first.
    """
    if not control:
        return
    tc = _argb_to_kodi(text_argb)
    sc = shadow_for_text(text_argb)
    kw_attempts = (
        dict(font=font, textColor=tc, disabledColor=tc, shadowColor=sc),
        dict(font=font, textColor=tc, disabledColor=tc, shadowColor=sc, focusedColor=tc),
        dict(font=font, textColor=tc, shadowColor=sc),
        dict(font=font, textColor=tc),
        dict(textColor=tc),
    )
    for kwargs in kw_attempts:
        try:
            control.setLabel(label, **kwargs)
            return
        except TypeError:
            continue
    pos_attempts = (
        (label, font, tc, tc, sc, tc),
        (label, font, tc, tc, sc),
        (label, font, tc),
        (label, font),
        (label,),
    )
    for args in pos_attempts:
        try:
            control.setLabel(*args)
            return
        except TypeError:
            continue


def set_skip_button_label(control, label, text_argb, font="font16"):
    """WindowXML ignores skin <font>/textcolor; apply label + colours in Python."""
    _set_control_label(control, label, text_argb, font)


def set_skip_info_label(control, label, text_argb, font="font10"):
    _set_control_label(control, label, text_argb, font)


def is_minimal_plate_filename(name: str) -> bool:
    n = (name or "").strip().lower()
    return n.endswith(".png") or n.endswith(".jpg") or n.endswith(".jpeg")


def minimal_plate_filename(settings) -> str:
    raw = (settings.get_text("minimal_button_style", "") or "").strip()
    if is_minimal_plate_filename(raw):
        return raw
    return "minimal_rounded_gray_640.png"


def build_skip_button_label(segment, format_setting, duration_str, addon=None):
    typ = display_segment_label(
        getattr(segment, "segment_type_label", None) or "segment"
    )
    if format_setting == "Skip":
        return get_localized(addon, 40000, "Skip")
    if format_setting == "Skip + Type":
        return get_localized(addon, 40002, "Skip %s", typ)
    return get_localized(addon, 40003, "Skip %s (%s)", typ, duration_str)


def _label_glyph_width_720(ch: str) -> float:
    """Rough 720p width of one glyph in the skin's button font (deliberately generous)."""
    if ch == " ":
        return 5.0
    if ch in "il.,:;|'!1":
        return 5.5 if ch != "1" else 10.5
    if ch in "()/[]-":
        return 6.5
    if ch.isdigit():
        return 10.5
    if ch in "mwMW":
        return 15.0
    if ch.isupper():
        return 13.0
    return 9.5


def estimate_skip_label_width_720(label: str) -> int:
    return int(round(sum(_label_glyph_width_720(c) for c in (label or ""))))


def skip_format_tier(format_setting) -> str:
    fmt = (format_setting or "").strip()
    if fmt == "Skip":
        return "Skip"
    if fmt == "Skip + Type":
        return "Skip + Type"
    return "Skip + Type + Duration"


def skip_label_width_720(label: str, format_setting) -> int:
    """Width of the skip button text area: first rung of the format's ladder that fits."""
    need = min(
        estimate_skip_label_width_720(label) + SKIP_BTN_TEXT_PAD_720,
        SKIP_BTN_MAX_TEXT_W_720,
    )
    steps = SKIP_WIDTH_STEPS_720[skip_format_tier(format_setting)]
    for step in steps:
        if need <= step:
            return step
    return min(need, SKIP_BTN_MAX_TEXT_W_720)


def widest_skip_label(segment, settings, addon=None) -> str:
    """Longest label the dialog can show for this segment (live durations never exceed it)."""
    fmt = settings.get_text("skip_button_format", "Skip + Type + Duration")
    start = float(getattr(segment, "start_seconds", 0) or 0)
    end = float(getattr(segment, "end_seconds", 0) or 0)
    total = max(0, int(round(max(0.0, end - start))))
    dur = skip_button_duration_text(
        total,
        total,
        total,
        settings.get_text("skip_duration_format", DURATION_FORMAT_1M30S),
        settings.get_text("skip_duration_content", DURATION_CONTENT_TOTAL),
    )
    return apply_skip_dialog_caps(
        build_skip_button_label(segment, fmt, dur, addon),
        settings.get_bool("skip_dialog_all_caps", False),
    )


def elapsed_progress_percent_float(current_time, segment_start, total_duration):
    if not total_duration or total_duration <= 0:
        return 0.0
    elapsed = max(current_time - segment_start, 0)
    p = (elapsed / float(total_duration)) * 100.0
    return min(max(p, 0.0), 100.0)


def progress_display_percent_float(elapsed_pct_f, countdown):
    return 100.0 - elapsed_pct_f if countdown else elapsed_pct_f


def elapsed_progress_percent(current_time, segment_start, total_duration):
    if not total_duration or total_duration <= 0:
        return 0
    elapsed = max(current_time - segment_start, 0)
    p = int((elapsed / float(total_duration)) * 100)
    return min(max(p, 0), 100)


def progress_display_percent(elapsed_pct, countdown):
    return 100 - elapsed_pct if countdown else elapsed_pct


def seed_progress_values(current_time, segment_start, total_duration, countdown, bar_width):
    """Return (classic_percent, smooth_fill_width) for the current playhead."""
    elapsed_f = elapsed_progress_percent_float(current_time, segment_start, total_duration)
    pct_f = progress_display_percent_float(elapsed_f, countdown)
    pct_f = min(max(pct_f, 0.0), 100.0)
    disp = int(round(pct_f))
    w = int(round((pct_f / 100.0) * float(bar_width)))
    return disp, max(0, min(int(bar_width), w))


def full_skip_focus_id(hide_close, hide_skip_icon):
    """3012 is hidden when the close button is hidden; match Full dialog XML visibility."""
    if hide_close:
        return 3016 if hide_skip_icon else 3015
    return 3012


def progress_mid_filename(settings) -> str:
    raw = (settings.get_text("progress_bar_style", "") or "").strip()
    if raw.endswith(".png"):
        return raw
    return "progress_mid.png"


def ending_text_for_segment(addon, segment) -> str:
    raw = getattr(segment, "segment_type_label", None) or ""
    if raw and raw.lower() != "segment":
        segment_type = display_segment_label(raw)
    else:
        segment_type = "Segment"
    return get_localized(addon, 40004, "%s ending in:", segment_type)


def apply_jump_label(window, text, control_id=3011):
    """Next-jump subtext: accent cyan, smaller than skip-button font16."""
    ctrl = _safe_control(window, control_id)
    if not ctrl:
        return
    set_skip_info_label(ctrl, text or "", JUMP_LABEL_ARGB, font=JUMP_LABEL_FONT)


def apply_jump_properties(window, addon, segment, all_caps: bool = False) -> Optional[str]:
    next_start = getattr(segment, "next_segment_start", None)
    if next_start is not None:
        next_start = compute_skip_seek_destination_seconds(segment, addon)
    jump_str = format_next_jump_label(
        addon,
        getattr(segment, "next_segment_info", None),
        next_start,
    )
    if jump_str:
        jump_str = apply_skip_dialog_caps(jump_str, all_caps)
        window.setProperty("next_jump_label", jump_str)
        window.setProperty("show_next_jump", "true")
        return jump_str
    window.setProperty("show_next_jump", "false")
    window.setProperty("next_jump_label", "")
    return None


def _safe_control(window, control_id):
    try:
        return window.getControl(control_id)
    except Exception:
        return None


def _place_ctrl(ctrl, x, y, w=None, h=None):
    if not ctrl:
        return
    try:
        ctrl.setPosition(int(x), int(y))
    except Exception:
        pass
    if w is not None:
        try:
            ctrl.setWidth(int(w))
        except Exception:
            pass
    if h is not None:
        try:
            ctrl.setHeight(int(h))
        except Exception:
            pass


def full_skip_panel_metrics(
    sc, compact, hide_close, hide_skip_icon, text_w, min_content_w=0
):
    """Geometry (skin pixels) of the Skip/Close row for a label of ``text_w`` (720p)."""
    margin = FULL_SKIP_MARGIN_720
    if compact:
        close_w = COMPACT_SKIP_CLOSE_W_720
        gap = COMPACT_SKIP_GAP_720
        content_w = text_w if hide_close else text_w + close_w + gap
        content_w = max(content_w, min_content_w)
        skip_w = content_w if hide_close else content_w - close_w - gap
        return {
            "panel_w": sc(content_w),
            "content_w": sc(content_w),
            "left0": 0,
            "skip_x": 0,
            "skip_w": sc(skip_w),
            "wide_x": 0,
            "wide_w": sc(content_w),
            "close_x": sc(skip_w + gap),
            "close_w": sc(close_w),
            "close_icon_x": None,
        }
    icon_slot = 0 if hide_skip_icon else SKIP_ICON_SLOT_720
    if hide_close:
        btn_w = text_w + 2 * icon_slot
        panel_w = max(btn_w + 2 * margin, min_content_w + 2 * margin)
        content_w = panel_w - 2 * margin
        return {
            "panel_w": sc(panel_w),
            "content_w": sc(content_w),
            "left0": sc(margin),
            "skip_x": sc(35),
            "skip_w": sc(text_w),
            "wide_x": sc(margin),
            "wide_w": sc(content_w),
            "close_x": 0,
            "close_w": 0,
            "close_icon_x": None,
        }
    skip_x = 35
    tail = SKIP_CLOSE_ICON_SLOT_720 + SKIP_CLOSE_BTN_W_720 + margin
    panel_w = max(skip_x + text_w + tail, min_content_w + 2 * margin)
    skip_w = panel_w - skip_x - tail
    return {
        "panel_w": sc(panel_w),
        "content_w": sc(panel_w - 2 * margin),
        "left0": sc(margin),
        "skip_x": sc(skip_x),
        "skip_w": sc(skip_w),
        "wide_x": sc(margin),
        "wide_w": sc(panel_w - 2 * margin),
        "close_x": sc(skip_x + skip_w + SKIP_CLOSE_ICON_SLOT_720),
        "close_w": sc(SKIP_CLOSE_BTN_W_720),
        "close_icon_x": sc(skip_x + skip_w),
    }


def _layout_full_skip_buttons(
    window,
    sc,
    compact,
    hide_close,
    align_right,
    place_focus_overlays=False,
    hide_skip_icon=False,
    text_w=None,
    min_content_w=0,
):
    """Place Skip/Close and optional Customize focus overlays; return (content_left, content_w)."""
    if text_w is None:
        # Legacy fixed layout: wide enough for any label.
        text_w = 290 if not compact else COMPACT_SKIP_CONTENT_W_720 - COMPACT_SKIP_CLOSE_W_720 - COMPACT_SKIP_GAP_720
    m = full_skip_panel_metrics(
        sc, compact, hide_close, hide_skip_icon, text_w, min_content_w
    )
    left0 = m["left0"]
    content_w = m["content_w"]
    btn_top = sc(COMPACT_SKIP_BTN_TOP_720) if compact else sc(10)
    btn_h = sc(COMPACT_SKIP_BTN_H_720) if compact else sc(25)
    skip_x, skip_w = m["skip_x"], m["skip_w"]
    close_x, close_w = m["close_x"], m["close_w"]
    wide_x, wide_w = m["wide_x"], m["wide_w"]
    try:
        window._skip_panel_w = m["panel_w"]
    except Exception:
        pass
    if m["close_icon_x"] is not None and not hide_close and not hide_skip_icon:
        _place_ctrl(
            _safe_control(window, SKIP_CLOSE_ICON_ID), m["close_icon_x"], sc(13)
        )

    # Each control call waits for a rendered frame, so place only the buttons the
    # skin can actually show. The preview window toggles these live, so it still
    # places every variant.
    if place_focus_overlays:
        _place_ctrl(_safe_control(window, 3012), skip_x, btn_top, skip_w, btn_h)
        _place_ctrl(_safe_control(window, 3013), close_x, btn_top, close_w, btn_h)
        _place_ctrl(_safe_control(window, 3015), wide_x, btn_top, wide_w, btn_h)
        _place_ctrl(_safe_control(window, 3016), wide_x, btn_top, wide_w, btn_h)
    else:
        active_id = full_skip_focus_id(hide_close, hide_skip_icon)
        if active_id == 3012:
            _place_ctrl(_safe_control(window, 3012), skip_x, btn_top, skip_w, btn_h)
        else:
            _place_ctrl(_safe_control(window, active_id), wide_x, btn_top, wide_w, btn_h)
        if not hide_close:
            _place_ctrl(_safe_control(window, 3013), close_x, btn_top, close_w, btn_h)
    if place_focus_overlays:
        for cid in CUSTOMIZE_SKIP_FOCUS_OVERLAY_IDS:
            if cid in (3040, 3042):
                _place_ctrl(_safe_control(window, cid), skip_x, btn_top, skip_w, btn_h)
            else:
                _place_ctrl(_safe_control(window, cid), wide_x, btn_top, wide_w, btn_h)
    try:
        if hide_close:
            window._skip_btn_geom = (wide_x, btn_top, wide_w, btn_h)
        else:
            window._skip_btn_geom = (skip_x, btn_top, skip_w, btn_h)
    except Exception:
        pass
    return left0, content_w


def apply_full_skip_layout(
    window,
    settings,
    playhead,
    segment,
    scale_fn: Callable[[int], int],
    log_fn: Optional[Callable[[str], None]] = None,
    place_focus_overlays: bool = False,
    addon=None,
):
    """Size the panel to the skip label, stack optional rows, seed progress from playhead."""
    sc = scale_fn
    compact = is_compact_full_mode(settings.get_text("skip_dialog_mode", SKIP_DIALOG_MODE_FULL))
    combined = is_compact_combined(settings)
    hide_close = True if combined else settings.get_bool("hide_close_button", False)
    align_right = skip_dialog_align_right(settings)
    if compact:
        window.setProperty("skippy_compact_full", "true")
        window.setProperty("hide_ending_text", "true")
        window.setProperty("hide_skip_icon", "true")
    else:
        window.setProperty("skippy_compact_full", "false")
    if combined:
        window.setProperty("hide_close_button", "true")
    window.setProperty("skippy_combined", "true" if combined else "false")

    focus_file = (settings.get_text("button_focus_style", "") or "").strip()
    if not focus_file.endswith(".png"):
        focus_file = "button_focus.png"
    sliced = bool(button_focus_nine_slice_border(focus_file))
    window.setProperty("skippy_combined_fill", focus_file)
    window.setProperty("skippy_combined_slice", "true" if sliced else "false")

    # Mirrors the dialog's own resolution so the placed button is the visible one.
    hide_skip_icon = True if compact else settings.get_bool("hide_skip_icon", False)
    show_jump_row = window.getProperty("show_next_jump") == "true"
    ending_row = (not compact) and window.getProperty("hide_ending_text") != "true"
    min_content_w = 0
    if show_jump_row:
        min_content_w = SKIP_ROWS_MIN_CONTENT_W_720["jump"]
    elif ending_row:
        min_content_w = SKIP_ROWS_MIN_CONTENT_W_720["ending"]
    label_for_width = widest_skip_label(segment, settings, addon)
    text_w = skip_label_width_720(
        label_for_width, settings.get_text("skip_button_format", "Skip + Type + Duration")
    )
    content_left, progress_bar_width = _layout_full_skip_buttons(
        window,
        sc,
        compact,
        hide_close,
        align_right,
        place_focus_overlays,
        hide_skip_icon,
        text_w=text_w,
        min_content_w=min_content_w,
    )
    panel_w = int(getattr(window, "_skip_panel_w", sc(FULL_SKIP_PANEL_W_720)))
    CONTENT_TOP = sc(33) if compact else sc(41)
    GAP_AFTER_JUMP = sc(5)
    GAP_BEFORE_PROGRESS = sc(4) if not compact else sc(3)
    BOTTOM_MARGIN = sc(4) if compact else sc(5)
    META_LINE_H = sc(20)
    BTN_BOTTOM = sc(COMPACT_SKIP_BTN_TOP_720 + COMPACT_SKIP_BTN_H_720) if compact else sc(35)
    UNDER_BTNS_FALLBACK = sc(8) if compact else sc(14)
    LEFT_MARGIN = content_left
    show_jump = window.getProperty("show_next_jump") == "true"
    hide_end = True if compact else window.getProperty("hide_ending_text") == "true"
    show_progress = settings.get_bool("show_progress_bar", False)
    show_separate_progress = show_progress and not combined
    countdown = settings.get_bool("progress_bar_countdown", False)
    if compact:
        progress_h = sc(COMPACT_PROGRESS_H_720)
    else:
        progress_h = sc(settings.get_int("progress_bar_height", 16, minimum=5, maximum=32))
    smooth_ui = settings.get_bool("smooth_progress_bar", False)
    total_duration = getattr(segment, "end_seconds", 0) - getattr(segment, "start_seconds", 0)

    def _log(msg):
        if log_fn:
            log_fn(msg)

    try:
        window._skip_progress_bar_width = progress_bar_width
    except Exception:
        pass

    bottom = CONTENT_TOP
    if show_jump:
        bottom += META_LINE_H
        if not hide_end or show_separate_progress:
            bottom += GAP_AFTER_JUMP
    if not hide_end:
        bottom += META_LINE_H
        if show_separate_progress:
            bottom += GAP_BEFORE_PROGRESS
    if show_separate_progress:
        bottom += progress_h
    has_meta = show_jump or (not hide_end) or show_separate_progress
    total_h = (bottom + BOTTOM_MARGIN) if has_meta else (BTN_BOTTOM + UNDER_BTNS_FALLBACK)
    total_h = max(total_h, BTN_BOTTOM + UNDER_BTNS_FALLBACK)

    try:
        panel = _safe_control(window, FULL_SKIP_PANEL_GROUP_ID)
        backdrop = _safe_control(window, FULL_SKIP_PANEL_BACKDROP_ID)
        if panel:
            # Keep XML posx/width (corner file already placed the group).
            # Only height follows ending text / progress / jump rows.
            try:
                panel.setHeight(total_h)
                panel.setWidth(panel_w)
            except Exception:
                pass
            if not place_focus_overlays:
                # The corner skin anchors the group for the widest panel; re-anchor it
                # for this width (right corners keep the same inset as left ones).
                try:
                    x720 = (
                        SKIP_DIALOG_CANVAS_W_720
                        - SKIP_DIALOG_SCREEN_MARGIN_720
                        if align_right
                        else SKIP_DIALOG_SCREEN_MARGIN_720
                    )
                    x = sc(x720) - panel_w if align_right else sc(x720)
                    panel.setPosition(int(x), int(panel.getPosition()[1]))
                except Exception as e:
                    _log("Full skip panel position: %s" % e)
        if backdrop:
            _place_ctrl(backdrop, 0, 0, panel_w, total_h)
            try:
                backdrop.setColorDiffuse(card_color_diffuse(settings))
            except Exception:
                pass
            try:
                backdrop.setVisible(
                    (not compact) and settings.get_bool("skip_card_enabled", True)
                )
            except Exception:
                pass
    except Exception as e:
        _log("Full skip panel height: %s" % e)

    bottom = CONTENT_TOP
    try:
        if show_jump:
            label_j = _safe_control(window, 3011)
            if label_j:
                _place_ctrl(label_j, LEFT_MARGIN, bottom, progress_bar_width, META_LINE_H)
            bottom += META_LINE_H
            if not hide_end or show_separate_progress:
                bottom += GAP_AFTER_JUMP

        if not hide_end:
            label_e = _safe_control(window, 2)
            if label_e:
                _place_ctrl(label_e, LEFT_MARGIN, bottom, progress_bar_width, META_LINE_H)
            bottom += META_LINE_H
            if show_separate_progress:
                bottom += GAP_BEFORE_PROGRESS

        progress = _safe_control(window, 3014)
        if progress:
            progress.setVisible(False)
        window.setProperty(SMOOTH_BAR_WINDOW_PROP, "false")
        geom = getattr(window, "_skip_btn_geom", None)
        current = playhead
        if current is None:
            current = getattr(segment, "start_seconds", 0)
        if combined and geom:
            skip_x, btn_top, skip_w, btn_h = geom
            window._skip_progress_bar_width = skip_w
            _pct, init_w = seed_progress_values(
                current,
                getattr(segment, "start_seconds", 0),
                total_duration,
                countdown,
                skip_w,
            )
            if sliced and init_w > 0:
                init_w = max(init_w, min(skip_w, COMBINED_SLICE_MIN_W))
            try:
                window._last_smooth_fill_w = init_w
            except Exception:
                pass
            # The sliced and stretched variants are mutually exclusive in the skin,
            # so only the pair that can be shown is touched.
            track = _safe_control(
                window, COMBINED_TRACK_SLICE_ID if sliced else COMBINED_TRACK_ID
            )
            active_fill = _safe_control(
                window, COMBINED_FILL_SLICE_ID if sliced else COMBINED_FILL_STRETCH_ID
            )
            # Texture, colordiffuse and visibility all come from the skin XML via
            # skippy_combined_fill / skippy_combined_slice, so only geometry is set
            # here. Setting the texture from Python would also drop the nine-slice
            # border the sliced variants declare.
            _place_ctrl(track, skip_x, btn_top, skip_w, btn_h)
            _place_ctrl(active_fill, skip_x, btn_top, init_w, btn_h)
            bg = _safe_control(window, SMOOTH_PROGRESS_BG_ID)
            fill = _safe_control(window, SMOOTH_PROGRESS_FILL_ID)
            if bg:
                try:
                    bg.setVisible(False)
                except Exception:
                    pass
            if fill:
                try:
                    fill.setVisible(False)
                except Exception:
                    pass
            window.setProperty("skippy_progress_ready", "false")
            _log(
                "Combined fill seeded: %spx / %spx (countdown=%s, playhead=%.2fs)"
                % (init_w, skip_w, countdown, float(current))
            )
        else:
            # Combined fill images are already hidden by skippy_combined in the skin.
            if show_separate_progress and progress:
                py = bottom
                progress.setPosition(LEFT_MARGIN, py)
                progress.setHeight(progress_h)
                try:
                    progress.setWidth(progress_bar_width)
                except Exception:
                    pass
                init_pct, init_w = seed_progress_values(
                    current,
                    getattr(segment, "start_seconds", 0),
                    total_duration,
                    countdown,
                    progress_bar_width,
                )
                progress.setPercent(init_pct)
                try:
                    window._last_smooth_fill_w = init_w
                except Exception:
                    pass
                bg = _safe_control(window, SMOOTH_PROGRESS_BG_ID)
                fill = _safe_control(window, SMOOTH_PROGRESS_FILL_ID)
                if bg and fill:
                    bg.setPosition(LEFT_MARGIN, py)
                    bg.setWidth(progress_bar_width)
                    bg.setHeight(progress_h)
                    fill.setPosition(LEFT_MARGIN, py)
                    fill.setHeight(progress_h)
                    fill.setWidth(init_w)
                    if smooth_ui:
                        progress.setVisible(False)
                        window.setProperty(SMOOTH_BAR_WINDOW_PROP, "true")
                    else:
                        window.setProperty(SMOOTH_BAR_WINDOW_PROP, "false")
                        progress.setVisible(True)
                else:
                    window.setProperty(SMOOTH_BAR_WINDOW_PROP, "false")
                    progress.setVisible(True)
                window.setProperty("skippy_progress_ready", "true")
                _log(
                    "Progress seeded: %s%% / %spx (countdown=%s, playhead=%.2fs)"
                    % (init_pct, init_w, countdown, float(current))
                )
            else:
                window.setProperty(SMOOTH_BAR_WINDOW_PROP, "false")
                window.setProperty("skippy_progress_ready", "false")
    except Exception as e:
        _log("Full skip vertical layout failed: %s" % e)
    return total_h


def mock_corner_pos(corner, stage_w, stage_h, panel_w, panel_h, margin=8):
    """Return (x, y) of a mock panel inside a fanart stage."""
    c = (corner or "BottomRight").replace(" ", "")
    x_right = max(margin, int(stage_w) - int(panel_w) - margin)
    y_bottom = max(margin, int(stage_h) - int(panel_h) - margin)
    if c == "TopLeft":
        return margin, margin
    if c == "TopRight":
        return x_right, margin
    if c == "BottomLeft":
        return margin, y_bottom
    return x_right, y_bottom


def apply_mock_textures(window, settings, minimal_mode: bool):
    """Skin-relative texture names via window properties (no filesystem paths)."""
    focus_file = (settings.get_text("button_focus_style", "") or "").strip()
    if not focus_file.endswith(".png"):
        focus_file = "button_focus.png"
    progress_file = progress_mid_filename(settings)
    plate = minimal_plate_filename(settings)
    hide_close = True if is_compact_combined(settings) else settings.get_bool(
        "hide_close_button", False
    )
    show_frame = settings.get_bool("show_skip_button_focus_texture", True)
    combined = is_compact_combined(settings)

    sliced = bool(button_focus_nine_slice_border(focus_file))
    window.setProperty("skippy_mock_focus", focus_file)
    window.setProperty("skippy_progress_mid", progress_file)
    window.setProperty("skippy_minimal_plate", plate)
    window.setProperty("skippy_mock_focus_slice", "true" if sliced else "false")
    window.setProperty("skippy_combined_fill", focus_file)
    window.setProperty("skippy_combined", "true" if combined else "false")
    window.setProperty("skippy_combined_slice", "true" if sliced else "false")

    show_narrow = (not minimal_mode) and (not hide_close) and (not combined)
    show_wide = (not minimal_mode) and hide_close and show_frame and (not combined)
    window.setProperty("skippy_mock_focus_narrow", "true" if show_narrow else "false")
    window.setProperty("skippy_mock_focus_wide", "true" if show_wide else "false")

    def _filename_image(cid, filename, visible=True):
        ctrl = _safe_control(window, cid)
        if not ctrl:
            return
        try:
            if filename and filename != "-":
                ctrl.setImage(filename)
        except Exception:
            pass
        try:
            ctrl.setVisible(bool(visible) and bool(filename) and filename != "-")
        except Exception:
            pass

    if minimal_mode:
        _filename_image(5021, plate, True)
        _filename_image(5040, plate, True)
        _filename_image(3040, focus_file, False)
        _filename_image(3041, focus_file, False)
        _filename_image(3042, focus_file, False)
        _filename_image(3043, focus_file, False)
        _filename_image(3031, progress_file, False)
        _filename_image(COMBINED_TRACK_ID, focus_file, False)
        _filename_image(COMBINED_TRACK_SLICE_ID, focus_file, False)
        _filename_image(COMBINED_FILL_STRETCH_ID, focus_file, False)
        _filename_image(COMBINED_FILL_SLICE_ID, focus_file, False)
        return

    _filename_image(3040, focus_file, show_narrow and not sliced)
    _filename_image(3041, focus_file, show_wide and not sliced)
    _filename_image(3042, focus_file, show_narrow and sliced)
    _filename_image(3043, focus_file, show_wide and sliced)
    _filename_image(COMBINED_TRACK_ID, focus_file, combined and not sliced)
    _filename_image(COMBINED_TRACK_SLICE_ID, focus_file, combined and sliced)
    if combined:
        for cid in (COMBINED_TRACK_ID, COMBINED_TRACK_SLICE_ID):
            track = _safe_control(window, cid)
            if track:
                try:
                    track.setColorDiffuse("66FFFFFF")
                except Exception:
                    pass
    _filename_image(COMBINED_FILL_STRETCH_ID, focus_file, combined and not sliced)
    _filename_image(COMBINED_FILL_SLICE_ID, focus_file, combined and sliced)
    show_progress = settings.get_bool("show_progress_bar", False) and not combined
    # Image fill so progress_bar_style is visible without patching SkipDialog XML.
    if show_progress:
        window.setProperty(SMOOTH_BAR_WINDOW_PROP, "true")
        prog = _safe_control(window, 3014)
        if prog:
            try:
                prog.setVisible(False)
            except Exception:
                pass
        _filename_image(3030, "progress_background.png", True)
        _filename_image(3031, progress_file, True)
    else:
        window.setProperty(SMOOTH_BAR_WINDOW_PROP, "false")
        _filename_image(3030, "progress_background.png", False)
        _filename_image(3031, progress_file, False)
