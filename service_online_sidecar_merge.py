# -*- coding: utf-8 -*-
"""Merge / update / neighbor-snap policy for online sidecar saves."""
from __future__ import annotations

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

def _log_sidecar_detail(msg):
    log_service_detail(msg, tag="sidecar")
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
