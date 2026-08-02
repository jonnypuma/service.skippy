# -*- coding: utf-8 -*-
"""Small JSON helpers for files kept in the add-on profile (addon_data)."""

from __future__ import annotations

import json
import os

import xbmcaddon
import xbmcvfs

ADDON_ID = "service.skippy"


def profile_dir() -> str | None:
    """Translated ``addon_data`` directory for Skippy, or None when unavailable."""
    try:
        profile = xbmcaddon.Addon(ADDON_ID).getAddonInfo("profile")
    except Exception:
        return None
    if not profile:
        return None
    try:
        return xbmcvfs.translatePath(profile)
    except Exception:
        return profile


def profile_path(*parts: str) -> str | None:
    base = profile_dir()
    if not base:
        return None
    return os.path.join(base, *parts)


def ensure_parent_dir(path: str) -> bool:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return True
    except OSError:
        return False


def read_json(path: str | None, default=None):
    """Parse a JSON file; returns ``default`` for missing or unreadable files."""
    if not path or not os.path.isfile(path):
        return default
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, TypeError, ValueError):
        return default


def write_json(path: str | None, data) -> bool:
    """Write JSON via a temp file + replace so a crash cannot truncate the original."""
    if not path:
        return False
    if not ensure_parent_dir(path):
        return False
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
        os.replace(tmp_path, path)
        return True
    except OSError:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        return False
