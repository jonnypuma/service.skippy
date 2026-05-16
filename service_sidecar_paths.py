# -*- coding: utf-8 -*-
"""Sidecar path discovery (.edl, chapter XML variants) and change signatures for cache invalidation."""
import os

import xbmc
import xbmcvfs

from segment_editor_parser import CHAPTER_XML_SIDECAR_SUFFIXES
from settings_utils import get_addon, log, log_service_detail


def _log_paths_detail(msg):
    log_service_detail(msg, tag="paths")


def _chapter_xml_paths_to_try(video_path):
    base = os.path.splitext(video_path)[0]
    ext = os.path.splitext(video_path)[1].lower()
    _log_paths_detail(f"🎬 Video container extension: {ext}")
    suffixes = list(CHAPTER_XML_SIDECAR_SUFFIXES)
    fallback_base = None
    try:
        player = xbmc.Player()
        if player.isPlayingVideo():
            fallback_base = player.getPlayingFile().rsplit(".", 1)[0]
            _log_paths_detail(f"🔄 Fallback base path from player: {fallback_base}")
    except RuntimeError:
        log("⚠️ getPlayingFile() failed inside chapter path resolution")
    paths_to_try = [f"{base}{s}" for s in suffixes]
    if fallback_base:
        paths_to_try += [f"{fallback_base}{s}" for s in suffixes]
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
    base = video_path.rsplit(".", 1)[0]
    ext = ("." + video_path.rsplit(".", 1)[1]).lower() if "." in video_path else ""
    _log_paths_detail(f"🎬 Video container extension (EDL path): {ext}")
    fallback_base = None
    try:
        player = xbmc.Player()
        if player.isPlayingVideo():
            fallback_base = player.getPlayingFile().rsplit(".", 1)[0]
            _log_paths_detail(f"🔄 Fallback base path from player: {fallback_base}")
    except RuntimeError:
        log("⚠️ getPlayingFile() failed inside EDL path resolution")
    paths_to_try = [f"{base}.edl"]
    if fallback_base:
        paths_to_try.append(f"{fallback_base}.edl")
    return paths_to_try


def local_chapter_or_edl_file_exists(video_path):
    for p in _chapter_xml_paths_to_try(video_path):
        if p and xbmcvfs.exists(p):
            return True
    for p in _edl_paths_to_try(video_path):
        if p and xbmcvfs.exists(p):
            return True
    return False


def _dedupe_paths(paths):
    seen = set()
    result = []
    for path in paths:
        if not path or path in seen:
            continue
        seen.add(path)
        result.append(path)
    return result


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


def _sidecar_signature(video_path):
    """Return existing sidecar paths with mtime/size so edits during playback can refresh parsing."""
    signature = []
    for path in _sidecar_paths_to_watch(video_path):
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
    for p in _chapter_xml_paths_to_try(video_path):
        if p and xbmcvfs.exists(p):
            return p
    return None


def _default_new_sidecar_chapter_xml_path(video_path):
    return os.path.splitext(video_path)[0] + "-chapters.xml"
