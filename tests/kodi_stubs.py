# -*- coding: utf-8 -*-
"""Minimal Kodi API stubs for offline import/syntax tests."""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock


def install_kodi_stubs(*, addon=None):
    """
    Register stub ``xbmc`` / ``xbmcgui`` / ``xbmcvfs`` / ``xbmcaddon`` modules.

    Safe to call multiple times; refreshes stub modules in ``sys.modules``.
    """
    if addon is None:
        addon = MagicMock()
        addon.getAddonInfo = lambda _key: "w:/fake/addon"
        addon.getSetting = lambda _key: "false"
        addon.getLocalizedString = lambda _key: ""

    xbmc = types.ModuleType("xbmc")
    xbmc.getCondVisibility = lambda _cond: False
    xbmc.executeJSONRPC = lambda _payload: '{"jsonrpc":"2.0","id":1,"result":[]}'
    xbmc.sleep = lambda _ms: None
    xbmc.LOGINFO = 1
    xbmc.LOGWARNING = 2
    xbmc.LOGERROR = 3
    xbmc.log = lambda _msg, _level=1: None

    class _Monitor:
        def __init__(self):
            pass

        def abortRequested(self):
            return True

        def waitForAbort(self, _seconds):
            return True

    class _Player:
        def isPlayingVideo(self):
            return False

        def isPlaying(self):
            return False

        def getPlayingFile(self):
            return ""

        def getTime(self):
            return 0.0

        def getTotalTime(self):
            return 0.0

    xbmc.Monitor = _Monitor
    xbmc.Player = _Player
    sys.modules["xbmc"] = xbmc

    xbmcvfs = types.ModuleType("xbmcvfs")
    xbmcvfs.exists = lambda _path: False
    xbmcvfs.translatePath = lambda path: path
    xbmcvfs.copy = lambda _src, _dst: True
    xbmcvfs.delete = lambda _path: True
    xbmcvfs.rename = lambda _src, _dst: True
    xbmcvfs.listdir = lambda _path: ([], [])

    def _file_stub(_path):
        return types.SimpleNamespace(
            read=lambda: b"",
            write=lambda _data: None,
            close=lambda: None,
        )

    xbmcvfs.File = _file_stub
    xbmcvfs.Stat = lambda _path: types.SimpleNamespace(
        st_mtime=lambda: 0,
        st_size=lambda: 0,
    )
    sys.modules["xbmcvfs"] = xbmcvfs

    xbmcgui = types.ModuleType("xbmcgui")
    xbmcgui.Window = type(
        "Window",
        (),
        {
            "__init__": lambda self, *_a, **_k: None,
            "getProperty": lambda self, _prop: "",
            "clearProperty": lambda self, _prop: None,
            "setProperty": lambda self, _prop, _val: None,
        },
    )
    xbmcgui.WindowXMLDialog = type("WindowXMLDialog", (), {})
    xbmcgui.WindowDialog = type("WindowDialog", (), {})
    xbmcgui.Dialog = type(
        "Dialog",
        (),
        {
            "notification": lambda *a, **k: None,
            "yesno": lambda *a, **k: False,
            "ok": lambda *a, **k: None,
            "input": lambda *a, **k: "",
            "select": lambda *a, **k: -1,
        },
    )
    xbmcgui.ListItem = type("ListItem", (), {"setLabel": lambda *a, **k: None})
    sys.modules["xbmcgui"] = xbmcgui

    xbmcaddon = types.ModuleType("xbmcaddon")
    xbmcaddon.Addon = lambda _addon_id: addon
    sys.modules["xbmcaddon"] = xbmcaddon

    return addon


def import_fresh(module_name: str):
    """Import ``module_name`` after removing it from ``sys.modules``."""
    sys.modules.pop(module_name, None)
    import importlib

    return importlib.import_module(module_name)
