import os
import threading
import time

import xbmc
import xbmcaddon
import xbmcgui

# Define a global variable to cache the addon object
_addon = None

FULL_SKIP_BUTTON_IDS = (3012, 3015, 3016)

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
    raw = (addon.getSetting("skip_dialog_font_color") or "FFFFFFFF").strip()
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
    raw = (addon.getSetting("minimal_button_style") or "").strip()
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
    if addon and addon.getSettingBool("enable_verbose_logging"):
        # The addon context might be lost, so check again before calling getAddonInfo
        try:
            xbmc.log(f"[{addon.getAddonInfo('id')} - SkipDialog] {msg}", xbmc.LOGINFO)
        except RuntimeError:
            # Fallback if the addon info can't be retrieved
            xbmc.log(f"[service.skippy - SkipDialog] {msg}", xbmc.LOGINFO)

def log_always(msg):
    # This function is now more robust against shutdown failures
    addon = get_addon()
    if addon:
        # Check if the addon is still in context
        try:
            xbmc.log(f"[{addon.getAddonInfo('id')} - SkipDialog] {msg}", xbmc.LOGINFO)
        except RuntimeError:
            # Fallback for when context is lost
            xbmc.log(f"[service.skippy - SkipDialog] {msg}", xbmc.LOGINFO)
    else:
        xbmc.log(f"[service.skippy - SkipDialog] {msg}", xbmc.LOGINFO)

def _build_skip_button_label(segment, format_setting, duration_str):
    if format_setting == "Skip":
        return "Skip"
    if format_setting == "Skip + Type":
        return f"Skip {segment.segment_type_label.title()}"
    return f"Skip {segment.segment_type_label.title()} ({duration_str})"


def _color_variants(argb):
    u = (argb or "FFFFFFFF").strip().upper()
    if u.startswith("0X"):
        u = u[2:]
    if len(u) == 8 and all(c in "0123456789ABCDEF" for c in u):
        yield u
        yield f"0x{u}"
    else:
        yield u


def _shadow_color_for_text(text_argb):
    """Contrast shadow: dark halo for light text, soft light halo for dark text."""
    u = (text_argb or "FFFFFFFF").strip().upper()
    if u.startswith("0X"):
        u = u[2:]
    if len(u) != 8 or not all(c in "0123456789ABCDEF" for c in u):
        return "FF000000"
    r = int(u[2:4], 16) / 255.0
    g = int(u[4:6], 16) / 255.0
    b = int(u[6:8], 16) / 255.0
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    if lum > 0.45:
        return "FF000000"
    return "99FFFFFF"


def _control_set_label_colors(control, label, font, text_argb):
    """Apply label/button text colors via Kodi API.

    Official order (ControlLabel / ControlButton):
    setLabel(label, font, textColor, disabledColor, shadowColor, focusedColor[, label2])
    We previously used (textColor, shadowColor, focusedColor, …) which put the user text
    color into the *shadow* slot, so shadow matched the caption.
    """
    dc = text_argb
    fc = text_argb
    sh = _shadow_color_for_text(text_argb)
    for tc in _color_variants(text_argb):
        for dc_v in _color_variants(dc):
            for sh_v in _color_variants(sh):
                for fc_v in _color_variants(fc):
                    try:
                        control.setLabel(
                            label,
                            font,
                            textColor=tc,
                            disabledColor=dc_v,
                            shadowColor=sh_v,
                            focusedColor=fc_v,
                            label2="",
                        )
                        return
                    except TypeError:
                        pass
                    try:
                        control.setLabel(label, font, tc, dc_v, sh_v, fc_v, "")
                        return
                    except (TypeError, ValueError):
                        pass
                    try:
                        control.setLabel(label, font, tc, dc_v, sh_v, fc_v)
                        return
                    except (TypeError, ValueError):
                        pass
    control.setLabel(label)


def _button_set_label_colors(control, label, font, text_argb, shadow_argb=None):
    """shadow_argb kept for API compatibility; actual shadow is contrast-based."""
    del shadow_argb  # unused — Kodi slot order made a separate shadow param misleading
    _control_set_label_colors(control, label, font, text_argb)


def _label_set_colors(control, label, font, text_argb, shadow_argb=None):
    del shadow_argb
    _control_set_label_colors(control, label, font, text_argb)


class SkipDialog(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        try:
            try:
                super().__init__(args[0], args[1], args[2], '720p')
            except TypeError:
                super().__init__(*args)
            self.segment = kwargs.get("segment", None)
            self._minimal_mode = False
            log(f"📦 Loaded dialog layout: {args[0]}")
        except Exception as e:
            log_always(f"❌ Failed to initialize SkipDialog (possible Kodi/device limitation): {e}")
            log_always(f"❌ Dialog initialization failed with args: {args}, kwargs: {kwargs}")
            raise

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
        self._minimal_mode = (addon.getSetting("skip_dialog_mode") or "Full").strip() == "Minimal"

        if self._minimal_mode:
            fmt = (addon.getSetting("minimal_skip_button_format") if addon else None) or "Skip + Type"
            log(f"🖼️ Minimal plate (XML patched in service): {_minimal_plate_filename(addon)}")
        else:
            fmt = (addon.getSetting("skip_button_format") if addon else None) or "Skip + Type + Duration"
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

        hide_ending_text = addon.getSettingBool("hide_ending_text") if addon else False
        self.setProperty("hide_ending_text", "true" if hide_ending_text else "false")

        hide_close = False
        hide_skip_icon = False
        if not self._minimal_mode:
            hide_close = addon.getSettingBool("hide_close_button") if addon else False
            self.setProperty("hide_close_button", "true" if hide_close else "false")
            hide_skip_icon = addon.getSettingBool("hide_skip_icon") if addon else False
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

        self._apply_dialog_text_colors()

        if not self._minimal_mode:
            try:
                addon = get_addon()
                raw_setting = addon.getSetting("show_progress_bar")
                show_progress = addon.getSettingBool("show_progress_bar")
                log(f"🧩 show_progress_bar raw setting: '{raw_setting}' -> bool: {show_progress}")
                progress = self.getControl(3014)
                progress.setVisible(show_progress)
                if show_progress:
                    progress.setPercent(0)
                    log("📊 Progress bar initialized at 0%")
                else:
                    log("📊 Progress bar hidden due to setting")
            except Exception as e:
                log(f"⚠️ Progress bar control error: {e}")

        try:
            if self._minimal_mode:
                self.setFocusId(3012)
                log("📐 Minimal: focus on skip chip (3012)")
            elif hide_close:
                focus_id = 3016 if hide_skip_icon else 3015
                self.setFocusId(focus_id)
                log(f"📐 Focus set to control {focus_id} (hide_close={hide_close}, hide_skip_icon={hide_skip_icon})")
            else:
                self.setFocusId(3012)
                log(f"📐 Focus set to control 3012 (hide_close={hide_close}, hide_skip_icon={hide_skip_icon})")
        except Exception as e:
            log(f"⚠️ Error setting dialog focus: {e}")
            try:
                self.setFocusId(3012)
                log("📐 Fallback: Focus set to control 3012")
            except Exception as e2:
                log_always(f"❌ CRITICAL: Failed to set focus to any button - dialog may not be functional: {e2}")

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

    def _monitor_segment_end(self):
        delay = 0.25
        timeout = self._total_duration + 5  # ⏳ Dynamic timeout based on segment length

        while not self._closing:
            if not self.player.isPlaying():
                log("⏹️ Playback stopped during dialog")
                break

            current = self.player.getTime()
            remaining = int(self.segment.end_seconds - current)
            m, s = divmod(max(remaining, 0), 60)
            self.setProperty("countdown", f"{m:02d}:{s:02d}")
            self._refresh_countdown_label()

            if not self._minimal_mode:
                try:
                    addon = get_addon()
                    raw_setting = addon.getSetting("show_progress_bar")
                    show_progress = addon.getSettingBool("show_progress_bar")
                    progress = self.getControl(3014)
                    progress.setVisible(show_progress)
                    if show_progress:
                        elapsed = max(current - self.segment.start_seconds, 0)
                        percent = int((elapsed / self._total_duration) * 100)
                        percent = min(max(percent, 0), 100)
                        progress.setPercent(percent)
                        log(f"📊 Progress bar visible: {percent}% (raw: '{raw_setting}')")
                    else:
                        progress.setVisible(False)
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
        """Apply font color via Python; XML $INFO in textcolor is unreliable for WindowXML."""
        col = getattr(self, "_skip_text_color_argb", "FF6E6E6E")
        sh = "FF000000"
        try:
            if self._minimal_mode:
                c = self.getControl(3012)
                lab = c.getLabel() or ""
                _button_set_label_colors(c, lab, "font16", col, sh)
                return
            for cid in FULL_SKIP_BUTTON_IDS:
                try:
                    c = self.getControl(cid)
                    lab = c.getLabel() or ""
                    _button_set_label_colors(c, lab, "font16", col, sh)
                except Exception:
                    pass
            try:
                c = self.getControl(3013)
                lab = c.getLabel() or ""
                _button_set_label_colors(c, lab, "font16", col, sh)
            except Exception:
                pass
            try:
                if self.getProperty("show_next_jump") == "true":
                    c = self.getControl(3011)
                    txt = self.getProperty("next_jump_label") or ""
                    _label_set_colors(c, txt, "font11", col, sh)
            except Exception as e:
                log(f"⚠️ next-jump label color: {e}")
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
            _label_set_colors(c, line, "font10", self._skip_text_color_argb, "FF000000")
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
            show_progress = get_addon().getSettingBool("show_progress_bar")
            if show_progress:
                self.getControl(3014).setPercent(0)
                log("🔄 Progress bar reset on close")
        except Exception as e:
            log(f"⚠️ Error resetting progress bar on close: {e}")
