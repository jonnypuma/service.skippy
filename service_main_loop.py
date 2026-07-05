"""Service main monitor loop (playback, segments, skip UI)."""

from __future__ import annotations

import time
import traceback
from dataclasses import dataclass
from typing import Any, Callable

import xbmc
import xbmcgui

from segment_editor_utils import get_home_window
from service_loop_nested import handle_rewind_and_nested_segments
from service_loop_playback import handle_replay_detection, handle_video_change
from service_loop_skip import process_segment_skips
from service_loop_toast import (
    try_show_missing_segments_toast,
    try_show_online_segments_applied_toast,
)
from service_playback_context import refresh_playback_context
from settings_utils import log, log_service_detail


@dataclass(frozen=True)
class ServiceLoopBindings:
    monitor: Any
    player: Any
    check_interval: int
    icon_path: str
    get_video_file: Callable[..., Any]
    skippy_skip_ui_suppression_state: Callable[..., Any]
    log_if_changed: Callable[..., Any]
    infer_playback_type: Callable[..., Any]
    should_show_missing_file_toast: Callable[..., Any]
    both_segment_sources_disabled_for_playback: Callable[..., bool]
    missing_segments_toast_message: Callable[..., str]
    parse_and_process_segments: Callable[..., Any]
    should_suppress_segment_dialog: Callable[..., bool]
    re_evaluate_segment_jump_points: Callable[..., None]
    is_nested_segment: Callable[..., bool]
    skip_dialog_layout_suffix: Callable[..., str]
    warm_skip_dialog_skin_textures: Callable[..., None]
    process_deferred_remote_probe: Callable[..., None]
    clear_deferred_remote_probe_state: Callable[..., None]


def _parse_segments_with_deferred_probe(ctx: ServiceLoopBindings, video, current_time, playback_type):
    """Parse segments; apply deferred remote probe and optional re-parse."""
    if video and playback_type:
        try:
            ctx.process_deferred_remote_probe(video, playback_type)
        except Exception as exc:
            log_service_detail(
                "deferred remote probe apply failed: %s" % exc, tag="remote_probe"
            )

    if not playback_type:
        log("⚠ Playback type not detected — skipping segment parsing")
        ctx.monitor.current_segments = []
        return current_time

    parse_started = time.time()
    ctx.monitor.current_segments = (
        ctx.parse_and_process_segments(video, current_time, playback_type) or []
    )
    parse_elapsed_ms = int((time.time() - parse_started) * 1000)
    log(
        "📦 Parsed %d segments for playback_type: %s"
        % (len(ctx.monitor.current_segments), playback_type)
    )

    try:
        refreshed_time = ctx.player.getTime()
        if abs(refreshed_time - current_time) > 0.5:
            log(
                "⏱️ Playhead moved during segment parse (%.2fs → %.2fs, parse took %dms)"
                % (current_time, refreshed_time, parse_elapsed_ms)
            )
        current_time = refreshed_time
        ctx.log_if_changed("playback_time", "⏱️ Playback time: %.2fs" % current_time)
    except RuntimeError:
        pass

    segment_count_after_first_parse = len(ctx.monitor.current_segments)

    if video and playback_type:
        parse_cache_before_probe = ctx.monitor.segment_parse_cache
        try:
            ctx.process_deferred_remote_probe(video, playback_type)
        except Exception as exc:
            log_service_detail(
                "deferred remote probe apply failed: %s" % exc, tag="remote_probe"
            )
        deferred_remote_applied = (
            parse_cache_before_probe is not None
            and ctx.monitor.segment_parse_cache is None
        )
        stash_ready = getattr(ctx.monitor, "deferred_remote_playback_stash", None)
        has_playback_stash = (
            isinstance(stash_ready, dict)
            and stash_ready.get("path") == video
            and stash_ready.get("playback_type") == playback_type
            and stash_ready.get("remote_list")
        )
        reparsed = []
        if deferred_remote_applied or (
            not ctx.monitor.current_segments and has_playback_stash
        ):
            reparsed = ctx.parse_and_process_segments(
                video, current_time, playback_type
            ) or []
            if reparsed:
                ctx.monitor.current_segments = reparsed
                log(
                    "📦 Reparsed after deferred remote probe: %d segment(s)"
                    % len(reparsed)
                )
                try:
                    refreshed_time = ctx.player.getTime()
                    if abs(refreshed_time - current_time) > 0.5:
                        log(
                            "⏱️ Playhead moved during reparsed segments "
                            "(%.2fs → %.2fs)"
                            % (current_time, refreshed_time)
                        )
                    current_time = refreshed_time
                    ctx.log_if_changed(
                        "playback_time", "⏱️ Playback time: %.2fs" % current_time
                    )
                except RuntimeError:
                    pass
        new_count = len(ctx.monitor.current_segments)
        if reparsed or deferred_remote_applied:
            try_show_online_segments_applied_toast(
                ctx,
                video=video,
                previous_count=segment_count_after_first_parse,
                new_count=new_count,
            )

    return current_time


def run_service_main_loop(ctx: ServiceLoopBindings) -> None:
    """Monitor playback and orchestrate segment skip UI."""

    while not ctx.monitor.abortRequested():
        try:
            win = get_home_window(ctx.monitor)
            if win is None:
                raise RuntimeError("home window unavailable")
            skip_ui = ctx.skippy_skip_ui_suppression_state(win)
            if skip_ui.suppress:
                if skip_ui.pending_marker_blocks:
                    ctx.log_if_changed(
                        "skip_dlg_marker_pending",
                        "⏸️ Skip dialog suppressed — segment marker start is pending",
                    )
                if ctx.monitor.waitForAbort(ctx.check_interval):
                    log("🛑 Abort requested — exiting monitor loop")
                    break
                continue
        except RuntimeError:
            pass
        except Exception as e:
            log_service_detail(
                "marker/editor pending guard: unexpected %s: %s\n%s"
                % (type(e).__name__, e, traceback.format_exc()),
                tag="skipui",
            )

        if not (ctx.player.isPlayingVideo() or xbmc.getCondVisibility("Player.HasVideo")):
            if ctx.monitor.waitForAbort(ctx.check_interval):
                log("🛑 Abort requested — exiting monitor loop")
            continue

        playback = refresh_playback_context(ctx)
        if playback is None:
            if ctx.monitor.waitForAbort(ctx.check_interval):
                log("🛑 Abort requested — exiting monitor loop")
                break
            continue

        video = playback.video_path
        current_time = playback.current_time
        playback_type = playback.playback_type
        show_dialogs = playback.show_dialogs

        if playback.is_paused or not playback.is_playing:
            ctx.log_if_changed(
                "paused_all",
                "⏸️ Video paused or not playing — skipping ALL segment processing "
                "(is_playing=%s, is_paused=%s, fast_path=%s)"
                % (
                    playback.is_playing,
                    playback.is_paused,
                    playback.used_pause_fast_path,
                ),
            )
            if ctx.monitor.last_time == 0:
                ctx.monitor.last_time = current_time
            if ctx.monitor.waitForAbort(ctx.check_interval):
                log("🛑 Abort requested — exiting monitor loop")
            continue

        handle_replay_detection(ctx, video, current_time)
        handle_video_change(ctx, video)

        current_time = _parse_segments_with_deferred_probe(
            ctx, video, current_time, playback_type
        )

        if not show_dialogs:
            log(
                "🚫 Skip dialogs disabled for %s — segments will not trigger prompts"
                % playback_type
            )

        major_rewind_detected = handle_rewind_and_nested_segments(ctx, current_time)

        if not ctx.monitor.playback_ready and current_time > 0:
            ctx.monitor.playback_ready = True
            ctx.monitor.playback_ready_time = time.time()
            log("✅ Playback confirmed via getTime() — setting playback_ready = True")

        try_show_missing_segments_toast(
            ctx,
            video=video,
            playback_type=playback_type,
            toast_movies=playback.toast_movies,
            toast_episodes=playback.toast_episodes,
            current_time=current_time,
        )

        process_segment_skips(
            ctx,
            video=video,
            playback_type=playback_type,
            show_dialogs=show_dialogs,
            current_time=current_time,
            major_rewind_detected=major_rewind_detected,
        )

        try:
            if ctx.player.isPlayingVideo():
                ctx.monitor.last_time = ctx.player.getTime()
            else:
                ctx.monitor.last_time = current_time
        except RuntimeError:
            ctx.monitor.last_time = current_time

        if ctx.monitor.waitForAbort(ctx.check_interval):
            log("🛑 Abort requested — exiting monitor loop")
            break
