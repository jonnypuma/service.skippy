# -*- coding: utf-8 -*-
"""Driving a progress control in the skin's own skip dialog or next episode popup.

``Skippy.Segment.Progress`` and the countdown properties are written once a service tick
(a second), and a progress control's ``<info>`` only takes whole percents, so a skin's bar or
ring would step once a second. A skin that wants it smooth declares, on the Home window, next
to ``Skippy.SkinSkipButton`` / ``Skippy.SkinNextEpisode``:

    Skippy.SkinSkipProgress.Window          id of its skip dialog window (Aeon Fuse: 1167)
    Skippy.SkinSkipProgress.Control         id of a progress control in it without <info>
    Skippy.SkinSkipProgress.Frames          optional: N pictures of a ring / image sequence

and the same three as ``Skippy.SkinNextEpisodeProgress.*`` for the next episode popup.

While an **Ask** segment is active (a next episode prompt is up) and ``Window.IsVisible(<Window>)``
holds, Skippy runs a :class:`smooth_progress.ProgressDriver` on that window: it looks the
control up for every update (a skin dialog frees its controls when it closes) and calls
``setPercent(float)``, at the video's frame rate. Any error stops it. It stops when the segment
ends or the prompt is answered, when the window is no longer visible, when playback stops, and
before Skippy itself skips or starts the next episode.

``Skippy.Segment.SmoothProgress`` (``Skippy.NextEpisode.SmoothProgress``) is ``true`` after the
first update and cleared when the driver stops: show the driven control only then, and the
``<info>`` one otherwise. With ``.Frames`` = N, ``Skippy.Segment.Frame`` (``Skippy.NextEpisode.Frame``)
is ``round(percent / 100 * (N - 1))``, written only when it changes.

The driven control shows the same thing as the ``<info>`` property it stands in for, so swapping
one for the other never jumps: the skip bar is the percent of the segment played (like
``Skippy.Segment.Progress``), the next episode bar the percent of the countdown gone (like
``Skippy.NextEpisode.Progress``).
"""

from __future__ import annotations

from smooth_progress import ProgressDriver, segment_percent

SKIP = "skip"
NEXT = "next"
TARGET_PREFIX = {SKIP: "Skippy.SkinSkipProgress.", NEXT: "Skippy.SkinNextEpisodeProgress."}
STATE_PREFIX = {SKIP: "Skippy.Segment.", NEXT: "Skippy.NextEpisode."}
END_GUARD_S = 1.0


def _int(text):
    try:
        value = int(str(text or "").strip())
    except (TypeError, ValueError):
        return None
    return value


def read_target(win, kind):
    """``(window id, control id, frames)`` the skin declared, or None."""
    prefix = TARGET_PREFIX[kind]
    try:
        window_id = _int(win.getProperty(prefix + "Window"))
        control_id = _int(win.getProperty(prefix + "Control"))
        frames = _int(win.getProperty(prefix + "Frames")) or 0
    except Exception:
        return None
    if not window_id or not control_id:
        return None
    return window_id, control_id, max(0, frames)


def frame_for(percent, frames):
    if frames < 2:
        return 0
    return int(round(float(percent) / 100.0 * (frames - 1)))


def _window_visible(window_id):
    try:
        import xbmc

        return bool(xbmc.getCondVisibility("Window.IsVisible(%d)" % int(window_id)))
    except Exception:
        return False


def _skin_window(window_id):
    import xbmcgui

    return xbmcgui.Window(int(window_id))


class SkinBar:
    """One driver on the skin's control, with the properties that go with it."""

    def __init__(self, kind, key, home, target, percent_at, *, visible=None, window_factory=None,
                 driver_factory=ProgressDriver, position=None):
        self.kind = kind
        self.key = key
        self.target = target
        self._home = home
        self._visible = visible or _window_visible
        window_id, control_id, frames = target
        window = (window_factory or _skin_window)(window_id)
        state = STATE_PREFIX[kind]
        self._smooth_prop = state + "SmoothProgress"
        self._frame_prop = state + "Frame"
        self._last_frame = None

        def apply(pct):
            window.getControl(control_id).setPercent(pct)
            if frames >= 2:
                frame = frame_for(pct, frames)
                if frame != self._last_frame:
                    self._last_frame = frame
                    home.setProperty(self._frame_prop, str(frame))

        self.driver = driver_factory(
            "skippy-skin-%s-progress" % kind,
            percent_at,
            apply,
            position=position,
            still_wanted=lambda: self._visible(window_id),
            on_first=lambda: home.setProperty(self._smooth_prop, "true"),
            on_stop=self._clear,
        )

    def _clear(self):
        for prop in (self._smooth_prop, self._frame_prop):
            try:
                self._home.clearProperty(prop)
            except Exception:
                pass

    def start(self):
        self.driver.start()
        return self

    def stop(self):
        self.driver.stop()
        self._clear()

    @property
    def running(self):
        return self.driver.running


def _bars(monitor) -> dict:
    bars = getattr(monitor, "_skin_bars", None)
    if not isinstance(bars, dict):
        bars = {}
        monitor._skin_bars = bars
    return bars


def stop_bar(monitor, kind) -> None:
    """Stop driving (before Skippy skips or starts the next episode, or when it no longer applies)."""
    if monitor is None:
        return
    bar = _bars(monitor).pop(kind, None)
    if bar is not None:
        bar.stop()


def _sync(monitor, kind, key, home, target, percent_at, visible, **kwargs) -> None:
    bars = _bars(monitor)
    bar = bars.get(kind)
    if bar is not None and bar.running and bar.key == key and bar.target == target:
        return
    if bar is not None:
        stop_bar(monitor, kind)
    if key is None or target is None or not visible(target[0]):
        return
    bars[kind] = SkinBar(kind, key, home, target, percent_at, visible=visible, **kwargs).start()


def sync_skip_bar(monitor, home, segment, mode, countdown=False, *, skin_button, visible=None, **kwargs) -> None:
    """Called every service tick with the active segment (or None) and what Skippy does with it.

    ``countdown`` is False for skins: their fallback, ``Skippy.Segment.Progress``, is the percent
    played. (It is kept as a parameter for a skin contract that may ask for the other way.)
    """
    visible = visible or _window_visible
    target = read_target(home, SKIP) if skin_button else None
    if segment is None or mode != "ask" or target is None:
        stop_bar(monitor, SKIP)
        return
    start, end = float(segment.start_seconds), float(segment.end_seconds)

    def percent_at(position):
        if position >= end:
            return None
        return segment_percent(position, start, end, countdown)

    key = ("skip", start, end, countdown)
    _sync(monitor, SKIP, key, home, target, percent_at, visible, **kwargs)


def sync_next_bar(monitor, home, prompt, *, skin_popup, visible=None, **kwargs) -> None:
    """Called every service tick with the prompt the skin draws (or None when none is up)."""
    visible = visible or _window_visible
    target = read_target(home, NEXT) if skin_popup else None
    if prompt is None or getattr(prompt, "finished", True) or target is None:
        stop_bar(monitor, NEXT)
        return
    begin, end, timed = float(prompt.begin), float(prompt.end), bool(prompt.timed)
    limit = end if timed else end - END_GUARD_S

    def percent_at(position):
        if position >= limit:
            return None
        return segment_percent(position, begin, end)

    key = ("next", begin, end, timed)
    _sync(monitor, NEXT, key, home, target, percent_at, visible, **kwargs)
