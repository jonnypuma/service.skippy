# -*- coding: utf-8 -*-
"""TheIntroDB / IntroDB.app fetch, merge, and playback cache."""

import json
import os
import re
import time

import xbmcaddon
from contextlib import closing
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import xbmc
import xbmcvfs

from settings_utils import (
    addon_get_bool,
    addon_get_setting_text,
    get_addon,
    log_remote,
    log_service_detail,
    parse_kodi_jsonrpc_raw,
)

from segment_item import SegmentItem
from skippy_stats import record_online_segments_downloaded
from remote_http import (
    ADDON_ID,
    INTRODB_SEGMENTS_URL,
    ONLINE_MERGE_INTRODB_FIRST,
    ONLINE_MERGE_THEINTRODB_FIRST,
    REMOTE_SEGMENT_PAYLOAD_KEYS,
    THEINTRODB_BASE_URL,
    _rlog,
    _safe_log_url,
    fetch_remote_json,
)
from remote_library import (
    build_movie_context,
    build_tv_episode_context,
    get_enriched_playing_item,
    playback_duration_seconds_for_upload,
    _get_playing_file_path,
)
def build_tv_cache_key(context):
    return (
        context.get("type"),
        context.get("tmdb_id"),
        context.get("imdb_id"),
        context.get("show_imdb_id"),
        context.get("season"),
        context.get("episode"),
    )


def normalize_skip_window(start_value, end_value, total_time, allow_zero_start=False):
    try:
        end_seconds = float(end_value)
    except (TypeError, ValueError):
        return None
    try:
        if start_value is None:
            start_seconds = 0.0 if allow_zero_start else 1.0
        else:
            start_seconds = float(start_value)
    except (TypeError, ValueError):
        start_seconds = 0.0 if allow_zero_start else 1.0
    if allow_zero_start:
        start_seconds = max(0.0, start_seconds)
    else:
        start_seconds = max(1.0, start_seconds)
    try:
        tt = float(total_time)
    except (TypeError, ValueError):
        tt = 0.0
    end_seconds = min(tt, end_seconds) if tt > 0 else end_seconds
    if end_seconds <= start_seconds:
        return None
    return start_seconds, end_seconds


def normalize_remote_segment_window(segment, total_time):
    if not isinstance(segment, dict):
        return None
    start_ms = segment.get("start_ms")
    end_ms = segment.get("end_ms")
    if end_ms is not None:
        try:
            return normalize_skip_window(
                None if start_ms is None else (float(start_ms) / 1000.0),
                float(end_ms) / 1000.0,
                total_time,
            )
        except (TypeError, ValueError):
            return None
    return normalize_skip_window(
        segment.get("start_sec"),
        segment.get("end_sec"),
        total_time,
    )


def _theintrodb_normalize_segment_field(raw):
    """
    TheIntroDB GET ``/v3/media`` returns each segment type as an **array** of
    objects (multiple windows per type possible). Legacy v1 used a single
    object per type; empty types were ``null`` in v1 and are **omitted** in v2/v3.
    """
    if raw is None:
        return []
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if isinstance(raw, dict):
        return [raw]
    return []


def _theintrodb_segment_entries(payload, total_time):
    out = []
    if not isinstance(payload, dict):
        return out
    tt_hint = None
    if total_time is not None:
        try:
            tt_hint = float(total_time)
        except (TypeError, ValueError):
            tt_hint = None
    for segment_name in REMOTE_SEGMENT_PAYLOAD_KEYS:
        entries = _theintrodb_normalize_segment_field(payload.get(segment_name))
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            end_ms_raw = entry.get("end_ms")
            if end_ms_raw is None:
                # v3: credits/preview may omit end (= through end of media)
                if segment_name not in ("credits", "preview"):
                    continue
                if tt_hint is None or tt_hint <= 0:
                    continue
                end_seconds = tt_hint
            else:
                try:
                    end_seconds = float(end_ms_raw) / 1000.0
                except (TypeError, ValueError):
                    continue
            start_ms_raw = entry.get("start_ms")
            if start_ms_raw is None:
                start_seconds = 0.0
            else:
                try:
                    start_seconds = float(start_ms_raw) / 1000.0
                except (TypeError, ValueError):
                    continue
            if start_seconds >= end_seconds:
                continue
            window = normalize_skip_window(
                start_seconds,
                end_seconds,
                total_time,
                allow_zero_start=True,
            )
            if window:
                out.append(
                    SegmentItem(
                        window[0],
                        window[1],
                        segment_name,
                        source="theintrodb",
                    )
                )
    return out


def _theintrodb_lookup_api_key():
    addon = get_addon()
    if not addon:
        return None
    key = (addon_get_setting_text(addon, "online_upload_theintrodb_api_key", "") or "").strip()
    return key or None


def fetch_theintrodb_segments(context, total_time):
    query = {}
    tmdb_id = context.get("tmdb_id")
    imdb_id = context.get("imdb_id")
    if (context.get("type") or "").lower() == "movie":
        if tmdb_id is not None:
            query["tmdb_id"] = tmdb_id
        elif imdb_id:
            query["imdb_id"] = imdb_id
        else:
            _rlog("TheIntroDB movie: need tmdb_id or imdb_id in context")
            return []
    else:
        season = context.get("season")
        episode = context.get("episode")
        if season is None or episode is None:
            _rlog("TheIntroDB TV: need season and episode in context")
            return []
        query["season"] = season
        query["episode"] = episode
        if tmdb_id is not None:
            query["tmdb_id"] = tmdb_id
        elif imdb_id:
            query["imdb_id"] = imdb_id
        else:
            _rlog(
                "TheIntroDB skipped: need tmdb_id or episode imdb_id in context "
                "(show_imdb alone is not enough for this API)"
            )
            return []

    if total_time is not None:
        try:
            tt = float(total_time)
            if tt > 0:
                query["duration_ms"] = int(round(tt * 1000.0))
        except (TypeError, ValueError):
            pass

    extra_headers = {}
    api_key = _theintrodb_lookup_api_key()
    if api_key:
        extra_headers["Authorization"] = "Bearer %s" % api_key

    payload = fetch_remote_json(
        "%s?%s" % (THEINTRODB_BASE_URL, urlencode(query)),
        "TheIntroDB",
        extra_headers=extra_headers or None,
    )
    if not payload:
        _rlog("TheIntroDB: no JSON payload (HTTP error, timeout, or empty body — see messages above)")
        return []
    segs = _theintrodb_segment_entries(payload, total_time)
    if segs:
        _rlog("TheIntroDB: using %d segment(s) %s" % (len(segs), [(s.segment_type_label, s.start_seconds, s.end_seconds) for s in segs]))
    else:
        keys = list(payload.keys()) if isinstance(payload, dict) else type(payload).__name__
        _rlog(
            "TheIntroDB: response OK but no usable segment windows after normalization (keys=%s)"
            % keys
        )
    return segs


def fetch_introdb_segments(context, total_time):
    imdb_id = context.get("show_imdb_id")
    if not imdb_id:
        _rlog("IntroDB.app lookup skipped: no show IMDb id")
        return []

    payload = fetch_remote_json(
        "%s?%s"
        % (
            INTRODB_SEGMENTS_URL,
            urlencode(
                {
                    "imdb_id": imdb_id,
                    "season": context.get("season"),
                    "episode": context.get("episode"),
                }
            ),
        ),
        "IntroDB.app",
    )
    if not isinstance(payload, dict):
        _rlog("IntroDB.app: response was not a JSON object (got %s)" % type(payload).__name__)
        return []

    out = []
    for segment_name in REMOTE_SEGMENT_PAYLOAD_KEYS:
        val = payload.get(segment_name)
        if val is None:
            continue
        if isinstance(val, list):
            for entry in val:
                if not isinstance(entry, dict):
                    continue
                window = normalize_remote_segment_window(entry, total_time)
                if window:
                    out.append(
                        SegmentItem(
                            window[0],
                            window[1],
                            segment_name,
                            source="introdb",
                        )
                    )
        else:
            window = normalize_remote_segment_window(val, total_time)
            if window:
                out.append(
                    SegmentItem(
                        window[0],
                        window[1],
                        segment_name,
                        source="introdb",
                    )
                )
    if out:
        _rlog("IntroDB.app: using %d segment(s) %s" % (len(out), [(s.segment_type_label, s.start_seconds, s.end_seconds) for s in out]))
    else:
        _rlog(
            "IntroDB.app: no segment windows (payload keys=%s)"
            % (list(payload.keys()),)
        )
    return out


def _segments_overlap(a, b, tol=1.5):
    return not (
        a.end_seconds + tol <= b.start_seconds
        or b.end_seconds + tol <= a.start_seconds
    )


def merge_remote_segments(primary_segs, secondary_segs):
    """Primary wins when both sources cover the same time window; secondary adds non-overlapping only."""
    out = list(primary_segs)
    for b in secondary_segs:
        if not any(_segments_overlap(b, a) for a in out):
            out.append(b)
    return sorted(out, key=lambda s: s.start_seconds)


def _online_merge_introdb_primary(playback_kind):
    """
    playback_kind: 'tv' or 'movie' — which setting key to read.
    Returns True if IntroDB.app should win overlapping windows vs TheIntroDB.
    """
    addon = get_addon()
    key = (
        "tv_online_merge_priority"
        if playback_kind == "tv"
        else "movie_online_merge_priority"
    )
    raw = (
        addon_get_setting_text(addon, key, ONLINE_MERGE_THEINTRODB_FIRST)
        if addon
        else ONLINE_MERGE_THEINTRODB_FIRST
    )
    return (raw or "").strip() == ONLINE_MERGE_INTRODB_FIRST


def fetch_remote_movie_segments(total_time, cache, snapshot=None):
    """
    Fetch intro/recap SegmentItems for the current movie (TheIntroDB only). Uses cache dict.
    """
    item = get_enriched_playing_item(snapshot=snapshot)
    if not item or (item.get("type") or "").lower() != "movie":
        _rlog("Remote movie segments: not a library movie item")
        return []

    context = build_movie_context(item)
    if not context:
        return []

    key = ("movie", context.get("tmdb_id"), context.get("imdb_id"))
    if key in cache:
        _rlog("cache hit movie key=%s -> %d segment(s)" % (key, len(cache[key])))
        return list(cache[key])

    try:
        tt = float(total_time)
    except (TypeError, ValueError):
        tt = 0.0
    if tt < 1.0:
        _rlog("Remote movie segments skipped: total time not available yet")
        return []

    the_segs = fetch_theintrodb_segments(context, tt)
    intro_segs = fetch_introdb_segments(context, tt)
    if _online_merge_introdb_primary("movie"):
        merged = merge_remote_segments(intro_segs, the_segs)
        _rlog(
            "Remote movie segments: merge order IntroDB.app primary (TheIntroDB=%d, IntroDB=%d pre-merge)"
            % (len(the_segs), len(intro_segs))
        )
    else:
        merged = merge_remote_segments(the_segs, intro_segs)
        _rlog(
            "Remote movie segments: merge order TheIntroDB primary (TheIntroDB=%d, IntroDB=%d pre-merge)"
            % (len(the_segs), len(intro_segs))
        )
    cache[key] = merged
    if merged:
        _rlog("TheIntroDB/IntroDB merge (movie): using %d segment(s)" % len(merged))
        record_online_segments_downloaded(len(merged))
    else:
        _rlog("TheIntroDB/IntroDB merge (movie): empty")
    return list(merged)


def fetch_remote_tv_segments_core(item, total_time, cache):
    """
    Fetch intro/recap SegmentItems for TV ``item`` (library episode dict).
    Uses ``cache`` (typically ``remote_segment_cache`` or a fresh ``{}`` for prefetch-only fetches).
    """
    if not item or (item.get("type") or "").lower() != "episode":
        _rlog("Remote TV segments core: not an episode item")
        return []

    context = build_tv_episode_context(item)
    if not context:
        return []

    key = build_tv_cache_key(context)
    if key in cache:
        _rlog("cache hit for key=%s -> %d segment(s)" % (key, len(cache[key])))
        return list(cache[key])

    try:
        tt = float(total_time)
    except (TypeError, ValueError):
        tt = 0.0
    if tt < 1.0:
        _rlog("Remote TV segments skipped: total time not available yet")
        return []

    the_segs = fetch_theintrodb_segments(context, tt)
    intro_segs = fetch_introdb_segments(context, tt)
    if _online_merge_introdb_primary("tv"):
        merged = merge_remote_segments(intro_segs, the_segs)
        _rlog(
            "merged remote (TV): IntroDB.app wins overlaps — %d segment(s) total "
            "(TheIntroDB=%d, IntroDB.app=%d pre-merge)"
            % (len(merged), len(the_segs), len(intro_segs))
        )
    else:
        merged = merge_remote_segments(the_segs, intro_segs)
        _rlog(
            "merged remote (TV): TheIntroDB wins overlaps — %d segment(s) total "
            "(TheIntroDB=%d, IntroDB.app=%d pre-merge)"
            % (len(merged), len(the_segs), len(intro_segs))
        )
    cache[key] = merged
    if merged:
        record_online_segments_downloaded(len(merged))
    else:
        _rlog(
            "merged remote (TV): empty (TheIntroDB=%d, IntroDB.app=%d segments before merge)"
            % (len(the_segs), len(intro_segs))
        )
    return list(merged)


def _try_tv_prefetch_handoff(item, cache):
    """Apply successor prefetch when playing file and cache key match; discard prefetch otherwise."""
    from prefetch_segment_cache import (
        consume_tv_prefetch_entry,
        peek_tv_prefetch_for_playing_path,
    )

    playing_path = item.get("file") or _get_playing_file_path()
    if not playing_path:
        return None
    entry = peek_tv_prefetch_for_playing_path(playing_path)
    if not entry:
        return None

    context = build_tv_episode_context(item)
    key = build_tv_cache_key(context) if context else None
    segs = entry.get("segments") or []
    exp_key = entry.get("cache_key")
    tags = sorted({getattr(s, "source", "?") for s in segs})

    if key and exp_key == key and segs:
        consume_tv_prefetch_entry()
        cache[key] = list(segs)
        _rlog(
            "TV prefetch handoff: %d segment(s) for %s key=%s sources=%s"
            % (len(segs), os.path.basename(str(playing_path)), key, tags)
        )
        log_service_detail(
            "prefetch handoff OK: segments=%d key=%s sources=%s path=%r"
            % (len(segs), key, ",".join(tags), playing_path),
            tag="prefetch",
        )
        return list(segs)

    consume_tv_prefetch_entry()
    _rlog(
        "TV prefetch handoff rejected (mismatch or empty): expected_key=%s got_key=%s segs=%d"
        % (exp_key, key, len(segs))
    )
    log_service_detail(
        "prefetch handoff REJECTED: expected_key=%s got_key=%s segcount=%d path=%r"
        % (exp_key, key, len(segs), playing_path),
        tag="prefetch",
    )
    return None


def fetch_remote_tv_segments(total_time, cache, snapshot=None):
    """
    Fetch intro/recap SegmentItems for the current TV episode. Uses cache dict keyed by episode ids.
    Applies **prefetch** handoff when the playing file matches a stored successor fetch.
    """
    item = get_enriched_playing_item(snapshot=snapshot)
    if not item:
        _rlog("Remote TV segments: no enriched playing item")
        return []

    handoff = _try_tv_prefetch_handoff(item, cache)
    if handoff is not None:
        return handoff

    return fetch_remote_tv_segments_core(item, total_time, cache)
