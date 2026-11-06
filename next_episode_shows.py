# -*- coding: utf-8 -*-
"""Per-show autoplay for the next episode prompt ("always play this show's next episode").

The choices live in one small JSON file in the add-on profile, keyed on the show's TMDB id
(IMDb id as fallback), the same key the per-title auto-skip rules use, so a choice follows
the show across re-encodes, renames and other copies of its episodes.

A show has one of two modes. ``auto`` starts its next episode by itself; ``ask`` always
shows the prompt, even when "Play the next episode automatically" is on. A show without an
entry follows that global setting.
"""

from __future__ import annotations

import os

from settings_utils import addon_get_bool, log
from skippy_profile_store import file_stamp, profile_path, read_json, write_json

SHOWS_FILENAME = "next_episode_shows.json"
SCHEMA = "skippy_next_episode_shows_v1"

KEY_PER_SHOW = "next_episode_per_show"

MODE_AUTO = "auto"
MODE_ASK = "ask"
MODES = (MODE_AUTO, MODE_ASK)

# (file stamp, {key: {"mode", "title"}}). The service reads this every tick inside the
# prompt window, while the Manage window and a backup restore change the file from other
# scripts, so a changed stamp (not just our own writes) drops the cache.
_cache: tuple | None = None


def per_show_autoplay_enabled(addon) -> bool:
    return addon_get_bool(addon, KEY_PER_SHOW, False)


def show_key_for_identity(identity) -> str | None:
    """``tv_tmdb_1396`` style key of the show an episode belongs to, or None when unknown."""
    if not identity or (identity.get("type") or "") != "episode":
        return None
    from per_show_overrides import override_key_for_identity

    return override_key_for_identity(identity)


def resolve_autoplay(global_autoplay, per_show_on, mode) -> bool:
    """Whether to start the next episode by itself: the show's choice wins when per-show is on."""
    if per_show_on and mode == MODE_AUTO:
        return True
    if per_show_on and mode == MODE_ASK:
        return False
    return bool(global_autoplay)


def _path() -> str | None:
    return profile_path(SHOWS_FILENAME)


def _clean_key(key) -> str | None:
    if not isinstance(key, str):
        return None
    key = key.strip()
    if not key or any(ch in key for ch in "/\\:"):
        return None
    return key


def _clean_entry(raw) -> dict | None:
    if not isinstance(raw, dict) or raw.get("mode") not in MODES:
        return None
    entry = {"mode": raw["mode"]}
    title = raw.get("title")
    if isinstance(title, str) and title.strip():
        entry["title"] = title.strip()
    return entry


def _clean_shows(raw) -> dict:
    shows = {}
    if isinstance(raw, dict):
        for key, value in raw.items():
            key = _clean_key(key)
            entry = _clean_entry(value)
            if key and entry:
                shows[key] = entry
    return shows


def load_shows() -> dict:
    """``{key: {"mode", "title"?}}`` as saved (cached; empty when nothing is saved)."""
    global _cache
    path = _path()
    stamp = file_stamp(path)
    if _cache is not None and _cache[0] == stamp:
        return _cache[1]
    data = read_json(path, default=None, recover=True)
    shows = _clean_shows(data.get("shows")) if isinstance(data, dict) else {}
    _cache = (stamp, shows)
    return shows


def lookup_mode(key) -> str | None:
    """Saved mode for this show, or None."""
    key = _clean_key(key)
    if not key:
        return None
    entry = load_shows().get(key)
    return entry["mode"] if entry else None


def _write(shows: dict) -> bool:
    global _cache
    _cache = None
    path = _path()
    if not path:
        return False
    if not write_json(path, {"schema": SCHEMA, "shows": shows}, keep_backup=True):
        log("⚠️ Per-show autoplay: could not write %s" % path)
        return False
    return True


def save_mode(key, mode, title: str = "") -> bool:
    """Save one show's choice. Returns True when written."""
    key = _clean_key(key)
    if not key or mode not in MODES:
        return False
    shows = dict(load_shows())
    previous = shows.get(key) or {}
    entry = {"mode": mode}
    title = (title or previous.get("title") or "").strip()
    if title:
        entry["title"] = title
    shows[key] = entry
    if not _write(shows):
        return False
    log("💾 Per-show autoplay saved: %s → %s" % (key, mode))
    return True


def delete_show(key) -> bool:
    """Forget one show's choice. Returns True when it was saved."""
    key = _clean_key(key)
    shows = dict(load_shows())
    if not key or key not in shows:
        return False
    del shows[key]
    if not _write(shows):
        return False
    log("🗑️ Per-show autoplay forgotten: %s" % key)
    return True


def display_title(key, entry) -> str:
    """The saved title, or a readable id (``TV · TMDB 1396``) when none was saved."""
    title = ((entry or {}).get("title") or "").strip()
    if title:
        return title
    parts = str(key).split("_", 2)
    if len(parts) == 3 and parts[1] in ("tmdb", "imdb"):
        return "TV · %s %s" % (parts[1].upper(), parts[2])
    return str(key)


def list_entries() -> list[dict]:
    """Rows for the Manage window: ``key``, ``title``, ``mode``; sorted by title."""
    rows = [
        {"key": key, "title": display_title(key, entry), "mode": entry["mode"]}
        for key, entry in load_shows().items()
    ]
    rows.sort(key=lambda row: (row["title"].lower(), row["key"]))
    return rows


def clear_all() -> int:
    """Forget every show. Returns how many were saved."""
    global _cache
    count = len(load_shows())
    path = _path()
    _cache = None
    if path and os.path.isfile(path):
        try:
            os.remove(path)
        except OSError as exc:
            log("⚠️ Per-show autoplay: could not delete %s (%s)" % (path, exc))
            return 0
    return count


def export_all() -> dict:
    """Snapshot for the profile-data backup: ``{key: {"mode", "title"?}}``."""
    return {key: dict(entry) for key, entry in load_shows().items()}


def merge_from_backup(incoming) -> tuple[int, int]:
    """
    Merge shows from a backup. Returns ``(added, updated)``.

    A backup entry wins over the local one for the same show; other local shows stay.
    """
    incoming = _clean_shows(incoming)
    if not incoming:
        return 0, 0
    shows = dict(load_shows())
    added = updated = 0
    changed = False
    for key, entry in incoming.items():
        local = shows.get(key)
        merged = dict(entry)
        if "title" not in merged and local and local.get("title"):
            merged["title"] = local["title"]
        if local is None:
            added += 1
        elif local["mode"] != entry["mode"]:
            updated += 1
        elif merged == local:
            continue
        shows[key] = merged
        changed = True
    if changed and not _write(shows):
        return 0, 0
    return added, updated


def clear_cache() -> None:
    global _cache
    _cache = None
