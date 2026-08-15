import threading
import time
import unicodedata

import xbmc
import xbmcgui

from addon_skin_resolution import init_window_xml_dialog, scale_skin_coord
from settings_utils import (
    SKIPPY_LOG_ERROR_ONLY,
    addon_get_bool,
    addon_get_int,
    addon_get_setting_text,
    get_addon,
    get_localized,
    skippy_log_effective_detail_level,
)
from skip_dialog_appearance import (
    FULL_SKIP_BUTTON_IDS,
    FULL_SKIP_PROGRESS_BAR_WIDTH,
    SMOOTH_BAR_WINDOW_PROP as _SMOOTH_BAR_WINDOW_PROP,
    SMOOTH_PROGRESS_FILL_ID as _SMOOTH_PROGRESS_FILL_ID,
    AddonSettingsReader,
    apply_full_skip_layout,
    apply_jump_properties,
    build_skip_button_label as _build_skip_button_label,
    DIALOG_READY_PROP as _DIALOG_READY_PROP,
    elapsed_progress_percent as _elapsed_progress_percent,
    elapsed_progress_percent_float as _elapsed_progress_percent_float,
    ending_text_for_segment,
    format_next_jump_label,
    full_skip_focus_id as _full_skip_focus_id,
    apply_skip_dialog_caps,
    JUMP_LABEL_ARGB,
    JUMP_LABEL_FONT,
    ENDING_TEXT_ARGB,
    is_compact_combined,
    is_compact_full_mode,
    is_minimal_skip_mode,
    skip_duration_for_playhead,
    skip_format_includes_duration,
    COMBINED_FILL_SLICE_ID,
    COMBINED_FILL_STRETCH_ID,
    COMBINED_SLICE_MIN_W,
    DURATION_CONTENT_TOTAL,
    minimal_plate_filename,
    progress_display_percent as _progress_display_percent,
    progress_display_percent_float as _progress_display_percent_float,
    resolve_font_color_argb,
    set_skip_button_label as _set_skip_button_label,
    set_skip_info_label as _set_skip_info_label,
    shadow_for_text as _shadow_for_text,
)
from skip_dialog_window_ui import _argb_to_kodi


def _ascii_log_text(msg):
    return unicodedata.normalize("NFKD", str(msg)).encode("ascii", "ignore").decode("ascii")


def _normalize_control_id(control_id):
    if hasattr(control_id, "getId"):
        control_id = control_id.getId()
    try:
        return int(control_id)
    except (TypeError, ValueError):
        return control_id


def _skip_dialog_font_color_argb(addon):
    """Resolve addon setting to AARRGGBB. Tests patch addon_get_setting_text on this module."""
    if not addon:
        return resolve_font_color_argb("")
    raw = (addon_get_setting_text(addon, "skip_dialog_font_color", "FFFFFFFF") or "FFFFFFFF").strip()
    return resolve_font_color_argb(raw)


def _minimal_plate_filename(addon):
    return minimal_plate_filename(AddonSettingsReader(addon))


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


class SkipDialog(xbmcgui.WindowXMLDialog):
    def _skin_sc(self, value):
        return scale_skin_coord(value, getattr(self, "_skin_resolution", None))

    def _set_smooth_bar_window_visible(self, visible):
        self.setProperty(_SMOOTH_BAR_WINDOW_PROP, "true" if visible else "false")

    def __init__(self, *args, **kwargs):
        try:
            self._skin_resolution = init_window_xml_dialog(super(SkipDialog, self), args)
            self.segment = kwargs.get("segment", None)
            self._minimal_mode = False
            self._compact_mode = False
            self._combined_mode = False
            log(
                f"📦 Loaded dialog layout: {args[0]} ({self._skin_resolution})"
            )
        except Exception as e:
            log_always(f"❌ Failed to initialize SkipDialog (possible Kodi/device limitation): {e}")
            log_always(f"❌ Dialog initialization failed with args: {args}, kwargs: {kwargs}")
            raise
        # Default until onInit resolves skip_dialog_font_color (XML uses $INFO[Window.Property(...)]).
        # Keep panel hidden until layout/progress are ready (Visible animation on group).
        try:
            self.setProperty("skip_dialog_text_color", "FFFFFFFF")
            self.setProperty("skippy_progress_ready", "false")
            self.setProperty(_DIALOG_READY_PROP, "false")
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
        raw_font_color = (
            addon_get_setting_text(addon, "skip_dialog_font_color", "FFFFFFFF") or "FFFFFFFF"
        ).strip()
        self._skip_text_color_argb = _skip_dialog_font_color_argb(addon)
        self.setProperty("skip_dialog_text_color", self._skip_text_color_argb)
        self._skip_all_caps = addon_get_bool(addon, "skip_dialog_all_caps", False) if addon else False
        log_always(
            f"Skip dialog font colour: raw={raw_font_color!r} "
            f"resolved={self._skip_text_color_argb} kodi={_argb_to_kodi(self._skip_text_color_argb)}"
        )
        dialog_mode = (addon_get_setting_text(addon, "skip_dialog_mode", "Full") or "Full").strip()
        self._minimal_mode = is_minimal_skip_mode(dialog_mode)
        self._compact_mode = is_compact_full_mode(dialog_mode)
        self._combined_mode = bool(addon) and is_compact_combined(AddonSettingsReader(addon))
        self._skip_fmt = (
            (addon_get_setting_text(addon, "minimal_skip_button_format", "Skip + Type") or "Skip + Type")
            if self._minimal_mode
            else (
                addon_get_setting_text(addon, "skip_button_format", "Skip + Type + Duration")
                or "Skip + Type + Duration"
            )
        )
        dur_content = (
            addon_get_setting_text(addon, "skip_duration_content", DURATION_CONTENT_TOTAL)
            or DURATION_CONTENT_TOTAL
        ).strip()
        self._skip_duration_live = skip_format_includes_duration(self._skip_fmt) and (
            dur_content != DURATION_CONTENT_TOTAL
        )
        self._last_skip_dur_key = None

        if self._minimal_mode:
            log(f"🖼️ Minimal plate (XML patched in service): {_minimal_plate_filename(addon)}")
        try:
            playhead = xbmc.Player().getTime()
        except Exception:
            playhead = self.segment.start_seconds
        duration_str = skip_duration_for_playhead(
            playhead,
            self.segment,
            AddonSettingsReader(addon),
        ) if addon else duration_str
        label = apply_skip_dialog_caps(
            _build_skip_button_label(self.segment, self._skip_fmt, duration_str, addon),
            self._skip_all_caps,
        )
        text_color = self._skip_text_color_argb
        for cid in FULL_SKIP_BUTTON_IDS:
            try:
                _set_skip_button_label(self.getControl(cid), label, text_color)
            except Exception:
                pass

        self.setProperty("countdown", "")

        self.setProperty(
            "ending_text",
            apply_skip_dialog_caps(ending_text_for_segment(addon, self.segment), self._skip_all_caps),
        )

        hide_ending_text = addon_get_bool(addon, "hide_ending_text", False) if addon else False
        hide_close = False
        hide_skip_icon = False
        if self._compact_mode:
            hide_ending_text = True
            hide_skip_icon = True
        self.setProperty("hide_ending_text", "true" if hide_ending_text else "false")
        self.setProperty("skippy_compact_full", "true" if self._compact_mode else "false")

        if not self._minimal_mode:
            hide_close = addon_get_bool(addon, "hide_close_button", False) if addon else False
            if self._combined_mode:
                hide_close = True
            self.setProperty("hide_close_button", "true" if hide_close else "false")
            if not self._compact_mode:
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
        self._skippy_dialog_result = None
        self.player = xbmc.Player()
        self._total_duration = self.segment.end_seconds - self.segment.start_seconds
        self._start_time = time.time()

        jump_str = apply_jump_properties(self, addon, self.segment, all_caps=self._skip_all_caps)
        if jump_str:
            log(
                "⏭️ Dialog configured for jump to next segment at %ss: %s"
                % (self.segment.next_segment_start, jump_str)
            )
        else:
            log("➡️ Dialog configured for normal skip to end of segment")

        if not self._minimal_mode:
            self._apply_full_skip_layout(addon)

        self._apply_dialog_text_colors()
        # Focus after reveal — Kodi rejects setFocusId while the panel group is still hidden.

        try:
            log(f"🟦 Dialog initialized: segment='{self.segment.segment_type_label}', duration={duration_str}")
            threading.Thread(target=self._monitor_segment_end, daemon=True).start()
            # Reveal panel only after labels, layout, and progress seed are done.
            self.setProperty(_DIALOG_READY_PROP, "true")
            # Let the GUI apply the visible condition before focusing (else "can't" focus).
            xbmc.sleep(50)
            self._apply_skip_dialog_focus(hide_close, hide_skip_icon)
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
        try:
            current = self.player.getTime()
        except Exception:
            current = self.segment.start_seconds
        apply_full_skip_layout(
            self,
            AddonSettingsReader(addon if addon is not None else get_addon()),
            playhead=current,
            segment=self.segment,
            scale_fn=self._skin_sc,
            log_fn=lambda msg: log("⚠️ %s" % msg) if "fail" in msg.lower() or "error" in msg.lower() else log("📊 %s" % msg),
        )

    def _apply_skip_dialog_focus(self, hide_close, hide_skip_icon):
        """Set button focus so texturefocus / OK work (call only after skippy_dialog_ready=true)."""
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
            # Focus can re-apply skin XML textcolorfocus; re-assert Python colours.
            self._apply_dialog_text_colors()
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
            delay = (1.0 / ups) if (smooth or getattr(self, "_combined_mode", False)) else 0.25

            current = self.player.getTime()
            remaining = int(self.segment.end_seconds - current)
            m, s = divmod(max(remaining, 0), 60)
            self.setProperty("countdown", f"{m:02d}:{s:02d}")
            self._refresh_countdown_label()
            self._refresh_skip_duration_label(current)

            if not self._minimal_mode:
                try:
                    if getattr(self, "_combined_mode", False):
                        self._update_combined_fill(current)
                    else:
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
                                    round(
                                        (pct_f / 100.0)
                                        * getattr(
                                            self,
                                            "_skip_progress_bar_width",
                                            self._skin_sc(FULL_SKIP_PROGRESS_BAR_WIDTH),
                                        )
                                    )
                                )
                                bar_w = getattr(
                                    self,
                                    "_skip_progress_bar_width",
                                    self._skin_sc(FULL_SKIP_PROGRESS_BAR_WIDTH),
                                )
                                w = max(0, min(bar_w, w))
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
                self._finish_dialog(False)
                break

            # ⏳ Timeout fallback
            if time.time() - self._start_time > timeout:
                log("⏳ Timeout reached — auto-decline")
                self._finish_dialog(False)
                break

            time.sleep(delay)

    def _refresh_skip_duration_label(self, playhead):
        if not getattr(self, "_skip_duration_live", False):
            return
        addon = get_addon()
        if not addon:
            return
        dur = skip_duration_for_playhead(playhead, self.segment, AddonSettingsReader(addon))
        if dur == getattr(self, "_last_skip_dur_key", None):
            return
        self._last_skip_dur_key = dur
        label = apply_skip_dialog_caps(
            _build_skip_button_label(self.segment, self._skip_fmt, dur, addon),
            getattr(self, "_skip_all_caps", False),
        )
        text_color = getattr(self, "_skip_text_color_argb", None) or "FF6E6E6E"
        ids = (3012,) if self._minimal_mode else FULL_SKIP_BUTTON_IDS
        for cid in ids:
            try:
                _set_skip_button_label(self.getControl(cid), label, text_color)
            except Exception:
                pass

    def _update_combined_fill(self, current):
        addon = get_addon()
        countdown = addon_get_bool(addon, "progress_bar_countdown", False) if addon else False
        bar_w = getattr(
            self,
            "_skip_progress_bar_width",
            self._skin_sc(FULL_SKIP_PROGRESS_BAR_WIDTH),
        )
        elapsed_f = _elapsed_progress_percent_float(
            current, self.segment.start_seconds, self._total_duration
        )
        pct_f = _progress_display_percent_float(elapsed_f, countdown)
        w = int(round((pct_f / 100.0) * float(bar_w)))
        w = max(0, min(int(bar_w), w))
        sliced = self.getProperty("skippy_combined_slice") == "true"
        if sliced and w > 0:
            w = max(w, min(int(bar_w), COMBINED_SLICE_MIN_W))
        if w == getattr(self, "_last_smooth_fill_w", None):
            return
        self._last_smooth_fill_w = w
        fill_id = COMBINED_FILL_SLICE_ID if sliced else COMBINED_FILL_STRETCH_ID
        try:
            self.getControl(fill_id).setWidth(w)
        except Exception:
            pass

    def _apply_dialog_text_colors(self):
        """Apply label text and colours; plain setLabel() resets XML/$INFO colours."""
        try:
            text_color = getattr(self, "_skip_text_color_argb", None) or "FF6E6E6E"
            self.setProperty("skip_dialog_text_color", text_color)
            if self._minimal_mode:
                c = self.getControl(3012)
                _set_skip_button_label(c, c.getLabel() or "", text_color)
                return
            for cid in FULL_SKIP_BUTTON_IDS:
                try:
                    c = self.getControl(cid)
                    _set_skip_button_label(c, c.getLabel() or "", text_color)
                except Exception:
                    pass
            try:
                c = self.getControl(3013)
                close_lbl = apply_skip_dialog_caps(
                    get_localized(get_addon(), 40001, "Close"),
                    getattr(self, "_skip_all_caps", False),
                )
                _set_skip_button_label(c, close_lbl, text_color)
            except Exception:
                pass
            try:
                if self.getProperty("show_next_jump") == "true":
                    c = self.getControl(3011)
                    txt = self.getProperty("next_jump_label") or ""
                    _set_skip_info_label(c, txt, JUMP_LABEL_ARGB, font=JUMP_LABEL_FONT)
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
            text_color = ENDING_TEXT_ARGB
            _set_skip_info_label(c, line, text_color, font="font10")
        except Exception:
            pass

    def _finish_dialog(self, response):
        """Record result before close() so the service loop can read it after doModal()."""
        self.response = response
        self._skippy_dialog_result = response
        self._closing = True
        self.close()

    def onClick(self, controlId):
        cid = _normalize_control_id(controlId)
        if cid in FULL_SKIP_BUTTON_IDS:
            result = self.segment.next_segment_start or self.segment.end_seconds + 1.0
            log(f"🖱️ User clicked skip → skipping to {result}s")
        else:
            result = False
            log(f"🖱️ User clicked cancel/close → declining skip (controlId={cid})")
        self._finish_dialog(result)

    def onAction(self, action):
        if action.getId() in [10, 92, 216]:
            log(f"🔙 User cancelled via action ID {action.getId()}")
            self._finish_dialog(False)


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
