# -*- coding: utf-8 -*-
"""Start the next episode and keep the one we leave marked as watched."""

from __future__ import annotations

import threading
import time
from typing import Optional

from next_episode_lookup import (
    KIND_EPISODE,
    KIND_MOVIE,
    SOURCE_LIBRARY,
    SOURCE_MOVIE,
    SOURCE_PLAYLIST,
    SOURCE_PROVIDER,
)
from next_episode_provider import REPLY_SENDER, SIGNAL_SUFFIX, encode_reply, reply_message
from remote_http import jsonrpc, parse_int
from settings_utils import log, log_error

MARK_WATCHED_DELAY_S = 4.0


def play_next(next_episode, *, resume=True) -> bool:
    """
    Switch playback to ``next_episode``. True when Kodi accepted the request.

    A playlist item is reached with ``Player.GoTo`` (the playlist stays intact); a
    library episode or movie is opened with ``Player.Open``. An episode a video add-on announced is
    opened from its ``play_url``, or the add-on is asked to start it with the ``play_info`` it gave
    (the same two ways Up Next does it).
    """
    source = next_episode.get("source")
    if source == SOURCE_PLAYLIST:
        response = jsonrpc(
            "Player.GoTo",
            {
                "playerid": next_episode.get("playerid"),
                "to": next_episode.get("position"),
            },
        )
    elif source == SOURCE_LIBRARY:
        response = jsonrpc(
            "Player.Open",
            {
                "item": {"episodeid": next_episode.get("episodeid")},
                "options": {"resume": bool(resume)},
            },
        )
    elif source == SOURCE_MOVIE:
        response = jsonrpc(
            "Player.Open",
            {
                "item": {"movieid": next_episode.get("movieid")},
                "options": {"resume": bool(resume)},
            },
        )
    elif source == SOURCE_PROVIDER:
        response = _play_provider_item(next_episode)
    else:
        return False
    ok = bool(response) and not response.get("error")
    if not ok:
        log_error("Next episode: Kodi refused to start %s: %s" % (source, response))
    return ok


def _play_provider_item(item):
    url = (item.get("play_url") or "").strip()
    if url:
        return jsonrpc("Player.Open", {"item": {"file": url}})
    provider = item.get("provider") or ""
    if not provider:
        return {}
    return jsonrpc(
        "JSONRPC.NotifyAll",
        {
            "sender": REPLY_SENDER + SIGNAL_SUFFIX,
            "message": reply_message(provider),
            "data": [encode_reply(item.get("play_info"))],
        },
    )


def current_playcount(episode_id, kind=KIND_EPISODE) -> Optional[int]:
    """Play count of a library episode (or movie), or None when it cannot be read."""
    if not episode_id:
        return None
    if kind == KIND_MOVIE:
        response = jsonrpc(
            "VideoLibrary.GetMovieDetails",
            {"movieid": episode_id, "properties": ["playcount"]},
            log_errors=False,
        )
        details = (response.get("result") or {}).get("moviedetails") or {}
    else:
        response = jsonrpc(
            "VideoLibrary.GetEpisodeDetails",
            {"episodeid": episode_id, "properties": ["playcount"]},
            log_errors=False,
        )
        details = (response.get("result") or {}).get("episodedetails") or {}
    return parse_int(details.get("playcount"))


def mark_watched_if_needed(episode_id, playcount_before, kind=KIND_EPISODE) -> bool:
    """
    Count ``episode_id`` (an episode, or a movie when ``kind`` says so) as watched unless Kodi
    already did while stopping it.

    Moving on N seconds before the end can fall short of Kodi's "watched" threshold,
    which would leave the episode unwatched. True when this call changed it.
    """
    if not episode_id or playcount_before is None:
        return False
    now_count = current_playcount(episode_id, kind)
    if now_count is None or now_count > playcount_before:
        return False
    method, id_key = (
        ("VideoLibrary.SetMovieDetails", "movieid")
        if kind == KIND_MOVIE
        else ("VideoLibrary.SetEpisodeDetails", "episodeid")
    )
    response = jsonrpc(
        method,
        {
            id_key: episode_id,
            "playcount": playcount_before + 1,
            "lastplayed": time.strftime("%Y-%m-%d %H:%M:%S"),
            "resume": {"position": 0, "total": 0},
        },
    )
    ok = bool(response) and not response.get("error")
    if ok:
        log("Next episode: marked %s %s as watched" % (kind, episode_id))
    return ok


def schedule_mark_watched(monitor, episode_id, playcount_before, kind=KIND_EPISODE) -> None:
    """Check the old episode (or movie) a few seconds after the switch, off the service thread."""
    if not episode_id or playcount_before is None:
        return

    def work():
        try:
            if monitor.waitForAbort(MARK_WATCHED_DELAY_S):
                return
            mark_watched_if_needed(episode_id, playcount_before, kind)
        except Exception as exc:
            log_error("Next episode: marking episode watched failed: %s" % exc)

    threading.Thread(target=work, daemon=True).start()
