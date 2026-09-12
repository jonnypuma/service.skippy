# -*- coding: utf-8 -*-
"""Negative cache for sidecar path existence probes (NFS-friendly)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional

from service_sidecar_paths import (
    sidecar_hits_from_directory_listing,
    vfs_file_exists,
    vfs_paths_match,
)
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


def _matching_probe_keys(cache: dict, video_path: str) -> list:
    return [key for key in cache if vfs_paths_match(key, video_path)]


def _probe_cache_get(cache: dict, video_path: str):
    hit = cache.get(video_path)
    if hit is not None:
        return hit
    for key in _matching_probe_keys(cache, video_path):
        return cache.get(key)
    return None


def _probe_cache_store(cache: dict, video_path: str, result) -> None:
    for key in _matching_probe_keys(cache, video_path):
        cache.pop(key, None)
    cache[video_path] = result


def _probe_cache_pop(cache: dict, video_path: str) -> None:
    for key in _matching_probe_keys(cache, video_path):
        cache.pop(key, None)


def clear_sidecar_probe_cache(segment_monitor=None, video_path: Optional[str] = None) -> None:
    """Drop cached probe results (one path or entire cache)."""
    if segment_monitor is None:
        return
    cache = getattr(segment_monitor, "sidecar_probe_cache", None)
    if not cache:
        segment_monitor.sidecar_probe_cache = {}
        return
    if video_path:
        _probe_cache_pop(cache, video_path)
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
        cached = _probe_cache_get(_probe_cache(segment_monitor), video_path)
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
        _probe_cache_store(_probe_cache(segment_monitor), video_path, result)

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


# RunScript (editor / marker) cannot see the service process's probe cache.
# They set a Home window property; the service consumes it on the next tick.
_PROBE_INVALIDATE_PROP = "skippy.sidecar_probe_invalidate.v1"


def request_sidecar_probe_invalidation(video_path=None) -> None:
    """Ask the playback service to drop its sidecar probe (and parse) cache."""
    try:
        import xbmcgui

        xbmcgui.Window(10000).setProperty(
            _PROBE_INVALIDATE_PROP, video_path or "*"
        )
    except Exception:
        pass


def _drop_playback_parse_cache(segment_monitor, video_path: Optional[str]) -> None:
    if segment_monitor is None:
        return
    cache = getattr(segment_monitor, "segment_parse_cache", None)
    if video_path and cache:
        cached_path = cache.get("path")
        if cached_path and not vfs_paths_match(cached_path, video_path):
            return
    segment_monitor.segment_parse_cache = None
    try:
        from playback_segment_cache import publish_parse_cache

        publish_parse_cache(None)
    except Exception:
        pass


def consume_sidecar_probe_invalidation(segment_monitor) -> bool:
    """Apply a pending editor/marker invalidation. True if a request was consumed."""
    try:
        import xbmcgui

        win = xbmcgui.Window(10000)
        raw = (win.getProperty(_PROBE_INVALIDATE_PROP) or "").strip()
        if not raw:
            return False
        win.clearProperty(_PROBE_INVALIDATE_PROP)
    except Exception:
        return False
    if raw == "*":
        clear_sidecar_probe_cache(segment_monitor)
        _drop_playback_parse_cache(segment_monitor, None)
        log("Sidecar probe cache cleared (editor/marker write, all paths)")
        return True
    clear_sidecar_probe_cache(segment_monitor, raw)
    _drop_playback_parse_cache(segment_monitor, raw)
    log("Sidecar probe cache cleared after editor/marker write for this file")
    return True
