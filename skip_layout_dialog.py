# -*- coding: utf-8 -*-
"""The skip dialog in one of the layouts of ``skip_layouts.py`` (every layout but the classic card).

It is the same dialog as ``skipdialog.SkipDialog`` for everything that matters to the service: the
answer it gives, where Skip lands, the end of the segment, pause and the timeout all come from
that class. Only the drawing differs: the skin file of a layout holds no text, colour or picture
of its own, so this class fills window properties and moves three things: the layout to its
corner, the fill of the progress, and (Timeline) the playhead.
"""

from __future__ import annotations

import threading
import time

import xbmc

import skip_layouts as sl
import skipdialog as base
from addon_skin_resolution import reconcile_window_xml_skin_resolution
from settings_utils import (
    addon_get_bool,
    addon_get_setting_text,
    compute_skip_seek_destination_seconds,
    get_addon,
    get_localized,
)
from skip_dialog_appearance import (
    DIALOG_READY_PROP,
    DURATION_CONTENT_TOTAL,
    AddonSettingsReader,
    apply_jump_properties,
    apply_skip_dialog_caps,
    build_skip_button_label,
    countdown_mmss,
    display_segment_label,
    ending_text_for_segment,
    skip_duration_for_playhead,
    skip_format_includes_duration,
)
from smooth_progress import ProgressDriver, segment_percent

log = base.log
log_always = base.log_always

FORMAT_WORD = "Skip"
FORMAT_SHORT = "Skip + Type"


def layout_for(addon):
    """The layout file to draw, or None for the classic card."""
    mode = (addon_get_setting_text(addon, "skip_dialog_mode", "CompactFull") or "CompactFull").strip()
    name = sl.normalize_layout(addon_get_setting_text(addon, sl.KEY_LAYOUT, sl.DEFAULT_LAYOUT))
    if sl.is_card(name):
        return None
    return sl.get(name, sl.size_for_mode(mode))


def layout_accent(addon, look_code, segment, settings=None, bare=False) -> str:
    """The colour of the progress: the segment type's (the default) or the look's accent."""
    from segment_editor_layout import CHIP_COLORS, chip_key

    if settings is not None:
        choice = settings.get_text(sl.KEY_BAR_COLOR, sl.BAR_TYPE)
    else:
        choice = addon_get_setting_text(addon, sl.KEY_BAR_COLOR, sl.BAR_TYPE)
    rgb = CHIP_COLORS.get(chip_key(getattr(segment, "segment_type_label", "")), "")
    return sl.accent(look_code, choice, rgb, bare)


def apply_overlay(window, get_control, scale, layout, position, kind, ids=(sl.ID_OVERLAY, sl.ID_OVERLAY_PLAIN)):
    """Show the shade of ``kind`` behind ``layout`` (or none): its picture as a window property, its
    box on the control. ``scale`` turns 720p units into those of the skin folder in use."""
    found = sl.overlay_box(layout, position, kind)
    window.setProperty("skl_overlay9", found["texture"] if found and found["nine"] else "")
    window.setProperty("skl_overlay", found["texture"] if found and not found["nine"] else "")
    if not found:
        return
    control = get_control(ids[0] if found["nine"] else ids[1])
    if control:
        left, top, width, height = (int(scale(v)) for v in found["box"])
        control.setPosition(left, top)
        control.setWidth(width)
        control.setHeight(height)


def playing_poster() -> str:
    """The poster of what is playing: the show's for an episode, else the film's; a wide picture as
    the last resort, so the Poster layout never has an empty frame while there is any art."""
    for label in ("Player.Art(tvshow.poster)", "Player.Art(season.poster)", "Player.Art(poster)",
                  "Player.Art(thumb)", "Player.Icon"):
        try:
            value = xbmc.getInfoLabel(label)
        except Exception:
            value = ""
        if value:
            return value
    return ""


def texts(addon, segment, playhead, caps, settings=None) -> dict:
    """The words of the dialog as window properties. ``settings`` is a reader of the skip dialog
    settings (the Customize screen passes its draft); the add-on's own by default."""
    settings = settings or AddonSettingsReader(addon)
    fmt = settings.get_text("skip_button_format", FORMAT_SHORT) or FORMAT_SHORT
    duration = skip_duration_for_playhead(playhead, segment, settings)

    def up(text):
        return apply_skip_dialog_caps(text or "", caps)

    raw_type = getattr(segment, "segment_type_label", "") or ""
    heading = ending_text_for_segment(addon, segment).rstrip().rstrip(":")
    return {
        "skl_skip": up(build_skip_button_label(segment, fmt, duration, addon)),
        "skl_skip_short": up(build_skip_button_label(segment, FORMAT_SHORT, duration, addon)),
        "skl_skip_word": up(build_skip_button_label(segment, FORMAT_WORD, duration, addon)),
        "skl_close": up(get_localized(addon, 40001, "Close")),
        "skl_kicker": up(display_segment_label(raw_type) or raw_type),
        "skl_range": "%s - %s" % (sl.clock(segment.start_seconds), sl.clock(segment.end_seconds)),
        "skl_heading": up(heading),
        "skl_t0": sl.clock(segment.start_seconds),
        "skl_t1": sl.clock(segment.end_seconds),
    }


class SkipLayoutDialog(base.SkipDialog):
    def __init__(self, *args, **kwargs):
        self._layout = kwargs.pop("layout")
        self._look_code = sl.normalize_look(kwargs.pop("look", sl.DEFAULT_LOOK))
        self._position = kwargs.pop("position", "BottomRight")
        super(SkipLayoutDialog, self).__init__(*args, **kwargs)
        # The base class leaves the bar alone while this is set: this class draws the progress.
        self._own_progress = True
        self._last_progress = None

    # ------------------------------------------------------------------ set-up
    def onInit(self):
        if not getattr(self, "segment", None):
            log("❌ Segment not set — aborting dialog init")
            self.close()
            return
        try:
            self._init_layout()
        except Exception as exc:
            log_always("❌ Skip layout dialog failed to start (%s): %s" % (type(exc).__name__, exc))
            try:
                self._finish_dialog(None)
            except Exception:
                pass

    def _init_layout(self):
        layout = self._layout
        self._skin_resolution = reconcile_window_xml_skin_resolution(
            self, getattr(self, "_skin_resolution", None), control_ids=(sl.ID_PROBE,)
        )
        addon = get_addon()
        look = sl.look(self._look_code)
        self._minimal_mode = False
        self._compact_mode = layout.size == sl.SIZE_COMPACT
        self._combined_mode = False
        self._skip_all_caps = look.caps
        self._countdown = addon_get_bool(addon, "progress_bar_countdown", False) if addon else False
        fmt = addon_get_setting_text(addon, "skip_button_format", FORMAT_SHORT) or FORMAT_SHORT
        content = (addon_get_setting_text(addon, "skip_duration_content", DURATION_CONTENT_TOTAL)
                   or DURATION_CONTENT_TOTAL).strip()
        self._skip_fmt = fmt
        self._skip_duration_live = skip_format_includes_duration(fmt) and content != DURATION_CONTENT_TOTAL
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

        bare = sl.is_bare(self._layout.name)
        for name, value in sl.properties(self._look_code, self._skin_resolution, bare).items():
            self.setProperty(name, value)
        self.setProperty("skl_accent", layout_accent(addon, self._look_code, self.segment, bare=bare))
        self.setProperty("skl_poster", playing_poster())
        self.setProperty("skl_top", "true" if sl.is_top(self._position) else "false")
        for name, value in texts(addon, self.segment, playhead, look.caps).items():
            self.setProperty(name, value)
        remaining = countdown_mmss(self.segment.end_seconds - playhead)
        self.setProperty("countdown", remaining)
        self.setProperty("skl_seconds", sl.seconds_left(remaining))
        apply_jump_properties(self, addon, self.segment, all_caps=look.caps)

        left, top = sl.origin(layout, self._position)
        self.getControl(sl.ID_ROOT).setPosition(self._skin_sc(left), self._skin_sc(top))
        try:
            apply_overlay(self, self.getControl, self._skin_sc, layout, self._position,
                          addon_get_setting_text(addon, sl.KEY_OVERLAY, sl.OVERLAY_NONE))
        except Exception as exc:
            log("⚠️ Skip layout overlay: %s" % exc)
        self.setProperty("skl_in", sl.appear_value(
            layout, self._position, addon_get_setting_text(addon, sl.KEY_APPEAR, sl.APPEARS[0])))
        self.setProperty("skl_out", sl.normalize_leave(addon_get_setting_text(addon, sl.KEY_LEAVE, sl.LEAVES[0])))
        self._pulse_on = addon_get_bool(addon, sl.KEY_PULSE, False) if addon else False
        self._place_jump_mark()
        self._apply_progress(self._percent_at(playhead) or 0.0, playhead)

        threading.Thread(target=self._monitor_segment_end, daemon=True).start()
        self.setProperty(DIALOG_READY_PROP, "true")
        self._start_progress_driver(addon)
        xbmc.sleep(50)  # the group must be visible before it can take the focus
        try:
            self.setFocusId(sl.ID_SKIP)
        except Exception as exc:
            log("⚠️ Skip layout focus: %s" % exc)
        log("✅ Skip layout %s (%s, %s) shown" % (layout.xml, self._look_code, self._position))

    # ---------------------------------------------------------------- progress
    def _percent_at(self, position):
        start, end = float(self.segment.start_seconds), float(self.segment.end_seconds)
        if position is None or position >= end:
            return None
        # The Timeline shows where the playhead is, so it never counts down.
        countdown = self._countdown and self._layout.progress != sl.PROGRESS_TIMELINE
        return segment_percent(position, start, end, countdown)

    def _apply_progress(self, percent, position=None):
        layout = self._layout
        if layout.progress == sl.PROGRESS_RING:
            frame = sl.ring_frame(percent)
            if frame != self._last_progress:
                self._last_progress = frame
                self.setProperty("skl_ring", frame)
            return
        left, top, width, height = sl.fill_size(layout, percent)
        box = tuple(int(self._skin_sc(v)) for v in (left, top, width, height))
        if box == self._last_progress:
            return
        self._last_progress = box
        fill = self.getControl(sl.ID_BAR_FILL)
        if layout.progress == sl.PROGRESS_TILE:
            fill.setPosition(box[0], box[1])
            fill.setHeight(box[3])
        fill.setWidth(box[2])
        if layout.progress == sl.PROGRESS_TIMELINE:
            head = self.getControl(sl.ID_PLAYHEAD)
            head.setPosition(box[0] + box[2] - 1, head.getY())

    def _place_jump_mark(self):
        if self._layout.progress != sl.PROGRESS_TIMELINE:
            return
        try:
            jump = compute_skip_seek_destination_seconds(self.segment, get_addon())
        except Exception:
            jump = None
        parts = sl.timeline_parts(
            self._layout, self.segment.start_seconds, self.segment.end_seconds, self.segment.start_seconds, jump
        )
        mark = self.getControl(sl.ID_NESTED)
        mark.setPosition(int(self._skin_sc(parts["jump_left"])), mark.getY())
        mark.setWidth(int(self._skin_sc(parts["jump_width"])))

    def _start_progress_driver(self, addon):
        if getattr(self, "_closing", False):
            return
        self._progress_driver = ProgressDriver(
            "skippy-skip-layout-progress",
            self._percent_at,
            self._apply_progress,
            position=self.player.getTime,
            still_wanted=lambda: not getattr(self, "_closing", False),
        ).start()

    # ------------------------------------------------- what the base loop calls
    def _refresh_countdown_label(self):
        try:
            countdown = self.getProperty("countdown")
            self.setProperty("skl_seconds", sl.seconds_left(countdown))
            self.setProperty("skl_pulse", "true" if sl.pulses(countdown, getattr(self, "_pulse_on", False)) else "")
        except Exception:
            pass

    def _refresh_skip_duration_label(self, playhead):
        if not getattr(self, "_skip_duration_live", False):
            return
        addon = get_addon()
        if not addon:
            return
        duration = skip_duration_for_playhead(playhead, self.segment, AddonSettingsReader(addon))
        if duration == self._last_skip_dur_key:
            return
        self._last_skip_dur_key = duration
        self.setProperty(
            "skl_skip",
            apply_skip_dialog_caps(
                build_skip_button_label(self.segment, self._skip_fmt, duration, addon), self._skip_all_caps
            ),
        )

    def _apply_dialog_text_colors(self):
        return  # every colour is a window property of the look

    # ------------------------------------------------------------------- input
    def onClick(self, controlId):
        cid = base._normalize_control_id(controlId)
        if cid == sl.ID_SKIP:
            result = compute_skip_seek_destination_seconds(self.segment, get_addon())
            log("🖱️ User clicked skip → skipping to %ss" % result)
        else:
            result = False
            log("🖱️ User clicked close → declining skip (controlId=%s)" % cid)
        self._finish_dialog(result)

    def onClose(self):
        self._stop_progress_driver()
