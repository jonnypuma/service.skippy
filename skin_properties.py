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
``Skippy.NextEpisode.Title``            ``The Return``
``Skippy.NextEpisode.ShowTitle``        ``Arrow`` (empty for a movie)
``Skippy.NextEpisode.Season`` / ``.Episode``  ``2`` / ``5``
``Skippy.NextEpisode.Plot``             its plot, when Kodi has one
``Skippy.NextEpisode.Thumb``            its picture, when Kodi has one
``Skippy.NextEpisode.Due``              ``true`` while the next episode prompt is due
--------------------------------------  ------------------------------------------------
Only while the skin draws the prompt (``Skippy.SkinNextEpisode``):
``Skippy.NextEpisode.Visible``          ``true`` while the prompt is up
``Skippy.NextEpisode.StillWatching``    ``true`` when it asks "Still watching?"
``Skippy.NextEpisode.Heading``          ``Play next episode?`` / ``Still watching?``
``Skippy.NextEpisode.PlayLabel``        ``Play now`` / ``Continue``
``Skippy.NextEpisode.CloseLabel``       ``Close`` / ``Stop``
``Skippy.NextEpisode.Countdown``        ``Episode ends in 00:42`` (or ``starts in``, ``Closing in``)
``Skippy.NextEpisode.SecondsLeft``      ``42``
``Skippy.NextEpisode.Progress``         ``30`` (percent of the countdown gone)
======================================  ================================================

A skin that draws its own skip button sets ``Skippy.SkinSkipButton`` to ``true`` on the Home
window (for example in its startup ``onload``); Skippy then opens no dialog of its own for
**Ask** segments, and the button calls ``RunScript(service.skippy,skip_current)``. In the same
way ``Skippy.SkinNextEpisode`` hands the next episode popup to the skin; its buttons call
``RunScript(service.skippy,next_episode_play)`` and ``RunScript(service.skippy,next_episode_close)``
(see ``next_episode_skin``).

Smooth bars in the skin's own dialogs (``skin_progress``). ``Skippy.Segment.Progress`` moves once a
second; a skin that wants its bar or ring to move every video frame declares, on the Home window:

======================================  ================================================
``Skippy.SkinSkipProgress.Window``      id of its skip dialog window (Aeon Fuse: ``1167``)
``Skippy.SkinSkipProgress.Control``     a progress control in it without ``<info>``
``Skippy.SkinSkipProgress.Frames``      optional: N pictures of a ring / image sequence
``Skippy.SkinNextEpisodeProgress.*``    the same three for its next episode popup
======================================  ================================================

and Skippy sets, while it drives that control with ``setPercent(float)``:

======================================  ================================================
``Skippy.Segment.SmoothProgress``       ``true`` after the first update, cleared when it stops:
                                        show the driven control only then, the ``<info>`` one otherwise
``Skippy.Segment.Frame``                ``round(percent / 100 * (N - 1))`` with ``.Frames`` = N
``Skippy.NextEpisode.SmoothProgress``   the same for the next episode popup
``Skippy.NextEpisode.Frame``            the same for the next episode popup
======================================  ================================================

The driven control shows what the ``<info>`` property it stands in for shows, so the swap never
jumps: the percent of the segment played (``Skippy.Segment.Progress``) and the percent of the next
episode countdown gone (``Skippy.NextEpisode.Progress``). Every property above stays as it is.
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
    "NextEpisode.Title",
    "NextEpisode.ShowTitle",
    "NextEpisode.Season",
    "NextEpisode.Episode",
    "NextEpisode.Plot",
    "NextEpisode.Thumb",
    "NextEpisode.Due",
    "NextEpisode.Visible",
    "NextEpisode.StillWatching",
    "NextEpisode.Heading",
    "NextEpisode.PlayLabel",
    "NextEpisode.CloseLabel",
    "NextEpisode.Countdown",
    "NextEpisode.SecondsLeft",
    "NextEpisode.Progress",
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


def _number(value) -> str:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return ""
    return str(number) if number >= 0 else ""


def _next_episode_values(monitor) -> dict:
    """``NextEpisode.*`` values (without the prefix) from the service's next episode state."""
    state = getattr(monitor, "next_episode_state", None)
    item = getattr(state, "next_item", None)
    if not isinstance(item, dict) or not item:
        return {}
    try:
        from next_episode_lookup import episode_label, is_movie_item

        label = episode_label(item)
        movie = is_movie_item(item)
    except Exception:
        label, movie = str(item.get("title") or ""), False
    art = item.get("art") if isinstance(item.get("art"), dict) else {}
    values = {
        "NextEpisode.Label": label,
        "NextEpisode.Title": str(item.get("title") or "").strip(),
        "NextEpisode.ShowTitle": "" if movie else str(item.get("showtitle") or "").strip(),
        "NextEpisode.Season": "" if movie else _number(item.get("season")),
        "NextEpisode.Episode": "" if movie else _number(item.get("episode")),
        "NextEpisode.Plot": str(item.get("plot") or "").strip(),
        "NextEpisode.Thumb": str(item.get("thumb") or art.get("thumb") or item.get("thumbnail") or ""),
    }
    prompt = getattr(state, "skin_prompt", None)
    if prompt is not None and not getattr(prompt, "finished", True):
        values.update(
            {
                "NextEpisode.Visible": "true",
                "NextEpisode.StillWatching": "true" if prompt.still_watching else "",
                "NextEpisode.Heading": prompt.heading,
                "NextEpisode.PlayLabel": prompt.play_label,
                "NextEpisode.CloseLabel": prompt.close_label,
                "NextEpisode.Countdown": prompt.countdown,
                "NextEpisode.SecondsLeft": str(prompt.seconds_left),
                "NextEpisode.Progress": str(prompt.progress),
            }
        )
    return values


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
    values.update(_next_episode_values(monitor))
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
