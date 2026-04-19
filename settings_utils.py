import unicodedata
import xbmcaddon
import xbmc
import xbmcvfs

# Log detail when enable_verbose_logging is true (skippy_log_detail_level)
SKIPPY_LOG_ERROR_ONLY = "ErrorOnly"
SKIPPY_LOG_NORMAL = "Normal"
SKIPPY_LOG_ALL = "All"


def get_addon():
    """Get the addon object, handling cases where addon is being updated/uninstalled."""
    try:
        # We pass the ID explicitly so Kodi knows exactly what we want
        return xbmcaddon.Addon('service.skippy')
    except RuntimeError:
        # If the addon is currently being uninstalled/updated, 
        # this will return None instead of crashing
        return None


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


def log(msg):
    """Standard INFO trace when verbose is on and log level is Normal or All detail."""
    addon = get_addon()
    if not addon:
        xbmc.log(f"[service.skippy - SettingsUtils] {msg} (shutdown)", xbmc.LOGINFO)
        return
    lv = skippy_log_effective_detail_level(addon)
    if lv == "Off" or lv == SKIPPY_LOG_ERROR_ONLY:
        return
    xbmc.log(f"[service.skippy - SettingsUtils] {msg}", xbmc.LOGINFO)


def log_error(msg):
    """LOGERROR when verbose is on (any level except Off). For Errors-only mode this is the main output."""
    addon = get_addon()
    if not addon:
        return
    lv = skippy_log_effective_detail_level(addon)
    if lv == "Off":
        return
    xbmc.log(f"[service.skippy - SettingsUtils] {msg}", xbmc.LOGERROR)


def log_remote(msg):
    """Online lookup INFO lines; Normal or All only (same channel as former _rlog)."""
    addon = get_addon()
    if not addon:
        return
    lv = skippy_log_effective_detail_level(addon)
    if lv not in (SKIPPY_LOG_NORMAL, SKIPPY_LOG_ALL):
        return
    xbmc.log("[service.skippy - remote] %s" % msg, xbmc.LOGINFO)


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
    xbmc.log(f"[{aid} - SegmentItem] {msg}", xbmc.LOGINFO)


def log_service_detail(msg):
    """Per-loop JSON-RPC, path probes, per-atom parse lines; All detail only (quieter Normal)."""
    addon = get_addon()
    if not addon:
        return
    if skippy_log_effective_detail_level(addon) != SKIPPY_LOG_ALL:
        return
    xbmc.log(f"[service.skippy - SettingsUtils] {msg}", xbmc.LOGINFO)


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
    xbmc.log(f"[{aid} - SegmentItem] {msg}", xbmc.LOGINFO)


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
            "ignore_internal_edl_actions=%s" % bo("ignore_internal_edl_actions", True),
            "rewind_threshold_seconds=%s" % ni("rewind_threshold_seconds", 8),
            "skip_dialog_mode=%s" % tx("skip_dialog_mode", "Full"),
            "skip_dialog_positions_full_minimal=%s" % positions,
            "show_progress_bar=%s" % bo("show_progress_bar", True),
            "hide_ending_text=%s" % bo("hide_ending_text", False),
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
            "save_online_chapters_existing_policy=%s" % tx("save_online_chapters_existing_policy", "SkipIfExists"),
            "save_online_chapters_backup_before_overwrite=%s" % bo("save_online_chapters_backup_before_overwrite", True),
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

def is_skip_enabled(playback_type):
    """Check if skipping is enabled at all for the given playback type."""
    addon = get_addon()
    if not addon:
        return False  # During update/uninstall, default to disabled
    if playback_type == "movie":
        enabled = addon_get_bool(addon, "enable_skip_movies")
        log(f"🎬 Skip enabled for movies: {enabled}")
        return enabled
    elif playback_type == "episode":
        enabled = addon_get_bool(addon, "enable_skip_episodes")
        log(f"📺 Skip enabled for episodes: {enabled}")
        return enabled
    log(f"⚠ Unknown playback type '{playback_type}' — skip disabled")
    return False

def is_skip_dialog_enabled(playback_type):
    """Check if skip dialog should be shown. Requires both skip and dialog to be enabled."""
    if not is_skip_enabled(playback_type):
        log(f"🚫 Skipping disabled for {playback_type} — dialog will not be shown")
        return False
    
    addon = get_addon()
    if not addon:
        return False  # During update/uninstall, default to disabled
    if playback_type == "movie":
        enabled = addon_get_bool(addon, "show_skip_dialog_movies")
        log(f"🎬 Skip dialog enabled for movies: {enabled}")
        return enabled
    elif playback_type == "episode":
        enabled = addon_get_bool(addon, "show_skip_dialog_episodes")
        log(f"📺 Skip dialog enabled for episodes: {enabled}")
        return enabled
    log(f"⚠ Unknown playback type '{playback_type}' — skip dialog disabled")
    return False

def get_user_skip_mode(label):
    title = normalize_label(label)
    log(f"🔍 Determining skip mode for: '{title}'")

    addon = get_addon()
    if not addon:
        return "ask"  # During update/uninstall, default to ask

    def parse_setting(key):
        raw = addon_get_setting_text(addon, key, "") or ""
        if not raw.strip():
            log(f"⚠ Setting '{key}' is empty")
        return set(normalize_label(x) for x in raw.split(",") if x.strip())

    always = parse_setting("segment_always_skip")
    ask = parse_setting("segment_ask_skip")
    never = parse_setting("segment_never_skip")

    if not always and not ask and not never:
        log("⚠️ All skip mode lists are empty — using default behavior: ask")

    if title in always:
        log(f"⚡ Matched in 'always' list: {title}")
        return "auto"
    if title in ask:
        log(f"❓ Matched in 'ask' list: {title}")
        return "ask"
    if title in never:
        log(f"🚫 Matched in 'never' list: {title}")
        return "never"

    log(f"🕳️ No skip mode match found for: {title} → using default: ask")
    return "ask"

def get_edl_type_map():
    addon = get_addon()
    if not addon:
        return {}  # During update/uninstall, return empty mapping
    raw = addon_get_setting_text(addon, "edl_action_mapping", "") or ""
    log(f"🔁 Raw EDL mapping string: {raw}")
    pairs = [entry.strip() for entry in raw.split(",") if ":" in entry]
    mapping = {}
    for pair in pairs:
        try:
            action, label = pair.split(":", 1)
            action_int = int(action.strip())
            normalized_label = normalize_label(label)
            mapping[action_int] = normalized_label
            log(f"✅ Parsed mapping: {action_int} → '{normalized_label}'")
        except Exception as e:
            log(f"⚠️ Skipped invalid mapping '{pair}': {e}")
    return mapping

# This function has been updated to use the correct API for Kodi v21.2 Omega
def show_overlapping_toast():
    addon = get_addon()
    if not addon:
        return False
    return addon_get_bool(addon, "show_toast_for_overlapping_nested_segments", False)