# -*- coding: utf-8 -*-
"""The "Current video" window: what Skippy knows about the video playing now.

Where the segments came from, what each one will do and why (the segment type, a
per-title choice, binge mode, skipping turned off), the binge run, and the last error
the playback loop hit. Runs as a RunScript, so it reads what the service mirrored to
the Home window (``playback_segment_cache`` and ``service_diagnostics``).
"""

from __future__ import annotations

import os

from settings_utils import (
    format_segment_label_for_ui,
    get_addon,
    get_localized,
    log,
)
from time_format import format_clock

ORIGIN_IDS = {"local": 48020, "remote": 48021, "embedded": 48022, "none": 48023}
ORIGIN_DEFAULTS = {
    "local": "Sidecar file",
    "remote": "Online",
    "embedded": "Embedded chapters",
    "none": "None found",
}
SOURCE_NAMES = {
    "xml": "chapters.xml",
    "edl": ".edl",
    "theintrodb": "TheIntroDB.org",
    "introdb": "IntroDB.app",
}
MODE_IDS = {"auto": (48026, "Skip automatically"), "ask": (48027, "Ask"), "never": (48028, "Never skip")}
REASON_IDS = {
    "binge": (48029, "%s (binge mode)"),
    "title": (48030, "%s (saved for this title)"),
    "off": (48034, "%s (skipping is off for this kind of video)"),
}


def _t(addon, string_id, default, *args):
    return get_localized(addon, string_id, default, *args)


def source_name(source, addon=None) -> str:
    key = (source or "").strip().lower()
    if key == "embedded":
        return _t(addon, 48022, "Embedded chapters")
    return SOURCE_NAMES.get(key, source or "?")


def effective_mode(addon, label, playback_type, override_key=None, binge_position=0):
    """``(mode, reason)`` the way the playback loop decides it; reason is None, binge, title or off."""
    from binge_mode import binge_behavior, binge_settings, segment_type_id
    from settings_utils import addon_get_bool
    from segment_types import get_user_skip_mode

    mode = get_user_skip_mode(label)
    reason = None
    if mode == "ask" and override_key:
        try:
            from per_show_overrides import MODE_AUTO, lookup_override, per_show_override_enabled

            if per_show_override_enabled(addon) and lookup_override(override_key, label) == MODE_AUTO:
                mode, reason = "auto", "title"
        except Exception:
            pass
    if playback_type == "episode":
        enabled, skip_recap, _gap = binge_settings(addon)
        new, why = binge_behavior(segment_type_id(label), mode, binge_position, enabled, skip_recap)
        if why:
            mode, reason = new, "binge"
    skip_key = {"episode": "enable_skip_episodes", "movie": "enable_skip_movies"}.get(playback_type)
    if mode != "never" and skip_key and not addon_get_bool(addon, skip_key, True):
        mode, reason = "never", "off"
    return mode, reason


def mode_text(addon, mode, reason) -> str:
    string_id, default = MODE_IDS.get(mode, MODE_IDS["never"])
    text = _t(addon, string_id, default)
    if reason in REASON_IDS:
        rid, rdefault = REASON_IDS[reason]
        text = _t(addon, rid, rdefault, text)
    return text


def _override_key_for(path):
    """Per-title key the way playback finds it (library metadata only)."""
    try:
        from per_show_overrides import override_key_for_identity
        from remote_segments import get_enriched_item_for_path, library_title_identity

        return override_key_for_identity(library_title_identity(get_enriched_item_for_path(path)))
    except Exception:
        return None


def build_diagnostics_rows(addon, playing_path, diag, parse, override_key=None):
    """``(rows, footnote)``. ``diag``: service_diagnostics object; ``parse``: parse cache snapshot."""
    from skippy_panel_ui import PanelRow

    diag = diag or {}
    rows = []
    if not playing_path:
        rows.append(PanelRow(_t(addon, 48012, "Nothing is playing.")))
        rows.extend(_error_rows(addon, diag))
        return rows, ""

    playback_type = diag.get("playback_type") if diag.get("video") == playing_path else ""
    rows.append(PanelRow(_t(addon, 48013, "File"), os.path.basename(playing_path.rstrip("/\\"))))
    title = diag.get("title") if diag.get("video") == playing_path else ""
    if title:
        name = _t(addon, 48014, "Show") if playback_type == "episode" else _t(addon, 48015, "Film")
        rows.append(PanelRow(name, title))
    position = 0
    if playback_type == "episode":
        from binge_mode import binge_settings

        position = int(diag.get("binge_position") or 0)
        enabled = binge_settings(addon)[0]
        value = (
            _t(addon, 48017, "Episode %d", position)
            if enabled and position > 0
            else _t(addon, 48018, "Off")
        )
        rows.append(PanelRow(_t(addon, 48016, "Binge run"), value))

    rows.append(PanelRow(_t(addon, 48024, "Segments"), header=True))
    if not parse or parse.get("path") != playing_path:
        rows.append(PanelRow(_t(addon, 48033, "Segments are still being read. Try again in a moment.")))
    else:
        origin = (parse.get("segment_origin") or "none").lower()
        segments = list(parse.get("segments") or [])
        sources = sorted({source_name(getattr(s, "source", ""), addon) for s in segments})
        origin_text = _t(addon, ORIGIN_IDS.get(origin, 48023), ORIGIN_DEFAULTS.get(origin, "None found"))
        if sources:
            origin_text = "%s (%s)" % (origin_text, ", ".join(sources))
        rows.append(PanelRow(_t(addon, 48019, "Segments from"), origin_text))
        if not segments:
            rows.append(PanelRow(_t(addon, 48025, "No segments for this video.")))
        kind = parse.get("playback_type") or playback_type
        for seg in sorted(segments, key=lambda s: (s.start_seconds, s.end_seconds)):
            label = getattr(seg, "segment_type_label", "") or "segment"
            mode, reason = effective_mode(addon, label, kind, override_key, position)
            rows.append(
                PanelRow(
                    "%s  %s–%s"
                    % (
                        format_segment_label_for_ui(label),
                        format_clock(seg.start_seconds),
                        format_clock(seg.end_seconds),
                    ),
                    mode_text(addon, mode, reason),
                )
            )
    rows.extend(_error_rows(addon, diag))
    return rows, ""


def _error_rows(addon, diag):
    from skippy_panel_ui import PanelRow

    rows = [PanelRow(_t(addon, 48031, "Last error"), header=True)]
    error = (diag or {}).get("last_error")
    if isinstance(error, dict) and error.get("text"):
        rows.append(PanelRow(str(error.get("at") or ""), str(error.get("where") or "")))
        rows.append(PanelRow(str(error["text"])))
    else:
        rows.append(PanelRow(_t(addon, 48032, "None since Kodi started")))
    return rows


def _playing_path():
    try:
        import xbmc

        player = xbmc.Player()
        if player.isPlayingVideo():
            return player.getPlayingFile() or ""
    except Exception:
        pass
    return ""


def show_diagnostics_modal() -> None:
    from playback_segment_cache import get_parse_cache_snapshot
    from service_diagnostics import read_diagnostics
    from skippy_panel_ui import show_panel_rows

    addon = get_addon()
    heading = _t(addon, 48010, "Current video")
    path = _playing_path()
    try:
        rows, footnote = build_diagnostics_rows(
            addon,
            path,
            read_diagnostics(),
            get_parse_cache_snapshot(),
            override_key=_override_key_for(path) if path else None,
        )
        show_panel_rows(heading, rows, _t(addon, 40001, "Close"), footnote=footnote)
    except Exception as exc:
        log("⚠ Current video window failed: %s" % exc)
