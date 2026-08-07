# -*- coding: utf-8 -*-
"""Playback glue for per-title autoskip overrides."""

from __future__ import annotations

from typing import Any

import xbmcgui

from per_show_overrides import (
    MODE_AUTO,
    MODE_DECLINED,
    lookup_override,
    override_key_for_identity,
    per_show_override_enabled,
    save_override,
)
from remote_segments import get_enriched_item_for_path, library_title_identity
from service_player_snapshot import get_player_snapshot, snapshot_matches_path
from settings_utils import (
    format_segment_label_for_ui,
    get_localized,
    log,
    log_service_detail,
    normalize_label,
)
from skippy_editor_modal_skin import sidecar_overwrite_yesno_show


def _log_detail(msg: str) -> None:
    log_service_detail(msg, tag="overrides")


def clear_playback_override_key(monitor) -> None:
    if monitor is not None:
        monitor.per_show_override_identity = None


def playback_override_identity(monitor, video_path):
    """
    ``(key, title)`` for the playing title, resolved once per video.

    Uses library metadata only, so this never blocks playback on an API call.
    """
    cached = getattr(monitor, "per_show_override_identity", None)
    if isinstance(cached, tuple) and len(cached) == 3 and cached[0] == video_path:
        return cached[1], cached[2]

    snapshot = get_player_snapshot(monitor)
    item = snapshot.item if snapshot_matches_path(snapshot, video_path) else None
    if not item:
        item = get_enriched_item_for_path(video_path, snapshot=snapshot)
    identity = library_title_identity(item)
    key = override_key_for_identity(identity)
    title = (identity or {}).get("title") or ""
    if monitor is not None:
        monitor.per_show_override_identity = (video_path, key, title)
    if key:
        _log_detail("per-show override key for %r: %s" % (title, key))
    else:
        _log_detail("per-show override unavailable: no TMDB/IMDb id for this title")
    return key, title


def apply_per_show_override(monitor, addon, video_path, segment_label, behavior):
    """Upgrade ``ask`` to ``auto`` when this title has a saved autoskip override."""
    if behavior != "ask" or not per_show_override_enabled(addon):
        return behavior
    key, _title = playback_override_identity(monitor, video_path)
    if not key:
        return behavior
    if lookup_override(key, segment_label) != MODE_AUTO:
        return behavior
    log(
        "⚡ Per-show override: '%s' set to auto-skip for %s"
        % (normalize_label(segment_label), key)
    )
    return "auto"


def _override_prompt_texts(addon, segment_label, title):
    display_label = format_segment_label_for_ui(
        normalize_label(segment_label) or "segment"
    )
    heading = get_localized(addon, 44000, "Always skip this segment?")
    if title:
        message = get_localized(
            addon,
            44001,
            "Automatically skip %s for %s from now on?",
            display_label,
            title,
        )
    else:
        message = get_localized(
            addon,
            44002,
            "Automatically skip %s for this title from now on?",
            display_label,
        )
    yes_label = get_localized(addon, 35018, "Yes")
    no_label = get_localized(addon, 44003, "Not now")
    return heading, message, yes_label, no_label


def maybe_prompt_per_show_override(ctx: Any, addon, segment, video_path) -> None:
    """
    After a confirmed skip, offer to auto-skip this segment type for this title.

    Asked at most once per title + segment type: a decline is remembered too.
    """
    monitor = ctx.monitor
    if not per_show_override_enabled(addon):
        return
    key, title = playback_override_identity(monitor, video_path)
    if not key:
        return
    segment_label = getattr(segment, "segment_type_label", "") or ""
    if lookup_override(key, segment_label) is not None:
        return

    try:
        if not ctx.player.isPlayingVideo():
            _log_detail("override prompt suppressed: video not playing")
            return
    except RuntimeError:
        _log_detail("override prompt suppressed: player state unavailable")
        return

    heading, message, yes_label, no_label = _override_prompt_texts(
        addon, segment_label, title
    )
    monitor.skip_dialog_modal_active = True
    try:
        try:
            confirmed = sidecar_overwrite_yesno_show(
                heading, message, yes_label, no_label
            )
        except Exception as exc:
            log("⚠ Per-show override prompt failed (%s) — using stock yesno" % exc)
            try:
                confirmed = xbmcgui.Dialog().yesno(
                    heading, message, nolabel=no_label, yeslabel=yes_label
                )
            except Exception:
                return
    finally:
        monitor.skip_dialog_modal_active = False

    save_override(
        key, segment_label, MODE_AUTO if confirmed else MODE_DECLINED, title=title
    )
    if confirmed:
        try:
            xbmcgui.Dialog().notification(
                heading=get_localized(addon, 43000, "Skippy"),
                message=get_localized(
                    addon, 44004, "Auto-skip saved for this title"
                ),
                icon=ctx.icon_path,
                time=2500,
                sound=False,
            )
        except Exception as exc:
            _log_detail("override saved toast failed: %s" % exc)
