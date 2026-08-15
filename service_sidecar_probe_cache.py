# -*- coding: utf-8 -*-
"""Negative cache for sidecar path existence probes (NFS-friendly)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional

from service_sidecar_paths import sidecar_hits_from_directory_listing, vfs_file_exists
from settings_utils import log

# Re-list at the same cadence as sidecar mtime checks so a newly added file is found.
PROBE_MAX_AGE_S = 5.0


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
    max_age_s: float = PROBE_MAX_AGE_S,
) -> SidecarProbeResult:
    """
    Return first existing chapter XML and EDL paths, caching per video.

    Uses a directory listing when possible so missing NFS candidates are never opened.
    Cached negatives are re-listed after ``max_age_s`` so a sidecar added mid-playback
    is still discovered.
    """
    if not video_path:
        return SidecarProbeResult(None, None, probed=False)

    now = time.monotonic()
    if segment_monitor is not None and not force:
        cached = _probe_cache(segment_monitor).get(video_path)
        if (
            cached is not None
            and cached.probed
            and (now - float(cached.probed_at or 0.0)) < max_age_s
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
