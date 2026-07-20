# -*- coding: utf-8 -*-
"""Skip dialog orchestration and auto-skip for active segments."""

from __future__ import annotations

import traceback
from typing import Any

import xbmc
import xbmcgui

from segment_item import segments_active_for_playback
from segment_editor_utils import get_home_window
from settings_utils import (
    addon_get_bool,
    addon_get_int,
    addon_get_setting_text,
    compute_skip_seek_destination_seconds,
    get_addon,
    get_localized,
    get_user_skip_mode,
    is_skip_enabled,
    log,
    log_service_detail,
)
from service_skip_seek_property import mark_skippy_skipping
from skipdialog import SkipDialog


# Max chained seeks in one tick (recap→intro→…); prevents runaway auto-skip loops.
_MAX_SKIP_CHAIN_DEPTH = 8


def process_segment_skips(
    ctx: Any,
    *,
    video: str,
    playback_type: str,
    show_dialogs: bool,
    current_time: float,
    major_rewind_detected: bool,
    _chain_depth: int = 0,
    _skip_ask_debounce: bool = False,
) -> None:
    monitor = ctx.monitor
    addon = get_addon()

    if not monitor.playback_ready:
        ctx.log_if_changed(
            "playback_ready", "⏳ Playback not ready — waiting before processing segments"
        )
        monitor.last_time = current_time
        return

    segments_to_process = monitor.current_segments
    if major_rewind_detected:
        log("🔄 Major rewind detected — re-evaluating all segments for active dialogs")
        monitor._last_log_state.clear()

    ctx.log_if_changed(
        "state_summary",
        "📊 Current state: prompted=%d items, recently_dismissed=%d items, skipped_to_nested=%d items"
        % (
            len(monitor.prompted),
            len(monitor.recently_dismissed),
            len(monitor.skipped_to_nested_segment),
        ),
    )

    active_for_playback = segments_active_for_playback(monitor.current_segments, current_time)
    active_playback_ids = {
        (int(round(s.start_seconds)), int(round(s.end_seconds)))
        for s in active_for_playback
    }

    land_time = None

    for segment in segments_to_process:
        seg_id = (
            int(round(segment.start_seconds)),
            int(round(segment.end_seconds)),
        )

        if seg_id in monitor.recently_dismissed:
            ctx.log_if_changed(
                "dismissed_%s" % (seg_id,),
                "🚫 Segment %s (%s) was dismissed — skipping ALL processing"
                % (seg_id, segment.segment_type_label),
            )
            monitor.prompted.add(seg_id)
            continue

        if seg_id in monitor.prompted:
            continue

        if seg_id not in active_playback_ids:
            continue

        if ctx.should_suppress_segment_dialog(
            segment,
            monitor.current_segments,
            current_time,
            monitor.recently_dismissed,
        ):
            ctx.log_if_changed(
                "suppressed_%s" % (seg_id,),
                "🚫 Segment %s dialog suppressed due to overlapping/nested segment priority"
                % (seg_id,),
            )
            continue

        if seg_id in monitor.skipped_to_nested_segment:
            nested_segment = monitor.skipped_to_nested_segment[seg_id]
            if nested_segment.is_active(current_time):
                ctx.log_if_changed(
                    "nested_%s" % (seg_id,),
                    "🚫 Segment %s dialog suppressed — still in nested segment '%s'"
                    % (seg_id, nested_segment.segment_type_label),
                )
                continue
            nested_seg_id_defensive = (
                int(round(nested_segment.start_seconds)),
                int(round(nested_segment.end_seconds)),
            )
            if nested_seg_id_defensive in monitor.recently_dismissed:
                monitor.recently_dismissed.remove(nested_seg_id_defensive)
            del monitor.skipped_to_nested_segment[seg_id]
            if seg_id not in monitor.recently_dismissed and seg_id in monitor.prompted:
                monitor.prompted.remove(seg_id)

        ctx.log_if_changed(
            "active_seg_%s" % (seg_id,),
            "🔎 Processing active segment: '%s' [%s-%s]"
            % (
                segment.segment_type_label,
                segment.start_seconds,
                segment.end_seconds,
            ),
        )
        behavior = get_user_skip_mode(segment.segment_type_label)
        ctx.log_if_changed(
            "behavior_%s" % (seg_id,),
            "🧪 Segment behavior: %s" % behavior,
        )

        if not show_dialogs:
            ctx.log_if_changed(
                "dialogs_disabled_%s" % (seg_id,),
                "🚫 Dialogs disabled — suppressing segment %s" % (seg_id,),
            )
            monitor.prompted.add(seg_id)
            continue
        if behavior == "never":
            ctx.log_if_changed(
                "never_%s" % (seg_id,),
                "🚫 Skipping dialog for '%s' (never)" % segment.segment_type_label,
            )
            # Mark prompted so we do not re-resolve skip mode every monitor tick.
            monitor.prompted.add(seg_id)
            continue

        ctx.log_if_changed(
            "active_behavior_%s" % (seg_id,),
            "🕒 Active segment: %s [%s-%s] → %s"
            % (
                segment.segment_type_label,
                segment.start_seconds,
                segment.end_seconds,
                behavior,
            ),
        )

        if not is_skip_enabled(playback_type):
            log("🚫 Skipping disabled for %s — segment %s" % (playback_type, seg_id))
            monitor.prompted.add(seg_id)
            continue

        jump_to = compute_skip_seek_destination_seconds(segment, addon)

        if behavior == "auto":
            landed = _handle_auto_skip(ctx, segment, seg_id, jump_to, addon)
            if landed is not None:
                land_time = landed
                break
        elif behavior == "ask":
            landed = _handle_ask_skip(
                ctx,
                segment,
                seg_id,
                jump_to,
                addon,
                skip_debounce=_skip_ask_debounce,
            )
            if landed is not None:
                land_time = landed
                break

    if (
        land_time is not None
        and _chain_depth < _MAX_SKIP_CHAIN_DEPTH
        and monitor.playback_ready
    ):
        log_service_detail(
            "⛓️ Chaining skip processing at %.2fs (depth %d)"
            % (land_time, _chain_depth + 1),
            tag="playback",
        )
        process_segment_skips(
            ctx,
            video=video,
            playback_type=playback_type,
            show_dialogs=show_dialogs,
            current_time=float(land_time),
            major_rewind_detected=False,
            _chain_depth=_chain_depth + 1,
            _skip_ask_debounce=True,
        )


def _track_skip_to_nested(ctx: Any, segment, seg_id) -> None:
    monitor = ctx.monitor
    if segment.next_segment_start is None:
        return
    target_segment = None
    for seg in monitor.current_segments:
        if seg.start_seconds == segment.next_segment_start:
            target_segment = seg
            break
    if not target_segment or not ctx.is_nested_segment(segment, target_segment):
        return
    monitor.skipped_to_nested_segment[seg_id] = target_segment
    monitor.prompted.add(seg_id)
    if seg_id in monitor.recently_dismissed:
        nested_seg_id = (
            int(round(target_segment.start_seconds)),
            int(round(target_segment.end_seconds)),
        )
        clearance_key = (seg_id, nested_seg_id)
        if clearance_key not in monitor.cleared_parent_dismissals:
            monitor.recently_dismissed.remove(seg_id)
            monitor.cleared_parent_dismissals.add(clearance_key)


def _handle_auto_skip(ctx: Any, segment, seg_id, jump_to, addon) -> float | None:
    monitor = ctx.monitor
    log(
        "⚙ Auto-skip behavior triggered for segment ID %s (%s)"
        % (seg_id, segment.segment_type_label)
    )
    _track_skip_to_nested(ctx, segment, seg_id)
    log_service_detail("🎯 Auto-skip: Issuing seekTime(%s) now..." % jump_to, tag="playback")
    mark_skippy_skipping(monitor, addon)
    ctx.player.seekTime(jump_to)
    try:
        actual_time = ctx.player.getTime() if ctx.player.isPlaying() else -1
    except RuntimeError:
        actual_time = -1
    log_service_detail(
        "🎯 Auto-skip: After seek: requested=%s, actual=%s" % (jump_to, actual_time),
        tag="playback",
    )
    land = float(jump_to)
    monitor.last_time = land
    if seg_id not in monitor.prompted:
        monitor.prompted.add(seg_id)
    _maybe_show_skip_toast(ctx, addon, segment, "auto")
    log("⚡ Auto-skipped to %s" % jump_to)
    return land


def _handle_ask_skip(
    ctx: Any,
    segment,
    seg_id,
    jump_to,
    addon,
    *,
    skip_debounce: bool = False,
) -> float | None:
    monitor = ctx.monitor
    log(
        "🧠 Ask-skip behavior triggered for segment ID %s (%s)"
        % (seg_id, segment.segment_type_label)
    )

    try:
        dialog_is_playing = ctx.player.isPlayingVideo()
        dialog_is_paused = xbmc.getCondVisibility("Player.Paused")
    except RuntimeError:
        dialog_is_playing = False
        dialog_is_paused = True

    # After seekTime, Kodi often reports Paused briefly; allow ask while we hold
    # Skippy.Skipping so chained intro/recap dialogs are not deferred a full tick.
    post_skip_grace = getattr(monitor, "skippy_skipping_since", None) is not None
    if (dialog_is_paused or not dialog_is_playing) and not post_skip_grace:
        log("⏸️ Video paused/stopped right before dialog — skipping segment %s" % (seg_id,))
        return None

    try:
        home = get_home_window(ctx.monitor)
        editor_modal_open = (
            home is not None
            and home.getProperty("skippy_editor_modal_open") == "true"
        )
    except RuntimeError:
        editor_modal_open = False
    if editor_modal_open:
        ctx.log_if_changed(
            "skip_dlg_segment_editor_open",
            "⏸️ Skip dialog suppressed — Segment Editor is open",
        )
        return None

    if monitor.skip_dialog_modal_active:
        ctx.log_if_changed(
            "skip_dialog_in_flight",
            "⏳ Skip dialog already active — skipping duplicate ask for segment %s"
            % (seg_id,),
        )
        return None

    monitor.skip_dialog_modal_active = True
    try:
        debounce_ms = addon_get_int(addon, "ask_dialog_debounce_ms", 300, minimum=0, maximum=500)
        if debounce_ms > 0 and not skip_debounce:
            log("🛑 Debouncing skip dialog for %dms" % debounce_ms)
            xbmc.sleep(debounce_ms)

        dialog_mode = (
            addon_get_setting_text(addon, "skip_dialog_mode", "Full") or "Full"
        ).strip()
        if dialog_mode == "Minimal":
            layout_value = ctx.skip_dialog_layout_suffix(addon, "minimal_skip_dialog_position")
            dialog_name = "Minimal_Skip_Dialog_%s.xml" % layout_value
        else:
            layout_value = ctx.skip_dialog_layout_suffix(addon, "skip_dialog_position")
            dialog_name = "SkipDialog_%s.xml" % layout_value
        log("📐 Using skip dialog (%s): %s" % (dialog_mode, dialog_name))

        try:
            ctx.warm_skip_dialog_skin_textures(addon)
        except Exception as e:
            log("⚠️ Failed to update skip dialog skin XML: %s" % e)

        try:
            dialog = SkipDialog(
                dialog_name, addon.getAddonInfo("path"), "default", segment=segment
            )
        except Exception as e:
            log("❌ Failed to create skip dialog: %s" % e)
            monitor.prompted.add(seg_id)
            return None

        confirmed = None
        try:
            dialog.doModal()
        except Exception as e:
            log("❌ Dialog doModal() failed: %s" % e)
            monitor.prompted.add(seg_id)
            return None

        response = getattr(dialog, "_skippy_dialog_result", None)
        if response is None:
            response = getattr(dialog, "response", None)
        try:
            del dialog
        except Exception:
            pass

        log(
            "Skip dialog closed: response=%r jump_to=%s seg=%s"
            % (response, jump_to, seg_id)
        )

        if response is not False and response is not None:
            log("✅ User confirmed skip for segment ID %s" % (seg_id,))
            _track_skip_to_nested(ctx, segment, seg_id)
            if seg_id not in monitor.prompted:
                monitor.prompted.add(seg_id)
            log_service_detail("🎯 Issuing seekTime(%s) now..." % jump_to, tag="playback")
            try:
                mark_skippy_skipping(monitor, addon)
                ctx.player.seekTime(float(jump_to))
            except (TypeError, ValueError, RuntimeError) as exc:
                log("❌ seekTime(%s) failed: %s" % (jump_to, exc))
                return None
            try:
                actual_time = ctx.player.getTime() if ctx.player.isPlaying() else -1
            except RuntimeError:
                actual_time = -1
            log_service_detail(
                "🎯 After seek: requested=%s, actual=%s" % (jump_to, actual_time),
                tag="playback",
            )
            land = float(jump_to)
            monitor.last_time = land
            _maybe_show_skip_toast(ctx, addon, segment, "confirmed")
            log("🚀 Jumped to %s" % jump_to)
            return land
        elif response is False:
            log("🙅 User dismissed skip dialog for segment ID %s" % (seg_id,))
            monitor.recently_dismissed.add(seg_id)
            monitor.prompted.add(seg_id)
        else:
            log(
                "⚠ Skip dialog closed without a choice for segment %s — will retry"
                % (seg_id,)
            )
    except RuntimeError as e:
        log("❌ Error showing skip dialog (RuntimeError): %s" % e)
        monitor.prompted.add(seg_id)
    except Exception as e:
        log(
            "❌ Error showing skip dialog (%s): %s\n%s"
            % (type(e).__name__, e, traceback.format_exc())
        )
        monitor.prompted.add(seg_id)
    finally:
        monitor.skip_dialog_modal_active = False
    return None


def _maybe_show_skip_toast(ctx: Any, addon, segment, reason: str) -> None:
    if not addon_get_bool(addon, "show_toast_for_skipped_segment", False):
        log("🔕 Skipped segment toast disabled by user setting")
        return
    log("🔔 Showing toast notification for %s skip" % reason)
    try:
        xbmcgui.Dialog().notification(
            heading=get_localized(addon, 43003, "Skipped"),
            message=get_localized(
                addon, 43004, "%s skipped", segment.segment_type_label.title()
            ),
            icon=ctx.icon_path,
            time=2000,
            sound=False,
        )
    except Exception as e:
        log("❌ Failed to display skip toast notification: %s" % e)
