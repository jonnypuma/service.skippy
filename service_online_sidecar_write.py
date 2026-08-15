# -*- coding: utf-8 -*-
"""Write chapters.xml / EDL and detect unchanged sidecar content."""
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
        ET.SubElement(atom, "ChapterTimeStart").text = seconds_to_hms(seg.start_seconds)
        ET.SubElement(atom, "ChapterTimeEnd").text = seconds_to_hms(seg.end_seconds)
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
    try:
        from service_sidecar_probe_cache import clear_sidecar_probe_cache

        clear_sidecar_probe_cache(segment_monitor, video_path)
    except Exception:
        pass
