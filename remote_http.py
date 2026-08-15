# -*- coding: utf-8 -*-
"""HTTP helpers for remote segment lookup (JSON-RPC, fetch, cooldowns)."""

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
ADDON_ID = "service.skippy"

# Settings tv_online_merge_priority / movie_online_merge_priority — UI labels them
# "online API priority"; ids use "merge" because the code merges two API responses and
# this chooses which source wins when both define the same time window.
ONLINE_MERGE_THEINTRODB_FIRST = "TheIntroDBFirst"
ONLINE_MERGE_INTRODB_FIRST = "IntroDBFirst"

# Keys TheIntroDB / IntroDB may expose (see API docs). Order is display/priority preference.
REMOTE_SEGMENT_PAYLOAD_KEYS = (
    "intro",
    "recap",
    "credits",
    "preview",
    "outro",
    "commercial",
)


def _rlog(msg):
    """Verbose Normal/All only; tag [service.skippy - remote] for kodi.log filtering."""
    log_remote(msg)


THEINTRODB_BASE_URL = "https://api.theintrodb.org/v3/media"
INTRODB_SEGMENTS_URL = "https://api.introdb.app/segments"
TMDB_API3_BASE = "https://api.themoviedb.org/3"
TMDB_HELPER_ADDON_ID = "plugin.video.themoviedb.helper"
REMOTE_LOOKUP_TIMEOUT = 5

# Monotonic deadline per API bucket after a transport/server failure (see fetch_remote_json).
_REMOTE_FETCH_COOL_UNTIL = {}
# Consecutive qualifying failures per bucket (reset on success). Drives exponential backoff.
_REMOTE_FETCH_FAILURE_STREAK = {}

_SXXEXX = re.compile(r"[Ss](\d{1,2})[Ee](\d{1,2})")

_REMOTE_BACKOFF_CAP_SECONDS = 3600
_REMOTE_BACKOFF_EXPONENT_CAP = 12

# Kodi VideoLibrary.GetEpisodeDetails: only valid Video.Fields.Episode names for this API.
# Do **not** request `imdbnumber` — not in the Episode enum (error at index 3).
# Use **`showtitle`** for the TV show name on episodes — some builds reject **`tvshowtitle`**
# (error at index 6 / Item.Fields.Base). IMDb/TMDB come from `uniqueid`.
_EPISODE_JSONRPC_FIELDS = [
    "season",
    "episode",
    "uniqueid",
    "tvshowid",
    "title",
    "file",
    "showtitle",
]

# Fallback if a skin/CoreELEC build rejects one of the above (see _fetch_episode_details).
_EPISODE_JSONRPC_FIELDS_MINIMAL = [
    "season",
    "episode",
    "uniqueid",
    "tvshowid",
    "title",
    "file",
]

# VideoLibrary.GetEpisodes (path filter) — same Episode fields as minimal + show title.
_GET_EPISODES_PROPERTIES = [
    "season",
    "episode",
    "uniqueid",
    "tvshowid",
    "title",
    "file",
    "showtitle",
]

# Player.GetItem: match SettingsUtils / other working paths — extra fields (type, id, season,
# label) have been seen to return {} on some CoreELEC/Kodi builds.
_PLAYER_GETITEM_FIELDS = ["file", "title", "showtitle", "episode"]


def jsonrpc(method, params=None, log_errors=True):
    payload = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        payload["params"] = params
    try:
        raw = xbmc.executeJSONRPC(json.dumps(payload))
    except (TypeError, ValueError, AttributeError) as exc:
        _rlog("JSON-RPC execute failed for %s: %s" % (method, exc))
        return {}
    data, err = parse_kodi_jsonrpc_raw(raw)
    if err:
        _rlog("JSON-RPC parse failed for %s: %s" % (method, err))
        return {}
    if data.get("error") and log_errors:
        _rlog("JSON-RPC error for %s: %s" % (method, data.get("error")))
    return data


def _addon_version():
    addon = get_addon()
    if not addon:
        return "0"
    try:
        return addon.getAddonInfo("version") or "0"
    except Exception:
        return "0"


def parse_int(v):
    if v is None:
        return None
    try:
        i = int(v)
        if i < 0:
            return None
        return i
    except (TypeError, ValueError):
        return None


def normalize_numeric_id(val):
    if val is None or val == "":
        return None
    try:
        s = str(val).strip()
        if s.lower().startswith("tt"):
            return None
        return int(float(s))
    except (TypeError, ValueError):
        return None


def normalize_imdb_id(val):
    if val is None or val == "":
        return None
    s = str(val).strip()
    if re.match(r"^tt\d+$", s, re.I):
        return s
    try:
        n = int(float(s))
        return "tt%07d" % n if n > 0 else None
    except (TypeError, ValueError):
        return None
def _safe_log_url(url):
    if "api_key=" in url:
        return re.sub(r"api_key=[^&]+", "api_key=***", url)
    return url


def _remote_cooldown_bucket(source_name):
    if source_name == "TMDB":
        return "tmdb"
    if source_name == "TheIntroDB":
        return "theintrodb"
    if source_name == "IntroDB.app":
        return "introdb"
    return "other"


def _remote_failure_cooldown_seconds():
    addon = get_addon()
    if not addon:
        return 120
    raw = addon_get_setting_text(addon, "remote_api_failure_cooldown_seconds", "120")
    try:
        n = int(str(raw).strip())
    except (TypeError, ValueError):
        n = 120
    return max(0, min(n, 3600))


def _remote_fetch_cooldown_active(bucket):
    secs = _remote_failure_cooldown_seconds()
    if secs <= 0:
        _REMOTE_FETCH_COOL_UNTIL.pop(bucket, None)
        _REMOTE_FETCH_FAILURE_STREAK.pop(bucket, None)
        return False
    until = _REMOTE_FETCH_COOL_UNTIL.get(bucket)
    if until is None:
        return False
    now = time.monotonic()
    if now >= until:
        _REMOTE_FETCH_COOL_UNTIL.pop(bucket, None)
        return False
    return True


def _retry_after_seconds_from_http_error(exc):
    """
    HTTP 429 often includes Retry-After (seconds). Some servers send an HTTP-date; we only parse integer seconds.
    """
    if not isinstance(exc, HTTPError) or exc.code != 429:
        return None
    try:
        ra = exc.headers.get("Retry-After")
        if ra is None:
            return None
        return int(str(ra).strip())
    except (TypeError, ValueError):
        return None


def _remote_fetch_begin_failure_cooldown(bucket, source_name, http_exc=None):
    base = _remote_failure_cooldown_seconds()
    if base <= 0:
        return

    streak = _REMOTE_FETCH_FAILURE_STREAK.get(bucket, 0) + 1
    _REMOTE_FETCH_FAILURE_STREAK[bucket] = streak

    retry_after = _retry_after_seconds_from_http_error(http_exc)
    if retry_after is not None:
        delay = max(retry_after, base)
        _rlog(
            "%s: HTTP 429 — using Retry-After=%ss (clamped with base %ss)"
            % (source_name, retry_after, base)
        )
    else:
        exp = min(streak - 1, _REMOTE_BACKOFF_EXPONENT_CAP)
        delay = min(base * (2**exp), _REMOTE_BACKOFF_CAP_SECONDS)

    delay = max(1, min(int(delay), _REMOTE_BACKOFF_CAP_SECONDS))
    _REMOTE_FETCH_COOL_UNTIL[bucket] = time.monotonic() + delay
    _rlog(
        "%s: failure backoff %ds (streak=%d, bucket=%s)"
        % (source_name, delay, streak, bucket)
    )


def _remote_fetch_mark_success(bucket):
    _REMOTE_FETCH_COOL_UNTIL.pop(bucket, None)
    _REMOTE_FETCH_FAILURE_STREAK.pop(bucket, None)


def fetch_remote_json(url, source_name, extra_headers=None):
    bucket = _remote_cooldown_bucket(source_name)
    if _remote_fetch_cooldown_active(bucket):
        _rlog(
            "%s: skipping request (%s cooldown active — reduce spam after errors)"
            % (source_name, bucket)
        )
        return None

    _rlog("%s lookup request -> %s" % (source_name, _safe_log_url(url)))
    headers = {
        "User-Agent": "%s/%s" % (ADDON_ID, _addon_version()),
        "Accept": "application/json",
    }
    if extra_headers:
        for k, v in extra_headers.items():
            if v is not None and str(v).strip():
                headers[k] = str(v).strip()
    request = Request(
        url,
        headers=headers,
    )
    try:
        with closing(urlopen(request, timeout=REMOTE_LOOKUP_TIMEOUT)) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        if exc.code == 404:
            _rlog(f"{source_name} lookup returned 404 (no metadata match)")
        else:
            _rlog(f"{source_name} lookup failed with HTTP {exc.code}")
            _remote_fetch_begin_failure_cooldown(bucket, source_name, exc)
        return None
    except URLError as exc:
        _rlog(f"{source_name} lookup failed: {exc.reason}")
        _remote_fetch_begin_failure_cooldown(bucket, source_name, None)
        return None
    except Exception as exc:
        _rlog(f"{source_name} lookup failed: {exc}")
        _remote_fetch_begin_failure_cooldown(bucket, source_name, None)
        return None

    try:
        data = json.loads(body)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        _rlog(f"{source_name} lookup returned invalid JSON: {exc}")
        _remote_fetch_begin_failure_cooldown(bucket, source_name, None)
        return None

    _remote_fetch_mark_success(bucket)
    return data
