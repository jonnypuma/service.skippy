# -*- coding: utf-8 -*-
"""Non-blocking online segment probe when Local-first defers the dialog-path fetch.

With **Local first** and a local sidecar, segment parsing uses local data immediately so
the first skip dialog is not blocked by TheIntroDB / IntroDB network calls. When online
lookup is enabled, a background thread fetches merged online segments for **Save online
segments** and **Sync local → online**; results are applied on the main service thread
when no skip/editor/marker modal is open.
"""
from __future__ import annotations

import threading

from remote_segments import fetch_remote_movie_segments, fetch_remote_tv_segments
from settings_utils import log, log_service_detail

_PROBE_RUNNING = "running"


def clear_deferred_remote_probe_state(segment_monitor) -> None:
    """Drop pending/running probe state (new video, replay reset, service start)."""
    if segment_monitor is None:
        return
    lock = getattr(segment_monitor, "deferred_remote_probe_lock", None)
    if lock is None:
        segment_monitor.deferred_remote_probe_path = None
        segment_monitor.deferred_remote_probe_playback_type = None
        segment_monitor.deferred_remote_probe_local_list = None
        segment_monitor.deferred_remote_probe_local_file_found = False
        segment_monitor.deferred_remote_probe_result = None
        return
    with lock:
        segment_monitor.deferred_remote_probe_path = None
        segment_monitor.deferred_remote_probe_playback_type = None
        segment_monitor.deferred_remote_probe_local_list = None
        segment_monitor.deferred_remote_probe_local_file_found = False
        segment_monitor.deferred_remote_probe_result = None


def _probe_log_detail(msg: str) -> None:
    log_service_detail(msg, tag="remote_probe")


def _fetch_remote_for_playback(playback_type, segment_monitor, segment_player):
    try:
        total_time = segment_player.getTotalTime()
    except RuntimeError:
        total_time = 0
    cache = segment_monitor.remote_segment_cache
    if playback_type == "episode":
        return fetch_remote_tv_segments(total_time, cache) or []
    if playback_type == "movie":
        return fetch_remote_movie_segments(total_time, cache) or []
    return []


def schedule_deferred_remote_probe(
    segment_monitor,
    path,
    playback_type,
    local_list,
    local_file_found,
    segment_player,
):
    """Start a daemon thread to fetch online segments for sidecar save / sync."""
    if not path or not playback_type:
        return
    lock = segment_monitor.deferred_remote_probe_lock
    with lock:
        if segment_monitor.deferred_remote_probe_path == path:
            state = segment_monitor.deferred_remote_probe_result
            if state == _PROBE_RUNNING or isinstance(state, dict):
                return
        segment_monitor.deferred_remote_probe_path = path
        segment_monitor.deferred_remote_probe_playback_type = playback_type
        segment_monitor.deferred_remote_probe_local_list = list(local_list or [])
        segment_monitor.deferred_remote_probe_local_file_found = bool(local_file_found)
        segment_monitor.deferred_remote_probe_result = _PROBE_RUNNING

    log(
        "🌐 LocalFirst with local sidecar — online probe scheduled in background "
        "(save/sync; dialog path uses local segments)"
    )

    def _worker():
        remote_list = []
        try:
            remote_list = _fetch_remote_for_playback(
                playback_type, segment_monitor, segment_player
            )
        except Exception as exc:
            log("⚠ Deferred online probe failed: %s" % exc)
        with lock:
            if segment_monitor.deferred_remote_probe_path != path:
                return
            segment_monitor.deferred_remote_probe_result = {
                "path": path,
                "playback_type": playback_type,
                "remote_list": list(remote_list or []),
            }
        _probe_log_detail(
            "deferred probe complete: path=%r segments=%d"
            % (path, len(remote_list or []))
        )

    threading.Thread(target=_worker, daemon=True, name="skippy_remote_probe").start()


def _playback_allows_deferred_apply(segment_monitor) -> bool:
    if segment_monitor is None:
        return False
    if getattr(segment_monitor, "skip_dialog_modal_active", False):
        return False
    try:
        import xbmcgui

        win = xbmcgui.Window(10000)
        if win.getProperty("skippy_marker_modal_open") == "true":
            return False
        if win.getProperty("skippy_editor_modal_open") == "true":
            return False
        if win.getProperty("skippy_editor_session_modal") == "true":
            return False
    except Exception:
        pass
    return True


def process_deferred_remote_probe(
    segment_monitor,
    path,
    playback_type,
    on_remote_segments_saved,
    on_local_to_online_sync_check,
    segment_player,
):
    """Apply a completed background probe on the main service thread."""
    if not path or not playback_type or segment_monitor is None:
        return
    if not _playback_allows_deferred_apply(segment_monitor):
        return

    lock = segment_monitor.deferred_remote_probe_lock
    with lock:
        if segment_monitor.deferred_remote_probe_path != path:
            return
        if segment_monitor.deferred_remote_probe_playback_type != playback_type:
            return
        state = segment_monitor.deferred_remote_probe_result
        if state is None or state == _PROBE_RUNNING or not isinstance(state, dict):
            return
        local_list = list(segment_monitor.deferred_remote_probe_local_list or [])
        local_file_found = bool(segment_monitor.deferred_remote_probe_local_file_found)
        remote_list = list(state.get("remote_list") or [])
        segment_monitor.deferred_remote_probe_result = None
        segment_monitor.deferred_remote_probe_path = None
        segment_monitor.deferred_remote_probe_playback_type = None
        segment_monitor.deferred_remote_probe_local_list = None
        segment_monitor.deferred_remote_probe_local_file_found = False

    _probe_log_detail(
        "applying deferred probe: path=%r remote=%d local=%d"
        % (path, len(remote_list), len(local_list))
    )

    if remote_list and on_remote_segments_saved:
        try:
            on_remote_segments_saved(path, remote_list)
        except Exception as exc:
            log("⚠ Deferred probe save callback failed: %s" % exc)

    if not local_list or not local_file_found or not on_local_to_online_sync_check:
        return

    try:
        from service_segment_sources import _invoke_local_to_online_sync
    except Exception as exc:
        log("⚠ Deferred probe sync import failed: %s" % exc)
        return

    addon = None
    try:
        from settings_utils import get_addon

        addon = get_addon()
    except Exception:
        pass

    try:
        _invoke_local_to_online_sync(
            path,
            playback_type,
            local_list,
            local_file_found,
            True,
            remote_list,
            segment_monitor,
            segment_player,
            on_local_to_online_sync_check,
            addon,
        )
    except Exception as exc:
        log("⚠ Deferred probe sync callback failed: %s" % exc)
