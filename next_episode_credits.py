# -*- coding: utf-8 -*-
"""Where the credits begin: the start of an episode's Credits segment, when it has one."""

from __future__ import annotations

from typing import Optional

CREDITS_TYPE_ID = "credits"
# Credits only count in the last half of the episode, so a mislabelled early segment
# (a "credits" row for the opening titles, say) never pulls the prompt to the middle.
MIN_CREDITS_FRACTION = 0.5


def segment_is_credits(segment) -> bool:
    """True when the segment's label resolves to the Credits type (aliases included)."""
    from segment_types import canonical_type_id

    return canonical_type_id(getattr(segment, "segment_type_label", "")) == CREDITS_TYPE_ID


def credits_start_seconds(segments, total_time, is_credits=segment_is_credits) -> Optional[float]:
    """Earliest start of a Credits segment in the second half of the episode, else None."""
    try:
        total = float(total_time)
    except (TypeError, ValueError):
        return None
    if total <= 0:
        return None
    best = None
    for segment in segments or ():
        try:
            start = float(segment.start_seconds)
            end = float(segment.end_seconds)
        except (AttributeError, TypeError, ValueError):
            continue
        if end <= start or start < total * MIN_CREDITS_FRACTION:
            continue
        try:
            if not is_credits(segment):
                continue
        except Exception:
            continue
        if best is None or start < best:
            best = start
    return best
