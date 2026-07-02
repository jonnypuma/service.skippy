# -*- coding: utf-8 -*-
"""Negative cache for sidecar path existence probes (NFS-friendly)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import xbmcvfs

from service_sidecar_paths import _chapter_xml_paths_to_try, _edl_paths_to_try
from settings_utils import log


@dataclass(frozen=True)
class SidecarProbeResult:
    """Cached sidecar probe for one video path."""

    chapter_path: Optional[str]
    edl_path: Optional[str]
    probed: bool
    chapter_path_count: int = 0
    edl_path_count: int = 0


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


def resolve_sidecar_paths(
    video_path: str,
    segment_monitor=None,
    *,
    force: bool = False,
) -> SidecarProbeResult:
    """
    Return first existing chapter XML and EDL paths, caching negatives per video.

    ``None`` for chapter_path/edl_path means probed and not found (negative cache).
    """
    if not video_path:
        return SidecarProbeResult(None, None, probed=False)

    if segment_monitor is not None and not force:
        cached = _probe_cache(segment_monitor).get(video_path)
        if cached is not None and cached.probed:
            return cached

    chapter_paths = _chapter_xml_paths_to_try(video_path)
    edl_paths = _edl_paths_to_try(video_path)

    chapter_path = None
    for path in chapter_paths:
        if not path:
            continue
        try:
            if xbmcvfs.exists(path):
                chapter_path = path
                break
        except Exception:
            continue

    edl_path = None
    for path in edl_paths:
        if not path:
            continue
        try:
            if xbmcvfs.exists(path):
                edl_path = path
                break
        except Exception:
            continue

    result = SidecarProbeResult(
        chapter_path=chapter_path,
        edl_path=edl_path,
        probed=True,
        chapter_path_count=len(chapter_paths),
        edl_path_count=len(edl_paths),
    )

    if segment_monitor is not None:
        _probe_cache(segment_monitor)[video_path] = result

    if not chapter_path and not edl_path:
        log(
            "Sidecar probe: no local sidecar (%d chapter paths, %d EDL paths)"
            % (len(chapter_paths), len(edl_paths))
        )

    return result


def local_sidecar_exists(video_path: str, segment_monitor=None) -> bool:
    """True when a chapter XML or EDL sidecar exists (uses probe cache when monitor given)."""
    result = resolve_sidecar_paths(video_path, segment_monitor)
    return bool(result.chapter_path or result.edl_path)
