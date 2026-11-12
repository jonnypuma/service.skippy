# -*- coding: utf-8 -*-
"""Home window properties a skin can read: the segment playing, what Skippy will do with it,
the next segment and the next episode.

All properties sit on ``Window(Home)`` and are empty when there is nothing to say, so a skin
tests them with ``String.IsEmpty``. They are written only when a value changes (the remaining
time once a second) and cleared when playback stops.

======================================  ================================================
``Skippy.HasSegments``                  ``true`` when the playing video has segments
``Skippy.Segment.Type``                 ``Intro`` (empty outside a segment)
``Skippy.Segment.TypeId``               ``intro`` (catalog id; for skin conditions)
``Skippy.Segment.Mode``                 ``auto``, ``ask`` or ``never``
``Skippy.Segment.Start`` / ``.End``     ``00:00`` / ``01:25`` (``HH:MM:SS`` past an hour)
``Skippy.Segment.Remaining``            ``0:42``
``Skippy.Segment.RemainingSeconds``     ``42``
``Skippy.Segment.Progress``             ``37`` (percent of the segment played)
``Skippy.Segment.Next.Type``            next segment after the playhead, ``Credits``
``Skippy.Segment.Next.Start``           ``42:10``
``Skippy.NextEpisode.Label``            ``S02E05 · The Return`` once the next one is known
``Skippy.NextEpisode.Thumb``            its picture, when Kodi has one
``Skippy.NextEpisode.Due``              ``true`` while the next episode prompt is due
======================================  ================================================

A skin that draws its own skip button sets ``Skippy.SkinSkipButton`` to ``true`` on the Home
window (for example in its startup ``onload``); Skippy then opens no dialog of its own for
**Ask** segments, and the button calls ``RunScript(service.skippy,skip_current)``.
"""

from __future__ import annotations

from time_format import format_clock, format_jump_clock

PREFIX = "Skippy."
SKIN_SKIP_BUTTON = "Skippy.SkinSkipButton"

KEYS = (
    "HasSegments",
    "Segment.Type",
    "Segment.TypeId",
    "Segment.Mode",
    "Segment.Start",
    "Segment.End",
    "Segment.Remaining",
    "Segment.RemainingSeconds",
    "Segment.Progress",
    "Segment.Next.Type",
    "Segment.Next.Start",
    "NextEpisode.Label",
    "NextEpisode.Thumb",
    "NextEpisode.Due",
)


def active_segment(segments, current_time):
    """The segment the playhead is in; the innermost (latest start) when several overlap."""
    try:
        t = float(current_time)
    except (TypeError, ValueError):
        return None
    inside = [s for s in segments or () if s.start_seconds <= t < s.end_seconds]
    if not inside:
        return None
    return max(inside, key=lambda s: (s.start_seconds, -s.end_seconds))


def next_segment(segments, current_time):
    try:
        t = float(current_time)
    except (TypeError, ValueError):
        return None
    ahead = [s for s in segments or () if s.start_seconds > t]
    return min(ahead, key=lambda s: (s.start_seconds, s.end_seconds)) if ahead else None


def _type_names(label):
    try:
        from segment_types import canonical_type_id, display_label_for

        return display_label_for(label) or label, canonical_type_id(label) or ""
    except Exception:
        return label or "", ""


def _next_episode_values(monitor):
    state = getattr(monitor, "next_episode_state", None)
    item = getattr(state, "next_item", None)
    if not isinstance(item, dict) or not item:
        return "", ""
    try:
        from next_episode_lookup import episode_label

        label = episode_label(item)
    except Exception:
        label = str(item.get("title") or "")
    art = item.get("art") if isinstance(item.get("art"), dict) else {}
    thumb = art.get("thumb") or item.get("thumbnail") or ""
    return label, str(thumb)


def build_skin_properties(segments, current_time, mode_for=None, *, monitor=None, next_due=False) -> dict:
    """Every property in :data:`KEYS` (prefixed), with ``""`` for the ones that do not apply."""
    values = {key: "" for key in KEYS}
    segments = list(segments or ())
    if segments:
        values["HasSegments"] = "true"
    seg = active_segment(segments, current_time)
    if seg is not None:
        name, type_id = _type_names(seg.segment_type_label)
        length = max(0.001, float(seg.end_seconds) - float(seg.start_seconds))
        remaining = max(0.0, float(seg.end_seconds) - float(current_time))
        values.update(
            {
                "Segment.Type": name,
                "Segment.TypeId": type_id,
                "Segment.Mode": (mode_for(seg) if mode_for else "") or "",
                "Segment.Start": format_jump_clock(seg.start_seconds),
                "Segment.End": format_jump_clock(seg.end_seconds),
                "Segment.Remaining": format_clock(remaining),
                "Segment.RemainingSeconds": str(int(remaining + 0.5)),
                "Segment.Progress": str(int(round(100.0 * (length - remaining) / length))),
            }
        )
    upcoming = next_segment(segments, current_time)
    if upcoming is not None:
        values["Segment.Next.Type"] = _type_names(upcoming.segment_type_label)[0]
        values["Segment.Next.Start"] = format_jump_clock(upcoming.start_seconds)
    label, thumb = _next_episode_values(monitor)
    values["NextEpisode.Label"] = label
    values["NextEpisode.Thumb"] = thumb
    values["NextEpisode.Due"] = "true" if next_due else ""
    return {PREFIX + key: value for key, value in values.items()}


def publish(win, monitor, props) -> int:
    """Write the properties that changed since the last call; returns how many were written."""
    if win is None or monitor is None:
        return 0
    last = getattr(monitor, "_skin_props", None) or {}
    written = 0
    for key, value in props.items():
        if last.get(key) == value:
            continue
        try:
            if value:
                win.setProperty(key, value)
            else:
                win.clearProperty(key)
            written += 1
        except Exception:
            pass
    monitor._skin_props = dict(props)
    return written


def clear(win, monitor) -> int:
    """Empty every property (playback stopped)."""
    if not getattr(monitor, "_skin_props", None):
        return 0
    return publish(win, monitor, {PREFIX + key: "" for key in KEYS})


def skin_draws_skip_button(win) -> bool:
    try:
        return (win.getProperty(SKIN_SKIP_BUTTON) or "").strip().lower() == "true"
    except Exception:
        return False
