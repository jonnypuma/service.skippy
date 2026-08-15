"""Merge or update online segments into local sidecars; write chapters.xml / EDL."""
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

from service_online_sidecar_merge import (  # noqa: F401
    _apply_neighbor_snap_trims,
    _finalize_sidecar_after_update_policy,
    _insert_unmatched_with_neighbor_snaps,
    _merge_sidecar_segments,
    _neighbor_snap_flags_for_policy,
    _pick_best_local_index_for_online,
    _prune_zero_or_negative_length_segments,
    _segment_item_with_times,
    _sidecar_update_plan,
    _snap_after_retimed_segments,
    _source_display_name,
    _summarize_online_by_source,
    _update_sidecar_segments,
)
from service_online_sidecar_preview import (  # noqa: F401
    _build_sidecar_ask_detail,
    _clamp_dialog_text,
    _lines_for_sidecar_preview_items,
    _lines_for_update_changes,
    _lines_overwrite_compare,
)
from service_online_sidecar_write import (  # noqa: F401
    _backup_sidecar_file,
    _build_chapters_xml_tree,
    _chapter_xml_save_content_unchanged,
    _edl_file_triples_match_segments,
    _edl_save_content_unchanged,
    _sidecar_list_matches_online,
    _write_chapters_xml_to_path,
    invalidate_segment_parse_cache_if_path,
)
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
