# -*- coding: utf-8 -*-
"""Ask-dialog preview text for online sidecar save."""
from __future__ import annotations



from online_segment_upload import (
    local_label_to_online_bucket,
    remote_payload_label_to_online_bucket,
)
from segment_editor_parser import (
    seconds_to_hms,
)
from service_online_policy import (
    _SAVE_CHAPTERS_OVERWRITE_ASK,
    _SAVE_CHAPTERS_UPDATE_ALL_ASK,
    _SAVE_CHAPTERS_UPDATE_ASK,
)
from service_segment_sources import (
    _parse_chapter_xml_string,
    parse_edl,
    safe_file_read,
)
from settings_utils import (
    get_addon,
    log,
    log_service_detail,
)
from service_online_sidecar_merge import (
    _t,
    _finalize_sidecar_after_update_policy,
    _neighbor_snap_flags_for_policy,
    _pick_best_local_index_for_online,
    _sidecar_update_plan,
    _source_display_name,
    _summarize_online_by_source,
)


def _log_sidecar_detail(msg):
    log_service_detail(msg, tag="sidecar")


def _lines_for_sidecar_preview_items(final_items, max_rows=36):
    lines = []
    if not final_items:
        lines.append("  " + _t(35032, "(empty)"))
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
        lines.append("  " + _t(35033, "… +%d more", len(final_items) - max_rows))
    return lines


def _lines_for_update_changes(change_rows, max_rows=14):
    lines = []
    if not change_rows:
        lines.append(
            _t(35034, "No overlapping segment types to update — local times already match.")
        )
        return lines
    lines.append(_t(35035, "Planned time updates (local label kept):"))
    for r in change_rows[:max_rows]:
        lines.append(
            "  • %s:  %s – %s  →  %s – %s  "
            % (
                r["local_label"],
                seconds_to_hms(r["old_start"]),
                seconds_to_hms(r["old_end"]),
                seconds_to_hms(r["new_start"]),
                seconds_to_hms(r["new_end"]),
            )
            + _t(
                35036,
                "(online %s from %s)",
                r["online_label"],
                _source_display_name(r["online_source"]),
            )
        )
    if len(change_rows) > max_rows:
        lines.append("  " + _t(35037, "… +%d more change(s)", len(change_rows) - max_rows))
    return lines


def _lines_overwrite_compare(local_items, online_items, max_lines=18):
    """Pair online windows to locals by canonical bucket for informational diff."""
    lines = []
    if not online_items:
        return lines
    locs = list(local_items)
    used_local = set()
    lines.append(_t(35038, "Overwrite replaces the file with online windows only. Comparison:"))
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
                "  + "
                + _t(35039, "Online-only type %s", olab)
                + "  %s – %s  (%s)" % (seconds_to_hms(osh), seconds_to_hms(oeh), src)
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
                "  + %s  %s – %s  (%s) — " % (olab, seconds_to_hms(osh), seconds_to_hms(oeh), src)
                + _t(35040, "no same-type local entry")
            )
            count += 1
            continue
        best_i = _pick_best_local_index_for_online(locs, used_local, canon_o, o)
        if best_i is None:
            continue
        e = locs[best_i]
        used_local.add(best_i)
        lines.append(
            "  • "
            + _t(
                35041,
                "%s  local %s – %s  →  online (%s) %s – %s",
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
        lines.append(_t(35042, "Local-only rows (will be removed on overwrite): %d", len(leftover)))
    return lines


def _clamp_dialog_text(text: str, max_chars: int = 3800) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 24] + "\n… " + _t(35043, "(message truncated)")


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
                    _t(
                        35044,
                        "[Chapters XML] Currently %d chapter(s); online returns %d window(s).",
                        len(existing),
                        len(online_segments),
                    )
                )
                lines.extend(
                    _lines_overwrite_compare(existing, online_segments)
                )
            if scope_edl and edl_path:
                existing_e = parse_edl(video_path, update_monitor=False) or []
                lines.append("")
                lines.append(
                    _t(
                        35045,
                        "[EDL] Currently %d row(s); online returns %d window(s).",
                        len(existing_e),
                        len(online_segments),
                    )
                )
                lines.extend(
                    _lines_overwrite_compare(existing_e, online_segments)
                )
        return _clamp_dialog_text("\n".join(lines))
    except Exception as exc:
        log("⚠ Could not build sidecar save prompt detail: %s" % exc)
        return ""
