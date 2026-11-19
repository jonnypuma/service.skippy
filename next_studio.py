# -*- coding: utf-8 -*-
"""The Studio of the Up Next popup: its tabs, its rows and its draft (no Kodi needed).

It is the screen of the round-3 mockup (board CN3): Look, Layout, Picture, Buttons, Motion and
Autoplay, on the frame of the skip dialog's Studio (``skip_studio.py``, ``SkipStudio.xml``). A row is
a setting: the draft holds the stored text of each, and Save writes the ones that changed.

A row of the mockup that has no function yet is listed all the same, dimmed, and says so: nothing
is hidden.
"""

from __future__ import annotations

from collections import namedtuple

import next_canvas as nc
import next_episode_appearance as app
import next_layouts as nl
import skip_canvas as cv
import skip_layouts as sl

TABS = ("look", "layout", "picture", "buttons", "motion", "autoplay")
TAB_LABELS = ((49020, "Look"), (49021, "Layout"), (49035, "Picture"), (49023, "Buttons"), (49126, "Motion"), (49200, "Autoplay"))

P = nc.PREFIX
KEY_PRESET = app.KEY_PRESET
KEY_LEGACY = "next_studio_legacy"  # the row that opens the options of the popup of earlier versions

# kinds: preset, seg (choices side by side), pick (step through), toggle, slider, pos (nine places), swatch
# (accent colours), action (OK does something), soon (in the mockup, not built yet)
Row = namedtuple("Row", "key kind name choices about low high")


def row(key, kind, name, choices=(), about=None, low=0, high=0) -> Row:
    return Row(key, kind, name, tuple(choices), about, low, high)


YES_NO = (("true", 44105, "Yes"), ("false", 44106, "No"))
FORMS = (("Full", 30116, "Full"), ("Compact", 49199, "Compact"), ("Minimal", 30117, "Minimal"))
CORNERS = (("Skin", 49149, "Skin"), ("Hard", 49075, "Hard"), ("Rounded", 49076, "Rounded"))
ZOOMS = (("70", 49095, "Small"), ("85", 49090, "Medium"), ("100", 49097, "Large"))
PROGRESS = (("Auto", 49113, "Line"), ("Off", 49088, "Off"))
FOCUS = ((app.FOCUS_PLAY, 47050, "Play now"), (app.FOCUS_CLOSE, 35019, "Cancel"))
END_ACTIONS = (("Play", 47050, "Play now"), ("Close", 40001, "Close"))
ACCENTS = ("Auto", "Gold", "Blue", "Red", "Green", "Teal", "Purple", "White")
PICTURES = (("Episode", 49036, "Episode picture"), ("Poster", 49037, "Poster"), ("Both", 49038, "Poster and episode"),
            ("Fanart", 49039, "Fanart"), ("Off", 49088, "Off"))
PROGRESS4 = (("Line", 49113, "Line"), ("Circle", 49114, "Circle"), ("Fill", 49115, "Fill"), ("Off", 49088, "Off"))
FILL_ON = (("Button", 49221, "Button"), ("Card", 49222, "Card"), ("Picture", 49035, "Picture"))
FALLBACKS = (("Fanart", 49039, "Fanart"), ("Poster", 49037, "Poster"), ("Nothing", 49223, "Nothing"))
CAPS = (("Look", 49020, "Look"), ("On", 44105, "Yes"), ("Off", 44106, "No"))
BARS = (("Smooth", 49219, "Smooth"), ("Steps", 49220, "Steps"))
FOCUS_STYLES = (("Look", 49020, "Look"), ("Accent", 49225, "Accent"), ("Outline", 49226, "Outline"))
# Skippy's own popup, or Kodi's small notification (then nothing of the look applies)
STYLES = ((app.STYLE_CUSTOM, 0, "Custom"), (app.STYLE_NATIVE, 0, "Native toast"))

TAB_ROWS = (
    # Look
    (
        row(app.KEY_STYLE, "seg", (47030, "Popup style"), STYLES),
        row(KEY_PRESET, "preset", (46015, "Preset")),
        row(app.KEY_LAYOUT_LOOK, "pick", (49012, "Layout look")),
        row(P + "form", "seg", (49152, "Size"), FORMS),
        row(P + "corners", "seg", (49072, "Corners"), CORNERS),
        row(P + "overlay", "pick", (49050, "Background overlay"), sl.OVERLAY_NAMES),
        row(P + "overlay_gradient", "toggle", (49116, "Overlay gradient")),
        row(app.KEY_PROGRESS, "seg", (49154, "Progress"), PROGRESS4),
        row(P + "fill_on", "seg", (49207, "Fill shows on"), FILL_ON),
        row(P + "accent", "swatch", (49101, "Accent colour")),
        row(P + "same_look", "toggle", (49206, "Same look as the skip dialog")),
        row(P + "follow_skin", "toggle", (49208, "Follow the skin style")),
        row(KEY_LEGACY, "action", (49205, "Options of Card (legacy)…")),
    ),
    # Layout
    (
        row(app.KEY_LAYOUT, "pick", (49150, "Design")),
        row(P + "place", "pos", (49151, "Position")),
        row(P + "distance", "slider", (49129, "Distance from the edge"), low=0, high=160),
        row(P + "zoom", "seg", (49099, "Size on screen"), ZOOMS),
        row(P + "subtitles", "toggle", (49209, "Keep clear of subtitles")),
    ),
    # Picture
    (
        row(P + "picture", "pick", (49035, "Picture"), PICTURES),
        row(P + "fallback", "pick", (49210, "When there is no episode picture"), FALLBACKS),
        row(P + "plot", "toggle", (49201, "Plot")),
        row(P + "kicker", "toggle", (49202, "Episode line")),
        row(P + "time", "toggle", (49211, "Time left")),
        row(P + "logo", "toggle", (49203, "Show logo")),
        row(P + "caps", "seg", (49212, "All capitals"), CAPS),
    ),
    # Buttons
    (
        row(app.KEY_FOCUS, "seg", (49130, "Button the focus starts on"), FOCUS),
        row(P + "close", "toggle", (49204, "Cancel button")),
        row(P + "credits", "toggle", (49213, "Watch credits button")),
        row(P + "icons", "toggle", (49079, "Icons on the buttons")),
        row(P + "focus_style", "seg", (49214, "Focus style"), FOCUS_STYLES),
    ),
    # Motion
    (
        row(P + "appear", "pick", (49059, "Appears"), sl.APPEAR_NAMES),
        row(P + "leave", "pick", (49065, "Leaves"), sl.LEAVE_NAMES),
        row(P + "bar", "seg", (49215, "Bar"), BARS),
        row(P + "pulse", "toggle", (49069, "Pulse in the last five seconds")),
        row(P + "speed", "slider", (49216, "Speed"), low=0, high=400),
    ),
    # Autoplay: the settings of the Up Next page, set where the popup is
    (
        row("next_episode_popup_end_action", "seg", (47120, "When the countdown ends"), END_ACTIONS),
        row("next_episode_lead_seconds", "slider", (47005, "Seconds before the end"), low=10, high=300),
        row("next_episode_start_at_credits", "toggle", (47064, "Start at the credits")),
        row("next_episode_per_show", "toggle", (47082, "Remember per show")),
        row("next_episode_still_watching", "toggle", (47060, "Ask if you are still watching")),
        row("next_episode_still_watching_after", "slider", (47062, "Episodes in a row before asking"), low=1, high=10),
        row("next_episode_resume", "toggle", (47013, "Resume a partly watched next episode")),
    ),
)
SLIDER_STEP = {P + "distance": 8, "next_episode_lead_seconds": 5, "next_episode_still_watching_after": 1, P + "speed": 20}


def progress_state(draft) -> str:
    """Which of the four Progress choices a draft has: the switch and the kind are two settings."""
    if not (draft or {}).get(app.KEY_PROGRESS, True):
        return "Off"
    kind = str((draft or {}).get(P + "progress"))
    return kind if kind in ("Circle", "Fill") else "Line"


def set_progress_state(draft, state) -> None:
    draft[app.KEY_PROGRESS] = state != "Off"
    if state != "Off":
        draft[P + "progress"] = "Auto" if state == "Line" else state
# the settings of the Autoplay tab and their defaults (the texts Kodi stores)
AUTO_KEYS = {
    "next_episode_popup_end_action": "Close", "next_episode_lead_seconds": "45", "next_episode_start_at_credits": "true",
    "next_episode_per_show": "false", "next_episode_still_watching": "true", "next_episode_still_watching_after": "3",
    "next_episode_resume": "true",
}
BOOL_ROWS = frozenset(r.key for rows in TAB_ROWS for r in rows if r.kind == "toggle")
# rows of a drawn design only; with the popup of earlier versions they are dimmed
DRAWN_ONLY = frozenset(r.key for rows in TAB_ROWS[:5] for r in rows
                       if r.key.startswith(P) or r.key in (app.KEY_LAYOUT_LOOK,)) - {KEY_PRESET}
WHY = {
    "drawn": (49158, "For the drawn designs: choose a Design other than Card to use it."),
    "soon": (49160, "Not built for the drawn designs yet."),
    "other": (49163, "Not used with the choices made on this screen."),
}


def canvas_keys() -> list:
    return [P + name for name in nc.OPTION_KEYS]


def default_draft() -> dict:
    """What Reset gives: every row at its default."""
    draft = dict(app.DEFAULT_DRAFT)
    draft.update({P + name: default for name, default in nc.OPTION_KEYS.items()})
    draft.update(AUTO_KEYS)
    return draft


def load(get_text, get_bool) -> dict:
    """The draft from two readers ``get_text(key, default)`` and ``get_bool(key, default)``."""
    draft = app.draft_from_reader(get_text, get_bool)
    for name, default in nc.OPTION_KEYS.items():
        found = get_text(P + name, default)
        draft[P + name] = str(found) if found not in (None, "") else default
    for key, default in AUTO_KEYS.items():
        found = get_text(key, default)
        draft[key] = str(found) if found not in (None, "") else default
    return draft


def payload(draft) -> dict:
    """``{setting id: text}`` of everything the Studio sets."""
    out = app.draft_setting_payload(draft)
    for key in canvas_keys() + list(AUTO_KEYS):
        out[key] = str((draft or {}).get(key, ""))
    return out


def changed(draft, original) -> dict:
    new, old = payload(draft), payload(original)
    return {key: value for key, value in new.items() if old.get(key) != value}


def is_drawn(draft) -> bool:
    return nl.is_drawn((draft or {}).get(app.KEY_LAYOUT))


def yes(value) -> bool:
    return value is True or str(value).strip().lower() in ("true", "1", "yes")


def why(draft, item) -> str:
    """Why a row is dimmed for this draft ("" when it applies): a key of ``WHY``."""
    if item.kind == "soon":
        return "soon"
    drawn = is_drawn(draft)
    if app.is_native_style(draft):
        # Kodi's own notification: only the style itself and the Autoplay tab apply
        return "" if item.key == app.KEY_STYLE or item.key in AUTO_KEYS else "other"
    if item.key == KEY_LEGACY:
        return "other" if drawn else ""
    if item.key in DRAWN_ONLY and not drawn:
        return "drawn"
    if item.key == app.KEY_LAYOUT_LOOK and (yes(draft.get(P + "same_look")) or yes(draft.get(P + "follow_skin"))):
        return "other"  # the look is the skip dialog's, or the skin's
    if item.key == P + "same_look" and yes(draft.get(P + "follow_skin")):
        return "other"  # the skin's style comes first
    if item.key == P + "fill_on" and progress_state(draft) != "Fill":
        return "other"  # only a fill has a place to show on
    if item.key == P + "overlay_gradient" and str(draft.get(P + "overlay")) in ("", sl.OVERLAY_AUTO, "None"):
        return "other"
    if item.key == "next_episode_still_watching_after" and not yes(draft.get("next_episode_still_watching")):
        return "other"
    if item.key == app.KEY_FOCUS and drawn and not yes(draft.get(P + "close")):
        return "other"  # without Cancel there is one button
    return ""


def tab_rows(draft) -> list:
    """For every tab its rows as ``(row, why)``."""
    return [[(item, why(draft, item)) for item in rows] for rows in TAB_ROWS]


def find(key) -> Row:
    for rows in TAB_ROWS:
        for item in rows:
            if item.key == key:
                return item
    raise KeyError(key)


def place_of(draft) -> str:
    return cv.place_name((draft or {}).get(P + "place") or (draft or {}).get(app.KEY_POSITION))


def nearest_corner(place) -> str:
    place = cv.place_name(place)
    return ("Top" if place.startswith("Top") else "Bottom") + ("Left" if "Left" in place else "Right")


def number(draft, item) -> int:
    try:
        return int(float(draft.get(item.key)))
    except (TypeError, ValueError):
        return item.low


def step(draft, item, delta) -> bool:
    """Change a row's value by one step. True when something changed."""
    key = item.key
    before = dict(draft)
    if item.kind == "preset":
        app.cycle_preset(draft, delta)
    elif item.kind == "toggle":
        if key in (app.KEY_THUMBNAIL, app.KEY_COUNTDOWN):
            draft[key] = not draft.get(key)
        else:
            draft[key] = "false" if yes(draft.get(key)) else "true"
    elif item.kind == "slider":
        size = SLIDER_STEP.get(key, 1)
        draft[key] = str(max(item.low, min(item.high, number(draft, item) + delta * size)))
    elif item.kind == "pos":
        place = cv.PLACES[(cv.PLACES.index(place_of(draft)) + delta) % len(cv.PLACES)]
        draft[key] = place
        draft[app.KEY_POSITION] = nearest_corner(place)
    elif item.kind == "swatch":
        current = draft.get(key) if draft.get(key) in ACCENTS else "Auto"
        draft[key] = ACCENTS[(ACCENTS.index(current) + delta) % len(ACCENTS)]
    elif key == app.KEY_PROGRESS:
        states = [choice[0] for choice in PROGRESS4]
        set_progress_state(draft, states[(states.index(progress_state(draft)) + delta) % len(states)])
    elif key in (app.KEY_LAYOUT, app.KEY_LAYOUT_LOOK, app.KEY_FOCUS, app.KEY_STYLE):
        draft[key] = app.cycle_choice(key, draft.get(key), delta)
    elif item.choices:
        values = [choice[0] for choice in item.choices]
        current = str(draft.get(key))
        index = values.index(current) if current in values else 0
        draft[key] = values[(index + delta) % len(values)]
    return draft != before


def choice_index(draft, item) -> int:
    """Which of a row's choices the draft has (for a row whose choices stand side by side)."""
    if item.key == app.KEY_PROGRESS:
        return [choice[0] for choice in PROGRESS4].index(progress_state(draft))
    values = [choice[0] for choice in item.choices]
    current = str(draft.get(item.key))
    return values.index(current) if current in values else 0


def title_words(tab) -> tuple:
    """String id and English of the tab's word in the large title."""
    return TAB_LABELS[tab]
