# -*- coding: utf-8 -*-
"""Settings, draft handling and layout maths for the next episode popup (no Kodi UI here)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from next_episode_look import (
    FOLLOW_LOOK,
    KEY_ALL_CAPS,
    KEY_BAR_STYLE,
    KEY_CARD_OPACITY,
    KEY_FOCUS_STYLE,
    KEY_HEADING_COLOR,
    KEY_LOOK,
    KEY_TEXT_COLOR,
    LOOK_CHOICES,
    LOOK_DEFAULT,
    OVERRIDE_KEYS,
    override_options,
)

import next_layouts
import skip_layouts

KEY_STYLE = "next_episode_popup_style"
KEY_LAYOUT = next_layouts.KEY_LAYOUT
KEY_LAYOUT_LOOK = next_layouts.KEY_LAYOUT_LOOK
KEY_POSITION = "next_episode_popup_position"
KEY_THUMBNAIL = "next_episode_popup_thumbnail"
KEY_COUNTDOWN = "next_episode_popup_countdown"
KEY_PROGRESS = "next_episode_popup_progress"
KEY_FOCUS = "next_episode_popup_focus"
KEY_SIZE = "next_episode_popup_size"
KEY_PICTURE = "next_episode_popup_picture"
# a drawn layout (next_canvas.py): its form and its size on screen; and the row that steps through
# every drawn design in every look (it is not stored: it sets the layout and the look)
KEY_FORM = "next_canvas_form"
KEY_ZOOM = "next_canvas_zoom"
KEY_PRESET = "next_canvas_preset"
FORMS = ("Full", "Compact", "Minimal")
ZOOMS = ("70", "85", "100")  # Small, Medium, Large

# Which picture the popup shows while "Show episode picture" is on.
PICTURE_EPISODE = "Episode"  # the wide picture of the episode (the default, as before)
PICTURE_POSTER = "Poster"  # the poster of the show (or of the film)
PICTURE_BOTH = "Both"  # the poster and the episode picture side by side, at one height
PICTURE_FANART = "Fanart"  # the fanart behind the whole popup
PICTURE_FANART_POSTER = "FanartPoster"  # the fanart behind the popup, the poster at the left
PICTURE_FANART_EPISODE = "FanartEpisode"  # the fanart behind the popup, the episode picture at the left
PICTURES = (PICTURE_EPISODE, PICTURE_POSTER, PICTURE_BOTH, PICTURE_FANART, PICTURE_FANART_POSTER, PICTURE_FANART_EPISODE)
FANART_PICTURES = (PICTURE_FANART, PICTURE_FANART_POSTER, PICTURE_FANART_EPISODE)
PICTURE_LABEL_IDS = {
    PICTURE_EPISODE: (49036, "Episode picture"),
    PICTURE_POSTER: (49037, "Poster"),
    PICTURE_BOTH: (49038, "Poster and episode"),
    PICTURE_FANART: (49039, "Fanart"),
    PICTURE_FANART_POSTER: (49048, "Fanart and poster"),
    PICTURE_FANART_EPISODE: (49049, "Fanart and episode"),
}

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

SIZE_NORMAL = "Normal"
SIZE_LARGE = "Large"
SIZES = (SIZE_NORMAL, SIZE_LARGE)
# Large shows the whole popup (text included) this many percent of its normal size, grown from
# the corner it sits in. The skin does it with a zoom effect (NextEpisodeDialog.xml and the
# mockup in NextEpisodeCustomize.xml), so the layout below stays the same for both sizes.
LARGE_ZOOM_PERCENT = 125

FOCUS_PLAY = "Play"
FOCUS_CLOSE = "Close"
FOCUS_CHOICES = (FOCUS_PLAY, FOCUS_CLOSE)
FOCUS_LABELS = {FOCUS_PLAY: "Play now", FOCUS_CLOSE: "Close"}

DEFAULT_DRAFT = {
    KEY_STYLE: STYLE_CUSTOM,
    KEY_LAYOUT: next_layouts.DEFAULT_LAYOUT,
    KEY_LAYOUT_LOOK: next_layouts.DEFAULT_LOOK,
    KEY_FORM: FORMS[0],
    KEY_ZOOM: ZOOMS[-1],
    KEY_LOOK: LOOK_DEFAULT,
    KEY_TEXT_COLOR: FOLLOW_LOOK,
    KEY_HEADING_COLOR: FOLLOW_LOOK,
    KEY_ALL_CAPS: FOLLOW_LOOK,
    KEY_FOCUS_STYLE: FOLLOW_LOOK,
    KEY_BAR_STYLE: FOLLOW_LOOK,
    KEY_CARD_OPACITY: FOLLOW_LOOK,
    KEY_POSITION: "BottomRight",
    KEY_SIZE: SIZE_NORMAL,
    KEY_THUMBNAIL: True,
    KEY_PICTURE: PICTURE_EPISODE,
    KEY_COUNTDOWN: True,
    KEY_PROGRESS: True,
    KEY_FOCUS: FOCUS_PLAY,
}
BOOL_KEYS = (KEY_THUMBNAIL, KEY_COUNTDOWN, KEY_PROGRESS)
CHOICE_KEYS = {
    KEY_STYLE: STYLES,
    KEY_LOOK: LOOK_CHOICES,
    KEY_POSITION: POSITIONS,
    KEY_SIZE: SIZES,
    KEY_LAYOUT: next_layouts.LAYOUTS,
    KEY_LAYOUT_LOOK: skip_layouts.LOOKS,
    KEY_FORM: FORMS,
    KEY_ZOOM: ZOOMS,
    KEY_PICTURE: PICTURES,
    KEY_FOCUS: FOCUS_CHOICES,
}
# The user's own choices on top of the look: each is "Same as look" or one stored value.
CHOICE_KEYS.update({key: override_options(key) for key in OVERRIDE_KEYS})

# --- layout in 720p units (the skin folder scales them by 1.5 for 1080i) ---
PANEL_W = 520
PAD = 10
THUMB_W = 120
THUMB_H = 68
POSTER_W, POSTER_H = 76, 114  # the poster instead of the episode picture
# Poster and episode: both at one height, the poster first
PAIR_H = 90
PAIR_POSTER_W = 60  # 2:3
PAIR_THUMB_W = 160  # 16:9
PAIR_GAP = 8
PAIR_W = PAIR_POSTER_W + PAIR_GAP + PAIR_THUMB_W
FANART_INSET = 6  # the fanart keeps this far inside the card, clear of its corners
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
    thumbnail: bool  # a picture stands at the left of the text
    text_x: int
    text_w: int
    heading_y: int
    episode_y: int
    countdown_y: Optional[int]
    bar_y: Optional[int]
    buttons_y: int
    button_w: int
    bar_w: int
    picture: str = ""  # PICTURE_* that is drawn, or "" for none
    thumb_w: int = THUMB_W
    thumb_h: int = THUMB_H
    picture_y: int = PAD  # top of the picture(s): centred against the rows beside them
    fanart: bool = False  # the fanart lies behind the popup
    pair: bool = False  # poster and episode picture side by side


def popup_layout(*, thumbnail: bool, countdown: bool, progress: bool, picture: str = PICTURE_EPISODE) -> PopupLayout:
    """Row positions: hidden rows leave no gap, the panel shrinks to fit.

    ``thumbnail`` says a picture is shown at all; ``picture`` which one. Fanart lies behind the
    popup, so the text then starts at the left edge.
    """
    picture = picture if (thumbnail and picture in PICTURES) else (PICTURE_EPISODE if thumbnail else "")
    pair = picture == PICTURE_BOTH
    if picture in (PICTURE_POSTER, PICTURE_FANART_POSTER):
        thumb_w, thumb_h = POSTER_W, POSTER_H
    elif pair:
        thumb_w, thumb_h = PAIR_W, PAIR_H
    else:
        thumb_w, thumb_h = THUMB_W, THUMB_H
    fanart = picture in FANART_PICTURES
    thumbnail = thumbnail and picture != PICTURE_FANART
    text_x = PAD + (thumb_w + TEXT_GAP if thumbnail else 0)
    text_w = PANEL_W - PAD - text_x
    heading_y = PAD
    episode_y = heading_y + HEADING_H + ROW_GAP
    y = episode_y + EPISODE_H + ROW_GAP
    picture_y = PAD
    if thumbnail:
        if pair:
            # the pair stands centred against the two text rows beside it
            picture_y = PAD + max(0, (y - ROW_GAP - PAD - thumb_h) // 2)
        y = max(y, PAD + thumb_h + ROW_GAP)
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
        picture=picture,
        thumb_w=thumb_w,
        thumb_h=thumb_h,
        picture_y=picture_y,
        fanart=fanart,
        pair=pair,
    )


def picture_plan(draft, episode) -> dict:
    """What to draw for the picture choice of ``draft`` with the art ``episode`` has.

    ``picture`` is the PICTURE_* that can be drawn ("" for none); ``thumb`` goes in the picture box,
    ``fanart`` behind the popup; ``pair_poster`` and ``pair_thumb`` are the two pictures of Poster and
    episode. A choice whose art is missing falls back to the nearest one that can be drawn, in the
    end to the episode picture, and to nothing when that is missing too.
    """
    episode = episode or {}
    none = {"picture": "", "thumb": "", "pair_poster": "", "pair_thumb": "", "fanart": ""}
    if not (draft or {}).get(KEY_THUMBNAIL):
        return none
    wide, poster = episode.get("thumb") or "", episode.get("poster") or ""
    fanart = episode.get("fanart") or wide
    wanted = normalize_choice(KEY_PICTURE, (draft or {}).get(KEY_PICTURE, PICTURE_EPISODE))
    backdrop = episode.get("fanart") or ""  # with a picture in front only real fanart will do
    if wanted == PICTURE_FANART_POSTER and poster:
        if backdrop:
            return dict(none, picture=PICTURE_FANART_POSTER, thumb=poster, fanart=backdrop)
        wanted = PICTURE_POSTER
    if wanted == PICTURE_FANART_EPISODE and wide and backdrop and backdrop != wide:
        return dict(none, picture=PICTURE_FANART_EPISODE, thumb=wide, fanart=backdrop)
    if wanted == PICTURE_POSTER and poster:
        return dict(none, picture=PICTURE_POSTER, thumb=poster)
    if wanted == PICTURE_BOTH and wide and poster:
        return dict(none, picture=PICTURE_BOTH, pair_poster=poster, pair_thumb=wide)
    if wanted == PICTURE_FANART and fanart:
        return dict(none, picture=PICTURE_FANART, fanart=fanart)
    if wide:
        return dict(none, picture=PICTURE_EPISODE, thumb=wide)
    return none


PICTURE_OFF = "Off"
PICTURE_ROW_CHOICES = (PICTURE_OFF,) + PICTURES


def picture_choice(draft) -> str:
    """What the picture row of the Customize screen shows: ``Off`` or the PICTURE_* in use."""
    if not (draft or {}).get(KEY_THUMBNAIL):
        return PICTURE_OFF
    return normalize_choice(KEY_PICTURE, (draft or {}).get(KEY_PICTURE, PICTURE_EPISODE))


def cycle_picture(draft, delta) -> None:
    """Step the picture row: Off, Episode picture, Poster, Poster and episode, Fanart, Fanart and
    poster, Fanart and episode. Switching the picture off keeps the kind for next time."""
    choices = PICTURE_ROW_CHOICES
    chosen = choices[(choices.index(picture_choice(draft)) + int(delta)) % len(choices)]
    if chosen == PICTURE_OFF:
        draft[KEY_THUMBNAIL] = False
        return
    draft[KEY_THUMBNAIL] = True
    draft[KEY_PICTURE] = chosen


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


def zoom_corner(draft_or_size, position=None) -> str:
    """The corner the skin grows the popup from, or ``""`` for the normal size.

    The skin shows the zoom of the matching corner name (``next_ep_zoom`` property), so the
    popup grows toward the middle of the screen and its margin to the edges stays the same.
    """
    if isinstance(draft_or_size, dict):
        size = draft_or_size.get(KEY_SIZE)
        position = draft_or_size.get(KEY_POSITION) if position is None else position
    else:
        size = draft_or_size
    if normalize_choice(KEY_SIZE, size) != SIZE_LARGE:
        return ""
    return normalize_choice(KEY_POSITION, position)


def zoom_center(position, screen_w=BASE_SCREEN_W, screen_h=BASE_SCREEN_H, margin_x=SCREEN_MARGIN_X, margin_y=SCREEN_MARGIN_Y):
    """``(x, y)`` of the corner of a popup in ``position``, which the zoom keeps in place."""
    position = normalize_choice(KEY_POSITION, position)
    x = margin_x if position.endswith("Left") else int(screen_w) - margin_x
    y = margin_y if position.startswith("Top") else int(screen_h) - margin_y
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
    layout = (draft or {}).get(KEY_LAYOUT)
    if not is_native_style(draft) and next_layouts.is_drawn(layout):
        # A design Skippy draws: the preset (every design in every look), then the two it is made of, its
        # form, its size on screen, where it sits and which button has the focus.
        return rows + [KEY_PRESET, KEY_LAYOUT, KEY_LAYOUT_LOOK, KEY_FORM, KEY_ZOOM, KEY_POSITION, KEY_FOCUS]
    if not is_native_style(draft) and not next_layouts.is_card(layout):
        # A layout that is a skin file: its look, where it sits and which button has the focus. The rows of
        # the card (Popup look, the colours, the size, the picture) do not apply to it.
        return rows + [KEY_PRESET, KEY_LAYOUT, KEY_LAYOUT_LOOK, KEY_POSITION, KEY_FOCUS]
    if not is_native_style(draft):
        # the popup of earlier versions: Popup layout leads to the drawn designs and their presets
        rows.append(KEY_LAYOUT)
        # The look, then what can be changed on top of it, then what is shown and where.
        rows += [KEY_LOOK, KEY_TEXT_COLOR, KEY_HEADING_COLOR, KEY_ALL_CAPS, KEY_FOCUS_STYLE]
        if (draft or {}).get(KEY_PROGRESS, True):
            rows.append(KEY_BAR_STYLE)
        rows += [
            KEY_CARD_OPACITY,
            KEY_POSITION,
            KEY_SIZE,
            KEY_THUMBNAIL,
            KEY_COUNTDOWN,
            KEY_PROGRESS,
            KEY_FOCUS,
        ]
    return rows


# --- presets: every drawn design in every look, and the popup of earlier versions ---
PRESET_SEP = " · "


def presets() -> list:
    """``(layout, look)`` of every preset, in the order the Preset row steps through them. The last one
    is the popup of earlier versions (its look is ``None``: it has looks of its own)."""
    found = [(layout, look) for layout in next_layouts.DRAWN_LAYOUTS for look in skip_layouts.LOOKS]
    return found + [(next_layouts.LAYOUT_CARD, None)]


def preset_name(layout, look) -> str:
    names = dict(next_layouts.LAYOUT_NAMES)
    layout = next_layouts.normalize_layout(layout)
    if look is None or not next_layouts.is_drawn(layout):
        return names[layout]
    return "%s%s%s" % (names[layout], PRESET_SEP, dict(skip_layouts.LOOK_NAMES)[skip_layouts.normalize_look(look)])


def preset_of(draft) -> tuple:
    """The preset a draft is, or ``None`` when its layout is none of them (Poster card)."""
    layout = next_layouts.normalize_layout((draft or {}).get(KEY_LAYOUT))
    if next_layouts.is_card(layout):
        return (next_layouts.LAYOUT_CARD, None)
    if next_layouts.is_drawn(layout):
        return (layout, skip_layouts.normalize_look((draft or {}).get(KEY_LAYOUT_LOOK)))
    return None


def cycle_preset(draft, delta) -> None:
    """Step to the next (or the previous) preset: it sets the layout and, for a drawn one, the look."""
    found = presets()
    current = preset_of(draft)
    index = found.index(current) if current in found else (-1 if delta > 0 else 0)
    layout, look = found[(index + (1 if delta > 0 else -1)) % len(found)]
    draft[KEY_LAYOUT] = layout
    if look is not None:
        draft[KEY_LAYOUT_LOOK] = look


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
