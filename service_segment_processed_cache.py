# -*- coding: utf-8 -*-
"""Cache for Pass 1/2 segment processing (linking) across monitor loop ticks."""

from __future__ import annotations

import copy
from typing import Any, Optional

from settings_utils import addon_get_bool, get_addon


def _is_nested_segment(segment_a, segment_b):
    return (
        segment_b.start_seconds >= segment_a.start_seconds
        and segment_b.end_seconds <= segment_a.end_seconds
    )


def clear_segment_processed_cache(segment_monitor) -> None:
    if segment_monitor is None:
        return
    segment_monitor.segment_processed_cache = None


def source_segment_fingerprint(segments) -> tuple:
    return tuple(
        (
            round(s.start_seconds, 3),
            round(s.end_seconds, 3),
            s.segment_type_label,
            getattr(s, "source", ""),
        )
        for s in sorted(segments or [], key=lambda x: x.start_seconds)
    )


def processed_settings_signature(addon, playback_type, source_settings_sig) -> tuple:
    if not addon:
        return (source_settings_sig, True)
    skip_overlaps = addon_get_bool(addon, "skip_overlapping_segments", True)
    return (source_settings_sig, skip_overlaps)


def compute_link_boundaries(filtered_segments) -> tuple:
    boundaries = []
    for i in range(len(filtered_segments)):
        parent = filtered_segments[i]
        for j in range(i + 1, len(filtered_segments)):
            child = filtered_segments[j]
            if child.start_seconds >= parent.end_seconds:
                break
            if _is_nested_segment(parent, child):
                boundaries.append(float(child.start_seconds))
    return tuple(sorted(set(boundaries)))


def compute_link_phase(current_time: Optional[float], boundaries: tuple) -> int:
    if current_time is None or not boundaries:
        return 0
    phase = 0
    for boundary in boundaries:
        if current_time >= boundary:
            phase += 1
        else:
            break
    return phase


def _clone_processed_segments(segments):
    return [copy.copy(seg) for seg in (segments or [])]


def _cache_key(
    path,
    playback_type,
    proc_settings_sig,
    sidecar_signature,
    source_fingerprint,
):
    return (
        path,
        playback_type,
        proc_settings_sig,
        sidecar_signature,
        source_fingerprint,
    )


def try_get_processed_cache(
    segment_monitor,
    path,
    playback_type,
    source_segments,
    current_time,
    *,
    source_settings_sig,
    sidecar_signature,
    clone_pass1_fn,
    log_if_changed,
):
    """
    Return processed segments from cache when valid.

    Returns (segments_or_none, cache_status) where cache_status is
    'hit', 'phase_reeval', or 'miss'.
    """
    cache = getattr(segment_monitor, "segment_processed_cache", None)
    if not cache or not source_segments:
        return None, "miss"

    fingerprint = source_segment_fingerprint(source_segments)
    addon = get_addon()
    proc_sig = processed_settings_signature(addon, playback_type, source_settings_sig)
    key = _cache_key(path, playback_type, proc_sig, sidecar_signature, fingerprint)

    if cache.get("key") != key:
        return None, "miss"

    boundaries = cache.get("link_boundaries") or ()
    phase = compute_link_phase(current_time, boundaries)
    cached_phase = cache.get("link_phase", 0)

    if phase == cached_phase:
        log_if_changed(
            "segment_process_cache",
            "♻ Using cached processed segments (phase=%d, count=%d)"
            % (phase, len(cache.get("processed_segments") or [])),
        )
        return _clone_processed_segments(cache.get("processed_segments") or []), "hit"

    pass1 = clone_pass1_fn(cache.get("pass1_segments") or [])
    from service_segment_processing import re_evaluate_segment_jump_points

    re_evaluate_segment_jump_points(pass1, current_time)
    cache["processed_segments"] = _clone_processed_segments(pass1)
    cache["link_phase"] = phase
    log_if_changed(
        "segment_process_phase",
        "♻ Re-evaluated processed segments for link phase %d → %d"
        % (cached_phase, phase),
    )
    return _clone_processed_segments(pass1), "phase_reeval"


def store_segment_processed_cache(
    segment_monitor,
    path,
    playback_type,
    source_segments,
    pass1_segments,
    processed_segments,
    current_time,
    *,
    source_settings_sig,
    sidecar_signature,
    nested_parent_map=None,
):
    addon = get_addon()
    proc_sig = processed_settings_signature(addon, playback_type, source_settings_sig)
    fingerprint = source_segment_fingerprint(source_segments)
    boundaries = compute_link_boundaries(pass1_segments)
    phase = compute_link_phase(current_time, boundaries)
    segment_monitor.segment_processed_cache = {
        "key": _cache_key(path, playback_type, proc_sig, sidecar_signature, fingerprint),
        "pass1_segments": _clone_processed_segments(pass1_segments),
        "processed_segments": _clone_processed_segments(processed_segments),
        "link_boundaries": boundaries,
        "link_phase": phase,
        "nested_parent_map": dict(nested_parent_map or {}),
    }
