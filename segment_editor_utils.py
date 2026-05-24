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


# Window(10000) IPC: RunScript cannot share Python globals; second editor hotkey sets this
# and SegmentEditorDialog's time thread calls close() (same pattern as label updates).
EDITOR_TOGGLE_CLOSE_REQUESTED = "skippy_editor_toggle_close_requested"
# Suppress stacked RunScript opens when modal flag is not set yet (race window).
EDITOR_LAUNCH_DEBOUNCE_TS = "skippy_editor_launch_debounce_ts"
EDITOR_LAUNCH_DEBOUNCE_SECONDS = 1.2
