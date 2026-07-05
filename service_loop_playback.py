# -*- coding: utf-8 -*-
"""Video change, replay detection, and monitor state resets."""

from __future__ import annotations

import os
import time
from typing import Any

import xbmc

from playback_segment_cache import publish_parse_cache
from segment_item import segment_is_active_lenient
from service_playback_context import invalidate_playback_context_cache
from service_segment_processed_cache import clear_segment_processed_cache
from service_segment_prefetch import clear_tv_prefetch_thread_state
from service_sidecar_probe_cache import clear_sidecar_probe_cache
from settings_utils import log, log_playback_settings_snapshot


def reset_monitor_playback_state(ctx: Any, *, log_prefix: str) -> None:
    """Clear per-title monitor caches (new video, replay, etc.)."""
    monitor = ctx.monitor
    monitor.shown_missing_file_toast = False
    monitor.prompted.clear()
    monitor.recently_dismissed.clear()
    monitor.segment_parse_cache = None
    clear_segment_processed_cache(monitor)
    publish_parse_cache(None)
    monitor.cleared_parent_dismissals.clear()
    monitor.playback_ready = False
    monitor.play_start_time = time.time()
    monitor.last_time = 0
    monitor.last_toast_time = 0
    monitor.skipped_to_nested_segment.clear()
    monitor._last_log_state.clear()
    monitor.overlap_editor_opened_for_path = None
    monitor.online_sidecar_save_prompt_suppressed_path = None
    monitor.local_to_online_sync_suppressed_path = None
    monitor.prefetch_tv_scheduled_path = None
    monitor.nested_parent_map = {}
    monitor.online_segments_toast_shown_for_path = None
    monitor._home_window = None
    clear_tv_prefetch_thread_state(monitor)
    ctx.clear_deferred_remote_probe_state(monitor)
    invalidate_playback_context_cache(monitor)
    clear_sidecar_probe_cache(monitor)
    log("%s state cleared - recently_dismissed now has %d items" % (log_prefix, len(monitor.recently_dismissed)))


def handle_replay_detection(ctx: Any, video: str, current_time: float) -> None:
    """Detect genuine replay of the same file and reset session state."""
    monitor = ctx.monitor
    try:
        is_playing_replay = ctx.player.isPlayingVideo()
        is_paused_replay = xbmc.getCondVisibility("Player.Paused")
        if is_paused_replay or not is_playing_replay:
            return
        if not (
            video == monitor.last_video
            and monitor.playback_ready
            and current_time < 5.0
            and time.time() - monitor.playback_ready_time > 5.0
        ):
            return

        try:
            final_replay_playing = ctx.player.isPlayingVideo()
            final_replay_paused = xbmc.getCondVisibility("Player.Paused")
        except RuntimeError:
            log(
                "🔕 CRITICAL: Cannot verify pause state during replay - NOT clearing recently_dismissed"
            )
            return

        if final_replay_paused or not final_replay_playing:
            log(
                "🔕 CRITICAL: Replay detected but paused - NOT clearing recently_dismissed "
                "(is_playing=%s, is_paused=%s)"
                % (final_replay_playing, final_replay_paused)
            )
            return

        is_genuine_replay = monitor.last_time > 10.0
        if not is_genuine_replay:
            is_in_active_segment = False
            if monitor.current_segments:
                for seg in monitor.current_segments:
                    if segment_is_active_lenient(seg, current_time):
                        is_in_active_segment = True
                        break
            if is_in_active_segment:
                log(
                    "🔒 Replay detected but we're in an active segment at %.2fs - NOT clearing"
                    % current_time
                )
                return
            if current_time < 2.0 and monitor.last_time >= 5.0:
                is_genuine_replay = True
                log(
                    "🔍 Replay detected: current=%.2fs, last=%.2fs - treating as genuine replay"
                    % (current_time, monitor.last_time)
                )
            else:
                log(
                    "🔒 Replay detected but last_time=%.2fs is low - NOT clearing"
                    % monitor.last_time
                )
                return

        if not is_genuine_replay:
            return

        log("🔁 Replay of same video detected — resetting monitor state")
        log(
            "🔍 Debug: About to clear recently_dismissed (currently has %d items: %s)"
            % (len(monitor.recently_dismissed), list(monitor.recently_dismissed))
        )
        reset_monitor_playback_state(ctx, log_prefix="✅ Replay")
    except RuntimeError:
        pass


def handle_video_change(ctx: Any, video: str) -> None:
    """Detect new video path and reset monitor state when playing."""
    monitor = ctx.monitor
    if video == monitor.last_video:
        return

    try:
        is_playing_new = ctx.player.isPlayingVideo()
        is_paused_new = xbmc.getCondVisibility("Player.Paused")
    except RuntimeError:
        log(
            "🚀 Video path changed but can't verify pause state - updating last_video only"
        )
        monitor.last_video = video
        return

    if is_paused_new or not is_playing_new:
        log("🚀 Video path changed but paused - updating last_video only (not clearing state)")
        monitor.last_video = video
        return

    try:
        final_new_playing = ctx.player.isPlayingVideo()
        final_new_paused = xbmc.getCondVisibility("Player.Paused")
    except RuntimeError:
        log(
            "🔕 CRITICAL: Cannot verify pause state during new video detection - NOT clearing"
        )
        monitor.last_video = video
        return

    if final_new_paused or not final_new_playing:
        log(
            "🔕 CRITICAL: Video path changed but paused - NOT clearing recently_dismissed "
            "(is_playing=%s, is_paused=%s)"
            % (final_new_playing, final_new_paused)
        )
        monitor.last_video = video
        return

    log("🚀 New video detected: %s" % os.path.basename(video))
    log("🆕 New video detected — resetting monitor state")
    monitor.last_video = video
    monitor.segment_file_found = False
    monitor.remote_segment_cache.clear()
    monitor.toast_overlap_shown = False
    reset_monitor_playback_state(ctx, log_prefix="✅ New video")
    log_playback_settings_snapshot()
