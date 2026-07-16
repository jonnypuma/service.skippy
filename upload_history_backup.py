# -*- coding: utf-8 -*-
"""Backup and restore online upload submission history (merge on restore)."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone

import xbmcgui
import xbmcvfs

from online_segment_upload import (
    _HISTORY_VERSION,
    load_upload_submission_history,
    merge_upload_submission_history,
)
from settings_backup import (
    ADDON_ID,
    _join_writable_folder_file,
    _read_json_file,
    _restore_browse_result_is_json_file,
    _write_json_file,
)

SCHEMA = "skippy_upload_history_backup_v1"


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


def export_to_path(addon, dest_json_path: str) -> int:
    """Write upload history backup; returns fingerprint count."""
    history = load_upload_submission_history()
    count = len(history.get("theintrodb") or []) + len(history.get("introdb") or [])
    payload = {
        "schema": SCHEMA,
        "addon_id": ADDON_ID,
        "addon_version_exported": addon.getAddonInfo("version") or "",
        "exported_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "online_upload_submissions": history,
        "fingerprint_count": count,
    }
    _write_json_file(dest_json_path, payload)
    return count


def import_merge_from_path(addon, src_json_path: str) -> tuple[int, int, str]:
    """Merge backup fingerprints into profile history."""
    data = _read_json_file(src_json_path)
    if data.get("schema") != SCHEMA:
        raise ValueError("Not a Skippy upload history backup (wrong or missing schema).")
    if data.get("addon_id") != ADDON_ID:
        raise ValueError("This file is not a Skippy (service.skippy) upload history backup.")
    raw = data.get("online_upload_submissions")
    incoming = _normalize_history_blob(raw)
    added, already = merge_upload_submission_history(incoming)
    ver = data.get("addon_version_exported") or "?"
    note = "Backup from add-on version %s." % ver
    return added, already, note


def run_backup_ui(addon, icon_path: str, log_fn) -> None:
    heading = addon.getLocalizedString(38009) if addon else "Backup upload history"
    folder = xbmcgui.Dialog().browse(3, heading, "files", "", False, False, "")
    if not folder or not str(folder).strip():
        return
    stamp = time.strftime("%Y%m%d-%H%M%S")
    name = "skippy-upload-history-backup-%s.json" % stamp
    dest = _join_writable_folder_file(folder, name)
    try:
        n = export_to_path(addon, dest)
    except Exception as e:
        log_fn("upload history backup failed: %s" % e)
        xbmcgui.Dialog().ok(ADDON_ID, "%s\n%s" % (addon.getLocalizedString(38004), e))
        return
    log_fn("upload history backup wrote %s fingerprints to %s" % (n, dest))
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
    heading = addon.getLocalizedString(38011) if addon else "Restore upload history"
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
        added, already, note = import_merge_from_path(addon, path)
    except ValueError as e:
        log_fn("upload history restore rejected: %s" % e)
        xbmcgui.Dialog().ok(ADDON_ID, "%s\n%s" % (addon.getLocalizedString(38007), e))
        return
    except Exception as e:
        log_fn("upload history restore failed: %s" % e)
        xbmcgui.Dialog().ok(ADDON_ID, "%s\n%s" % (addon.getLocalizedString(38004), e))
        return
    log_fn(
        "upload history restore merge added=%s already=%s (%s)"
        % (added, already, note)
    )
    try:
        xbmcgui.Dialog().notification(
            heading,
            addon.getLocalizedString(38014) % (added, already),
            icon_path or "DefaultAddonService.png",
            6000,
            sound=False,
        )
    except Exception:
        xbmcgui.Dialog().ok(
            heading,
            "%s\n%s" % (addon.getLocalizedString(38014) % (added, already), note),
        )
