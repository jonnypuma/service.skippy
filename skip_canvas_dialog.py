# -*- coding: utf-8 -*-
"""The skip dialog of a drawn design (``skip_canvas``): same behaviour as the other layouts, but
every part is placed by Skippy, so the options can change the build."""

from __future__ import annotations

import os
import re
import threading
import time

import xbmc

import skip_canvas as cv
import skip_canvas_draw as draw
import skip_layout_dialog as layouts
import skip_layouts as sl
from addon_skin_resolution import reconcile_window_xml_skin_resolution
from segment_relations import parse_jump_info
from settings_utils import (
    addon_get_bool,
    addon_get_setting_text,
    compute_skip_seek_destination_seconds,
    get_addon,
)
from skip_dialog_appearance import (
    DIALOG_READY_PROP,
    DURATION_CONTENT_TOTAL,
    AddonSettingsReader,
    apply_jump_properties,
    countdown_mmss,
    display_segment_label,
    skip_duration_for_playhead,
)

log = layouts.log
log_always = layouts.log_always

KEY_CORNERS = "skip_canvas_corners"
KEY_CLOSE = "skip_canvas_close"
KEY_ICONS = "skip_canvas_icons"
KEY_KICKER = "skip_canvas_kicker"
KEY_NESTED = "skip_canvas_nested"
KEY_TEXT_SHADOW = "skip_canvas_text_shadow"
KEY_TEXT_SIZE = "skip_canvas_text_size"
KEY_TEXT_OUTLINE = "skip_canvas_outline"
KEY_BACKGROUND = "skip_canvas_background"
KEY_BAR_EDGES = "skip_canvas_bar_edges"
KEY_ZOOM = "skip_canvas_zoom"
KEY_ACCENT = "skip_canvas_accent"
KEY_PROGRESS = "skip_canvas_progress"
KEY_GRADIENT_ON = "skip_canvas_overlay_gradient"
KEY_GRADIENT = "skip_canvas_gradient"
# Accent colour: Auto follows the bar colour setting (the segment type's colour or the look's accent)
ACCENTS = (("Auto", ""), ("Gold", "FFE8B04B"), ("Blue", "FF7FB4FF"), ("Red", "FFFF5C6C"), ("Green", "FF5CD68A"),
           ("Teal", "FF3CC8C0"), ("Purple", "FFB48CFF"), ("White", "FFFFFFFF"))


def distance(value) -> int:
    try:
        return max(0, min(160, int(float(value))))
    except (TypeError, ValueError):
        return 64


def zoom(value) -> int:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return 100
    return min(cv.ZOOMS, key=lambda size: abs(size - number))
SIZE_NAMES = {sl.SIZE_FULL: "Full", sl.SIZE_COMPACT: "Compact", sl.SIZE_MINIMAL: "Minimal"}


def corners(value) -> str:
    return sl.normalize_choice(value, cv.looks.CORNERS, "Skin")


def colour(argb):
    """``AARRGGBB`` as ``(r, g, b, a)``, or None."""
    text = str(argb or "").strip()
    if len(text) != 8:
        return None
    try:
        return int(text[2:4], 16), int(text[4:6], 16), int(text[6:8], 16), int(text[0:2], 16)
    except ValueError:
        return None


def canvas_overlay(value) -> str:
    """The overlay choice as the drawn designs know it: the design's own, none, or one of the kinds."""
    kind = sl.normalize_overlay(value)
    return kind if kind in sl.OVERLAYS else "Auto"


def options_from(get_text, get_bool, layout, look_code, position, accent_argb=None) -> cv.Options:
    """The options of a drawn design from the settings (or from a Customize draft)."""
    return cv.Options(
        design=layout.name,
        size=SIZE_NAMES.get(layout.size, "Full"),
        look=sl.normalize_look(look_code),
        corners=corners(get_text(KEY_CORNERS, "Skin")),
        close=bool(get_bool(KEY_CLOSE, True)),
        icons=bool(get_bool(KEY_ICONS, True)),
        kicker=bool(get_bool(KEY_KICKER, True)),
        nested=bool(get_bool(KEY_NESTED, True)),
        progress=(sl.normalize_choice(get_text(KEY_PROGRESS, "Auto"), cv.PROGRESS, "Auto")
                  if get_bool("show_progress_bar", True) else "Off"),
        accent=colour(dict(ACCENTS).get(sl.normalize_choice(get_text(KEY_ACCENT, "Auto"), [a for a, _c in ACCENTS], "Auto"))
                      or accent_argb),
        zoom=zoom(get_text(KEY_ZOOM, "100")),
        overlay_gradient=bool(get_bool(KEY_GRADIENT_ON, False)),
        appear=sl.normalize_appear(get_text(sl.KEY_APPEAR, sl.APPEARS[0])),
        leave=sl.normalize_leave(get_text(sl.KEY_LEAVE, sl.LEAVES[0])),
        pulse=bool(get_bool(sl.KEY_PULSE, False)),
        gradient=sl.normalize_choice(get_text(KEY_GRADIENT, "Auto"), cv.GRADIENTS, "Auto"),
        place=cv.place_name(get_text("skip_canvas_place", "") or position),
        distance=distance(get_text("skip_canvas_distance", "64")),
        overlay=canvas_overlay(get_text(sl.KEY_OVERLAY, sl.OVERLAY_AUTO)),
        text_shadow=sl.normalize_choice(get_text(KEY_TEXT_SHADOW, "Mild"), cv.TEXT_SHADOWS, "Mild"),
        text_outline=sl.normalize_choice(get_text(KEY_TEXT_OUTLINE, "Medium"), cv.OUTLINES, "Medium"),
        text_size=cv.text_size(get_text(KEY_TEXT_SIZE, "100")),
        background=sl.normalize_choice(get_text(KEY_BACKGROUND, "None"), cv.BACKGROUNDS, "None"),
        bar_edges=sl.normalize_choice(get_text(KEY_BAR_EDGES, "Straight"), cv.BAR_EDGES, "Straight"),
    )


def playing_fanart() -> str:
    """The fanart of what is playing, for Background Fanart: the show's, else the item's own."""
    for label in ("Player.Art(tvshow.fanart)", "Player.Art(fanart)", "VideoPlayer.Art(tvshow.fanart)", "Player.Art(thumb)"):
        try:
            found = xbmc.getInfoLabel(label)
        except Exception:
            found = ""
        if found:
            return found
    return ""


_LEADING_ZERO = re.compile(r"(?<![\d:])0(\d:\d\d)")


def short_clock(text) -> str:
    """Times the way the designs write them: ``0:27``, not ``00:27``."""
    return _LEADING_ZERO.sub(lambda found: found.group(1), str(text or ""))


def texts_from(found, countdown, nested, duration, percent, now="", land="", block="") -> cv.Texts:
    """What the design writes, from the texts of ``skip_layout_dialog.texts`` and the countdown.
    ``block`` names the segment Skip lands in (Timeline writes it on its second block)."""
    found = {key: short_clock(value) for key, value in found.items()}
    countdown, nested, now, land = short_clock(countdown), short_clock(nested), short_clock(now), short_clock(land)
    return cv.Texts(
        kicker=found.get("skl_kicker", ""),
        range=found.get("skl_range", "").replace(" - ", " – "),
        ending=found.get("skl_heading", ""),
        countdown=countdown,
        nested="",
        nested_time=land,
        nested_line=nested or "",  # the whole line is one text here, the time is part of it
        chip=block,
        skip=found.get("skl_skip_short", ""),
        skip_word=found.get("skl_skip_word", "") or "Skip",
        # Timeline: the start of the segment, the playhead, where Skip lands, the end
        t0=found.get("skl_t0", ""), t1=found.get("skl_t1", ""), now=now, rest="",
        duration=duration,
        close=found.get("skl_close", ""),
        percent=percent,
    )


def tick(canvas, heading, kicker, countdown, seconds_left) -> None:
    """Write the time left wherever a drawn design shows it (the real dialog every second, the
    Studio's preview as it plays)."""
    look = canvas.look or {}
    countdown = short_clock(countdown)
    canvas.set_text("heading", ("%s %s" % (cv._caps(heading, look), countdown)).strip())
    canvas.set_text("countdown", countdown)
    # the small forms that write the time left in a line of their own
    canvas.set_text("countdown_line", "%s [B]%s[/B]" % (cv._caps(kicker, look), countdown))
    canvas.set_text("ends_line", cv._caps("%s %s" % (cv.Texts.ends_in, countdown), look))
    canvas.set_text("seconds", str(max(0, int(seconds_left))))


def warm() -> None:
    """What a drawn dialog needs before it can show, done ahead of time (at the start of playback):
    this module and the drawing code are loaded, the skin's fonts are read and kept."""
    draw.read_fonts()
    cv.draw(cv.Options(), cv.Texts())
    # the drawn Up Next popup uses the same engine: its code is loaded and one design is built as well
    try:
        import next_canvas
        import next_canvas_dialog  # noqa: F401

        next_canvas.draw(cv.Options(design="NCard"), next_canvas.Texts())
    except Exception:
        pass


class SkipCanvasDialog(layouts.SkipLayoutDialog):
    def __init__(self, *args, **kwargs):
        self._created = time.time()
        # The flag is off when the window opens (Kodi does not undo an animation whose condition already held then:
        # the dialog stayed unseen for good). The window is empty until the drawing starts, which sets the flag.
        draw.reveal()
        super(SkipCanvasDialog, self).__init__(*args, **kwargs)

    def _init_layout(self):
        init_started = time.time()
        layout = self._layout
        draw.conceal()  # as early as can be: Kodi takes a frame or two to act on it
        self._skin_resolution = reconcile_window_xml_skin_resolution(
            self, getattr(self, "_skin_resolution", None), control_ids=(cv.ID_PROBE,)
        )
        addon = get_addon()
        look = sl.look(self._look_code)
        self._minimal_mode = False
        self._compact_mode = layout.size == sl.SIZE_COMPACT
        self._combined_mode = False
        self._skip_all_caps = look.caps
        self._countdown = addon_get_bool(addon, "progress_bar_countdown", False) if addon else False
        content = (addon_get_setting_text(addon, "skip_duration_content", DURATION_CONTENT_TOTAL)
                   or DURATION_CONTENT_TOTAL).strip()
        # a drawn design has a place for the time on Skip: its own switch decides, not the wording of the button
        self._show_duration = addon_get_bool(addon, "skip_canvas_time", True) if addon else True
        self._skip_duration_live = self._show_duration and content != DURATION_CONTENT_TOTAL
        self._last_skip_dur_key = None
        self._closing = False
        self.response = None
        self._skippy_dialog_result = None
        self.player = xbmc.Player()
        self._total_duration = self.segment.end_seconds - self.segment.start_seconds
        self._start_time = time.time()
        try:
            playhead = self.player.getTime()
        except Exception:
            playhead = self.segment.start_seconds

        found = layouts.texts(addon, self.segment, playhead, False)
        remaining = countdown_mmss(self.segment.end_seconds - playhead)
        self.setProperty("countdown", remaining)
        nested = apply_jump_properties(self, addon, self.segment, all_caps=False)
        self._heading = found.get("skl_heading", "")
        self._kicker = found.get("skl_kicker", "")
        options = options_from(
            lambda key, default: addon_get_setting_text(addon, key, default),
            lambda key, default: addon_get_bool(addon, key, default),
            layout, self._look_code, self._position,
            layouts.layout_accent(addon, self._look_code, self.segment),
        )
        try:
            land = compute_skip_seek_destination_seconds(self.segment, addon)
        except Exception:
            land = None
        block = ""
        if layout.name == "Timeline":
            try:
                _kind, label = parse_jump_info(getattr(self.segment, "next_segment_info", None))
                block = display_segment_label(label) if label else ""
            except Exception:
                block = ""
        texts = texts_from(found, remaining, nested, self._duration_text(playhead), self._percent_at(playhead) or 0.0,
                           now=sl.clock(playhead), land=sl.clock(land) if land else "", block=block)
        if options.background == "Fanart":
            # Background Fanart: the picture of what is playing (a show's own fanart before the episode's)
            texts.fanart = playing_fanart()
        folder = "720" if str(self._skin_resolution).startswith("720") else "1080"
        media = os.path.join(addon.getAddonInfo("path"), "resources", "skins", "default", "media")
        before_canvas = time.time()
        self._canvas = draw.Canvas(self, folder, media)
        fonts_ms = int((time.time() - before_canvas) * 1000)
        self._canvas.draw(options, texts)
        self._canvas.timing.update(prep_ms=int((before_canvas - init_started) * 1000), fonts_ms=fonts_ms,
                                   open_ms=int((init_started - self._created) * 1000))
        self._last_progress = None
        self._apply_progress(self._percent_at(playhead) or 0.0, playhead)

        threading.Thread(target=self._monitor_segment_end, daemon=True).start()
        # Still unseen: the focus goes where it starts and the buttons take its colours, so that the dialog
        # comes complete and in one piece. Then it is shown, and its parts come as Appears says.
        first = cv.ID_SKIP
        if options.close and addon_get_setting_text(addon, "skip_canvas_focus", "Skip") == "Close" and layout.has_close:
            first = cv.ID_CLOSE
        try:
            self.setFocusId(first)
            self._canvas.set_focus("close" if first == cv.ID_CLOSE else "skip")
        except Exception as exc:
            log("⚠️ Skip canvas focus: %s" % exc)
        # Uncovered first (every part is still at nothing: each waits for "ready"), then "ready": the parts come
        # from nothing, all together, the way Appears says.
        draw.settle()
        draw.reveal()
        self.setProperty(DIALOG_READY_PROP, "true")
        self._start_progress_driver(addon)
        log_always("Skip dialog drawn: %s %s (%s, %s) %s" % (options.design, options.size, options.look, options.place,
                                                              self._canvas.timing))

    def _duration_text(self, playhead) -> str:
        if not getattr(self, "_show_duration", False):
            return ""
        addon = get_addon()
        try:
            # already a text in the chosen duration format ("1m 30s", "1:30", ...)
            return short_clock(skip_duration_for_playhead(playhead, self.segment, AddonSettingsReader(addon)) or "")
        except Exception:
            return ""

    # ---------------------------------------------------------------- progress
    def _apply_progress(self, percent, position=None):
        canvas = getattr(self, "_canvas", None)
        if canvas is None:
            return
        key = int(round(float(percent) * 10))
        if key == self._last_progress:
            return
        self._last_progress = key
        canvas.set_percent(percent)
        if self._layout.name == "Timeline":
            try:
                if position is None:
                    position = self.player.getTime()
                canvas.set_text("now", short_clock(sl.clock(position)))
            except Exception:
                pass

    def _place_jump_mark(self):
        return

    def _refresh_countdown_label(self):
        canvas = getattr(self, "_canvas", None)
        if canvas is None:
            return
        try:
            left = max(0.0, self.segment.end_seconds - self.player.getTime())
            tick(canvas, self._heading, getattr(self, "_kicker", ""), self.getProperty("countdown"), left)
            # the beat of the last seconds (Pulse)
            beating = "true" if left <= cv.PULSE_SECONDS else ""
            if beating != getattr(self, "_beating", ""):
                self._beating = beating
                self.setProperty("skippy_dialog_pulse", beating)
        except Exception:
            pass

    def close(self):
        """Leave the way Leaves says, then close."""
        canvas = getattr(self, "_canvas", None)
        if canvas is not None and not getattr(self, "_left", False):
            self._left = True
            try:
                self.setProperty("skippy_dialog_out", "true")
                xbmc.sleep(int(canvas.leave_ms) + 30)
            except Exception:
                pass
        draw.reveal()  # never leave the flag behind
        super(SkipCanvasDialog, self).close()

    def _refresh_skip_duration_label(self, playhead):
        if not getattr(self, "_skip_duration_live", False) or getattr(self, "_canvas", None) is None:
            return
        text = self._duration_text(playhead)
        if text != self._last_skip_dur_key:
            self._last_skip_dur_key = text
            self._canvas.set_text("skip_time", text)

    # ------------------------------------------------------------------- input
    def onAction(self, action):
        super(SkipCanvasDialog, self).onAction(action)
        self._follow_focus()

    def onFocus(self, controlId):
        self._follow_focus()

    def _follow_focus(self):
        canvas = getattr(self, "_canvas", None)
        if canvas is None or getattr(self, "_closing", False):
            return
        try:
            canvas.set_focus("close" if self.getFocusId() == cv.ID_CLOSE else "skip")
        except Exception:
            pass

    def onClick(self, controlId):
        cid = layouts.base._normalize_control_id(controlId)
        if cid == cv.ID_SKIP:
            result = compute_skip_seek_destination_seconds(self.segment, get_addon())
            log("🖱️ User clicked skip → skipping to %ss" % result)
        else:
            result = False
            log("🖱️ User clicked close → declining skip (controlId=%s)" % cid)
        self._finish_dialog(result)
