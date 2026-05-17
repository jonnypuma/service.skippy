# -*- coding: utf-8 -*-
"""TV successor online-segment prefetch (separate from ``remote_segment_cache``).

Handoff: only after path match **and** ``build_tv_cache_key`` matches the playing
library episode. Cleared at service start; replaced when scheduling a new prefetch.
"""
import copy
import os

import xbmcvfs

_entry = None


def clear_prefetch_segment_cache():
    global _entry
    _entry = None


def _paths_refer_to_same_video(path_a, path_b):
    if not path_a or not path_b:
        return False
    try:
        ta = xbmcvfs.translatePath(str(path_a).strip())
        tb = xbmcvfs.translatePath(str(path_b).strip())
        return os.path.normcase(os.path.normpath(ta)) == os.path.normcase(
            os.path.normpath(tb)
        )
    except (OSError, TypeError, ValueError, AttributeError):
        sa = str(path_a).strip().replace("\\", "/").rstrip("/")
        sb = str(path_b).strip().replace("\\", "/").rstrip("/")
        return sa.lower() == sb.lower()


def set_tv_segment_prefetch(target_path, segments, cache_key):
    """Store online segments for the successor episode file (replaces any prior entry)."""
    global _entry
    if not target_path or not cache_key:
        _entry = None
        return
    _entry = {
        "target_path": str(target_path).strip(),
        "segments": [copy.copy(s) for s in (segments or [])],
        "cache_key": cache_key,
    }


def peek_tv_prefetch_for_playing_path(playing_path):
    """Return the live prefetch entry if ``playing_path`` is the prefetched file; else None."""
    if not _entry or not playing_path:
        return None
    if not _paths_refer_to_same_video(_entry["target_path"], playing_path):
        return None
    return _entry


def consume_tv_prefetch_entry():
    """Drop prefetch storage after successful or rejected handoff."""
    global _entry
    _entry = None
