# -*- coding: utf-8 -*-
"""Optional playback pause while blocking online segment API lookup runs."""
from __future__ import annotations

import xbmc

from settings_utils import addon_get_bool, get_addon, log_service_detail


def pause_during_online_lookup_enabled(addon=None) -> bool:
    ad = addon if addon is not None else get_addon()
    if not ad:
        return False
    return addon_get_bool(ad, "pause_during_online_lookup", False)


def pause_playback_for_online_lookup(player) -> bool:
    """Pause video if setting enabled and playback is active. Returns True if we paused."""
    if not pause_during_online_lookup_enabled():
        return False
    try:
        if not player.isPlayingVideo():
            return False
        if xbmc.getCondVisibility("Player.Paused"):
            return False
        player.pause()
        if xbmc.getCondVisibility("Player.Paused"):
            log_service_detail(
                "Paused playback during online segment lookup", tag="remote"
            )
            return True
    except RuntimeError:
        pass
    return False


def resume_playback_after_online_lookup(player, we_paused: bool) -> None:
    """Resume only if this session paused and the player is still paused."""
    if not we_paused:
        return
    try:
        if player.isPlayingVideo() and xbmc.getCondVisibility("Player.Paused"):
            player.pause()
            log_service_detail(
                "Resumed playback after online segment lookup", tag="remote"
            )
    except RuntimeError:
        pass


def run_blocking_online_lookup(player, fetch_callable):
    """Run a blocking remote fetch, optionally pausing playback around it."""
    we_paused = pause_playback_for_online_lookup(player)
    try:
        return fetch_callable()
    finally:
        resume_playback_after_online_lookup(player, we_paused)
