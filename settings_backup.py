# -*- coding: utf-8 -*-
"""Backup and restore Skippy add-on settings as JSON (all persisted keys from settings.xml)."""
from __future__ import annotations

import json
import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import xbmcgui
import xbmcvfs

SCHEMA = "skippy_settings_backup_v1"
ADDON_ID = "service.skippy"


def _settings_xml_path(addon) -> str:
    return os.path.join(addon.getAddonInfo("path"), "resources", "settings.xml")


def iter_persisted_setting_ids(addon) -> list[str]:
    path = _settings_xml_path(addon)
    if not os.path.isfile(path):
        return []
    tree = ET.parse(path)
    ids = []
    for setting in tree.getroot().iter("setting"):
        sid = setting.get("id")
        stype = setting.get("type")
        if sid and stype != "action":
            ids.append(sid)
    return ids


def collect_settings(addon) -> dict[str, str]:
    keys = iter_persisted_setting_ids(addon)
    out: dict[str, str] = {}
    for k in keys:
        try:
            out[k] = addon.getSetting(k)
        except Exception:
            out[k] = ""
    return out


def _path_try_variants(path: str) -> list[str]:
    """Kodi vfs paths (e.g. smb://) vs translatePath; try raw first."""
    raw = str(path).strip()
    out = []
    if raw:
        out.append(raw)
    try:
        t = xbmcvfs.translatePath(raw)
    except (TypeError, ValueError):
        t = ""
    if t and t not in out:
        out.append(t.rstrip())

    seen_keys: list[str] = []
    uniq: list[str] = []
    for p in out:
        if not p:
            continue
        key = p.replace("\\", "/").lower()
        if key in seen_keys:
            continue
        seen_keys.append(key)
        uniq.append(p)
    return uniq


def _write_json_file(path: str, payload: dict) -> None:
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    ba = bytearray(text.encode("utf-8"))
    last_err: Exception | None = None

    for pth in _path_try_variants(path):
        try:
            with open(pth, "w", encoding="utf-8", newline="\n") as fp:
                fp.write(text)
            return
        except OSError as e:
            last_err = e
        except (TypeError, UnicodeError):
            continue
        try:
            vfs_f = xbmcvfs.File(pth, "w")
            try:
                vfs_f.write(ba)
            finally:
                del vfs_f
            return
        except Exception as e:
            last_err = e

    if last_err is not None:
        raise last_err
    raise OSError("failed to write settings backup")


def _read_json_file(path: str) -> dict:
    last_err: Exception | None = None
    for pth in _path_try_variants(path):
        try:
            with open(pth, encoding="utf-8") as fp:
                return json.load(fp)
        except json.JSONDecodeError:
            raise
        except UnicodeDecodeError:
            raise
        except OSError as e:
            last_err = e
        f = None
        try:
            f = xbmcvfs.File(pth)
            b = f.readBytes()
            if not b:
                continue
            return json.loads(bytes(b).decode("utf-8", errors="strict"))
        except json.JSONDecodeError:
            raise
        except UnicodeDecodeError:
            raise
        except Exception as e:
            last_err = e
        finally:
            if f is not None:
                del f

    if last_err is not None:
        raise last_err
    raise ValueError("Empty backup file")


def export_to_path(addon, dest_json_path: str) -> int:
    """Write JSON backup; returns number of keys written."""
    keys = iter_persisted_setting_ids(addon)
    payload = {
        "schema": SCHEMA,
        "addon_id": ADDON_ID,
        "addon_version_exported": addon.getAddonInfo("version") or "",
        "exported_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "settings": collect_settings(addon),
        "setting_key_count": len(keys),
    }
    _write_json_file(dest_json_path, payload)
    return len(keys)


def apply_imported_settings(addon, settings: dict, allowed: set[str]) -> tuple[int, int]:
    applied = 0
    unknown = 0
    for k, v in settings.items():
        if k not in allowed:
            unknown += 1
            continue
        try:
            addon.setSetting(k, "" if v is None else str(v))
            applied += 1
        except Exception:
            unknown += 1
    return applied, unknown


def import_from_path(addon, src_json_path: str) -> tuple[int, int, str]:
    """Load backup and apply overlapping keys. Returns (applied_count, skipped_or_failed_count, note)."""
    data = _read_json_file(src_json_path)
    if data.get("schema") != SCHEMA:
        raise ValueError("Not a Skippy settings backup (wrong or missing schema).")
    if data.get("addon_id") != ADDON_ID:
        raise ValueError("This file is not a Skippy (service.skippy) settings backup.")
    raw = data.get("settings")
    if not isinstance(raw, dict):
        raise ValueError("Backup file has no settings object.")
    allowed = set(iter_persisted_setting_ids(addon))
    applied, bad = apply_imported_settings(addon, raw, allowed)
    ver = data.get("addon_version_exported") or "?"
    note = "Backup from add-on version %s." % ver
    return applied, bad, note


def _restore_browse_result_is_json_file(path) -> bool:
    """
    Kodi browse() can return a folder (or other path) when the user backs out without choosing
    a file — still non-empty and xbmcvfs.exists. Only treat as a choice when we have a concrete
    .json file (not a directory).
    """
    p = (path or "").strip()
    if not p:
        return False
    if not p.lower().endswith(".json"):
        return False
    if not xbmcvfs.exists(p):
        return False
    pt = xbmcvfs.translatePath(p)
    try:
        if os.path.isdir(pt):
            return False
        if os.path.isfile(pt):
            return True
    except OSError:
        pass
    f = None
    try:
        f = xbmcvfs.File(p)
        f.read(1)
        return True
    except Exception:
        return False
    finally:
        if f is not None:
            del f


def _join_writable_folder_file(folder: str, filename: str) -> str:
    """
    Build destination path inside a Kodi browse() folder. Use forward slashes —
    ``os.path.join`` breaks vfs URLs (``smb://``, ``nfs://``, …).
    """
    root = str(folder).strip().replace("\\", "/").rstrip("/")
    return root + "/" + filename


def run_backup_ui(addon, icon_path: str, log_fn) -> None:
    heading = addon.getLocalizedString(38000) if addon else "Backup settings"
    # Same share as Restore: **files** exposes all Kodi file sources (not just **local**).
    # Pass default="" so Cancel returns empty string. If default is a real path, Kodi returns
    # that same path on Cancel — indistinguishable from OK, so backup would run anyway.
    folder = xbmcgui.Dialog().browse(3, heading, "files", "", False, False, "")
    if not folder or not str(folder).strip():
        return
    stamp = time.strftime("%Y%m%d-%H%M%S")
    name = "skippy-settings-backup-%s.json" % stamp
    dest = _join_writable_folder_file(folder, name)
    try:
        n = export_to_path(addon, dest)
    except Exception as e:
        log_fn("settings backup failed: %s" % e)
        xbmcgui.Dialog().ok(ADDON_ID, "%s\n%s" % (addon.getLocalizedString(38004), e))
        return
    log_fn("settings backup wrote %s keys to %s" % (n, dest))
    try:
        xbmcgui.Dialog().notification(
            heading,
            addon.getLocalizedString(38005) % name,
            icon_path or "DefaultAddonService.png",
            4500,
            sound=False,
        )
    except Exception:
        xbmcgui.Dialog().ok(heading, addon.getLocalizedString(38005) % name)


def run_restore_ui(addon, icon_path: str, log_fn) -> None:
    heading = addon.getLocalizedString(38002) if addon else "Restore settings"
    path = xbmcgui.Dialog().browse(1, heading, "files", ".json", False, False, "")
    if not _restore_browse_result_is_json_file(path):
        return
    yes = xbmcgui.Dialog().yesno(
        ADDON_ID,
        addon.getLocalizedString(38006),
    )
    if not yes:
        return
    try:
        applied, bad, note = import_from_path(addon, path)
    except ValueError as e:
        log_fn("settings restore rejected: %s" % e)
        xbmcgui.Dialog().ok(ADDON_ID, "%s\n%s" % (addon.getLocalizedString(38007), e))
        return
    except Exception as e:
        log_fn("settings restore failed: %s" % e)
        xbmcgui.Dialog().ok(ADDON_ID, "%s\n%s" % (addon.getLocalizedString(38004), e))
        return
    log_fn(
        "settings restore applied=%s skipped=%s (%s)"
        % (applied, bad, note)
    )
    try:
        xbmcgui.Dialog().notification(
            heading,
            addon.getLocalizedString(38008) % (applied, bad),
            icon_path or "DefaultAddonService.png",
            6000,
            sound=False,
        )
    except Exception:
        xbmcgui.Dialog().ok(
            heading,
            "%s\n%s" % (addon.getLocalizedString(38008) % (applied, bad), note),
        )
