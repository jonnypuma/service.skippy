# -*- coding: utf-8 -*-
"""Sidecar path discovery (.edl, chapter XML variants) and change signatures for cache invalidation."""
import os
import xml.etree.ElementTree as ET

import xbmc
import xbmcvfs

from segment_editor_parser import CHAPTER_XML_SIDECAR_SUFFIXES, normalize_matroska_chapter_xml_text
from settings_utils import get_addon, log, log_service_detail

# Jellyfin Kodi plugin (chapters/edl exporter) may place exports under this folder beside the video.
_JF_CHAPTERS_SUBDIR = ".chapters"


def _log_paths_detail(msg):
    log_service_detail(msg, tag="paths")


def _dedupe_paths(paths):
    seen = set()
    result = []
    for path in paths:
        if not path or path in seen:
            continue
        seen.add(path)
        result.append(path)
    return result


def _unique_trimmed_basenames(video_path):
    """Full path prefixes without extension: playback path plus optional player's file."""
    bases = []
    seen = set()

    def push(b):
        if b and b not in seen:
            seen.add(b)
            bases.append(b)

    push(os.path.splitext(video_path)[0])
    try:
        player = xbmc.Player()
        if player.isPlayingVideo():
            push(os.path.splitext(player.getPlayingFile())[0])
    except RuntimeError:
        pass
    return bases


def _chapter_xml_paths_to_try(video_path):
    ext = os.path.splitext(video_path)[1].lower()
    _log_paths_detail(f"🎬 Video container extension: {ext}")
    suffixes = list(CHAPTER_XML_SIDECAR_SUFFIXES)

    bases = _unique_trimmed_basenames(video_path)
    paths_to_try = []
    try:
        player = xbmc.Player()
        if player.isPlayingVideo():
            fb = player.getPlayingFile().rsplit(".", 1)[0]
            _log_paths_detail(f"🔄 Fallback base path from player: {fb}")
    except RuntimeError:
        log("⚠️ getPlayingFile() failed inside chapter path resolution")

    # 1) Traditional sidecars beside the video (same basename)
    for base in bases:
        for s in suffixes:
            paths_to_try.append(f"{base}{s}")

    # 2) Jellyfin-style: parent/.chapters/<stem><suffix>
    for base in bases:
        parent = os.path.dirname(base)
        stem = os.path.basename(base)
        if not parent or not stem:
            continue
        subdir = os.path.join(parent, _JF_CHAPTERS_SUBDIR)
        for s in suffixes:
            paths_to_try.append(os.path.join(subdir, f"{stem}{s}"))

    paths_to_try = _dedupe_paths(paths_to_try)

    # 3) Directory chapters.xml beside the media file (no basename match)
    vp_parent = os.path.dirname(video_path)
    if vp_parent:
        chap = os.path.join(vp_parent, "chapters.xml")
        if chap not in set(paths_to_try):
            paths_to_try.append(chap)

    _log_parent_dir_contents(video_path, ext)
    return paths_to_try


def _log_parent_dir_contents(video_path, ext):
    """Log parent directory contents for MP4 files to help diagnose sidecar issues (All detail only)."""
    addon = get_addon()
    if not addon:
        return
    from settings_utils import SKIPPY_LOG_ALL, skippy_log_effective_detail_level

    if skippy_log_effective_detail_level(addon) != SKIPPY_LOG_ALL:
        return
    if ext not in (".mp4", ".m4v"):
        return
    try:
        parent = (
            video_path.rsplit("/", 1)[0]
            if "/" in video_path
            else video_path.rsplit("\\", 1)[0]
        )
        dirs, files = xbmcvfs.listdir(parent)
        _log_paths_detail(
            f"📁 MP4 parent directory listing ({parent}): dirs={dirs[:10]}, files={files[:20]}"
        )
    except (OSError, IOError, RuntimeError, ValueError, TypeError, AttributeError) as e:
        _log_paths_detail(f"📁 MP4 parent directory listing failed: {e}")


def _edl_paths_to_try(video_path):
    ext = ("." + video_path.rsplit(".", 1)[1]).lower() if "." in video_path else ""
    _log_paths_detail(f"🎬 Video container extension (EDL path): {ext}")
    try:
        player = xbmc.Player()
        if player.isPlayingVideo():
            _log_paths_detail(
                f"🔄 Fallback base path from player: {player.getPlayingFile().rsplit('.', 1)[0]}"
            )
    except RuntimeError:
        log("⚠️ getPlayingFile() failed inside EDL path resolution")

    bases = _unique_trimmed_basenames(video_path)
    paths_to_try = []
    for base in bases:
        paths_to_try.append(f"{base}.edl")
    for base in bases:
        parent = os.path.dirname(base)
        stem = os.path.basename(base)
        if parent and stem:
            paths_to_try.append(os.path.join(parent, _JF_CHAPTERS_SUBDIR, f"{stem}.edl"))
    return _dedupe_paths(paths_to_try)


def _find_existing_edl_path(video_path):
    """First existing .edl in discovery order (sibling preferred, then .chapters/)."""
    for p in _edl_paths_to_try(video_path):
        try:
            if p and xbmcvfs.exists(p):
                return p
        except Exception:
            continue
    return None


def local_chapter_or_edl_file_exists(video_path, segment_monitor=None):
    if segment_monitor is not None:
        from service_sidecar_probe_cache import local_sidecar_exists

        return local_sidecar_exists(video_path, segment_monitor)
    for p in _chapter_xml_paths_to_try(video_path):
        if p and xbmcvfs.exists(p):
            return True
    for p in _edl_paths_to_try(video_path):
        if p and xbmcvfs.exists(p):
            return True
    return False


def _sidecar_paths_to_watch(video_path):
    return _dedupe_paths(
        _chapter_xml_paths_to_try(video_path) + _edl_paths_to_try(video_path)
    )


def _safe_stat_value(stat_obj, name):
    try:
        value = getattr(stat_obj, name)
        return value() if callable(value) else value
    except Exception:
        return None


def _sidecar_signature(video_path, segment_monitor=None):
    """Return existing sidecar paths with mtime/size so edits during playback can refresh parsing."""
    if segment_monitor is not None:
        from service_sidecar_probe_cache import resolve_sidecar_paths

        probe = resolve_sidecar_paths(video_path, segment_monitor)
        if probe.probed and not probe.chapter_path and not probe.edl_path:
            return tuple()

    signature = []
    watch_paths = _sidecar_paths_to_watch(video_path)
    if segment_monitor is not None:
        from service_sidecar_probe_cache import resolve_sidecar_paths

        probe = resolve_sidecar_paths(video_path, segment_monitor)
        if probe.probed:
            watch_paths = [
                p
                for p in watch_paths
                if p
                in (
                    probe.chapter_path,
                    probe.edl_path,
                )
            ]
    for path in watch_paths:
        try:
            if not xbmcvfs.exists(path):
                continue
            stat_obj = xbmcvfs.Stat(path)
            signature.append(
                (
                    path,
                    _safe_stat_value(stat_obj, "st_mtime"),
                    _safe_stat_value(stat_obj, "st_size"),
                )
            )
        except (
            OSError,
            IOError,
            RuntimeError,
            ValueError,
            TypeError,
            AttributeError,
        ) as e:
            _log_paths_detail(f"⚠ Could not stat sidecar path {path}: {e}")
            signature.append((path, None, None))
    return tuple(signature)


def _sidecar_chapter_xml_exists(video_path):
    for p in _chapter_xml_paths_to_try(video_path):
        if p and xbmcvfs.exists(p):
            return True
    return False


def playback_path_supports_sidecar_chapters_xml(video_path):
    """
    chapters.xml sidecars are written next to the resolved playback path. Skip plugin URLs,
    .strm stubs, and common non-local schemes where a sibling file is meaningless or unsafe.
    """
    if not video_path or not isinstance(video_path, str):
        return False
    p = video_path.strip()
    low = p.lower()
    if low.startswith("plugin://"):
        return False
    if low.endswith(".strm"):
        return False
    for prefix in (
        "http://",
        "https://",
        "rtp://",
        "rtmp://",
        "rtsp://",
        "mmsh://",
        "mms://",
    ):
        if low.startswith(prefix):
            return False
    return True


def _find_existing_sidecar_chapter_xml_path(video_path):
    """
    Prefer the first sidecar path that exists and is valid XML after normalization
    (see ``normalize_matroska_chapter_xml_text``). If every existing file is corrupt,
    return the first existing path so callers can overwrite/repair it.
    """
    paths = _chapter_xml_paths_to_try(video_path)
    seen = set()
    first_existing = None
    for p in paths:
        if not p or p in seen:
            continue
        seen.add(p)
        try:
            exists = xbmcvfs.exists(p)
        except Exception:
            continue
        if not exists:
            continue
        if first_existing is None:
            first_existing = p
        try:
            f = xbmcvfs.File(p)
            data = f.read()
            f.close()
        except Exception:
            continue
        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="replace")
        if not data or not str(data).strip():
            continue
        try:
            ET.fromstring(normalize_matroska_chapter_xml_text(data))
        except Exception:
            continue
        return p
    return first_existing


def _default_new_sidecar_chapter_xml_path(video_path):
    return os.path.splitext(video_path)[0] + "-chapters.xml"
