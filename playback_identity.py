# -*- coding: utf-8 -*-
"""Which show or film is playing, as a stable key and a name to show.

Used to tell episodes of one show apart from another (binge mode) and to add up time
saved per title (statistics). Library metadata comes first; for files outside the
library the show is the folder that holds the episode (``Show/Season 01/…``).
No network calls: everything comes from the player item Kodi already returned.
"""

from __future__ import annotations

import re

_SEASON_FOLDER = re.compile(
    r"^(?:season|series|staffel|saison|temporada|stagione|sæson|säsong|sesong|seizoen|s)"
    r"[\s._-]*\d{1,4}$|^specials?$",
    re.IGNORECASE,
)


def _clean(text) -> str:
    return " ".join(str(text or "").split())


def _folder_parts(path) -> list:
    text = str(path or "").replace("\\", "/")
    if "://" in text:
        text = text.split("://", 1)[1]
    return [p for p in text.split("/") if p]


def show_folder_name(path) -> str:
    """Name of the folder above the episode file, skipping a ``Season NN`` folder."""
    parts = _folder_parts(path)[:-1]
    while parts and _SEASON_FOLDER.match(parts[-1].strip()):
        parts.pop()
    return _clean(parts[-1]) if parts else ""


def title_identity(item, video_path="", playback_type="") -> tuple:
    """``(key, name)`` for the show (episodes) or the film (movies); ``(None, "")`` when unknown.

    Keys: ``tv:<tvshowid>`` for library shows, ``show:<name>`` / ``movie:<name>`` otherwise
    (lower case, so ``The Office`` and ``the office`` are one title).
    """
    item = item if isinstance(item, dict) else {}
    kind = (playback_type or "").strip().lower()
    if kind == "episode":
        name = _clean(item.get("showtitle")) or show_folder_name(video_path or item.get("file"))
        try:
            show_id = int(item.get("tvshowid"))
        except (TypeError, ValueError):
            show_id = -1
        if show_id > 0:
            return "tv:%d" % show_id, name
        if name:
            return "show:%s" % name.lower(), name
        return None, ""
    if kind == "movie":
        name = _clean(item.get("title")) or _clean(item.get("label"))
        if name:
            return "movie:%s" % name.lower(), name
    return None, ""


def monitor_title_identity(monitor, video_path="", playback_type="") -> tuple:
    """:func:`title_identity` from the player snapshot the service keeps for this video."""
    try:
        from service_player_snapshot import get_player_snapshot, snapshot_matches_path

        snapshot = get_player_snapshot(monitor)
        item = snapshot.item if snapshot_matches_path(snapshot, video_path) else {}
    except Exception:
        item = {}
    return title_identity(item, video_path, playback_type)
