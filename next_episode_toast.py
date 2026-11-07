# -*- coding: utf-8 -*-
"""Native toast prompt for the next episode: a Kodi toast plus an invisible key catcher."""

from __future__ import annotations

import threading
import types

import xbmcgui

from next_episode_lookup import episode_label, is_movie_item
from next_episode_state import END_CLOSE, END_PLAY, TIMED_OUT
from skip_dialog_native import (
    SkipToastKeys,
    _TOAST_MIN_MS,
    _dismiss_toast,
    _playhead,
    _toast_keepalive,
)
from settings_utils import get_localized, log


def build_toast_texts(addon, next_episode, still_watching=False):
    """Return ``(heading, body)``; the body is never shortened (Kodi scrolls long text)."""
    if still_watching:
        heading = get_localized(addon, 47070, "Still watching?")
        press = get_localized(addon, 47073, "Press OK to continue")
    else:
        if is_movie_item(next_episode):
            heading = get_localized(addon, 47146, "Play next movie?")
        else:
            heading = get_localized(addon, 47020, "Play next episode?")
        press = get_localized(addon, 47021, "Press OK to play")
    label = episode_label(next_episode)
    body = "%s \u00b7 %s" % (label, press) if label else press
    return heading, body


def show_next_episode_toast(
    addon,
    player,
    next_episode,
    window_start,
    total,
    still_watching=False,
    timed=False,
    end_action=END_CLOSE,
):
    """
    Show the toast until its countdown ends and wait for OK / Back.

    ``total`` is where the toast ends: the end of the file, or sooner when it is ``timed``.

    Returns True (OK: play now), False (Back: dismissed), ``TIMED_OUT`` (a timed toast, or
    one whose end action is Play, ran out) or None (the prompt closed by itself: playback
    stopped, the file ended, or the playhead left the window).
    """
    heading, body = build_toast_texts(addon, next_episode, still_watching)
    icon = addon.getAddonInfo("icon") or ""

    def post(ms):
        try:
            xbmcgui.Dialog().notification(heading, body, icon, int(ms), False)
        except Exception as exc:
            log("\u26a0\ufe0f Next episode toast failed: %s" % exc)

    head = _playhead(player, window_start)
    post(max(_TOAST_MIN_MS, int((float(total) - head) * 1000)))
    dlg = SkipToastKeys("SkipToastKeys.xml", addon.getAddonInfo("path"), "default")
    stop = threading.Event()
    window = types.SimpleNamespace(
        start_seconds=float(window_start), end_seconds=float(total)
    )
    runs_out = (bool(timed) or end_action == END_PLAY) and not still_watching

    def close():
        # The keep-alive calls this when playback left the stretch or reached its end; only
        # reaching the end is a timeout.
        reached_end = False
        if runs_out:
            try:
                reached_end = bool(player.isPlaying()) and (
                    _playhead(player, window_start) >= float(total) - 1.0
                )
            except Exception:
                reached_end = False
        if reached_end:
            dlg._finish(TIMED_OUT)
        else:
            dlg.close()

    threading.Thread(
        target=_toast_keepalive,
        args=(player, window, post, close, stop),
        daemon=True,
    ).start()
    try:
        dlg.doModal()
    finally:
        stop.set()
        _dismiss_toast()
    result = dlg.result
    del dlg
    return result
