# -*- coding: utf-8 -*-
"""What the next episode popup shows and where, shared by the popup and the Customize mockup.

Both windows draw the same controls from the same numbers, so the mockup in the Customize screen
is the popup itself: ``popup_ids(offset)`` names the controls (the mockup uses its own copy of them,
``MOCK_ID_OFFSET`` higher), ``popup_placements`` says where each one sits inside the panel and
``look_properties`` gives the skin properties of a look. Nothing here talks to Kodi.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from next_episode_appearance import (
    BAR_H,
    BUTTON_GAP,
    BUTTON_H,
    COUNTDOWN_H,
    EPISODE_H,
    FOCUS_CLOSE,
    HEADING_H,
    KEY_FOCUS,
    PAD,
    THUMB_H,
    THUMB_W,
    bar_fill_width,
)
from next_episode_look import resolve_popup_look
from settings_utils import addon_get_setting_text, get_localized
from skip_dialog_appearance import (
    apply_skip_dialog_caps,
    countdown_mmss,
    progress_tiled_variant,
    resolve_font_color_argb,
)

# The mockup in the Customize screen has its own copy of every popup control, this many ids higher.
MOCK_ID_OFFSET = 2000


@dataclass(frozen=True)
class PopupIds:
    panel: int
    backdrop: int
    thumb: int
    heading: int
    episode: int
    countdown: int
    bar_bg: int
    bar_fill: int  # tiled fill, cropped from the left
    bar_fill_stretch: int  # fill for bar textures that have no tiled version
    plate_play: int
    plate_close: int
    play: int
    close: int
    focus_play: Tuple[int, int, int]  # three cuts of the focus texture per button
    focus_close: Tuple[int, int, int]


def popup_ids(offset=0) -> PopupIds:
    """Control ids of the popup skin (``offset`` 0) or of the copy in the Customize mockup."""
    return PopupIds(
        panel=5000 + offset,
        backdrop=5001 + offset,
        thumb=5002 + offset,
        heading=5003 + offset,
        episode=5004 + offset,
        countdown=5005 + offset,
        bar_bg=5006 + offset,
        bar_fill=5007 + offset,
        bar_fill_stretch=5012 + offset,
        plate_play=5010 + offset,
        plate_close=5011 + offset,
        play=5008 + offset,
        close=5009 + offset,
        focus_play=(5013 + offset, 5014 + offset, 5015 + offset),
        focus_close=(5016 + offset, 5017 + offset, 5018 + offset),
    )


def popup_placements(layout, ids):
    """``[(control id, x, y, w, h)]`` in 720p units, relative to the panel, for the controls it uses.

    A hidden row (no picture, no time left, no bar) has no entry, so it leaves no gap.
    """
    out = [(ids.backdrop, 0, 0, layout.panel_w, layout.panel_h)]
    if layout.thumbnail:
        out.append((ids.thumb, PAD, PAD, THUMB_W, THUMB_H))
    out.append((ids.heading, layout.text_x, layout.heading_y, layout.text_w, HEADING_H))
    out.append((ids.episode, layout.text_x, layout.episode_y, layout.text_w, EPISODE_H))
    if layout.countdown_y is not None:
        out.append((ids.countdown, PAD, layout.countdown_y, layout.bar_w, COUNTDOWN_H))
    if layout.bar_y is not None:
        for cid in (ids.bar_bg, ids.bar_fill, ids.bar_fill_stretch):
            out.append((cid, PAD, layout.bar_y, layout.bar_w, BAR_H))
    second_x = PAD + layout.button_w + BUTTON_GAP
    for cid, x in (
        (ids.plate_play, PAD),
        (ids.play, PAD),
        (ids.plate_close, second_x),
        (ids.close, second_x),
    ):
        out.append((cid, x, layout.buttons_y, layout.button_w, BUTTON_H))
    for images, x in ((ids.focus_play, PAD), (ids.focus_close, second_x)):
        for cid in images:
            out.append((cid, x, layout.buttons_y, layout.button_w, BUTTON_H))
    return out


def skip_text_color(addon) -> str:
    """The skip dialog's font colour, which a look follows unless it has a colour of its own."""
    raw = addon_get_setting_text(addon, "skip_dialog_font_color", "FFFFFFFF") or "FFFFFFFF"
    return resolve_font_color_argb(raw.strip(), fallback="FFFFFFFF")


def look_properties(draft, addon, bar_h_px, fallback_text_color):
    """``(look, bar is tiled, {skin property: value})`` for a draft.

    ``fallback_text_color`` is used when the look follows the skip dialog's font colour;
    ``bar_h_px`` is the on-screen height of the bar, which picks the matching tiled texture.
    """
    look = resolve_popup_look(draft, addon)
    tiled = progress_tiled_variant(look.bar_texture, bar_h_px)
    text = (
        resolve_font_color_argb(look.text_color, fallback="FFFFFFFF")
        if look.text_color
        else fallback_text_color
    )
    props = {
        "skip_dialog_text_color": text,
        "next_ep_card_color": look.card_color,
        "next_ep_heading_color": look.heading_color,
        "next_ep_focus_texture": look.focus_texture,
        "next_ep_focus_border": look.focus_border,
        "next_ep_bar_tiled": "true" if tiled else "false",
        "next_ep_bar_tiled_texture": tiled or "",
        "next_ep_bar_texture": look.bar_texture,
    }
    return look, bool(tiled), props


def popup_texts(addon, caps_on, next_episode, *, still_watching=False) -> dict:
    """Heading, episode line and the two button labels, already upper-cased when the look says so."""
    from next_episode_lookup import episode_label

    def caps(text):
        return apply_skip_dialog_caps(text, bool(caps_on))

    if still_watching:
        heading = get_localized(addon, 47070, "Still watching?")
        play = get_localized(addon, 47071, "Continue")
        close = get_localized(addon, 47072, "Stop")
    else:
        heading = get_localized(addon, 47020, "Play next episode?")
        play = get_localized(addon, 47050, "Play now")
        close = get_localized(addon, 40001, "Close")
    return {
        "heading": caps(heading),
        "label": caps(episode_label(next_episode)),
        "play": caps(play),
        "close": caps(close),
    }


def countdown_text(addon, caps_on, seconds) -> str:
    """``Episode ends in 00:42``."""
    return apply_skip_dialog_caps(
        get_localized(addon, 47051, "Episode ends in %s", countdown_mmss(seconds)), bool(caps_on)
    )


def fill_width(tiled, fraction, bar_w_px, bar_h_px) -> int:
    """Width in pixels of the filled part of the bar.

    A tiled bar is cropped to whole segments (none is squeezed); any other texture is stretched.
    """
    if tiled:
        return bar_fill_width(fraction, bar_w_px, bar_h_px)
    return int(round(min(1.0, max(0.0, float(fraction))) * bar_w_px))


def focus_is_close(draft) -> bool:
    """Whether the Close button is the one that starts with focus."""
    return (draft or {}).get(KEY_FOCUS) == FOCUS_CLOSE
