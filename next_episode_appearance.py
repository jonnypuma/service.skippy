# -*- coding: utf-8 -*-
"""Settings, draft handling and layout maths for the next episode popup (no Kodi UI here)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from next_episode_look import KEY_LOOK, LOOK_CHOICES, LOOK_DEFAULT, LOOK_LABELS

KEY_STYLE = "next_episode_popup_style"
KEY_POSITION = "next_episode_popup_position"
KEY_THUMBNAIL = "next_episode_popup_thumbnail"
KEY_COUNTDOWN = "next_episode_popup_countdown"
KEY_PROGRESS = "next_episode_popup_progress"
KEY_FOCUS = "next_episode_popup_focus"

STYLE_CUSTOM = "Custom"
STYLE_NATIVE = "Native"
STYLES = (STYLE_CUSTOM, STYLE_NATIVE)
STYLE_LABELS = {STYLE_CUSTOM: "Custom", STYLE_NATIVE: "Native toast"}

POSITIONS = ("BottomRight", "TopRight", "TopLeft", "BottomLeft")
POSITION_LABELS = {
    "BottomRight": "Bottom Right",
    "TopRight": "Top Right",
    "TopLeft": "Top Left",
    "BottomLeft": "Bottom Left",
}

FOCUS_PLAY = "Play"
FOCUS_CLOSE = "Close"
FOCUS_CHOICES = (FOCUS_PLAY, FOCUS_CLOSE)
FOCUS_LABELS = {FOCUS_PLAY: "Play now", FOCUS_CLOSE: "Close"}

DEFAULT_DRAFT = {
    KEY_STYLE: STYLE_CUSTOM,
    KEY_LOOK: LOOK_DEFAULT,
    KEY_POSITION: "BottomRight",
    KEY_THUMBNAIL: True,
    KEY_COUNTDOWN: True,
    KEY_PROGRESS: True,
    KEY_FOCUS: FOCUS_PLAY,
}
BOOL_KEYS = (KEY_THUMBNAIL, KEY_COUNTDOWN, KEY_PROGRESS)
CHOICE_KEYS = {
    KEY_STYLE: STYLES,
    KEY_LOOK: LOOK_CHOICES,
    KEY_POSITION: POSITIONS,
    KEY_FOCUS: FOCUS_CHOICES,
}

# --- layout in 720p units (the skin folder scales them by 1.5 for 1080i) ---
PANEL_W = 520
PAD = 10
THUMB_W = 120
THUMB_H = 68
TEXT_GAP = 10
HEADING_H = 24
EPISODE_H = 52  # two lines of the episode font; longer titles wrap, they are never cut
COUNTDOWN_H = 20
BAR_H = 10
BUTTON_H = 34
BUTTON_GAP = 10
ROW_GAP = 4
SCREEN_MARGIN_X = 20
SCREEN_MARGIN_Y = 20
BASE_SCREEN_W = 1280
BASE_SCREEN_H = 720


@dataclass(frozen=True)
class PopupLayout:
    panel_w: int
    panel_h: int
    thumbnail: bool
    text_x: int
    text_w: int
    heading_y: int
    episode_y: int
    countdown_y: Optional[int]
    bar_y: Optional[int]
    buttons_y: int
    button_w: int
    bar_w: int


def popup_layout(*, thumbnail: bool, countdown: bool, progress: bool) -> PopupLayout:
    """Row positions: hidden rows leave no gap, the panel shrinks to fit."""
    text_x = PAD + (THUMB_W + TEXT_GAP if thumbnail else 0)
    text_w = PANEL_W - PAD - text_x
    heading_y = PAD
    episode_y = heading_y + HEADING_H + ROW_GAP
    y = episode_y + EPISODE_H + ROW_GAP
    if thumbnail:
        y = max(y, PAD + THUMB_H + ROW_GAP)
    countdown_y = None
    bar_y = None
    if countdown:
        countdown_y = y
        y += COUNTDOWN_H + ROW_GAP
    if progress:
        bar_y = y
        y += BAR_H + ROW_GAP + 2
    buttons_y = y + ROW_GAP
    return PopupLayout(
        panel_w=PANEL_W,
        panel_h=buttons_y + BUTTON_H + PAD,
        thumbnail=thumbnail,
        text_x=text_x,
        text_w=text_w,
        heading_y=heading_y,
        episode_y=episode_y,
        countdown_y=countdown_y,
        bar_y=bar_y,
        buttons_y=buttons_y,
        button_w=(PANEL_W - 2 * PAD - BUTTON_GAP) // 2,
        bar_w=PANEL_W - 2 * PAD,
    )


def popup_origin(
    position,
    panel_w=PANEL_W,
    panel_h=0,
    screen_w=BASE_SCREEN_W,
    screen_h=BASE_SCREEN_H,
    margin_x=SCREEN_MARGIN_X,
    margin_y=SCREEN_MARGIN_Y,
):
    """Top-left corner ``(x, y)`` of the panel for a stored position value."""
    position = normalize_choice(KEY_POSITION, position)
    right = max(margin_x, int(screen_w) - int(panel_w) - margin_x)
    bottom = max(margin_y, int(screen_h) - int(panel_h) - margin_y)
    x = margin_x if position.endswith("Left") else right
    y = margin_y if position.startswith("Top") else bottom
    return x, y


# --- draft handling (used by the Customize modal and the dialog) ---


def normalize_choice(key, value):
    """A stored choice, or the default when the stored text is not one of the options."""
    options = CHOICE_KEYS[key]
    text = str(value or "").replace(" ", "").strip()
    for option in options:
        if option.lower() == text.lower():
            return option
    return DEFAULT_DRAFT[key]


def draft_from_reader(get_text, get_bool) -> dict:
    """Build a draft from two callables ``get_text(key, default)`` and ``get_bool``."""
    draft = {}
    for key, default in DEFAULT_DRAFT.items():
        if key in BOOL_KEYS:
            draft[key] = bool(get_bool(key, default))
        else:
            draft[key] = normalize_choice(key, get_text(key, default))
    return draft


def load_popup_draft(addon) -> dict:
    from settings_utils import addon_get_bool, addon_get_setting_text

    if not addon:
        return dict(DEFAULT_DRAFT)
    return draft_from_reader(
        lambda key, default: addon_get_setting_text(addon, key, default),
        lambda key, default: addon_get_bool(addon, key, default),
    )


def draft_setting_payload(draft) -> dict:
    """``{setting id: text}`` exactly as ``Addon.setSetting`` stores it."""
    payload = {}
    for key, default in DEFAULT_DRAFT.items():
        value = (draft or {}).get(key, default)
        if key in BOOL_KEYS:
            payload[key] = "true" if value else "false"
        else:
            payload[key] = normalize_choice(key, value)
    return payload


def cycle_choice(key, current, delta):
    options = CHOICE_KEYS[key]
    current = normalize_choice(key, current)
    return options[(options.index(current) + int(delta)) % len(options)]


def is_native_style(draft_or_value) -> bool:
    value = (
        draft_or_value.get(KEY_STYLE)
        if isinstance(draft_or_value, dict)
        else draft_or_value
    )
    return normalize_choice(KEY_STYLE, value) == STYLE_NATIVE


def customize_rows(draft) -> list:
    """Setting ids shown in the Customize modal, top to bottom, for this draft."""
    rows = [KEY_STYLE]
    if not is_native_style(draft):
        rows += [KEY_LOOK, KEY_POSITION, KEY_THUMBNAIL, KEY_COUNTDOWN, KEY_PROGRESS, KEY_FOCUS]
    return rows


# --- countdown maths ---


def seconds_left(head, total) -> float:
    try:
        return max(0.0, float(total) - float(head))
    except (TypeError, ValueError):
        return 0.0


def window_fraction_left(head, window_start, total) -> float:
    """1.0 when the window opens, 0.0 at the end; never outside 0..1."""
    try:
        span = float(total) - float(window_start)
        if span <= 0:
            return 0.0
        return min(1.0, max(0.0, (float(total) - float(head)) / span))
    except (TypeError, ValueError):
        return 0.0


# The fill is a pre-tiled texture that is cropped from the left, never stretched, so every
# segment keeps its size and the count shrinks. One segment plus its gap is this many bar
# heights, the same as the skip dialog's segmented bar (the textures are generated for it).
SEGMENT_PITCH_PER_HEIGHT = 0.8125


def segment_pitch(bar_h) -> int:
    """On-screen width (px) of one segment plus its gap for a bar of the given height."""
    return max(3, int(round(SEGMENT_PITCH_PER_HEIGHT * int(bar_h))))


def bar_fill_width(fraction, bar_w, bar_h) -> int:
    """Fill width in whole segments: the whole bar at the start of the window, none at the end."""
    pitch = segment_pitch(bar_h)
    fraction = min(1.0, max(0.0, float(fraction)))
    count = min(int(bar_w // pitch), int(round(fraction * bar_w / pitch)))
    return int(count * pitch)
