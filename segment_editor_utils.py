# -*- coding: utf-8 -*-
"""Shared helpers for Skippy's integrated segment editor."""
import unicodedata

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

ADDON_ID = "service.skippy"
LOG_PREFIX = f"[{ADDON_ID} - SegmentEditor]"

_addon = None
_verbose_cached = None


def get_addon():
    global _addon
    if _addon is None:
        _addon = xbmcaddon.Addon(ADDON_ID)
    return _addon


def refresh_addon():
    global _addon
    _addon = None


def _read_verbose_setting():
    try:
        return get_addon().getSettingBool("enable_verbose_logging")
    except Exception:
        return False


def refresh_verbose_setting():
    global _verbose_cached
    _verbose_cached = _read_verbose_setting()
    return _verbose_cached


def log(msg):
    global _verbose_cached
    if _verbose_cached is None:
        _verbose_cached = _read_verbose_setting()
    if _verbose_cached:
        safe = (
            unicodedata.normalize("NFKD", str(msg))
            .encode("ascii", "ignore")
            .decode("ascii")
        )
        xbmc.log(f"{LOG_PREFIX} {safe}", xbmc.LOGINFO)


def log_always(msg):
    safe = (
        unicodedata.normalize("NFKD", str(msg))
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    xbmc.log(f"{LOG_PREFIX} {safe}", xbmc.LOGINFO)


def log_error(msg):
    safe = (
        unicodedata.normalize("NFKD", str(msg))
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    xbmc.log(f"{LOG_PREFIX} {safe}", xbmc.LOGERROR)


def notify_open_editor():
    from segment_editor_session import open_segment_editor as _open

    try:
        return _open()
    except Exception as err:
        log_error(f"Failed to open editor: {err}")
        import traceback

        log_error(traceback.format_exc())
        return False


def get_video_file():
    try:
        player = xbmc.Player()
        if not (
            player.isPlayingVideo() or xbmc.getCondVisibility("Player.HasVideo")
        ):
            return None
        path = player.getPlayingFile()
    except RuntimeError:
        return None

    if xbmcvfs.exists(path):
        return path
    return None


def set_editor_modal_open(is_open):
    try:
        window = xbmcgui.Window(10000)
        if is_open:
            window.setProperty("skippy_editor_modal_open", "true")
        else:
            window.clearProperty("skippy_editor_modal_open")
    except Exception:
        pass


def _truthy_window_prop(value):
    s = (value or "").strip().lower()
    return s in ("1", "true", "yes", "on")


# Set for the whole open_segment_editor() try/finally (covers RunScript timing vs onInit).
EDITOR_SESSION_MODAL_PROP = "skippy_editor_session_modal"


def set_editor_session_modal(is_open):
    try:
        window = xbmcgui.Window(10000)
        if is_open:
            window.setProperty(EDITOR_SESSION_MODAL_PROP, "true")
        else:
            window.clearProperty(EDITOR_SESSION_MODAL_PROP)
    except Exception:
        pass


def get_home_window(monitor=None):
    """Return Kodi home window (10000), cached on monitor when provided."""
    if monitor is not None:
        cached = getattr(monitor, "_home_window", None)
        if cached is not None:
            return cached
    try:
        win = xbmcgui.Window(10000)
    except Exception:
        return None
    if monitor is not None:
        monitor._home_window = win
    return win


def _window_home(win):
    if win is not None:
        return win
    return get_home_window()


def segment_editor_modal_is_open(win=None):
    """True when the segment editor session or dialog has marked the home window."""
    wh = _window_home(win)
    if wh is None:
        return False
    try:
        if _truthy_window_prop(wh.getProperty("skippy_editor_modal_open")):
            return True
        if _truthy_window_prop(wh.getProperty(EDITOR_SESSION_MODAL_PROP)):
            return True
    except Exception:
        pass
    return False


MARKER_SECOND_PRESS_FLOW_PROP = "skippy_marker_second_press_flow"


def marker_flow_blocks_editor_launch(win=None):
    """True while marker UX is active — pending first press, picker modal, or second-press save flow."""
    wh = _window_home(win)
    if wh is None:
        return False
    try:
        # Wide truthy parsing for marker session props (Omega uses 1/true/yes/on).
        if _truthy_window_prop(wh.getProperty(MARKER_SECOND_PRESS_FLOW_PROP)):
            return True
        if (wh.getProperty("skippy_marker_start") or "").strip():
            return True
        if _truthy_window_prop(wh.getProperty("skippy_marker_modal_open")):
            return True
    except Exception:
        return False
    return False


def set_marker_second_press_flow_active(is_active, win=None):
    """True while segment marker is in second-press save flow (editor-launch guard timing)."""
    wh = _window_home(win)
    if wh is None:
        return
    try:
        if is_active:
            wh.setProperty(MARKER_SECOND_PRESS_FLOW_PROP, "true")
        else:
            wh.clearProperty(MARKER_SECOND_PRESS_FLOW_PROP)
    except Exception:
        pass


# Window(10000) IPC: RunScript cannot share Python globals; second editor hotkey sets this
# and SegmentEditorDialog's time thread calls close() (same pattern as label updates).
EDITOR_TOGGLE_CLOSE_REQUESTED = "skippy_editor_toggle_close_requested"
# Suppress stacked RunScript opens when modal flag is not set yet (race window).
EDITOR_LAUNCH_DEBOUNCE_TS = "skippy_editor_launch_debounce_ts"
EDITOR_LAUNCH_DEBOUNCE_SECONDS = 1.2
