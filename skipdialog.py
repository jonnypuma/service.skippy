import xbmcgui
import xbmc
import xbmcaddon
import threading
import time
import json

# Define a global variable to cache the addon object
_addon = None

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

class SkipDialog(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args)
        self.segment = kwargs.get("segment", None)
        log(f"📦 Loaded dialog layout: {args[0]}")

    def onInit(self):
        log_always(f"🔍 onInit called — segment={getattr(self, 'segment', None)}")

        if not hasattr(self, "segment") or not self.segment:
            log("❌ Segment not set — aborting dialog init")
            self.close()
            return

        duration = int(self.segment.end_seconds - self.segment.start_seconds)
        m, s = divmod(duration, 60)
        duration_str = f"{m}m{s}s" if m else f"{s}s"
        label = f"Skip {self.segment.segment_type_label.title()} ({duration_str})"
        self.getControl(3012).setLabel(label)
        self.setProperty("countdown", "")
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

        # 📊 Setup progress bar (read setting dynamically)
        try:
            # Read setting dynamically instead of caching
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

        log(f"🟦 Dialog initialized: segment='{self.segment.segment_type_label}', duration={duration_str}")
        threading.Thread(target=self._monitor_segment_end, daemon=True).start()

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

            # 📊 Update progress bar (check setting dynamically)
            try:
                # Re-read the setting each time to handle changes
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
                    # Ensure progress bar is hidden when disabled
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

    def onClick(self, controlId):
        if controlId == 3012:
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
            # Reset progress bar on close (read setting dynamically)
            show_progress = get_addon().getSettingBool("show_progress_bar")
            if show_progress:
                self.getControl(3014).setPercent(0)
                log("🔄 Progress bar reset on close")
        except Exception as e:
            log(f"⚠️ Error resetting progress bar on close: {e}")
