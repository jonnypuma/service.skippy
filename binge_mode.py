# -*- coding: utf-8 -*-
"""Binge mode: see the intro once per sitting.

Episodes of one show played one after the other make a run. The first episode of a run
plays its intro; from the second on the intro is skipped without asking, and, when
**Also skip the recap** is on, so is the recap (you just saw the episode before). How the
next episode started does not matter: Play now, the autoplay countdown, a playlist,
Kodi's "play next video" or picking it by hand all continue the run.

A run ends when another show or a film plays, or when nothing of the show has been on
screen for longer than the gap set in settings (default 10 minutes).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from settings_utils import addon_get_bool, addon_get_int, log

INTRO = "intro"
RECAP = "recap"
DEFAULT_GAP_MINUTES = 10

REASON_FIRST = "binge_first"
REASON_LATER = "binge_later"


@dataclass
class BingeRun:
    show_key: Optional[str] = None
    show_name: str = ""
    video: Optional[str] = None
    position: int = 0
    last_seen_mono: Optional[float] = None


def binge_settings(addon) -> tuple:
    """``(enabled, skip_recap, gap_seconds)``."""
    enabled = addon_get_bool(addon, "binge_mode_enabled", False)
    skip_recap = addon_get_bool(addon, "binge_mode_skip_recap", True)
    gap = addon_get_int(addon, "binge_mode_gap_minutes", DEFAULT_GAP_MINUTES)
    try:
        gap = max(1, min(240, int(gap)))
    except (TypeError, ValueError):
        gap = DEFAULT_GAP_MINUTES
    return enabled, skip_recap, gap * 60.0


def _run(monitor) -> BingeRun:
    run = getattr(monitor, "binge_run", None)
    if not isinstance(run, BingeRun):
        run = BingeRun()
        monitor.binge_run = run
    return run


def note_playback(monitor, video, playback_type, show_key, show_name="", gap_seconds=600.0, now=None):
    """Update the run for one tick of playback; returns the episode's place in its run (0: none)."""
    if monitor is None:
        return 0
    run = _run(monitor)
    now = time.monotonic() if now is None else float(now)
    if playback_type != "episode" or not show_key or not video:
        if run.show_key is not None:
            log("🍿 Binge run ended (%s is playing)" % (playback_type or "something else"))
        run.show_key, run.show_name, run.video, run.position = None, "", None, 0
        run.last_seen_mono = now
        return 0
    recent = run.last_seen_mono is not None and now - run.last_seen_mono <= gap_seconds
    if video == run.video and show_key == run.show_key and recent:
        run.last_seen_mono = now
        return run.position
    if show_key == run.show_key and recent and run.position > 0:
        run.position += 1
    else:
        run.position = 1
    run.show_key, run.show_name, run.video = show_key, show_name, video
    run.last_seen_mono = now
    log("🍿 Binge run: episode %d of %s" % (run.position, show_name or show_key))
    return run.position


def binge_position(monitor) -> int:
    run = getattr(monitor, "binge_run", None)
    return run.position if isinstance(run, BingeRun) else 0


def binge_behavior(type_id, behavior, position, enabled, skip_recap) -> tuple:
    """``(behavior, reason)`` after binge mode; reason is None when binge mode changed nothing."""
    if not enabled or position <= 0:
        return behavior, None
    if type_id == INTRO:
        if position == 1:
            return ("never", REASON_FIRST) if behavior != "never" else (behavior, None)
        return ("auto", REASON_LATER) if behavior != "auto" else (behavior, None)
    if type_id == RECAP and skip_recap and position >= 2 and behavior != "auto":
        return "auto", REASON_LATER
    return behavior, None


def segment_type_id(label) -> str:
    try:
        from segment_types import canonical_type_id

        return canonical_type_id(label) or ""
    except Exception:
        return ""


def apply_binge_mode(monitor, addon, playback_type, segment_label, behavior) -> str:
    """Behavior for this segment once binge mode has had its say."""
    if playback_type != "episode":
        return behavior
    enabled, skip_recap, _gap = binge_settings(addon)
    if not enabled:
        return behavior
    new, reason = binge_behavior(
        segment_type_id(segment_label), behavior, binge_position(monitor), enabled, skip_recap
    )
    if reason:
        log(
            "🍿 Binge mode: %s → %s (episode %d of the run)"
            % (segment_label, new, binge_position(monitor))
        )
    return new
