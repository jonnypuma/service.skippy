# -*- coding: utf-8 -*-
"""Published snapshot of ``monitor.segment_parse_cache`` for non-service code.

The service calls :func:`publish_parse_cache` whenever the cache dict is replaced
or cleared.

``RunScript`` / ``segment_marker.py`` runs in a **separate** Python invoker from
the background service: module globals like ``_snapshot`` are **not** shared.
The same snapshot is therefore **mirrored** to ``Window(10000)`` so the Segment
Editor (and any script entry) can read the last parse via
:func:`get_parse_cache_snapshot`.
"""
import json
from types import SimpleNamespace

import xbmcgui

_PARSE_WIN_PROP = "skippy.parse_cache_snapshot.v1"
_JSON_VERSION = 1

_snapshot = None


def _segments_to_payload_list(segments):
    out = []
    for seg in segments or []:
        out.append(
            {
                "start": float(getattr(seg, "start_seconds", 0)),
                "end": float(getattr(seg, "end_seconds", 0)),
                "label": getattr(seg, "segment_type_label", "") or "",
                "source": getattr(seg, "source", "edl") or "edl",
                "action_type": getattr(seg, "action_type", None),
            }
        )
    return out


def _write_window_mirror(snapshot):
    try:
        win = xbmcgui.Window(10000)
        if snapshot is None:
            win.clearProperty(_PARSE_WIN_PROP)
            return
        payload = {
            "v": _JSON_VERSION,
            "path": snapshot.get("path") or "",
            "playback_type": snapshot.get("playback_type") or "",
            "segment_origin": snapshot.get("segment_origin") or "none",
            "segments": _segments_to_payload_list(snapshot.get("segments")),
        }
        win.setProperty(_PARSE_WIN_PROP, json.dumps(payload, separators=(",", ":")))
    except Exception:
        pass


def _read_window_mirror():
    try:
        raw = xbmcgui.Window(10000).getProperty(_PARSE_WIN_PROP)
        if not raw:
            return None
        data = json.loads(raw)
        if data.get("v") != _JSON_VERSION:
            return None
        segs = []
        for s in data.get("segments") or []:
            at = s.get("action_type")
            if at is not None and at != "":
                at = str(at)
            else:
                at = None
            segs.append(
                SimpleNamespace(
                    start_seconds=float(s["start"]),
                    end_seconds=float(s["end"]),
                    segment_type_label=str(s.get("label") or ""),
                    source=str(s.get("source") or "edl"),
                    action_type=at,
                )
            )
        return {
            "path": data.get("path") or None,
            "playback_type": data.get("playback_type") or "",
            "segment_origin": data.get("segment_origin") or "none",
            "segments": segs,
        }
    except Exception:
        return None


def publish_parse_cache(snapshot):
    """Set or clear the mirrored cache (``None`` when invalidated)."""
    global _snapshot
    _snapshot = snapshot
    _write_window_mirror(snapshot)


def get_parse_cache_snapshot():
    """
    Return the last published cache dict or ``None``.

    In the service process, returns the in-memory snapshot. In a ``RunScript``
    invoker (same machine, different interpreter), reads the window mirror.
    """
    global _snapshot
    if _snapshot is not None:
        return _snapshot
    return _read_window_mirror()
