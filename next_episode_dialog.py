# -*- coding: utf-8 -*-
"""Custom next episode popup: a WindowXMLDialog with an optional picture, time left and bar."""

from __future__ import annotations

import os
import threading
import time

import xbmcgui

from addon_skin_resolution import (
    init_window_xml_dialog,
    probe_control_ids_for_xml,
    reconcile_window_xml_skin_resolution,
    scale_skin_coord,
)
from next_episode_appearance import (
    BAR_H,
    DEFAULT_DRAFT,
    FOCUS_CLOSE,
    KEY_COUNTDOWN,
    KEY_FOCUS,
    KEY_POSITION,
    KEY_PROGRESS,
    KEY_THUMBNAIL,
    popup_layout,
    popup_origin,
    seconds_left,
    window_fraction_left,
    zoom_corner,
)
from next_episode_lookup import is_movie_item
from next_episode_state import END_CLOSE, END_GUARD_S, END_PLAY, TIMED_OUT
from next_episode_view import (
    countdown_mode,
    countdown_settings,
    countdown_text,
    fill_width,
    look_properties,
    popup_ids,
    popup_placements,
    popup_texts,
    skip_text_color,
)
from settings_utils import get_localized, log
from skip_dialog_appearance import apply_skip_dialog_caps

IDS = popup_ids()
ID_PANEL = IDS.panel
ID_BACKDROP = IDS.backdrop
ID_THUMB = IDS.thumb
ID_HEADING = IDS.heading
ID_EPISODE = IDS.episode
ID_COUNTDOWN = IDS.countdown
ID_BAR_BG = IDS.bar_bg
ID_BAR_FILL = IDS.bar_fill
ID_PLAY = IDS.play
ID_CLOSE = IDS.close
ID_PLATE_PLAY = IDS.plate_play
ID_PLATE_CLOSE = IDS.plate_close
ID_BAR_FILL_STRETCH = IDS.bar_fill_stretch  # the fill for bar textures that have no tiled version
# Three cuts of the focus texture per button; the skin shows the one that fits the texture.
FOCUS_IMAGES = {ID_PLAY: IDS.focus_play, ID_CLOSE: IDS.focus_close}

XML_NAME = "NextEpisodeDialog.xml"
_TICK_S = 0.25
_BACK_ACTIONS = (10, 92, 216)
_PREVIEW_LOOP_S = 45.0


def _text_color(addon) -> str:
    return skip_text_color(addon)


class NextEpisodeDialog(xbmcgui.WindowXMLDialog):
    next_episode: dict = {}
    still_watching = False
    timed = False
    end_action = END_CLOSE

    def __init__(self, *args, **kwargs):
        self._skin_resolution = init_window_xml_dialog(super(NextEpisodeDialog, self), args)
        self._xml_layout = args[0] if args else XML_NAME
        self.addon = kwargs.get("addon")
        self.draft = dict(DEFAULT_DRAFT)
        self.draft.update(kwargs.get("draft") or {})
        self.next_episode = kwargs.get("next_episode") or {}
        self.player = kwargs.get("player")
        self.window_start = float(kwargs.get("window_start") or 0.0)
        self.total = float(kwargs.get("total") or 0.0)
        self.preview = bool(kwargs.get("preview"))
        self.still_watching = bool(kwargs.get("still_watching"))
        # ``total`` is where the countdown ends: the end of the file, or sooner when the prompt
        # is set to stay up for a fixed time (``timed``). ``end_action`` is what happens there.
        self.timed = bool(kwargs.get("timed")) and not self.still_watching
        self.end_action = (
            END_PLAY
            if kwargs.get("end_action") == END_PLAY and not self.still_watching
            else END_CLOSE
        )
        self.result = None
        self._layout = None
        self._look = None
        self._bar_tiled = True
        self._last_fill_w = None
        self._started = time.monotonic()
        self._stop = threading.Event()
        self._closing = False
        try:
            self.setProperty("skippy_dialog_ready", "false")
            self.setProperty("skip_dialog_text_color", "FFFFFFFF")
        except Exception:
            pass

    # --- helpers -------------------------------------------------------------

    def _sc(self, value):
        return scale_skin_coord(value, getattr(self, "_skin_resolution", None))

    def _ctrl(self, cid):
        try:
            return self.getControl(cid)
        except Exception:
            return None

    def _place(self, cid, x, y, w=None, h=None):
        ctrl = self._ctrl(cid)
        if ctrl is None:
            return None
        try:
            ctrl.setPosition(self._sc(x), self._sc(y))
            if w is not None:
                ctrl.setWidth(self._sc(w))
            if h is not None:
                ctrl.setHeight(self._sc(h))
        except Exception as exc:
            log("Next episode popup: placing control %s failed: %s" % (cid, exc))
        return ctrl

    def _show(self, cid, visible):
        ctrl = self._ctrl(cid)
        if ctrl is not None:
            try:
                ctrl.setVisible(bool(visible))
            except Exception:
                pass

    # --- lifecycle -----------------------------------------------------------

    def onInit(self):
        asked = getattr(self, "_skin_resolution", None)
        locked = reconcile_window_xml_skin_resolution(
            self, asked, control_ids=probe_control_ids_for_xml(self._xml_layout)
        )
        if locked != asked:
            log("Next episode popup: skin resolution re-locked %s -> %s" % (asked, locked))
            self._skin_resolution = locked
        addon = self.addon
        draft = self.draft
        show_thumb = bool(draft.get(KEY_THUMBNAIL)) and bool(self.next_episode.get("thumb"))
        layout = popup_layout(
            thumbnail=show_thumb,
            countdown=bool(draft.get(KEY_COUNTDOWN)),
            progress=bool(draft.get(KEY_PROGRESS)),
        )
        self._layout = layout
        self._apply_look()
        texts = popup_texts(
            addon, self._caps_on(), self.next_episode, still_watching=self.still_watching
        )
        try:
            self.setProperty("next_ep_heading", texts["heading"])
            self.setProperty("next_ep_label", texts["label"])
            self.setProperty("next_ep_thumb", self.next_episode.get("thumb") or "")
            self.setProperty("next_ep_has_thumb", "true" if show_thumb else "false")
        except Exception as exc:
            log("Next episode popup: setting texts failed: %s" % exc)
        self._apply_layout(layout)
        for cid, text in ((ID_PLAY, texts["play"]), (ID_CLOSE, texts["close"])):
            ctrl = self._ctrl(cid)
            if ctrl is not None:
                try:
                    ctrl.setLabel(text)
                except Exception:
                    pass
        self._update_countdown(self._head())
        try:
            self.setProperty("skippy_dialog_ready", "true")
            # Whoever answers "still watching?" is awake: Continue is always under the cursor.
            focus = (
                ID_CLOSE
                if draft.get(KEY_FOCUS) == FOCUS_CLOSE and not self.still_watching
                else ID_PLAY
            )
            self.setFocusId(focus)
        except Exception:
            pass
        threading.Thread(target=self._watch, daemon=True).start()

    def _caps_on(self) -> bool:
        look = getattr(self, "_look", None)
        return bool(look and look.all_caps)

    def _caps(self, text):
        return apply_skip_dialog_caps(text, self._caps_on())

    def _apply_look(self):
        """Colours, focus texture and bar texture of the chosen look, as skin properties."""
        look, tiled, props = look_properties(
            self.draft, self.addon, self._sc(BAR_H), _text_color(self.addon)
        )
        self._look = look
        self._bar_tiled = tiled
        try:
            for name, value in props.items():
                self.setProperty(name, value)
        except Exception as exc:
            log("Next episode popup: applying the look failed: %s" % exc)

    def _apply_layout(self, layout):
        x, y = popup_origin(self.draft.get(KEY_POSITION), layout.panel_w, layout.panel_h)
        self._place(ID_PANEL, x, y, layout.panel_w, layout.panel_h)
        for cid, px, py, pw, ph in popup_placements(layout, IDS):
            self._place(cid, px, py, pw, ph)
        self._show(ID_COUNTDOWN, layout.countdown_y is not None)
        has_bar = layout.bar_y is not None
        self._show(ID_BAR_BG, has_bar)
        try:
            self.setProperty("next_ep_has_bar", "true" if has_bar else "false")
            # The size: the skin grows the popup from this corner ("" keeps the normal size).
            self.setProperty("next_ep_zoom", zoom_corner(self.draft))
        except Exception:
            pass
        if has_bar:
            self._last_fill_w = None

    def _head(self) -> float:
        if self.preview:
            loop = max(1.0, self.total - self.window_start)
            return self.window_start + (time.monotonic() - self._started) % loop
        try:
            return float(self.player.getTime())
        except Exception:
            return self.window_start

    def _update_countdown(self, head):
        layout = self._layout
        if layout is None:
            return
        try:
            if layout.countdown_y is not None:
                mode = countdown_mode(self.end_action, self.timed, self.still_watching)
                self.setProperty(
                    "next_ep_countdown",
                    countdown_text(
                        self.addon,
                        self._caps_on(),
                        seconds_left(head, self.total),
                        mode,
                        movie=is_movie_item(self.next_episode),
                    ),
                )
            if layout.bar_y is not None:
                tiled = getattr(self, "_bar_tiled", True)
                fill = self._ctrl(ID_BAR_FILL if tiled else ID_BAR_FILL_STRETCH)
                if fill is not None:
                    fraction = window_fraction_left(head, self.window_start, self.total)
                    # A tiled image is cropped from the left: segments disappear, none is squeezed.
                    width = fill_width(
                        tiled, fraction, self._sc(layout.bar_w), self._sc(BAR_H)
                    )
                    if width != getattr(self, "_last_fill_w", None):
                        self._last_fill_w = width
                        fill.setWidth(width)
        except Exception as exc:
            log("Next episode popup: updating the countdown failed: %s" % exc)

    def _watch(self):
        """Keep the countdown moving; close by itself when the prompt no longer applies."""
        while not self._stop.wait(_TICK_S):
            if self.preview:
                self._update_countdown(self._head())
                continue
            try:
                playing = bool(self.player.isPlaying())
            except Exception:
                playing = False
            head = self._head()
            if not playing or head < self.window_start - 1.0:
                self._finish(None)
                return
            # A prompt that runs to the end of the file stops a moment before it, where Kodi's
            # own end-of-file handling takes over; a timed one stops exactly where it was set to.
            limit = self.total if self.timed else self.total - END_GUARD_S
            if head >= limit:
                self._finish(TIMED_OUT if self.timed or self.end_action == END_PLAY else None)
                return
            self._update_countdown(head)

    def _finish(self, result):
        """Record the answer before close() so the caller can read it after doModal()."""
        if self._closing:
            return
        self._closing = True
        self.result = result
        self._stop.set()
        try:
            self.close()
        except Exception:
            pass

    # --- input ---------------------------------------------------------------

    def onClick(self, controlId):
        try:
            cid = int(controlId)
        except (TypeError, ValueError):
            return
        if cid == ID_PLAY:
            self._finish(True)
        elif cid == ID_CLOSE:
            self._finish(False)

    def onAction(self, action):
        try:
            if action.getId() in _BACK_ACTIONS:
                self._finish(False)
        except Exception:
            pass

    def onClose(self):
        self._stop.set()


def mock_episode(addon) -> dict:
    """The example episode shown by the Customize preview."""
    thumb = ""
    if addon:
        candidate = os.path.join(addon.getAddonInfo("path") or "", "fanart.png")
        if os.path.exists(candidate):
            thumb = candidate
    return {
        "season": 1,
        "episode": 2,
        "title": get_localized(addon, 47053, "Episode title"),
        "thumb": thumb,
    }


def show_next_episode_dialog(
    addon,
    player,
    next_episode,
    window_start,
    total,
    *,
    draft=None,
    preview=False,
    still_watching=False,
    timed=False,
    end_action=END_CLOSE,
):
    """
    Show the popup until it is answered or no longer applies.

    ``total`` is where the countdown ends (the end of the file, or sooner for a ``timed``
    popup) and ``end_action`` is what the caller will do then.

    Returns True (Play now), False (Close / Back), ``TIMED_OUT`` (the countdown ran out of a
    timed popup, or out of one whose end action is Play) or None (it closed by itself:
    playback stopped, the file ended, or the playhead left the window).
    """
    dialog = NextEpisodeDialog(
        XML_NAME,
        addon.getAddonInfo("path"),
        "default",
        addon=addon,
        draft=draft,
        next_episode=next_episode,
        player=player,
        window_start=window_start,
        total=total,
        preview=preview,
        still_watching=still_watching,
        timed=timed,
        end_action=end_action,
    )
    try:
        dialog.doModal()
    finally:
        dialog._stop.set()
    result = dialog.result
    del dialog
    return result


def preview_countdown(addon):
    """``(seconds, timed, end action)`` the preview loops over, from the saved prompt settings."""
    seconds, action = countdown_settings(addon)
    if seconds > 0:
        return float(seconds), True, action
    return _PREVIEW_LOOP_S, False, action


def show_preview(addon, draft) -> None:
    """Open the popup with an example episode and a looping countdown."""
    seconds, timed, action = preview_countdown(addon)
    show_next_episode_dialog(
        addon,
        None,
        mock_episode(addon),
        0.0,
        seconds,
        draft=draft,
        preview=True,
        timed=timed,
        end_action=action,
    )
