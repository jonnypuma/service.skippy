# -*- coding: utf-8 -*-
"""Small JSON helpers for files kept in the add-on profile (addon_data)."""

from __future__ import annotations

import json
import os
import shutil

import xbmc
import xbmcaddon
import xbmcvfs

ADDON_ID = "service.skippy"

# Copy of the last good file, kept by files that hold the user's own work
# (segment types, saved presets, source choices).
BACKUP_SUFFIX = ".bak"
# A file that no longer parses is moved here instead of being overwritten.
CORRUPT_SUFFIX = ".corrupt"


def _log(msg: str) -> None:
    try:
        xbmc.log("[service.skippy - store] %s" % msg, xbmc.LOGWARNING)
    except Exception:
        pass


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


def _load_json_file(path: str):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _is_valid_json_file(path: str) -> bool:
    try:
        _load_json_file(path)
    except (OSError, TypeError, ValueError):
        return False
    return True


def read_json(path: str | None, default=None, *, recover: bool = False):
    """Parse a JSON file; returns ``default`` for missing or unreadable files.

    With ``recover=True`` a file that exists but does not parse (empty, truncated,
    hand-edited wrongly) is not silently replaced by defaults: it is moved to
    ``<name>.corrupt`` for inspection and the last good copy ``<name>.bak`` is
    restored and returned when there is one.
    """
    if not path or not os.path.isfile(path):
        return default
    try:
        return _load_json_file(path)
    except (OSError, TypeError):
        return default
    except ValueError:
        if not recover:
            return default
    # Unparseable content: keep it aside, then fall back to the last good copy.
    try:
        os.replace(path, path + CORRUPT_SUFFIX)
        _log("%s is not valid JSON; kept as %s%s" % (path, os.path.basename(path), CORRUPT_SUFFIX))
    except OSError:
        pass
    backup = path + BACKUP_SUFFIX
    if not os.path.isfile(backup):
        return default
    try:
        data = _load_json_file(backup)
    except (OSError, TypeError, ValueError):
        return default
    try:
        shutil.copyfile(backup, path)
        _log("restored %s from its backup" % path)
    except OSError:
        pass
    return data


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


def write_json(path: str | None, data, *, keep_backup: bool = False) -> bool:
    """Write JSON via a temp file + replace so a crash cannot truncate the original.

    ``keep_backup=True`` first copies the current file to ``<name>.bak`` when (and
    only when) it is itself valid JSON, so a good backup is never replaced by a
    damaged file.
    """
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
        if keep_backup and os.path.isfile(path) and _is_valid_json_file(path):
            try:
                shutil.copyfile(path, path + BACKUP_SUFFIX)
            except OSError:
                pass
        os.replace(tmp_path, path)
        _fsync_directory(os.path.dirname(path))
        return True
    except (OSError, TypeError, ValueError):
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        return False
