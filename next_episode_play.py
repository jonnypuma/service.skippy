# -*- coding: utf-8 -*-
"""Start the next episode and keep the one we leave marked as watched."""

from __future__ import annotations

import threading
import time
from typing import Optional

from next_episode_lookup import SOURCE_LIBRARY, SOURCE_PLAYLIST
from remote_http import jsonrpc, parse_int
from settings_utils import log, log_error

MARK_WATCHED_DELAY_S = 4.0


def play_next(next_episode, *, resume=True) -> bool:
    """
    Switch playback to ``next_episode``. True when Kodi accepted the request.

    A playlist item is reached with ``Player.GoTo`` (the playlist stays intact); a
    library episode is opened with ``Player.Open``.
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
    else:
        return False
    ok = bool(response) and not response.get("error")
    if not ok:
        log_error("Next episode: Kodi refused to start %s: %s" % (source, response))
    return ok


def current_playcount(episode_id) -> Optional[int]:
    """Play count of a library episode, or None when it cannot be read."""
    if not episode_id:
        return None
    response = jsonrpc(
        "VideoLibrary.GetEpisodeDetails",
        {"episodeid": episode_id, "properties": ["playcount"]},
        log_errors=False,
    )
    details = (response.get("result") or {}).get("episodedetails") or {}
    return parse_int(details.get("playcount"))


def mark_watched_if_needed(episode_id, playcount_before) -> bool:
    """
    Count ``episode_id`` as watched unless Kodi already did while stopping it.

    Moving on N seconds before the end can fall short of Kodi's "watched" threshold,
    which would leave the episode unwatched. True when this call changed it.
    """
    if not episode_id or playcount_before is None:
        return False
    now_count = current_playcount(episode_id)
    if now_count is None or now_count > playcount_before:
        return False
    response = jsonrpc(
        "VideoLibrary.SetEpisodeDetails",
        {
            "episodeid": episode_id,
            "playcount": playcount_before + 1,
            "lastplayed": time.strftime("%Y-%m-%d %H:%M:%S"),
            "resume": {"position": 0, "total": 0},
        },
    )
    ok = bool(response) and not response.get("error")
    if ok:
        log("Next episode: marked episode %s as watched" % episode_id)
    return ok


def schedule_mark_watched(monitor, episode_id, playcount_before) -> None:
    """Check the old episode a few seconds after the switch, off the service thread."""
    if not episode_id or playcount_before is None:
        return

    def work():
        try:
            if monitor.waitForAbort(MARK_WATCHED_DELAY_S):
                return
            mark_watched_if_needed(episode_id, playcount_before)
        except Exception as exc:
            log_error("Next episode: marking episode watched failed: %s" % exc)

    threading.Thread(target=work, daemon=True).start()
