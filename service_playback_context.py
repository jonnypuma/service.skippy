# -*- coding: utf-8 -*-
"""Cached playback metadata for the service monitor loop."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import xbmc
import xbmcvfs

from settings_utils import (
    addon_get_bool,
    get_addon,
    is_skip_dialog_enabled,
    log,
    log_service_detail,
    parse_kodi_jsonrpc_raw,
)


@dataclass
class PlaybackContext:
    video_path: Optional[str] = None
    is_playing: bool = False
    is_paused: bool = True
    current_time: float = 0.0
    player_item: dict = field(default_factory=dict)
    playback_type: str = ""
    toast_allowed: bool = False
    show_dialogs: bool = False
    toast_movies: bool = False
    toast_episodes: bool = False
    used_pause_fast_path: bool = False


def _player_state(player) -> tuple[bool, bool]:
    try:
        is_playing = player.isPlayingVideo()
        is_paused = xbmc.getCondVisibility("Player.Paused")
        return is_playing, is_paused
    except RuntimeError:
        return False, True


def _quiet_video_path(player) -> Optional[str]:
    """Resolve playing file without verbose logging (pause fast-path)."""
    try:
        if not (player.isPlayingVideo() or xbmc.getCondVisibility("Player.HasVideo")):
            return None
        path = player.getPlayingFile()
    except RuntimeError:
        return None
    if not path:
        return None
    try:
        if xbmcvfs.exists(path):
            return path
    except Exception:
        pass
    return None


def _fetch_player_item_via_jsonrpc(
    infer_playback_type: Callable[..., str],
    *,
    log_jsonrpc: bool,
) -> tuple[dict, bool]:
    """Return (item, toast_allowed). Empty item on failure."""
    addon = get_addon()
    show_not_found_toast_for_movies = (
        addon_get_bool(addon, "show_not_found_toast_for_movies", False) if addon else False
    )
    show_not_found_toast_for_tv_episodes = (
        addon_get_bool(addon, "show_not_found_toast_for_tv_episodes", False)
        if addon
        else False
    )

    query_active = {
        "jsonrpc": "2.0",
        "id": "getPlayers",
        "method": "Player.GetActivePlayers",
    }
    if log_jsonrpc:
        log_service_detail(
            "📨 JSON-RPC request: %s" % json.dumps(query_active), tag="jsonrpc"
        )
    try:
        response_active = xbmc.executeJSONRPC(json.dumps(query_active))
    except (TypeError, ValueError, AttributeError) as exc:
        if log_jsonrpc:
            log_service_detail(
                "executeJSONRPC(Player.GetActivePlayers) failed: %s" % exc,
                tag="jsonrpc",
            )
        return {}, False
    if log_jsonrpc:
        log_service_detail("📬 JSON-RPC response: %s" % response_active, tag="jsonrpc")

    active_result, err_a = parse_kodi_jsonrpc_raw(response_active)
    if err_a:
        if log_jsonrpc:
            log_service_detail("Player.GetActivePlayers parse: %s" % err_a, tag="jsonrpc")
        return {}, False
    active_players = active_result.get("result", [])

    if not active_players:
        if log_jsonrpc:
            log("⏳ No active players — retrying after 250ms")
        xbmc.sleep(250)
        try:
            retry_response = xbmc.executeJSONRPC(json.dumps(query_active))
        except (TypeError, ValueError, AttributeError) as exc:
            if log_jsonrpc:
                log_service_detail(
                    "executeJSONRPC(Player.GetActivePlayers retry) failed: %s" % exc,
                    tag="jsonrpc",
                )
            return {}, False
        if log_jsonrpc:
            log("📬 JSON-RPC retry response: %s" % retry_response)
        retry_result, err_r = parse_kodi_jsonrpc_raw(retry_response)
        if err_r:
            if log_jsonrpc:
                log_service_detail(
                    "Player.GetActivePlayers retry parse: %s" % err_r, tag="jsonrpc"
                )
            return {}, False
        active_players = retry_result.get("result", [])

    if not active_players:
        if log_jsonrpc:
            log_service_detail(
                "🚫 No active video player found — suppressing toast", tag="jsonrpc"
            )
        return {}, False

    video_player = next((p for p in active_players if p.get("type") == "video"), None)
    player_id = video_player.get("playerid") if video_player else None
    if player_id is None:
        if log_jsonrpc:
            log_service_detail(
                "🚫 No video player ID found — suppressing toast", tag="jsonrpc"
            )
        return {}, False

    query_item = {
        "jsonrpc": "2.0",
        "id": "VideoGetItem",
        "method": "Player.GetItem",
        "params": {
            "playerid": player_id,
            "properties": ["file", "title", "showtitle", "episode"],
        },
    }
    if log_jsonrpc:
        log_service_detail(
            "📨 JSON-RPC request: %s" % json.dumps(query_item), tag="jsonrpc"
        )
    try:
        response_item = xbmc.executeJSONRPC(json.dumps(query_item))
    except (TypeError, ValueError, AttributeError) as exc:
        if log_jsonrpc:
            log_service_detail(
                "executeJSONRPC(Player.GetItem) failed: %s" % exc, tag="jsonrpc"
            )
        return {}, False
    if log_jsonrpc:
        log_service_detail("📬 JSON-RPC response: %s" % response_item, tag="jsonrpc")

    item_result, err_i = parse_kodi_jsonrpc_raw(response_item)
    if err_i:
        if log_jsonrpc:
            log_service_detail("Player.GetItem parse: %s" % err_i, tag="jsonrpc")
        return {}, False
    item = item_result.get("result", {}).get("item", {}) or {}

    if not item:
        if log_jsonrpc:
            log("⚠ Player.GetItem returned empty item — metadata not ready")
        return {}, False
    if not item.get("title") and not item.get("label") and log_jsonrpc:
        log(
            "⚠ Player.GetItem missing title/label — metadata may still be loading "
            "(file-based inference will be used)"
        )

    return item, _toast_allowed_for_item(
        item,
        show_not_found_toast_for_movies,
        show_not_found_toast_for_tv_episodes,
        infer_playback_type=infer_playback_type,
        log_decision=log_jsonrpc,
    )


def _toast_allowed_for_item(
    item: dict,
    show_movies: bool,
    show_episodes: bool,
    *,
    infer_playback_type: Optional[Callable[..., str]],
    log_decision: bool,
) -> bool:
    playback_type = infer_playback_type(item)
    if log_decision:
        log("🧠 Inferred playback type: %s" % playback_type)
        log(
            "📁 File: %s, Title: %s, Showtitle: %s, Episode: %s"
            % (
                item.get("file"),
                item.get("title"),
                item.get("showtitle"),
                item.get("episode"),
            )
        )

    if playback_type == "movie":
        if not show_movies:
            if log_decision:
                log("🛑 Suppressing toast — movie playback and disabled in settings")
            return False
        if log_decision:
            log("✅ Toast allowed — movie playback and enabled in settings")
        return True
    if playback_type == "episode":
        if not show_episodes:
            if log_decision:
                log("🛑 Suppressing toast — episode playback and disabled in settings")
            return False
        if log_decision:
            log("✅ Toast allowed — episode playback and enabled in settings")
        return True
    if log_decision:
        log("⚠ Unknown playback type '%s' — suppressing toast" % playback_type)
    return False


def evaluate_toast_allowed(
    item: dict,
    playback_type: str,
    *,
    infer_playback_type: Callable[..., str],
) -> bool:
    """Settings-only toast gate when item/type already known (no JSON-RPC)."""
    addon = get_addon()
    show_movies = (
        addon_get_bool(addon, "show_not_found_toast_for_movies", False) if addon else False
    )
    show_episodes = (
        addon_get_bool(addon, "show_not_found_toast_for_tv_episodes", False)
        if addon
        else False
    )
    if playback_type:
        if playback_type == "movie":
            return show_movies
        if playback_type == "episode":
            return show_episodes
        return False
    if item:
        return _toast_allowed_for_item(
            item,
            show_movies,
            show_episodes,
            infer_playback_type=infer_playback_type,
            log_decision=False,
        )
    return False


def refresh_playback_context(
    ctx: Any,
    *,
    force: bool = False,
) -> Optional[PlaybackContext]:
    """
    Single entry for loop tick: player state, path, optional JSON-RPC metadata.

    Pause fast-path: when paused and video unchanged, skip JSON-RPC and heavy logging.
    """
    player = ctx.player
    monitor = ctx.monitor
    log_if_changed = ctx.log_if_changed
    infer_playback_type = ctx.infer_playback_type

    is_playing, is_paused = _player_state(player)

    cached = getattr(monitor, "_playback_context_cache", None)
    cached_video = getattr(monitor, "_playback_context_video", None)

    if is_paused and not force and cached and cached_video:
        video = _quiet_video_path(player)
        if video and video == cached_video:
            try:
                current_time = player.getTime()
            except RuntimeError:
                current_time = cached.current_time
            log_if_changed(
                "pause_state",
                "⏸️ Playback state: is_playing=%s, is_paused=%s (cached)"
                % (is_playing, is_paused),
            )
            return PlaybackContext(
                video_path=video,
                is_playing=is_playing,
                is_paused=is_paused,
                current_time=current_time,
                player_item=cached.player_item,
                playback_type=cached.playback_type,
                toast_allowed=cached.toast_allowed,
                show_dialogs=cached.show_dialogs,
                toast_movies=cached.toast_movies,
                toast_episodes=cached.toast_episodes,
                used_pause_fast_path=True,
            )

    video = ctx.get_video_file()
    if not video:
        log_if_changed("no_video", "⚠ get_video_file() returned None — skipping this cycle")
        return None

    log_if_changed("playback_path", "🎯 Kodi playback path: %s" % video)

    try:
        current_time = player.getTime()
        log_if_changed("playback_time", "⏱️ Playback time: %.2fs" % current_time)
    except RuntimeError:
        log("⚠ player.getTime() failed — no media playing")
        return None

    log_if_changed(
        "pause_state",
        "⏸️ Playback state: is_playing=%s, is_paused=%s" % (is_playing, is_paused),
    )

    need_jsonrpc = force or cached_video != video or cached is None
    player_item: dict = {}
    toast_allowed = False

    if need_jsonrpc:
        log_service_detail(
            "🚦 Fetching Player.GetItem (cache miss or video change)", tag="jsonrpc"
        )
        player_item, toast_allowed = _fetch_player_item_via_jsonrpc(
            infer_playback_type, log_jsonrpc=True
        )
    elif cached:
        player_item = cached.player_item
        toast_allowed = cached.toast_allowed

    playback_type = infer_playback_type(player_item) if player_item else ""
    log_if_changed("playback_type", "🔍 Playback type: '%s'" % playback_type)

    if not playback_type and video:
        synthetic = {
            "file": video,
            "title": os.path.basename(video),
            "showtitle": "",
            "episode": -1,
        }
        playback_type = infer_playback_type(synthetic)
        log_if_changed(
            "playback_type_fallback",
            "🔍 Playback type (fallback from path): '%s'" % playback_type,
        )

    addon = get_addon()
    show_dialogs = is_skip_dialog_enabled(playback_type)
    toast_movies = addon_get_bool(addon, "show_not_found_toast_for_movies", False)
    toast_episodes = addon_get_bool(addon, "show_not_found_toast_for_tv_episodes", False)
    log_if_changed(
        "settings",
        "🧪 Settings → show_dialogs: %s, toast_movies: %s, toast_episodes: %s"
        % (show_dialogs, toast_movies, toast_episodes),
    )

    if player_item and not toast_allowed:
        toast_allowed = evaluate_toast_allowed(
            player_item, playback_type, infer_playback_type=infer_playback_type
        )

    result = PlaybackContext(
        video_path=video,
        is_playing=is_playing,
        is_paused=is_paused,
        current_time=current_time,
        player_item=player_item,
        playback_type=playback_type,
        toast_allowed=toast_allowed,
        show_dialogs=show_dialogs,
        toast_movies=toast_movies,
        toast_episodes=toast_episodes,
        used_pause_fast_path=False,
    )

    monitor._playback_context_cache = result
    monitor._playback_context_video = video
    monitor._playback_was_paused = is_paused
    return result


def invalidate_playback_context_cache(monitor) -> None:
    monitor._playback_context_cache = None
    monitor._playback_context_video = None
