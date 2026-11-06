# -*- coding: utf-8 -*-
"""Custom next episode popup: a WindowXMLDialog with an optional picture, time left and bar."""

from __future__ import annotations

import os
import threading
import time

import xbmc
import xbmcgui

from addon_skin_resolution import (
    init_window_xml_dialog,
    probe_control_ids_for_xml,
    reconcile_window_xml_skin_resolution,
    scale_skin_coord,
)
from next_episode_appearance import (
    BAR_H,
    BUTTON_GAP,
    BUTTON_H,
    COUNTDOWN_H,
    DEFAULT_DRAFT,
    EPISODE_H,
    FOCUS_CLOSE,
    HEADING_H,
    KEY_COUNTDOWN,
    KEY_FOCUS,
    KEY_POSITION,
    KEY_PROGRESS,
    KEY_THUMBNAIL,
    PAD,
    THUMB_H,
    THUMB_W,
    bar_fill_width,
    popup_layout,
    popup_origin,
    seconds_left,
    window_fraction_left,
)
from next_episode_lookup import episode_label
from next_episode_look import resolve_popup_look
from next_episode_state import END_GUARD_S
from settings_utils import addon_get_setting_text, get_localized, log
from skip_dialog_appearance import (
    apply_skip_dialog_caps,
    countdown_mmss,
    progress_tiled_variant,
    resolve_font_color_argb,
)

ID_PANEL = 5000
ID_BACKDROP = 5001
ID_THUMB = 5002
ID_HEADING = 5003
ID_EPISODE = 5004
ID_COUNTDOWN = 5005
ID_BAR_BG = 5006
ID_BAR_FILL = 5007
ID_PLAY = 5008
ID_CLOSE = 5009
ID_PLATE_PLAY = 5010
ID_PLATE_CLOSE = 5011
ID_BAR_FILL_STRETCH = 5012  # the fill for bar textures that have no tiled version
# Three cuts of the focus texture per button; the skin shows the one that fits the texture.
FOCUS_IMAGES = {ID_PLAY: (5013, 5014, 5015), ID_CLOSE: (5016, 5017, 5018)}

XML_NAME = "NextEpisodeDialog.xml"
_TICK_S = 0.25
_BACK_ACTIONS = (10, 92, 216)
_PREVIEW_LOOP_S = 45.0


def _text_color(addon) -> str:
    raw = addon_get_setting_text(addon, "skip_dialog_font_color", "FFFFFFFF") or "FFFFFFFF"
    return resolve_font_color_argb(raw.strip(), fallback="FFFFFFFF")


class NextEpisodeDialog(xbmcgui.WindowXMLDialog):
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
        try:
            self.setProperty(
                "next_ep_heading",
                self._caps(
                    get_localized(addon, 47070, "Still watching?")
                    if self.still_watching
                    else get_localized(addon, 47020, "Play next episode?")
                ),
            )
            self.setProperty("next_ep_label", self._caps(episode_label(self.next_episode)))
            self.setProperty("next_ep_thumb", self.next_episode.get("thumb") or "")
            self.setProperty("next_ep_has_thumb", "true" if show_thumb else "false")
        except Exception as exc:
            log("Next episode popup: setting texts failed: %s" % exc)
        self._apply_layout(layout)
        if self.still_watching:
            labels = (
                (ID_PLAY, get_localized(addon, 47071, "Continue")),
                (ID_CLOSE, get_localized(addon, 47072, "Stop")),
            )
        else:
            labels = (
                (ID_PLAY, get_localized(addon, 47050, "Play now")),
                (ID_CLOSE, get_localized(addon, 40001, "Close")),
            )
        for cid, text in labels:
            ctrl = self._ctrl(cid)
            if ctrl is not None:
                try:
                    ctrl.setLabel(self._caps(text))
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

    def _caps(self, text):
        look = getattr(self, "_look", None)
        return apply_skip_dialog_caps(text, bool(look and look.all_caps))

    def _apply_look(self):
        """Colours, focus texture and bar texture of the chosen look, as skin properties."""
        look = resolve_popup_look(self.draft, self.addon)
        self._look = look
        tiled = progress_tiled_variant(look.bar_texture, self._sc(BAR_H))
        self._bar_tiled = bool(tiled)
        text = (
            resolve_font_color_argb(look.text_color, fallback="FFFFFFFF")
            if look.text_color
            else _text_color(self.addon)
        )
        try:
            for name, value in (
                ("skip_dialog_text_color", text),
                ("next_ep_card_color", look.card_color),
                ("next_ep_heading_color", look.heading_color),
                ("next_ep_focus_texture", look.focus_texture),
                ("next_ep_focus_border", look.focus_border),
                ("next_ep_bar_tiled", "true" if tiled else "false"),
                ("next_ep_bar_tiled_texture", tiled or ""),
                ("next_ep_bar_texture", look.bar_texture),
            ):
                self.setProperty(name, value)
        except Exception as exc:
            log("Next episode popup: applying the look failed: %s" % exc)

    def _apply_layout(self, layout):
        x, y = popup_origin(self.draft.get(KEY_POSITION), layout.panel_w, layout.panel_h)
        self._place(ID_PANEL, x, y, layout.panel_w, layout.panel_h)
        self._place(ID_BACKDROP, 0, 0, layout.panel_w, layout.panel_h)
        if layout.thumbnail:
            self._place(ID_THUMB, PAD, PAD, THUMB_W, THUMB_H)
        self._place(ID_HEADING, layout.text_x, layout.heading_y, layout.text_w, HEADING_H)
        self._place(ID_EPISODE, layout.text_x, layout.episode_y, layout.text_w, EPISODE_H)
        has_countdown = layout.countdown_y is not None
        self._show(ID_COUNTDOWN, has_countdown)
        if has_countdown:
            self._place(ID_COUNTDOWN, PAD, layout.countdown_y, layout.bar_w, COUNTDOWN_H)
        has_bar = layout.bar_y is not None
        self._show(ID_BAR_BG, has_bar)
        try:
            self.setProperty("next_ep_has_bar", "true" if has_bar else "false")
        except Exception:
            pass
        if has_bar:
            self._place(ID_BAR_BG, PAD, layout.bar_y, layout.bar_w, BAR_H)
            self._place(ID_BAR_FILL, PAD, layout.bar_y, layout.bar_w, BAR_H)
            self._place(ID_BAR_FILL_STRETCH, PAD, layout.bar_y, layout.bar_w, BAR_H)
            self._last_fill_w = None
        second_x = PAD + layout.button_w + BUTTON_GAP
        for cid, x_pos in (
            (ID_PLATE_PLAY, PAD),
            (ID_PLAY, PAD),
            (ID_PLATE_CLOSE, second_x),
            (ID_CLOSE, second_x),
        ):
            self._place(cid, x_pos, layout.buttons_y, layout.button_w, BUTTON_H)
        for cid, x_pos in ((ID_PLAY, PAD), (ID_CLOSE, second_x)):
            for image_id in FOCUS_IMAGES[cid]:
                self._place(image_id, x_pos, layout.buttons_y, layout.button_w, BUTTON_H)

    def _head(self) -> float:
        if self.preview:
            return self.window_start + (time.monotonic() - self._started) % _PREVIEW_LOOP_S
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
                self.setProperty(
                    "next_ep_countdown",
                    self._caps(
                        get_localized(
                            self.addon,
                            47051,
                            "Episode ends in %s",
                            countdown_mmss(seconds_left(head, self.total)),
                        )
                    ),
                )
            if layout.bar_y is not None:
                tiled = getattr(self, "_bar_tiled", True)
                fill = self._ctrl(ID_BAR_FILL if tiled else ID_BAR_FILL_STRETCH)
                if fill is not None:
                    fraction = window_fraction_left(head, self.window_start, self.total)
                    bar_w = self._sc(layout.bar_w)
                    if tiled:
                        # Crop a tiled image from the left: segments disappear, none is squeezed.
                        width = bar_fill_width(fraction, bar_w, self._sc(BAR_H))
                    else:
                        width = int(round(fraction * bar_w))
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
            if (
                not playing
                or head >= self.total - END_GUARD_S
                or head < self.window_start - 1.0
            ):
                self._finish(None)
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
):
    """
    Show the popup until it is answered or no longer applies.

    Returns True (Play now), False (Close / Back) or None (it closed by itself:
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
    )
    try:
        dialog.doModal()
    finally:
        dialog._stop.set()
    result = dialog.result
    del dialog
    return result


def show_preview(addon, draft) -> None:
    """Open the popup with an example episode and a looping countdown."""
    show_next_episode_dialog(
        addon,
        None,
        mock_episode(addon),
        0.0,
        _PREVIEW_LOOP_S,
        draft=draft,
        preview=True,
    )
