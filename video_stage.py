# -*- coding: utf-8 -*-
"""The playing video, small, under a dialog: Takeover + video (Up Next) and the segment editor's small video.

Kodi draws a video in a ``videowindow`` control at that control's size only while its full-screen video
window is not the active one. Over full-screen video, a dialog's video window only shows the piece of the
full picture that lies behind it (tried in 8.31.0). So a plain window (a ``WindowXML``, not a dialog) is
opened first: it has the video window at the same place as the dialog's, and while it is the active window
the video is drawn small. The dialog then opens over it. When the dialog closes, the window closes too and a
video that still plays gets the whole screen back.

A modal dialog keeps Kodi from activating another window, so the window must open before the dialog does
(the segment editor reopens itself to switch).
"""

from __future__ import annotations

import xbmc
import xbmcgui

from settings_utils import log

FULLSCREEN_VIDEO = 12005
FANART_PROPERTY = "skippy_stage_fanart"  # on the Home window: the picture the stage shows (else it is black)


def open_stage(addon, xml_name, fanart=""):
    """Open the plain window ``xml_name`` (a file of Skippy's skin folder) without waiting on it, while a video
    plays. Returns the window, or None when nothing plays or it could not be opened."""
    try:
        if not xbmc.Player().isPlayingVideo():
            return None
        xbmcgui.Window(10000).setProperty(FANART_PROPERTY, fanart or "")
        stage = xbmcgui.WindowXML(xml_name, addon.getAddonInfo("path"), "default", "1080i")
        stage.show()
        for _ in range(40):  # until Kodi has it as the active window, so the dialog comes over it
            if xbmcgui.getCurrentWindowId() != FULLSCREEN_VIDEO:
                break
            xbmc.sleep(25)
        log("Video stage %s open (window %s)" % (xml_name, xbmcgui.getCurrentWindowId()))
        return stage
    except Exception as exc:
        log("Video stage %s could not be opened: %s" % (xml_name, exc))
        return None


def close_stage(stage) -> None:
    """Close the plain window and give a video that still plays the whole screen back."""
    if stage is None:
        return
    try:
        stage.close()
    except Exception:
        pass
    try:
        xbmcgui.Window(10000).clearProperty(FANART_PROPERTY)
    except Exception:
        pass
    del stage
    try:
        if xbmc.Player().isPlayingVideo() and xbmcgui.getCurrentWindowId() != FULLSCREEN_VIDEO:
            xbmc.executebuiltin("ActivateWindow(fullscreenvideo)")
    except Exception:
        pass
