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


@dataclass
class NextEpisodeState:
    video: str
    lookup: str = LOOKUP_IDLE
    next_item: Optional[dict] = None
    current_episode_id: Optional[int] = None
    current_playcount: Optional[int] = None
    dismissed: bool = False
    started: bool = False
    failed: bool = False
    last_prompt_mono: float = 0.0
    created_mono: float = field(default_factory=lambda: time.monotonic())
    # "Still watching?" guard: decided once per episode, and the watchdog that stops a playlist.
    guard_checked: bool = False
    guard_ask: bool = False
    guard_cancel: Optional[object] = None


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
