# -*- coding: utf-8 -*-
"""Remote intro/recap lookup: **TV** — TheIntroDB + IntroDB.app; **movies** — TheIntroDB only.

TheIntroDB and IntroDB require **TMDB** and/or **IMDb** ids (see https://theintrodb.org/docs and
https://introdb.app/docs/api). **Primary** source is Kodi’s library (`uniqueid`). When those ids are
missing, Skippy can call **api.themoviedb.org/3** (optional API key in settings, or the key from
**plugin.video.themoviedb.helper** if enabled). **Playback path** uses JSON-RPC: `Files.GetFileDetails`,
`GetEpisodeDetails` / `GetMovieDetails`, optional `GetEpisodes` path filter, and **SxxExx** for TV gaps.

Debug: enable **Settings → Debug logging**, then filter `kodi.log` for `service.skippy - remote`.
"""
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

from segment_item import SegmentItem
from settings_utils import addon_get_bool, addon_get_setting_text, get_addon, log_remote

ADDON_ID = "service.skippy"

# Stored labelenum values for settings tv_online_merge_priority / movie_online_merge_priority
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


THEINTRODB_BASE_URL = "https://api.theintrodb.org/v2/media"
INTRODB_SEGMENTS_URL = "http://api.introdb.app/segments"
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
        result = json.loads(raw)
    except Exception as exc:
        _rlog(f"JSON-RPC failure for {method}: {exc}")
        return {}
    if result.get("error") and log_errors:
        _rlog(f"JSON-RPC error for {method}: {result.get('error')}")
    return result


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


def _tmdb_helper_addon_api_key():
    """API key from plugin.video.themoviedb.helper (TMDB v3)."""
    try:
        h = xbmcaddon.Addon(TMDB_HELPER_ADDON_ID)
    except Exception:
        return None
    for sid in (
        "tmdb_apikey",
        "tmdb_api_key",
        "api_key",
    ):
        raw = None
        get_ok = False
        try:
            raw = h.getSetting(sid)
            get_ok = True
        except Exception:
            pass
        if get_ok:
            if raw is not None and str(raw).strip():
                return str(raw).strip()
            continue
        if hasattr(h, "getSettingString"):
            try:
                raw = h.getSettingString(sid)
                if raw is not None and str(raw).strip():
                    return str(raw).strip()
            except Exception:
                pass
    return None


def _get_tmdb_api_key():
    """
    TMDB v3 API key: single Skippy field (`tv_tmdb_api_key` id), then TheMovieDB Helper when enabled.
    Shared by TV episode and movie online lookup (Segment sources → Online APIs).
    """
    addon = get_addon()
    if not addon:
        return None
    k = addon_get_setting_text(addon, "tv_tmdb_api_key", "")
    if k and str(k).strip():
        return str(k).strip()
    if not addon_get_bool(addon, "tv_tmdb_use_helper_api_key", True):
        return None
    return _tmdb_helper_addon_api_key()


def _tmdb_api3_json(subpath, api_key, extra_params=None):
    if not api_key:
        return None
    params = {"api_key": api_key}
    if extra_params:
        params.update(extra_params)
    url = "%s%s?%s" % (TMDB_API3_BASE, subpath, urlencode(params))
    return fetch_remote_json(url, "TMDB")


def _tmdb_search_tv_show_id(title, api_key):
    if not title or not api_key:
        return None
    data = _tmdb_api3_json("/search/tv", api_key, {"query": title})
    if not isinstance(data, dict):
        return None
    results = data.get("results") or []
    if not results:
        return None
    try:
        return int(results[0]["id"])
    except (KeyError, TypeError, ValueError, IndexError):
        return None


def _tmdb_enrich_missing_ids(item, season, episode, tmdb_id, imdb_id, show_imdb_id, api_key):
    """
    Fill missing TMDB show id / episode IMDb / show IMDb via TMDB v3 (IntroDB / TheIntroDB requirements).
    """
    title = (item.get("showtitle") or item.get("title") or "").strip()
    tv_id = tmdb_id
    if tv_id is not None:
        try:
            tv_id = int(tv_id)
        except (TypeError, ValueError):
            tv_id = None
    if tv_id is None and title:
        tv_id = _tmdb_search_tv_show_id(title, api_key)
        if tv_id:
            _rlog("TMDB API: matched show id=%s for query %r" % (tv_id, title[:50]))
    if tv_id is None:
        return tmdb_id, imdb_id, show_imdb_id

    new_tmdb = tmdb_id if tmdb_id is not None else tv_id
    new_imdb = imdb_id
    new_show_imdb = show_imdb_id

    if new_show_imdb is None:
        ex = _tmdb_api3_json("/tv/%s/external_ids" % int(tv_id), api_key)
        if isinstance(ex, dict):
            new_show_imdb = normalize_imdb_id(ex.get("imdb_id"))
            if new_show_imdb:
                _rlog("TMDB API: show IMDb from external_ids")

    if new_imdb is None:
        ep = _tmdb_api3_json(
            "/tv/%s/season/%s/episode/%s" % (int(tv_id), int(season), int(episode)),
            api_key,
        )
        if isinstance(ep, dict):
            ext = ep.get("external_ids") or {}
            new_imdb = normalize_imdb_id(ext.get("imdb_id"))
            if new_imdb:
                _rlog("TMDB API: episode IMDb from episode external_ids")

    return new_tmdb, new_imdb, new_show_imdb


def _tmdb_enrich_missing_movie_ids(item, tmdb_id, imdb_id, api_key):
    """Fill missing TMDB movie id / IMDb via TMDB v3 find, search, and external_ids."""
    title = (item.get("title") or "").strip()
    mid = tmdb_id
    if mid is not None:
        try:
            mid = int(mid)
        except (TypeError, ValueError):
            mid = None
    # IMDb in Kodi but no TMDB uniqueid — resolve movie id via /find (same idea as TV external_ids).
    if mid is None and imdb_id:
        data = _tmdb_api3_json(
            "/find/%s" % imdb_id,
            api_key,
            {"external_source": "imdb_id"},
        )
        if isinstance(data, dict):
            for m in data.get("movie_results") or []:
                try:
                    cand = int(m.get("id"))
                except (TypeError, ValueError):
                    continue
                if cand:
                    mid = cand
                    _rlog("TMDB API: movie tmdb_id=%s from find by IMDb" % mid)
                    break
    if mid is None and title:
        data = _tmdb_api3_json("/search/movie", api_key, {"query": title})
        if isinstance(data, dict):
            results = data.get("results") or []
            if results:
                try:
                    mid = int(results[0]["id"])
                except (KeyError, TypeError, ValueError, IndexError):
                    mid = None
                if mid:
                    _rlog("TMDB API: matched movie id=%s for query %r" % (mid, title[:50]))
    if mid is None:
        return tmdb_id, imdb_id

    new_tmdb = tmdb_id if tmdb_id is not None else mid
    new_imdb = imdb_id
    if not new_imdb:
        ex = _tmdb_api3_json("/movie/%s/external_ids" % int(mid), api_key)
        if isinstance(ex, dict):
            new_imdb = normalize_imdb_id(ex.get("imdb_id"))
            if new_imdb:
                _rlog("TMDB API: movie IMDb from external_ids")

    return new_tmdb, new_imdb


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


def fetch_remote_json(url, source_name):
    bucket = _remote_cooldown_bucket(source_name)
    if _remote_fetch_cooldown_active(bucket):
        _rlog(
            "%s: skipping request (%s cooldown active — reduce spam after errors)"
            % (source_name, bucket)
        )
        return None

    _rlog("%s lookup request -> %s" % (source_name, _safe_log_url(url)))
    request = Request(
        url,
        headers={
            "User-Agent": "%s/%s" % (ADDON_ID, _addon_version()),
            "Accept": "application/json",
        },
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
    except (TypeError, ValueError) as exc:
        _rlog(f"{source_name} lookup returned invalid JSON: {exc}")
        _remote_fetch_begin_failure_cooldown(bucket, source_name, None)
        return None

    _remote_fetch_mark_success(bucket)
    return data


def get_active_video_player_id():
    result = jsonrpc("Player.GetActivePlayers", log_errors=False)
    players = result.get("result") or []
    for p in players:
        if p.get("type") == "video":
            return p.get("playerid")
    return None


def _get_playing_file_path():
    try:
        return xbmc.Player().getPlayingFile()
    except Exception:
        return None


def _item_has_playback_metadata(item):
    """True when Player.GetItem has enough data to use (not {} during startup race)."""
    if not item:
        return False
    if item.get("type") == "episode" and item.get("id"):
        return True
    if item.get("file") or item.get("showtitle"):
        return True
    return False


def _episode_from_get_episodes_path(ep_id, path_hint):
    """
    Last-resort Kodi library lookup: find the episode row by path (same idea as other addons
    that match the playing file to the library). Does not call TMDB — only JSON-RPC.
    """
    if not path_hint or not ep_id:
        return None
    base = os.path.basename(path_hint)
    if not base:
        return None
    needles = [base]
    if "." in base:
        needles.append(base.rsplit(".", 1)[0])
    needles = [n for n in needles if len(n) >= 4]
    seen = set()
    for needle in needles:
        if needle in seen:
            continue
        seen.add(needle)
        r = jsonrpc(
            "VideoLibrary.GetEpisodes",
            {
                "properties": _GET_EPISODES_PROPERTIES,
                "filter": {
                    "field": "path",
                    "operator": "contains",
                    "value": needle,
                },
            },
            log_errors=False,
        )
        if r.get("error"):
            continue
        for ep in (r.get("result") or {}).get("episodes") or []:
            try:
                eid = int(ep.get("episodeid"))
            except (TypeError, ValueError):
                continue
            if eid == ep_id:
                return ep
    return None


def _fetch_episode_details(ep_id, path_hint=None):
    """Return (episode row dict or None, jsonrpc error or None). Retries with fewer fields on -32602."""
    det = jsonrpc(
        "VideoLibrary.GetEpisodeDetails",
        {"episodeid": ep_id, "properties": _EPISODE_JSONRPC_FIELDS},
        log_errors=False,
    )
    ed = (det.get("result") or {}).get("episodedetails") or {}
    if ed:
        return ed, None
    err = det.get("error")
    last_err = err
    if err and err.get("code") == -32602:
        det2 = jsonrpc(
            "VideoLibrary.GetEpisodeDetails",
            {"episodeid": ep_id, "properties": _EPISODE_JSONRPC_FIELDS_MINIMAL},
            log_errors=False,
        )
        ed2 = (det2.get("result") or {}).get("episodedetails") or {}
        if ed2:
            _rlog(
                "GetEpisodeDetails: using minimal properties (full list rejected by Kodi)"
            )
            return ed2, None
        last_err = det2.get("error") or err
    if path_hint:
        ep_list = _episode_from_get_episodes_path(ep_id, path_hint)
        if ep_list:
            _rlog(
                "Episode metadata via VideoLibrary.GetEpisodes (path contains filename)"
            )
            return ep_list, None
    return None, last_err


_MOVIE_JSONRPC_FIELDS = ["uniqueid", "imdbnumber", "title", "file"]


def _fetch_movie_details(movie_id):
    det = jsonrpc(
        "VideoLibrary.GetMovieDetails",
        {"movieid": int(movie_id), "properties": _MOVIE_JSONRPC_FIELDS},
        log_errors=False,
    )
    return (det.get("result") or {}).get("moviedetails") or {}


def _item_from_files_get_file_details(path):
    """
    When Player.GetItem returns {} for ~1s after start, resolve library episode or movie via path.
    Files.GetFileDetails -> GetEpisodeDetails / GetMovieDetails.
    """
    if not path:
        return None
    r = jsonrpc(
        "Files.GetFileDetails",
        {"file": path, "media": "video", "properties": ["title", "playcount", "runtime"]},
        log_errors=False,
    )
    fd = (r.get("result") or {}).get("filedetails") or {}
    if fd.get("type") == "movie":
        mid = fd.get("id")
        try:
            mid = int(mid)
        except (TypeError, ValueError):
            return None
        md = _fetch_movie_details(mid)
        if not md:
            _rlog("Files.GetFileDetails fallback: GetMovieDetails empty for movieid=%s" % mid)
            return None
        item = {
            "type": "movie",
            "id": mid,
            "file": md.get("file") or path,
            "title": md.get("title"),
        }
        for k in ("uniqueid", "imdbnumber"):
            if md.get(k) is not None:
                item[k] = md[k]
        return item
    if fd.get("type") != "episode":
        return None
    ep_id = fd.get("id")
    try:
        ep_id = int(ep_id)
    except (TypeError, ValueError):
        return None
    ed, rpc_err = _fetch_episode_details(ep_id, path)
    if not ed:
        if rpc_err:
            _rlog(
                "Files.GetFileDetails fallback: GetEpisodeDetails JSON-RPC error for episodeid=%s: %s"
                % (ep_id, rpc_err)
            )
        else:
            _rlog(
                "Files.GetFileDetails fallback: GetEpisodeDetails empty for episodeid=%s"
                % ep_id
            )
        return None
    item = {
        "type": "episode",
        "id": ep_id,
        "file": ed.get("file") or path,
    }
    for k in ("season", "episode", "uniqueid", "imdbnumber", "tvshowid", "title"):
        if ed.get(k) is not None:
            item[k] = ed[k]
    st = ed.get("showtitle") or ed.get("tvshowtitle")
    if st:
        item["showtitle"] = st
    return item


def get_enriched_playing_item():
    """Return current video Player.GetItem dict with season, uniqueid, etc., or None."""
    player_id = get_active_video_player_id()
    if player_id is None:
        _rlog("no active video player id (cannot run Player.GetItem)")
        return None

    props = _PLAYER_GETITEM_FIELDS
    result = jsonrpc(
        "Player.GetItem",
        {"playerid": player_id, "properties": props},
        log_errors=False,
    )
    raw = (result.get("result") or {}).get("item") or {}
    item = raw if _item_has_playback_metadata(raw) else None

    if not item:
        path = _get_playing_file_path()
        item = _item_from_files_get_file_details(path)
        if item:
            _rlog(
                "resolved playing item via Files.GetFileDetails (Player.GetItem was empty — startup race)"
            )

    if not item:
        for attempt in range(4):
            _rlog(
                "Player.GetItem still empty (attempt %d/4) — retry in 250ms"
                % (attempt + 1)
            )
            xbmc.sleep(250)
            result = jsonrpc(
                "Player.GetItem",
                {"playerid": player_id, "properties": props},
                log_errors=False,
            )
            raw = (result.get("result") or {}).get("item") or {}
            if raw and _item_has_playback_metadata(raw):
                item = raw
                break
            if attempt == 3:
                path = _get_playing_file_path()
                item = _item_from_files_get_file_details(path)
                if item:
                    _rlog(
                        "resolved playing item via Files.GetFileDetails after GetItem retries"
                    )

    if not item:
        _rlog(
            "Remote TV segments: no enriched playing item (GetItem empty after retries + file fallback failed)"
        )
        return None

    # Minimal Player.GetItem omits type/id/uniqueid — merge library row once via path.
    path = item.get("file") or _get_playing_file_path()
    itype = (item.get("type") or "").lower()
    need_lib = path and (
        (itype == "episode" and (not item.get("id") or not item.get("uniqueid")))
        or (itype == "movie" and (not item.get("id") or not item.get("uniqueid")))
        or (
            itype not in ("episode", "movie")
            and (not item.get("id") or not item.get("uniqueid"))
        )
    )
    if need_lib:
        sup = _item_from_files_get_file_details(path)
        if sup:
            for k in (
                "type",
                "id",
                "season",
                "episode",
                "uniqueid",
                "imdbnumber",
                "tvshowid",
                "title",
                "file",
            ):
                if sup.get(k) is not None:
                    item[k] = sup[k]
            if sup.get("showtitle"):
                item["showtitle"] = sup["showtitle"]

    itype = (item.get("type") or "").lower()
    if itype == "movie":
        st = item.get("title") or ""
    else:
        st = item.get("showtitle") or item.get("title") or ""
    _rlog(
        "playing item: type=%s id=%s S=%s E=%s show=%r"
        % (
            item.get("type"),
            item.get("id"),
            item.get("season"),
            item.get("episode"),
            st[:60] + ("…" if len(st) > 60 else ""),
        )
    )
    return item


def _use_filename_season_episode_fallback(item):
    """
    Season/episode from Kodi library metadata take priority. Parse SxxExx from the path only
    when the current item is not a library episode (e.g. file mode / not scanned).
    """
    if not item:
        return True
    itype = (item.get("type") or "").lower()
    if itype != "episode":
        return True
    ep_id = item.get("id")
    try:
        ep_id = int(ep_id)
    except (TypeError, ValueError):
        ep_id = None
    return not (ep_id and ep_id > 0)


def get_show_imdb_id(item):
    uid = item.get("uniqueid") or {}
    imdb = normalize_imdb_id(uid.get("imdb"))
    if imdb:
        return imdb

    tvshowid = item.get("tvshowid")
    try:
        tvshowid = int(tvshowid)
    except (TypeError, ValueError):
        tvshowid = None
    if tvshowid and tvshowid > 0:
        det = jsonrpc(
            "VideoLibrary.GetTVShowDetails",
            {"tvshowid": tvshowid, "properties": ["imdbnumber", "uniqueid"]},
            log_errors=False,
        )
        td = (det.get("result") or {}).get("tvshowdetails") or {}
        tuid = td.get("uniqueid") or {}
        imdb = normalize_imdb_id(tuid.get("imdb") or td.get("imdbnumber"))
        if imdb:
            return imdb
    return None


def _parse_library_episode_id(item):
    eid = item.get("id")
    try:
        eid = int(eid)
        return eid if eid > 0 else None
    except (TypeError, ValueError):
        return None


def _parse_library_movie_id(item):
    mid = item.get("id")
    try:
        mid = int(mid)
        return mid if mid > 0 else None
    except (TypeError, ValueError):
        return None


def _apply_kodi_movie_id_layers(item, tmdb_id, imdb_id):
    """Merge uniqueid from GetMovieDetails when Player item is thin."""
    if (item.get("type") or "").lower() != "movie":
        return tmdb_id, imdb_id
    mid = _parse_library_movie_id(item)
    if not mid:
        return tmdb_id, imdb_id
    if tmdb_id is not None and imdb_id:
        return tmdb_id, imdb_id
    md = _fetch_movie_details(mid)
    uid = md.get("uniqueid") or {}
    if not isinstance(uid, dict):
        uid = {}
    if tmdb_id is None:
        tmdb_id = normalize_numeric_id(uid.get("tmdb"))
        if tmdb_id is not None:
            _rlog("Kodi movie layers: tmdb_id=%s from GetMovieDetails" % tmdb_id)
    if not imdb_id:
        imdb_id = normalize_imdb_id(uid.get("imdb") or md.get("imdbnumber"))
        if imdb_id:
            _rlog("Kodi movie layers: imdb from GetMovieDetails")
    return tmdb_id, imdb_id


def build_movie_context(item):
    """Context for TheIntroDB movie lookup (tmdb_id and/or imdb_id)."""
    if not item:
        return None
    if (item.get("type") or "").lower() != "movie":
        return None
    uid = item.get("uniqueid") or {}
    if not isinstance(uid, dict):
        uid = {}
    tmdb_id = normalize_numeric_id(uid.get("tmdb"))
    imdb_id = normalize_imdb_id(uid.get("imdb") or item.get("imdbnumber"))
    tmdb_id, imdb_id = _apply_kodi_movie_id_layers(item, tmdb_id, imdb_id)

    addon = get_addon()
    if addon and addon_get_bool(addon, "tv_tmdb_resolve_missing_ids", True):
        key = _get_tmdb_api_key()
        if key and (tmdb_id is None or not imdb_id):
            tmdb_id, imdb_id = _tmdb_enrich_missing_movie_ids(item, tmdb_id, imdb_id, key)
            _rlog(
                "After TMDB API enrichment (movie): tmdb=%s imdb=%s" % (tmdb_id, imdb_id)
            )

    if tmdb_id is None and not imdb_id:
        _rlog("Remote movie segments skipped: no TMDB/IMDb after Kodi and TMDB API")
        return None
    return {"type": "movie", "tmdb_id": tmdb_id, "imdb_id": imdb_id}


def _resolve_tvshow_id(item):
    """tvshowid from item, episode row, or infolabel (service.nextonlibrary-style)."""
    tid = item.get("tvshowid")
    try:
        tid = int(tid)
        if tid > 0:
            return tid
    except (TypeError, ValueError):
        pass
    ep_id = _parse_library_episode_id(item)
    if ep_id:
        det = jsonrpc(
            "VideoLibrary.GetEpisodeDetails",
            {"episodeid": ep_id, "properties": ["tvshowid"]},
            log_errors=False,
        )
        ed = (det.get("result") or {}).get("episodedetails") or {}
        ts = ed.get("tvshowid")
        try:
            ts = int(ts)
            if ts > 0:
                return ts
        except (TypeError, ValueError):
            pass
    raw = xbmc.getInfoLabel("VideoPlayer.TvShowDBID")
    ts = parse_int(raw)
    return ts if ts and ts > 0 else None


def _tmdb_from_tvshow_row(tvshow_id):
    det = jsonrpc(
        "VideoLibrary.GetTVShowDetails",
        {"tvshowid": int(tvshow_id), "properties": ["uniqueid"]},
        log_errors=False,
    )
    td = (det.get("result") or {}).get("tvshowdetails") or {}
    uid = td.get("uniqueid") or {}
    return normalize_numeric_id(uid.get("tmdb"))


def _uniqueid_from_episode_row(episode_id):
    """Minimal GetEpisodeDetails — uniqueid only (imdbnumber is not a valid Episode field)."""
    det = jsonrpc(
        "VideoLibrary.GetEpisodeDetails",
        {"episodeid": int(episode_id), "properties": ["uniqueid"]},
        log_errors=False,
    )
    if det.get("error"):
        return {}, None
    ed = (det.get("result") or {}).get("episodedetails") or {}
    uid = ed.get("uniqueid") or {}
    if not isinstance(uid, dict):
        uid = {}
    imdb = normalize_imdb_id(uid.get("imdb"))
    return uid, imdb


def _get_first_infolabel(labels):
    for lab in labels:
        try:
            v = xbmc.getInfoLabel(lab)
        except Exception:
            v = ""
        if v and str(v).strip():
            return str(v).strip()
    return ""


def _tmdb_from_infolabels():
    v = _get_first_infolabel(
        [
            "ListItem.UniqueID(tmdb)",
            "VideoPlayer.UniqueID(tmdb)",
            "VideoPlayer.Property(tmdb_id)",
            "VideoPlayer.Property(tmdb)",
        ]
    )
    return normalize_numeric_id(v) if v else None


def _show_imdb_from_infolabels():
    v = _get_first_infolabel(
        [
            "VideoPlayer.TVshowIMDBNumber",
            "Container.ListItem.TVShowIMDBNumber",
            "ListItem.TVShowIMDBNumber",
        ]
    )
    return normalize_imdb_id(v) if v else None


def _apply_kodi_library_id_layers(item, tmdb_id, imdb_id, show_imdb_id):
    """
    Fill TMDB/IMDb from Kodi DB + infolabels (same strategy as service.nextonlibrary):
    show-level uniqueid.tmdb often exists when episode row only has TVDB/Sonarr.
    """
    if (item.get("type") or "").lower() != "episode":
        return tmdb_id, imdb_id, show_imdb_id

    if tmdb_id is None:
        tvshow_id = _resolve_tvshow_id(item)
        if tvshow_id:
            tmdb_id = _tmdb_from_tvshow_row(tvshow_id)
            if tmdb_id is not None:
                _rlog(
                    "Kodi layers: tmdb_id=%s from TV show uniqueid (tvshowid=%s)"
                    % (tmdb_id, tvshow_id)
                )

    ep_id = _parse_library_episode_id(item)
    if ep_id:
        if tmdb_id is None or not imdb_id:
            uid_e, imdb_e = _uniqueid_from_episode_row(ep_id)
            if tmdb_id is None:
                tmdb_id = normalize_numeric_id(uid_e.get("tmdb"))
                if tmdb_id is not None:
                    _rlog(
                        "Kodi layers: tmdb_id=%s from episode DB uniqueid (episodeid=%s)"
                        % (tmdb_id, ep_id)
                    )
            if not imdb_id and imdb_e:
                imdb_id = imdb_e
                _rlog("Kodi layers: episode imdb from GetEpisodeDetails")

    if tmdb_id is None:
        tmdb_il = _tmdb_from_infolabels()
        if tmdb_il is not None:
            tmdb_id = tmdb_il
            _rlog("Kodi layers: tmdb_id=%s from infolabel" % tmdb_id)

    if not show_imdb_id:
        sil = _show_imdb_from_infolabels()
        if sil:
            show_imdb_id = sil
            _rlog("Kodi layers: show_imdb from infolabel")

    return tmdb_id, imdb_id, show_imdb_id


def build_tv_episode_context(item):
    if not item:
        return None

    season = parse_int(item.get("season"))
    episode = parse_int(item.get("episode"))
    file_path = item.get("file") or ""

    if season is None or episode is None:
        m = _SXXEXX.search(file_path or "")
        if m:
            if _use_filename_season_episode_fallback(item):
                season = season if season is not None else int(m.group(1))
                episode = episode if episode is not None else int(m.group(2))
            elif (item.get("type") or "").lower() == "episode" and item.get("id"):
                # Library episode: fill only missing values (e.g. GetEpisodeDetails omitted season)
                season = season if season is not None else int(m.group(1))
                episode = episode if episode is not None else int(m.group(2))
        if season is None or episode is None:
            if (item.get("type") or "").lower() == "episode" and item.get("id"):
                _rlog(
                    "Remote TV segments skipped: library episode missing season/episode in metadata "
                    "and no SxxExx in path"
                )
            else:
                _rlog(
                    "Remote TV segments skipped: no season/episode after metadata "
                    "(for files not in the library, add SxxExx to the filename if needed)"
                )
            return None

    uid = item.get("uniqueid") or {}
    if not isinstance(uid, dict):
        uid = {}
    tmdb_id = normalize_numeric_id(uid.get("tmdb"))
    imdb_id = normalize_imdb_id(uid.get("imdb") or item.get("imdbnumber"))
    show_imdb_id = get_show_imdb_id(item) or imdb_id

    tmdb_id, imdb_id, show_imdb_id = _apply_kodi_library_id_layers(
        item, tmdb_id, imdb_id, show_imdb_id
    )
    if not show_imdb_id:
        show_imdb_id = get_show_imdb_id(item) or imdb_id

    _rlog(
        "Kodi library uniqueid keys for S%02dE%02d: %s (tmdb=%s imdb=%s show_imdb=%s)"
        % (
            season,
            episode,
            sorted(uid.keys()),
            tmdb_id,
            imdb_id,
            show_imdb_id,
        )
    )

    addon = get_addon()
    if (
        addon
        and addon_get_bool(addon, "tv_use_online_segment_lookup", False)
        and addon_get_bool(addon, "tv_tmdb_resolve_missing_ids", True)
    ):
        key = _get_tmdb_api_key()
        if key and (tmdb_id is None or not imdb_id or show_imdb_id is None):
            tmdb_id, imdb_id, show_imdb_id = _tmdb_enrich_missing_ids(
                item, season, episode, tmdb_id, imdb_id, show_imdb_id, key
            )
            _rlog(
                "After TMDB API enrichment: tmdb=%s episode_imdb=%s show_imdb=%s"
                % (tmdb_id, imdb_id, show_imdb_id)
            )

    if tmdb_id is None and not imdb_id and not show_imdb_id:
        tvdb_raw = uid.get("tvdb")
        if tvdb_raw is not None and str(tvdb_raw).strip() != "":
            _rlog(
                "Remote TV segments skipped: Kodi has TVDB in uniqueid (%s) but TheIntroDB and "
                "IntroDB.app need TMDB and/or IMDb — add a TMDB API key (TV episode settings), "
                "use TheMovieDB Helper’s key, or rescrape with TMDB/IMDb."
                % tvdb_raw
            )
        else:
            _rlog(
                "Remote TV segments skipped: no TMDB/IMDb for S%02dE%02d after Kodi and TMDB API "
                "(enable resolve + API key or TheMovieDB Helper), or rescrape."
                % (season, episode)
            )
        return None

    ctx = {
        "type": "tv",
        "season": season,
        "episode": episode,
        "tmdb_id": tmdb_id,
        "imdb_id": imdb_id,
        "show_imdb_id": show_imdb_id,
    }
    _rlog(
        "TV context: S%02dE%02d tmdb_id=%s episode_imdb=%s show_imdb=%s"
        % (season, episode, tmdb_id, imdb_id, show_imdb_id)
    )
    return ctx


def build_tv_cache_key(context):
    return (
        context.get("type"),
        context.get("tmdb_id"),
        context.get("imdb_id"),
        context.get("show_imdb_id"),
        context.get("season"),
        context.get("episode"),
    )


def normalize_skip_window(start_value, end_value, total_time):
    try:
        end_seconds = float(end_value)
    except (TypeError, ValueError):
        return None
    try:
        start_seconds = float(start_value) if start_value is not None else 1.0
    except (TypeError, ValueError):
        start_seconds = 1.0
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


def _theintrodb_segment_entries(payload, total_time):
    out = []
    for segment_name in REMOTE_SEGMENT_PAYLOAD_KEYS:
        entries = payload.get(segment_name) or []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            try:
                end_ms = float(entry.get("end_ms"))
            except (TypeError, ValueError):
                continue
            start_ms = entry.get("start_ms")
            try:
                start_ms = float(start_ms) if start_ms is not None else None
            except (TypeError, ValueError):
                start_ms = None
            if start_ms is not None and end_ms <= start_ms:
                continue
            window = normalize_skip_window(
                None if start_ms is None else (start_ms / 1000.0),
                end_ms / 1000.0,
                total_time,
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

    payload = fetch_remote_json(
        "%s?%s" % (THEINTRODB_BASE_URL, urlencode(query)),
        "TheIntroDB",
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


def fetch_remote_movie_segments(total_time, cache):
    """
    Fetch intro/recap SegmentItems for the current movie (TheIntroDB only). Uses cache dict.
    """
    item = get_enriched_playing_item()
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
    else:
        _rlog("TheIntroDB/IntroDB merge (movie): empty")
    return list(merged)


def fetch_remote_tv_segments(total_time, cache):
    """
    Fetch intro/recap SegmentItems for the current TV episode. Uses cache dict keyed by episode ids.
    """
    item = get_enriched_playing_item()
    if not item:
        _rlog("Remote TV segments: no enriched playing item")
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
    if not merged:
        _rlog(
            "merged remote (TV): empty (TheIntroDB=%d, IntroDB.app=%d segments before merge)"
            % (len(the_segs), len(intro_segs))
        )
    return list(merged)
