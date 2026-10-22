"""Native skip prompt: Kodi's stock Yes/No dialog, drawn by the active skin.

Text is fixed when the dialog opens (Kodi offers no handle to update it), so there
is no live countdown or progress bar. ``autoclose`` plus a small watcher thread
dismiss the prompt when the segment ends, playback stops, or the user seeks away.
"""

import threading
import time

import xbmc
import xbmcgui

from addon_skin_resolution import init_window_xml_dialog
from settings_utils import (
    addon_get_bool,
    addon_get_setting_text,
    compute_skip_seek_destination_seconds,
    get_localized,
    log,
)
from skip_dialog_appearance import (
    DURATION_CONTENT_TOTAL,
    DURATION_FORMAT_1M30S,
    build_skip_button_label,
    countdown_mmss,
    ending_text_for_segment,
    format_next_jump_label,
    skip_button_duration_text,
)

NATIVE_FOCUS_SKIP = "Skip"
NATIVE_FOCUS_DISMISS = "Dismiss"
_DLG_NO_BTN = getattr(xbmcgui, "DLG_YESNO_NO_BTN", 0)
_DLG_YES_BTN = getattr(xbmcgui, "DLG_YESNO_YES_BTN", 1)
_WATCH_INTERVAL_S = 0.5


def is_native_skip_dialog(addon):
    if not addon:
        return False
    raw = addon_get_setting_text(addon, "skip_dialog_type", "Custom") or "Custom"
    return raw.strip().lower() == "native"


def _playhead(player, fallback):
    try:
        return float(player.getTime())
    except Exception:
        return float(fallback)


def build_native_texts(addon, segment, playhead):
    """Return (heading, message, skip_label, dismiss_label) for the stock dialog."""
    start = float(segment.start_seconds)
    end = float(segment.end_seconds)
    total_i = max(0, int(round(end - start)))
    remaining = max(0.0, end - max(playhead, start))
    fmt = (
        addon_get_setting_text(addon, "native_skip_format", "Skip + Type") or "Skip + Type"
    ).strip()
    include_type = fmt != "Skip"
    skip_label = build_skip_button_label(
        segment, "Skip + Type" if include_type else "Skip", "", addon
    )
    if addon_get_bool(addon, "native_show_duration", True):
        dur_style = (
            addon_get_setting_text(addon, "native_duration_format", DURATION_FORMAT_1M30S)
            or DURATION_FORMAT_1M30S
        )
        duration_str = skip_button_duration_text(
            0, total_i, total_i, dur_style, DURATION_CONTENT_TOTAL
        )
        if include_type:
            skip_label = build_skip_button_label(
                segment, "Skip + Type + Duration", duration_str, addon
            )
        else:
            skip_label = "%s (%s)" % (skip_label, duration_str)

    lines = ["%s %s" % (ending_text_for_segment(addon, segment), countdown_mmss(remaining))]
    if addon_get_bool(addon, "native_show_jump_hint", True):
        next_start = getattr(segment, "next_segment_start", None)
        if next_start is not None:
            next_start = compute_skip_seek_destination_seconds(segment, addon)
        jump = format_next_jump_label(
            addon, getattr(segment, "next_segment_info", None), next_start
        )
        if jump:
            lines.append(jump)
    return (
        addon.getAddonInfo("name") or "Skippy",
        "\n".join(lines),
        skip_label,
        get_localized(addon, 40001, "Close"),
    )


def _watch_and_close(player, segment, auto_close, stop):
    start = float(segment.start_seconds)
    end = float(segment.end_seconds)
    while not stop.wait(_WATCH_INTERVAL_S):
        try:
            playing = player.isPlaying()
        except Exception:
            playing = False
        leave = not playing
        if playing and auto_close:
            head = _playhead(player, start)
            leave = head >= end - 0.5 or head < start - 1.0 or head > end + 1.0
        if leave:
            xbmc.executebuiltin("Dialog.Close(yesnodialog,true)")
            return


def show_native_skip_dialog(addon, segment, player):
    """Show the native prompt (Yes/No dialog or toast). Seek target on Skip, else False."""
    if addon_get_bool(addon, "native_use_toast", True):
        return show_toast_skip_dialog(addon, segment, player)
    start = float(segment.start_seconds)
    head = _playhead(player, start)
    heading, message, skip_label, dismiss_label = build_native_texts(addon, segment, head)
    auto_close = addon_get_bool(addon, "native_auto_close", True)
    focus = (
        addon_get_setting_text(addon, "native_default_focus", NATIVE_FOCUS_SKIP)
        or NATIVE_FOCUS_SKIP
    ).strip()
    default_btn = _DLG_NO_BTN if focus == NATIVE_FOCUS_DISMISS else _DLG_YES_BTN

    kwargs = {"nolabel": dismiss_label, "yeslabel": skip_label}
    if auto_close:
        kwargs["autoclose"] = max(1000, int((float(segment.end_seconds) - head) * 1000))

    stop = threading.Event()
    threading.Thread(
        target=_watch_and_close, args=(player, segment, auto_close, stop), daemon=True
    ).start()
    try:
        dlg = xbmcgui.Dialog()
        try:
            chosen = dlg.yesno(heading, message, defaultbutton=default_btn, **kwargs)
        except TypeError:  # Kodi < 20 has no defaultbutton
            chosen = dlg.yesno(heading, message, **kwargs)
    finally:
        stop.set()
    if chosen:
        return compute_skip_seek_destination_seconds(segment, addon)
    return False


# --------------------------------------------------------------------------- toast
_TOAST_VISIBLE_COND = "Window.IsVisible(notification) | Window.IsActive(notification)"
_TOAST_FIRST_CHECK_S = 1.2
_TOAST_REPOST_GAP_S = 2.0
_TOAST_MAX_REPOSTS = 30
_TOAST_MIN_MS = 1500
_ACTION_SELECT = getattr(xbmcgui, "ACTION_SELECT_ITEM", 7)
_BACK_ACTIONS = (10, 92, 216)


class SkipToastKeys(xbmcgui.WindowXMLDialog):
    """Invisible modal that holds focus so OK / Back reach Skippy while a toast shows."""

    def __init__(self, *args, **kwargs):
        init_window_xml_dialog(super(SkipToastKeys, self), args)
        self.result = None
        self._done = False

    def onInit(self):
        try:
            self.setFocusId(3012)
        except Exception:
            pass

    def _finish(self, value):
        if self._done:
            return
        self._done = True
        self.result = value
        self.close()

    def onClick(self, controlId):
        self._finish(True)

    def onAction(self, action):
        aid = action.getId()
        if aid == _ACTION_SELECT:
            self._finish(True)
        elif aid in _BACK_ACTIONS:
            self._finish(False)


def _dismiss_toast():
    xbmc.executebuiltin("Dialog.Close(notification,true)")
    xbmc.executebuiltin("Dialog.Close(10107,true)")


def _toast_visible():
    try:
        return bool(xbmc.getCondVisibility(_TOAST_VISIBLE_COND))
    except Exception:
        return False


def _toast_keepalive(player, segment, post, close_dialog, stop):
    """Keep the toast up for the whole segment; close the key catcher when it ends.

    Kodi toasts expire on their own timer and are replaced by other add-ons' toasts.
    Once the toast has been seen on screen, re-post it with the remaining time whenever
    it disappears while the segment is still running. If the first post is never seen
    (visibility condition unsupported by the skin), no re-posts are made.
    """
    start = float(segment.start_seconds)
    end = float(segment.end_seconds)
    posted_at = time.time()
    reliable = None
    reposts = 0
    while not stop.wait(_WATCH_INTERVAL_S):
        try:
            playing = player.isPlaying()
        except Exception:
            playing = False
        head = _playhead(player, start) if playing else start
        if not playing or head >= end - 0.5 or head < start - 1.0 or head > end + 1.0:
            close_dialog()
            return
        now = time.time()
        visible = _toast_visible()
        if reliable is None:
            if now - posted_at >= _TOAST_FIRST_CHECK_S:
                reliable = visible
                log("🔔 Toast visibility %s — keep-alive %s" % (
                    "detected" if visible else "not detected",
                    "on" if visible else "off",
                ))
            continue
        if (
            reliable
            and not visible
            and reposts < _TOAST_MAX_REPOSTS
            and now - posted_at >= _TOAST_REPOST_GAP_S
        ):
            post(max(_TOAST_MIN_MS, int((end - head) * 1000)))
            posted_at = now
            reposts += 1


def show_toast_skip_dialog(addon, segment, player):
    """Skin toast for the look + invisible dialog for OK / Back. Seek target or False."""
    head = _playhead(player, float(segment.start_seconds))
    _heading, message, skip_label, _dismiss = build_native_texts(addon, segment, head)
    hint = message.split("\n", 1)[1] if "\n" in message else ""
    body = get_localized(addon, 46008, "Press OK to skip")
    if hint:
        body = "%s \u00b7 %s" % (body, hint)
    icon = addon.getAddonInfo("icon") or ""

    def post(ms):
        try:
            xbmcgui.Dialog().notification(skip_label, body, icon, int(ms), False)
        except Exception as exc:
            log("⚠️ Skip toast failed: %s" % exc)

    post(max(_TOAST_MIN_MS, int((float(segment.end_seconds) - head) * 1000)))
    dlg = SkipToastKeys("SkipToastKeys.xml", addon.getAddonInfo("path"), "default")
    stop = threading.Event()
    threading.Thread(
        target=_toast_keepalive,
        args=(player, segment, post, dlg.close, stop),
        daemon=True,
    ).start()
    try:
        dlg.doModal()
    finally:
        stop.set()
        _dismiss_toast()
    chosen = dlg.result is True
    del dlg
    if chosen:
        return compute_skip_seek_destination_seconds(segment, addon)
    return False
