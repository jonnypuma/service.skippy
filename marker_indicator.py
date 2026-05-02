# -*- coding: utf-8 -*-
"""On-screen pending segment marker indicator (top-left during playback).

Skippy stores text in Window(10000) property ``skippy_marker_indicator``.
The service draws a small chip on Kodi's fullscreen video window (no skin change
required). Controls are parented to ``xbmcgui.Window(12005/10800)`` instead of a
``WindowDialog`` so input stays on the fullscreen context and marker keymaps keep
working for the second mark.
"""
import os

import xbmcaddon
import xbmcgui
import xbmcvfs

ADDON_ID = "service.skippy"

# Fullscreen playback window ids (file / PVR live TV).
_WINDOW_FULLSCREEN_VIDEO = 12005
_WINDOW_FULLSCREEN_LIVETV = 10800
_FULLSCREEN_IDS = (_WINDOW_FULLSCREEN_VIDEO, _WINDOW_FULLSCREEN_LIVETV)

_attached_window_id = None
_bg_control = None
_label_control = None


def _media_texture(filename):
    try:
        addon = xbmcaddon.Addon(ADDON_ID)
        path = os.path.join(
            addon.getAddonInfo("path"),
            "resources",
            "skins",
            "default",
            "media",
            filename,
        )
        if xbmcvfs.exists(path):
            return path
    except Exception:
        pass
    return filename


def _detach():
    """Remove chip controls from whichever fullscreen window they were attached to."""
    global _attached_window_id, _bg_control, _label_control
    wid = _attached_window_id
    if wid is None:
        return
    try:
        win = xbmcgui.Window(wid)
        for ctrl in (_label_control, _bg_control):
            if ctrl is not None:
                try:
                    win.removeControl(ctrl)
                except Exception:
                    pass
    except Exception:
        pass
    _attached_window_id = None
    _bg_control = None
    _label_control = None


def _layout_chip(window):
    """Return (x, y, chip_w, chip_h, label_x, label_y, label_w, label_h) in window coords."""
    w, h = window.getWidth(), window.getHeight()
    margin_x, margin_y = 24, 20
    chip_h = 72
    chip_w = min(680, max(120, w - 2 * margin_x))
    x0 = margin_x
    y0 = margin_y
    pad_x = 16
    label_x = x0 + pad_x
    label_y = y0 + 12
    label_w = chip_w - 2 * pad_x
    label_h = 48
    return x0, y0, chip_w, chip_h, label_x, label_y, label_w, label_h


def _attach_chip(window_id, text):
    """Create controls and add them to the given fullscreen window."""
    global _attached_window_id, _bg_control, _label_control

    win = xbmcgui.Window(window_id)
    tex = _media_texture("white.png")
    x0, y0, cw, ch, lx, ly, lw, lh = _layout_chip(win)
    _bg_control = xbmcgui.ControlImage(x0, y0, cw, ch, tex)
    _bg_control.setColorDiffuse("E0101010")
    _label_control = xbmcgui.ControlLabel(lx, ly, lw, lh, text, "font30", "FFFFFFFF")
    win.addControl(_bg_control)
    win.addControl(_label_control)
    _attached_window_id = window_id


def sync_marker_pending_indicator(playback_active):
    """Show or hide the overlay from ``skippy_marker_indicator`` when video is active."""
    if not playback_active:
        _detach()
        return

    try:
        text = (xbmcgui.Window(10000).getProperty("skippy_marker_indicator") or "").strip()
    except Exception:
        text = ""

    if not text:
        _detach()
        return

    try:
        try:
            current_id = xbmcgui.getCurrentWindowId()
        except Exception:
            current_id = None

        if current_id not in _FULLSCREEN_IDS:
            _detach()
            return

        if _attached_window_id is not None and _attached_window_id != current_id:
            _detach()

        if _attached_window_id is None:
            _attach_chip(current_id, text)
        else:
            try:
                _label_control.setLabel(text)
            except Exception:
                _detach()
                _attach_chip(current_id, text)
    except Exception:
        _detach()
