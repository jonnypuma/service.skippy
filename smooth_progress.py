# -*- coding: utf-8 -*-
"""Progress bars that move every video frame instead of in whole-percent jumps.

Kodi's progress control reads its ``<info>`` as a whole percent, and an image fill moves in
whole skin units, so a bar driven once a second (or once a percent) visibly steps. A
:class:`ProgressDriver` thread sets a bar from the player's own time, as often as the video
has frames, the way Aeon Fuse's helper drives its music Now playing fill:

* ``xbmc.Player().getTime()`` is read for every update (it costs about a microsecond and moves
  in 10 ms steps), so pause, seek and buffering need no handling of their own;
* updates keep to a steady clock: each is due ``1 / rate`` after the one before, so the time
  the calls take does not lower the rate; more than one period behind starts over from now;
* the rate is the video's frame rate (``Player.Process(videofps)``), else the frames Kodi
  draws (``System.FPS``), else 25; read again every quarter second; four a second while paused;
* while paused Kodi's time wobbles by a few milliseconds: the bar never moves back by less
  than half a second, so its edge pixel cannot flicker; a real seek back is larger;
* the per-update path is ``position()``, ``percent_at()`` and ``apply()``; settings, window
  checks and pause are looked at only every quarter second, and nothing is logged per update.

``stop()`` sets an event and joins the thread, so no update can run after a dialog closes.
"""

from __future__ import annotations

import re
import threading
import time

CHECK_S = 0.25          # how often the driver looks at pause, the rate and whether it is still wanted
PAUSED_RATE = 4.0
DEFAULT_RATE = 25.0
LOWEST_RATE, HIGHEST_RATE = 10.0, 120.0
HOLD_BACK_S = 0.5       # while paused, never step back by less than this


def parse_rate(text):
    """``"23.976"`` / ``"23,976"`` / ``"59.94 fps"`` → 23.976; None when there is no number."""
    match = re.search(r"\d+(?:[.,]\d+)?", str(text or ""))
    if not match:
        return None
    try:
        value = float(match.group(0).replace(",", "."))
    except ValueError:
        return None
    return value if value > 0 else None


def clamp_rate(value) -> float:
    return min(HIGHEST_RATE, max(LOWEST_RATE, float(value)))


def video_frame_rate(info_label=None) -> float:
    """Updates a second: the video's frame rate, else what Kodi draws, else 25 (within 10-120)."""
    if info_label is None:
        import xbmc

        info_label = xbmc.getInfoLabel
    for label in ("Player.Process(videofps)", "System.FPS"):
        try:
            rate = parse_rate(info_label(label))
        except Exception:
            rate = None
        if rate and rate >= LOWEST_RATE / 2:
            return clamp_rate(rate)
    return DEFAULT_RATE


def held_position(last, position):
    """``position``, except a step back of less than :data:`HOLD_BACK_S` keeps ``last``."""
    if last is not None and 0.0 < last - position < HOLD_BACK_S:
        return last
    return position


def segment_percent(position, start, end, countdown=False):
    """Percent of ``start``..``end`` played (or left, with ``countdown``), as a float in 0-100."""
    length = float(end) - float(start)
    if length <= 0:
        return 100.0 if not countdown else 0.0
    pct = (float(position) - float(start)) * 100.0 / length
    pct = min(100.0, max(0.0, pct))
    return 100.0 - pct if countdown else pct


def _is_paused():
    try:
        import xbmc

        return bool(xbmc.getCondVisibility("Player.Paused"))
    except Exception:
        return False


def _default_position():
    import xbmc

    player = xbmc.Player()
    return player.getTime


class ProgressDriver:
    """Sets one bar from the playhead until stopped, the bar ends or it is no longer wanted.

    * ``percent_at(position)`` → percent (float), or None when the bar is done (segment ended);
    * ``apply(percent)`` draws it; returning False or raising stops the driver;
    * ``still_wanted()`` (optional) is asked every quarter second;
    * ``on_first()`` runs after the first ``apply`` (for example to show the driven control),
      ``on_stop()`` once when the thread ends, whatever the reason.
    """

    def __init__(
        self,
        name,
        percent_at,
        apply,
        *,
        position=None,
        still_wanted=None,
        on_first=None,
        on_stop=None,
        rate=None,
        paused=None,
        clock=None,
        wait=None,
    ):
        self.name = name
        self._percent_at = percent_at
        self._apply = apply
        self._position = position
        self._still_wanted = still_wanted
        self._on_first = on_first
        self._on_stop = on_stop
        self._rate = rate or video_frame_rate
        self._paused = paused or _is_paused
        self._clock = clock or time.monotonic
        self._stop = threading.Event()
        self._wait = wait or self._stop.wait
        self._thread = None
        self.updates = 0
        self.stopped_because = ""

    # --- lifecycle -------------------------------------------------------------

    def start(self):
        if self._thread is not None:
            return self
        self._thread = threading.Thread(target=self.run, name=self.name)
        self._thread.daemon = True
        self._thread.start()
        return self

    def stop(self, timeout=1.0):
        """Ask the thread to end and wait for it, so nothing is drawn after this returns."""
        self._stop.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout)

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # --- the loop ----------------------------------------------------------------

    def run(self):
        position_of = self._position
        try:
            if position_of is None:
                position_of = _default_position()
        except Exception as exc:
            self._finish("no player: %s" % exc)
            return
        rate = DEFAULT_RATE
        paused = False
        next_check = 0.0
        last = None
        due = self._clock()
        try:
            while not self._stop.is_set():
                now = self._clock()
                if now >= next_check:
                    if self._still_wanted is not None and not self._still_wanted():
                        self.stopped_because = "no longer wanted"
                        break
                    paused = bool(self._paused())
                    try:
                        rate = float(self._rate())
                    except Exception:
                        rate = DEFAULT_RATE
                    next_check = now + CHECK_S
                try:
                    position = float(position_of())
                except Exception:
                    self.stopped_because = "playback ended"
                    break
                position = held_position(last, position)
                last = position
                percent = self._percent_at(position)
                if percent is None:
                    self.stopped_because = "bar finished"
                    break
                if self._apply(min(100.0, max(0.0, float(percent)))) is False:
                    self.stopped_because = "control gone"
                    break
                self.updates += 1
                if self.updates == 1 and self._on_first is not None:
                    self._on_first()
                period = 1.0 / (PAUSED_RATE if paused else max(1.0, rate))
                due += period
                now = self._clock()
                if due < now - period:
                    due = now
                if self._wait(max(0.001, due - now)):
                    break
        except Exception as exc:
            self.stopped_because = "error: %s" % exc
        self._finish(self.stopped_because or "stopped")

    def _finish(self, why):
        self.stopped_because = why
        if self._on_stop is not None:
            try:
                self._on_stop()
            except Exception:
                pass
