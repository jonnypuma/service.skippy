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


def file_stamp(path: str | None):
    """``(mtime_ns, size)`` of a file, or None when it is missing.

    The service and the settings/manage windows run as separate scripts, each with
    its own module state. A cache that only the writer invalidates goes stale as
    soon as another script changes the file; comparing stamps catches that.
    """
    if not path:
        return None
    try:
        info = os.stat(path)
    except OSError:
        return None
    return (info.st_mtime_ns, info.st_size)


def read_json(path: str | None, default=None):
    """Parse a JSON file; returns ``default`` for missing or unreadable files."""
    if not path or not os.path.isfile(path):
        return default
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, TypeError, ValueError):
        return default


def _fsync_directory(directory: str) -> None:
    """Best effort: persist the rename itself (POSIX only; ignored elsewhere)."""
    if not directory:
        return
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


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
            handle.flush()
            # Without this a power cut right after the replace can leave an empty
            # file on devices that lose power abruptly (set-top boxes, SD cards).
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
        _fsync_directory(os.path.dirname(path))
        return True
    except (OSError, TypeError, ValueError):
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        return False
