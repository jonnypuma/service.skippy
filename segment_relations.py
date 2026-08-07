# -*- coding: utf-8 -*-
"""Segment geometry helpers: ids, nesting/overlap relations, and jump-hint text.

Both the parse-time linking pass and the rewind-time re-evaluation walk the same
forward-overlap relation, and the skip dialog has to read back the hint text those
passes write. Keeping the traversal, the hint producers, and the hint parser in one
module keeps them from drifting apart.
"""

from __future__ import annotations

import re

RELATION_NESTED = "nested"
RELATION_OVERLAPPING = "overlapping"

JUMP_KIND_REMAINING = "remaining"
JUMP_KIND_NAMED = "named"


def segment_id(segment) -> tuple:
    """Stable identity for a segment: whole-second (start, end)."""
    return (
        int(round(segment.start_seconds)),
        int(round(segment.end_seconds)),
    )


def is_nested_segment(segment_a, segment_b) -> bool:
    """True when ``segment_b`` is fully contained within ``segment_a``."""
    return (
        segment_b.start_seconds >= segment_a.start_seconds
        and segment_b.end_seconds <= segment_a.end_seconds
    )


def is_overlapping_segment(segment_a, segment_b) -> bool:
    """True when the segments overlap without either fully containing the other."""
    if (
        segment_a.end_seconds <= segment_b.start_seconds
        or segment_b.end_seconds <= segment_a.start_seconds
    ):
        return False
    if is_nested_segment(segment_a, segment_b) or is_nested_segment(segment_b, segment_a):
        return False
    return True


def iter_forward_overlaps(segments, index):
    """
    Yield ``(other, relation)`` for later segments starting before ``segments[index]`` ends.

    ``relation`` is ``RELATION_NESTED``, ``RELATION_OVERLAPPING``, or ``None`` (the
    current segment is itself contained in ``other``). Expects ``segments`` sorted
    by ``start_seconds``; stops at the first non-touching segment.
    """
    current = segments[index]
    for candidate in segments[index + 1 :]:
        if candidate.start_seconds >= current.end_seconds:
            return
        if is_nested_segment(current, candidate):
            yield candidate, RELATION_NESTED
        elif is_overlapping_segment(current, candidate):
            yield candidate, RELATION_OVERLAPPING
        else:
            yield candidate, None


def jump_info_nested(segment) -> str:
    return "nested segment '%s'" % segment.segment_type_label


def jump_info_overlapping(segment) -> str:
    return "overlapping segment '%s'" % segment.segment_type_label


def jump_info_remaining(parent_segment) -> str:
    return "remaining '%s'" % parent_segment.segment_type_label


_REMAINING_INFO = re.compile(r"(?i)^remaining\s+(?:'([^']+)'|(.+))$")
_QUOTED_LABEL = re.compile(r"'([^']+)'")


def parse_jump_info(info):
    """
    Split a ``next_segment_info`` hint into ``(kind, label)``.

    ``kind`` is ``JUMP_KIND_REMAINING`` when the skip lands back inside a parent
    segment, ``JUMP_KIND_NAMED`` when it lands on a named segment, else ``None``.
    """
    text = (info or "").strip()
    if not text:
        return None, None
    remaining = _REMAINING_INFO.match(text)
    if remaining:
        label = (remaining.group(1) or remaining.group(2) or "").strip()
        if label:
            return JUMP_KIND_REMAINING, label
    quoted = _QUOTED_LABEL.search(text)
    if quoted:
        label = quoted.group(1).strip()
        if label:
            return JUMP_KIND_NAMED, label
    return None, None
