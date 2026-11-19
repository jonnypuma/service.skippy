# -*- coding: utf-8 -*-
"""The next episode popup in one of the layouts of ``next_layouts.py`` (every layout but the card).

It is ``next_episode_dialog.NextEpisodeDialog`` for everything that matters to the caller: the
answer, the countdown, when it closes by itself. Only the drawing differs: a layout's skin file
takes its texts, colours and pictures from window properties, and this class moves two things:
the layout to its corner and the progress (a line that shrinks, or a ring).
"""

from __future__ import annotations

import threading

import next_episode_dialog as base
import next_layouts as nl
import skip_layouts as sl
from addon_skin_resolution import reconcile_window_xml_skin_resolution
from next_episode_appearance import KEY_FOCUS, KEY_POSITION, FOCUS_CLOSE, seconds_left, window_fraction_left
from next_episode_lookup import is_movie_item
from next_episode_view import countdown_mode, countdown_text, popup_texts
from settings_utils import log
from smooth_progress import ProgressDriver


def layout_for(draft):
    """The layout file to draw for a draft, or None for the classic card."""
    name = nl.normalize_layout((draft or {}).get(nl.KEY_LAYOUT))
    return None if nl.is_card(name) else nl.get(name)


def look_code(draft) -> str:
    return sl.normalize_look((draft or {}).get(nl.KEY_LAYOUT_LOOK))


def look_properties(code, resolution, bare=False) -> dict:
    """The skin properties of a look for a popup layout (those of the skip dialog layouts, and the
    dark ring behind the countdown of Play ring)."""
    props = dict(sl.properties(code, resolution, bare))
    props["skl_ring_back"] = "59FFFFFF"
    return props


def texts(addon, caps, episode, still_watching=False) -> dict:
    found = popup_texts(addon, caps, episode, still_watching=still_watching)
    return {"nl_heading": found["heading"], "nl_label": found["label"], "nl_play": found["play"], "nl_close": found["close"]}


class NextLayoutDialog(base.NextEpisodeDialog):
    def __init__(self, *args, **kwargs):
        self._nl_layout = kwargs.pop("layout")
        super(NextLayoutDialog, self).__init__(*args, **kwargs)
        self._nl_last = None

    def onInit(self):
        layout = self._nl_layout
        self._skin_resolution = reconcile_window_xml_skin_resolution(
            self, getattr(self, "_skin_resolution", None), control_ids=(nl.ID_PROBE,)
        )
        code = look_code(self.draft)
        caps = sl.look(code).caps
        self._nl_caps = caps
        position = self.draft.get(KEY_POSITION)
        try:
            bare = self._nl_layout.name in nl.BARE_LAYOUTS
            for name, value in look_properties(code, self._skin_resolution, bare).items():
                self.setProperty(name, value)
            self.setProperty("skl_top", "true" if sl.is_top(position) else "false")
            for name, value in texts(self.addon, caps, self.next_episode, self.still_watching).items():
                self.setProperty(name, value)
            self.setProperty("nl_picture", nl.picture(layout, self.next_episode))
            self.setProperty("nl_logo", (self.next_episode or {}).get("logo") or "")
            self._nl_queue = []
            if layout.name == "Queue":
                self._fill_queue()
            left, top = nl.origin(layout, position)
            self.getControl(nl.ID_ROOT).setPosition(self._sc(left), self._sc(top))
        except Exception as exc:
            log("Next episode popup layout: set-up failed: %s" % exc)
        head = self._head()
        self._update_countdown(head)
        self._set_bar_percent(self._bar_percent(head) or 0.0)
        try:
            self.setProperty("skippy_dialog_ready", "true")
            focus = nl.ID_CLOSE if self.draft.get(KEY_FOCUS) == FOCUS_CLOSE and not self.still_watching else nl.ID_PLAY
            self.setFocusId(focus)
        except Exception:
            pass
        self._start_progress_driver()
        threading.Thread(target=self._watch, daemon=True).start()

    def _fill_queue(self):
        """Queue: the next episode and the two after it as cards (the preview shows three of its one)."""
        from next_episode_lookup import episode_label, find_queue

        queue = find_queue(self.next_episode, nl.QUEUE_SIZE)
        if len(queue) == 1 and getattr(self, "preview", False):
            queue = queue * nl.QUEUE_SIZE
        self._nl_queue = queue
        for index in range(nl.QUEUE_SIZE):
            episode = queue[index] if index < len(queue) else None
            label = (episode_label(episode) or episode.get("title") or " ") if episode else ""
            if episode and getattr(self, "_nl_caps", False):
                label = label.upper()
            self.setProperty("nl_q%d_label" % index, label)
            self.setProperty("nl_q%d_thumb" % index, (episode.get("thumb") or episode.get("fanart") or "") if episode else "")

    # ----------------------------------------------------------------- progress
    def _set_bar_percent(self, pct):
        layout = self._nl_layout
        if layout.progress == sl.PROGRESS_RING:
            frame = sl.ring_frame(pct)
            if frame != self._nl_last:
                self._nl_last = frame
                self.setProperty("nl_ring", frame)
            return
        width = int(self._sc(nl.fill_width(layout, pct)))
        if width != self._nl_last:
            self._nl_last = width
            self.getControl(nl.ID_BAR_FILL).setWidth(width)

    def _start_progress_driver(self):
        if getattr(self, "_closing", False):
            return
        self._progress_driver = ProgressDriver(
            "skippy-next-layout-progress",
            self._bar_percent,
            self._set_bar_percent,
            position=self._head,
            still_wanted=lambda: not getattr(self, "_closing", False),
        ).start()

    def _update_countdown(self, head, bar=True):
        try:
            left = seconds_left(head, self.total)
            mode = countdown_mode(self.end_action, self.timed, self.still_watching)
            self.setProperty(
                "next_ep_countdown",
                countdown_text(self.addon, getattr(self, "_nl_caps", False), left, mode, movie=is_movie_item(self.next_episode)),
            )
            self.setProperty("nl_seconds", str(int(max(0.0, left))))
            if bar:
                self._set_bar_percent(100.0 * window_fraction_left(head, self.window_start, self.total))
        except Exception as exc:
            log("Next episode popup layout: updating the countdown failed: %s" % exc)

    # -------------------------------------------------------------------- input
    def onClick(self, controlId):
        try:
            cid = int(controlId)
        except (TypeError, ValueError):
            return
        if cid in nl.QUEUE_IDS[1:] and getattr(self, "_nl_queue", None):
            # a later card of the Queue: that episode becomes the one to play
            index = nl.QUEUE_IDS.index(cid)
            if index < len(self._nl_queue) and self._nl_queue[index] is not self.next_episode:
                chosen = dict(self._nl_queue[index])
                self.next_episode.clear()
                self.next_episode.update(chosen)
            self._finish(True)
        elif cid == nl.ID_PLAY:
            self._finish(True)
        elif cid == nl.ID_CLOSE:
            self._finish(False)
