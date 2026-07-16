# -*- coding: utf-8 -*-
"""Home-window Skippy.Skipping property for cooperative skin seek-OSD hiding."""

from __future__ import annotations

import time

import xbmc

from segment_editor_utils import get_home_window
from settings_utils import addon_get_bool, log_service_detail

# Home window property name (Window 10000). Skins hide seek OSD while non-empty.
SKIPPY_SKIPPING_PROPERTY = "Skippy.Skipping"

# Keep the property at least this long so skins (often HasPerformedSeek(3))
# do not flash the seek bar the moment we clear.
_SKIPPING_MIN_SECONDS = 5.0
# Match common Estuary-style seek OSD window (seconds).
_SKIPPING_SEEK_INFOBOOL = "Player.HasPerformedSeek(3) | Player.Caching"


def mark_skippy_skipping(monitor, addon=None) -> None:
    """Set Skippy.Skipping immediately before a Skippy-initiated seekTime."""
    if not addon_get_bool(addon, "signal_skipping_for_skins", False):
        return
    monitor.skippy_skipping_since = time.monotonic()
    home = get_home_window(monitor)
    if home is None:
        return
    try:
        home.setProperty(SKIPPY_SKIPPING_PROPERTY, "true")
        log_service_detail(
            "🎯 Set %s=true (skin may hide seek OSD)" % SKIPPY_SKIPPING_PROPERTY,
            tag="playback",
        )
    except Exception as exc:
        log_service_detail(
            "⚠️ Failed to set %s: %s" % (SKIPPY_SKIPPING_PROPERTY, exc),
            tag="playback",
        )


def clear_skippy_skipping(monitor) -> None:
    """Force-clear Skippy.Skipping (stop, new video, abort)."""
    if getattr(monitor, "skippy_skipping_since", None) is None:
        # Still clear a stale Home property if present.
        home = get_home_window(monitor)
        if home is None:
            return
        try:
            if home.getProperty(SKIPPY_SKIPPING_PROPERTY):
                home.clearProperty(SKIPPY_SKIPPING_PROPERTY)
        except Exception:
            pass
        return

    monitor.skippy_skipping_since = None
    home = get_home_window(monitor)
    if home is None:
        return
    try:
        home.clearProperty(SKIPPY_SKIPPING_PROPERTY)
        log_service_detail(
            "🎯 Cleared %s" % SKIPPY_SKIPPING_PROPERTY,
            tag="playback",
        )
    except Exception as exc:
        log_service_detail(
            "⚠️ Failed to clear %s: %s" % (SKIPPY_SKIPPING_PROPERTY, exc),
            tag="playback",
        )


def maybe_clear_skippy_skipping(monitor) -> None:
    """Clear after min duration once seek + caching have settled."""
    since = getattr(monitor, "skippy_skipping_since", None)
    if since is None:
        return
    if time.monotonic() - float(since) < _SKIPPING_MIN_SECONDS:
        return
    try:
        if xbmc.getCondVisibility(_SKIPPING_SEEK_INFOBOOL):
            return
    except Exception:
        # If conditions fail, clear so the property cannot stick forever.
        pass
    clear_skippy_skipping(monitor)


def tick_skippy_skipping_property(monitor, *, playing: bool) -> None:
    """Per-loop maintenance: clear when idle; otherwise settle after seek."""
    if not playing:
        clear_skippy_skipping(monitor)
        return
    maybe_clear_skippy_skipping(monitor)
