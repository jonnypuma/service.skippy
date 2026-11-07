# -*- coding: utf-8 -*-
"""Per-video state and window arithmetic for the next episode prompt."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

LOOKUP_IDLE = "idle"
LOOKUP_RUNNING = "running"
LOOKUP_FOUND = "found"
LOOKUP_NONE = "none"

# The prompt never opens in the first half minute: a short clip would otherwise show
# it the moment playback starts.
MIN_WINDOW_START_S = 30.0
# Closer to the end than this, the file is over; Kodi's own end-of-file handling wins.
END_GUARD_S = 1.0
# Seeking back this far before the window re-arms a prompt that was dismissed or used.
REARM_MARGIN_S = 5.0
# A prompt that closed on its own is not shown again within this many seconds.
MIN_REPROMPT_S = 3.0
# A credits segment that leaves less than this before the end is not worth a prompt of its own.
MIN_CREDITS_REMAINING_S = 10.0

# What happens when the prompt's countdown reaches zero and nobody has answered.
END_CLOSE = "Close"
END_PLAY = "Play"
END_ACTIONS = (END_CLOSE, END_PLAY)
# The settings that decide how long the prompt stays up and what it does when that runs out.
KEY_POPUP_DURATION = "next_episode_popup_duration"
KEY_END_ACTION = "next_episode_popup_end_action"
# The most seconds the prompt can be asked to stay up (0 keeps it up until the episode ends).
MAX_POPUP_DURATION_S = 120
# What the prompt returns when its countdown ran out; True / False / None keep their meaning.
TIMED_OUT = "timed_out"


@dataclass
class NextEpisodeState:
    video: str
    lookup: str = LOOKUP_IDLE
    next_item: Optional[dict] = None
    current_episode_id: Optional[int] = None
    current_playcount: Optional[int] = None
    # "episode" or "movie": what is playing, which decides how it is marked as watched.
    current_kind: str = "episode"
    dismissed: bool = False
    started: bool = False
    failed: bool = False
    last_prompt_mono: float = 0.0
    # The show's per-show autoplay key and title (empty when unknown or the feature is off).
    show_key: Optional[str] = None
    show_title: str = ""
    created_mono: float = field(default_factory=lambda: time.monotonic())
    # "Still watching?" guard: decided once per episode, and the watchdog that stops a playlist.
    guard_checked: bool = False
    guard_ask: bool = False
    guard_cancel: Optional[object] = None
    # How the episode went, for the same guard: the last playhead position and total length seen,
    # when (monotonic), and whether the viewer answered its prompt with a button.
    last_time: float = 0.0
    total: float = 0.0
    last_seen_mono: float = 0.0
    answered: bool = False
    # What the video add-on said about the next episode (Up Next's upnext_data), and whether this
    # is playback Skippy otherwise ignores (an add-on or stream URL), which has no library entry.
    provider: Optional[object] = None
    remote: bool = False


def reset_guard(state) -> None:
    """Forget the "still watching?" decision and stand the end-of-file watchdog down."""
    cancel = state.guard_cancel
    if cancel is not None:
        try:
            cancel.set()
        except Exception:
            pass
    state.guard_cancel = None
    state.guard_checked = False
    state.guard_ask = False


def window_start(total_time, lead_seconds, credits_start=None) -> Optional[float]:
    """
    Playhead position where the prompt is due, or None when it never is.

    ``credits_start`` (where the Credits segment begins) replaces "``lead_seconds`` before
    the end" when it leaves a usable window.
    """
    try:
        total = float(total_time)
        lead = float(lead_seconds)
    except (TypeError, ValueError):
        return None
    if total <= 0 or lead <= 0:
        return None
    if credits_start is not None:
        try:
            credits = float(credits_start)
        except (TypeError, ValueError):
            credits = None
        if credits is not None and MIN_WINDOW_START_S <= credits <= total - MIN_CREDITS_REMAINING_S:
            return credits
    start = total - lead
    if start < MIN_WINDOW_START_S:
        return None
    return start


def in_prompt_window(current_time, total_time, lead_seconds, credits_start=None) -> bool:
    start = window_start(total_time, lead_seconds, credits_start)
    if start is None:
        return False
    try:
        now = float(current_time)
        total = float(total_time)
    except (TypeError, ValueError):
        return False
    return start <= now < total - END_GUARD_S


def rearm_if_before_window(
    state, current_time, total_time, lead_seconds, credits_start=None
) -> bool:
    """Forget a dismissal / hand-off once the playhead is well before the window."""
    start = window_start(total_time, lead_seconds, credits_start)
    if start is None:
        return False
    try:
        now = float(current_time)
    except (TypeError, ValueError):
        return False
    if now >= start - REARM_MARGIN_S:
        return False
    changed = state.dismissed or state.started or state.failed
    state.dismissed = False
    state.started = False
    state.failed = False
    reset_guard(state)
    return changed


def normalize_end_action(value) -> str:
    """A stored "when the countdown ends" value, or Close when it is not one of the options."""
    text = str(value or "").strip().lower()
    for option in END_ACTIONS:
        if option.lower() == text:
            return option
    return END_CLOSE


def popup_span(window_start, current_time, total_time, duration):
    """
    ``(begin, end, timed)``: the stretch of the file the prompt counts down over.

    ``duration`` 0 counts down over the whole window, up to the end of the file. Any other
    value counts down that many seconds from where the prompt appears (never before the
    window starts); when that reaches the end of the file anyway, the prompt simply runs to
    the end and ``timed`` is False.
    """
    try:
        start = float(window_start)
        now = float(current_time)
        total = float(total_time)
        length = float(duration)
    except (TypeError, ValueError):
        return window_start, total_time, False
    if length <= 0:
        return start, total, False
    begin = max(start, now)
    end = begin + length
    if end >= total - END_GUARD_S:
        return begin, total, False
    return begin, end, True
