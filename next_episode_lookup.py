# -*- coding: utf-8 -*-
"""Find the episode that follows the one that is playing.

Two sources, in this order:

* the active video playlist, when it has an item after the current position (the
  user queued it, and Kodi would play it next anyway);
* the video library: the next episode of the same show in season/episode order.

Both return a plain dict (see ``SOURCE_*``) that ``next_episode_play`` can start.
"""

from __future__ import annotations

from typing import Optional

from remote_http import jsonrpc, parse_int

SOURCE_LIBRARY = "library"
SOURCE_PLAYLIST = "playlist"

_ORDER_PROPERTIES = ["season", "episode", "playcount", "file"]
_DETAIL_PROPERTIES = [
    "title",
    "showtitle",
    "season",
    "episode",
    "file",
    "playcount",
    "tvshowid",
    "art",
]
_CURRENT_PROPERTIES = ["tvshowid", "season", "episode", "file", "playcount"]
_PLAYLIST_PROPERTIES = ["title", "showtitle", "season", "episode", "file", "art"]
# Wide pictures only: the popup's picture box is 16:9, a poster would be cropped.
_THUMB_KEYS = ("thumb", "landscape", "fanart", "tvshow.landscape", "tvshow.fanart")


def _positive_int(value) -> Optional[int]:
    number = parse_int(value)
    return number if number is not None and number > 0 else None


def pick_thumb(art) -> str:
    """The best wide picture in a Kodi ``art`` dict, or an empty string."""
    if not isinstance(art, dict):
        return ""
    for key in _THUMB_KEYS:
        value = art.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def pick_next_episode(episodes, current, *, skip_watched=False):
    """
    Choose the row that follows ``current`` in season/episode order.

    ``episodes`` are library rows (``episodeid``, ``season``, ``episode``,
    ``playcount``, ``file``); ``current`` is a dict with ``id``, ``season``,
    ``episode`` and ``file``. Gaps in the numbering are fine (E03 is followed by E05
    when E04 is not in the library). Specials (season 0) are never "next" for a
    regular episode, and a special is only followed by another special. Rows that
    share the current file (one file holding several episodes) are skipped.
    """
    cur_season = parse_int(current.get("season"))
    cur_episode = parse_int(current.get("episode"))
    if cur_season is None or cur_episode is None or cur_season < 0 or cur_episode < 0:
        return None
    cur_id = _positive_int(current.get("id"))
    cur_file = current.get("file") or ""
    in_specials = cur_season == 0

    candidates = []
    for row in episodes or []:
        season = parse_int(row.get("season"))
        number = parse_int(row.get("episode"))
        episode_id = _positive_int(row.get("episodeid"))
        if season is None or number is None or episode_id is None:
            continue
        if (season == 0) != in_specials:
            continue
        candidates.append((season, number, episode_id, row))
    candidates.sort(key=lambda c: (c[0], c[1], c[2]))

    for season, number, episode_id, row in candidates:
        if (season, number) <= (cur_season, cur_episode):
            continue
        if episode_id == cur_id:
            continue
        if cur_file and row.get("file") == cur_file:
            continue
        if skip_watched and (parse_int(row.get("playcount")) or 0) > 0:
            continue
        return row
    return None


def describe_current_episode(item) -> dict:
    """
    Normalise the playing item into ``{id, tvshowid, season, episode, file, playcount}``.

    ``Player.GetItem`` may lack the show id or the numbering, so missing pieces are
    read from the library row. Keys that stay unknown are ``None``.
    """
    item = item or {}
    is_episode = (item.get("type") or "").lower() == "episode"
    current = {
        "id": _positive_int(item.get("id")) if is_episode else None,
        "tvshowid": _positive_int(item.get("tvshowid")),
        "season": parse_int(item.get("season")),
        "episode": parse_int(item.get("episode")),
        "file": item.get("file") or "",
        "playcount": None,
    }
    # The play count is never part of Player.GetItem and the hand-off needs it, so a
    # library episode always costs one details call.
    if current["id"]:
        response = jsonrpc(
            "VideoLibrary.GetEpisodeDetails",
            {"episodeid": current["id"], "properties": _CURRENT_PROPERTIES},
            log_errors=False,
        )
        row = (response.get("result") or {}).get("episodedetails") or {}
        current["tvshowid"] = current["tvshowid"] or _positive_int(row.get("tvshowid"))
        if current["season"] is None or current["season"] < 0:
            current["season"] = parse_int(row.get("season"))
        if current["episode"] is None or current["episode"] < 0:
            current["episode"] = parse_int(row.get("episode"))
        current["file"] = current["file"] or row.get("file") or ""
        current["playcount"] = parse_int(row.get("playcount"))
    return current


def find_library_successor(item, *, skip_watched=False, current=None) -> Optional[dict]:
    """Next episode of the same show in the video library, or None."""
    current = current or describe_current_episode(item)
    if not current["tvshowid"]:
        return None
    response = jsonrpc(
        "VideoLibrary.GetEpisodes",
        {"tvshowid": current["tvshowid"], "properties": _ORDER_PROPERTIES},
        log_errors=False,
    )
    rows = (response.get("result") or {}).get("episodes") or []
    row = pick_next_episode(rows, current, skip_watched=skip_watched)
    if not row:
        return None
    episode_id = _positive_int(row.get("episodeid"))
    details_response = jsonrpc(
        "VideoLibrary.GetEpisodeDetails",
        {"episodeid": episode_id, "properties": _DETAIL_PROPERTIES},
        log_errors=False,
    )
    details = (details_response.get("result") or {}).get("episodedetails") or row
    return {
        "source": SOURCE_LIBRARY,
        "episodeid": episode_id,
        "title": details.get("title") or row.get("label") or "",
        "showtitle": details.get("showtitle") or "",
        "season": parse_int(details.get("season", row.get("season"))),
        "episode": parse_int(details.get("episode", row.get("episode"))),
        "file": details.get("file") or row.get("file") or "",
        "thumb": pick_thumb(details.get("art")),
    }


def find_playlist_successor() -> Optional[dict]:
    """The item after the current position in the active video playlist, or None."""
    players = (jsonrpc("Player.GetActivePlayers", log_errors=False).get("result")) or []
    player_id = None
    for entry in players:
        if entry.get("type") == "video":
            player_id = parse_int(entry.get("playerid"))
            break
    if player_id is None:
        return None
    props = (
        jsonrpc(
            "Player.GetProperties",
            {"playerid": player_id, "properties": ["playlistid", "position"]},
            log_errors=False,
        ).get("result")
        or {}
    )
    playlist_id = parse_int(props.get("playlistid"))
    position = parse_int(props.get("position"))
    if playlist_id is None or playlist_id < 0 or position is None or position < 0:
        return None
    response = jsonrpc(
        "Playlist.GetItems",
        {
            "playlistid": playlist_id,
            "properties": _PLAYLIST_PROPERTIES,
            "limits": {"start": position + 1, "end": position + 2},
        },
        log_errors=False,
    )
    items = (response.get("result") or {}).get("items") or []
    if not items:
        return None
    nxt = items[0]
    return {
        "source": SOURCE_PLAYLIST,
        "playerid": player_id,
        "playlistid": playlist_id,
        "position": position + 1,
        "title": nxt.get("title") or nxt.get("label") or "",
        "showtitle": nxt.get("showtitle") or "",
        "season": parse_int(nxt.get("season")),
        "episode": parse_int(nxt.get("episode")),
        "file": nxt.get("file") or "",
        "thumb": pick_thumb(nxt.get("art")),
    }


def find_next_episode(item, *, skip_watched=False, current=None) -> Optional[dict]:
    """Next episode to offer for the playing ``item`` (playlist first, then library)."""
    return find_playlist_successor() or find_library_successor(
        item, skip_watched=skip_watched, current=current
    )


def episode_label(episode) -> str:
    """``S01E05 \u00b7 Title`` (or just the title when the numbering is unknown)."""
    season = parse_int(episode.get("season"))
    number = parse_int(episode.get("episode"))
    title = (episode.get("title") or "").strip()
    code = ""
    if season is not None and number is not None and season >= 0 and number >= 0:
        code = "S%02dE%02d" % (season, number)
    if code and title:
        return "%s \u00b7 %s" % (code, title)
    return code or title
