# -*- coding: utf-8 -*-
"""The skin's own next episode popup.

A skin that draws its own popup sets ``Skippy.SkinNextEpisode`` to ``true`` on the Home window.
Skippy then opens no popup or toast of its own: when the prompt is due it fills the
``Skippy.NextEpisode.*`` properties (``skin_properties``), sets ``Skippy.NextEpisode.Visible``,
and waits for the skin's buttons, which call ``RunScript(service.skippy,next_episode_play)``
and ``RunScript(service.skippy,next_episode_close)``. Everything else stays as it is: when the
prompt is due, the countdown and what happens when it runs out, "Still watching?", autoplay,
marking as watched and the per-show choices.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from next_episode_state import END_GUARD_S, END_PLAY, TIMED_OUT

SKIN_NEXT_EPISODE = "Skippy.SkinNextEpisode"
REQUEST_PLAY = "play"
REQUEST_CLOSE = "close"
# A button press older than this (the video was paused, or no prompt was up) is dropped.
REQUEST_MAX_AGE_S = 5.0
# The prompt played out to the end of the file without an answer, like the popup closing by itself.
ENDED = "ended"


@dataclass
class SkinPrompt:
    begin: float
    end: float
    timed: bool
    end_action: str
    still_watching: bool
    heading: str = ""
    label: str = ""
    play_label: str = ""
    close_label: str = ""
    countdown: str = ""
    seconds_left: int = 0
    progress: int = 0
    finished: bool = False


def skin_draws_next_episode(win) -> bool:
    try:
        return (win.getProperty(SKIN_NEXT_EPISODE) or "").strip().lower() == "true"
    except Exception:
        return False


def request_next_episode(monitor, what) -> None:
    """From ``onNotification``: the skin's Play or Close button was pressed."""
    if monitor is not None and what in (REQUEST_PLAY, REQUEST_CLOSE):
        monitor.next_episode_request = (what, time.monotonic())


def take_request(monitor, now=None) -> Optional[str]:
    """The pending button press (once), or None; an old one is dropped."""
    request = getattr(monitor, "next_episode_request", None)
    monitor.next_episode_request = None
    if not request:
        return None
    what, at = request
    now = time.monotonic() if now is None else now
    return what if now - float(at) <= REQUEST_MAX_AGE_S else None


def prompt_answer(prompt, current_time, request):
    """What the popup would have answered by now: True, False, ``TIMED_OUT``, ``ENDED`` or None.

    The same rules as the popup: Play is True and Close is False; a timed countdown, or one that
    plays the next episode when it runs out, ends in ``TIMED_OUT`` at its end; one that runs to the
    end of the file stops just before it.
    """
    if request == REQUEST_PLAY:
        return True
    if request == REQUEST_CLOSE:
        return False
    limit = prompt.end if prompt.timed else prompt.end - END_GUARD_S
    try:
        head = float(current_time)
    except (TypeError, ValueError):
        return None
    if head < limit:
        return None
    runs_out = (prompt.timed or prompt.end_action == END_PLAY) and not prompt.still_watching
    return TIMED_OUT if runs_out else ENDED


def build_prompt(addon, next_item, begin, end, timed, end_action, still_watching) -> SkinPrompt:
    from next_episode_view import popup_texts

    texts = popup_texts(addon, False, next_item, still_watching=still_watching)
    return SkinPrompt(
        begin=float(begin),
        end=float(end),
        timed=bool(timed) and not still_watching,
        end_action=end_action if not still_watching else "",
        still_watching=bool(still_watching),
        heading=texts["heading"],
        label=texts["label"],
        play_label=texts["play"],
        close_label=texts["close"],
    )


def update_countdown(prompt, addon, current_time, movie=False) -> None:
    """The countdown line, seconds left and percent of the countdown gone, for the skin."""
    from next_episode_view import countdown_mode, countdown_text

    try:
        head = float(current_time)
    except (TypeError, ValueError):
        return
    left = max(0.0, prompt.end - head)
    span = max(0.001, prompt.end - prompt.begin)
    prompt.seconds_left = int(left + 0.5)
    prompt.progress = int(round(100.0 * min(1.0, max(0.0, (head - prompt.begin) / span))))
    mode = countdown_mode(prompt.end_action, prompt.timed, prompt.still_watching)
    prompt.countdown = countdown_text(addon, False, left, mode, movie=movie)
