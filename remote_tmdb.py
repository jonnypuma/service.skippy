# -*- coding: utf-8 -*-
"""TMDB API helpers for Skippy remote lookup."""


import re
import unicodedata

import xbmcaddon
from urllib.parse import urlencode


from settings_utils import (
    addon_get_bool,
    addon_get_setting_text,
    get_addon,
)

from remote_http import (
    TMDB_API3_BASE,
    TMDB_HELPER_ADDON_ID,
    _rlog,
    fetch_remote_json,
    normalize_imdb_id,
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


# "Doctor Who (2005)": the year in brackets at the end of a title, as libraries name remakes.
_TITLE_YEAR = re.compile(r"^(.*\S)\s*\((\d{4})\)\s*$")


def split_title_year(title):
    """``("Doctor Who", 2005)`` for ``"Doctor Who (2005)"``; a title without a year gets None."""
    text = (title or "").strip()
    match = _TITLE_YEAR.match(text)
    if match:
        return match.group(1).strip(), int(match.group(2))
    return text, None


def _year_of(value):
    """The year of a TMDB date (``"2005-03-26"``) or a Kodi year (2005, ``"2005"``), else None."""
    match = re.match(r"\s*(\d{4})", str(value or ""))
    return int(match.group(1)) if match else None


def _title_key(text):
    """Case, accents and punctuation do not count when titles are compared."""
    folded = unicodedata.normalize("NFKD", str(text or "")).casefold()
    return " ".join("".join(ch if ch.isalnum() else " " for ch in folded if not unicodedata.combining(ch)).split())


def pick_search_result(results, title, year, name_keys, date_key):
    """
    The search row that best fits ``title`` and ``year``.

    TMDB orders by popularity, so the first row of "The Office" may be the other country's
    show. An exact title counts most, then the year (a year off by one counts half, as Kodi
    and TMDB sometimes disagree about it); between equals, TMDB's order decides.
    """
    wanted = _title_key(title)
    best, best_score = None, -1.0
    for row in results or []:
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        exact = any(_title_key(row.get(key)) == wanted for key in name_keys if row.get(key))
        score = 2.0 if exact else 0.0
        found = _year_of(row.get(date_key))
        if year and found:
            if found == year:
                score += 1.0
            elif abs(found - year) == 1:
                score += 0.5
        if score > best_score:
            best, best_score = row, score
    return best


def _tmdb_search_id(path, year_param, name_keys, date_key, title, api_key, year=None):
    if not title or not api_key:
        return None
    query, title_year = split_title_year(title)
    year = _year_of(year) or title_year
    results = []
    if year:
        data = _tmdb_api3_json(path, api_key, {"query": query, year_param: year})
        results = (data.get("results") or []) if isinstance(data, dict) else []
    if not results:
        data = _tmdb_api3_json(path, api_key, {"query": query})
        results = (data.get("results") or []) if isinstance(data, dict) else []
    row = pick_search_result(results, query, year, name_keys, date_key)
    if row is None:
        return None
    try:
        return int(row["id"])
    except (KeyError, TypeError, ValueError):
        return None


def _tmdb_search_tv_show_id(title, api_key, year=None):
    """TMDB id of the show called ``title`` (first aired in ``year`` when known)."""
    return _tmdb_search_id(
        "/search/tv", "first_air_date_year", ("name", "original_name"), "first_air_date", title, api_key, year
    )


def _tmdb_search_movie_id(title, api_key, year=None):
    """TMDB id of the movie called ``title`` (released in ``year`` when known)."""
    return _tmdb_search_id(
        "/search/movie", "year", ("title", "original_title"), "release_date", title, api_key, year
    )


def _tmdb_enrich_missing_ids(item, season, episode, tmdb_id, imdb_id, show_imdb_id, api_key, year=None):
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
        tv_id = _tmdb_search_tv_show_id(title, api_key, year)
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


def _tmdb_enrich_missing_movie_ids(item, tmdb_id, imdb_id, api_key, year=None):
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
        mid = _tmdb_search_movie_id(title, api_key, year if year is not None else item.get("year"))
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
