# -*- coding: utf-8 -*-
"""Backup and restore profile data: upload history, title autoskip, statistics.

Restore merges into the local profile (upload fingerprints union; title overrides
merge per key; statistics take the larger counter values). Legacy
``skippy_upload_history_backup_v1`` files (history only) still restore.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

import xbmcgui

from online_segment_upload import (
    _HISTORY_VERSION,
    load_upload_submission_history,
    merge_upload_submission_history,
)
from per_show_overrides import export_all_overrides, merge_overrides_from_backup
from settings_backup import (
    ADDON_ID,
    _join_writable_folder_file,
    _read_json_file,
    _restore_browse_result_is_json_file,
    _write_json_file,
)
from skippy_stats import load_statistics, merge_statistics_from_backup

SCHEMA = "skippy_profile_data_backup_v1"
LEGACY_SCHEMA = "skippy_upload_history_backup_v1"
_ACCEPTED_SCHEMAS = (SCHEMA, LEGACY_SCHEMA)


def _normalize_history_blob(raw) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("Backup has no online_upload_submissions object.")
    out = {
        "v": int(raw.get("v") or _HISTORY_VERSION),
        "theintrodb": [],
        "introdb": [],
    }
    for bucket in ("theintrodb", "introdb"):
        lst = raw.get(bucket) or []
        if not isinstance(lst, list):
            continue
        out[bucket] = [str(x).strip() for x in lst if str(x).strip()]
    return out


def _normalize_overrides_blob(raw) -> dict:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("Backup show_overrides must be an object.")
    out = {}
    for key, payload in raw.items():
        if not isinstance(key, str) or not isinstance(payload, dict):
            continue
        store_key = key.strip()
        if not store_key or any(ch in store_key for ch in "/\\:"):
            continue
        segments_raw = payload.get("segments")
        if not isinstance(segments_raw, dict):
            continue
        segments = {}
        for label, mode in segments_raw.items():
            if mode in ("auto", "declined") and str(label).strip():
                segments[str(label).strip()] = mode
        if not segments:
            continue
        entry = {"schema": payload.get("schema") or "skippy_show_overrides_v1",
                 "key": store_key,
                 "segments": segments}
        title = (payload.get("title") or "").strip()
        if title:
            entry["title"] = title
        out[store_key] = entry
    return out


def export_to_path(addon, dest_json_path: str) -> dict:
    """Write profile-data backup; returns counts dict for logging/UI."""
    history = load_upload_submission_history()
    fingerprint_count = len(history.get("theintrodb") or []) + len(
        history.get("introdb") or []
    )
    overrides = export_all_overrides()
    stats = load_statistics()
    payload = {
        "schema": SCHEMA,
        "addon_id": ADDON_ID,
        "addon_version_exported": addon.getAddonInfo("version") or "",
        "exported_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "online_upload_submissions": history,
        "fingerprint_count": fingerprint_count,
        "show_overrides": overrides,
        "override_title_count": len(overrides),
        "statistics": stats,
    }
    _write_json_file(dest_json_path, payload)
    return {
        "fingerprints": fingerprint_count,
        "override_titles": len(overrides),
        "skip_total": int((stats.get("skips") or {}).get("total") or 0),
    }


def import_merge_from_path(addon, src_json_path: str) -> tuple[dict, str]:
    """
    Merge backup profile data into the local profile.

    Returns ``(summary, note)`` where summary has history/override/stats fields.
    """
    data = _read_json_file(src_json_path)
    schema = data.get("schema")
    if schema not in _ACCEPTED_SCHEMAS:
        raise ValueError("Not a Skippy profile-data backup (wrong or missing schema).")
    if data.get("addon_id") != ADDON_ID:
        raise ValueError(
            "This file is not a Skippy (service.skippy) profile-data backup."
        )

    summary = {
        "history_added": 0,
        "history_already": 0,
        "override_titles": 0,
        "override_segments_added": 0,
        "override_segments_updated": 0,
        "stats_merged": False,
    }

    raw_history = data.get("online_upload_submissions")
    if raw_history is not None:
        incoming = _normalize_history_blob(raw_history)
        added, already = merge_upload_submission_history(incoming)
        summary["history_added"] = added
        summary["history_already"] = already

    if schema == SCHEMA:
        overrides = _normalize_overrides_blob(data.get("show_overrides"))
        if overrides:
            titles, added, updated = merge_overrides_from_backup(overrides)
            summary["override_titles"] = titles
            summary["override_segments_added"] = added
            summary["override_segments_updated"] = updated
        if "statistics" in data:
            summary["stats_merged"] = bool(
                merge_statistics_from_backup(data.get("statistics"))
            )

    ver = data.get("addon_version_exported") or "?"
    note = "Backup from add-on version %s." % ver
    return summary, note


def _format_restore_summary(addon, summary: dict) -> str:
    """Localized one-line restore result for toast / dialog."""
    from settings_utils import get_localized

    stats_word = get_localized(
        addon,
        38020 if summary.get("stats_merged") else 38021,
        "updated" if summary.get("stats_merged") else "unchanged",
    )
    return get_localized(
        addon,
        38014,
        "Merged: %d new fingerprint(s) (%d already present); "
        "%d title auto-skip(s); %d segment rule(s); statistics %s.",
        int(summary.get("history_added") or 0),
        int(summary.get("history_already") or 0),
        int(summary.get("override_titles") or 0),
        int(summary.get("override_segments_added") or 0)
        + int(summary.get("override_segments_updated") or 0),
        stats_word,
    )


def run_backup_ui(addon, icon_path: str, log_fn) -> None:
    heading = (
        addon.getLocalizedString(38009) if addon else "Back up profile data"
    )
    folder = xbmcgui.Dialog().browse(3, heading, "files", "", False, False, "")
    if not folder or not str(folder).strip():
        return
    stamp = time.strftime("%Y%m%d-%H%M%S")
    name = "skippy-profile-data-backup-%s.json" % stamp
    dest = _join_writable_folder_file(folder, name)
    try:
        counts = export_to_path(addon, dest)
    except Exception as e:
        log_fn("profile data backup failed: %s" % e)
        xbmcgui.Dialog().ok(ADDON_ID, "%s\n%s" % (addon.getLocalizedString(38004), e))
        return
    log_fn(
        "profile data backup wrote fingerprints=%s override_titles=%s skips=%s to %s"
        % (
            counts.get("fingerprints"),
            counts.get("override_titles"),
            counts.get("skip_total"),
            dest,
        )
    )
    try:
        xbmcgui.Dialog().notification(
            heading,
            addon.getLocalizedString(38005) % name,
            icon_path or "DefaultAddonService.png",
            4500,
            sound=False,
        )
    except Exception:
        xbmcgui.Dialog().ok(heading, addon.getLocalizedString(38005) % name)


def run_restore_ui(addon, icon_path: str, log_fn) -> None:
    heading = (
        addon.getLocalizedString(38011) if addon else "Restore profile data"
    )
    path = xbmcgui.Dialog().browse(1, heading, "files", ".json", False, False, "")
    if not _restore_browse_result_is_json_file(path):
        return
    yes = xbmcgui.Dialog().yesno(
        ADDON_ID,
        addon.getLocalizedString(38013),
    )
    if not yes:
        return
    try:
        summary, note = import_merge_from_path(addon, path)
    except ValueError as e:
        log_fn("profile data restore rejected: %s" % e)
        xbmcgui.Dialog().ok(ADDON_ID, "%s\n%s" % (addon.getLocalizedString(38007), e))
        return
    except Exception as e:
        log_fn("profile data restore failed: %s" % e)
        xbmcgui.Dialog().ok(ADDON_ID, "%s\n%s" % (addon.getLocalizedString(38004), e))
        return
    message = _format_restore_summary(addon, summary)
    log_fn("profile data restore %s (%s)" % (message, note))
    try:
        xbmcgui.Dialog().notification(
            heading,
            message,
            icon_path or "DefaultAddonService.png",
            6000,
            sound=False,
        )
    except Exception:
        xbmcgui.Dialog().ok(heading, "%s\n%s" % (message, note))
