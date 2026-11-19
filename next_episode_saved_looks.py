# -*- coding: utf-8 -*-
"""Looks of the next episode popup that the user saved under a name.

A saved look is the **Popup look** plus the six parts changed on top of it (text and heading
colour, all caps, button highlight, bar style, card opacity), exactly what the Customize screen
sets with its look rows. Where the popup sits, what it shows and which button is focused first are
never part of a look, so loading one keeps those as they are.

They live in ``addon_data/service.skippy/next_episode_looks.json``, the same way the skip
dialog's saved presets do, and travel with the profile data backup.
"""

from __future__ import annotations

from next_episode_appearance import (CHOICE_KEYS, KEY_FORM, KEY_LAYOUT, KEY_LAYOUT_LOOK, KEY_PICTURE, KEY_THUMBNAIL,
                                     KEY_ZOOM)
from next_episode_look import FOLLOW_LOOK, KEY_LOOK, LOOK_LABELS, OVERRIDE_KEYS, PRESET_NAMES
from skippy_profile_store import profile_path, read_json, write_json

USER_LOOKS_FILE = "next_episode_looks.json"
USER_LOOKS_SCHEMA = "skippy_next_episode_looks_v1"
MAX_NAME_LEN = 40
MAX_USER_LOOKS = 50

LOOK_KEYS = (KEY_LOOK,) + tuple(OVERRIDE_KEYS)
# Since the popup has layouts a saved look is the whole design: also the layout, the look of that
# layout and the picture. A look saved before that has none of these and leaves them alone.
DESIGN_KEYS = (KEY_LAYOUT, KEY_LAYOUT_LOOK, KEY_PICTURE, KEY_FORM, KEY_ZOOM)

# Codes ``save_user_look`` answers with.
SAVED = ""
ERR_NAME = "name"
ERR_BUILTIN_NAME = "builtin_name"
ERR_LIMIT = "limit"
ERR_WRITE = "write"


def clean_name(name) -> str:
    text = " ".join(str(name or "").split())
    return text[:MAX_NAME_LEN].strip()


def builtin_names() -> set:
    """The names of the built-in looks, which a saved look cannot use."""
    return {label.lower() for label in LOOK_LABELS.values()} | {name.lower() for name in PRESET_NAMES}


def _strict_choice(key, value):
    """The stored form of ``value`` when it is one of the options of ``key``, else None."""
    text = str(value if value is not None else "").replace(" ", "").strip().lower()
    for option in CHOICE_KEYS[key]:
        if option.lower() == text:
            return option
    return None


def sanitize_values(raw) -> dict:
    """The seven look values, or ``{}`` when the look itself is unknown (a part that is not
    understood falls back to **Same as look**)."""
    if not isinstance(raw, dict):
        return {}
    look = _strict_choice(KEY_LOOK, raw.get(KEY_LOOK))
    if look is None:
        return {}
    values = {KEY_LOOK: look}
    for key in OVERRIDE_KEYS:
        values[key] = _strict_choice(key, raw.get(key)) or FOLLOW_LOOK
    for key in DESIGN_KEYS:
        choice = _strict_choice(key, raw.get(key)) if key in raw else None
        if choice is not None:
            values[key] = choice
    if KEY_THUMBNAIL in raw and isinstance(raw[KEY_THUMBNAIL], bool):
        values[KEY_THUMBNAIL] = raw[KEY_THUMBNAIL]
    return values


def snapshot(draft) -> dict:
    """The look values of a Customize draft."""
    draft = draft or {}
    raw = {key: draft.get(key) for key in LOOK_KEYS}
    raw.update({key: draft[key] for key in DESIGN_KEYS + (KEY_THUMBNAIL,) if key in draft})
    return sanitize_values(raw)


def apply_look(draft, values) -> bool:
    """Put saved look values into the draft (nothing else changes). True when they were usable."""
    clean = sanitize_values(values)
    if not clean:
        return False
    for key, value in clean.items():
        draft[key] = value
    return True


def builtin_look_name(values):
    """The name of the built-in look these values are exactly, else None."""
    clean = sanitize_values(values)
    if not clean or any(clean[key] != FOLLOW_LOOK for key in OVERRIDE_KEYS):
        return None
    # A design with a new layout, or with another picture than the episode's, is not a built-in look.
    if clean.get(KEY_LAYOUT, "Card") != "Card" or clean.get(KEY_PICTURE, "Episode") != "Episode":
        return None
    if clean.get(KEY_THUMBNAIL, True) is not True:
        return None
    return LOOK_LABELS.get(clean[KEY_LOOK])


# ----------------------------------------------------------------- user store
def _store_path():
    return profile_path(USER_LOOKS_FILE)


def load_user_looks() -> dict:
    data = read_json(_store_path(), {}, recover=True)
    raw = data.get("looks") if isinstance(data, dict) else None
    out = {}
    if isinstance(raw, dict):
        for name, entry in raw.items():
            nm = clean_name(name)
            values = sanitize_values(entry.get("values") if isinstance(entry, dict) else None)
            if nm and values and nm.lower() not in builtin_names():
                out[nm] = values
    return out


def _write_user_looks(looks: dict) -> bool:
    payload = {
        "schema": USER_LOOKS_SCHEMA,
        "looks": {name: {"values": vals} for name, vals in sorted(looks.items())},
    }
    return write_json(_store_path(), payload, keep_backup=True)


def list_user_looks() -> list:
    """``[(name, values)]`` of the saved looks, A to Z."""
    looks = load_user_looks()
    return [(name, looks[name]) for name in sorted(looks, key=str.lower)]


def find_saved_look(values, looks=None):
    """Name of the saved look whose values are exactly these, else None."""
    clean = sanitize_values(values)
    if not clean:
        return None
    # A look matches when everything it stores is what these values have; one saved before the
    # layouts stores less. Of several matches the one that stores most wins.
    best, best_size = None, -1
    for name, saved in (load_user_looks() if looks is None else looks).items():
        if saved and all(clean.get(key) == value for key, value in saved.items()) and len(saved) > best_size:
            best, best_size = name, len(saved)
    return best


def detect_saved_look(draft):
    """Name of the saved look the draft currently shows, else None."""
    return find_saved_look(snapshot(draft))


def save_user_look(name, draft) -> tuple:
    """Returns ``(ok, code)``; codes: ``name``, ``builtin_name``, ``limit``, ``write``."""
    nm = clean_name(name)
    if not nm:
        return False, ERR_NAME
    if nm.lower() in builtin_names():
        return False, ERR_BUILTIN_NAME
    looks = {k: v for k, v in load_user_looks().items() if k.lower() != nm.lower()}
    if len(looks) >= MAX_USER_LOOKS:
        return False, ERR_LIMIT
    values = snapshot(draft)
    if not values:
        return False, ERR_WRITE
    looks[nm] = values
    return (True, SAVED) if _write_user_looks(looks) else (False, ERR_WRITE)


def delete_user_look(name) -> bool:
    looks = load_user_looks()
    if name not in looks:
        return False
    del looks[name]
    return _write_user_looks(looks)


# ------------------------------------------------------------------- backup
def export_user_looks() -> dict:
    return {
        "schema": USER_LOOKS_SCHEMA,
        "looks": {n: {"values": v} for n, v in load_user_looks().items()},
    }


def merge_user_looks_from_backup(blob) -> int:
    """Add looks from a backup; names (and looks) already saved are kept. Returns how many were added."""
    if not isinstance(blob, dict):
        return 0
    incoming = blob.get("looks")
    if not isinstance(incoming, dict):
        return 0
    looks = load_user_looks()
    added = 0
    for name, entry in incoming.items():
        nm = clean_name(name)
        values = sanitize_values(entry.get("values") if isinstance(entry, dict) else None)
        if not nm or not values or nm.lower() in builtin_names():
            continue
        if any(existing.lower() == nm.lower() for existing in looks):
            continue
        if find_saved_look(values, looks) is not None:
            continue
        if len(looks) >= MAX_USER_LOOKS:
            break
        looks[nm] = values
        added += 1
    if added and not _write_user_looks(looks):
        return 0
    return added
