"""Merge or update online segments into local sidecars; write chapters.xml / EDL."""

import os
import xml.etree.ElementTree as ET
from collections import defaultdict

import xbmc
import xbmcgui
import xbmcvfs

from online_segment_upload import (
    local_label_to_online_bucket,
    remote_payload_label_to_online_bucket,
)
from playback_segment_cache import publish_parse_cache
from segment_editor_parser import (
    dedupe_overlapping_same_label_segments,
    safe_file_write,
    save_edl,
    seconds_to_hms,
)
from segment_item import SegmentItem
from service_online_policy import (
    _SAVE_CHAPTERS_MERGE,
    _SAVE_CHAPTERS_OVERWRITE_ASK,
    _SAVE_CHAPTERS_OVERWRITE_SILENT,
    _SAVE_CHAPTERS_SKIP_IF_EXISTS,
    _SAVE_CHAPTERS_UPDATE_ALL_ASK,
    _SAVE_CHAPTERS_UPDATE_ALL_SILENT,
    _SAVE_CHAPTERS_UPDATE_ASK,
    _SAVE_CHAPTERS_UPDATE_SILENT,
    _SAVE_ONLINE_FORMAT_BOTH,
    _SAVE_ONLINE_FORMAT_EDL,
    _SAVE_ONLINE_FORMAT_XML,
    _normalize_online_sidecar_policy,
    _normalize_save_online_format,
    policy_allows_neighbor_snap,
)
from service_segment_sources import (
    _chapter_window_overlap,
    _parse_chapter_xml_string,
    parse_edl,
    safe_file_read,
)
from service_sidecar_paths import (
    _default_new_sidecar_chapter_xml_path,
    _edl_paths_to_try,
    _find_existing_sidecar_chapter_xml_path,
    playback_path_supports_sidecar_chapters_xml,
)
from settings_utils import (
    addon_get_bool,
    addon_get_setting_text,
    get_addon,
    get_edl_label_to_action_map,
    get_edl_type_map,
    log,
    log_service_detail,
    normalize_label,
)


def _log_sidecar_detail(msg):
    log_service_detail(msg, tag="sidecar")


from skippy_editor_modal_skin import sidecar_overwrite_yesno_show


def _sidecar_update_ask_heading_body(policy, scope):
    """Localized (heading id, body id) for Update vs Update All confirmation."""
    is_all = policy == _SAVE_CHAPTERS_UPDATE_ALL_ASK
    if scope == "xml":
        return (35020, 35021) if is_all else (35012, 35013)
    if scope == "edl":
        return (35022, 35023) if is_all else (35014, 35015)
    return (35024, 35025) if is_all else (35016, 35017)


def _suppress_online_sidecar_save_prompt(video_path, segment_monitor):
    """Remember overwrite/update was settled (Yes or No) — do not re-prompt after parse refresh."""
    if segment_monitor is not None and video_path:
        segment_monitor.online_sidecar_save_prompt_suppressed_path = video_path


def _sidecar_overwrite_yesno(heading, message):
    """
    Overwrite/update confirmation with a tall scrollable body.
    If playback is not active, does not show a dialog (returns False).
    """
    try:
        if not xbmc.Player().isPlayingVideo():
            _log_sidecar_detail("Sidecar prompt suppressed: video not playing")
            return False
    except Exception:
        _log_sidecar_detail("Sidecar prompt suppressed: player state unavailable")
        return False

    addon = get_addon()
    try:
        if addon:
            ylbl = addon.getLocalizedString(35018)
            clbl = addon.getLocalizedString(35019)
        else:
            ylbl, clbl = "Yes", "Cancel"
    except Exception:
        ylbl, clbl = "Yes", "Cancel"
    if not (ylbl or "").strip():
        ylbl = "Yes"
    if not (clbl or "").strip():
        clbl = "Cancel"

    try:
        return sidecar_overwrite_yesno_show(
            heading, message or "", ylbl, clbl
        )
    except Exception as e:
        log("⚠ Tall sidecar prompt failed (%s) — falling back to stock yesno" % e)
        try:
            if not xbmc.Player().isPlayingVideo():
                return False
            return bool(xbmcgui.Dialog().yesno(heading, message))
        except RuntimeError as e2:
            log("⚠ Stock sidecar yesno failed (%s) — treating as declined" % e2)
            return False


# Sidecar / xbmcvfs file ops: catch expected failures without masking MemoryError etc.
_VFS_IO_EXC = (OSError, IOError, RuntimeError, ValueError, TypeError, AttributeError)


def _online_sidecar_save_allowed(addon, video_path, segments):
    """Shared gate: addon toggle, non-empty inputs, and path suitable for sidecars."""
    if not addon or not addon_get_bool(
        addon, "save_online_segments_to_chapters_xml", False
    ):
        return False
    if not video_path or not segments:
        return False
    if not playback_path_supports_sidecar_chapters_xml(video_path):
        log(
            "Skipping save online sidecars: path is not suitable (plugin/STRM/stream URL)"
        )
        return False
    return True


def _seconds_to_chapter_hms(sec):
    sec = max(0.0, float(sec))
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec - h * 3600 - m * 60
    return "%02d:%02d:%06.3f" % (h, m, s)


def _merge_sidecar_segments(existing_items, online_items, tol=1.5):
    """Keep all existing; add online segments that do not overlap any kept window (by time)."""
    merged = list(existing_items)
    for o in online_items:
        if any(
            _chapter_window_overlap(
                o.start_seconds, o.end_seconds, x.start_seconds, x.end_seconds, tol
            )
            for x in merged
        ):
            continue
        merged.append(
            SegmentItem(
                o.start_seconds,
                o.end_seconds,
                o.segment_type_label or "segment",
                source=o.source or "online",
            )
        )
    merged.sort(key=lambda s: s.start_seconds)
    return dedupe_overlapping_same_label_segments(merged, tol)


def _overlap_duration(s1, e1, s2, e2):
    lo = max(float(s1), float(s2))
    hi = min(float(e1), float(e2))
    return max(0.0, hi - lo)


def _segment_item_with_times(base, start, end):
    return SegmentItem(
        float(start),
        float(end),
        base.segment_type_label,
        source=base.source,
        action_type=base.action_type,
        timeout=base.timeout,
        allow_input=base.allow_input,
        next_segment_start=base.next_segment_start,
        next_segment_info=base.next_segment_info,
    )


def _source_display_name(source: str | None) -> str:
    s = (source or "").strip().lower()
    if s == "theintrodb":
        return "TheIntroDB.org"
    if s == "introdb":
        return "IntroDB.app"
    return source or "online"


def _summarize_online_by_source(online_items, max_per_source=8):
    """Lines describing online windows grouped by API source."""
    by_src = defaultdict(list)
    for o in online_items:
        by_src[_source_display_name(getattr(o, "source", None))].append(o)
    lines = []
    if not online_items:
        lines.append("No online segment windows in this response.")
        return lines
    lines.append("[Online lookup]")
    for src in sorted(by_src.keys(), key=str.lower):
        segs = sorted(by_src[src], key=lambda s: float(s.start_seconds))
        lines.append("  %s — %d window(s):" % (src, len(segs)))
        for s in segs[:max_per_source]:
            lines.append(
                "    • %s  %s – %s"
                % (
                    s.segment_type_label or "?",
                    seconds_to_hms(float(s.start_seconds)),
                    seconds_to_hms(float(s.end_seconds)),
                )
            )
        if len(segs) > max_per_source:
            lines.append(
                "    … +%d more" % (len(segs) - max_per_source),
            )
    return lines


def _pick_best_local_index_for_online(result, used, canon_o, o):
    candidates = [
        i
        for i, e in enumerate(result)
        if i not in used
        and local_label_to_online_bucket(e.segment_type_label) == canon_o
    ]
    if not candidates:
        return None
    best_i = None
    best_ov = -1.0
    for i in candidates:
        e = result[i]
        ov = _overlap_duration(
            e.start_seconds,
            e.end_seconds,
            o.start_seconds,
            o.end_seconds,
        )
        if ov > best_ov:
            best_ov = ov
            best_i = i
        elif ov == best_ov and best_i is not None:
            if float(e.start_seconds) < float(result[best_i].start_seconds):
                best_i = i
    if best_i is None:
        return None
    if best_ov <= 0.0:
        best_i = min(
            candidates,
            key=lambda i: abs(
                float(result[i].start_seconds) - float(o.start_seconds)
            ),
        )
    return best_i


def _sidecar_update_plan(existing_items, online_items):
    """
    Returns ``(change_rows, updated_list, unmatched_online)`` where
    ``unmatched_online`` lists online SegmentItems with a recognized bucket but
    no local row of that type (candidates for Update All insert).
    """
    result = list(existing_items)
    changes = []
    unmatched = []
    used = set()
    onlines = sorted(online_items, key=lambda o: float(o.start_seconds))
    for o in onlines:
        canon_o = remote_payload_label_to_online_bucket(o.segment_type_label)
        if canon_o is None:
            continue
        best_i = _pick_best_local_index_for_online(result, used, canon_o, o)
        if best_i is None:
            unmatched.append(o)
            continue
        e = result[best_i]
        ns, ne = float(o.start_seconds), float(o.end_seconds)
        os_, oe = float(e.start_seconds), float(e.end_seconds)
        if os_ != ns or oe != ne:
            changes.append(
                {
                    "local_label": e.segment_type_label or "segment",
                    "old_start": os_,
                    "old_end": oe,
                    "new_start": ns,
                    "new_end": ne,
                    "online_label": o.segment_type_label or "?",
                    "online_source": getattr(o, "source", None) or "",
                }
            )
        result[best_i] = _segment_item_with_times(e, ns, ne)
        used.add(best_i)
    result.sort(key=lambda s: float(s.start_seconds))
    return changes, result, unmatched


def _update_sidecar_segments(existing_items, online_items):
    return _sidecar_update_plan(existing_items, online_items)[1]


_SNAP_TRIM_EPS = 1e-6


def _neighbor_snap_flags_for_policy(policy, addon):
    """Read snap toggles only for Update / Update All; always off for Merge/Overwrite."""
    if not policy_allows_neighbor_snap(policy) or not addon:
        return False, False
    return (
        addon_get_bool(addon, "online_sidecar_snap_neighbor_start", False),
        addon_get_bool(addon, "online_sidecar_snap_neighbor_end", False),
    )


def _finalize_sidecar_after_update_policy(existing_items, online_segments, policy, addon):
    """
    Matched buckets are retimed from online. Optional neighbor snap trims overlaps
    caused by those retimes (Update and Update All). Update All then appends
    missing online buckets and runs the same snap rules per insert.
    """
    snap_s, snap_e = _neighbor_snap_flags_for_policy(policy, addon)
    ch, base, unmatched = _sidecar_update_plan(
        list(existing_items), online_segments
    )
    items = list(base)
    if snap_s or snap_e:
        _snap_after_retimed_segments(items, ch, snap_s, snap_e)
        items[:] = _prune_zero_or_negative_length_segments(items)
        items[:] = list(dedupe_overlapping_same_label_segments(items, 1.5))
    if policy in (
        _SAVE_CHAPTERS_UPDATE_ALL_SILENT,
        _SAVE_CHAPTERS_UPDATE_ALL_ASK,
    ):
        if not unmatched:
            return items
        return _insert_unmatched_with_neighbor_snaps(
            items, unmatched, snap_s, snap_e
        )
    return items


def _snap_after_retimed_segments(items, change_rows, snap_start, snap_end):
    """After bucket retimes, trim neighbors overlapping the new windows (mutates ``items``)."""
    if not (snap_start or snap_end) or not change_rows:
        return
    anchors = []
    for r in change_rows:
        lab = normalize_label(r["local_label"] or "")
        ns, ne = float(r["new_start"]), float(r["new_end"])
        for s in items:
            if normalize_label(s.segment_type_label or "") != lab:
                continue
            if (
                abs(float(s.start_seconds) - ns) < 1e-3
                and abs(float(s.end_seconds) - ne) < 1e-3
            ):
                if s not in anchors:
                    anchors.append(s)
                break
    for a in sorted(anchors, key=lambda s: float(s.start_seconds)):
        _apply_neighbor_snap_trims(items, a, snap_start, snap_end)
        items.sort(key=lambda s: float(s.start_seconds))


def _anchor_wrap_prefers_snap_end(anchor):
    """
    When one local row fully contains the anchor window, a single row can only
    receive one trim. Credits/preview-style anchors trim the neighbor's **end**
    to the anchor **start** (e.g. main ends where credits start). Intro/recap
    anchors trim the neighbor's **start** to the anchor **end** (e.g. main
    resumes after intro). Separate prologue/main rows each get their own case
    (left overlap / wrap) without splitting.
    """
    b = remote_payload_label_to_online_bucket(anchor.segment_type_label or "")
    return b in ("credits", "preview")


def _apply_neighbor_snap_trims(items, anchor, snap_start, snap_end):
    """
    Trim **distinct** overlapping neighbors: left-side overlap → optional
    **snap_end** (neighbor ends at anchor start); right-side overlap →
    **snap start** (neighbor starts at anchor end). A single row that **fully
    contains** the anchor is **never** split; one trim is applied from anchor
    type (see ``_anchor_wrap_prefers_snap_end``). Iterate backwards for stable
    indices.
    """
    ns = float(anchor.start_seconds)
    ne = float(anchor.end_seconds)
    eps = _SNAP_TRIM_EPS
    idx = len(items) - 1
    while idx >= 0:
        other = items[idx]
        if other is anchor:
            idx -= 1
            continue
        os_ = float(other.start_seconds)
        oe = float(other.end_seconds)
        if _overlap_duration(ns, ne, os_, oe) <= eps:
            idx -= 1
            continue
        if os_ <= ns + eps and oe >= ne - eps:
            prefer_end = _anchor_wrap_prefers_snap_end(anchor)
            if prefer_end:
                if snap_end and ns > os_ + eps:
                    items[idx] = _segment_item_with_times(other, os_, ns)
            else:
                if snap_start and oe > ne + eps:
                    items[idx] = _segment_item_with_times(other, ne, oe)
            idx -= 1
            continue
        if os_ + eps < ns < oe <= ne + eps:
            if snap_end:
                new_oe = ns
                if new_oe > os_ + eps:
                    items[idx] = _segment_item_with_times(other, os_, new_oe)
            idx -= 1
            continue
        if ns - eps <= os_ < ne < oe - eps:
            if snap_start:
                new_os = ne
                if new_os + eps < oe:
                    items[idx] = _segment_item_with_times(other, new_os, oe)
            idx -= 1
            continue
        idx -= 1


def _prune_zero_or_negative_length_segments(items):
    out = []
    for s in items:
        if float(s.end_seconds) > float(s.start_seconds) + _SNAP_TRIM_EPS:
            out.append(s)
    return out


def _insert_unmatched_with_neighbor_snaps(base_list, unmatched, snap_start, snap_end):
    items = list(base_list)
    for u in sorted(unmatched, key=lambda x: float(x.start_seconds)):
        n = SegmentItem(
            float(u.start_seconds),
            float(u.end_seconds),
            u.segment_type_label or "segment",
            source=getattr(u, "source", None) or "online",
        )
        items.append(n)
        _apply_neighbor_snap_trims(items, n, snap_start, snap_end)
        items.sort(key=lambda s: float(s.start_seconds))
    items = _prune_zero_or_negative_length_segments(items)
    return dedupe_overlapping_same_label_segments(items, 1.5)


def _lines_for_sidecar_preview_items(final_items, max_rows=36):
    lines = []
    if not final_items:
        lines.append("  (empty)")
        return lines
    for s in sorted(final_items, key=lambda x: float(x.start_seconds))[:max_rows]:
        lines.append(
            "  • %s  %s – %s"
            % (
                s.segment_type_label or "?",
                seconds_to_hms(float(s.start_seconds)),
                seconds_to_hms(float(s.end_seconds)),
            )
        )
    if len(final_items) > max_rows:
        lines.append("  … +%d more" % (len(final_items) - max_rows))
    return lines


def _lines_for_update_changes(change_rows, max_rows=14):
    lines = []
    if not change_rows:
        lines.append("No overlapping segment types to update — local times already match.")
        return lines
    lines.append("Planned time updates (local label kept):")
    for r in change_rows[:max_rows]:
        lines.append(
            "  • %s:  %s – %s  →  %s – %s  (online %s from %s)"
            % (
                r["local_label"],
                seconds_to_hms(r["old_start"]),
                seconds_to_hms(r["old_end"]),
                seconds_to_hms(r["new_start"]),
                seconds_to_hms(r["new_end"]),
                r["online_label"],
                _source_display_name(r["online_source"]),
            )
        )
    if len(change_rows) > max_rows:
        lines.append("  … +%d more change(s)" % (len(change_rows) - max_rows))
    return lines


def _lines_overwrite_compare(local_items, online_items, max_lines=18):
    """Pair online windows to locals by canonical bucket for informational diff."""
    lines = []
    if not online_items:
        return lines
    locs = list(local_items)
    used_local = set()
    lines.append("Overwrite replaces the file with online windows only. Comparison:")
    n_on = sorted(online_items, key=lambda x: float(x.start_seconds))
    count = 0
    for o in n_on:
        if count >= max_lines:
            break
        canon_o = remote_payload_label_to_online_bucket(o.segment_type_label)
        src = _source_display_name(getattr(o, "source", None))
        olab = o.segment_type_label or "?"
        osh, oeh = float(o.start_seconds), float(o.end_seconds)
        if canon_o is None:
            lines.append(
                "  + Online-only type %s  %s – %s  (%s)"
                % (olab, seconds_to_hms(osh), seconds_to_hms(oeh), src)
            )
            count += 1
            continue
        candidates = [
            i
            for i, e in enumerate(locs)
            if i not in used_local
            and local_label_to_online_bucket(e.segment_type_label) == canon_o
        ]
        if not candidates:
            lines.append(
                "  + %s  %s – %s  (%s) — no same-type local entry"
                % (olab, seconds_to_hms(osh), seconds_to_hms(oeh), src)
            )
            count += 1
            continue
        best_i = _pick_best_local_index_for_online(locs, used_local, canon_o, o)
        if best_i is None:
            continue
        e = locs[best_i]
        used_local.add(best_i)
        lines.append(
            "  • %s  local %s – %s  →  online (%s) %s – %s"
            % (
                e.segment_type_label or "?",
                seconds_to_hms(float(e.start_seconds)),
                seconds_to_hms(float(e.end_seconds)),
                src,
                seconds_to_hms(osh),
                seconds_to_hms(oeh),
            )
        )
        count += 1
    leftover = [i for i in range(len(locs)) if i not in used_local]
    if leftover:
        lines.append("Local-only rows (will be removed on overwrite): %d" % len(leftover))
    return lines


def _clamp_dialog_text(text: str, max_chars: int = 3800) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 24] + "\n… (message truncated)"


def _build_sidecar_ask_detail(
    video_path,
    online_segments,
    policy,
    *,
    scope_xml,
    scope_edl,
    xml_path,
    edl_path,
):
    """
    Extra body text for overwrite/update confirmation (sources + per-sidecar diff).
    ``scope_*`` is which sidecar(s) this prompt applies to.
    """
    try:
        lines = _summarize_online_by_source(online_segments)
        if policy in (
            _SAVE_CHAPTERS_UPDATE_ASK,
            _SAVE_CHAPTERS_UPDATE_ALL_ASK,
        ):
            addon = get_addon()
            if scope_xml and xml_path:
                raw = safe_file_read(xml_path)
                existing = _parse_chapter_xml_string(raw) if raw else []
                ch = _sidecar_update_plan(list(existing), online_segments)[0]
                lines.append("")
                lines.append("[Chapters XML]")
                lines.extend(_lines_for_update_changes(ch))
            if scope_edl and edl_path:
                existing_e = parse_edl(video_path, update_monitor=False)
                ch2 = _sidecar_update_plan(
                    list(existing_e or []), online_segments
                )[0]
                lines.append("")
                lines.append("[EDL]")
                lines.extend(_lines_for_update_changes(ch2))
            snap_s, snap_e = _neighbor_snap_flags_for_policy(policy, addon)
            if snap_s or snap_e:
                lines.append("")
                if addon:
                    y_on = addon.getLocalizedString(35029)
                    n_off = addon.getLocalizedString(35030)
                    lines.append(addon.getLocalizedString(35026))
                    lines.append(
                        addon.getLocalizedString(35027)
                        % (y_on if snap_s else n_off)
                    )
                    lines.append(
                        addon.getLocalizedString(35028)
                        % (y_on if snap_e else n_off)
                    )
                else:
                    lines.append("[Neighbor snap]")
                    lines.append(
                        "Snap neighbor start: %s" % ("On" if snap_s else "Off")
                    )
                    lines.append(
                        "Snap neighbor end: %s" % ("On" if snap_e else "Off")
                    )
            if scope_xml and xml_path:
                raw = safe_file_read(xml_path)
                existing = _parse_chapter_xml_string(raw) if raw else []
                final = _finalize_sidecar_after_update_policy(
                    list(existing), online_segments, policy, addon
                )
                lines.append("")
                hdr = (
                    addon.getLocalizedString(35031)
                    if addon
                    else "If you accept, this sidecar will contain:"
                )
                lines.append("[Chapters XML] %s" % hdr)
                lines.extend(_lines_for_sidecar_preview_items(final))
            if scope_edl and edl_path:
                existing_e = parse_edl(video_path, update_monitor=False) or []
                final_e = _finalize_sidecar_after_update_policy(
                    list(existing_e), online_segments, policy, addon
                )
                lines.append("")
                hdr = (
                    addon.getLocalizedString(35031)
                    if addon
                    else "If you accept, this sidecar will contain:"
                )
                lines.append("[EDL] %s" % hdr)
                lines.extend(_lines_for_sidecar_preview_items(final_e))
        elif policy == _SAVE_CHAPTERS_OVERWRITE_ASK:
            if scope_xml and xml_path:
                raw = safe_file_read(xml_path)
                existing = _parse_chapter_xml_string(raw) if raw else []
                lines.append("")
                lines.append(
                    "[Chapters XML] Currently %d chapter(s); online returns %d window(s)."
                    % (len(existing), len(online_segments))
                )
                lines.extend(
                    _lines_overwrite_compare(existing, online_segments)
                )
            if scope_edl and edl_path:
                existing_e = parse_edl(video_path, update_monitor=False) or []
                lines.append("")
                lines.append(
                    "[EDL] Currently %d row(s); online returns %d window(s)."
                    % (len(existing_e), len(online_segments))
                )
                lines.extend(
                    _lines_overwrite_compare(existing_e, online_segments)
                )
        return _clamp_dialog_text("\n".join(lines))
    except Exception as exc:
        log("⚠ Could not build sidecar save prompt detail: %s" % exc)
        return ""


def _segments_signature_for_save_compare(segments, time_decimals=3):
    """Stable sorted tuples for comparing segment lists (times + normalized label)."""
    if not segments:
        return ()
    rows = []
    for s in segments:
        lab = getattr(s, "segment_type_label", None) or "segment"
        lab_s = (
            normalize_label(lab) if isinstance(lab, str) else normalize_label(str(lab))
        )
        rows.append(
            (
                round(float(s.start_seconds), time_decimals),
                round(float(s.end_seconds), time_decimals),
                lab_s,
            )
        )
    return tuple(sorted(rows))


def _sidecar_list_matches_online(existing_items, online_items):
    """True when both lists represent the same segment windows and labels."""
    return _segments_signature_for_save_compare(
        existing_items
    ) == _segments_signature_for_save_compare(online_items)


def _edl_action_triples_from_raw(edl_data, ignore_internal, type_map):
    """Sorted (start, end, action) tuples; rules aligned with parse_edl."""
    if not edl_data:
        return ()
    rows = []
    for line in edl_data.splitlines():
        parts = line.strip().split()
        if len(parts) != 3:
            continue
        try:
            s, e, action = float(parts[0]), float(parts[1]), int(parts[2])
        except ValueError:
            continue
        if ignore_internal and type_map.get(action) is None:
            continue
        rows.append((round(s, 3), round(e, 3), action))
    return tuple(sorted(rows))


def _edl_action_triples_from_segments(segments, time_decimals=3):
    """Same EDL triples we would write for segments (label -> action like save_edl)."""
    label_to_action = get_edl_label_to_action_map()
    rows = []
    for seg in segments:
        seg_label = getattr(seg, "segment_type_label", None) or "segment"
        if seg_label in label_to_action:
            action = label_to_action[seg_label]
        elif getattr(seg, "action_type", None) is not None:
            action = seg.action_type
        else:
            action = 4
        try:
            action = int(action)
        except (TypeError, ValueError):
            action = 4
        rows.append(
            (
                round(float(seg.start_seconds), time_decimals),
                round(float(seg.end_seconds), time_decimals),
                action,
            )
        )
    return tuple(sorted(rows))


def _edl_file_triples_match_segments(existing_path, segments):
    raw = safe_file_read(existing_path)
    _ig = get_addon()
    ignore_internal = (
        addon_get_bool(_ig, "ignore_internal_edl_actions", False) if _ig else False
    )
    disk = _edl_action_triples_from_raw(
        raw or "", ignore_internal, get_edl_type_map()
    )
    want = _edl_action_triples_from_segments(segments)
    return disk == want


def _chapter_xml_save_content_unchanged(video_path, segments, policy):
    """
    True if an existing chapter XML already matches what we would write
    (overwrite: same as online; merge: merge adds nothing).
    """
    if policy not in (
        _SAVE_CHAPTERS_MERGE,
        _SAVE_CHAPTERS_OVERWRITE_SILENT,
        _SAVE_CHAPTERS_OVERWRITE_ASK,
        _SAVE_CHAPTERS_UPDATE_SILENT,
        _SAVE_CHAPTERS_UPDATE_ASK,
        _SAVE_CHAPTERS_UPDATE_ALL_SILENT,
        _SAVE_CHAPTERS_UPDATE_ALL_ASK,
    ):
        return False
    if not segments:
        return True
    existing_path = _find_existing_sidecar_chapter_xml_path(video_path)
    if not existing_path:
        return False
    raw = safe_file_read(existing_path)
    existing_items = _parse_chapter_xml_string(raw) if raw else []
    if policy == _SAVE_CHAPTERS_MERGE:
        if not existing_items and raw:
            return False
        merged = _merge_sidecar_segments(list(existing_items), segments)
        return _segments_signature_for_save_compare(
            merged
        ) == _segments_signature_for_save_compare(existing_items)
    if policy in (
        _SAVE_CHAPTERS_UPDATE_SILENT,
        _SAVE_CHAPTERS_UPDATE_ASK,
        _SAVE_CHAPTERS_UPDATE_ALL_SILENT,
        _SAVE_CHAPTERS_UPDATE_ALL_ASK,
    ):
        if not existing_items and raw:
            return False
        updated = _finalize_sidecar_after_update_policy(
            list(existing_items), segments, policy, get_addon()
        )
        return _segments_signature_for_save_compare(
            updated
        ) == _segments_signature_for_save_compare(existing_items)
    return _sidecar_list_matches_online(existing_items, segments)


def _edl_save_content_unchanged(video_path, segments, policy):
    if policy not in (
        _SAVE_CHAPTERS_MERGE,
        _SAVE_CHAPTERS_OVERWRITE_SILENT,
        _SAVE_CHAPTERS_OVERWRITE_ASK,
        _SAVE_CHAPTERS_UPDATE_SILENT,
        _SAVE_CHAPTERS_UPDATE_ASK,
        _SAVE_CHAPTERS_UPDATE_ALL_SILENT,
        _SAVE_CHAPTERS_UPDATE_ALL_ASK,
    ):
        return False
    if not segments:
        return True
    existing_path = None
    for p in _edl_paths_to_try(video_path):
        if p and xbmcvfs.exists(p):
            existing_path = p
            break
    if not existing_path:
        return False
    existing_items = parse_edl(video_path, update_monitor=False)
    if policy == _SAVE_CHAPTERS_MERGE:
        if not existing_items:
            raw = safe_file_read(existing_path)
            if raw and str(raw).strip():
                return False
            merged = _merge_sidecar_segments([], segments)
            return _segments_signature_for_save_compare(
                merged
            ) == _segments_signature_for_save_compare(existing_items)
        merged = _merge_sidecar_segments(list(existing_items), segments)
        return _segments_signature_for_save_compare(
            merged
        ) == _segments_signature_for_save_compare(existing_items)
    if policy in (
        _SAVE_CHAPTERS_UPDATE_SILENT,
        _SAVE_CHAPTERS_UPDATE_ASK,
        _SAVE_CHAPTERS_UPDATE_ALL_SILENT,
        _SAVE_CHAPTERS_UPDATE_ALL_ASK,
    ):
        if not existing_items:
            raw = safe_file_read(existing_path)
            if raw and str(raw).strip():
                return False
            updated = _finalize_sidecar_after_update_policy(
                [], segments, policy, get_addon()
            )
            return _segments_signature_for_save_compare(
                updated
            ) == _segments_signature_for_save_compare(existing_items)
        updated = _finalize_sidecar_after_update_policy(
            list(existing_items), segments, policy, get_addon()
        )
        return _segments_signature_for_save_compare(
            updated
        ) == _segments_signature_for_save_compare(existing_items)
    return _edl_file_triples_match_segments(existing_path, segments)


def _build_chapters_xml_tree(segment_items):
    root = ET.Element("Chapters")
    edition = ET.SubElement(root, "EditionEntry")
    for seg in segment_items:
        atom = ET.SubElement(edition, "ChapterAtom")
        ET.SubElement(atom, "ChapterTimeStart").text = _seconds_to_chapter_hms(
            seg.start_seconds
        )
        ET.SubElement(atom, "ChapterTimeEnd").text = _seconds_to_chapter_hms(
            seg.end_seconds
        )
        disp = ET.SubElement(atom, "ChapterDisplay")
        lab = seg.segment_type_label or "segment"
        ET.SubElement(disp, "ChapterString").text = (
            lab if isinstance(lab, str) else str(lab)
        )
    try:
        ET.indent(root, space="  ")
    except AttributeError:
        pass
    return root


def _write_chapters_xml_to_path(out_path, segment_items):
    segment_items = dedupe_overlapping_same_label_segments(list(segment_items))
    root = _build_chapters_xml_tree(segment_items)
    try:
        xml_body = ET.tostring(root, encoding="unicode")
    except TypeError:
        xml_body = ET.tostring(root, encoding="utf-8").decode(
            "utf-8", errors="replace"
        )
    data = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_body
    ok, _nbytes = safe_file_write(out_path, data, is_bytes=False)
    if not ok:
        raise OSError("Chapter XML safe_file_write failed for %s" % out_path)


def _backup_sidecar_file(addon, src_path):
    if not addon or not addon_get_bool(
        addon, "save_online_chapters_backup_before_overwrite", True
    ):
        return
    bak = src_path + ".bck"
    try:
        if xbmcvfs.exists(bak):
            xbmcvfs.delete(bak)
        ok = False
        try:
            ok = xbmcvfs.copy(src_path, bak)
        except _VFS_IO_EXC:
            ok = False
        if not ok:
            inf = xbmcvfs.File(src_path)
            data = inf.read()
            inf.close()
            out = xbmcvfs.File(bak, "w")
            out.write(data)
            out.close()
        log("📋 Backed up existing sidecar to %s" % bak)
    except _VFS_IO_EXC as e:
        log("⚠️ Could not back up sidecar (%s): %s" % (bak, e))


def invalidate_segment_parse_cache_if_path(video_path, segment_monitor):
    """After online sidecar writes, drop cache so the next parse sees new mtimes/content."""
    if not video_path:
        return
    cache = segment_monitor.segment_parse_cache
    if cache and cache.get("path") == video_path:
        _log_sidecar_detail(
            "Clearing segment parse cache after online sidecar save for this file"
        )
        segment_monitor.segment_parse_cache = None
        publish_parse_cache(None)


def _maybe_save_online_segments_chapters_xml(
    video_path,
    segments,
    policy,
    addon,
    skip_overwrite_prompt=False,
    segment_monitor=None,
):
    existing_path = _find_existing_sidecar_chapter_xml_path(video_path)
    out_path = existing_path or _default_new_sidecar_chapter_xml_path(video_path)

    if not existing_path:
        if not segments:
            return
        try:
            _write_chapters_xml_to_path(out_path, list(segments))
            log(
                "💾 Saved chapter XML (%d segments) → %s"
                % (len(segments), out_path)
            )
        except _VFS_IO_EXC as e:
            log("⚠️ Could not save chapters.xml: %s" % e)
        return

    if policy == _SAVE_CHAPTERS_SKIP_IF_EXISTS:
        log(
            "Skipping save chapters.xml: file exists and policy is skip (%s)"
            % existing_path
        )
        return

    raw = safe_file_read(existing_path)
    existing_items = _parse_chapter_xml_string(raw) if raw else []
    items_to_write = list(segments)

    if policy == _SAVE_CHAPTERS_MERGE:
        if not existing_items and raw:
            log("⚠️ Merge skipped: could not parse existing chapter XML; not writing")
            return
        items_to_write = _merge_sidecar_segments(existing_items, segments)
        if _segments_signature_for_save_compare(
            items_to_write
        ) == _segments_signature_for_save_compare(existing_items):
            _log_sidecar_detail(
                "Skipping save chapters.xml: merged online data matches existing file"
            )
            return
        log(
            "Merging online segments into existing chapter XML → %d chapter atom(s)"
            % len(items_to_write)
        )
    elif policy in (
        _SAVE_CHAPTERS_UPDATE_SILENT,
        _SAVE_CHAPTERS_UPDATE_ASK,
        _SAVE_CHAPTERS_UPDATE_ALL_SILENT,
        _SAVE_CHAPTERS_UPDATE_ALL_ASK,
    ):
        if not existing_items and raw:
            log("⚠️ Update skipped: could not parse existing chapter XML; not writing")
            return
        items_to_write = _finalize_sidecar_after_update_policy(
            list(existing_items), segments, policy, addon
        )
        if _segments_signature_for_save_compare(
            items_to_write
        ) == _segments_signature_for_save_compare(existing_items):
            _log_sidecar_detail(
                "Skipping save chapters.xml: no changes from online update policy"
            )
            return
        if policy in (
            _SAVE_CHAPTERS_UPDATE_ALL_SILENT,
            _SAVE_CHAPTERS_UPDATE_ALL_ASK,
        ):
            log(
                "Update All: chapter XML from online → %d chapter atom(s)"
                % len(items_to_write)
            )
        else:
            log(
                "Updating matched segments in chapter XML from online → %d chapter atom(s)"
                % len(items_to_write)
            )
    elif policy in (
        _SAVE_CHAPTERS_OVERWRITE_SILENT,
        _SAVE_CHAPTERS_OVERWRITE_ASK,
    ):
        items_to_write = list(segments)
        if _sidecar_list_matches_online(existing_items, items_to_write):
            _log_sidecar_detail(
                "Skipping save chapters.xml: online segments match existing file"
            )
            return
        log(
            "Overwriting existing chapter XML with %d online segment(s)"
            % len(items_to_write)
        )

    if policy == _SAVE_CHAPTERS_OVERWRITE_ASK and not skip_overwrite_prompt:
        detail = _build_sidecar_ask_detail(
            video_path,
            segments,
            policy,
            scope_xml=True,
            scope_edl=False,
            xml_path=existing_path,
            edl_path=None,
        )
        msg = addon.getLocalizedString(35004)
        if detail:
            msg = "%s\n\n%s" % (msg, detail)
        yes = _sidecar_overwrite_yesno(addon.getLocalizedString(35000), msg)
        if not yes:
            log("User declined overwrite of existing chapter XML — not saving")
            _suppress_online_sidecar_save_prompt(video_path, segment_monitor)
            return
        _suppress_online_sidecar_save_prompt(video_path, segment_monitor)
    elif policy in (
        _SAVE_CHAPTERS_UPDATE_ASK,
        _SAVE_CHAPTERS_UPDATE_ALL_ASK,
    ) and not skip_overwrite_prompt:
        detail = _build_sidecar_ask_detail(
            video_path,
            segments,
            policy,
            scope_xml=True,
            scope_edl=False,
            xml_path=existing_path,
            edl_path=None,
        )
        h, mb = _sidecar_update_ask_heading_body(policy, "xml")
        msg = addon.getLocalizedString(mb)
        if detail:
            msg = "%s\n\n%s" % (msg, detail)
        yes = _sidecar_overwrite_yesno(addon.getLocalizedString(h), msg)
        if not yes:
            log("User declined update of existing chapter XML — not saving")
            _suppress_online_sidecar_save_prompt(video_path, segment_monitor)
            return
        _suppress_online_sidecar_save_prompt(video_path, segment_monitor)

    if existing_path and policy in (
        _SAVE_CHAPTERS_OVERWRITE_SILENT,
        _SAVE_CHAPTERS_OVERWRITE_ASK,
        _SAVE_CHAPTERS_MERGE,
        _SAVE_CHAPTERS_UPDATE_SILENT,
        _SAVE_CHAPTERS_UPDATE_ASK,
        _SAVE_CHAPTERS_UPDATE_ALL_SILENT,
        _SAVE_CHAPTERS_UPDATE_ALL_ASK,
    ):
        _backup_sidecar_file(addon, existing_path)

    try:
        _write_chapters_xml_to_path(out_path, items_to_write)
        log("💾 Saved chapter XML (%d segments) → %s" % (len(items_to_write), out_path))
    except _VFS_IO_EXC as e:
        log("⚠️ Could not save chapters.xml: %s" % e)


def _maybe_save_online_segments_edl(
    video_path,
    segments,
    policy,
    addon,
    skip_overwrite_prompt=False,
    segment_monitor=None,
):
    existing_path = None
    for p in _edl_paths_to_try(video_path):
        if p and xbmcvfs.exists(p):
            existing_path = p
            break
    base = video_path.rsplit(".", 1)[0]
    out_path = existing_path or (base + ".edl")

    if not existing_path:
        if not segments:
            return
        try:
            if not save_edl(video_path, list(segments)):
                raise OSError("save_edl returned False for %s" % out_path)
            log("💾 Saved EDL (%d segments) → %s" % (len(segments), out_path))
        except _VFS_IO_EXC as e:
            log("⚠️ Could not save EDL: %s" % e)
        return

    if policy == _SAVE_CHAPTERS_SKIP_IF_EXISTS:
        log(
            "Skipping save EDL: file exists and policy is skip (%s)"
            % existing_path
        )
        return

    existing_items = parse_edl(video_path, update_monitor=False)
    items_to_video = list(segments)

    if policy == _SAVE_CHAPTERS_MERGE:
        if not existing_items:
            raw = safe_file_read(existing_path)
            if raw and str(raw).strip():
                log("⚠️ Merge skipped: could not read/parse existing EDL; not writing")
                return
            items_to_video = _merge_sidecar_segments([], segments)
        else:
            items_to_video = _merge_sidecar_segments(existing_items, segments)
        if _segments_signature_for_save_compare(
            items_to_video
        ) == _segments_signature_for_save_compare(existing_items):
            _log_sidecar_detail(
                "Skipping save EDL: merged online data matches existing file"
            )
            return
        log(
            "Merging online segments into existing EDL → %d entr(y/ies)"
            % len(items_to_video)
        )
    elif policy in (
        _SAVE_CHAPTERS_UPDATE_SILENT,
        _SAVE_CHAPTERS_UPDATE_ASK,
        _SAVE_CHAPTERS_UPDATE_ALL_SILENT,
        _SAVE_CHAPTERS_UPDATE_ALL_ASK,
    ):
        if not existing_items:
            raw = safe_file_read(existing_path)
            if raw and str(raw).strip():
                log("⚠️ Update skipped: could not read/parse existing EDL; not writing")
                return
            items_to_video = _finalize_sidecar_after_update_policy(
                [], segments, policy, addon
            )
        else:
            items_to_video = _finalize_sidecar_after_update_policy(
                list(existing_items), segments, policy, addon
            )
        if _segments_signature_for_save_compare(
            items_to_video
        ) == _segments_signature_for_save_compare(existing_items):
            _log_sidecar_detail(
                "Skipping save EDL: no changes from online update policy"
            )
            return
        if policy in (
            _SAVE_CHAPTERS_UPDATE_ALL_SILENT,
            _SAVE_CHAPTERS_UPDATE_ALL_ASK,
        ):
            log(
                "Update All: EDL from online → %d entr(y/ies)"
                % len(items_to_video)
            )
        else:
            log(
                "Updating matched segments in existing EDL from online → %d entr(y/ies)"
                % len(items_to_video)
            )
    elif policy in (
        _SAVE_CHAPTERS_OVERWRITE_SILENT,
        _SAVE_CHAPTERS_OVERWRITE_ASK,
    ):
        items_to_video = list(segments)
        if _edl_file_triples_match_segments(existing_path, items_to_video):
            _log_sidecar_detail(
                "Skipping save EDL: on-disk EDL actions/times match online segments"
            )
            return
        log(
            "Overwriting existing EDL with %d online segment(s)"
            % len(items_to_video)
        )

    if policy == _SAVE_CHAPTERS_OVERWRITE_ASK and not skip_overwrite_prompt:
        detail = _build_sidecar_ask_detail(
            video_path,
            segments,
            policy,
            scope_xml=False,
            scope_edl=True,
            xml_path=None,
            edl_path=existing_path,
        )
        msg = addon.getLocalizedString(35005)
        if detail:
            msg = "%s\n\n%s" % (msg, detail)
        yes = _sidecar_overwrite_yesno(addon.getLocalizedString(35000), msg)
        if not yes:
            log("User declined overwrite of existing EDL — not saving")
            _suppress_online_sidecar_save_prompt(video_path, segment_monitor)
            return
        _suppress_online_sidecar_save_prompt(video_path, segment_monitor)
    elif policy in (
        _SAVE_CHAPTERS_UPDATE_ASK,
        _SAVE_CHAPTERS_UPDATE_ALL_ASK,
    ) and not skip_overwrite_prompt:
        detail = _build_sidecar_ask_detail(
            video_path,
            segments,
            policy,
            scope_xml=False,
            scope_edl=True,
            xml_path=None,
            edl_path=existing_path,
        )
        h, mb = _sidecar_update_ask_heading_body(policy, "edl")
        msg = addon.getLocalizedString(mb)
        if detail:
            msg = "%s\n\n%s" % (msg, detail)
        yes = _sidecar_overwrite_yesno(addon.getLocalizedString(h), msg)
        if not yes:
            log("User declined update of existing EDL — not saving")
            _suppress_online_sidecar_save_prompt(video_path, segment_monitor)
            return
        _suppress_online_sidecar_save_prompt(video_path, segment_monitor)

    if existing_path and policy in (
        _SAVE_CHAPTERS_OVERWRITE_SILENT,
        _SAVE_CHAPTERS_OVERWRITE_ASK,
        _SAVE_CHAPTERS_MERGE,
        _SAVE_CHAPTERS_UPDATE_SILENT,
        _SAVE_CHAPTERS_UPDATE_ASK,
        _SAVE_CHAPTERS_UPDATE_ALL_SILENT,
        _SAVE_CHAPTERS_UPDATE_ALL_ASK,
    ):
        _backup_sidecar_file(addon, existing_path)

    try:
        if not save_edl(video_path, items_to_video):
            raise OSError("save_edl returned False for %s" % out_path)
        log("💾 Saved EDL (%d segments) → %s" % (len(items_to_video), out_path))
    except _VFS_IO_EXC as e:
        log("⚠️ Could not save EDL: %s" % e)


def maybe_save_online_segments_to_sidecars(video_path, segments, segment_monitor):
    """
    When enabled, write online SegmentItems to `.edl` and/or chapters.xml beside the video.

    Formats are controlled by ``save_online_segments_format`` (Both / EDL / XML).
    Existing-file behavior uses ``save_online_chapters_existing_policy`` (normalized),
    separately per sidecar type that is being written.
    """
    addon = get_addon()
    if not _online_sidecar_save_allowed(addon, video_path, segments):
        return

    try:
        if not xbmc.Player().isPlayingVideo():
            _log_sidecar_detail("Skipping online sidecar save: video not playing")
            return
    except Exception:
        _log_sidecar_detail("Skipping online sidecar save: player state unavailable")
        return

    if (
        segment_monitor is not None
        and video_path
        and getattr(segment_monitor, "online_sidecar_save_prompt_suppressed_path", None)
        == video_path
    ):
        _log_sidecar_detail(
            "Skipping online sidecar save: overwrite/update already settled for "
            "this file (no re-prompt until next title)"
        )
        return

    fmt = _normalize_save_online_format(
        addon_get_setting_text(
            addon,
            "save_online_segments_format",
            _SAVE_ONLINE_FORMAT_BOTH,
        )
    )
    policy = _normalize_online_sidecar_policy(
        addon_get_setting_text(
            addon,
            "save_online_chapters_existing_policy",
            _SAVE_CHAPTERS_SKIP_IF_EXISTS,
        )
    )
    _log_sidecar_detail(
        "Online sidecar save: format=%s policy=%s" % (fmt, policy)
    )

    write_xml = fmt in (_SAVE_ONLINE_FORMAT_XML, _SAVE_ONLINE_FORMAT_BOTH)
    write_edl = fmt in (_SAVE_ONLINE_FORMAT_EDL, _SAVE_ONLINE_FORMAT_BOTH)
    do_xml = write_xml
    do_edl = write_edl
    if do_xml and _chapter_xml_save_content_unchanged(video_path, segments, policy):
        log(
            "Skipping chapter XML save: sidecar already matches online segment data"
        )
        do_xml = False
    if do_edl and _edl_save_content_unchanged(video_path, segments, policy):
        log("Skipping EDL save: sidecar already matches online segment data")
        do_edl = False

    if not do_xml and not do_edl:
        return

    skip_xml_prompt = False
    skip_edl_prompt = False

    if policy in (
        _SAVE_CHAPTERS_OVERWRITE_ASK,
        _SAVE_CHAPTERS_UPDATE_ASK,
        _SAVE_CHAPTERS_UPDATE_ALL_ASK,
    ):
        xml_existing = (
            _find_existing_sidecar_chapter_xml_path(video_path) if write_xml else None
        )
        edl_existing = None
        if write_edl:
            for p in _edl_paths_to_try(video_path):
                if p and xbmcvfs.exists(p):
                    edl_existing = p
                    break
        need_xml_ask = bool(xml_existing and do_xml)
        need_edl_ask = bool(edl_existing and do_edl)
        is_over = policy == _SAVE_CHAPTERS_OVERWRITE_ASK
        if need_xml_ask and need_edl_ask:
            h, m = (
                (35002, 35003)
                if is_over
                else _sidecar_update_ask_heading_body(policy, "both")
            )
            detail = _build_sidecar_ask_detail(
                video_path,
                segments,
                policy,
                scope_xml=True,
                scope_edl=True,
                xml_path=xml_existing,
                edl_path=edl_existing,
            )
            msg = addon.getLocalizedString(m)
            if detail:
                msg = "%s\n\n%s" % (msg, detail)
            if not _sidecar_overwrite_yesno(addon.getLocalizedString(h), msg):
                log(
                    "User declined %s of existing chapter XML and EDL — "
                    "not saving online sidecars"
                    % ("overwrite" if is_over else "update",)
                )
                _suppress_online_sidecar_save_prompt(video_path, segment_monitor)
                return
            skip_xml_prompt = True
            skip_edl_prompt = True
            _suppress_online_sidecar_save_prompt(video_path, segment_monitor)
        elif need_xml_ask:
            h, m = (
                (35000, 35004)
                if is_over
                else _sidecar_update_ask_heading_body(policy, "xml")
            )
            detail = _build_sidecar_ask_detail(
                video_path,
                segments,
                policy,
                scope_xml=True,
                scope_edl=False,
                xml_path=xml_existing,
                edl_path=None,
            )
            msg = addon.getLocalizedString(m)
            if detail:
                msg = "%s\n\n%s" % (msg, detail)
            if not _sidecar_overwrite_yesno(addon.getLocalizedString(h), msg):
                log(
                    "User declined %s of existing chapter XML — "
                    "not saving chapter XML from online"
                    % ("overwrite" if is_over else "update",)
                )
                do_xml = False
                if not (write_edl and do_edl):
                    _suppress_online_sidecar_save_prompt(
                        video_path, segment_monitor
                    )
            else:
                skip_xml_prompt = True
                _suppress_online_sidecar_save_prompt(video_path, segment_monitor)
        elif need_edl_ask:
            h, m = (
                (35000, 35005)
                if is_over
                else _sidecar_update_ask_heading_body(policy, "edl")
            )
            detail = _build_sidecar_ask_detail(
                video_path,
                segments,
                policy,
                scope_xml=False,
                scope_edl=True,
                xml_path=None,
                edl_path=edl_existing,
            )
            msg = addon.getLocalizedString(m)
            if detail:
                msg = "%s\n\n%s" % (msg, detail)
            if not _sidecar_overwrite_yesno(addon.getLocalizedString(h), msg):
                log(
                    "User declined %s of existing EDL — "
                    "not saving EDL from online"
                    % ("overwrite" if is_over else "update",)
                )
                do_edl = False
                if not do_xml:
                    _suppress_online_sidecar_save_prompt(
                        video_path, segment_monitor
                    )
            else:
                skip_edl_prompt = True
                _suppress_online_sidecar_save_prompt(video_path, segment_monitor)

    if do_xml:
        _maybe_save_online_segments_chapters_xml(
            video_path,
            segments,
            policy,
            addon,
            skip_overwrite_prompt=skip_xml_prompt,
            segment_monitor=segment_monitor,
        )
    if do_edl:
        _maybe_save_online_segments_edl(
            video_path,
            segments,
            policy,
            addon,
            skip_overwrite_prompt=skip_edl_prompt,
            segment_monitor=segment_monitor,
        )
    if do_xml or do_edl:
        invalidate_segment_parse_cache_if_path(video_path, segment_monitor)


def maybe_save_online_segments_to_chapters_xml(video_path, segments, segment_monitor):
    """Backward-compatible name; writes according to save format + policy."""
    maybe_save_online_segments_to_sidecars(video_path, segments, segment_monitor)
