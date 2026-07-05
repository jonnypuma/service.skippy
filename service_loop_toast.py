# -*- coding: utf-8 -*-
"""Missing-segments toast logic for the service monitor loop."""

from __future__ import annotations

import time
from typing import Any

import xbmc
import xbmcgui

from settings_utils import addon_get_bool, get_addon, log


def try_show_online_segments_applied_toast(
    ctx: Any,
    *,
    video: str,
    previous_count: int,
    new_count: int,
) -> None:
    """One-shot toast when deferred online segments change the playback timeline."""
    monitor = ctx.monitor
    if not video or new_count <= 0:
        return
    if previous_count > 0 and new_count <= previous_count:
        return
    if getattr(monitor, "online_segments_toast_shown_for_path", None) == video:
        return
    addon = get_addon()
    if not addon_get_bool(addon, "toast_online_segments_applied", True):
        return
    try:
        xbmcgui.Dialog().notification(
            heading="Skippy",
            message="Online segments loaded",
            icon=ctx.icon_path,
            time=3000,
            sound=False,
        )
        monitor.online_segments_toast_shown_for_path = video
        log("🔔 Online segments applied toast shown for %s" % video)
    except Exception as exc:
        log("❌ Failed to show online segments applied toast: %s" % exc)


def try_show_missing_segments_toast(
    ctx: Any,
    *,
    video: str,
    playback_type: str,
    toast_movies: bool,
    toast_episodes: bool,
    current_time: float,
) -> None:
    monitor = ctx.monitor
    if not monitor.playback_ready:
        return
    if monitor.shown_missing_file_toast:
        return
    if time.time() - monitor.playback_ready_time < 2:
        return
    if monitor.segment_file_found:
        return
    if ctx.both_segment_sources_disabled_for_playback(playback_type):
        return

    try:
        toast_is_playing = ctx.player.isPlayingVideo()
        toast_is_paused = xbmc.getCondVisibility("Player.Paused")
    except RuntimeError:
        log("🔕 Missing segments toast suppressed — player state unavailable")
        return

    if toast_is_paused or not toast_is_playing:
        log(
            "🔕 Missing segments toast suppressed — playback is paused or not playing "
            "(is_playing=%s, is_paused=%s)"
            % (toast_is_playing, toast_is_paused)
        )
        return

    log("⚠ [TOAST BLOCK] Entered toast logic block")
    try:
        toast_enabled = (playback_type == "movie" and toast_movies) or (
            playback_type == "episode" and toast_episodes
        )
        if not toast_enabled:
            log("✅ [TOAST BLOCK] Toast suppressed — toast toggle disabled for this type")
            monitor.shown_missing_file_toast = True
            return

        cooldown = 6
        now = time.time()
        if now - monitor.last_toast_time < cooldown:
            log(
                "⏳ [TOAST BLOCK] Suppressed — cooldown active (%ds since last toast)"
                % int(now - monitor.last_toast_time)
            )
            return

        msg_type = "episode" if playback_type == "episode" else "movie"
        log("🔔 Attempting to show toast notification for missing segments (%s)" % msg_type)

        try:
            final_toast_is_playing = ctx.player.isPlayingVideo()
            final_toast_is_paused = xbmc.getCondVisibility("Player.Paused")
        except RuntimeError:
            log("🔕 Missing segments toast suppressed — player state unavailable right before showing")
            return

        if final_toast_is_paused or not final_toast_is_playing:
            log(
                "🔕 Missing segments toast suppressed — playback paused right before showing "
                "(is_playing=%s, is_paused=%s)"
                % (final_toast_is_playing, final_toast_is_paused)
            )
            return

        try:
            toast_msg = ctx.missing_segments_toast_message(playback_type, video)
            xbmcgui.Dialog().notification(
                heading="Skippy",
                message=toast_msg,
                icon=ctx.icon_path,
                time=3000,
                sound=False,
            )
            monitor.last_toast_time = now
            monitor.shown_missing_file_toast = True
            log("✅ Toast displayed for %s" % msg_type)
        except RuntimeError as e:
            log("❌ Failed to display missing segments toast notification: %s" % e)
        except (OSError, ValueError, TypeError, AttributeError) as e:
            log(
                "❌ Failed to display missing segments toast notification (%s): %s"
                % (type(e).__name__, e)
            )
        except Exception as e:
            log(
                "❌ Failed to display missing segments toast notification (%s): %s"
                % (type(e).__name__, e)
            )
    except Exception as e:
        log(
            "❌ [TOAST BLOCK] missing segments toast failed (%s): %s"
            % (type(e).__name__, e)
        )
        monitor.shown_missing_file_toast = True
