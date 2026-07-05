import os
import time
import threading
import json
import re
import traceback
from collections import namedtuple
import xbmc
import xbmcgui
import xbmcvfs
import xbmcaddon

from settings_utils import (
    addon_get_bool,
    get_addon,
    log,
    log_always,
    log_service_detail,
    parse_kodi_jsonrpc_raw,
    skippy_notification_icon,
)
from keymap_utils import install_marker_keymap, install_editor_keymap
from prefetch_segment_cache import clear_prefetch_segment_cache
from service_online_sidecar_save import (
    maybe_save_online_segments_to_chapters_xml as _maybe_save_online_segments_to_chapters_xml_impl,
    maybe_save_online_segments_to_sidecars as _maybe_save_online_segments_to_sidecars_impl,
)
from service_deferred_remote_probe import (
    clear_deferred_remote_probe_state,
    process_deferred_remote_probe,
)
from service_local_to_online_sync import maybe_prompt_sync_local_to_online
from service_sidecar_probe_cache import local_sidecar_exists
from service_playback_context import (
    _fetch_player_item_via_jsonrpc,
    evaluate_toast_allowed,
)
from service_segment_sources import (
    get_cached_source_segments as _get_cached_source_segments_impl,
)
from service_segment_processing import (
    is_nested_segment,
    parse_and_process_segments as _parse_and_process_segments_impl,
    re_evaluate_segment_jump_points,
    should_suppress_segment_dialog,
)
from service_main_loop import ServiceLoopBindings, run_service_main_loop
from service_skip_dialog_skin import (
    _skip_dialog_layout_suffix,
    warm_skip_dialog_skin_textures,
)


def log_if_changed(key, msg):
    """Only log if the message is different from the last logged message for this key."""
    if key not in monitor._last_log_state or monitor._last_log_state[key] != msg:
        monitor._last_log_state[key] = msg
        log(msg)

CHECK_INTERVAL = 1
SIDECAR_MTIME_CHECK_INTERVAL = 5
# Drop orphaned first-press marker state after this many seconds (wall clock).
MARKER_PENDING_STALE_SECONDS = 86400
_MARKER_PENDING_TS_PROP = "skippy_marker_pending_ts"
ICON_PATH = skippy_notification_icon(get_addon()) or ""


class PlayerMonitor(xbmc.Monitor):
    def __init__(self):
        super().__init__()
        self.segment_file_found = False
        self.prompted = set()
        self.recently_dismissed = set()
        self.current_segments = []
        self.last_video = None
        self.last_time = 0
        self.shown_missing_file_toast = False
        self.playback_ready = False
        self.playback_ready_time = 0
        self.play_start_time = 0
        self.last_toast_time = 0
        self.last_toast_for_file = {}
        self.sidecar_probe_cache = {}
        self.toast_overlap_shown = False
        self.skipped_to_nested_segment = {}  # Track when we've skipped to nested segments
        self._last_log_state = {}  # Cache for logging state changes only
        self.cleared_parent_dismissals = set()  # Track which parent dismissals have been cleared for nested segments
        self.remote_segment_cache = {}  # Online lookup cache (TV: TheIntroDB+IntroDB; movies: TheIntroDB)
        self.segment_parse_cache = None  # Parsed source segments for current playback; refreshed when sidecars change
        self.segment_processed_cache = None  # Pass 1/2 linked segments; invalidated on source/settings change
        self.nested_parent_map = {}  # child seg id -> parent seg id (built during Pass 2)
        self.online_segments_toast_shown_for_path = None
        self._home_window = None
        self.skip_dialog_modal_active = False  # Single-flight guard for ask-dialog(doModal)
        # Once per file: auto-open editor when overlaps present (open_segment_editor_on_overlap).
        self.overlap_editor_opened_for_path = None
        # Overwrite/update ask was answered (Yes or No) for this file — no re-prompt until next title.
        self.online_sidecar_save_prompt_suppressed_path = None
        self.local_to_online_sync_suppressed_path = None
        clear_prefetch_segment_cache()
        self.prefetch_tv_scheduled_path = None
        self.prefetch_tv_lock = threading.Lock()
        self.prefetch_tv_result = None
        self.deferred_remote_probe_lock = threading.Lock()
        clear_deferred_remote_probe_state(self)

    def onNotification(self, sender, method, data):
        """Open segment editor when triggered via JSON-RPC NotifyAll (legacy: service.segmenteditor)."""
        try:
            ignored_methods = {
                "AudioLibrary.OnUpdate",
                "VideoLibrary.OnUpdate",
                "GUI.OnScreensaverActivated",
                "GUI.OnScreensaverDeactivated",
                "VideoLibrary.OnScanStarted",
                "VideoLibrary.OnScanFinished",
                "AudioLibrary.OnScanStarted",
                "AudioLibrary.OnScanFinished",
            }
            if method in ignored_methods:
                return

            try:
                if isinstance(data, str):
                    data_lower = data.lower()
                elif data is not None:
                    data_lower = str(data).lower()
                else:
                    data_lower = ""
            except Exception:
                data_lower = ""

            if (
                method == "open_segment_editor"
                or method == "Other.open_segment_editor"
                or method.endswith("open_segment_editor")
                or "open_segment_editor" in data_lower
            ):
                log_always("Open segment editor (IPC / NotifyAll)")
                from segment_editor_session import open_segment_editor

                open_segment_editor()
        except Exception as exc:
            log(f"onNotification handler error: {exc}")

    def onSettingsChanged(self):
        try:
            install_marker_keymap(get_addon())
        except Exception as exc:
            log(f"⚠️ Failed to refresh Segment Marker keymap after settings change: {exc}")
        try:
            install_editor_keymap(get_addon())
        except Exception as exc:
            log(f"⚠️ Failed to refresh Segment Editor keymap after settings change: {exc}")
        try:
            import segment_editor_utils as _editor_utils

            _editor_utils.refresh_verbose_setting()
        except Exception:
            pass

        try:
            warm_skip_dialog_skin_textures(get_addon())
        except Exception as exc:
            log(f"⚠️ Failed to refresh skip dialog skin textures after settings change: {exc}")

monitor = PlayerMonitor()
player = xbmc.Player()

try:
    warm_skip_dialog_skin_textures(get_addon())
except Exception as exc:
    log(f"⚠️ Failed to warm skip dialog skin textures at service start: {exc}")


def get_video_file():
    """Resolve the playing file path. Matches the main loop: use Player.HasVideo as well as isPlayingVideo,
    because during startup/buffering Kodi often reports HasVideo before isPlayingVideo becomes true — the old
    isPlayingVideo-only check caused get_video_file() to return None while the outer loop still thought a video
    was active, so segments/metadata were never parsed until a later stop/start."""
    path = None
    try:
        if player.isPlayingVideo() or xbmc.getCondVisibility("Player.HasVideo"):
            path = player.getPlayingFile()
    except RuntimeError:
        path = None
    if not path:
        return None

    if xbmcvfs.exists(path):
        return path

    log(f"❓ Unrecognized or inaccessible path: {path}")
    return None


SkipUiSuppression = namedtuple(
    "SkipUiSuppression",
    ("suppress", "marker_modal_open", "editor_modal_open", "pending_marker_blocks"),
)


def skippy_skip_ui_suppression_state(win):
    """Defer skip-dialog work while marker/editor modals are open or a first-press mark is pending.

    Clears **skippy_marker_start** / path / timestamp when the marker feature is off or the pending
    start is stale. Caller should **continue** the service loop when **suppress** is true.
    """
    marker_modal_open = win.getProperty("skippy_marker_modal_open") == "true"
    editor_modal_open = win.getProperty("skippy_editor_modal_open") == "true"
    pending_marker_blocks = False
    if win.getProperty("skippy_marker_start") and not marker_modal_open:
        addon_guard = get_addon()
        marker_feature_on = (
            addon_get_bool(addon_guard, "segment_marker_enabled", False)
            if addon_guard
            else False
        )
        if not marker_feature_on:
            try:
                win.clearProperty("skippy_marker_start")
                win.clearProperty("skippy_marker_path")
                win.clearProperty(_MARKER_PENDING_TS_PROP)
            except RuntimeError:
                pass
            except Exception as e:
                log_service_detail(
                    "clear marker pending (feature off): %s: %s"
                    % (type(e).__name__, e),
                    tag="skipui",
                )
            log_if_changed(
                "marker_pending_cleared_disabled",
                "🧹 Cleared segment marker pending state (segment marker disabled in settings)",
            )
        else:
            ts_raw = win.getProperty(_MARKER_PENDING_TS_PROP)
            stale = False
            if ts_raw:
                try:
                    age = time.time() - float(ts_raw)
                    if age > MARKER_PENDING_STALE_SECONDS:
                        stale = True
                except (TypeError, ValueError):
                    stale = True
            if stale:
                try:
                    win.clearProperty("skippy_marker_start")
                    win.clearProperty("skippy_marker_path")
                    win.clearProperty(_MARKER_PENDING_TS_PROP)
                except RuntimeError:
                    pass
                except Exception as e:
                    log_service_detail(
                        "clear marker pending (stale): %s: %s"
                        % (type(e).__name__, e),
                        tag="skipui",
                    )
                log_if_changed(
                    "marker_pending_cleared_stale",
                    "🧹 Cleared segment marker pending start (stale: older than %ss)"
                    % int(MARKER_PENDING_STALE_SECONDS),
                )
            elif win.getProperty("skippy_marker_start"):
                playing_path = get_video_file()
                if playing_path:
                    pending_path = (win.getProperty("skippy_marker_path") or "").strip()
                    if not pending_path:
                        pending_marker_blocks = True
                    else:
                        try:
                            pending_marker_blocks = (
                                xbmcvfs.translatePath(pending_path)
                                == xbmcvfs.translatePath(playing_path)
                            )
                        except (TypeError, ValueError, OSError, RuntimeError, AttributeError):
                            pending_marker_blocks = pending_path == playing_path
                        except Exception as e:
                            log_service_detail(
                                "marker pending path compare: %s: %s\n%s"
                                % (
                                    type(e).__name__,
                                    e,
                                    traceback.format_exc(),
                                ),
                                tag="skipui",
                            )
                            pending_marker_blocks = pending_path == playing_path
    suppress = (
        marker_modal_open or editor_modal_open or pending_marker_blocks
    )
    return SkipUiSuppression(
        suppress,
        marker_modal_open,
        editor_modal_open,
        pending_marker_blocks,
    )


def infer_playback_type(item):
    showtitle = item.get("showtitle", "")
    episode = item.get("episode", -1)
    file_path = item.get("file", "")

    log_service_detail(f"📺 showtitle: {showtitle}, episode: {episode}", tag="playback")
    normalized_path = file_path.lower()

    if showtitle:
        return "episode"
    if isinstance(episode, int) and episode > 0:
        return "episode"
    # SxxExy in path (1-2 digits each); Kodi "unknown" file playback often lacks library fields
    if re.search(r"s\d{1,2}e\d{1,2}", normalized_path):
        log_service_detail(
            "🧠 Fallback heuristic matched SxxExx pattern — inferring episode",
            tag="playback",
        )
        return "episode"
    # Standalone E## (e.g. "... Insiderbericht E01 Inferno ...") common when season is omitted
    if re.search(
        r"(?:^|[\s.\-_/\\])e\d{1,2}(?:[\s.\-_/\\]|$)", normalized_path, re.I
    ):
        log_service_detail(
            "🧠 Fallback heuristic matched standalone E## pattern — inferring episode",
            tag="playback",
        )
        return "episode"

    return "movie"

def should_show_missing_file_toast(item=None, playback_type=None):
    """
    Return (toast_allowed, item). When item/type are supplied, skips JSON-RPC
    (used by the monitor loop playback context cache).
    """
    if item is not None and playback_type:
        allowed = evaluate_toast_allowed(
            item, playback_type, infer_playback_type=infer_playback_type
        )
        return allowed, item

    log_service_detail("🚦 Entered should_show_missing_file_toast()", tag="jsonrpc")
    fetched_item, allowed, _player_id = _fetch_player_item_via_jsonrpc(
        infer_playback_type, log_jsonrpc=True
    )
    return allowed, fetched_item


def _both_segment_sources_disabled_for_playback(playback_type):
    """True when both local chapter/EDL and online lookup are off for this type."""
    addon = get_addon()
    if not addon:
        return True
    if playback_type == "episode":
        loc = addon_get_bool(addon, "tv_use_local_chapter_edl", True)
        onl = addon_get_bool(addon, "tv_use_online_segment_lookup", False)
        return not loc and not onl
    if playback_type == "movie":
        loc = addon_get_bool(addon, "movie_use_local_chapter_edl", True)
        onl = addon_get_bool(addon, "movie_use_online_segment_lookup", False)
        return not loc and not onl
    return False


def _missing_segments_toast_message(playback_type, video_path):
    """Copy for the 'no segments' notification from current TV/movie source toggles."""
    addon = get_addon()
    if playback_type == "episode":
        loc = addon_get_bool(addon, "tv_use_local_chapter_edl", True) if addon else True
        onl = (
            addon_get_bool(addon, "tv_use_online_segment_lookup", False) if addon else False
        )
        type_word = "episode"
    elif playback_type == "movie":
        loc = addon_get_bool(addon, "movie_use_local_chapter_edl", True) if addon else True
        onl = (
            addon_get_bool(addon, "movie_use_online_segment_lookup", False)
            if addon
            else False
        )
        type_word = "movie"
    else:
        return "No skip segments found for this video."

    has_sidecar = bool(video_path) and local_sidecar_exists(
        video_path, segment_monitor=monitor
    )

    if not loc and onl:
        if has_sidecar:
            return (
                "No online segment data found; local segment data is available for this %s."
                % type_word
            )
        return "No online segment data found for this %s." % type_word

    if loc and not onl:
        return "No local segment data found for this %s." % type_word

    if loc and onl:
        return "No segments found locally or online for this %s." % type_word

    return "No skip segments found for this %s." % type_word


def maybe_save_online_segments_to_sidecars(video_path, segments):
    _maybe_save_online_segments_to_sidecars_impl(
        video_path, segments, monitor
    )


def maybe_save_online_segments_to_chapters_xml(video_path, segments):
    """Backward-compatible name; writes according to save format + policy."""
    _maybe_save_online_segments_to_chapters_xml_impl(
        video_path, segments, monitor
    )


def get_cached_source_segments(path, playback_type):
    return _get_cached_source_segments_impl(
        path,
        playback_type,
        segment_monitor=monitor,
        segment_player=player,
        on_remote_segments_saved=maybe_save_online_segments_to_sidecars,
        on_local_to_online_sync_check=maybe_prompt_sync_local_to_online,
        sidecar_mtime_check_interval=SIDECAR_MTIME_CHECK_INTERVAL,
    )


def parse_and_process_segments(path, current_time=None, playback_type=None):
    return _parse_and_process_segments_impl(
        path,
        current_time,
        playback_type,
        get_cached_source_segments=get_cached_source_segments,
        segment_monitor=monitor,
        segment_player=player,
        overlap_toast_icon_path=ICON_PATH,
        log_if_changed=log_if_changed,
    )


def _process_deferred_remote_probe_for_playback(video, playback_type):
    if not video or not playback_type:
        return
    try:
        process_deferred_remote_probe(
            monitor,
            video,
            playback_type,
            maybe_save_online_segments_to_sidecars,
            maybe_prompt_sync_local_to_online,
            player,
        )
    except Exception as exc:
        log_service_detail(
            'deferred remote probe apply failed: %s' % exc,
            tag='remote_probe',
        )


log_always('📡 XML-EDL Intro Skipper service started.')
install_marker_keymap(get_addon())
install_editor_keymap(get_addon())

run_service_main_loop(
    ServiceLoopBindings(
        monitor=monitor,
        player=player,
        check_interval=CHECK_INTERVAL,
        icon_path=ICON_PATH,
        get_video_file=get_video_file,
        skippy_skip_ui_suppression_state=skippy_skip_ui_suppression_state,
        log_if_changed=log_if_changed,
        infer_playback_type=infer_playback_type,
        should_show_missing_file_toast=should_show_missing_file_toast,
        both_segment_sources_disabled_for_playback=_both_segment_sources_disabled_for_playback,
        missing_segments_toast_message=_missing_segments_toast_message,
        parse_and_process_segments=parse_and_process_segments,
        should_suppress_segment_dialog=should_suppress_segment_dialog,
        re_evaluate_segment_jump_points=re_evaluate_segment_jump_points,
        is_nested_segment=is_nested_segment,
        skip_dialog_layout_suffix=_skip_dialog_layout_suffix,
        warm_skip_dialog_skin_textures=warm_skip_dialog_skin_textures,
        process_deferred_remote_probe=_process_deferred_remote_probe_for_playback,
        clear_deferred_remote_probe_state=clear_deferred_remote_probe_state,
    )
)
