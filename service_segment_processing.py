"""Overlap / nesting detection, segment dialog suppression, and parse-and-process pipeline."""

import xbmc
import xbmcgui

from segment_item import segment_is_active_lenient, segments_active_for_playback
from segment_editor_utils import set_editor_modal_open
from settings_utils import addon_get_bool, get_addon, log, show_overlapping_toast


def is_nested_segment(segment_a, segment_b):
    """
    Check if segment_b is fully nested inside segment_a.
    Returns True if segment_b is completely contained within segment_a.
    """
    return segment_b.start_seconds >= segment_a.start_seconds and segment_b.end_seconds <= segment_a.end_seconds


def is_overlapping_segment(segment_a, segment_b):
    """
    Check if two segments overlap (but not nested).
    Returns True if segments overlap but neither is fully contained in the other.
    """
    if (
        segment_a.end_seconds <= segment_b.start_seconds
        or segment_b.end_seconds <= segment_a.start_seconds
    ):
        return False

    if is_nested_segment(segment_a, segment_b) or is_nested_segment(segment_b, segment_a):
        return False

    return True


def should_suppress_segment_dialog(
    current_segment, all_segments, current_time, recently_dismissed=None
):
    """
    Check if the current segment dialog should be suppressed because we're inside
    a nested or overlapping segment that should take priority.

    Returns True if the dialog should be suppressed.

    Args:
        recently_dismissed: Set of dismissed segment IDs. If a parent segment is dismissed,
                          nested segments should still be allowed to show.
    """
    active_segments = segments_active_for_playback(all_segments, current_time)

    if len(active_segments) <= 1:
        return False

    active_segments.sort(key=lambda s: s.start_seconds)

    try:
        current_index = active_segments.index(current_segment)
    except ValueError:
        return False

    current_seg_id = (
        int(round(current_segment.start_seconds)),
        int(round(current_segment.end_seconds)),
    )

    if recently_dismissed:
        for i in range(current_index):
            parent_segment = active_segments[i]
            parent_seg_id = (
                int(round(parent_segment.start_seconds)),
                int(round(parent_segment.end_seconds)),
            )
            if parent_seg_id in recently_dismissed and is_nested_segment(
                parent_segment, current_segment
            ):
                log(
                    f"✅ Allowing nested segment '{current_segment.segment_type_label}' to show even though parent '{parent_segment.segment_type_label}' was dismissed"
                )
                return False

    for i in range(current_index + 1, len(active_segments)):
        later_segment = active_segments[i]

        if is_nested_segment(current_segment, later_segment):
            if recently_dismissed:
                if current_seg_id in recently_dismissed:
                    log(
                        f"✅ Allowing nested segment '{later_segment.segment_type_label}' to show even though parent '{current_segment.segment_type_label}' was dismissed"
                    )
                    return False
            log(
                f"🚫 Suppressing dialog for '{current_segment.segment_type_label}' because '{later_segment.segment_type_label}' is nested within it"
            )
            return True

        if is_overlapping_segment(current_segment, later_segment):
            log(
                f"🚫 Suppressing dialog for '{current_segment.segment_type_label}' because '{later_segment.segment_type_label}' overlaps with it"
            )
            return True

    return False


def re_evaluate_segment_jump_points(segments, current_time):
    """
    Re-evaluate jump points for segments based on current playback position.
    This is needed after major rewinds to ensure correct jump targets.
    """
    log(f"🔄 Re-evaluating jump points for {len(segments)} segments at time {current_time:.2f}")

    for i in range(len(segments)):
        current_seg = segments[i]

        next_jump_target = None
        next_segment_info = None

        for j in range(i + 1, len(segments)):
            next_seg = segments[j]

            if next_seg.start_seconds < current_seg.end_seconds:
                if is_nested_segment(current_seg, next_seg):
                    if current_time < next_seg.start_seconds:
                        log(
                            f"🔍 Re-evaluating: '{next_seg.segment_type_label}' is nested in '{current_seg.segment_type_label}', current time {current_time:.2f} is before nested segment ({next_seg.start_seconds}-{next_seg.end_seconds})"
                        )
                        next_jump_target = next_seg.start_seconds
                        next_segment_info = f"nested segment '{next_seg.segment_type_label}'"
                        break
                    else:
                        log(
                            f"🔍 Re-evaluating: '{next_seg.segment_type_label}' is nested in '{current_seg.segment_type_label}', but current time {current_time:.2f} is at or past nested segment ({next_seg.start_seconds}-{next_seg.end_seconds}), will skip to parent end"
                        )
                        next_jump_target = None
                        next_segment_info = None
                        break

                elif is_overlapping_segment(current_seg, next_seg):
                    log(
                        f"🔍 Re-evaluating: '{next_seg.segment_type_label}' overlaps with '{current_seg.segment_type_label}'"
                    )
                    next_jump_target = next_seg.start_seconds
                    next_segment_info = f"overlapping segment '{next_seg.segment_type_label}'"
                    break
            else:
                break

        current_seg.next_segment_start = next_jump_target
        current_seg.next_segment_info = next_segment_info

        if next_jump_target is not None:
            log(
                f"🔗 Re-evaluated jump point for '{current_seg.segment_type_label}' to {next_jump_target}s ({next_segment_info})"
            )
        else:
            log(
                f"🔗 Re-evaluated jump point for '{current_seg.segment_type_label}' to end of segment ({current_seg.end_seconds}s)"
            )

    log(
        f"🔍 Additional pass: Checking nested segments for correct jump points at time {current_time:.2f}"
    )
    for i in range(len(segments)):
        current_seg = segments[i]

        if segment_is_active_lenient(current_seg, current_time):
            for j in range(i):
                parent_seg = segments[j]
                if is_nested_segment(parent_seg, current_seg):
                    if current_seg.next_segment_start != current_seg.end_seconds:
                        log(
                            f"🔧 Fixing nested segment '{current_seg.segment_type_label}': setting jump point to {current_seg.end_seconds}s (end of segment)"
                        )
                        current_seg.next_segment_start = current_seg.end_seconds
                        current_seg.next_segment_info = f"remaining {parent_seg.segment_type_label}"
                    break


def parse_and_process_segments(
    path,
    current_time=None,
    playback_type=None,
    *,
    get_cached_source_segments,
    segment_monitor,
    segment_player,
    overlap_toast_icon_path,
    log_if_changed,
):
    """
    Parses segments, filters them based on settings, and then links overlapping/nested segments.
    If current_time is provided, the linking logic will be context-aware.
    For TV episodes, optional local files and online APIs are controlled by TV-only settings.
    """
    try:
        is_playing_parse = segment_player.isPlayingVideo()
        is_paused_parse = xbmc.getCondVisibility("Player.Paused")
        if is_paused_parse or not is_playing_parse:
            log(
                f"🔕 parse_and_process_segments called while paused — returning empty list to prevent toast spamming (is_playing={is_playing_parse}, is_paused={is_paused_parse})"
            )
            return []
    except RuntimeError:
        log(
            "🔕 parse_and_process_segments called but player state unavailable — returning empty list"
        )
        return []

    log(f"🚦 Starting new segment parse and process for: {path}")
    addon = get_addon()
    if not addon:
        return []

    parsed = get_cached_source_segments(path, playback_type)

    if not parsed:
        log("🚫 No segment file found or parsed segments were empty.")
        return []

    log("⚙️ Pass 1: Filtering segments...")
    skip_overlaps = addon_get_bool(addon, "skip_overlapping_segments", True)

    segments = sorted(parsed, key=lambda s: s.start_seconds)

    filtered_segments = []

    for current_seg in segments:
        is_overlapping_with_filtered = False
        for existing_seg in filtered_segments:
            if not (
                current_seg.end_seconds <= existing_seg.start_seconds
                or current_seg.start_seconds >= existing_seg.end_seconds
            ):
                is_overlapping_with_filtered = True
                break

        if is_overlapping_with_filtered and skip_overlaps:
            log(
                f"🚫 Skipping segment {current_seg.start_seconds}-{current_seg.end_seconds} due to user setting 'skip_overlapping_segments' which detected an overlap."
            )
            continue

        filtered_segments.append(current_seg)

    log(f"✅ Pass 1 complete. Filtered segments: {len(filtered_segments)}")

    log("🔗 Pass 2: Linking segments for progressive skipping and detecting overlaps/nested...")
    has_overlap_or_nested = False

    for i in range(len(filtered_segments)):
        current_seg = filtered_segments[i]

        next_jump_target = None
        next_segment_info = None

        for j in range(i + 1, len(filtered_segments)):
            next_seg = filtered_segments[j]

            if next_seg.start_seconds < current_seg.end_seconds:
                has_overlap_or_nested = True

                if is_nested_segment(current_seg, next_seg):
                    log(
                        f"🔍 Detected NESTED segment: '{next_seg.segment_type_label}' ({next_seg.start_seconds}-{next_seg.end_seconds}) is nested inside '{current_seg.segment_type_label}' ({current_seg.start_seconds}-{current_seg.end_seconds})"
                    )

                    if current_time is None or current_time < next_seg.start_seconds:
                        next_jump_target = next_seg.start_seconds
                        next_segment_info = f"nested segment '{next_seg.segment_type_label}'"
                        log(
                            f"🔗 Setting jump point for '{current_seg.segment_type_label}' to {next_jump_target}s ({next_segment_info})"
                        )
                    else:
                        log(
                            f"🔗 Context-aware: current time {current_time:.2f} is at or past nested segment, will skip to end of parent"
                        )
                        next_jump_target = None
                        next_segment_info = None

                    next_seg.next_segment_start = next_seg.end_seconds
                    next_seg.next_segment_info = f"remaining {current_seg.segment_type_label}"
                    log(
                        f"🔗 Setting jump point for nested '{next_seg.segment_type_label}' to {next_seg.end_seconds}s (remaining {current_seg.segment_type_label})"
                    )

                elif is_overlapping_segment(current_seg, next_seg):
                    log(
                        f"🔍 Detected OVERLAPPING segment: '{next_seg.segment_type_label}' ({next_seg.start_seconds}-{next_seg.end_seconds}) overlaps with '{current_seg.segment_type_label}' ({current_seg.start_seconds}-{current_seg.end_seconds})"
                    )
                    next_jump_target = next_seg.start_seconds
                    next_segment_info = f"overlapping segment '{next_seg.segment_type_label}'"

                if next_jump_target is not None:
                    current_seg.next_segment_start = next_jump_target
                    current_seg.next_segment_info = next_segment_info
                    log(
                        f"🔗 Setting jump point for '{current_seg.segment_type_label}' to {next_jump_target}s ({next_segment_info})"
                    )
                    break
            else:
                break

    if (
        has_overlap_or_nested
        and not skip_overlaps
        and addon_get_bool(addon, "open_segment_editor_on_overlap", False)
        and addon.getSetting("segment_editor_enabled") == "true"
        and segment_monitor.overlap_editor_opened_for_path != path
    ):
        try:
            _oe_play = segment_player.isPlayingVideo()
            _oe_pause = xbmc.getCondVisibility("Player.Paused")
            if not _oe_pause and _oe_play:
                segment_monitor.overlap_editor_opened_for_path = path
                log(
                    "📂 Overlapping/nested segments detected — launching Segment Editor "
                    "(open_segment_editor_on_overlap)"
                )
                # RunScript is async; set window property now so the service loop suppresses
                # skip dialog in the same iteration (segment_editor_session clears on early exit).
                set_editor_modal_open(True)
                xbmc.executebuiltin("RunScript(service.skippy,open_segment_editor)")
            else:
                log_if_changed(
                    "overlap_editor_paused",
                    "🔕 Overlap auto-editor suppressed — playback paused or not playing",
                )
        except RuntimeError:
            pass

    if segment_monitor.toast_overlap_shown:
        log_if_changed(
            "toast_already_shown",
            "🔕 Overlapping segments toast already shown — skipping",
        )
        return filtered_segments

    should_show_toast = has_overlap_or_nested and show_overlapping_toast()
    if not should_show_toast:
        return filtered_segments

    try:
        is_playing_toast = segment_player.isPlayingVideo()
        is_paused_toast = xbmc.getCondVisibility("Player.Paused")
        if is_paused_toast or not is_playing_toast:
            log(
                f"🔕 Suppressing overlapping segments toast because playback is paused or not playing (is_playing={is_playing_toast}, is_paused={is_paused_toast})"
            )
            return filtered_segments
    except RuntimeError:
        log("🔕 Suppressing overlapping segments toast because player state unavailable")
        return filtered_segments

    if segment_monitor.recently_dismissed:
        log_if_changed(
            "toast_dismissed",
            "🔕 Suppressing overlapping segments toast because user has dismissed a segment dialog",
        )
        return filtered_segments

    try:
        final_is_playing = segment_player.isPlayingVideo()
        final_is_paused = xbmc.getCondVisibility("Player.Paused")
        if final_is_paused or not final_is_playing:
            log(
                f"🔕 Final pause check: Suppressing overlapping segments toast because playback is paused or not playing (is_playing={final_is_playing}, is_paused={final_is_paused})"
            )
            return filtered_segments
    except RuntimeError:
        log(
            "🔕 Final pause check: Suppressing overlapping segments toast because player state unavailable"
        )
        return filtered_segments

    log("🔔 Attempting to show toast notification for overlapping segments")
    try:
        xbmcgui.Dialog().notification(
            heading="Skippy",
            message="Overlapping/Nested segments detected.",
            icon=overlap_toast_icon_path,
            time=4000,
        )
        segment_monitor.toast_overlap_shown = True
        log("✅ Toast notification displayed for overlapping segments")
    except Exception as e:
        log(
            f"❌ Failed to display overlapping segments toast notification (possible Kodi/device limitation): {e}"
        )

    log(f"✅ Pass 2 complete. Final segments to process: {len(filtered_segments)}")
    return filtered_segments
