"""Service main monitor loop (playback, segments, skip UI)."""

from __future__ import annotations

import os
import time
import traceback
from dataclasses import dataclass
from typing import Any, Callable

import xbmc
import xbmcgui

from marker_indicator import sync_marker_pending_indicator
from playback_segment_cache import publish_parse_cache
from segment_item import segments_active_for_playback, segment_is_active_lenient
from settings_utils import (
    addon_get_bool,
    addon_get_int,
    addon_get_setting_text,
    get_addon,
    get_user_skip_mode,
    is_skip_dialog_enabled,
    is_skip_enabled,
    log,
    log_playback_settings_snapshot,
    log_service_detail,
)
from skipdialog import SkipDialog, _minimal_plate_filename


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
    update_minimal_skip_dialog_textures: Callable[..., None]
    update_full_skip_dialog_textures: Callable[..., None]


def run_service_main_loop(ctx: ServiceLoopBindings) -> None:
    """Block until abort; body moved verbatim from service.py."""

    while not ctx.monitor.abortRequested():
        playback_active = False
        try:
            playback_active = ctx.player.isPlayingVideo() or xbmc.getCondVisibility(
                "Player.HasVideo"
            )
        except Exception:
            playback_active = False
        try:
            sync_marker_pending_indicator(playback_active)
        except Exception:
            pass
    
        try:
            win = xbmcgui.Window(10000)
            skip_ui = ctx.skippy_skip_ui_suppression_state(win)
            if skip_ui.suppress:
                if skip_ui.pending_marker_blocks:
                    ctx.log_if_changed(
                        "skip_dlg_marker_pending",
                        "⏸️ Skip dialog suppressed — segment marker start is pending for this file",
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
    
        if ctx.player.isPlayingVideo() or xbmc.getCondVisibility("Player.HasVideo"):
            video = ctx.get_video_file()
            if not video:
                ctx.log_if_changed("no_video", "⚠ get_video_file() returned None — skipping this cycle")
                # CRITICAL: Don't set last_video to None here - this causes video change detection to trigger incorrectly
                # when video becomes available again (e.g., after pause/resume)
                # Only clear last_video if we're sure playback has actually stopped
                continue
    
            if video:
                # 🔁 Detect replay of same video
                # CRITICAL: Only check if NOT paused - don't reset state when paused
                # CRITICAL: Do NOT clear recently_dismissed on replay if we have dismissed segments
                # This prevents clearing on resume from pause (which can look like a replay)
                try:
                    is_playing_replay = ctx.player.isPlayingVideo()
                    is_paused_replay = xbmc.getCondVisibility("Player.Paused")
                    if not is_paused_replay and is_playing_replay:
                        current_playback_time = ctx.player.getTime()
                        if (
                            video == ctx.monitor.last_video
                            and ctx.monitor.playback_ready
                            and current_playback_time < 5.0
                            and time.time() - ctx.monitor.playback_ready_time > 5.0
                        ):
                            # CRITICAL: Double-check pause state right before clearing
                            # CRITICAL: Use last_time to distinguish genuine replay from resume
                            # On genuine replay: playback jumps from higher position to < 5.0 seconds
                            # On resume: playback continues from where it was paused (won't jump to < 5.0)
                            try:
                                final_replay_playing = ctx.player.isPlayingVideo()
                                final_replay_paused = xbmc.getCondVisibility("Player.Paused")
                                if final_replay_paused or not final_replay_playing:
                                    log(f"🔕 CRITICAL: Replay detected but paused - NOT clearing recently_dismissed (is_playing={final_replay_playing}, is_paused={final_replay_paused})")
                                else:
                                    # Check if this is a genuine replay by comparing current position to last known position
                                    # If last_time was much higher (> 10s), this is likely a replay, not a resume
                                    is_genuine_replay = ctx.monitor.last_time > 10.0
                                    
                                    if not is_genuine_replay:
                                        # last_time is low - might be a resume from early in video
                                        # Also check if we're currently in any active segments
                                        is_in_active_segment = False
                                        if ctx.monitor.current_segments:
                                            for seg in ctx.monitor.current_segments:
                                                if segment_is_active_lenient(
                                                    seg, current_playback_time
                                                ):
                                                    is_in_active_segment = True
                                                    break
                                        
                                        if is_in_active_segment:
                                            log(f"🔒 Replay detected but we're in an active segment at {current_playback_time:.2f}s - NOT clearing (likely resume, not replay)")
                                        else:
                                            # Not in active segment and last_time is low - still might be a replay from very early
                                            # But to be safe, only clear if we're very close to start (< 2.0s) and last_time was at least 5s
                                            if current_playback_time < 2.0 and ctx.monitor.last_time >= 5.0:
                                                is_genuine_replay = True
                                                log(f"🔍 Replay detected: current={current_playback_time:.2f}s, last={ctx.monitor.last_time:.2f}s - treating as genuine replay")
                                            else:
                                                log(f"🔒 Replay detected but last_time={ctx.monitor.last_time:.2f}s is low - NOT clearing (likely resume from early position)")
                                    
                                    if is_genuine_replay:
                                        # This is a genuine replay - clear dismissed state so dialogs can reappear
                                        log("🔁 Replay of same video detected — resetting monitor state")
                                        log(f"🔍 Debug: About to clear recently_dismissed (currently has {len(ctx.monitor.recently_dismissed)} items: {list(ctx.monitor.recently_dismissed)})")
                                        log(f"🔍 Debug: Replay detected: current={current_playback_time:.2f}s, last={ctx.monitor.last_time:.2f}s")
                                        ctx.monitor.shown_missing_file_toast = False
                                        ctx.monitor.prompted.clear()
                                        ctx.monitor.recently_dismissed.clear()
                                        ctx.monitor.segment_parse_cache = None
                                        publish_parse_cache(None)
                                        log(f"🔍 Debug: recently_dismissed cleared - now has {len(ctx.monitor.recently_dismissed)} items")
                                        ctx.monitor.cleared_parent_dismissals.clear()
                                        ctx.monitor.playback_ready = False
                                        ctx.monitor.play_start_time = time.time()
                                        ctx.monitor.last_time = 0
                                        ctx.monitor.last_toast_time = 0
                                        # CRITICAL: Do NOT reset toast_overlap_shown on replay - it should only show once per video
                                        # Only reset on new video (see line 766)
                                        ctx.monitor.skipped_to_nested_segment.clear()
                                        # Clear log cache on replay to allow re-logging
                                        ctx.monitor._last_log_state.clear()
                                        ctx.monitor.overlap_editor_opened_for_path = None
                                        log(f"✅ Replay state cleared - recently_dismissed now has {len(ctx.monitor.recently_dismissed)} items")
                            except RuntimeError:
                                log(f"🔕 CRITICAL: Cannot verify pause state during replay - NOT clearing recently_dismissed to prevent clearing on pause")
                except RuntimeError:
                    # Playback may have stopped, skip replay detection
                    pass
    
                # Only log when video changes
                # CRITICAL: Video path change = new video, so clear recently_dismissed
                # The video path does NOT change on pause/resume, only when a different video is playing
                if video != ctx.monitor.last_video:
                    try:
                        is_playing_new = ctx.player.isPlayingVideo()
                        is_paused_new = xbmc.getCondVisibility("Player.Paused")
                        
                        if not is_paused_new and is_playing_new:
                            # CRITICAL: Double-check pause state right before clearing
                            try:
                                final_new_playing = ctx.player.isPlayingVideo()
                                final_new_paused = xbmc.getCondVisibility("Player.Paused")
                                if final_new_paused or not final_new_playing:
                                    log(f"🔕 CRITICAL: Video path changed but paused - NOT clearing recently_dismissed (is_playing={final_new_playing}, is_paused={final_new_paused})")
                                    ctx.monitor.last_video = video  # Still update last_video
                                else:
                                    # Video path changed and we're playing - this is a new video
                                    log(f"🚀 New video detected: {os.path.basename(video)}")
                                    log("🆕 New video detected — resetting monitor state")
                                    log(f"🔍 Debug: About to clear recently_dismissed (currently has {len(ctx.monitor.recently_dismissed)} items: {list(ctx.monitor.recently_dismissed)})")
                                    ctx.monitor.last_video = video
                                    ctx.monitor.segment_file_found = False
                                    ctx.monitor.remote_segment_cache.clear()
                                    ctx.monitor.segment_parse_cache = None
                                    publish_parse_cache(None)
                                    ctx.monitor.shown_missing_file_toast = False
                                    ctx.monitor.prompted.clear()
                                    ctx.monitor.recently_dismissed.clear()
                                    log(f"🔍 Debug: recently_dismissed cleared - now has {len(ctx.monitor.recently_dismissed)} items")
                                    ctx.monitor.cleared_parent_dismissals.clear()
                                    ctx.monitor.playback_ready = False
                                    ctx.monitor.play_start_time = time.time()
                                    ctx.monitor.last_time = 0
                                    ctx.monitor.last_toast_time = 0
                                    ctx.monitor.toast_overlap_shown = False
                                    ctx.monitor.skipped_to_nested_segment.clear()
                                    ctx.monitor.overlap_editor_opened_for_path = None
                                    # Clear log cache on new video to allow re-logging
                                    ctx.monitor._last_log_state.clear()
                                    log(f"✅ New video state cleared - recently_dismissed now has {len(ctx.monitor.recently_dismissed)} items")
                                    log_playback_settings_snapshot()
                            except RuntimeError:
                                log(f"🔕 CRITICAL: Cannot verify pause state during new video detection - NOT clearing recently_dismissed to prevent clearing on pause/resume")
                                ctx.monitor.last_video = video  # Still update last_video
                        else:
                            # Video changed but paused - just update last_video, don't clear state
                            log(f"🚀 Video path changed but paused - updating last_video only (not clearing state)")
                            ctx.monitor.last_video = video
                    except RuntimeError:
                        # If we can't check pause state, be safe and don't clear
                        log(f"🚀 Video path changed but can't verify pause state - updating last_video only (not clearing state)")
                        ctx.monitor.last_video = video
                
                addon = get_addon()
                try:
                    allow_toast, item = ctx.should_show_missing_file_toast()
                    playback_type = ctx.infer_playback_type(item) if item else ""
                    ctx.log_if_changed("playback_type", f"🔍 Playback type: '{playback_type}'")
                except Exception as e:
                    log(f"❌ JSON-RPC / toast path failed ({type(e).__name__}): {e}")
                    item = None
                    playback_type = ""
                if not playback_type and video:
                    synthetic = {
                        "file": video,
                        "title": os.path.basename(video),
                        "showtitle": "",
                        "episode": -1,
                    }
                    playback_type = ctx.infer_playback_type(synthetic)
                    ctx.log_if_changed(
                        "playback_type_fallback",
                        f"🔍 Playback type (fallback from path): '{playback_type}'",
                    )
    
                show_dialogs = is_skip_dialog_enabled(playback_type)
                toast_movies = addon_get_bool(addon, "show_not_found_toast_for_movies", False)
                toast_episodes = addon_get_bool(addon, "show_not_found_toast_for_tv_episodes", False)
    
                ctx.log_if_changed("settings", f"🧪 Settings → show_dialogs: {show_dialogs}, toast_movies: {toast_movies}, toast_episodes: {toast_episodes}")
    
            try:
                current_time = ctx.player.getTime()
                # Only log time changes, not every second
                ctx.log_if_changed("playback_time", f"⏱️ Playback time: {current_time:.2f}s")
            except RuntimeError:
                log("⚠ player.getTime() failed — no media playing")
                continue
    
            # Check if playback is paused - do this FIRST, before any segment processing
            # Initialize to safe defaults (assume paused to be safe)
            is_playing = False
            is_paused = True
            try:
                is_playing = ctx.player.isPlayingVideo()
                is_paused = xbmc.getCondVisibility("Player.Paused")
            except RuntimeError:
                is_playing = False
                is_paused = True
            
            # Log pause state changes for debugging (use log_if_changed to reduce clutter)
            ctx.log_if_changed("pause_state", f"⏸️ Playback state: is_playing={is_playing}, is_paused={is_paused}")
            
            # CRITICAL: If video is paused or not playing, skip ALL segment processing
            # This prevents ANY dialogs from appearing when paused, regardless of dismissal status
            # This also prevents parse_and_process_segments from being called when paused, which prevents toast spamming
            if is_paused or not is_playing:
                # Log pause state (use log_if_changed to reduce clutter, but log when state changes)
                ctx.log_if_changed("paused_all", f"⏸️ Video paused or not playing — skipping ALL segment processing (is_playing={is_playing}, is_paused={is_paused})")
                # CRITICAL: Don't update last_time when paused - this could cause issues with rewind detection
                # Only update last_time if we were previously playing (to track position)
                if ctx.monitor.last_time == 0:
                    ctx.monitor.last_time = current_time
                continue
    
            # Only parse segments when NOT paused
            if not playback_type:
                log("⚠ Playback type not detected — skipping segment parsing")
                ctx.monitor.current_segments = []
            else:
                # CRITICAL: Only call parse_and_process_segments when NOT paused
                # This prevents toast spamming when paused
                ctx.monitor.current_segments = ctx.parse_and_process_segments(
                    video, current_time, playback_type
                ) or []
                log(f"📦 Parsed {len(ctx.monitor.current_segments)} segments for playback_type: {playback_type}")
    
            if not show_dialogs:
                log(f"🚫 Skip dialogs disabled for {playback_type} — segments will not trigger prompts")
    
            rewind_threshold = addon_get_int(
                get_addon(), "rewind_threshold_seconds", 8, minimum=2, maximum=30
            )
            major_rewind_detected = False
            
            # Check for rewind BEFORE updating last_time
            if ctx.monitor.last_time > 0:  # Only check if we have a previous time
                rewind_detected = current_time < ctx.monitor.last_time and ctx.monitor.last_time - current_time > rewind_threshold
                if rewind_detected:
                    log(f"🔍 Rewind check: current={current_time:.2f}, last={ctx.monitor.last_time:.2f}, threshold={rewind_threshold}, difference={ctx.monitor.last_time - current_time:.2f}")
            else:
                rewind_detected = False
            
            if rewind_detected:
                # CRITICAL: Only clear state if NOT paused - don't clear dismissals when paused
                # The pause check above should prevent this, but add defensive check here too
                try:
                    is_playing_rewind = ctx.player.isPlayingVideo()
                    is_paused_rewind = xbmc.getCondVisibility("Player.Paused")
                    if not is_paused_rewind and is_playing_rewind:
                        # CRITICAL: Double-check pause state right before clearing
                        try:
                            final_rewind_playing = ctx.player.isPlayingVideo()
                            final_rewind_paused = xbmc.getCondVisibility("Player.Paused")
                            if final_rewind_paused or not final_rewind_playing:
                                log(f"🔕 CRITICAL: Rewind detected but paused - NOT clearing recently_dismissed (is_playing={final_rewind_playing}, is_paused={final_rewind_paused})")
                            else:
                                log(f"⏪ Significant rewind detected ({ctx.monitor.last_time:.2f} → {current_time:.2f}) — threshold: {rewind_threshold}s")
                                log(f"🔍 Debug: About to clear recently_dismissed (currently has {len(ctx.monitor.recently_dismissed)} items: {list(ctx.monitor.recently_dismissed)})")
                                ctx.monitor.prompted.clear()
                                ctx.monitor.recently_dismissed.clear()
                                log(f"🔍 Debug: recently_dismissed cleared - now has {len(ctx.monitor.recently_dismissed)} items")
                                ctx.monitor.cleared_parent_dismissals.clear()
                                ctx.monitor.skipped_to_nested_segment.clear()
                                
                                # Re-evaluate segment jump points after major rewind to ensure correct jump targets
                                if ctx.monitor.current_segments:
                                    ctx.re_evaluate_segment_jump_points(ctx.monitor.current_segments, current_time)
                                
                                major_rewind_detected = True
                                log("🧹 recently_dismissed cleared due to rewind, nested segment tracking cleared, jump points re-evaluated")
                                log(f"✅ Rewind state cleared - recently_dismissed now has {len(ctx.monitor.recently_dismissed)} items")
                        except RuntimeError:
                            log(f"🔕 CRITICAL: Cannot verify pause state during rewind - NOT clearing recently_dismissed to prevent clearing on pause")
                    else:
                        log(f"⏪ Rewind detected but paused - NOT clearing recently_dismissed")
                except RuntimeError:
                    log(f"⏪ Rewind detected but can't verify pause state - NOT clearing recently_dismissed")
            
            # CRITICAL: Check if we're inside a nested segment and clear its parent from recently_dismissed
            # Only clear when we're actually INSIDE the nested segment (current_time is past nested segment start)
            # This allows parent dialog to reappear after nested segment ends
            # CRITICAL: This check happens AFTER the pause check, so it only runs when NOT paused
            # NOTE: This handles natural entry into nested segments (not explicit skips)
            # Explicit skips handle clearing in the skip blocks above
            if ctx.monitor.current_segments and ctx.monitor.recently_dismissed:
                # Only proceed if we have segments and dismissed items
                ctx.log_if_changed("nested_clear_check", f"🔍 Checking nested segment clearing: {len(ctx.monitor.current_segments)} segments, {len(ctx.monitor.recently_dismissed)} dismissed, current_time={current_time:.2f}")
                
                # CRITICAL: First, identify which segments are actually nested (have a parent)
                # We only want to process segments that are nested inside other segments
                for nested_seg in ctx.monitor.current_segments:
                    nested_seg_id = (int(round(nested_seg.start_seconds)), int(round(nested_seg.end_seconds)))
                    is_inside_nested = (current_time >= nested_seg.start_seconds and current_time <= nested_seg.end_seconds)
                    
                    # CRITICAL: Only process if we're inside this segment AND it's actually nested (has a parent)
                    # Check if this segment has a parent by looking for segments that contain it
                    has_parent = False
                    parent_seg_for_nested = None
                    for potential_parent in ctx.monitor.current_segments:
                        if potential_parent != nested_seg and ctx.is_nested_segment(potential_parent, nested_seg):
                            has_parent = True
                            parent_seg_for_nested = potential_parent
                            break
                    
                    if not has_parent:
                        # This segment is not nested, skip it
                        continue
                    
                    ctx.log_if_changed(f"nested_check_{nested_seg_id}", f"🔍 Nested segment {nested_seg_id} ({nested_seg.segment_type_label}): start={nested_seg.start_seconds:.2f}, end={nested_seg.end_seconds:.2f}, current={current_time:.2f}, is_inside={is_inside_nested}, has_parent={has_parent}")
                    
                    if is_inside_nested:
                        # CRITICAL: When entering a nested segment naturally, ONLY clear the parent segment from recently_dismissed
                        # Do NOT clear the nested segment itself - if it was dismissed, it should stay dismissed until we exit it
                        # The nested segment will be cleared from recently_dismissed when we EXIT it (see exit logic below)
                        
                        # CRITICAL: Check if the parent segment was dismissed and clear it
                        if parent_seg_for_nested:
                            parent_seg_id_check = (int(round(parent_seg_for_nested.start_seconds)), int(round(parent_seg_for_nested.end_seconds)))
                            is_parent_dismissed = parent_seg_id_check in ctx.monitor.recently_dismissed
                            
                            log(f"🔍 Inside nested segment {nested_seg_id} ({nested_seg.segment_type_label}) - checking parent {parent_seg_id_check} ({parent_seg_for_nested.segment_type_label}): dismissed={is_parent_dismissed}")
                            log(f"🔍 Debug: recently_dismissed contains: {list(ctx.monitor.recently_dismissed)}")
                            
                            if is_parent_dismissed:
                                # Use a key to track that we've cleared this parent for this nested segment
                                clearance_key = (parent_seg_id_check, nested_seg_id)
                                if clearance_key not in ctx.monitor.cleared_parent_dismissals:
                                    # First time clearing for this parent-nested pair - we're inside the nested segment
                                    log(f"🔓 About to clear parent segment {parent_seg_id_check} from recently_dismissed (currently has {len(ctx.monitor.recently_dismissed)} items: {list(ctx.monitor.recently_dismissed)})")
                                    if parent_seg_id_check in ctx.monitor.recently_dismissed:
                                        ctx.monitor.recently_dismissed.remove(parent_seg_id_check)
                                        ctx.monitor.cleared_parent_dismissals.add(clearance_key)
                                        log(f"🔓 SUCCESS: Cleared parent segment {parent_seg_id_check} ({parent_seg_for_nested.segment_type_label}) from recently_dismissed because we're inside nested segment {nested_seg.segment_type_label} (current_time={current_time:.2f})")
                                        log(f"🔍 Debug: recently_dismissed now has {len(ctx.monitor.recently_dismissed)} items: {list(ctx.monitor.recently_dismissed)}")
                                        # CRITICAL: Also remove parent from prompted so its dialog can show again after nested segment ends
                                        if parent_seg_id_check in ctx.monitor.prompted:
                                            ctx.monitor.prompted.remove(parent_seg_id_check)
                                            log(f"🔓 Also removed parent segment {parent_seg_id_check} from prompted set so dialog can show again after nested segment ends")
                                            log(f"🔍 Debug: prompted now has {len(ctx.monitor.prompted)} items: {list(ctx.monitor.prompted)}")
                                    else:
                                        log(f"⚠️ WARNING: Parent {parent_seg_id_check} was supposed to be in recently_dismissed but wasn't found!")
                                else:
                                    log(f"🔍 Already cleared parent {parent_seg_id_check} for nested {nested_seg_id} - skipping (clearance_key already exists)")
                            else:
                                log(f"🔍 Parent {parent_seg_id_check} is not dismissed, no need to clear")
            
            # CRITICAL: Check if we've exited any nested segments (both skipped-to and naturally entered)
            # and remove them from recently_dismissed if they were dismissed
            # This must happen BEFORE processing segments so that parent dialogs can show immediately
            if ctx.monitor.current_segments:
                for nested_seg in ctx.monitor.current_segments:
                    nested_seg_id_exit = (int(round(nested_seg.start_seconds)), int(round(nested_seg.end_seconds)))
                    # Check if we're no longer inside this nested segment
                    if current_time > nested_seg.end_seconds:
                        # We've exited this nested segment - clear it from recently_dismissed so it can show again if re-entered
                        if nested_seg_id_exit in ctx.monitor.recently_dismissed:
                            ctx.monitor.recently_dismissed.remove(nested_seg_id_exit)
                            log(f"🔓 Removed nested segment {nested_seg_id_exit} ({nested_seg.segment_type_label}) from recently_dismissed after exiting nested segment")
                            log(f"🔍 Debug: recently_dismissed now has {len(ctx.monitor.recently_dismissed)} items: {list(ctx.monitor.recently_dismissed)}")
            
            # Check if we've exited any nested segments we skipped to and need to re-enable parent segment dialogs
            if ctx.monitor.skipped_to_nested_segment:
                ctx.log_if_changed("checking_nested", f"🔍 Checking {len(ctx.monitor.skipped_to_nested_segment)} tracked nested segments at time {current_time:.2f}")
            
            segments_to_remove = []
            for parent_seg_id, nested_segment in ctx.monitor.skipped_to_nested_segment.items():
                # Check if we're no longer in the nested segment
                is_nested_active = nested_segment.is_active(current_time)
                ctx.log_if_changed(f"nested_check_{parent_seg_id}", f"🔍 Nested segment '{nested_segment.segment_type_label}' ({nested_segment.start_seconds}-{nested_segment.end_seconds}) active at {current_time:.2f}: {is_nested_active}")
                
                if not is_nested_active:
                    # We've exited the nested segment, remove from tracking
                    segments_to_remove.append(parent_seg_id)
                    
                    # CRITICAL: Remove nested segment from recently_dismissed if it was dismissed
                    # The nested segment dismissal should only last until we exit the nested segment
                    nested_seg_id = (int(round(nested_segment.start_seconds)), int(round(nested_segment.end_seconds)))
                    if nested_seg_id in ctx.monitor.recently_dismissed:
                        ctx.monitor.recently_dismissed.remove(nested_seg_id)
                        log(f"🔓 Removed nested segment {nested_seg_id} ({nested_segment.segment_type_label}) from recently_dismissed after exiting nested segment")
                        log(f"🔍 Debug: recently_dismissed now has {len(ctx.monitor.recently_dismissed)} items: {list(ctx.monitor.recently_dismissed)}")
                    
                    # Re-enable the parent segment dialog by removing it from prompted set
                    # BUT: Only if the parent was NOT dismissed by the user
                    if parent_seg_id not in ctx.monitor.recently_dismissed:
                        if parent_seg_id in ctx.monitor.prompted:
                            ctx.monitor.prompted.remove(parent_seg_id)
                            log(f"🔄 Exited nested segment '{nested_segment.segment_type_label}', re-enabled parent segment {parent_seg_id} dialog (removed from prompted)")
                            # CRITICAL: Re-evaluate jump points for the parent segment to ensure it can show its dialog
                            # Find the parent segment in current_segments and update its jump point
                            for seg in ctx.monitor.current_segments:
                                # Use same seg_id format as main loop (round then int) for consistent matching
                                seg_id_check = (int(round(seg.start_seconds)), int(round(seg.end_seconds)))
                                if seg_id_check == parent_seg_id:
                                    # Re-evaluate jump point for this parent segment
                                    seg.next_segment_start = None
                                    seg.next_segment_info = None
                                    log(f"🔄 Reset jump point for parent segment {parent_seg_id} to allow dialog to show")
                                    break
                        else:
                            log(f"🔄 Exited nested segment '{nested_segment.segment_type_label}', parent segment {parent_seg_id} was not in prompted set (will show if active)")
                    else:
                        log(f"🔄 Exited nested segment '{nested_segment.segment_type_label}', but parent segment {parent_seg_id} was dismissed — NOT re-enabling")
                    
                    # Re-evaluate segment jump points since we've exited a nested segment
                    if ctx.monitor.current_segments:
                        log(f"🔄 Re-evaluating jump points after exiting nested segment '{nested_segment.segment_type_label}'")
                        ctx.re_evaluate_segment_jump_points(ctx.monitor.current_segments, current_time)
            
            # Remove exited nested segments from tracking
            for seg_id in segments_to_remove:
                del ctx.monitor.skipped_to_nested_segment[seg_id]
                log(f"🗑️ Removed parent segment {seg_id} from skipped_to_nested_segment tracking")
    
            if not ctx.monitor.playback_ready and current_time > 0:
                ctx.monitor.playback_ready = True
                ctx.monitor.playback_ready_time = time.time()
                log("✅ Playback confirmed via getTime() — setting playback_ready = True")
    
            if (
                ctx.monitor.playback_ready
                and not ctx.monitor.shown_missing_file_toast
                and time.time() - ctx.monitor.playback_ready_time >= 2
                and not ctx.monitor.segment_file_found
                and not ctx.both_segment_sources_disabled_for_playback(playback_type)
            ):
                # CRITICAL: Check if playback is paused BEFORE showing toast to prevent spamming when paused
                try:
                    toast_is_playing = ctx.player.isPlayingVideo()
                    toast_is_paused = xbmc.getCondVisibility("Player.Paused")
                    if toast_is_paused or not toast_is_playing:
                        log(f"🔕 Missing segments toast suppressed — playback is paused or not playing (is_playing={toast_is_playing}, is_paused={toast_is_paused})")
                        # Don't set shown_missing_file_toast = True here - allow retry when resumed
                        # This prevents the toast from being suppressed permanently when paused
                    else:
                        log("⚠ [TOAST BLOCK] Entered toast logic block")
                        try:
                            toast_enabled = (
                                (playback_type == "movie" and toast_movies) or
                                (playback_type == "episode" and toast_episodes)
                            )
    
                            if toast_enabled:
                                cooldown = 6
                                now = time.time()
                                if now - ctx.monitor.last_toast_time >= cooldown:
                                    msg_type = "episode" if playback_type == "episode" else "movie"
                                    log(f"🔔 Attempting to show toast notification for missing segments ({msg_type})")
    
                                    # CRITICAL: Double-check pause state right before showing toast
                                    try:
                                        final_toast_is_playing = ctx.player.isPlayingVideo()
                                        final_toast_is_paused = xbmc.getCondVisibility("Player.Paused")
                                        if final_toast_is_paused or not final_toast_is_playing:
                                            log(f"🔕 Missing segments toast suppressed — playback paused right before showing (is_playing={final_toast_is_playing}, is_paused={final_toast_is_paused})")
                                        else:
                                            try:
                                                toast_msg = ctx.missing_segments_toast_message(
                                                    playback_type, video
                                                )
                                                xbmcgui.Dialog().notification(
                                                    heading="Skippy",
                                                    message=toast_msg,
                                                    icon=ctx.icon_path,
                                                    time=3000,
                                                    sound=False
                                                )
                                                ctx.monitor.last_toast_time = now
                                                ctx.monitor.shown_missing_file_toast = True
                                                log(f"✅ Toast displayed for {msg_type}")
                                            except RuntimeError as e:
                                                log(
                                                    f"❌ Failed to display missing segments toast notification: {e}"
                                                )
                                            except (OSError, ValueError, TypeError, AttributeError) as e:
                                                log(
                                                    f"❌ Failed to display missing segments toast notification ({type(e).__name__}): {e}"
                                                )
                                            except Exception as e:
                                                log(
                                                    f"❌ Failed to display missing segments toast notification ({type(e).__name__}): {e}"
                                                )
                                    except RuntimeError:
                                        log("🔕 Missing segments toast suppressed — player state unavailable right before showing")
                                else:
                                    log(f"⏳ [TOAST BLOCK] Suppressed — cooldown active ({int(now - ctx.monitor.last_toast_time)}s since last toast)")
                            else:
                                log("✅ [TOAST BLOCK] Toast suppressed — toast toggle disabled for this type")
                                ctx.monitor.shown_missing_file_toast = True
                        except Exception as e:
                            log(
                                f"❌ [TOAST BLOCK] should_show_missing_file_toast() failed "
                                f"({type(e).__name__}): {e}"
                            )
                            ctx.monitor.shown_missing_file_toast = True
                except RuntimeError:
                    log("🔕 Missing segments toast suppressed — player state unavailable")
    
            if not ctx.monitor.playback_ready:
                ctx.log_if_changed("playback_ready", "⏳ Playback not ready — waiting before processing segments")
                ctx.monitor.last_time = current_time
                continue
    
            # Process segments - if major rewind was detected, force re-evaluation of all segments
            segments_to_process = ctx.monitor.current_segments
            if major_rewind_detected:
                log("🔄 Major rewind detected — re-evaluating all segments for active dialogs")
                # Clear log cache on major rewind to allow re-logging
                ctx.monitor._last_log_state.clear()
            
            # Debug: Show current state of tracking sets (only log when counts change)
            ctx.log_if_changed("state_summary", f"📊 Current state: prompted={len(ctx.monitor.prompted)} items, recently_dismissed={len(ctx.monitor.recently_dismissed)} items, skipped_to_nested={len(ctx.monitor.skipped_to_nested_segment)} items")
    
            active_for_playback = segments_active_for_playback(
                ctx.monitor.current_segments, current_time
            )
            active_playback_ids = {
                (int(round(s.start_seconds)), int(round(s.end_seconds)))
                for s in active_for_playback
            }
    
            for segment in segments_to_process:
                # Generate segment ID consistently - use round() then int() to handle floating point precision
                # This ensures consistent matching even if segment times have slight floating point differences
                seg_id = (int(round(segment.start_seconds)), int(round(segment.end_seconds)))
                
                # CRITICAL: Check if dismissed FIRST, before any other checks
                # This ensures dismissed dialogs never reappear, even after pause/resume
                # This check must happen before is_active, prompted, or any other checks
                # This is the ABSOLUTE FIRST check - nothing else matters if the segment was dismissed
                if seg_id in ctx.monitor.recently_dismissed:
                    # Always log this (not using log_if_changed) to help debug dismissal issues
                    # Log every time to catch any cases where this check might be bypassed
                    log(f"🚫 Segment {seg_id} ({segment.segment_type_label}) was dismissed — skipping ALL processing (will not reappear after pause/resume)")
                    log(f"🔍 Debug: segment.start_seconds={segment.start_seconds}, segment.end_seconds={segment.end_seconds}, seg_id={seg_id}")
                    log(f"🔍 Debug: recently_dismissed contains {len(ctx.monitor.recently_dismissed)} items: {list(ctx.monitor.recently_dismissed)}")
                    # Ensure it's also in prompted to prevent any further checks
                    ctx.monitor.prompted.add(seg_id)
                    # CRITICAL: Use continue to skip ALL further processing for this segment
                    continue
                
                if seg_id in ctx.monitor.prompted:
                    # Only log once per segment when it's first marked as prompted
                    continue
    
                if seg_id not in active_playback_ids:
                    # Don't log inactive segments - they're checked every second
                    continue
                
                # Check if this segment dialog should be suppressed due to overlapping/nested segments
                # Pass recently_dismissed so nested segments can show even if parent was dismissed
                # The should_suppress_segment_dialog function handles the logic for nested segments in dismissed parents
                if ctx.should_suppress_segment_dialog(segment, ctx.monitor.current_segments, current_time, ctx.monitor.recently_dismissed):
                    ctx.log_if_changed(f"suppressed_{seg_id}", f"🚫 Segment {seg_id} dialog suppressed due to overlapping/nested segment priority")
                    continue
                
                # Check if this segment dialog should be suppressed because we've skipped to a nested segment
                # BUT: Only suppress if we're still within the nested segment
                # If we've exited the nested segment, the parent should show its dialog again
                # NOTE: This check should rarely be needed since we clean up exited nested segments above,
                # but it's here as a defensive check in case we missed something
                if seg_id in ctx.monitor.skipped_to_nested_segment:
                    nested_segment = ctx.monitor.skipped_to_nested_segment[seg_id]
                    # Only suppress if we're still in the nested segment
                    if nested_segment.is_active(current_time):
                        ctx.log_if_changed(f"nested_{seg_id}", f"🚫 Segment {seg_id} dialog suppressed because we're still in nested segment '{nested_segment.segment_type_label}'")
                        continue
                    else:
                        # We've exited the nested segment, but the parent is still active
                        # This should have been handled above, but clean up here as well
                        log(f"🔄 Exited nested segment '{nested_segment.segment_type_label}', parent {seg_id} is still active — allowing parent dialog to show (defensive cleanup)")
                        
                        # CRITICAL: Remove nested segment from recently_dismissed if it was dismissed
                        nested_seg_id_defensive = (int(round(nested_segment.start_seconds)), int(round(nested_segment.end_seconds)))
                        if nested_seg_id_defensive in ctx.monitor.recently_dismissed:
                            ctx.monitor.recently_dismissed.remove(nested_seg_id_defensive)
                            log(f"🔓 Removed nested segment {nested_seg_id_defensive} ({nested_segment.segment_type_label}) from recently_dismissed after exiting nested segment (defensive cleanup)")
                        
                        del ctx.monitor.skipped_to_nested_segment[seg_id]
                        # Also remove from prompted if it's there, so the parent dialog can show again
                        # BUT: Only if the parent was NOT dismissed by the user
                        if seg_id not in ctx.monitor.recently_dismissed:
                            if seg_id in ctx.monitor.prompted:
                                ctx.monitor.prompted.remove(seg_id)
                                log(f"🔄 Removed parent segment {seg_id} from prompted set to allow dialog to show (defensive cleanup)")
                        # Don't continue - let the parent segment dialog show
                
                # Only log segment processing when it's a new active segment
                log(f"🔎 Processing active segment: '{segment.segment_type_label}' [{segment.start_seconds}-{segment.end_seconds}]")
                behavior = get_user_skip_mode(segment.segment_type_label)
                log(f"🧪 Segment behavior: {behavior}")
    
                if not show_dialogs:
                    ctx.log_if_changed(f"dialogs_disabled_{seg_id}", f"🚫 Dialogs disabled in settings — suppressing dialog for segment {seg_id} (behavior: {behavior})")
                    ctx.monitor.prompted.add(seg_id)
                    continue  
                if behavior == "never":
                    ctx.log_if_changed(f"never_{seg_id}", f"🚫 Skipping dialog for '{segment.segment_type_label}' (user preference: never)")
                    continue
    
                log(f"🕒 Active segment: {segment.segment_type_label} [{segment.start_seconds}-{segment.end_seconds}] → {behavior}")
    
                # Check if skipping is enabled for this playback type
                if not is_skip_enabled(playback_type):
                    log(f"🚫 Skipping disabled for {playback_type} — segment {seg_id} will not be skipped")
                    ctx.monitor.prompted.add(seg_id)
                    continue
    
                # Correctly handle jump point from the new logic
                jump_to = segment.next_segment_start if segment.next_segment_start is not None else segment.end_seconds + 1.0
    
                if behavior == "auto":
                    log(f"⚙ Auto-skip behavior triggered for segment ID {seg_id} ({segment.segment_type_label})")
                    
                    # Track if we're skipping to a nested segment
                    if segment.next_segment_start is not None:
                        # Find the target segment we're jumping to
                        target_segment = None
                        for seg in ctx.monitor.current_segments:
                            if seg.start_seconds == segment.next_segment_start:
                                target_segment = seg
                                break
                        
                        if target_segment and ctx.is_nested_segment(segment, target_segment):
                            # We're skipping to a nested segment, track this
                            ctx.monitor.skipped_to_nested_segment[seg_id] = target_segment
                            log(f"🔗 Tracked skip to nested segment: {seg_id} -> {target_segment.segment_type_label}")
                            log(f"🔗 Parent segment {seg_id} will be re-enabled when exiting nested segment {target_segment.start_seconds}-{target_segment.end_seconds}")
                            # CRITICAL: Add parent to prompted to suppress its dialog while in nested segment
                            # This will be removed when nested segment ends (in the cleanup logic above)
                            ctx.monitor.prompted.add(seg_id)
                            log(f"🔗 Added parent segment {seg_id} to prompted set to suppress dialog while in nested segment")
                            # CRITICAL: Clear parent from recently_dismissed if it was dismissed
                            # This allows the parent dialog to reappear after the nested segment ends
                            if seg_id in ctx.monitor.recently_dismissed:
                                nested_seg_id = (int(round(target_segment.start_seconds)), int(round(target_segment.end_seconds)))
                                clearance_key = (seg_id, nested_seg_id)
                                if clearance_key not in ctx.monitor.cleared_parent_dismissals:
                                    ctx.monitor.recently_dismissed.remove(seg_id)
                                    ctx.monitor.cleared_parent_dismissals.add(clearance_key)
                                    log(f"🔓 Cleared parent segment {seg_id} from recently_dismissed because user skipped to nested segment {target_segment.segment_type_label}")
                                    log(f"🔍 Debug: recently_dismissed now has {len(ctx.monitor.recently_dismissed)} items: {list(ctx.monitor.recently_dismissed)}")
                                else:
                                    log(f"🔍 Parent segment {seg_id} dismissal already cleared for nested segment {nested_seg_id}")
                    
                    log_service_detail(
                        f"🎯 Auto-skip: Issuing seekTime({jump_to}) now...",
                        tag="playback",
                    )
                    ctx.player.seekTime(jump_to)
                    # Give Kodi time to process the seek before continuing
                    xbmc.sleep(500)
                    actual_time = ctx.player.getTime() if ctx.player.isPlaying() else -1
                    log_service_detail(
                        f"🎯 Auto-skip: After seek: requested={jump_to}, actual={actual_time}",
                        tag="playback",
                    )
                    ctx.monitor.last_time = jump_to
                    # Only add to prompted if we're NOT skipping to a nested segment
                    # (If we are, it was already added above)
                    if seg_id not in ctx.monitor.prompted:
                        ctx.monitor.prompted.add(seg_id)
    
                    if addon_get_bool(addon, "show_toast_for_skipped_segment", False):
                        log("🔔 Showing toast notification for auto-skipped segment")
                        try:
                            xbmcgui.Dialog().notification(
                                heading="Skipped",
                                message=f"{segment.segment_type_label.title()} skipped",
                                icon=ctx.icon_path,
                                time=2000,
                                sound=False
                            )
                            log("✅ Toast notification displayed successfully")
                        except RuntimeError as e:
                            log(f"❌ Failed to display skip toast notification: {e}")
                        except (OSError, ValueError, TypeError, AttributeError) as e:
                            log(
                                f"❌ Failed to display skip toast notification ({type(e).__name__}): {e}"
                            )
                        except Exception as e:
                            log(
                                f"❌ Failed to display skip toast notification ({type(e).__name__}): {e}"
                            )
                    else:
                        log("🔕 Skipped segment toast disabled by user setting")
    
                    log(f"⚡ Auto-skipped to {jump_to}")
    
                elif behavior == "ask":
                    log(f"🧠 Ask-skip behavior triggered for segment ID {seg_id} ({segment.segment_type_label})")
    
                    # Note: Dismissal check and pause check are already done at the top of the loop
                    # This ensures dismissed dialogs never reappear
                    # Pause check prevents dialogs from appearing when paused
    
                    # Double-check pause state right before showing dialog (defensive programming)
                    try:
                        dialog_is_playing = ctx.player.isPlayingVideo()
                        dialog_is_paused = xbmc.getCondVisibility("Player.Paused")
                    except RuntimeError:
                        dialog_is_playing = False
                        dialog_is_paused = True
                    
                    if dialog_is_paused or not dialog_is_playing:
                        log(f"⏸️ Video paused/stopped right before dialog — skipping dialog for segment {seg_id}")
                        # Don't add to prompted, allow retry when resumed
                        continue
    
                    try:
                        editor_modal_open = (
                            xbmcgui.Window(10000).getProperty("skippy_editor_modal_open")
                            == "true"
                        )
                    except RuntimeError:
                        editor_modal_open = False
                    if editor_modal_open:
                        ctx.log_if_changed(
                            "skip_dlg_segment_editor_open",
                            "⏸️ Skip dialog suppressed — Segment Editor is open",
                        )
                        continue
    
                    if ctx.monitor.skip_dialog_modal_active:
                        ctx.log_if_changed(
                            "skip_dialog_in_flight",
                            "⏳ Skip dialog already active — skipping duplicate ask for segment %s (%s)"
                            % (seg_id, segment.segment_type_label),
                        )
                        continue
    
                    ctx.monitor.skip_dialog_modal_active = True
                    try:
                        log("🛑 Debouncing skip dialog for 300ms")
                        xbmc.sleep(300)
    
                        dialog_mode = (addon_get_setting_text(addon, "skip_dialog_mode", "Full") or "Full").strip()
                        if dialog_mode == "Minimal":
                            layout_value = ctx.skip_dialog_layout_suffix(
                                addon, "minimal_skip_dialog_position"
                            )
                            dialog_name = f"Minimal_Skip_Dialog_{layout_value}.xml"
                        else:
                            layout_value = ctx.skip_dialog_layout_suffix(
                                addon, "skip_dialog_position"
                            )
                            dialog_name = f"SkipDialog_{layout_value}.xml"
                        log(f"📐 Using skip dialog ({dialog_mode}): {dialog_name}")
    
                        try:
                            if dialog_mode == "Minimal":
                                plate_file = _minimal_plate_filename(addon)
                                ctx.update_minimal_skip_dialog_textures(plate_file)
                                log(f"🎨 Minimal textures set to: {plate_file}")
                            else:
                                focus_texture_file = addon_get_setting_text(addon, "button_focus_style", "") or ""
                                mid_texture_file = addon_get_setting_text(addon, "progress_bar_style", "") or ""
                                if not focus_texture_file:
                                    focus_texture_file = "button_focus.png"
                                if addon_get_bool(addon, "hide_close_button", False) and not addon_get_bool(
                                    addon, "show_skip_button_focus_texture", True
                                ):
                                    focus_texture_file = "-"
                                if not mid_texture_file:
                                    mid_texture_file = "progress_mid.png"
                                ctx.update_full_skip_dialog_textures(focus_texture_file, mid_texture_file)
                        except Exception as e:
                            log(f"⚠️ Failed to update skip dialog skin XML: {e}")
    
                        log(f"🎬 Attempting to create skip dialog: {dialog_name}")
                        try:
                            dialog = SkipDialog(dialog_name, addon.getAddonInfo("path"), "default", segment=segment)
                            log("✅ Skip dialog created successfully")
                        except Exception as e:
                            log(f"❌ Failed to create skip dialog (possible Kodi/device limitation): {e}")
                            log(f"❌ Dialog creation failed for segment {seg_id} ({segment.segment_type_label})")
                            ctx.monitor.prompted.add(seg_id)
                            continue
    
                        try:
                            log("🔄 Calling dialog.doModal()")
                            dialog.doModal()
                            log("✅ Dialog doModal() completed")
                        except Exception as e:
                            log(f"❌ Dialog doModal() failed (possible Kodi/device limitation): {e}")
                            log(f"❌ Dialog display failed for segment {seg_id} ({segment.segment_type_label})")
                            try:
                                del dialog
                            except Exception:
                                pass
                            ctx.monitor.prompted.add(seg_id)
                            continue
    
                        confirmed = getattr(dialog, "response", None)
                        try:
                            del dialog
                        except Exception:
                            pass
    
                        if confirmed:
                            log(f"✅ User confirmed skip for segment ID {seg_id}")
    
                            # Track if we're skipping to a nested segment
                            if segment.next_segment_start is not None:
                                # Find the target segment we're jumping to
                                target_segment = None
                                for seg in ctx.monitor.current_segments:
                                    if seg.start_seconds == segment.next_segment_start:
                                        target_segment = seg
                                        break
    
                                if target_segment and ctx.is_nested_segment(segment, target_segment):
                                    # We're skipping to a nested segment, track this
                                    ctx.monitor.skipped_to_nested_segment[seg_id] = target_segment
                                    log(f"🔗 Tracked skip to nested segment: {seg_id} -> {target_segment.segment_type_label}")
                                    log(f"🔗 Parent segment {seg_id} will be re-enabled when exiting nested segment {target_segment.start_seconds}-{target_segment.end_seconds}")
                                    # CRITICAL: Add parent to prompted to suppress its dialog while in nested segment
                                    # This will be removed when nested segment ends (in the cleanup logic above)
                                    ctx.monitor.prompted.add(seg_id)
                                    log(f"🔗 Added parent segment {seg_id} to prompted set to suppress dialog while in nested segment")
                                    # CRITICAL: Clear parent from recently_dismissed if it was dismissed
                                    # This allows the parent dialog to reappear after the nested segment ends
                                    if seg_id in ctx.monitor.recently_dismissed:
                                        nested_seg_id = (int(round(target_segment.start_seconds)), int(round(target_segment.end_seconds)))
                                        clearance_key = (seg_id, nested_seg_id)
                                        if clearance_key not in ctx.monitor.cleared_parent_dismissals:
                                            ctx.monitor.recently_dismissed.remove(seg_id)
                                            ctx.monitor.cleared_parent_dismissals.add(clearance_key)
                                            log(f"🔓 Cleared parent segment {seg_id} from recently_dismissed because user skipped to nested segment {target_segment.segment_type_label}")
                                            log(f"🔍 Debug: recently_dismissed now has {len(ctx.monitor.recently_dismissed)} items: {list(ctx.monitor.recently_dismissed)}")
                                        else:
                                            log(f"🔍 Parent segment {seg_id} dismissal already cleared for nested segment {nested_seg_id}")
    
                            # Only add to prompted if we're NOT skipping to a nested segment
                            # (If we are, it was already added above)
                            if seg_id not in ctx.monitor.prompted:
                                ctx.monitor.prompted.add(seg_id)
                            log_service_detail(
                                f"🎯 Issuing seekTime({jump_to}) now...",
                                tag="playback",
                            )
                            ctx.player.seekTime(jump_to)
                            # Give Kodi time to process the seek before continuing
                            xbmc.sleep(500)
                            actual_time = ctx.player.getTime() if ctx.player.isPlaying() else -1
                            log_service_detail(
                                f"🎯 After seek: requested={jump_to}, actual={actual_time}",
                                tag="playback",
                            )
                            ctx.monitor.last_time = jump_to
    
                            if addon_get_bool(addon, "show_toast_for_skipped_segment", False):
                                log("🔔 Showing toast notification for user-confirmed skip")
                                try:
                                    xbmcgui.Dialog().notification(
                                        heading="Skipped",
                                        message=f"{segment.segment_type_label.title()} skipped",
                                        icon=ctx.icon_path,
                                        time=2000,
                                        sound=False
                                    )
                                    log("✅ Toast notification displayed successfully")
                                except RuntimeError as e:
                                    log(f"❌ Failed to display skip toast notification: {e}")
                                except (OSError, ValueError, TypeError, AttributeError) as e:
                                    log(
                                        f"❌ Failed to display skip toast notification ({type(e).__name__}): {e}"
                                    )
                                except Exception as e:
                                    log(
                                        f"❌ Failed to display skip toast notification ({type(e).__name__}): {e}"
                                    )
                            else:
                                log("🔕 Skipped segment toast disabled by user setting")
    
                            log(f"🚀 Jumped to {jump_to}")
                        else:
                            log(f"🙅 User dismissed skip dialog for segment ID {seg_id}")
                            log(f"🔍 Debug: segment.start_seconds={segment.start_seconds}, segment.end_seconds={segment.end_seconds}, seg_id={seg_id}")
                            # CRITICAL: Use the same seg_id that was calculated at the start of the loop
                            # This ensures perfect matching with the recently_dismissed check
                            # The seg_id was already calculated as (int(round(segment.start_seconds)), int(round(segment.end_seconds)))
                            ctx.monitor.recently_dismissed.add(seg_id)
                            ctx.monitor.prompted.add(seg_id)
                            log(f"📊 Added {seg_id} to recently_dismissed and prompted sets")
                            log(f"🔍 Debug: recently_dismissed now contains {len(ctx.monitor.recently_dismissed)} items: {list(ctx.monitor.recently_dismissed)}")
                            log(f"🔒 Segment {seg_id} ({segment.segment_type_label}) is now permanently dismissed for this playback session")
                            log(f"🔒 This segment will NOT reappear after pause/resume unless there is a major rewind")
                            # Verify the dismissal was recorded
                            if seg_id in ctx.monitor.recently_dismissed:
                                log(f"✅ Verification: Segment {seg_id} confirmed in recently_dismissed set")
                            else:
                                log(f"❌ ERROR: Segment {seg_id} NOT found in recently_dismissed set after adding!")
                    except RuntimeError as e:
                        log(f"❌ Error showing skip dialog (RuntimeError): {e}")
                        ctx.monitor.prompted.add(seg_id)
                    except (OSError, ValueError, TypeError, AttributeError) as e:
                        log(
                            f"❌ Error showing skip dialog ({type(e).__name__}): {e}"
                        )
                        ctx.monitor.prompted.add(seg_id)
                    except Exception as e:
                        log(f"❌ Error showing skip dialog ({type(e).__name__}): {e}")
                        ctx.monitor.prompted.add(seg_id)
                    finally:
                        ctx.monitor.skip_dialog_modal_active = False
    
            # Update last_time at the end of each main loop cycle for next iteration's rewind detection
            ctx.monitor.last_time = current_time
    
    
        if ctx.monitor.waitForAbort(ctx.check_interval):
            log("🛑 Abort requested — exiting monitor loop")
