# -*- coding: utf-8 -*-
"""Playback fallback: chapters muxed in the playing file (not sidecar XML/EDL)."""

from __future__ import annotations

import json

import xbmc

from mkv_chapter_parse import parse_matroska_chapters_via_vfs
from segment_editor_parser import parse_embedded_chapters_via_mkvextract
from segment_item import SegmentItem
from settings_utils import (
    addon_get_setting_text,
    get_addon,
    log,
    log_service_detail,
    normalize_label,
    parse_kodi_jsonrpc_raw,
)


def _log_detail(msg):
    log_service_detail(msg, tag="segments")


def _playing_path(segment_player, video_path):
    path = (video_path or "").strip()
    if path:
        return path
    if segment_player is None:
        return ""
    try:
        return segment_player.getPlayingFile() or ""
    except RuntimeError:
        return ""


def _total_time(segment_player) -> float:
    if segment_player is None:
        return 0.0
    try:
        return float(segment_player.getTotalTime() or 0.0)
    except (RuntimeError, TypeError, ValueError):
        return 0.0


def _resolve_player_id(player_id):
    if player_id is not None:
        return player_id
    raw = xbmc.executeJSONRPC(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": "EmbeddedChaptersPlayers",
                "method": "Player.GetActivePlayers",
            }
        )
    )
    data, err = parse_kodi_jsonrpc_raw(raw)
    if err or not data:
        _log_detail("Embedded chapters: GetActivePlayers failed (%s)" % (err or "empty"))
        return None
    if data.get("error"):
        return None
    players = data.get("result") or []
    video_player = next((p for p in players if p.get("type") == "video"), None)
    if not video_player:
        return None
    return video_player.get("playerid")


def _chapter_time_to_seconds(raw, total_s: float) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0.0
    if value >= 1e12:
        return value / 1e9
    if total_s and value > max(total_s * 2.0, 1000.0):
        return value / 1000.0
    if not total_s and value > 86400:
        return value / 1000.0
    return value


def _rows_from_get_chapters(player_id, segment_player):
    """Kodi 22+ Player.GetChapters. Returns None if the method is unavailable."""
    if player_id is None:
        return None
    raw = xbmc.executeJSONRPC(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": "EmbeddedChaptersList",
                "method": "Player.GetChapters",
                "params": {"playerid": int(player_id)},
            }
        )
    )
    data, err = parse_kodi_jsonrpc_raw(raw)
    if err or not data:
        _log_detail("Embedded chapters: GetChapters failed (%s)" % (err or "empty"))
        return None
    error = data.get("error") or {}
    if error:
        code = error.get("code")
        message = str(error.get("message") or "")
        _log_detail(
            "Embedded chapters: GetChapters not used (%s %s)" % (code, message)
        )
        return None
    result = data.get("result")
    chapters = []
    if isinstance(result, dict):
        chapters = result.get("chapters") or []
    elif isinstance(result, list):
        chapters = result
    if not isinstance(chapters, list):
        return []
    total_s = _total_time(segment_player)
    rows = []
    for ch in chapters:
        if not isinstance(ch, dict):
            continue
        name = ch.get("name") or ch.get("label") or ""
        start = _chapter_time_to_seconds(ch.get("time", 0), total_s)
        rows.append({"name": name, "start": start, "end": None})
    return rows


def _rows_from_mkvextract(video_path):
    items = parse_embedded_chapters_via_mkvextract(video_path)
    if not items:
        return []
    return [
        {
            "name": getattr(item, "segment_type_label", "") or "",
            "start": float(item.start_seconds),
            "end": float(item.end_seconds),
        }
        for item in items
    ]


def _load_embedded_chapter_rows(segment_player, player_id, video_path):
    resolved_id = _resolve_player_id(player_id)
    jsonrpc_rows = _rows_from_get_chapters(resolved_id, segment_player)
    if jsonrpc_rows is not None:
        if jsonrpc_rows:
            log(
                "Embedded chapters: using Player.GetChapters (%d chapter(s))"
                % len(jsonrpc_rows)
            )
        else:
            _log_detail("Embedded chapters: Player.GetChapters returned no chapters")
        return jsonrpc_rows

    path = _playing_path(segment_player, video_path)
    if not path:
        _log_detail("Embedded chapters: no playing path for file fallbacks")
        return []

    vfs_rows = parse_matroska_chapters_via_vfs(path)
    if vfs_rows:
        log("Embedded chapters: using Matroska header via VFS (%d chapter(s))" % len(vfs_rows))
        return vfs_rows

    extract_rows = _rows_from_mkvextract(path)
    if extract_rows:
        log("Embedded chapters: using mkvextract (%d chapter(s))" % len(extract_rows))
        return extract_rows

    _log_detail("Embedded chapters: no chapters from GetChapters, VFS, or mkvextract")
    return []


def _segments_from_rows(rows, keywords, segment_player):
    if not rows:
        return []
    ordered = sorted(rows, key=lambda item: float(item.get("start") or 0.0))
    total_s = _total_time(segment_player)
    segments = []
    for i, row in enumerate(ordered):
        name = row.get("name") or ""
        label = normalize_label(name)
        start_sec = float(row.get("start") or 0.0)
        end_sec = row.get("end")
        if end_sec is None:
            if i + 1 < len(ordered):
                end_sec = float(ordered[i + 1].get("start") or start_sec)
            elif total_s > start_sec:
                end_sec = total_s
            else:
                end_sec = start_sec + 300.0
        else:
            end_sec = float(end_sec)
        if label not in keywords:
            _log_detail(
                "Embedded chapter '%s' (label='%s') not in keywords — skipping"
                % (name, label)
            )
            continue
        if end_sec > start_sec:
            segments.append(
                SegmentItem(start_sec, end_sec, label, source="embedded")
            )
            log("Embedded chapter matched: '%s' [%s-%s]" % (name, start_sec, end_sec))
    if segments:
        log("Total embedded chapters matched keywords: %d" % len(segments))
    else:
        _log_detail("Embedded chapters: none matched custom_segment_keywords")
    return segments


def parse_embedded_chapters(segment_player=None, player_id=None, video_path=None):
    """Return keyword-matched segments muxed in the current file.

    Prefers ``Player.GetChapters`` (Kodi 22+). On Omega and NFS, falls back to a
    bounded Matroska header read through VFS, then ``mkvextract`` for local files.
    Does not call ``Player.GetProperties`` with ``chapters`` (not a valid property).
    """
    addon = get_addon()
    if not addon:
        return []
    keywords_raw = addon_get_setting_text(addon, "custom_segment_keywords", "")
    keywords = set(normalize_label(k) for k in keywords_raw.split(",") if k.strip())
    if not keywords:
        _log_detail("Embedded chapters: no custom_segment_keywords configured")
        return []
    try:
        rows = _load_embedded_chapter_rows(segment_player, player_id, video_path)
        return _segments_from_rows(rows, keywords, segment_player)
    except Exception as exc:
        log("Embedded chapters parse failed: %s" % exc)
        return []
