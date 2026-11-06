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


def forward_jump_target(segments, index, current_time=None):
    """
    Where a skip from ``segments[index]`` lands first: ``(start, info)``, or
    ``(None, None)`` when it should go straight to the segment's own end.

    This is the single rule behind both the parse-time linking pass and the
    rewind-time re-evaluation, so the two cannot disagree. Walking the later
    segments in start order, the skip stops at

    * the first nested segment that is still ahead of the playhead (or any
      nested segment when ``current_time`` is None); nested segments the
      playhead has already passed are skipped over, and
    * the start of an overlapping segment.

    With several nested segments the skip therefore stops at each one in turn:
    leaving the first brings the parent's dialog back, now pointing at the next.
    """
    for other, relation in iter_forward_overlaps(segments, index):
        if relation == RELATION_NESTED:
            if current_time is None or current_time < other.start_seconds:
                return other.start_seconds, jump_info_nested(other)
        elif relation == RELATION_OVERLAPPING:
            return other.start_seconds, jump_info_overlapping(other)
    return None, None


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
