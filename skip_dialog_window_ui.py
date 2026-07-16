# -*- coding: utf-8 -*-
"""Skip dialog colour helpers.

A former WindowDialog control builder lived here; it was unused (skip UI is
WindowXML only). Kept as a small module so ``skipdialog.py`` and tests can
share ARGB → Kodi hex conversion.
"""

from __future__ import annotations


def _argb_to_kodi(argb):
    """Convert AARRGGBB / RRGGBB to Kodi ``0xAARRGGBB`` for ``setLabel``."""
    s = (argb or "FF6E6E6E").strip().upper()
    if len(s) == 8:
        return f"0x{s}"
    if len(s) == 6:
        return f"0xFF{s}"
    return "0xFF6E6E6E"
