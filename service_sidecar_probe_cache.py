# -*- coding: utf-8 -*-
"""Negative cache for sidecar path existence probes (NFS-friendly)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional

from service_sidecar_paths import sidecar_hits_from_directory_listing, vfs_file_exists
from settings_utils import log

# Hit cache matches sidecar mtime checks. Confirmed misses wait longer so NFS
# directory listings are not repeated every few seconds during playback.
PROBE_HIT_MAX_AGE_S = 5.0
PROBE_MISS_MAX_AGE_S = 60.0
PROBE_MAX_AGE_S = PROBE_HIT_MAX_AGE_S


@dataclass(frozen=True)
class SidecarProbeResult:
    """Cached sidecar probe for one video path."""

    chapter_path: Optional[str]
    edl_path: Optional[str]
    probed: bool
    chapter_path_count: int = 0
    edl_path_count: int = 0
    probed_at: float = 0.0


def _probe_cache(segment_monitor: Any) -> dict:
    cache = getattr(segment_monitor, "sidecar_probe_cache", None)
    if cache is None:
        cache = {}
        segment_monitor.sidecar_probe_cache = cache
    return cache


def clear_sidecar_probe_cache(segment_monitor=None, video_path: Optional[str] = None) -> None:
    """Drop cached probe results (one path or entire cache)."""
    if segment_monitor is None:
        return
    cache = getattr(segment_monitor, "sidecar_probe_cache", None)
    if not cache:
        segment_monitor.sidecar_probe_cache = {}
        return
    if video_path:
        cache.pop(video_path, None)
    else:
        cache.clear()


def _first_existing(listed_path, unknown_paths):
    if listed_path:
        return listed_path
    for path in unknown_paths or []:
        if vfs_file_exists(path):
            return path
    return None


def resolve_sidecar_paths(
    video_path: str,
    segment_monitor=None,
    *,
    force: bool = False,
    max_age_s: float | None = None,
) -> SidecarProbeResult:
    """
    Return first existing chapter XML and EDL paths, caching per video.

    Uses a directory listing when possible so missing NFS candidates are never opened.
    Hits re-list after ``PROBE_HIT_MAX_AGE_S`` (sidecar mtime cadence). Confirmed
    misses wait ``PROBE_MISS_MAX_AGE_S`` before listing again.
    """
    if not video_path:
        return SidecarProbeResult(None, None, probed=False)

    now = time.monotonic()
    if segment_monitor is not None and not force:
        cached = _probe_cache(segment_monitor).get(video_path)
        ttl = max_age_s
        if ttl is None and cached is not None and cached.probed:
            if cached.chapter_path or cached.edl_path:
                ttl = PROBE_HIT_MAX_AGE_S
            else:
                ttl = PROBE_MISS_MAX_AGE_S
        if ttl is None:
            ttl = PROBE_HIT_MAX_AGE_S
        if (
            cached is not None
            and cached.probed
            and (now - float(cached.probed_at or 0.0)) < float(ttl)
        ):
            return cached

    (
        listed_chapter,
        listed_edl,
        unknown_ch,
        unknown_edl,
        chapter_count,
        edl_count,
    ) = sidecar_hits_from_directory_listing(video_path)

    chapter_path = _first_existing(listed_chapter, unknown_ch)
    edl_path = _first_existing(listed_edl, unknown_edl)

    result = SidecarProbeResult(
        chapter_path=chapter_path,
        edl_path=edl_path,
        probed=True,
        chapter_path_count=chapter_count,
        edl_path_count=edl_count,
        probed_at=now,
    )

    if segment_monitor is not None:
        _probe_cache(segment_monitor)[video_path] = result

    if not chapter_path and not edl_path:
        log(
            "Sidecar probe: no local sidecar (%d chapter paths, %d EDL paths)"
            % (chapter_count, edl_count)
        )

    return result


def local_sidecar_exists(video_path: str, segment_monitor=None) -> bool:
    """True when a chapter XML or EDL sidecar exists (uses probe cache when monitor given)."""
    result = resolve_sidecar_paths(video_path, segment_monitor)
    return bool(result.chapter_path or result.edl_path)
