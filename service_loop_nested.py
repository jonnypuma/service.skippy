# -*- coding: utf-8 -*-
"""Rewind detection and nested-segment dismissal tracking."""

from __future__ import annotations

from typing import Any

import xbmc

from settings_utils import addon_get_int, get_addon, log


def handle_rewind_and_nested_segments(ctx: Any, current_time: float) -> bool:
    """
    Process rewind clears and nested-segment parent/exit tracking.

    Returns True when a major rewind was detected (for downstream re-evaluation).
    """
    monitor = ctx.monitor
    rewind_threshold = addon_get_int(
        get_addon(), "rewind_threshold_seconds", 8, minimum=2, maximum=30
    )
    major_rewind_detected = False

    rewind_detected = False
    if monitor.last_time > 0:
        rewind_detected = (
            current_time < monitor.last_time
            and monitor.last_time - current_time > rewind_threshold
        )
        if rewind_detected:
            log(
                "🔍 Rewind check: current=%.2f, last=%.2f, threshold=%d, difference=%.2f"
                % (
                    current_time,
                    monitor.last_time,
                    rewind_threshold,
                    monitor.last_time - current_time,
                )
            )

    if rewind_detected:
        try:
            is_playing_rewind = ctx.player.isPlayingVideo()
            is_paused_rewind = xbmc.getCondVisibility("Player.Paused")
            if not is_paused_rewind and is_playing_rewind:
                try:
                    final_rewind_playing = ctx.player.isPlayingVideo()
                    final_rewind_paused = xbmc.getCondVisibility("Player.Paused")
                    if final_rewind_paused or not final_rewind_playing:
                        log(
                            "🔕 CRITICAL: Rewind detected but paused - NOT clearing recently_dismissed"
                        )
                    else:
                        log(
                            "⏪ Significant rewind detected (%.2f → %.2f) — threshold: %ds"
                            % (monitor.last_time, current_time, rewind_threshold)
                        )
                        monitor.prompted.clear()
                        monitor.recently_dismissed.clear()
                        monitor.cleared_parent_dismissals.clear()
                        monitor.skipped_to_nested_segment.clear()
                        if monitor.current_segments:
                            ctx.re_evaluate_segment_jump_points(
                                monitor.current_segments, current_time
                            )
                        major_rewind_detected = True
                        log(
                            "🧹 recently_dismissed cleared due to rewind, nested segment tracking cleared"
                        )
                except RuntimeError:
                    log(
                        "🔕 CRITICAL: Cannot verify pause state during rewind - NOT clearing"
                    )
            else:
                log("⏪ Rewind detected but paused - NOT clearing recently_dismissed")
        except RuntimeError:
            log("⏪ Rewind detected but can't verify pause state - NOT clearing")

    _clear_parent_dismissals_when_inside_nested(ctx, current_time)
    _clear_dismissals_on_nested_exit(ctx, current_time)
    _cleanup_skipped_to_nested(ctx, current_time)
    return major_rewind_detected


def _clear_parent_dismissals_when_inside_nested(ctx: Any, current_time: float) -> None:
    monitor = ctx.monitor
    if not monitor.current_segments or not monitor.recently_dismissed:
        return

    ctx.log_if_changed(
        "nested_clear_check",
        "🔍 Checking nested segment clearing: %d segments, %d dismissed, current_time=%.2f"
        % (
            len(monitor.current_segments),
            len(monitor.recently_dismissed),
            current_time,
        ),
    )

    for nested_seg in monitor.current_segments:
        nested_seg_id = (
            int(round(nested_seg.start_seconds)),
            int(round(nested_seg.end_seconds)),
        )
        is_inside_nested = (
            current_time >= nested_seg.start_seconds
            and current_time <= nested_seg.end_seconds
        )

        has_parent = False
        parent_seg_for_nested = None
        for potential_parent in monitor.current_segments:
            if potential_parent != nested_seg and ctx.is_nested_segment(
                potential_parent, nested_seg
            ):
                has_parent = True
                parent_seg_for_nested = potential_parent
                break

        if not has_parent:
            continue

        ctx.log_if_changed(
            "nested_check_%s" % (nested_seg_id,),
            "🔍 Nested segment %s (%s): start=%.2f, end=%.2f, current=%.2f, is_inside=%s"
            % (
                nested_seg_id,
                nested_seg.segment_type_label,
                nested_seg.start_seconds,
                nested_seg.end_seconds,
                current_time,
                is_inside_nested,
            ),
        )

        if not is_inside_nested or not parent_seg_for_nested:
            continue

        parent_seg_id_check = (
            int(round(parent_seg_for_nested.start_seconds)),
            int(round(parent_seg_for_nested.end_seconds)),
        )
        if parent_seg_id_check not in monitor.recently_dismissed:
            continue

        clearance_key = (parent_seg_id_check, nested_seg_id)
        if clearance_key in monitor.cleared_parent_dismissals:
            continue

        if parent_seg_id_check in monitor.recently_dismissed:
            monitor.recently_dismissed.remove(parent_seg_id_check)
            monitor.cleared_parent_dismissals.add(clearance_key)
            log(
                "🔓 Cleared parent segment %s (%s) from recently_dismissed inside nested %s"
                % (
                    parent_seg_id_check,
                    parent_seg_for_nested.segment_type_label,
                    nested_seg.segment_type_label,
                )
            )
            if parent_seg_id_check in monitor.prompted:
                monitor.prompted.remove(parent_seg_id_check)


def _clear_dismissals_on_nested_exit(ctx: Any, current_time: float) -> None:
    monitor = ctx.monitor
    if not monitor.current_segments:
        return
    for nested_seg in monitor.current_segments:
        nested_seg_id_exit = (
            int(round(nested_seg.start_seconds)),
            int(round(nested_seg.end_seconds)),
        )
        if current_time > nested_seg.end_seconds:
            if nested_seg_id_exit in monitor.recently_dismissed:
                monitor.recently_dismissed.remove(nested_seg_id_exit)
                log(
                    "🔓 Removed nested segment %s (%s) from recently_dismissed after exit"
                    % (nested_seg_id_exit, nested_seg.segment_type_label)
                )


def _cleanup_skipped_to_nested(ctx: Any, current_time: float) -> None:
    monitor = ctx.monitor
    if monitor.skipped_to_nested_segment:
        ctx.log_if_changed(
            "checking_nested",
            "🔍 Checking %d tracked nested segments at time %.2f"
            % (len(monitor.skipped_to_nested_segment), current_time),
        )

    segments_to_remove = []
    for parent_seg_id, nested_segment in monitor.skipped_to_nested_segment.items():
        is_nested_active = nested_segment.is_active(current_time)
        ctx.log_if_changed(
            "nested_check_%s" % (parent_seg_id,),
            "🔍 Nested segment '%s' (%s-%s) active at %.2f: %s"
            % (
                nested_segment.segment_type_label,
                nested_segment.start_seconds,
                nested_segment.end_seconds,
                current_time,
                is_nested_active,
            ),
        )
        if is_nested_active:
            continue

        segments_to_remove.append(parent_seg_id)
        nested_seg_id = (
            int(round(nested_segment.start_seconds)),
            int(round(nested_segment.end_seconds)),
        )
        if nested_seg_id in monitor.recently_dismissed:
            monitor.recently_dismissed.remove(nested_seg_id)
            log(
                "🔓 Removed nested segment %s (%s) from recently_dismissed after exit"
                % (nested_seg_id, nested_segment.segment_type_label)
            )

        if parent_seg_id not in monitor.recently_dismissed:
            if parent_seg_id in monitor.prompted:
                monitor.prompted.remove(parent_seg_id)
                log(
                    "🔄 Exited nested segment '%s', re-enabled parent segment %s dialog"
                    % (nested_segment.segment_type_label, parent_seg_id)
                )
                for seg in monitor.current_segments:
                    seg_id_check = (
                        int(round(seg.start_seconds)),
                        int(round(seg.end_seconds)),
                    )
                    if seg_id_check == parent_seg_id:
                        seg.next_segment_start = None
                        seg.next_segment_info = None
                        break
            else:
                log(
                    "🔄 Exited nested segment '%s', parent %s was not in prompted set"
                    % (nested_segment.segment_type_label, parent_seg_id)
                )
        else:
            log(
                "🔄 Exited nested segment '%s', but parent %s was dismissed"
                % (nested_segment.segment_type_label, parent_seg_id)
            )

        if monitor.current_segments:
            ctx.re_evaluate_segment_jump_points(monitor.current_segments, current_time)

    for seg_id in segments_to_remove:
        del monitor.skipped_to_nested_segment[seg_id]
        log(
            "🗑️ Removed parent segment %s from skipped_to_nested_segment tracking"
            % (seg_id,)
        )
