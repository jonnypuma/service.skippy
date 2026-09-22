# -*- coding: utf-8 -*-
"""Skippy usage statistics: skips, time saved, and online segment traffic.

Counters live in ``addon_data/service.skippy/statistics.json`` and are updated from
both the playback loop and background prefetch/upload threads, so every mutation goes
through one lock and a write-through cache.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone

from settings_utils import log_service_detail, normalize_label
from skippy_profile_store import profile_path, read_json, write_json

STATS_FILENAME = "statistics.json"
SCHEMA = "skippy_statistics_v1"

_lock = threading.RLock()
_cache: dict | None = None


def _log(msg: str) -> None:
    log_service_detail(msg, tag="stats")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _empty_stats() -> dict:
    return {
        "schema": SCHEMA,
        "since_utc": _utc_now(),
        "skips": {"total": 0, "seconds_saved": 0.0, "by_type": {}},
        "online": {"segments_downloaded": 0, "segments_uploaded": 0},
    }


def _as_int(value, default=0) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def _as_float(value, default=0.0) -> float:
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return default


def _stats_type_key(label) -> str:
    """Canonical type id when the label is a known alias, else the normalized text."""
    norm = normalize_label(label)
    if not norm:
        return ""
    try:
        from segment_types import canonical_type_id

        return canonical_type_id(label) or norm
    except Exception:
        return norm


def _fold_by_type(raw) -> dict:
    """Sum counts that are aliases of the same type (behind the scenes + behind_the_scenes)."""
    folded = {}
    if not isinstance(raw, dict):
        return folded
    for label, count in raw.items():
        key = _stats_type_key(label)
        if not key:
            continue
        folded[key] = folded.get(key, 0) + _as_int(count)
    return folded


def _normalized(data) -> dict:
    stats = _empty_stats()
    if not isinstance(data, dict):
        return stats
    if isinstance(data.get("since_utc"), str) and data["since_utc"].strip():
        stats["since_utc"] = data["since_utc"].strip()
    skips = data.get("skips")
    if isinstance(skips, dict):
        stats["skips"]["total"] = _as_int(skips.get("total"))
        stats["skips"]["seconds_saved"] = _as_float(skips.get("seconds_saved"))
        by_type = skips.get("by_type")
        if isinstance(by_type, dict):
            stats["skips"]["by_type"] = _fold_by_type(by_type)
    online = data.get("online")
    if isinstance(online, dict):
        stats["online"]["segments_downloaded"] = _as_int(
            online.get("segments_downloaded")
        )
        stats["online"]["segments_uploaded"] = _as_int(online.get("segments_uploaded"))
    return stats


def _stats_path() -> str | None:
    return profile_path(STATS_FILENAME)


def load_statistics() -> dict:
    """Current counters (normalized); reads from disk once, then from cache."""
    global _cache
    with _lock:
        if _cache is None:
            raw = read_json(_stats_path(), default=None)
            _cache = _normalized(raw)
            raw_skips = raw.get("skips") if isinstance(raw, dict) else None
            raw_by = (
                raw_skips.get("by_type")
                if isinstance(raw_skips, dict)
                else None
            )
            if isinstance(raw_by, dict) and raw_by != _cache["skips"]["by_type"]:
                _flush()
        return {
            "schema": _cache["schema"],
            "since_utc": _cache["since_utc"],
            "skips": {
                "total": _cache["skips"]["total"],
                "seconds_saved": _cache["skips"]["seconds_saved"],
                "by_type": dict(_cache["skips"]["by_type"]),
            },
            "online": dict(_cache["online"]),
        }


def _flush() -> None:
    if _cache is None:
        return
    if not write_json(_stats_path(), _cache):
        _log("could not write statistics file")


def record_skip(segment_label, seconds_saved=0.0) -> None:
    """Count one skip and the playback time it saved."""
    try:
        from segment_types import canonical_type_id

        label = canonical_type_id(segment_label) or "segment"
    except Exception:
        label = normalize_label(segment_label) or "segment"
    with _lock:
        load_statistics()
        _cache["skips"]["total"] += 1
        _cache["skips"]["seconds_saved"] = round(
            _cache["skips"]["seconds_saved"] + _as_float(seconds_saved), 3
        )
        by_type = _cache["skips"]["by_type"]
        by_type[label] = by_type.get(label, 0) + 1
        _flush()


def record_online_segments_downloaded(count) -> None:
    """Count segments received from a fresh online lookup (cache hits excluded)."""
    added = _as_int(count)
    if added <= 0:
        return
    with _lock:
        load_statistics()
        _cache["online"]["segments_downloaded"] += added
        _flush()


def record_online_segment_uploaded(count=1) -> None:
    """Count segments accepted by an online database."""
    added = _as_int(count)
    if added <= 0:
        return
    with _lock:
        load_statistics()
        _cache["online"]["segments_uploaded"] += added
        _flush()


def merge_statistics_from_backup(incoming) -> bool:
    """
    Merge backup counters into local statistics.

    Uses the larger value for each counter (idempotent on re-restore of the same
    backup) and keeps the earlier ``since_utc`` when both are present.
    Returns True when anything changed.
    """
    incoming_stats = _normalized(incoming)
    with _lock:
        load_statistics()
        changed = False

        local_since = _cache.get("since_utc") or ""
        incoming_since = incoming_stats.get("since_utc") or ""
        if incoming_since and (
            not local_since or incoming_since < local_since
        ):
            _cache["since_utc"] = incoming_since
            changed = True

        local_skips = _cache["skips"]
        incoming_skips = incoming_stats["skips"]
        by_type = local_skips["by_type"]
        for label, count in (incoming_skips.get("by_type") or {}).items():
            if count > by_type.get(label, 0):
                by_type[label] = count
                changed = True
        type_total = sum(by_type.values())
        best_total = max(local_skips["total"], incoming_skips["total"], type_total)
        if best_total != local_skips["total"]:
            local_skips["total"] = best_total
            changed = True
        if incoming_skips["seconds_saved"] > local_skips["seconds_saved"]:
            local_skips["seconds_saved"] = incoming_skips["seconds_saved"]
            changed = True

        local_online = _cache["online"]
        incoming_online = incoming_stats["online"]
        for field in ("segments_downloaded", "segments_uploaded"):
            if incoming_online.get(field, 0) > local_online.get(field, 0):
                local_online[field] = incoming_online[field]
                changed = True

        if changed:
            _flush()
        return changed


def reset_statistics() -> None:
    global _cache
    with _lock:
        _cache = _empty_stats()
        _flush()


def clear_cache() -> None:
    global _cache
    with _lock:
        _cache = None
