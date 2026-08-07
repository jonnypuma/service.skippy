# -*- coding: utf-8 -*-
"""Single source of truth for Skippy time formatting and parsing.

Sidecar writers (chapters.xml / EDL), the editor, the marker, and the skip dialog all
need the same conversions. They used to keep private copies that drifted in rounding
and negative-value handling.
"""

from __future__ import annotations

import re

_NUMERIC_TIME_RE = re.compile(r"^\d+(?:\.\d+)?$")


def hms_to_seconds(value) -> float:
    """Convert ``HH:MM:SS.mmm``, ``MM:SS``, or plain seconds to a non-negative float.

    Raises ValueError on negative, empty, or otherwise malformed input.
    """
    if value is None:
        raise ValueError("Time input is empty")

    text = str(value).strip()
    if not text:
        raise ValueError("Time input is empty")
    if text.startswith("-"):
        raise ValueError(f"Time cannot be negative: {value!r}")
    if text.startswith("+"):
        text = text[1:].strip()
        if not text:
            raise ValueError("Time input is empty")

    parts = text.split(":")
    if len(parts) > 3:
        raise ValueError(f"Invalid time format: {value!r}")

    # Every part but the last must be a plain integer; the last may be decimal.
    for part in parts[:-1]:
        if not part or not part.isdigit():
            raise ValueError(f"Invalid time component {part!r} in {value!r}")
    if not _NUMERIC_TIME_RE.match(parts[-1]):
        raise ValueError(f"Invalid seconds component {parts[-1]!r} in {value!r}")

    if len(parts) == 3:
        hours, minutes, seconds = parts
        total = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    elif len(parts) == 2:
        minutes, seconds = parts
        total = int(minutes) * 60 + float(seconds)
    else:
        total = float(parts[0])

    if total < 0:
        raise ValueError(f"Time cannot be negative: {value!r}")
    return total


def seconds_to_hms(seconds) -> str:
    """``HH:MM:SS.mmm`` — the form chapters.xml sidecars use."""
    value = max(0.0, float(seconds))
    hours = int(value // 3600)
    minutes = int((value % 3600) // 60)
    return "%02d:%02d:%06.3f" % (hours, minutes, value - hours * 3600 - minutes * 60)


def seconds_to_edl(seconds) -> str:
    """Plain decimal seconds — the form EDL sidecars use."""
    return "%.3f" % float(seconds)


def format_clock(seconds) -> str:
    """``H:MM:SS`` past an hour, otherwise ``M:SS`` (compact, for toasts and labels)."""
    value = max(0.0, float(seconds))
    hours = int(value // 3600)
    minutes = int((value % 3600) // 60)
    secs = int(value % 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_jump_clock(seconds) -> str:
    """``HH:MM:SS`` past an hour, otherwise ``MM:SS`` (zero-padded, for dialog subtext)."""
    total = max(0, int(float(seconds)))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return "%02d:%02d:%02d" % (hours, minutes, secs)
    return "%02d:%02d" % (minutes, secs)
