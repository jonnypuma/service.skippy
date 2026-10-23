# -*- coding: utf-8 -*-
"""Source picker: local sidecar vs two agreeing online sources.

When TheIntroDB and IntroDB.app agree (start and end within 1.5 s) but the local sidecar
differs by more, the user can review the sources in a modal, jump to each start/end and keep
one source. The choice is stored per video file and applied whenever segments are parsed.
"""
from __future__ import annotations

from online_segment_upload import (
    local_label_to_online_bucket,
    remote_payload_label_to_online_bucket,
)
from settings_utils import addon_get_bool, get_addon, log, log_service_detail
from skippy_profile_store import profile_path, read_json, write_json

TOLERANCE_S = 1.5
CHOICES_FILE = "source_choices.json"
CHOICE_LOCAL = "local"
CHOICE_ONLINE = "online"
MAX_STORED_FILES = 300


def source_conflict_enabled(addon) -> bool:
    return bool(addon) and addon_get_bool(addon, "source_conflict_prompt", False)


class SourceConflict:
    def __init__(self, bucket, label, local, online, online_sources):
        self.bucket = bucket
        self.label = label
        self.local = local
        self.online = online
        self.online_sources = online_sources


def _local_candidate(local_items, bucket, near):
    best = None
    for seg in local_items or []:
        if local_label_to_online_bucket(getattr(seg, "segment_type_label", "") or "") != bucket:
            continue
        if best is None or abs(seg.start_seconds - near) < abs(best.start_seconds - near):
            best = seg
    return best


def find_source_conflicts(local_items, remote_items, tol=TOLERANCE_S):
    """Segments where both online sources agree but the local sidecar does not."""
    found = []
    for rem in remote_items or []:
        corroboration = getattr(rem, "corroboration", None)
        if not corroboration:
            continue
        bucket = remote_payload_label_to_online_bucket(getattr(rem, "segment_type_label", "") or "")
        if not bucket:
            continue
        local = _local_candidate(local_items, bucket, rem.start_seconds)
        if local is None:
            continue
        if abs(local.start_seconds - rem.start_seconds) > tol or abs(local.end_seconds - rem.end_seconds) > tol:
            sources = [getattr(rem, "source", "")] + [c[0] for c in corroboration]
            found.append(SourceConflict(bucket, rem.segment_type_label, local, rem, sources))
    return found


# ------------------------------------------------------------------ choices
def _load_choices() -> dict:
    data = read_json(profile_path(CHOICES_FILE), {})
    return data if isinstance(data, dict) else {}


def get_choice(path, bucket):
    entry = _load_choices().get(str(path or ""))
    value = entry.get(bucket) if isinstance(entry, dict) else None
    return value if value in (CHOICE_LOCAL, CHOICE_ONLINE) else None


def save_choice(path, bucket, choice) -> bool:
    if not path or choice not in (CHOICE_LOCAL, CHOICE_ONLINE):
        return False
    data = _load_choices()
    entry = data.get(path) if isinstance(data.get(path), dict) else {}
    entry[bucket] = choice
    data.pop(path, None)
    data[path] = entry  # most recent last
    while len(data) > MAX_STORED_FILES:
        data.pop(next(iter(data)))
    return write_json(profile_path(CHOICES_FILE), data)


def apply_source_choices(path, parsed, local_list, remote_list):
    """Swap the winning source's segment for the user's pick, per conflicting segment."""
    if not parsed or not local_list or not remote_list:
        return parsed
    result = list(parsed)
    for conflict in find_source_conflicts(local_list, remote_list):
        choice = get_choice(path, conflict.bucket)
        if choice == CHOICE_ONLINE:
            old, new = conflict.local, conflict.online
        elif choice == CHOICE_LOCAL:
            old, new = conflict.online, conflict.local
        else:
            continue
        result = [new if seg is old else seg for seg in result]
    return result


# ------------------------------------------------------------------- prompt
def _log(msg):
    log_service_detail(msg, tag="source_conflict")


def maybe_prompt_source_conflict(video_path, playback_type, local_items, remote_items, segment_monitor):
    """Ask once per playback whether to review disagreeing sources."""
    addon = get_addon()
    if not source_conflict_enabled(addon) or not local_items or not remote_items:
        return
    if segment_monitor is not None and video_path and (
        getattr(segment_monitor, "source_conflict_suppressed_path", None) == video_path
    ):
        return
    conflicts = [c for c in find_source_conflicts(local_items, remote_items) if get_choice(video_path, c.bucket) is None]
    if not conflicts:
        return
    try:
        from service_local_to_online_sync import _playback_allows_sync_prompt

        if not _playback_allows_sync_prompt(segment_monitor):
            _log("Source conflict prompt skipped: playback/modal guard")
            return
    except Exception:
        pass
    if segment_monitor is not None and video_path:
        segment_monitor.source_conflict_suppressed_path = video_path
    try:
        from skip_source_picker_ui import review_source_conflicts

        review_source_conflicts(addon, video_path, conflicts, segment_monitor)
    except Exception as exc:
        log("⚠ Source conflict review failed: %s" % exc)
