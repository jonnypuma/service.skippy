# -*- coding: utf-8 -*-
"""Shared EDL line parsing for the service, the editor, and the marker.

Each of them used to split EDL rows itself, with slightly different tolerance for
comments, missing action fields, and trailing columns — so a file that the editor
listed could be partly ignored during playback.
"""

from __future__ import annotations

# Kodi's EDL "cut/scene" action; used when a row omits the action column.
EDL_DEFAULT_ACTION = 4


def parse_edl_line(line, *, default_action=None):
    """
    Split one EDL row into ``(start_seconds, end_seconds, action)``.

    Returns ``None`` for blank rows, ``#`` comments, and malformed rows, so a bad
    row never aborts a whole file. Extra columns after the action are ignored.
    When the action column is missing, ``default_action`` is used; ``None`` (the
    default) rejects such rows instead.
    """
    text = (line or "").strip()
    if not text or text.startswith("#"):
        return None

    parts = text.split()
    if len(parts) < 2:
        return None
    try:
        start = float(parts[0])
        end = float(parts[1])
    except (TypeError, ValueError):
        return None

    if len(parts) > 2:
        try:
            action = int(parts[2])
        except (TypeError, ValueError):
            return None
    elif default_action is None:
        return None
    else:
        action = int(default_action)

    return start, end, action
