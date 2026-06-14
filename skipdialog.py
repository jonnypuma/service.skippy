import os
import threading
import time
import unicodedata

import xbmc
import xbmcaddon
import xbmcgui

from addon_skin_resolution import init_window_xml_dialog, scale_skin_coord
from settings_utils import (
    SKIPPY_LOG_ERROR_ONLY,
    addon_get_bool,
    addon_get_int,
    addon_get_setting_text,
    skippy_log_effective_detail_level,
)

# Define a global variable to cache the addon object
_addon = None

FULL_SKIP_BUTTON_IDS = (3012, 3015, 3016)

_FULL_SKIP_PANEL_GROUP_ID = 3080
_FULL_SKIP_PANEL_BACKDROP_ID = 3081

FULL_SKIP_PROGRESS_BAR_WIDTH = 370  # base width; use _skip_sc() at runtime for 1080i


def _skip_sc(value):
    return scale_skin_coord(value)
_SMOOTH_PROGRESS_BG_ID = 3030
_SMOOTH_PROGRESS_FILL_ID = 3031
# Skin <visible> on 3030/3031 reads this; Python setVisible on images is unreliable vs XML.
_SMOOTH_BAR_WINDOW_PROP = "skippy_smooth_bar"


def _ascii_log_text(msg):
    return unicodedata.normalize("NFKD", str(msg)).encode("ascii", "ignore").decode("ascii")


def _full_skip_focus_id(hide_close, hide_skip_icon):
    """3012 is hidden when the close button is hidden; match Full dialog XML visibility."""
    if hide_close:
        return 3016 if hide_skip_icon else 3015
    return 3012

# Human-readable fallbacks if settings.xml ever omits optionvalues (older installs).
_SKIP_DIALOG_FONT_COLOR_ARGB = {
    "white": "FFFFFFFF",
    "light grey": "FF8E8E8E",
    "light gray": "FF8E8E8E",
    "grey": "FF6E6E6E",
    "gray": "FF6E6E6E",
    "dark grey": "FF3D3D3D",
    "dark gray": "FF3D3D3D",
    "black": "FF000000",
    "blue": "FF1976D2",
    "red": "FFE5392F",
    "green": "FF43A047",
    "aquamarine": "FF00ACC1",
    "pink": "FFE91E63",
    "purple": "FF8E24AA",
    "peach": "FFFF8A65",
    "orange": "FFEF6C00",
    "yellow": "FFF9A825",
}

# labelenum may store a numeric index string on some Kodi builds.
_SKIP_DIALOG_FONT_COLOR_INDEXED = (
    "FFFFFFFF",
    "FF8E8E8E",
    "FF6E6E6E",
    "FF3D3D3D",
    "FF000000",
    "FF1976D2",
    "FFE5392F",
    "FF43A047",
    "FF00ACC1",
    "FFE91E63",
    "FF8E24AA",
    "FFFF8A65",
    "FFEF6C00",
    "FFF9A825",
)


def _skip_dialog_font_color_argb(addon):
    """Resolve addon setting to AARRGGBB. Avoid defaulting to white (invisible on light plates)."""
    # Safe default matches old unfocused-ish tone, visible on white minimal plates.
    fallback = "FF6E6E6E"
    if not addon:
        return fallback
    raw = (addon_get_setting_text(addon, "skip_dialog_font_color", "FFFFFFFF") or "FFFFFFFF").strip()
    if not raw:
        return fallback
    # Stored hex from optionvalues (preferred).
    if len(raw) == 8 and all(c in "0123456789ABCDEFabcdef" for c in raw):
        return raw.upper()
    if len(raw) == 6 and all(c in "0123456789ABCDEFabcdef" for c in raw):
        return f"FF{raw.upper()}"
    key = raw.lower()
    if key in _SKIP_DIALOG_FONT_COLOR_ARGB:
        return _SKIP_DIALOG_FONT_COLOR_ARGB[key]
    if raw.isdigit():
        idx = int(raw)
        if 0 <= idx < len(_SKIP_DIALOG_FONT_COLOR_INDEXED):
            return _SKIP_DIALOG_FONT_COLOR_INDEXED[idx]
    return fallback


def _minimal_plate_filename(addon):
    raw = (addon_get_setting_text(addon, "minimal_button_style", "") or "").strip()
    if raw.endswith(".png"):
        return raw
    return "minimal_rounded_gray_640.png"


def get_addon():
    """Returns the xbmcaddon.Addon object for this addon,
    or None if it fails to load."""
    # Always create a fresh addon object to avoid caching issues
    try:
        return xbmcaddon.Addon("service.skippy")
    except RuntimeError:
        return None

def log(msg):
    addon = get_addon()
    if not addon:
        return
    lv = skippy_log_effective_detail_level(addon)
    if lv == "Off" or lv == SKIPPY_LOG_ERROR_ONLY:
        return
    try:
        xbmc.log(f"[{addon.getAddonInfo('id')} - SkipDialog] {_ascii_log_text(msg)}", xbmc.LOGINFO)
    except RuntimeError:
        xbmc.log(f"[service.skippy - SkipDialog] {_ascii_log_text(msg)}", xbmc.LOGINFO)

def log_always(msg):
    # This function is now more robust against shutdown failures
    addon = get_addon()
    if addon:
        # Check if the addon is still in context
        try:
            xbmc.log(f"[{addon.getAddonInfo('id')} - SkipDialog] {_ascii_log_text(msg)}", xbmc.LOGINFO)
        except RuntimeError:
            # Fallback for when context is lost
            xbmc.log(f"[service.skippy - SkipDialog] {_ascii_log_text(msg)}", xbmc.LOGINFO)
    else:
        xbmc.log(f"[service.skippy - SkipDialog] {_ascii_log_text(msg)}", xbmc.LOGINFO)

def _build_skip_button_label(segment, format_setting, duration_str):
    if format_setting == "Skip":
        return "Skip"
    if format_setting == "Skip + Type":
        return f"Skip {segment.segment_type_label.title()}"
    return f"Skip {segment.segment_type_label.title()} ({duration_str})"


def _elapsed_progress_percent_float(current_time, segment_start, total_duration):
    if not total_duration or total_duration <= 0:
        return 0.0
    elapsed = max(current_time - segment_start, 0)
    p = (elapsed / float(total_duration)) * 100.0
    return min(max(p, 0.0), 100.0)


def _progress_display_percent_float(elapsed_pct_f, countdown):
    return 100.0 - elapsed_pct_f if countdown else elapsed_pct_f


def _elapsed_progress_percent(current_time, segment_start, total_duration):
    if not total_duration or total_duration <= 0:
        return 0
    elapsed = max(current_time - segment_start, 0)
    p = int((elapsed / float(total_duration)) * 100)
    return min(max(p, 0), 100)


def _progress_display_percent(elapsed_pct, countdown):
    return 100 - elapsed_pct if countdown else elapsed_pct


def _seed_progress_values(current_time, segment_start, total_duration, countdown, bar_width):
    """Return (classic_percent, smooth_fill_width) for the current playhead."""
    elapsed_f = _elapsed_progress_percent_float(current_time, segment_start, total_duration)
    pct_f = _progress_display_percent_float(elapsed_f, countdown)
    pct_f = min(max(pct_f, 0.0), 100.0)
    disp = int(round(pct_f))
    w = int(round((pct_f / 100.0) * float(bar_width)))
    return disp, max(0, min(int(bar_width), w))


class SkipDialog(xbmcgui.WindowXMLDialog):
    def _set_smooth_bar_window_visible(self, visible):
        self.setProperty(_SMOOTH_BAR_WINDOW_PROP, "true" if visible else "false")

    def __init__(self, *args, **kwargs):
        try:
            init_window_xml_dialog(super(SkipDialog, self), args)
            self.segment = kwargs.get("segment", None)
            self._minimal_mode = False
            log(f"📦 Loaded dialog layout: {args[0]}")
        except Exception as e:
            log_always(f"❌ Failed to initialize SkipDialog (possible Kodi/device limitation): {e}")
            log_always(f"❌ Dialog initialization failed with args: {args}, kwargs: {kwargs}")
            raise
        # Default until onInit resolves skip_dialog_font_color (XML uses $INFO[Window.Property(...)]).
        try:
            self.setProperty("skip_dialog_text_color", "FFFFFFFF")
            self.setProperty("skippy_progress_ready", "false")
        except Exception:
            pass

    def onInit(self):
        try:
            log_always(f"🔍 onInit called — segment={getattr(self, 'segment', None)}")

            if not hasattr(self, "segment") or not self.segment:
                log("❌ Segment not set — aborting dialog init")
                self.close()
                return
        except Exception as e:
            log_always(f"❌ Error in onInit before segment check (possible Kodi/device limitation): {e}")
            try:
                self.close()
            except:
                pass
            return

        duration = int(self.segment.end_seconds - self.segment.start_seconds)
        m, s = divmod(duration, 60)
        duration_str = f"{m}m{s}s" if m else f"{s}s"

        addon = get_addon()
        self._skip_text_color_argb = _skip_dialog_font_color_argb(addon)
        self.setProperty("skip_dialog_text_color", self._skip_text_color_argb)
        self._minimal_mode = (addon_get_setting_text(addon, "skip_dialog_mode", "Full") or "Full").strip() == "Minimal"

        if self._minimal_mode:
            fmt = addon_get_setting_text(addon, "minimal_skip_button_format", "Skip + Type") or "Skip + Type"
            log(f"🖼️ Minimal plate (XML patched in service): {_minimal_plate_filename(addon)}")
        else:
            fmt = addon_get_setting_text(addon, "skip_button_format", "Skip + Type + Duration") or "Skip + Type + Duration"
        label = _build_skip_button_label(self.segment, fmt, duration_str)
        for cid in FULL_SKIP_BUTTON_IDS:
            try:
                self.getControl(cid).setLabel(label)
            except Exception:
                pass

        self.setProperty("countdown", "")

        if self.segment.segment_type_label and self.segment.segment_type_label.lower() != "segment":
            segment_type = self.segment.segment_type_label.title()
        else:
            segment_type = "Segment"
        self.setProperty("ending_text", f"{segment_type} ending in:")

        hide_ending_text = addon_get_bool(addon, "hide_ending_text", False) if addon else False
        self.setProperty("hide_ending_text", "true" if hide_ending_text else "false")

        hide_close = False
        hide_skip_icon = False
        if not self._minimal_mode:
            hide_close = addon_get_bool(addon, "hide_close_button", False) if addon else False
            self.setProperty("hide_close_button", "true" if hide_close else "false")
            hide_skip_icon = addon_get_bool(addon, "hide_skip_icon", False) if addon else False
            self.setProperty("hide_skip_icon", "true" if hide_skip_icon else "false")
            if hide_close:
                try:
                    self.getControl(3013).setVisible(False)
                    log("🚫 Close button hidden per setting")
                except Exception as e:
                    log(f"⚠️ Error hiding close button: {e}")
        else:
            self.setProperty("hide_close_button", "true")
            self.setProperty("hide_skip_icon", "true")

        self._closing = False
        self.response = None
        self.player = xbmc.Player()
        self._total_duration = self.segment.end_seconds - self.segment.start_seconds
        self._start_time = time.time()

        # Enhanced: Set property for next segment jump time with better info
        if self.segment.next_segment_start is not None:
            jump_m, jump_s = divmod(int(self.segment.next_segment_start), 60)
            
            # Use the next_segment_info if available, otherwise use generic text
            if hasattr(self.segment, 'next_segment_info') and self.segment.next_segment_info:
                # Extract segment label from info if it contains one
                if "'" in self.segment.next_segment_info:
                    # Extract text between quotes
                    import re
                    match = re.search(r"'([^']+)'", self.segment.next_segment_info)
                    if match:
                        segment_label = match.group(1).title()
                        jump_str = f"Skip to {segment_label} at {jump_m:02d}:{jump_s:02d}"
                    else:
                        jump_str = f"Skip to next segment at {jump_m:02d}:{jump_s:02d}"
                else:
                    jump_str = f"Skip to next segment at {jump_m:02d}:{jump_s:02d}"
            else:
                jump_str = f"Skip to next segment at {jump_m:02d}:{jump_s:02d}"
            
            self.setProperty("next_jump_label", jump_str)
            self.setProperty("show_next_jump", "true")
            log(f"⏭️ Dialog configured for jump to next segment at {self.segment.next_segment_start}s: {jump_str}")
        else:
            self.setProperty("show_next_jump", "false")
            log("➡️ Dialog configured for normal skip to end of segment")

        if not self._minimal_mode:
            self._apply_full_skip_layout(addon)

        self._apply_dialog_text_colors()
        self._apply_skip_dialog_focus(hide_close, hide_skip_icon)

        try:
            log(f"🟦 Dialog initialized: segment='{self.segment.segment_type_label}', duration={duration_str}")
            threading.Thread(target=self._monitor_segment_end, daemon=True).start()
            log("✅ Dialog onInit completed successfully")
        except Exception as e:
            log_always(f"❌ Error during dialog onInit completion (possible Kodi/device limitation): {e}")
            log_always(f"❌ Dialog initialization failed for segment: {getattr(self.segment, 'segment_type_label', 'unknown')}")
            try:
                self.close()
            except:
                pass

    def _apply_full_skip_layout(self, addon):
        """Stack optional Full rows, set final panel height, seed progress from playhead, then show."""
        sc = _skip_sc
        CONTENT_TOP = sc(41)
        GAP_AFTER_JUMP = sc(5)
        GAP_BEFORE_PROGRESS = sc(4)
        BOTTOM_MARGIN = sc(5)
        META_LINE_H = sc(20)
        BTN_BOTTOM = sc(35)
        UNDER_BTNS_FALLBACK = sc(14)
        LEFT_MARGIN = sc(5)
        progress_bar_width = sc(FULL_SKIP_PROGRESS_BAR_WIDTH)

        ad = addon if addon is not None else get_addon()
        show_jump = self.getProperty("show_next_jump") == "true"
        hide_end = self.getProperty("hide_ending_text") == "true"
        show_progress = addon_get_bool(ad, "show_progress_bar", False) if ad else False
        countdown = addon_get_bool(ad, "progress_bar_countdown", False) if ad else False

        progress_h = (
            addon_get_int(ad, "progress_bar_height", 16, minimum=5, maximum=32)
            if ad
            else 16
        )
        smooth_ui = addon_get_bool(ad, "smooth_progress_bar", False) if ad else False

        bottom = CONTENT_TOP
        if show_jump:
            bottom += META_LINE_H
            if not hide_end or show_progress:
                bottom += GAP_AFTER_JUMP
        if not hide_end:
            bottom += META_LINE_H
            if show_progress:
                bottom += GAP_BEFORE_PROGRESS
        if show_progress:
            bottom += progress_h
        has_meta = show_jump or (not hide_end) or show_progress
        total_h = (bottom + BOTTOM_MARGIN) if has_meta else (BTN_BOTTOM + UNDER_BTNS_FALLBACK)
        total_h = max(total_h, BTN_BOTTOM + UNDER_BTNS_FALLBACK)

        try:
            self.getControl(_FULL_SKIP_PANEL_GROUP_ID).setHeight(total_h)
            self.getControl(_FULL_SKIP_PANEL_BACKDROP_ID).setHeight(total_h)
        except Exception as e:
            log(f"⚠️ Full skip panel height: {e}")

        bottom = CONTENT_TOP

        try:
            if show_jump:
                label_j = self.getControl(3011)
                label_j.setPosition(LEFT_MARGIN, bottom)
                bottom += META_LINE_H
                if not hide_end or show_progress:
                    bottom += GAP_AFTER_JUMP

            if not hide_end:
                label_e = self.getControl(2)
                label_e.setPosition(LEFT_MARGIN, bottom)
                bottom += META_LINE_H
                if show_progress:
                    bottom += GAP_BEFORE_PROGRESS

            progress = self.getControl(3014)
            progress.setVisible(False)
            self._set_smooth_bar_window_visible(False)
            if show_progress:
                py = bottom
                progress.setPosition(LEFT_MARGIN, py)
                progress.setHeight(progress_h)
                try:
                    current = self.player.getTime()
                except Exception:
                    current = self.segment.start_seconds
                init_pct, init_w = _seed_progress_values(
                    current,
                    self.segment.start_seconds,
                    self._total_duration,
                    countdown,
                    progress_bar_width,
                )
                progress.setPercent(init_pct)
                self._last_smooth_fill_w = init_w
                try:
                    bg = self.getControl(_SMOOTH_PROGRESS_BG_ID)
                    fill = self.getControl(_SMOOTH_PROGRESS_FILL_ID)
                    bg.setPosition(LEFT_MARGIN, py)
                    bg.setWidth(progress_bar_width)
                    bg.setHeight(progress_h)
                    fill.setPosition(LEFT_MARGIN, py)
                    fill.setHeight(progress_h)
                    fill.setWidth(init_w)
                except Exception as e:
                    log(f"⚠️ Smooth progress controls (3030/3031): {e}")
                    self._set_smooth_bar_window_visible(False)
                    progress.setVisible(True)
                else:
                    if smooth_ui:
                        progress.setVisible(False)
                        self._set_smooth_bar_window_visible(True)
                    else:
                        self._set_smooth_bar_window_visible(False)
                        progress.setVisible(True)
                try:
                    self.setProperty("skippy_progress_ready", "true")
                except Exception:
                    pass
                log(
                    f"📊 Progress seeded at open: {init_pct}% / {init_w}px "
                    f"(countdown={countdown}, playhead={current:.2f}s)"
                )
            else:
                self._set_smooth_bar_window_visible(False)
                try:
                    self.setProperty("skippy_progress_ready", "false")
                except Exception:
                    pass
        except Exception as e:
            log(f"⚠️ Full skip vertical layout failed: {e}")

    def _apply_skip_dialog_focus(self, hide_close, hide_skip_icon):
        """Set button focus so texturefocus appears with the dialog (not after layout lag)."""
        try:
            if self._minimal_mode:
                focus_id = 3012
            else:
                focus_id = _full_skip_focus_id(hide_close, hide_skip_icon)
            self.setFocusId(focus_id)
            log(
                f"📐 Focus set to control {focus_id} (minimal={self._minimal_mode}, "
                f"hide_close={hide_close}, hide_skip_icon={hide_skip_icon})"
            )
        except Exception as e:
            log(f"⚠️ Error setting dialog focus: {e}")
            try:
                fid = (
                    3012
                    if self._minimal_mode
                    else _full_skip_focus_id(hide_close, hide_skip_icon)
                )
                self.setFocusId(fid)
                log(f"📐 Fallback: Focus set to control {fid}")
            except Exception as e2:
                log_always(
                    f"❌ CRITICAL: Failed to set focus to any button - dialog may not be functional: {e2}"
                )

    def _monitor_segment_end(self):
        timeout = self._total_duration + 5  # ⏳ Dynamic timeout based on segment length
        self._last_smooth_fill_w = getattr(self, "_last_smooth_fill_w", None)
        self._last_smooth_log_ts = 0.0
        self._last_classic_log_ts = 0.0

        while not self._closing:
            if not self.player.isPlaying():
                log("⏹️ Playback stopped during dialog")
                break

            addon = get_addon()
            smooth = addon_get_bool(addon, "smooth_progress_bar", False) if addon else False
            ups = addon_get_int(addon, "progress_bar_updates_per_second", 4) if addon else 4
            ups = min(120, max(2, ups))
            delay = (1.0 / ups) if smooth else 0.25

            current = self.player.getTime()
            remaining = int(self.segment.end_seconds - current)
            m, s = divmod(max(remaining, 0), 60)
            self.setProperty("countdown", f"{m:02d}:{s:02d}")
            self._refresh_countdown_label()

            if not self._minimal_mode:
                try:
                    raw_setting = addon_get_setting_text(addon, "show_progress_bar", "")
                    show_progress = addon_get_bool(addon, "show_progress_bar", False)
                    countdown = addon_get_bool(addon, "progress_bar_countdown", False) if addon else False
                    progress = self.getControl(3014)
                    fill = self.getControl(_SMOOTH_PROGRESS_FILL_ID)

                    if show_progress:
                        if smooth:
                            progress.setVisible(False)
                            self._set_smooth_bar_window_visible(True)
                            elapsed_f = _elapsed_progress_percent_float(
                                current, self.segment.start_seconds, self._total_duration
                            )
                            pct_f = _progress_display_percent_float(elapsed_f, countdown)
                            w = int(
                                round((pct_f / 100.0) * _skip_sc(FULL_SKIP_PROGRESS_BAR_WIDTH))
                            )
                            w = max(0, min(_skip_sc(FULL_SKIP_PROGRESS_BAR_WIDTH), w))
                            if w != self._last_smooth_fill_w:
                                self._last_smooth_fill_w = w
                                fill.setWidth(w)
                            now_wall = time.time()
                            if (now_wall - self._last_smooth_log_ts) >= 1.5:
                                self._last_smooth_log_ts = now_wall
                                log(
                                    f"📊 Smooth bar {w}px (≈{pct_f:.2f}%, countdown={countdown}, ups={ups}, raw: '{raw_setting}')"
                                )
                        else:
                            self._last_smooth_fill_w = None
                            self._set_smooth_bar_window_visible(False)
                            progress.setVisible(True)
                            elapsed_pct = _elapsed_progress_percent(
                                current, self.segment.start_seconds, self._total_duration
                            )
                            disp = _progress_display_percent(elapsed_pct, countdown)
                            progress.setPercent(disp)
                            now_wall = time.time()
                            if (now_wall - self._last_classic_log_ts) >= 1.5:
                                self._last_classic_log_ts = now_wall
                                log(
                                    f"📊 Progress bar {disp}% (elapsed={elapsed_pct}%, countdown={countdown}, raw: '{raw_setting}')"
                                )
                    else:
                        self._last_smooth_fill_w = None
                        progress.setVisible(False)
                        self._set_smooth_bar_window_visible(False)
                        log(f"📊 Progress bar hidden due to setting (raw: '{raw_setting}')")
                except Exception as e:
                    log(f"⚠️ Progress bar update error: {e}")

            # ⌛ Segment end reached
            if current >= self.segment.end_seconds - 0.5:
                log("⌛ Segment ended — auto-decline")
                self._closing = True
                self.response = False
                self.close()
                break

            # ⏳ Timeout fallback
            if time.time() - self._start_time > timeout:
                log("⏳ Timeout reached — auto-decline")
                self._closing = True
                self.response = False
                self.close()
                break

            time.sleep(delay)

    def _apply_dialog_text_colors(self):
        """Keep label text in sync; colours come from Window.Property(skip_dialog_text_color) in XML."""
        try:
            if self._minimal_mode:
                c = self.getControl(3012)
                lab = c.getLabel() or ""
                c.setLabel(lab)
                return
            for cid in FULL_SKIP_BUTTON_IDS:
                try:
                    c = self.getControl(cid)
                    lab = c.getLabel() or ""
                    c.setLabel(lab)
                except Exception:
                    pass
            try:
                c = self.getControl(3013)
                lab = c.getLabel() or ""
                c.setLabel(lab)
            except Exception:
                pass
            try:
                if self.getProperty("show_next_jump") == "true":
                    c = self.getControl(3011)
                    txt = self.getProperty("next_jump_label") or ""
                    c.setLabel(txt)
            except Exception as e:
                log(f"⚠️ next-jump label: {e}")
            self._refresh_countdown_label()
        except Exception as e:
            log(f"⚠️ _apply_dialog_text_colors: {e}")

    def _refresh_countdown_label(self):
        if self._minimal_mode:
            return
        if self.getProperty("hide_ending_text") == "true":
            return
        try:
            c = self.getControl(2)
            et = self.getProperty("ending_text") or ""
            cd = self.getProperty("countdown") or ""
            line = f"{et} {cd}".strip()
            c.setLabel(line)
        except Exception:
            pass

    def onClick(self, controlId):
        if controlId in FULL_SKIP_BUTTON_IDS:
            self.response = self.segment.next_segment_start or self.segment.end_seconds + 1.0
            log(f"🖱️ User clicked skip → skipping to {self.response}s")
        else:
            self.response = False
            log(f"🖱️ User clicked cancel/close → declining skip")

        self._closing = True
        self.close()

    def onAction(self, action):
        if action.getId() in [10, 92, 216]:
            log(f"🔙 User cancelled via action ID {action.getId()}")
            self.response = False
            self._closing = True
            self.close()


    def onClose(self):
        try:
            if getattr(self, "_minimal_mode", False):
                return
            self._set_smooth_bar_window_visible(False)
            try:
                self.setProperty("skippy_progress_ready", "false")
            except Exception:
                pass
            _ad = get_addon()
            show_progress = addon_get_bool(_ad, "show_progress_bar", False) if _ad else False
            if show_progress:
                self.getControl(3014).setPercent(0)
                try:
                    self.getControl(_SMOOTH_PROGRESS_FILL_ID).setWidth(0)
                except Exception:
                    pass
                log("🔄 Progress bar reset on close")
        except Exception as e:
            log(f"⚠️ Error resetting progress bar on close: {e}")
