# -*- coding: utf-8 -*-
"""Which look of the drawn dialogs goes with what the skin is showing (Follow the skin style).

Aeon Fuse says its theme and style in skin settings: the Fused Glass theme (``aeon.fglass``, on top
of Aeon Glass, ``aeon.vglass``) and, inside it, the Skin style (``aeon.fgmenu``: empty for Dark,
``glass`` for Clear, ``frost``, ``system`` for Fused Glass style). Another skin has no look to follow.
"""

from __future__ import annotations

SKIN_ID = "skin.aeon.fuse"
# Skin style of the Fused Glass theme -> look
FUSED = {"": "fgd", "dark": "fgd", "glass": "fgc", "clear": "fgc", "frost": "fgf", "system": "fgs"}


def look_for(skin_dir, has_setting, get_string):
    """The look for a skin, from ``has_setting(name)`` and ``get_string(name)``; None when the skin is not
    one whose style can be followed."""
    if str(skin_dir or "").strip().lower() != SKIN_ID:
        return None
    if has_setting("aeon.fglass"):
        return FUSED.get(str(get_string("aeon.fgmenu") or "").strip().lower(), "fgd")
    if has_setting("aeon.vglass"):
        return "agl"
    return "aeo"


def current():
    """The look of the skin Kodi is showing now, or None."""
    try:
        import xbmc

        return look_for(
            xbmc.getSkinDir(),
            lambda name: bool(xbmc.getCondVisibility("Skin.HasSetting(%s)" % name)),
            lambda name: xbmc.getInfoLabel("Skin.String(%s)" % name),
        )
    except Exception:
        return None
