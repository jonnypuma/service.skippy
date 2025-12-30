import unicodedata
import xbmcaddon
import xbmc
import xbmcvfs

def get_addon():
    return xbmcaddon.Addon()

def log(msg):
    if get_addon().getSettingBool("enable_verbose_logging"):
        xbmc.log(f"[{get_addon().getAddonInfo('id')} - SettingsUtils] {msg}", xbmc.LOGINFO)

def log_always(msg):
    xbmc.log(f"[{get_addon().getAddonInfo('id')} - SettingsUtils] {msg}", xbmc.LOGINFO)

def normalize_label(label):
    # Normalize and lowercase labels for consistent matching
    return unicodedata.normalize("NFKC", label or "").strip().lower()

def is_skip_enabled(playback_type):
    """Check if skipping is enabled at all for the given playback type."""
    addon = get_addon()
    if playback_type == "movie":
        enabled = addon.getSettingBool("enable_skip_movies")
        log(f"🎬 Skip enabled for movies: {enabled}")
        return enabled
    elif playback_type == "episode":
        enabled = addon.getSettingBool("enable_skip_episodes")
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
    if playback_type == "movie":
        enabled = addon.getSettingBool("show_skip_dialog_movies")
        log(f"🎬 Skip dialog enabled for movies: {enabled}")
        return enabled
    elif playback_type == "episode":
        enabled = addon.getSettingBool("show_skip_dialog_episodes")
        log(f"📺 Skip dialog enabled for episodes: {enabled}")
        return enabled
    log(f"⚠ Unknown playback type '{playback_type}' — skip dialog disabled")
    return False

def get_user_skip_mode(label):
    title = normalize_label(label)
    log(f"🔍 Determining skip mode for: '{title}'")

    def parse_setting(key):
        raw = get_addon().getSetting(key)
        if not raw:
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
    raw = get_addon().getSetting("edl_action_mapping")
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
    try:
        # Get the settings object from the addon
        settings = get_addon().getSettings()
        # Call the getBool method on the settings object
        return settings.getBool("show_toast_for_overlapping_nested_segments")
    except Exception as e:
        log_always(f"EXCEPTION: {e}")
        # Return False as a safe fallback if the setting isn't available or the call fails
        return False