# -*- coding: utf-8 -*-
"""TMDB API helpers for Skippy remote lookup."""

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

from remote_http import (
    ADDON_ID,
    TMDB_API3_BASE,
    TMDB_HELPER_ADDON_ID,
    REMOTE_LOOKUP_TIMEOUT,
    _rlog,
    _safe_log_url,
    fetch_remote_json,
    jsonrpc,
    normalize_imdb_id,
    normalize_numeric_id,
    parse_int,
)
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
