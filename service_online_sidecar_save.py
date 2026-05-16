"""Merge or update online segments into local sidecars; write chapters.xml / EDL."""

import xml.etree.ElementTree as ET
from collections import defaultdict

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
    _SAVE_CHAPTERS_UPDATE_ASK,
    _SAVE_CHAPTERS_UPDATE_SILENT,
    _SAVE_ONLINE_FORMAT_BOTH,
    _SAVE_ONLINE_FORMAT_EDL,
    _SAVE_ONLINE_FORMAT_XML,
    _normalize_online_sidecar_policy,
    _normalize_save_online_format,
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


def _safe_overwrite_yesno(heading, message):
    """Overwrite/merge prompt; Kodi GUI errors → declined (False)."""
    try:
        return bool(xbmcgui.Dialog().yesno(heading, message))
    except RuntimeError as e:
        log("⚠ Sidecar overwrite prompt failed (%s) — treating as declined" % e)
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
    Returns ``(change_rows, updated_list)`` where ``change_rows`` are dicts with
    keys local_label, old_start, old_end, new_start, new_end, online_label,
    online_source — only entries whose times actually change.
    """
    result = list(existing_items)
    changes = []
    used = set()
    onlines = sorted(online_items, key=lambda o: float(o.start_seconds))
    for o in onlines:
        canon_o = remote_payload_label_to_online_bucket(o.segment_type_label)
        if canon_o is None:
            continue
        best_i = _pick_best_local_index_for_online(result, used, canon_o, o)
        if best_i is None:
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
    return changes, result


def _update_sidecar_segments(existing_items, online_items):
    return _sidecar_update_plan(existing_items, online_items)[1]


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
        if policy == _SAVE_CHAPTERS_UPDATE_ASK:
            if scope_xml and xml_path:
                raw = safe_file_read(xml_path)
                existing = _parse_chapter_xml_string(raw) if raw else []
                ch, _ = _sidecar_update_plan(list(existing), online_segments)
                lines.append("")
                lines.append("[Chapters XML]")
                lines.extend(_lines_for_update_changes(ch))
            if scope_edl and edl_path:
                existing_e = parse_edl(video_path, update_monitor=False)
                ch2, _ = _sidecar_update_plan(list(existing_e or []), online_segments)
                lines.append("")
                lines.append("[EDL]")
                lines.extend(_lines_for_update_changes(ch2))
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
    if policy in (_SAVE_CHAPTERS_UPDATE_SILENT, _SAVE_CHAPTERS_UPDATE_ASK):
        if not existing_items and raw:
            return False
        updated = _update_sidecar_segments(list(existing_items), segments)
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
    if policy in (_SAVE_CHAPTERS_UPDATE_SILENT, _SAVE_CHAPTERS_UPDATE_ASK):
        if not existing_items:
            raw = safe_file_read(existing_path)
            if raw and str(raw).strip():
                return False
            updated = _update_sidecar_segments([], segments)
            return _segments_signature_for_save_compare(
                updated
            ) == _segments_signature_for_save_compare(existing_items)
        updated = _update_sidecar_segments(list(existing_items), segments)
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
    video_path, segments, policy, addon, skip_overwrite_prompt=False
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
    elif policy in (_SAVE_CHAPTERS_UPDATE_SILENT, _SAVE_CHAPTERS_UPDATE_ASK):
        if not existing_items and raw:
            log("⚠️ Update skipped: could not parse existing chapter XML; not writing")
            return
        items_to_write = _update_sidecar_segments(list(existing_items), segments)
        if _segments_signature_for_save_compare(
            items_to_write
        ) == _segments_signature_for_save_compare(existing_items):
            _log_sidecar_detail(
                "Skipping save chapters.xml: no matched segments to update from online"
            )
            return
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
        yes = _safe_overwrite_yesno(addon.getLocalizedString(35000), msg)
        if not yes:
            log("User declined overwrite of existing chapter XML — not saving")
            return
    elif policy == _SAVE_CHAPTERS_UPDATE_ASK and not skip_overwrite_prompt:
        detail = _build_sidecar_ask_detail(
            video_path,
            segments,
            policy,
            scope_xml=True,
            scope_edl=False,
            xml_path=existing_path,
            edl_path=None,
        )
        msg = addon.getLocalizedString(35013)
        if detail:
            msg = "%s\n\n%s" % (msg, detail)
        yes = _safe_overwrite_yesno(addon.getLocalizedString(35012), msg)
        if not yes:
            log("User declined update of existing chapter XML — not saving")
            return

    if existing_path and policy in (
        _SAVE_CHAPTERS_OVERWRITE_SILENT,
        _SAVE_CHAPTERS_OVERWRITE_ASK,
        _SAVE_CHAPTERS_MERGE,
        _SAVE_CHAPTERS_UPDATE_SILENT,
        _SAVE_CHAPTERS_UPDATE_ASK,
    ):
        _backup_sidecar_file(addon, existing_path)

    try:
        _write_chapters_xml_to_path(out_path, items_to_write)
        log("💾 Saved chapter XML (%d segments) → %s" % (len(items_to_write), out_path))
    except _VFS_IO_EXC as e:
        log("⚠️ Could not save chapters.xml: %s" % e)


def _maybe_save_online_segments_edl(
    video_path, segments, policy, addon, skip_overwrite_prompt=False
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
    elif policy in (_SAVE_CHAPTERS_UPDATE_SILENT, _SAVE_CHAPTERS_UPDATE_ASK):
        if not existing_items:
            raw = safe_file_read(existing_path)
            if raw and str(raw).strip():
                log("⚠️ Update skipped: could not read/parse existing EDL; not writing")
                return
            items_to_video = _update_sidecar_segments([], segments)
        else:
            items_to_video = _update_sidecar_segments(
                list(existing_items), segments
            )
        if _segments_signature_for_save_compare(
            items_to_video
        ) == _segments_signature_for_save_compare(existing_items):
            _log_sidecar_detail(
                "Skipping save EDL: no matched segments to update from online"
            )
            return
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
        yes = _safe_overwrite_yesno(addon.getLocalizedString(35000), msg)
        if not yes:
            log("User declined overwrite of existing EDL — not saving")
            return
    elif policy == _SAVE_CHAPTERS_UPDATE_ASK and not skip_overwrite_prompt:
        detail = _build_sidecar_ask_detail(
            video_path,
            segments,
            policy,
            scope_xml=False,
            scope_edl=True,
            xml_path=None,
            edl_path=existing_path,
        )
        msg = addon.getLocalizedString(35015)
        if detail:
            msg = "%s\n\n%s" % (msg, detail)
        yes = _safe_overwrite_yesno(addon.getLocalizedString(35014), msg)
        if not yes:
            log("User declined update of existing EDL — not saving")
            return

    if existing_path and policy in (
        _SAVE_CHAPTERS_OVERWRITE_SILENT,
        _SAVE_CHAPTERS_OVERWRITE_ASK,
        _SAVE_CHAPTERS_MERGE,
        _SAVE_CHAPTERS_UPDATE_SILENT,
        _SAVE_CHAPTERS_UPDATE_ASK,
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

    if policy in (_SAVE_CHAPTERS_OVERWRITE_ASK, _SAVE_CHAPTERS_UPDATE_ASK):
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
                else (35016, 35017)
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
            if not _safe_overwrite_yesno(addon.getLocalizedString(h), msg):
                log(
                    "User declined %s of existing chapter XML and EDL — "
                    "not saving online sidecars"
                    % ("overwrite" if is_over else "update",)
                )
                return
            skip_xml_prompt = True
            skip_edl_prompt = True
        elif need_xml_ask:
            h, m = (
                (35000, 35004)
                if is_over
                else (35012, 35013)
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
            if not _safe_overwrite_yesno(addon.getLocalizedString(h), msg):
                log(
                    "User declined %s of existing chapter XML — "
                    "not saving chapter XML from online"
                    % ("overwrite" if is_over else "update",)
                )
                do_xml = False
            else:
                skip_xml_prompt = True
        elif need_edl_ask:
            h, m = (
                (35000, 35005)
                if is_over
                else (35014, 35015)
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
            if not _safe_overwrite_yesno(addon.getLocalizedString(h), msg):
                log(
                    "User declined %s of existing EDL — "
                    "not saving EDL from online"
                    % ("overwrite" if is_over else "update",)
                )
                do_edl = False
            else:
                skip_edl_prompt = True

    if do_xml:
        _maybe_save_online_segments_chapters_xml(
            video_path,
            segments,
            policy,
            addon,
            skip_overwrite_prompt=skip_xml_prompt,
        )
    if do_edl:
        _maybe_save_online_segments_edl(
            video_path,
            segments,
            policy,
            addon,
            skip_overwrite_prompt=skip_edl_prompt,
        )
    if do_xml or do_edl:
        invalidate_segment_parse_cache_if_path(video_path, segment_monitor)


def maybe_save_online_segments_to_chapters_xml(video_path, segments, segment_monitor):
    """Backward-compatible name; writes according to save format + policy."""
    maybe_save_online_segments_to_sidecars(video_path, segments, segment_monitor)
