# -*- coding: utf-8 -*-
"""Prompt to upload local sidecar segments missing from online databases."""

from __future__ import annotations

import xbmc
import xbmcgui

from online_segment_upload import (
    TARGET_BOTH,
    TARGET_INTRODB_APP,
    TARGET_THEINTRODB,
    _media_key,
    _upload_time_range,
    classify_segment_label_normalized,
    local_label_to_online_bucket,
    remote_payload_label_to_online_bucket,
    segment_has_pending_upload,
    upload_segments_subset,
)
from remote_segments import (
    build_upload_context,
    fetch_remote_movie_segments,
    fetch_remote_tv_segments,
    get_enriched_item_for_path,
)
from settings_utils import (
    addon_get_setting_text,
    get_addon,
    log,
    log_service_detail,
    normalize_label,
)
from skippy_editor_modal_skin import sidecar_overwrite_yesno_show

_SYNC_OFF = "Off"
_SYNC_ASK = "Ask"

_SYNC_LABEL_NORMALIZED = {
    normalize_label("Off"): _SYNC_OFF,
    normalize_label("Ask"): _SYNC_ASK,
}


def _log_sync_detail(msg: str) -> None:
    log_service_detail(msg, tag="sync_up")


def sync_local_to_online_policy(addon) -> str:
    raw = addon_get_setting_text(addon, "sync_local_to_online", _SYNC_OFF) or _SYNC_OFF
    if raw in (_SYNC_OFF, _SYNC_ASK):
        return raw
    mapped = _SYNC_LABEL_NORMALIZED.get(normalize_label(raw))
    if mapped:
        return mapped
    return _SYNC_OFF


def sync_local_to_online_enabled(addon) -> bool:
    if not addon or addon.getSetting("online_upload_enabled") != "true":
        return False
    return sync_local_to_online_policy(addon) == _SYNC_ASK


def probe_remote_segments_for_sync(playback_type, segment_monitor, segment_player):
    """Fetch online segments for sync comparison (uses service remote cache)."""
    try:
        total_time = segment_player.getTotalTime()
    except RuntimeError:
        total_time = 0
    cache = segment_monitor.remote_segment_cache
    if playback_type == "episode":
        return fetch_remote_tv_segments(total_time, cache) or []
    if playback_type == "movie":
        return fetch_remote_movie_segments(total_time, cache) or []
    return []


def _remote_buckets(remote_items) -> set[str]:
    buckets = set()
    for seg in remote_items or []:
        lab = getattr(seg, "segment_type_label", "") or ""
        b = remote_payload_label_to_online_bucket(lab)
        if b:
            buckets.add(b)
    return buckets


def _pick_local_for_bucket(local_items, bucket: str):
    candidates = []
    for seg in local_items or []:
        b = local_label_to_online_bucket(getattr(seg, "segment_type_label", "") or "")
        if b == bucket:
            candidates.append(seg)
    if not candidates:
        return None
    return min(candidates, key=lambda s: float(getattr(s, "start_seconds", 0) or 0))


def _upload_target_from_settings(addon) -> str:
    order = [TARGET_BOTH, TARGET_THEINTRODB, TARGET_INTRODB_APP]
    raw = addon_get_setting_text(addon, "online_upload_default_target", TARGET_BOTH) or TARGET_BOTH
    return raw if raw in order else TARGET_BOTH


def compute_local_to_online_upload_candidates(
    video_path,
    local_items,
    remote_items,
    addon,
) -> list:
    """
    Local segments whose canonical bucket is absent online and still pending upload.
    """
    if not local_items:
        return []

    item = get_enriched_item_for_path(video_path)
    ctx = build_upload_context(item)
    if not ctx:
        _log_sync_detail("Sync upload: no TMDB/library context")
        return []

    target = _upload_target_from_settings(addon)
    media_key = _media_key(ctx)
    t_db_key = (addon.getSetting("online_upload_theintrodb_api_key") or "").strip()
    idb_key = (addon.getSetting("online_upload_introdb_api_key") or "").strip()

    remote_b = _remote_buckets(remote_items)
    local_buckets = set()
    for seg in local_items:
        b = local_label_to_online_bucket(getattr(seg, "segment_type_label", "") or "")
        if b:
            local_buckets.add(b)

    pending_buckets = sorted(local_buckets - remote_b)
    candidates = []
    for bucket in pending_buckets:
        seg = _pick_local_for_bucket(local_items, bucket)
        if not seg:
            continue
        if not segment_has_pending_upload(seg, target, media_key, t_db_key, idb_key):
            continue
        candidates.append(seg)

    return candidates


def _format_sync_prompt_body(candidates, remote_items) -> str:
    addon = get_addon()
    intro = ""
    if addon:
        if remote_items:
            intro = addon.getLocalizedString(39061) or ""
        else:
            intro = addon.getLocalizedString(39060) or ""
    if not intro.strip():
        intro = (
            "Some segment types from your local sidecar are not online yet."
            if remote_items
            else "No online segment data was found for this title."
        )

    header = ""
    if addon:
        header = addon.getLocalizedString(39062) or ""
    if not header.strip():
        header = "Local sidecar has segments not found online:"

    lines = []
    for seg in candidates:
        mapped = classify_segment_label_normalized(
            getattr(seg, "segment_type_label", "") or ""
        )
        bucket = mapped[0] if mapped else "segment"
        raw = getattr(seg, "raw_label", None) or getattr(seg, "segment_type_label", bucket)
        tr = _upload_time_range(seg.start_seconds, seg.end_seconds)
        lines.append("  • %s (%s)  %s" % (raw, bucket, tr))

    footer = ""
    if addon:
        footer = addon.getLocalizedString(39063) or ""
    if not footer.strip():
        footer = "Upload these using your default upload target?"

    return intro + "\n\n" + header + "\n\n" + "\n".join(lines) + "\n\n" + footer


def _suppress_sync_prompt(video_path, segment_monitor) -> None:
    if segment_monitor is not None and video_path:
        segment_monitor.local_to_online_sync_suppressed_path = video_path


def _sync_yesno(heading, message) -> bool:
    try:
        if not xbmc.Player().isPlayingVideo():
            _log_sync_detail("Sync prompt suppressed: video not playing")
            return False
    except Exception:
        _log_sync_detail("Sync prompt suppressed: player state unavailable")
        return False

    addon = get_addon()
    try:
        if addon:
            ylbl = addon.getLocalizedString(35018) or "Yes"
            clbl = addon.getLocalizedString(35019) or "Cancel"
        else:
            ylbl, clbl = "Yes", "Cancel"
    except Exception:
        ylbl, clbl = "Yes", "Cancel"

    try:
        return sidecar_overwrite_yesno_show(heading, message or "", ylbl, clbl)
    except Exception as exc:
        log("⚠ Sync prompt failed (%s) — falling back to stock yesno" % exc)
        try:
            return xbmcgui.Dialog().yesno(heading, message or "", nolabel=clbl, yeslabel=ylbl)
        except Exception:
            return False


def _playback_allows_sync_prompt(segment_monitor) -> bool:
    try:
        if not xbmc.Player().isPlayingVideo():
            return False
    except Exception:
        return False
    if segment_monitor is not None and getattr(
        segment_monitor, "skip_dialog_modal_active", False
    ):
        return False
    try:
        win = xbmcgui.Window(10000)
        if win.getProperty("skippy_editor_modal_open") == "true":
            return False
    except Exception:
        pass
    return True


def maybe_prompt_sync_local_to_online(
    video_path,
    playback_type,
    local_items,
    remote_items,
    segment_monitor,
) -> None:
    """Ask once per title to upload local segment types missing online."""
    addon = get_addon()
    if not sync_local_to_online_enabled(addon):
        return
    if not local_items:
        return
    if (
        segment_monitor is not None
        and video_path
        and getattr(segment_monitor, "local_to_online_sync_suppressed_path", None)
        == video_path
    ):
        _log_sync_detail("Sync upload skipped: already settled for this file")
        return
    if not _playback_allows_sync_prompt(segment_monitor):
        _log_sync_detail("Sync upload skipped: playback/modal guard")
        return

    candidates = compute_local_to_online_upload_candidates(
        video_path, local_items, remote_items, addon
    )
    if not candidates:
        _log_sync_detail("Sync upload: no pending candidates")
        return

    t_db_key = (addon.getSetting("online_upload_theintrodb_api_key") or "").strip()
    idb_key = (addon.getSetting("online_upload_introdb_api_key") or "").strip()
    target = _upload_target_from_settings(addon)
    do_tidb = target in (TARGET_BOTH, TARGET_THEINTRODB) and bool(t_db_key)
    do_idb = target in (TARGET_BOTH, TARGET_INTRODB_APP) and bool(idb_key)
    if not do_tidb and not do_idb:
        _log_sync_detail("Sync upload skipped: no API keys for chosen target")
        return

    heading = addon.getLocalizedString(39059) if addon else ""
    if not (heading or "").strip():
        heading = "Sync local segments to online?"
    body = _format_sync_prompt_body(candidates, remote_items)

    yes = _sync_yesno(heading, body)
    _suppress_sync_prompt(video_path, segment_monitor)
    if not yes:
        _log_sync_detail("Sync upload declined by user")
        return

    _log_sync_detail(
        "Sync upload accepted: %d segment(s) for %s"
        % (len(candidates), video_path)
    )
    upload_segments_subset(
        video_path,
        candidates,
        target,
        show_empty_message=False,
        show_result=True,
    )
