# -*- coding: utf-8 -*-
"""Find the episode (or movie) that follows the one that is playing.

Two sources, in this order:

* the active video playlist, when it has an item after the current position (the
  user queued it, and Kodi would play it next anyway);
* the video library: the next episode of the same show in season/episode order, or, for a
  movie that belongs to a Kodi collection (a movie set), the next movie of that collection.

Both return a plain dict (see ``SOURCE_*``) that ``next_episode_play`` can start.
"""

from __future__ import annotations

from typing import Optional

from remote_http import jsonrpc, parse_int

SOURCE_LIBRARY = "library"
SOURCE_PLAYLIST = "playlist"
# Told to us by the video add-on that is playing the episode (Up Next's ``upnext_data`` signal).
SOURCE_PROVIDER = "provider"
# The next movie of the collection (movie set) the playing movie belongs to.
SOURCE_MOVIE = "movie"

# What is playing: an episode (the default) or a movie.
KIND_EPISODE = "episode"
KIND_MOVIE = "movie"

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
_MOVIE_CURRENT_PROPERTIES = ["setid", "year", "file", "playcount"]
_MOVIE_SET_PROPERTIES = ["title", "sorttitle", "year", "file", "playcount", "art", "setid"]
# Wide pictures only: the popup's picture box is 16:9, a poster would be cropped.
_THUMB_KEYS = ("thumb", "landscape", "fanart", "tvshow.landscape", "tvshow.fanart")
# A movie's "thumb" is its poster, so only the wide pictures count.
_MOVIE_THUMB_KEYS = ("landscape", "fanart")
# Movies without a year go last in their collection.
_NO_YEAR = 10 ** 6


def _positive_int(value) -> Optional[int]:
    number = parse_int(value)
    return number if number is not None and number > 0 else None


def pick_thumb(art, keys=_THUMB_KEYS) -> str:
    """The best wide picture in a Kodi ``art`` dict, or an empty string."""
    if not isinstance(art, dict):
        return ""
    for key in keys:
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


def is_movie_playback(item) -> bool:
    """Whether the playing item (``Player.GetItem``) is a movie."""
    return isinstance(item, dict) and (item.get("type") or "").lower() == KIND_MOVIE


def is_movie_item(next_item) -> bool:
    """Whether an offered "next" item is a movie."""
    return isinstance(next_item, dict) and next_item.get("source") == SOURCE_MOVIE


def _movie_order(row):
    """Sort key of a collection's movies: by year, then sort title (or title), then id."""
    year = parse_int(row.get("year"))
    name = (row.get("sorttitle") or row.get("title") or row.get("label") or "").strip().lower()
    return (year if year is not None and year > 0 else _NO_YEAR, name, _positive_int(row.get("movieid")) or 0)


def pick_next_movie(movies, current, *, skip_watched=False):
    """
    Choose the movie that follows ``current`` in its collection.

    ``movies`` are the rows of ``VideoLibrary.GetMovieSetDetails`` (``movieid``, ``title``,
    ``sorttitle``, ``year``, ``playcount``, ``file``); ``current`` is a dict with ``id`` and
    ``file``. The collection is ordered by year, then sort title, as Kodi lists it. None when the
    playing movie is not in the list or is the last one. Rows that share the current file are
    skipped, and watched movies too when ``skip_watched``.
    """
    rows = []
    for row in movies or []:
        if isinstance(row, dict) and _positive_int(row.get("movieid")):
            rows.append(row)
    rows.sort(key=_movie_order)
    cur_id = _positive_int(current.get("id"))
    cur_file = current.get("file") or ""
    position = None
    for index, row in enumerate(rows):
        if cur_id and _positive_int(row.get("movieid")) == cur_id:
            position = index
            break
    if position is None and cur_file:
        for index, row in enumerate(rows):
            if row.get("file") == cur_file:
                position = index
                break
    if position is None:
        return None
    for row in rows[position + 1 :]:
        if cur_file and row.get("file") == cur_file:
            continue
        if skip_watched and (parse_int(row.get("playcount")) or 0) > 0:
            continue
        return row
    return None


def describe_current_movie(item) -> dict:
    """
    Normalise the playing movie into ``{kind, id, setid, year, file, playcount}``.

    ``Player.GetItem`` does not say which collection a movie is in, so a library movie costs
    one details call (which also gives the play count the hand-off needs).
    """
    item = item or {}
    is_movie = is_movie_playback(item)
    current = {
        "kind": KIND_MOVIE,
        "id": _positive_int(item.get("id")) if is_movie else None,
        "setid": _positive_int(item.get("setid")),
        "year": parse_int(item.get("year")),
        "file": item.get("file") or "",
        "playcount": None,
    }
    if current["id"]:
        response = jsonrpc(
            "VideoLibrary.GetMovieDetails",
            {"movieid": current["id"], "properties": _MOVIE_CURRENT_PROPERTIES},
            log_errors=False,
        )
        row = (response.get("result") or {}).get("moviedetails") or {}
        current["setid"] = current["setid"] or _positive_int(row.get("setid"))
        if current["year"] is None or current["year"] <= 0:
            current["year"] = parse_int(row.get("year"))
        current["file"] = current["file"] or row.get("file") or ""
        current["playcount"] = parse_int(row.get("playcount"))
    return current


def find_movie_successor(item, *, skip_watched=False, current=None) -> Optional[dict]:
    """Next movie of the collection the playing movie belongs to, or None."""
    current = current or describe_current_movie(item)
    if not current.get("id") or not current.get("setid"):
        return None
    response = jsonrpc(
        "VideoLibrary.GetMovieSetDetails",
        {
            "setid": current["setid"],
            "properties": ["title"],
            "movies": {"properties": _MOVIE_SET_PROPERTIES},
        },
        log_errors=False,
    )
    rows = ((response.get("result") or {}).get("setdetails") or {}).get("movies") or []
    row = pick_next_movie(rows, current, skip_watched=skip_watched)
    if not row:
        return None
    return {
        "source": SOURCE_MOVIE,
        "movieid": _positive_int(row.get("movieid")),
        "title": row.get("title") or row.get("label") or "",
        "showtitle": "",
        "season": None,
        "episode": None,
        "year": parse_int(row.get("year")),
        "file": row.get("file") or "",
        "thumb": pick_thumb(row.get("art"), _MOVIE_THUMB_KEYS),
    }


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
    """Next episode (or movie) to offer for the playing ``item`` (playlist first, then library)."""
    if is_movie_playback(item) or (current or {}).get("kind") == KIND_MOVIE:
        return find_playlist_successor() or find_movie_successor(
            item, skip_watched=skip_watched, current=current
        )
    return find_playlist_successor() or find_library_successor(
        item, skip_watched=skip_watched, current=current
    )


def episode_label(episode) -> str:
    """``S01E05 \u00b7 Title`` (or just the title when the numbering is unknown); ``Title (2005)`` for a movie."""
    if is_movie_item(episode):
        name = (episode.get("title") or "").strip()
        year = parse_int(episode.get("year"))
        return "%s (%d)" % (name, year) if name and year is not None and year > 0 else name
    season = parse_int(episode.get("season"))
    number = parse_int(episode.get("episode"))
    title = (episode.get("title") or "").strip()
    code = ""
    if season is not None and number is not None and season >= 0 and number >= 0:
        code = "S%02dE%02d" % (season, number)
    if code and title:
        return "%s \u00b7 %s" % (code, title)
    return code or title
