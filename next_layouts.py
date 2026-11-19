# -*- coding: utf-8 -*-
"""The layouts of the next episode popup besides the classic card.

``Card`` is the popup of every earlier version (``NextEpisodeDialog.xml``, its looks, its Customize
screen). Every other layout is a skin file of its own, ``NextLayout_<name>.xml``, written by
``tools/gen_next_layouts.py`` and run by ``next_layout_dialog.py``. Like the skip dialog layouts
(``skip_layouts.py``) a file holds no text, colour or picture of its own; the six looks, their
pictures and the placement rules are the ones of ``skip_layouts.py``.

Everything here is in 720p units and needs no Kodi.
"""

from __future__ import annotations

from dataclasses import dataclass

import skip_layouts as sl

KEY_LAYOUT = "next_episode_popup_layout"
KEY_LAYOUT_LOOK = "next_episode_popup_layout_look"

LAYOUT_CARD = "Card"
LAYOUT_TAKE_VIDEO = "TakeVideo"
# (stored value, name shown)
LAYOUT_NAMES = (
    # the popup of every earlier version, with its own looks and options: it stays the default
    (LAYOUT_CARD, "Card (legacy)"),
    # the designs of the mockups, drawn by Skippy (next_canvas.py): Full, Compact and Minimal each
    ("CardA", "Card"),
    ("Slab", "Poster slab"),
    ("Ring", "Play ring"),
    ("Band", "Lower third"),
    ("Float", "Float"),
    ("Takeover", "Takeover"),  # the next episode takes the whole screen
    # Takeover with what is playing small at the top right. Kodi draws a video small only
    # while its full-screen video window is not the active one, so a plain window is opened under the popup.
    (LAYOUT_TAKE_VIDEO, "Takeover + video"),
    ("Queue", "Queue"),  # the next three episodes side by side
    ("Rail", "Side rail"),
    ("Poster", "Poster card"),  # the Card with the show's poster for its picture
)
# the layouts Skippy draws itself: every one but the popup of earlier versions
DRAWN_LAYOUTS = ("CardA", "Slab", "Ring", "Band", "Float", "Takeover", LAYOUT_TAKE_VIDEO, "Queue", "Rail", "Poster")
LAYOUTS = tuple(stored for stored, _name in LAYOUT_NAMES)
NEW_LAYOUTS = LAYOUTS[1:]
# What a new installation shows: the drawn Card in Fused Glass Dark (the user's choice, 2026-11-19).
# A text that is no layout at all still reads as the popup of earlier versions (normalize_layout).
DEFAULT_LAYOUT = "CardA"
DEFAULT_LOOK = sl.DEFAULT_SKIP_LOOK
# popup layouts whose texts and buttons sit straight on the video
BARE_LAYOUTS = ("Ring", "Band", "Float", "Takeover", LAYOUT_TAKE_VIDEO)

# Control ids shared by every layout file.
ID_ROOT = 5200
ID_PROBE = 5290  # an unseen image as wide as the classic popup, so the skin folder can be told apart
ID_PLAY = 5210
ID_CLOSE = 5220
ID_BAR_FILL = 5231
ID_RING = 5240
PROBE_W = 520

PICTURE_WIDE = "wide"  # the episode picture, else the fanart
PICTURE_POSTER = "poster"  # the poster, else the episode picture
PICTURE_NONE = ""
PICTURE_BACKDROP = "backdrop"  # the fanart, else the episode picture, else the poster

# Queue: the episodes that follow, as cards. The first card is the Play button of the other layouts.
QUEUE_SIZE = 3
QUEUE_IDS = (ID_PLAY, 5252, 5253)
QUEUE_CARD_W, QUEUE_CARD_H, QUEUE_GAP, QUEUE_LEFT, QUEUE_TOP = 200, 112, 16, 16, 40


def queue_left(index) -> int:
    return QUEUE_LEFT + int(index) * (QUEUE_CARD_W + QUEUE_GAP)


@dataclass(frozen=True)
class Layout:
    """One skin file. ``track`` is where the progress is drawn: left, top, width, height."""

    name: str
    width: int
    height: int
    anchor: str
    progress: str
    track: tuple
    picture: str

    @property
    def xml(self) -> str:
        return "NextLayout_%s.xml" % self.name


_ALL = (
    Layout("Poster", 520, 150, sl.ANCHOR_CORNER, sl.PROGRESS_LINE, (116, 100, 388, 4), PICTURE_POSTER),
    Layout("Slab", 420, 216, sl.ANCHOR_FLUSH, sl.PROGRESS_LINE, (0, 0, 420, 4), PICTURE_WIDE),
    Layout("Ring", 480, 164, sl.ANCHOR_CORNER, sl.PROGRESS_RING, (78, 37, 56, 56), PICTURE_WIDE),
    Layout("Band", 1280, 150, sl.ANCHOR_BAND, sl.PROGRESS_LINE, (48, 128, 1184, 3), PICTURE_WIDE),
    Layout("Float", 470, 150, sl.ANCHOR_CORNER, sl.PROGRESS_RING, (280, 113, 22, 22), PICTURE_NONE),
    Layout("Rail", 184, 296, sl.ANCHOR_EDGE, sl.PROGRESS_LINE, (16, 208, 152, 3), PICTURE_WIDE),
    Layout("Takeover", 1280, 720, sl.ANCHOR_BAND, sl.PROGRESS_LINE, (64, 648, 560, 4), PICTURE_BACKDROP),
    Layout("Queue", 664, 244, sl.ANCHOR_CENTER, sl.PROGRESS_LINE, (16, 190, 632, 3), PICTURE_NONE),
)
_BY_NAME = {item.name: item for item in _ALL}


def all_layouts() -> tuple:
    return _ALL


def normalize_layout(value) -> str:
    """A stored layout, or ``Card`` when the text is not one of them."""
    text = "".join(str(value or "").split()).lower()
    for stored, name in LAYOUT_NAMES:
        if text in (stored.lower(), "".join(name.split()).lower()):
            return stored
    return LAYOUT_CARD


def is_card(layout) -> bool:
    return normalize_layout(layout) == LAYOUT_CARD


def is_drawn(layout) -> bool:
    return normalize_layout(layout) in DRAWN_LAYOUTS


def get(layout) -> Layout:
    """The file of a layout (``Card`` and a drawn layout that never had one raise ``KeyError``)."""
    return _BY_NAME[normalize_layout(layout)]


def layout_options() -> list:
    return [(name, stored) for stored, name in LAYOUT_NAMES]


def look_options() -> list:
    return sl.look_options()


def origin(layout: Layout, position) -> tuple:
    """Left and top on the 720p canvas for a stored corner: the rules of the skip dialog layouts."""
    return sl.origin(layout, position)


def fill_width(layout: Layout, percent) -> int:
    """Width of the line for a percentage of the countdown that is left."""
    share = max(0.0, min(100.0, float(percent))) / 100.0
    return int(round(layout.track[2] * share))


def picture(layout: Layout, episode) -> str:
    """The picture a layout shows for an episode, with its fallbacks ("" when there is none)."""
    episode = episode or {}
    wide = episode.get("thumb") or episode.get("fanart") or ""
    if layout.picture == PICTURE_POSTER:
        return episode.get("poster") or wide
    if layout.picture == PICTURE_BACKDROP:
        return episode.get("fanart") or episode.get("thumb") or episode.get("poster") or ""
    if layout.picture == PICTURE_WIDE:
        return wide or episode.get("poster") or ""
    return ""
