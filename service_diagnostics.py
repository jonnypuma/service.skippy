# -*- coding: utf-8 -*-
"""What the service knows about the playing video, for the "Current video" window.

The service and the settings window run as separate scripts, so the service mirrors a
small JSON object to ``Window(10000)``. The segments themselves and the source that won
are already mirrored by ``playback_segment_cache``; this adds the title, the binge run,
the per-title override key and the last error the playback loop hit.
"""

from __future__ import annotations

import json
import time

DIAG_WIN_PROP = "skippy.diagnostics.v1"
_JSON_VERSION = 1


def _window():
    import xbmcgui

    return xbmcgui.Window(10000)


def publish_diagnostics(monitor, **fields) -> None:
    """Merge ``fields`` into the published object; writes only when something changed."""
    if monitor is None:
        return
    current = dict(getattr(monitor, "_diagnostics", None) or {})
    merged = dict(current)
    merged.update(fields)
    if merged == current and current:
        return
    monitor._diagnostics = merged
    payload = dict(merged)
    payload["v"] = _JSON_VERSION
    try:
        _window().setProperty(DIAG_WIN_PROP, json.dumps(payload, separators=(",", ":")))
    except Exception:
        pass


def note_loop_error(monitor, signature, where="playback loop", now=None) -> None:
    """Remember the last error, with the local time it happened."""
    stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))
    publish_diagnostics(
        monitor, last_error={"text": str(signature)[:300], "where": where, "at": stamp}
    )


def read_diagnostics() -> dict:
    """The published object, or ``{}`` when the service has published nothing."""
    try:
        raw = _window().getProperty(DIAG_WIN_PROP)
        data = json.loads(raw) if raw else {}
    except Exception:
        return {}
    if not isinstance(data, dict) or data.get("v") != _JSON_VERSION:
        return {}
    return data
