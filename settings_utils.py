import json
import os
import re
import unicodedata
import xbmcaddon
import xbmc
import xbmcgui
import xbmcvfs

# Log detail when enable_verbose_logging is true (skippy_log_detail_level)
SKIPPY_LOG_ERROR_ONLY = "ErrorOnly"
SKIPPY_LOG_NORMAL = "Normal"
SKIPPY_LOG_ALL = "All"


def _redact_secrets_for_log(msg):
    """Strip common secret patterns before logging (URLs, JSON-ish key values)."""
    s = str(msg)
    s = re.sub(r"(?i)(api_key)(=)([^&\s\"]+)", r"\1\2***", s)
    s = re.sub(r'(?i)("api_key"\s*:\s*")([^"]*)(")', r"\1***\3", s)
    s = re.sub(r"(?i)(bearer\s+)([\w\-\.]+)", r"\1***", s)
    return s


def _ascii_log_text(msg):
    return (
        unicodedata.normalize("NFKD", _redact_secrets_for_log(msg))
        .encode("ascii", "ignore")
        .decode("ascii")
    )


def parse_kodi_jsonrpc_raw(raw):
    """
    Decode Kodi xbmc.executeJSONRPC string result.

    Returns (dict, None) on success. On failure returns (None, short error reason)
    suitable for detail logs — never raises.
    """
    if raw is None:
        return None, "response is None"
    if not isinstance(raw, str):
        return None, "response is not str (got %s)" % type(raw).__name__
    text = raw.strip()
    if not text:
        return None, "empty response string"
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        head = raw[:220].replace("\r", " ").replace("\n", " ")
        return None, "JSONDecodeError: %s; head=%r" % (exc, head)
    if not isinstance(data, dict):
        return None, "top-level JSON is %s, expected object" % type(data).__name__
    return data, None


def get_addon():
    """Get the addon object, handling cases where addon is being updated/uninstalled."""
    try:
        # We pass the ID explicitly so Kodi knows exactly what we want
        return xbmcaddon.Addon('service.skippy')
    except RuntimeError:
        # If the addon is currently being uninstalled/updated, 
        # this will return None instead of crashing
        return None


def get_localized(addon, string_id, default="", *args):
    """Resolve ``strings.po`` id; fall back to ``default``; optional ``%`` formatting.

    Empty or numeric-only Kodi returns are treated as missing (common when an
    id is not in the active language file).
    """
    text = ""
    if addon is not None and string_id is not None:
        try:
            text = addon.getLocalizedString(int(string_id)) or ""
        except Exception:
            text = ""
    if not text or text.strip() == str(string_id):
        text = default if default is not None else ""
    if args:
        try:
            return text % args
        except Exception:
            return text
    return text


def skippy_notification_icon(addon):
    """
    Filesystem path for Dialog().notification(..., icon=...).

    Prefer metadata icon from Kodi (correct for packaged assets); fall back to icon.png
    beside addon.xml. Forward slashes — some builds ignore Windows backslash paths for
    toast images and show the default info glyph instead.
    """
    if not addon:
        return ""
    candidates = []
    try:
        meta = addon.getAddonInfo("icon")
        if meta:
            candidates.append(meta)
    except Exception:
        pass
    try:
        root = addon.getAddonInfo("path")
        if root:
            candidates.append(os.path.join(root, "icon.png"))
    except Exception:
        pass
    for raw in candidates:
        if not raw:
            continue
        path = raw.replace("\\", "/")
        try:
            if xbmcvfs.exists(path):
                return path
        except Exception:
            pass
    if candidates:
        return (candidates[0] or "").replace("\\", "/")
    return ""


def notify_skippy(
    addon, message, title="Skippy", time_ms=4500, *, prefer_builtin=False
):
    """Toast with Skippy icon. Use ``prefer_builtin=True`` when a fullscreen WindowXML/modal hides ``Dialog.notification``."""

    if addon is None:
        try:
            addon = xbmcaddon.Addon("service.skippy")
        except Exception:
            addon = None
    icon = skippy_notification_icon(addon) if addon else ""
    dlg = None
    try:
        dlg = xbmcgui.Dialog()
    except Exception:
        dlg = None

    def _builtin():
        tc = (
            ((title or "Skippy").replace(",", " — ").replace("\n", " ").strip())
            .replace('"', "'")[:240]
        )
        mc = (
            ((message or "").replace(",", " — ").replace("\n", " ").strip())
            .replace('"', "'")[:2000]
        )
        ic = (icon or "").strip().replace("\\", "/")
        tm = max(1500, int(time_ms))
        try:
            if ic:
                xbmc.executebuiltin(
                    'Notification("%s","%s",%d,"%s")' % (tc, mc, tm, ic)
                )
            else:
                xbmc.executebuiltin('Notification("%s","%s",%d)' % (tc, mc, tm))
        except Exception:
            pass

    if prefer_builtin:
        _builtin()
        return

    if dlg is not None:
        try:
            dlg.notification(
                title or "Skippy",
                message or "",
                icon=icon,
                time=max(1500, int(time_ms)),
                sound=False,
            )
            return
        except TypeError:
            try:
                dlg.notification(
                    title or "Skippy",
                    message or "",
                    icon,
                    max(1500, int(time_ms)),
                    False,
                )
                return
            except Exception:
                pass
        except Exception:
            pass

    _builtin()


def _addon_read_setting_raw(addon, key):
    """
    Read setting as string. Prefer getSetting; call getSettingString only if getSetting raises.

    On some CoreELEC/Kodi builds, getSetting returns \"\" for false bools. The old logic treated
    that as \"missing\" and fell through to getSettingString, which still logs C++ Invalid setting
    type for non-string setting types even when Python catches the exception.
    """
    if not addon:
        return None
    try:
        s = addon.getSetting(key)
        if s is not None:
            return str(s)
    except Exception:
        pass
    if hasattr(addon, "getSettingString"):
        try:
            s = addon.getSettingString(key)
            if s is not None:
                return str(s)
        except Exception:
            pass
    return None


def skippy_log_effective_detail_level(addon):
    """
    Returns 'Off', SKIPPY_LOG_ERROR_ONLY, SKIPPY_LOG_NORMAL, or SKIPPY_LOG_ALL.
    """
    if not addon:
        return "Off"
    if not addon_get_bool(addon, "enable_verbose_logging", False):
        return "Off"
    lv = addon_get_setting_text(addon, "skippy_log_detail_level", SKIPPY_LOG_NORMAL)
    lv = (lv or SKIPPY_LOG_NORMAL).strip()
    if lv == SKIPPY_LOG_ERROR_ONLY:
        return SKIPPY_LOG_ERROR_ONLY
    if lv == SKIPPY_LOG_ALL:
        return SKIPPY_LOG_ALL
    return SKIPPY_LOG_NORMAL


def addon_get_bool(addon, key, default=False):
    """
    Read bool settings without getSettingBool (some Kodi/CoreELEC builds log Invalid setting type).
    Uses _addon_read_setting_raw (getSetting first, then getSettingString).
    """
    if not addon:
        return default
    s = _addon_read_setting_raw(addon, key)
    if s is None or s == "":
        return default
    return str(s).lower() in ("true", "1", "yes")


def addon_get_setting_text(addon, key, default=""):
    """Read a text/hidden setting; fall back to getSetting if getSettingString fails."""
    if not addon:
        return default
    s = _addon_read_setting_raw(addon, key)
    if s is None:
        return default
    return s


def addon_get_int(addon, key, default=0, minimum=None, maximum=None):
    """Read integer settings without getSettingInt when that API throws on some builds."""
    if not addon:
        return default
    raw = _addon_read_setting_raw(addon, key)
    if raw is None or str(raw).strip() == "":
        v = default
    else:
        try:
            v = int(str(raw).strip())
        except (TypeError, ValueError):
            v = default
    if minimum is not None:
        v = max(minimum, v)
    if maximum is not None:
        v = min(maximum, v)
    return v


def get_skip_jump_offset_seconds(addon):
    """Seconds added to the computed skip destination (-5..+5). Default 0."""
    return addon_get_int(addon, "skip_jump_offset_seconds", 0, minimum=-5, maximum=5)


def compute_skip_seek_destination_seconds(segment, addon):
    """
    Seek target when skipping ``segment``: base jump (next segment start or
    end_seconds+1) plus **Jump offset** from settings. Clamped >= 0.
    """
    base = (
        segment.next_segment_start
        if segment.next_segment_start is not None
        else segment.end_seconds + 1.0
    )
    off = float(get_skip_jump_offset_seconds(addon))
    return max(0.0, float(base) + off)


def log(msg):
    """Standard INFO trace when verbose is on and log level is Normal or All detail."""
    addon = get_addon()
    if not addon:
        xbmc.log(f"[service.skippy - SettingsUtils] {_ascii_log_text(msg)} (shutdown)", xbmc.LOGINFO)
        return
    lv = skippy_log_effective_detail_level(addon)
    if lv == "Off" or lv == SKIPPY_LOG_ERROR_ONLY:
        return
    xbmc.log(f"[service.skippy - SettingsUtils] {_ascii_log_text(msg)}", xbmc.LOGINFO)


def log_error(msg):
    """LOGERROR when verbose is on (any level except Off). For Errors-only mode this is the main output."""
    addon = get_addon()
    if not addon:
        return
    lv = skippy_log_effective_detail_level(addon)
    if lv == "Off":
        return
    xbmc.log(f"[service.skippy - SettingsUtils] {_ascii_log_text(msg)}", xbmc.LOGERROR)


def log_remote(msg):
    """Online lookup INFO lines; Normal or All only (same channel as former _rlog)."""
    addon = get_addon()
    if not addon:
        return
    lv = skippy_log_effective_detail_level(addon)
    if lv not in (SKIPPY_LOG_NORMAL, SKIPPY_LOG_ALL):
        return
    xbmc.log("[service.skippy - remote] %s" % _ascii_log_text(msg), xbmc.LOGINFO)


def log_segment_detail(msg):
    """High-frequency SegmentItem traces; All detail only."""
    addon = get_addon()
    if not addon:
        return
    if skippy_log_effective_detail_level(addon) != SKIPPY_LOG_ALL:
        return
    try:
        aid = addon.getAddonInfo("id")
    except Exception:
        aid = "service.skippy"
    xbmc.log(f"[{aid} - SegmentItem] {_ascii_log_text(msg)}", xbmc.LOGINFO)


def log_service_detail(msg, *, tag="SettingsUtils"):
    """Per-loop JSON-RPC, path probes, per-atom parse lines; All detail only (quiets Normal).

    tag: short sub-source for kodi.log filters, e.g. jsonrpc, segments, sidecar, playback.
    """
    addon = get_addon()
    if not addon:
        return
    if skippy_log_effective_detail_level(addon) != SKIPPY_LOG_ALL:
        return
    xbmc.log(f"[service.skippy - {tag}] {_ascii_log_text(msg)}", xbmc.LOGINFO)


def log_segment(msg):
    """SegmentItem INFO when verbose is Normal or All (not Error-only)."""
    addon = get_addon()
    if not addon:
        return
    lv = skippy_log_effective_detail_level(addon)
    if lv == "Off" or lv == SKIPPY_LOG_ERROR_ONLY:
        return
    try:
        aid = addon.getAddonInfo("id")
    except Exception:
        aid = "service.skippy"
    xbmc.log(f"[{aid} - SegmentItem] {_ascii_log_text(msg)}", xbmc.LOGINFO)


def _playback_snap_trim(s, max_len=120):
    if s is None:
        return ""
    s = str(s).replace("\r", " ").replace("\n", " ").strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


def log_playback_settings_snapshot(addon=None):
    """
    Log a compact settings bundle once per new playback (verbose Normal or All only).
    Uses setting ids as in settings.xml; does not log API key values (only whether set).
    """
    addon = addon or get_addon()
    if not addon:
        return
    lv = skippy_log_effective_detail_level(addon)
    if lv == "Off" or lv == SKIPPY_LOG_ERROR_ONLY:
        return

    def bo(k, default=False):
        return "true" if addon_get_bool(addon, k, default) else "false"

    def tx(k, default=""):
        v = addon_get_setting_text(addon, k, default)
        if v is None:
            v = default
        return str(v).replace("\r", " ").replace("\n", " ").strip()

    def ni(k, default=0):
        return str(addon_get_int(addon, k, default))

    tmdb_set = "true" if (tx("tv_tmdb_api_key", "") or "").strip() else "false"
    verb = "true" if addon_get_bool(addon, "enable_verbose_logging", False) else "false"
    detail = tx("skippy_log_detail_level", SKIPPY_LOG_NORMAL) or SKIPPY_LOG_NORMAL
    positions = "%s/%s" % (
        tx("skip_dialog_position", "?"),
        tx("minimal_skip_dialog_position", "?"),
    )

    part_skip = ", ".join(
        [
            "enable_skip_movies=%s" % bo("enable_skip_movies", True),
            "enable_skip_episodes=%s" % bo("enable_skip_episodes", True),
            "show_skip_dialog_movies=%s" % bo("show_skip_dialog_movies", True),
            "show_skip_dialog_episodes=%s" % bo("show_skip_dialog_episodes", True),
            "skip_overlapping_segments=%s" % bo("skip_overlapping_segments", True),
            "open_segment_editor_on_overlap=%s" % bo("open_segment_editor_on_overlap", False),
            "ignore_internal_edl_actions=%s" % bo("ignore_internal_edl_actions", True),
            "rewind_threshold_seconds=%s" % ni("rewind_threshold_seconds", 8),
            "skip_jump_offset_seconds=%s" % ni("skip_jump_offset_seconds", 0),
            "ask_dialog_debounce_ms=%s" % ni("ask_dialog_debounce_ms", 300),
            "skip_dialog_mode=%s" % tx("skip_dialog_mode", "Full"),
            "skip_dialog_positions_full_minimal=%s" % positions,
            "show_progress_bar=%s" % bo("show_progress_bar", True),
            "progress_bar_countdown=%s" % bo("progress_bar_countdown", False),
            "progress_bar_style=%s" % tx("progress_bar_style", "progress_mid.png"),
            "progress_bar_height=%s" % ni("progress_bar_height", 16),
            "smooth_progress_bar=%s" % bo("smooth_progress_bar", False),
            "progress_bar_updates_per_second=%s" % ni("progress_bar_updates_per_second", 4),
            "hide_ending_text=%s" % bo("hide_ending_text", False),
            "show_skip_button_focus_texture=%s" % bo("show_skip_button_focus_texture", True),
        ]
    )
    part_sources = ", ".join(
        [
            "tv_use_local_chapter_edl=%s" % bo("tv_use_local_chapter_edl", True),
            "tv_use_online_segment_lookup=%s" % bo("tv_use_online_segment_lookup", False),
            "tv_segment_source_priority=%s" % tx("tv_segment_source_priority", "LocalFirst"),
            "tv_online_merge_priority=%s" % tx("tv_online_merge_priority", "TheIntroDBFirst"),
            "movie_use_local_chapter_edl=%s" % bo("movie_use_local_chapter_edl", True),
            "movie_use_online_segment_lookup=%s" % bo("movie_use_online_segment_lookup", False),
            "movie_segment_source_priority=%s" % tx("movie_segment_source_priority", "LocalFirst"),
            "movie_online_merge_priority=%s" % tx("movie_online_merge_priority", "TheIntroDBFirst"),
            "save_online_segments_to_chapters_xml=%s" % bo("save_online_segments_to_chapters_xml", False),
            "save_online_segments_format=%s" % tx("save_online_segments_format", "Both"),
            "save_online_chapters_existing_policy=%s" % tx("save_online_chapters_existing_policy", "SkipIfExists"),
            "save_online_chapters_backup_before_overwrite=%s" % bo("save_online_chapters_backup_before_overwrite", True),
            "online_sidecar_snap_neighbor_start=%s" % bo("online_sidecar_snap_neighbor_start", False),
            "online_sidecar_snap_neighbor_end=%s" % bo("online_sidecar_snap_neighbor_end", False),
            "tv_prefetch_next_episode=%s" % bo("tv_prefetch_next_episode", True),
        ]
    )
    part_api = ", ".join(
        [
            "tv_tmdb_resolve_missing_ids=%s" % bo("tv_tmdb_resolve_missing_ids", True),
            "tv_tmdb_api_key_set=%s" % tmdb_set,
            "tv_tmdb_use_helper_api_key=%s" % bo("tv_tmdb_use_helper_api_key", True),
            "remote_api_failure_cooldown_seconds=%s" % ni("remote_api_failure_cooldown_seconds", 120),
            "toast_not_found_tv=%s" % bo("show_not_found_toast_for_tv_episodes", True),
            "toast_not_found_movie=%s" % bo("show_not_found_toast_for_movies", False),
            "toast_overlap=%s" % bo("show_toast_for_overlapping_nested_segments", False),
            "toast_skipped_segment=%s" % bo("show_toast_for_skipped_segment", True),
            "toast_segment_marker=%s"
            % bo("show_toast_for_segment_marker", True),
            "enable_verbose_logging=%s" % verb,
            "skippy_log_detail_level=%s" % detail,
        ]
    )
    kw = _playback_snap_trim(tx("custom_segment_keywords", ""), 160)
    always = _playback_snap_trim(tx("segment_always_skip", ""), 100)
    ask = _playback_snap_trim(tx("segment_ask_skip", ""), 100)
    never = _playback_snap_trim(tx("segment_never_skip", ""), 100)
    edl_map = _playback_snap_trim(tx("edl_action_mapping", ""), 200)

    log("📋 Playback settings snapshot [skip & dialog] — %s" % part_skip)
    log(
        "📋 Playback settings snapshot [keyword lists truncated] — custom_segment_keywords=%r segment_always_skip=%r segment_ask_skip=%r segment_never_skip=%r edl_action_mapping=%r"
        % (kw, always, ask, never, edl_map)
    )
    log("📋 Playback settings snapshot [TV/movie sources & save online] — %s" % part_sources)
    log("📋 Playback settings snapshot [API, toasts, logging] — %s" % part_api)


def log_always(msg):
    """Startup/shutdown and rare critical paths; always INFO."""
    addon = get_addon()
    if addon:
        xbmc.log(f"[service.skippy - SettingsUtils] {msg}", xbmc.LOGINFO)
    else:
        xbmc.log(f"[service.skippy - SettingsUtils] {msg} (shutdown)", xbmc.LOGINFO)

def normalize_label(label):
    # Normalize and lowercase labels for consistent matching
    return unicodedata.normalize("NFKC", label or "").strip().lower()


# Must stay in sync with ``resources/settings.xml`` default for ``custom_segment_keywords``.
_DEFAULT_CUSTOM_SEGMENT_KEYWORDS = (
    "intro,recap,main,credits,outro,prologue,epilogue,ad,ads,sponsor,sponsors,"
    "commercial,commercials,preview,next time on,next on,sneak peek,last time on,"
    "last on,previously on,closing,ending,behind the scenes,behind-the-scenes,bts,featurette"
)


def format_segment_label_for_ui(label):
    """Format comma-list keywords for picker display (title-like when all lowercase)."""
    value = (label or "").strip()
    if not value:
        return value
    if any(ch.isupper() for ch in value):
        return value
    return " ".join(word[:1].upper() + word[1:] for word in value.split())


def get_custom_segment_keyword_labels(addon=None):
    """
    Ordered unique labels from **Segment keywords to watch for** (comma-separated).
    Shared by Segment Marker and Segment Editor label pickers.
    """
    if addon:
        raw = addon_get_setting_text(
            addon,
            "custom_segment_keywords",
            _DEFAULT_CUSTOM_SEGMENT_KEYWORDS,
        )
        if raw is None or not str(raw).strip():
            raw = _DEFAULT_CUSTOM_SEGMENT_KEYWORDS
    else:
        raw = _DEFAULT_CUSTOM_SEGMENT_KEYWORDS
    keywords = [k.strip() for k in str(raw).split(",") if k.strip()]
    if not keywords:
        keywords = [
            k.strip()
            for k in _DEFAULT_CUSTOM_SEGMENT_KEYWORDS.split(",")
            if k.strip()
        ]
    seen = set()
    unique = []
    for k in keywords:
        kl = normalize_label(k)
        if kl not in seen:
            seen.add(kl)
            unique.append(format_segment_label_for_ui(k))
    return unique


# Last values logged for skip / skip-dialog settings (service polls these frequently).
_skip_enabled_last_logged = {}
_dialog_enabled_last_logged = {}
_invalid_playback_type_warned = set()


def is_skip_enabled(playback_type):
    """Check if skipping is enabled at all for the given playback type."""
    addon = get_addon()
    if not addon:
        return False  # During update/uninstall, default to disabled
    if playback_type == "movie":
        enabled = addon_get_bool(addon, "enable_skip_movies")
        prev = _skip_enabled_last_logged.get("movie")
        if prev != enabled:
            _skip_enabled_last_logged["movie"] = enabled
            log(f"🎬 Skip enabled for movies: {enabled}")
        return enabled
    if playback_type == "episode":
        enabled = addon_get_bool(addon, "enable_skip_episodes")
        prev = _skip_enabled_last_logged.get("episode")
        if prev != enabled:
            _skip_enabled_last_logged["episode"] = enabled
            log(f"📺 Skip enabled for episodes: {enabled}")
        return enabled
    if playback_type not in _invalid_playback_type_warned:
        _invalid_playback_type_warned.add(playback_type)
        log(f"⚠ Unknown playback type '{playback_type}' — skip disabled")
    return False


def is_skip_dialog_enabled(playback_type):
    """Check if skip dialog should be shown. Requires both skip and dialog to be enabled."""
    if not is_skip_enabled(playback_type):
        return False

    addon = get_addon()
    if not addon:
        return False  # During update/uninstall, default to disabled
    if playback_type == "movie":
        enabled = addon_get_bool(addon, "show_skip_dialog_movies")
        prev = _dialog_enabled_last_logged.get("movie")
        if prev != enabled:
            _dialog_enabled_last_logged["movie"] = enabled
            log(f"🎬 Skip dialog enabled for movies: {enabled}")
        return enabled
    if playback_type == "episode":
        enabled = addon_get_bool(addon, "show_skip_dialog_episodes")
        prev = _dialog_enabled_last_logged.get("episode")
        if prev != enabled:
            _dialog_enabled_last_logged["episode"] = enabled
            log(f"📺 Skip dialog enabled for episodes: {enabled}")
        return enabled
    return False

def get_user_skip_mode(label):
    title = normalize_label(label)
    log_service_detail(f"🔍 Determining skip mode for: '{title}'")

    addon = get_addon()
    if not addon:
        return "ask"  # During update/uninstall, default to ask

    def parse_setting(key):
        raw = addon_get_setting_text(addon, key, "") or ""
        if not raw.strip():
            log_service_detail(f"⚠ Setting '{key}' is empty")
        return set(normalize_label(x) for x in raw.split(",") if x.strip())

    always = parse_setting("segment_always_skip")
    ask = parse_setting("segment_ask_skip")
    never = parse_setting("segment_never_skip")

    if not always and not ask and not never:
        log("⚠️ All skip mode lists are empty — using default behavior: ask")

    if title in always:
        log_service_detail(f"⚡ Matched in 'always' list: {title}")
        return "auto"
    if title in ask:
        log_service_detail(f"❓ Matched in 'ask' list: {title}")
        return "ask"
    if title in never:
        log_service_detail(f"🚫 Matched in 'never' list: {title}")
        return "never"

    log_service_detail(f"🕳️ No skip mode match found for: {title} → using default: ask")
    return "ask"

# Must stay in sync with ``resources/settings.xml`` default for ``edl_action_mapping``.
_DEFAULT_EDL_ACTION_MAPPING = (
    "4:Segment,5:Intro,6:Ad,7:Commercial,8:Credits,9:Recap,10:Prologue,11:Epilogue,"
    "12:Main,13:Outro,14:Unknown,15:Preview,16:Sponsor,17:Cold_open"
)


def _parse_edl_type_map_pairs(raw):
    """Parse mapping string into action_int -> normalized label."""
    mapping = {}
    for pair in [entry.strip() for entry in (raw or "").split(",") if ":" in entry]:
        try:
            action, label = pair.split(":", 1)
            action_int = int(action.strip())
            mapping[action_int] = normalize_label(label)
        except Exception:
            pass
    return mapping


def _parse_edl_label_to_action_pairs(raw):
    """Last entry wins for duplicate labels in the same string."""
    label_to_action = {}
    for pair in [entry.strip() for entry in (raw or "").split(",") if ":" in entry]:
        try:
            action, label = pair.split(":", 1)
            label_to_action[normalize_label(label)] = int(action.strip())
        except Exception:
            pass
    return label_to_action


def get_edl_type_map():
    """action int -> normalized label; user mapping overlays addon defaults."""
    addon = get_addon()
    if not addon:
        return {}
    raw = addon_get_setting_text(addon, "edl_action_mapping", "") or ""
    log(f"🔁 Raw EDL mapping string: {raw}")
    base = _parse_edl_type_map_pairs(_DEFAULT_EDL_ACTION_MAPPING)
    user = _parse_edl_type_map_pairs(raw)
    merged = {**base, **user}
    log(
        "🔁 EDL action map: %d type(s) merged (%d from user string)"
        % (len(merged), len(user))
    )
    return merged


def get_edl_label_to_action_map():
    """
    Normalized label -> EDL action int; user mapping overlays addon defaults
    (same merge as get_edl_type_map) so legacy installs get e.g. Outro → 13.
    """
    addon = get_addon()
    if not addon:
        return {}
    raw = addon_get_setting_text(addon, "edl_action_mapping", "") or ""
    base = _parse_edl_label_to_action_pairs(_DEFAULT_EDL_ACTION_MAPPING)
    user = _parse_edl_label_to_action_pairs(raw)
    return {**base, **user}


# This function has been updated to use the correct API for Kodi v21.2 Omega
def show_overlapping_toast():
    addon = get_addon()
    if not addon:
        return False
    return addon_get_bool(addon, "show_toast_for_overlapping_nested_segments", False)