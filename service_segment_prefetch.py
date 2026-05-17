# -*- coding: utf-8 -*-
"""Schedule library-based prefetch of **online-only** segments for the next TV episode."""

import os

from prefetch_segment_cache import clear_prefetch_segment_cache, set_tv_segment_prefetch
from remote_segments import (
    build_tv_cache_key,
    build_tv_episode_context,
    fetch_remote_tv_segments_core,
    get_enriched_item_for_path,
    resolve_tv_library_successor_episode_item,
    episode_runtime_seconds_for_prefetch,
)
from service_online_policy import _normalize_segment_source_priority
from settings_utils import (
    addon_get_bool,
    addon_get_setting_text,
    get_addon,
    log,
    log_service_detail,
)


def _prefetch_log_detail(msg):
    log_service_detail(msg, tag="prefetch")


def _segment_sources_summary(segments):
    if not segments:
        return "none"
    tags = sorted({getattr(s, "source", "?") for s in segments})
    return ",".join(tags)


def schedule_tv_successor_prefetch(segment_monitor, path, playback_type):
    """
    When TV **Online first** and **Prefetch next episode** is on, fetch merged online
    segments for the library successor and store them for handoff on next playback.
    """
    addon = get_addon()
    if not addon:
        return

    if not addon_get_bool(addon, "tv_prefetch_next_episode", True):
        clear_prefetch_segment_cache()
        segment_monitor.prefetch_tv_scheduled_path = None
        _prefetch_log_detail("prefetch: disabled in settings — cleared store")
        return

    if playback_type != "episode":
        clear_prefetch_segment_cache()
        segment_monitor.prefetch_tv_scheduled_path = None
        _prefetch_log_detail(
            "prefetch: not a TV episode — cleared store (playback_type=%r)"
            % (playback_type,)
        )
        return

    if not addon_get_bool(addon, "tv_use_online_segment_lookup", False):
        clear_prefetch_segment_cache()
        segment_monitor.prefetch_tv_scheduled_path = None
        _prefetch_log_detail("prefetch: TV online lookup off — cleared store")
        return

    priority_raw = addon_get_setting_text(
        addon, "tv_segment_source_priority", "LocalFirst"
    ) or "LocalFirst"
    priority = _normalize_segment_source_priority(priority_raw)
    if priority != "OnlineFirst":
        clear_prefetch_segment_cache()
        segment_monitor.prefetch_tv_scheduled_path = None
        _prefetch_log_detail(
            "prefetch: segment priority is %s (not Online first) — cleared store"
            % priority_raw
        )
        return

    if segment_monitor.prefetch_tv_scheduled_path == path:
        return

    segment_monitor.prefetch_tv_scheduled_path = path

    item = get_enriched_item_for_path(path)
    if not item or (item.get("type") or "").lower() != "episode":
        clear_prefetch_segment_cache()
        _prefetch_log_detail(
            "prefetch: no library episode row for current file — cleared store"
        )
        return

    successor = resolve_tv_library_successor_episode_item(item)
    if not successor:
        clear_prefetch_segment_cache()
        _prefetch_log_detail(
            "prefetch: no library successor after S%s E%s — cleared store"
            % (item.get("season"), item.get("episode"))
        )
        return

    ep_id = successor.get("id")
    try:
        ep_id = int(ep_id)
    except (TypeError, ValueError):
        ep_id = None
    tt = episode_runtime_seconds_for_prefetch(ep_id) if ep_id else 0.0
    if tt < 1.0:
        clear_prefetch_segment_cache()
        _prefetch_log_detail(
            "prefetch: successor episodeid=%s runtime=%s unavailable — cleared store"
            % (ep_id, tt)
        )
        return

    succ_path = successor.get("file") or ""
    succ_ctx = build_tv_episode_context(successor)
    succ_key = build_tv_cache_key(succ_ctx) if succ_ctx else None
    _prefetch_log_detail(
        "prefetch: fetching successor S%sE%s → %s key=%s runtime=%.1fs"
        % (
            successor.get("season"),
            successor.get("episode"),
            os.path.basename(str(succ_path)),
            succ_key,
            tt,
        )
    )

    segs = fetch_remote_tv_segments_core(successor, tt, {})
    if not segs:
        clear_prefetch_segment_cache()
        log(
            "TV prefetch: successor S%sE%s has no online segments — nothing stored"
            % (successor.get("season"), successor.get("episode"))
        )
        _prefetch_log_detail("prefetch: API merge returned 0 segments — cleared store")
        return

    if not succ_ctx or not succ_key:
        clear_prefetch_segment_cache()
        _prefetch_log_detail("prefetch: could not build TV context/key for successor")
        return

    set_tv_segment_prefetch(succ_path, segs, succ_key)
    log(
        "TV prefetch: stored %d online segment(s) for next episode S%sE%s (%s)"
        % (
            len(segs),
            successor.get("season"),
            successor.get("episode"),
            os.path.basename(str(succ_path)),
        )
    )
    _prefetch_log_detail(
        "prefetch: stored segments sources=[%s] cache_key=%s target_path=%r"
        % (_segment_sources_summary(segs), succ_key, succ_path)
    )
