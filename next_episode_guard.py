# -*- coding: utf-8 -*-
"""The "still watching?" guard: episodes that played in a row without a button press."""

from __future__ import annotations

import threading
from dataclasses import dataclass

# Kodi's idle clock restarts on every button press, but also around a switch of file, so a
# press only counts when it is clearly later than the start of the episode.
IDLE_SLACK_S = 10.0
# A playlist carries on by itself at the end of a file. When nobody answered the question,
# playback is stopped this long before the end instead.
STOP_BEFORE_END_S = 3.0
_WATCHDOG_TICK_S = 0.25
# The viewer went back before the window: somebody is there, the watchdog stands down.
_SEEK_BACK_S = 1.5
# An episode that was this close to its end when it was last seen played on to the end; the next
# one counts as started by itself when it began within the gap (the loop may skip a few ticks).
HANDOFF_END_S = 15.0
HANDOFF_GAP_S = 60.0


@dataclass
class WatchChain:
    """Episodes that played in a row without a button press. Lives on the service monitor."""

    unattended: int = 0
    autoplay_pending: bool = False


def begin_episode(chain, carried=False) -> None:
    """A new episode started: a run of hand-offs nobody pressed a button for goes on, anything else ends it.

    ``carried`` says the episode before it played to its end and the next one began by itself
    (Kodi's own "play next video", a playlist), which Skippy did not start either.
    """
    if not (chain.autoplay_pending or carried):
        chain.unattended = 0
    chain.autoplay_pending = False


def ended_on_its_own(state, now) -> bool:
    """Whether the episode of ``state`` played on to its end without anyone answering its prompt.

    Then whatever started the next video did so by itself. An episode the viewer moved on from
    (Play now, Close, Stop), or one Skippy started the next of, does not count.
    """
    if getattr(state, "answered", False) or getattr(state, "started", False):
        return False
    try:
        total = float(getattr(state, "total", 0.0))
        last = float(getattr(state, "last_time", 0.0))
        seen = float(getattr(state, "last_seen_mono", 0.0))
        now = float(now)
    except (TypeError, ValueError):
        return False
    if total <= 0 or seen <= 0:
        return False
    return total - last <= HANDOFF_END_S and now - seen <= HANDOFF_GAP_S


def input_since(started_mono, now, idle_seconds) -> bool:
    """True when a button was pressed after the episode started (or when we cannot tell)."""
    if idle_seconds is None:
        return True
    try:
        idle = float(idle_seconds)
        elapsed = float(now) - float(started_mono)
    except (TypeError, ValueError):
        return True
    return idle + IDLE_SLACK_S < elapsed


def evaluate(chain, started_mono, now, idle_seconds, limit) -> bool:
    """
    Count the episode that is ending; True when the viewer should be asked.

    A press during the episode starts the count over. Otherwise the episode counts as
    one in a row (the one playing included) and the question is due at ``limit``.
    """
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        return False
    if limit < 1:
        return False
    if input_since(started_mono, now, idle_seconds):
        chain.unattended = 0
        return False
    chain.unattended += 1
    return chain.unattended >= limit


def start_stop_watchdog(player, window_start, total, tick=_WATCHDOG_TICK_S) -> threading.Event:
    """
    Stop ``player`` shortly before the end of the file unless the returned event is set.

    The thread also ends when playback stops or the viewer seeks back before the window.
    """
    cancel = threading.Event()
    threading.Thread(
        target=watch_for_the_end,
        args=(player, float(window_start), float(total), cancel, tick),
        daemon=True,
    ).start()
    return cancel


def watch_for_the_end(player, window_start, total, cancel, tick=_WATCHDOG_TICK_S) -> bool:
    """Worker of :func:`start_stop_watchdog`. True when it stopped the player."""
    while not cancel.wait(tick):
        try:
            if not player.isPlaying():
                return False
            head = float(player.getTime())
        except Exception:
            return False
        if head < window_start - _SEEK_BACK_S:
            return False
        if head >= total - STOP_BEFORE_END_S:
            try:
                player.stop()
            except Exception:
                return False
            return True
    return False
