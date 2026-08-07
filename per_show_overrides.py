# -*- coding: utf-8 -*-
"""Per-title autoskip overrides ("always skip Intro for this show").

Overrides are stored under ``addon_data/service.skippy/show_overrides/`` in one JSON
file per title, named after the title's TMDB id (IMDb id as fallback). Keying on the
library id rather than the file path means the choice survives re-encodes, renames,
and different versions of the same movie or episode.
"""

from __future__ import annotations

import os

from settings_utils import addon_get_bool, log, log_service_detail, normalize_label
from skippy_profile_store import profile_path, read_json, write_json

OVERRIDES_DIRNAME = "show_overrides"
SCHEMA = "skippy_show_overrides_v1"

MODE_AUTO = "auto"
MODE_DECLINED = "declined"

# key -> overrides dict; the skip path reads this on every active segment.
_cache: dict[str, dict] = {}


def per_show_override_enabled(addon) -> bool:
    return addon_get_bool(addon, "per_show_autoskip_override", False)


def override_key_for_identity(identity) -> str | None:
    """``tv_tmdb_1396`` / ``movie_imdb_tt0133093`` style id, or None when unknown."""
    if not identity:
        return None
    kind = "tv" if (identity.get("type") or "") == "episode" else "movie"
    tmdb_id = identity.get("tmdb_id")
    if tmdb_id is not None:
        return "%s_tmdb_%s" % (kind, tmdb_id)
    imdb_id = identity.get("imdb_id")
    if imdb_id:
        return "%s_imdb_%s" % (kind, imdb_id)
    return None


def _store_path(key: str) -> str | None:
    if not key or any(ch in key for ch in "/\\:"):
        return None
    return profile_path(OVERRIDES_DIRNAME, "%s.json" % key)


def load_overrides(key: str) -> dict:
    """``{normalized_label: mode}`` for one title (cached; empty when nothing saved)."""
    if not key:
        return {}
    cached = _cache.get(key)
    if cached is not None:
        return cached
    data = read_json(_store_path(key), default=None)
    segments = {}
    if isinstance(data, dict):
        raw = data.get("segments")
        if isinstance(raw, dict):
            for label, mode in raw.items():
                if mode in (MODE_AUTO, MODE_DECLINED):
                    segments[normalize_label(label)] = mode
    _cache[key] = segments
    return segments


def lookup_override(key: str, segment_label) -> str | None:
    """Saved mode for this title + segment type, or None."""
    if not key:
        return None
    return load_overrides(key).get(normalize_label(segment_label))


def save_override(key: str, segment_label, mode: str, title: str = "") -> bool:
    """Persist one title + segment type decision. Returns True when written."""
    if not key or mode not in (MODE_AUTO, MODE_DECLINED):
        return False
    path = _store_path(key)
    if not path:
        return False
    existing = read_json(path, default=None)
    payload = existing if isinstance(existing, dict) else {}
    segments = payload.get("segments")
    if not isinstance(segments, dict):
        segments = {}
    segments[normalize_label(segment_label)] = mode
    payload["schema"] = SCHEMA
    payload["key"] = key
    payload["segments"] = segments
    if title:
        payload["title"] = title
    if not write_json(path, payload):
        log("⚠️ Per-show override: could not write %s" % path)
        return False
    _cache.pop(key, None)
    log(
        "💾 Per-show override saved: %s → %s = %s"
        % (key, normalize_label(segment_label), mode)
    )
    return True


def delete_override(key: str) -> bool:
    """Delete one title's override file. Returns True when the file was removed."""
    path = _store_path(key)
    if not path or not os.path.isfile(path):
        _cache.pop(key, None)
        return False
    try:
        os.remove(path)
    except OSError as exc:
        log_service_detail(
            "per-show override: could not delete %s (%s)" % (path, exc),
            tag="overrides",
        )
        return False
    _cache.pop(key, None)
    log("🗑️ Per-show override deleted: %s" % key)
    return True


def _key_from_filename(name: str) -> str | None:
    if not name.endswith(".json"):
        return None
    key = name[:-5]
    if not key or any(ch in key for ch in "/\\:"):
        return None
    return key


def _display_title_for_payload(key: str, payload: dict) -> str:
    title = (payload.get("title") or "").strip()
    if title:
        return title
    # Fall back to a readable id when the save happened without a library title.
    parts = key.split("_", 2)
    if len(parts) == 3 and parts[1] in ("tmdb", "imdb"):
        kind = "TV" if parts[0] == "tv" else "Movie"
        return "%s · %s %s" % (kind, parts[1].upper(), parts[2])
    return key


def list_title_entries(*, auto_only: bool = True) -> list[dict]:
    """
    Saved per-title override rows for the manage UI.

    Each item: ``key``, ``title``, ``path``, ``auto_labels``, ``declined_labels``.
    When ``auto_only`` is True (default), only titles with at least one auto-skip remain.
    """
    entries = []
    for path in stored_override_files():
        key = _key_from_filename(os.path.basename(path))
        if not key:
            continue
        payload = read_json(path, default=None)
        if not isinstance(payload, dict):
            continue
        raw = payload.get("segments")
        if not isinstance(raw, dict):
            continue
        auto_labels = []
        declined_labels = []
        for label, mode in raw.items():
            normalized = normalize_label(label)
            if not normalized:
                continue
            if mode == MODE_AUTO:
                auto_labels.append(normalized)
            elif mode == MODE_DECLINED:
                declined_labels.append(normalized)
        auto_labels.sort()
        declined_labels.sort()
        if auto_only and not auto_labels:
            continue
        entries.append(
            {
                "key": key,
                "title": _display_title_for_payload(key, payload),
                "path": path,
                "auto_labels": auto_labels,
                "declined_labels": declined_labels,
            }
        )
    entries.sort(key=lambda item: (item["title"].lower(), item["key"]))
    return entries


def clear_cache() -> None:
    _cache.clear()


def stored_override_files() -> list[str]:
    directory = profile_path(OVERRIDES_DIRNAME)
    if not directory or not os.path.isdir(directory):
        return []
    try:
        names = sorted(os.listdir(directory))
    except OSError:
        return []
    return [
        os.path.join(directory, name) for name in names if name.endswith(".json")
    ]


def clear_all_overrides() -> int:
    """Delete every stored override file. Returns the number removed."""
    removed = 0
    for path in stored_override_files():
        try:
            os.remove(path)
            removed += 1
        except OSError as exc:
            log_service_detail(
                "per-show override: could not delete %s (%s)" % (path, exc),
                tag="overrides",
            )
    clear_cache()
    return removed
