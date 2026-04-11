import os
import time
import platform
import unicodedata
import xml.etree.ElementTree as ET
import json
import re
import xbmc
import xbmcgui
import xbmcvfs
import xbmcaddon

from settings_utils import is_skip_dialog_enabled, is_skip_enabled
from skipdialog import SkipDialog, _minimal_plate_filename
from segment_item import SegmentItem
from settings_utils import (
    get_user_skip_mode,
    get_edl_type_map,
    get_addon,
    log,
    log_always,
    normalize_label,
    show_overlapping_toast,
)

_SKIP_DIALOG_FULL_FILES = (
    'SkipDialog_BottomRight.xml',
    'SkipDialog_BottomLeft.xml',
    'SkipDialog_TopLeft.xml',
    'SkipDialog_TopRight.xml',
)
_SKIP_DIALOG_MINIMAL_FILES = (
    'Minimal_Skip_Dialog_BottomRight.xml',
    'Minimal_Skip_Dialog_BottomLeft.xml',
    'Minimal_Skip_Dialog_TopLeft.xml',
    'Minimal_Skip_Dialog_TopRight.xml',
)
_FULL_MODE_BUTTON_IDS = frozenset({'3012', '3013', '3015', '3016'})
_MINIMAL_PLATE_IMAGE_ID = '3021'
_DEFAULT_SKIP_DIALOG_CORNER = 'Bottom Right'


def _skip_dialog_layout_suffix(addon, setting_id):
    """Stored value matches Full mode: e.g. 'Bottom Right' from values list."""
    raw = (addon.getSetting(setting_id) or '').strip() or _DEFAULT_SKIP_DIALOG_CORNER
    return raw.replace(' ', '')


def _get_skins_720p_dir():
    addon = get_addon()
    if not addon:
        return None
    return os.path.join(addon.getAddonInfo('path'), 'resources', 'skins', 'default', '720p')


def _set_button_texturefocus(control, texture_path):
    for child in control:
        if child.tag == 'texturefocus':
            child.text = texture_path
            return
    el = ET.SubElement(control, 'texturefocus')
    el.text = texture_path


def _write_skin_xml(tree, xml_path):
    try:
        ET.indent(tree, space='  ')
    except AttributeError:
        pass
    kwargs = {"encoding": "utf-8", "xml_declaration": True}
    try:
        tree.write(xml_path, short_empty_elements=False, **kwargs)
    except TypeError:
        tree.write(xml_path, **kwargs)


def _update_full_skip_dialog_textures(texture_path):
    """Set texturefocus on Full mode skip/close buttons only (by control id)."""
    try:
        xml_dir = _get_skins_720p_dir()
        if not xml_dir or not texture_path:
            return
        for xml_file in _SKIP_DIALOG_FULL_FILES:
            xml_path = os.path.join(xml_dir, xml_file)
            if not os.path.isfile(xml_path):
                continue
            tree = ET.parse(xml_path)
            root = tree.getroot()
            for control in root.iter('control'):
                if control.get('type') != 'button':
                    continue
                cid = control.get('id')
                if cid in _FULL_MODE_BUTTON_IDS:
                    _set_button_texturefocus(control, texture_path)
            _write_skin_xml(tree, xml_path)
            log(f"📝 Updated Full dialog {xml_file} button focus texture: {texture_path}")
    except Exception as e:
        log(f"⚠️ Failed to update Full skip dialog XML: {e}")


def _set_image_texture(control, texture_path):
    for child in control:
        if child.tag == 'texture':
            child.text = texture_path
            return
    el = ET.SubElement(control, 'texture')
    el.text = texture_path


def _update_minimal_skip_dialog_textures(texture_filename):
    """Minimal chip: plate image 3021 + single skip button 3012 texturefocus."""
    try:
        xml_dir = _get_skins_720p_dir()
        if not xml_dir or not texture_filename:
            return
        for xml_file in _SKIP_DIALOG_MINIMAL_FILES:
            xml_path = os.path.join(xml_dir, xml_file)
            if not os.path.isfile(xml_path):
                continue
            tree = ET.parse(xml_path)
            root = tree.getroot()
            for control in root.iter('control'):
                ctype = control.get('type')
                cid = control.get('id')
                if ctype == 'image' and cid == _MINIMAL_PLATE_IMAGE_ID:
                    _set_image_texture(control, texture_filename)
                if ctype == 'button' and cid == '3012':
                    _set_button_texturefocus(control, texture_filename)
            _write_skin_xml(tree, xml_path)
            log(f"📝 Updated Minimal dialog {xml_file}: plate + button focus → {texture_filename}")
    except Exception as e:
        log(f"⚠️ Failed to update Minimal skip dialog XML: {e}")


def log_if_changed(key, msg):
    """Only log if the message is different from the last logged message for this key."""
    if key not in monitor._last_log_state or monitor._last_log_state[key] != msg:
        monitor._last_log_state[key] = msg
        log(msg)

CHECK_INTERVAL = 1
ICON_PATH = os.path.join(get_addon().getAddonInfo("path"), "icon.png")

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
        self.item_metadata_ready = False
        self.last_playback_item = None
        self.last_toast_for_file = {}
        self.toast_overlap_shown = False
        self.skipped_to_nested_segment = {}  # Track when we've skipped to nested segments
        self._last_log_state = {}  # Cache for logging state changes only
        self.cleared_parent_dismissals = set()  # Track which parent dismissals have been cleared for nested segments

monitor = PlayerMonitor()
player = xbmc.Player()

def hms_to_seconds(hms):
    h, m, s = hms.strip().split(":")
    return int(h)*3600 + int(m)*60 + float(s)

def safe_file_read(*paths):
    for path in paths:
        if path:
            log(f"📂 Attempting to read: {path}")
            try:
                f = xbmcvfs.File(path)
                content = f.read()
                f.close()
                if isinstance(content, bytes):
                    content = content.decode('utf-8', errors='replace')
                if content:
                    log(f"✅ Successfully read file: {path}")
                    return content
                else:
                    log(f"⚠ File was empty: {path}")
            except Exception as e:
                log(f"❌ Failed to read {path}: {e}")
    return None

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

    log(f"🎯 Kodi playback path: {path}")
    log(f"🔧 show_not_found_toast_for_movies: {get_addon().getSettingBool('show_not_found_toast_for_movies')}")
    log(f"🔧 show_not_found_toast_for_tv_episodes: {get_addon().getSettingBool('show_not_found_toast_for_tv_episodes')}")

    if xbmcvfs.exists(path):
        return path

    log(f"❓ Unrecognized or inaccessible path: {path}")
    return None

def infer_playback_type(item):
    showtitle = item.get("showtitle", "")
    episode = item.get("episode", -1)
    file_path = item.get("file", "")

    log(f"📺 showtitle: {showtitle}, episode: {episode}")
    normalized_path = file_path.lower()

    if showtitle:
        return "episode"
    if isinstance(episode, int) and episode > 0:
        return "episode"
    if re.search(r"s\d{2}e\d{2}", normalized_path):
        log("🧠 Fallback heuristic matched SxxExx pattern — inferring episode")
        return "episode"

    return "movie"

def should_show_missing_file_toast():
    log("🚦 Entered should_show_missing_file_toast()")

    addon = get_addon()
    show_not_found_toast_for_movies = addon.getSettingBool("show_not_found_toast_for_movies")
    show_not_found_toast_for_tv_episodes = addon.getSettingBool("show_not_found_toast_for_tv_episodes")

    query_active = {
        "jsonrpc": "2.0",
        "id": "getPlayers",
        "method": "Player.GetActivePlayers"
    }
    log(f"📨 JSON-RPC request: {json.dumps(query_active)}")
    response_active = xbmc.executeJSONRPC(json.dumps(query_active))
    log(f"📬 JSON-RPC response: {response_active}")
    active_result = json.loads(response_active)
    active_players = active_result.get("result", [])

    if not active_players:
        log("⏳ No active players — retrying after 250ms")
        xbmc.sleep(250)
        retry_response = xbmc.executeJSONRPC(json.dumps(query_active))
        log(f"📬 JSON-RPC retry response: {retry_response}")
        retry_result = json.loads(retry_response)
        active_players = retry_result.get("result", [])

    if not active_players:
        log("🚫 No active video player found — suppressing toast")
        return False, {}

    video_player = next((p for p in active_players if p.get("type") == "video"), None)
    player_id = video_player.get("playerid") if video_player else None

    if player_id is None:
        log("🚫 No video player ID found — suppressing toast")
        return False, {}

    query_item = {
        "jsonrpc": "2.0",
        "id": "VideoGetItem",
        "method": "Player.GetItem",
        "params": {
            "playerid": player_id,
            "properties": ["file", "title", "showtitle", "episode"]
        }
    }
    log(f"📨 JSON-RPC request: {json.dumps(query_item)}")
    response_item = xbmc.executeJSONRPC(json.dumps(query_item))
    item_result = json.loads(response_item)
    item = item_result.get("result", {}).get("item", {})

    if not item:
        log("⚠ Player.GetItem returned empty item — metadata not ready")
        return False, {}
    if not item.get("title") and not item.get("label"):
        log("⚠ Player.GetItem missing title/label — metadata may still be loading (file-based inference will be used)")

    playback_type = infer_playback_type(item)
    log(f"🧠 Inferred playback type: {playback_type}")
    log(f"📁 File: {item.get('file')}, Title: {item.get('title')}, Showtitle: {item.get('showtitle')}, Episode: {item.get('episode')}")

    if playback_type == "movie":
        if not show_not_found_toast_for_movies:
            log("🛑 Suppressing toast — movie playback and disabled in settings")
            return False, item
        log("✅ Toast allowed — movie playback and enabled in settings")
    elif playback_type == "episode":
        if not show_not_found_toast_for_tv_episodes:
            log("🛑 Suppressing toast — episode playback and disabled in settings")
            return False, item
        log("✅ Toast allowed — episode playback and enabled in settings")
    else:
        log(f"⚠ Unknown playback type '{playback_type}' — suppressing toast")
        return False, item

    return True, item

def parse_chapters(video_path):
    base = os.path.splitext(video_path)[0]
    suffixes = ["-chapters.xml", "_chapters.xml"]
    fallback_base = None

    try:
        if player.isPlayingVideo():
            fallback_base = player.getPlayingFile().rsplit('.', 1)[0]
            log(f"🔄 Fallback base path from player: {fallback_base}")
    except RuntimeError:
        log("⚠️ getPlayingFile() failed inside parse_chapters fallback")

    paths_to_try = [f"{base}{s}" for s in suffixes]
    if fallback_base:
        paths_to_try += [f"{fallback_base}{s}" for s in suffixes]

    log(f"🔍 Attempting chapter XML paths: {paths_to_try}")
    xml_data = safe_file_read(*paths_to_try)
    if not xml_data:
        monitor.segment_file_found = False
        log("🚫 No chapter XML file found — segment_file_found set to False")
        return None

    monitor.segment_file_found = True
    log("✅ Chapter XML file found — segment_file_found set to True")

    try:
        root = ET.fromstring(xml_data)
        result = []
        for atom in root.findall(".//ChapterAtom"):
            raw_label = atom.findtext(".//ChapterDisplay/ChapterString", default="")
            label = normalize_label(raw_label)
            start = atom.findtext("ChapterTimeStart")
            end = atom.findtext("ChapterTimeEnd")
            if start and end:
                result.append(SegmentItem(
                    hms_to_seconds(start),
                    hms_to_seconds(end),
                    label,
                    source="xml"
                ))
                log(f"📘 Parsed XML segment: {start} → {end} | label='{label}'")
        if result:
            log(f"✅ Total segments parsed from XML: {len(result)}")
        else:
            log("⚠ Chapter XML parsed but no valid segments found")
        return result if result else None
    except Exception as e:
        log(f"❌ XML parse failed: {e}")
    return None

def parse_edl(video_path):
    base = video_path.rsplit('.', 1)[0]
    fallback_base = None

    try:
        if player.isPlayingVideo():
            fallback_base = player.getPlayingFile().rsplit('.', 1)[0]
            log(f"🔄 Fallback base path from player: {fallback_base}")
    except RuntimeError:
        log("⚠️ getPlayingFile() failed inside parse_edl fallback")

    paths_to_try = [f"{base}.edl"]
    if fallback_base:
        paths_to_try.append(f"{fallback_base}.edl")

    log(f"🔍 Attempting EDL paths: {paths_to_try}")
    edl_data = safe_file_read(*paths_to_try)
    if not edl_data:
        monitor.segment_file_found = False
        log("🚫 No EDL file found — segment_file_found set to False")
        return []

    monitor.segment_file_found = True
    log("✅ EDL file found — segment_file_found set to True")
    log(f"🧾 Raw EDL content:\n{edl_data}")

    segments = []
    mapping = get_edl_type_map()
    ignore_internal = get_addon().getSettingBool("ignore_internal_edl_actions")
    log(f"🔧 ignore_internal_edl_actions setting: {ignore_internal}")

    try:
        for line in edl_data.splitlines():
            parts = line.strip().split()
            if len(parts) == 3:
                s, e, action = float(parts[0]), float(parts[1]), int(parts[2])
                label = mapping.get(action)

                if ignore_internal and label is None:
                    log(f"⚠ Unrecognized EDL action type: {action} — not in mapping")
                    log(f"🚫 Ignoring unmapped EDL action {action} due to setting")
                    continue

                label = label or "segment"
                segments.append(SegmentItem(s, e, label, source="edl"))
                log(f"📗 Parsed EDL line: {s} → {e} | action={action} | label='{label}'")
    except Exception as e:
        log(f"❌ EDL parse failed: {e}")

    log(f"✅ Total segments parsed from EDL: {len(segments)}")
    return segments

def is_nested_segment(segment_a, segment_b):
    """
    Check if segment_b is fully nested inside segment_a.
    Returns True if segment_b is completely contained within segment_a.
    """
    return (segment_b.start_seconds >= segment_a.start_seconds and 
            segment_b.end_seconds <= segment_a.end_seconds)

def is_overlapping_segment(segment_a, segment_b):
    """
    Check if two segments overlap (but not nested).
    Returns True if segments overlap but neither is fully contained in the other.
    """
    # Check if they overlap at all
    if (segment_a.end_seconds <= segment_b.start_seconds or 
        segment_b.end_seconds <= segment_a.start_seconds):
        return False
    
    # If they overlap, check if one is nested in the other
    if is_nested_segment(segment_a, segment_b) or is_nested_segment(segment_b, segment_a):
        return False
    
    return True

def should_suppress_segment_dialog(current_segment, all_segments, current_time, recently_dismissed=None):
    """
    Check if the current segment dialog should be suppressed because we're inside
    a nested or overlapping segment that should take priority.
    
    Returns True if the dialog should be suppressed.
    
    Args:
        recently_dismissed: Set of dismissed segment IDs. If a parent segment is dismissed,
                          nested segments should still be allowed to show.
    """
    # Find all segments that are currently active (contain current_time)
    active_segments = [seg for seg in all_segments if seg.is_active(current_time)]
    
    if len(active_segments) <= 1:
        return False  # No conflicts
    
    # Sort active segments by start time to process in order
    active_segments.sort(key=lambda s: s.start_seconds)
    
    # Find the current segment in the active list
    try:
        current_index = active_segments.index(current_segment)
    except ValueError:
        return False  # Current segment not in active list
    
    # Use same seg_id format as main loop (round then int) for consistent matching
    current_seg_id = (int(round(current_segment.start_seconds)), int(round(current_segment.end_seconds)))
    
    # FIRST: Check if current segment is nested within a dismissed parent
    # If so, allow it to show (don't suppress)
    if recently_dismissed:
        for i in range(current_index):
            parent_segment = active_segments[i]
            # Use same seg_id format as main loop (round then int) for consistent matching
            parent_seg_id = (int(round(parent_segment.start_seconds)), int(round(parent_segment.end_seconds)))
            # If current segment is nested within a dismissed parent, allow it to show
            if parent_seg_id in recently_dismissed and is_nested_segment(parent_segment, current_segment):
                log(f"✅ Allowing nested segment '{current_segment.segment_type_label}' to show even though parent '{parent_segment.segment_type_label}' was dismissed")
                return False
    
    # SECOND: Check if there are any segments that start after the current segment
    # and are nested within it - these should take priority
    for i in range(current_index + 1, len(active_segments)):
        later_segment = active_segments[i]
        
        # If the later segment is nested within the current segment, suppress current
        # BUT: if the parent (current) segment was dismissed, allow nested segments to show
        if is_nested_segment(current_segment, later_segment):
            if recently_dismissed:
                # If parent was dismissed, don't suppress - let nested segment show
                if current_seg_id in recently_dismissed:
                    log(f"✅ Allowing nested segment '{later_segment.segment_type_label}' to show even though parent '{current_segment.segment_type_label}' was dismissed")
                    return False
            log(f"🚫 Suppressing dialog for '{current_segment.segment_type_label}' because '{later_segment.segment_type_label}' is nested within it")
            return True
        
        # If the later segment overlaps with current segment, suppress current
        if is_overlapping_segment(current_segment, later_segment):
            log(f"🚫 Suppressing dialog for '{current_segment.segment_type_label}' because '{later_segment.segment_type_label}' overlaps with it")
            return True
    
    return False

def re_evaluate_segment_jump_points(segments, current_time):
    """
    Re-evaluate jump points for segments based on current playback position.
    This is needed after major rewinds to ensure correct jump targets.
    """
    log(f"🔄 Re-evaluating jump points for {len(segments)} segments at time {current_time:.2f}")
    
    for i in range(len(segments)):
        current_seg = segments[i]
        
        # Find the next segment that starts within or after this segment
        next_jump_target = None
        next_segment_info = None
        
        for j in range(i + 1, len(segments)):
            next_seg = segments[j]
            
            # Check if next segment starts within current segment (overlap or nested)
            if next_seg.start_seconds < current_seg.end_seconds:
                # Determine relationship type
                if is_nested_segment(current_seg, next_seg):
                    # For nested segments, only set jump to nested segment if we're still before the nested segment
                    if current_time < next_seg.start_seconds:
                        log(f"🔍 Re-evaluating: '{next_seg.segment_type_label}' is nested in '{current_seg.segment_type_label}', current time {current_time:.2f} is before nested segment ({next_seg.start_seconds}-{next_seg.end_seconds})")
                        next_jump_target = next_seg.start_seconds
                        next_segment_info = f"nested segment '{next_seg.segment_type_label}'"
                        break
                    else:
                        # We're at or past the nested segment, skip to end of parent
                        log(f"🔍 Re-evaluating: '{next_seg.segment_type_label}' is nested in '{current_seg.segment_type_label}', but current time {current_time:.2f} is at or past nested segment ({next_seg.start_seconds}-{next_seg.end_seconds}), will skip to parent end")
                        next_jump_target = None  # Will default to end of current segment
                        next_segment_info = None
                        break
                        
                elif is_overlapping_segment(current_seg, next_seg):
                    log(f"🔍 Re-evaluating: '{next_seg.segment_type_label}' overlaps with '{current_seg.segment_type_label}'")
                    next_jump_target = next_seg.start_seconds
                    next_segment_info = f"overlapping segment '{next_seg.segment_type_label}'"
                    break
            else:
                # No more segments within current segment, break
                break
        
        # Update the segment's jump point
        current_seg.next_segment_start = next_jump_target
        current_seg.next_segment_info = next_segment_info
        
        if next_jump_target is not None:
            log(f"🔗 Re-evaluated jump point for '{current_seg.segment_type_label}' to {next_jump_target}s ({next_segment_info})")
        else:
            log(f"🔗 Re-evaluated jump point for '{current_seg.segment_type_label}' to end of segment ({current_seg.end_seconds}s)")
    
    # Additional pass: Ensure nested segments have correct jump points when we're rewinding into them
    log(f"🔍 Additional pass: Checking nested segments for correct jump points at time {current_time:.2f}")
    for i in range(len(segments)):
        current_seg = segments[i]
        
        # Check if current_time is within this segment
        if current_seg.start_seconds <= current_time <= current_seg.end_seconds:
            # Find if this segment is nested within any parent segment
            for j in range(i):
                parent_seg = segments[j]
                if is_nested_segment(parent_seg, current_seg):
                    # This is a nested segment, ensure it has the correct jump point
                    if current_seg.next_segment_start != current_seg.end_seconds:
                        log(f"🔧 Fixing nested segment '{current_seg.segment_type_label}': setting jump point to {current_seg.end_seconds}s (end of segment)")
                        current_seg.next_segment_start = current_seg.end_seconds
                        current_seg.next_segment_info = f"remaining {parent_seg.segment_type_label}"
                    break

def parse_and_process_segments(path, current_time=None):
    """
    Parses segments, filters them based on settings, and then links overlapping/nested segments.
    If current_time is provided, the linking logic will be context-aware.
    """
    # CRITICAL: Defensive check - never process segments when paused
    # This prevents toast spamming even if this function is called while paused
    # Always check pause state first, before doing ANY processing
    try:
        is_playing_parse = player.isPlayingVideo()
        is_paused_parse = xbmc.getCondVisibility("Player.Paused")
        if is_paused_parse or not is_playing_parse:
            # Always log this (not using log_if_changed) to help debug toast spamming
            log(f"🔕 parse_and_process_segments called while paused — returning empty list to prevent toast spamming (is_playing={is_playing_parse}, is_paused={is_paused_parse})")
            return []
    except RuntimeError:
        # Always log this (not using log_if_changed) to help debug toast spamming
        log("🔕 parse_and_process_segments called but player state unavailable — returning empty list")
        return []
    
    log(f"🚦 Starting new segment parse and process for: {path}")
    parsed = parse_chapters(path)
    if not parsed:
        parsed = parse_edl(path)
    
    if not parsed:
        log("🚫 No segment file found or parsed segments were empty.")
        return []

    # --- Pass 1: Filter segments based on user settings ---
    log("⚙️ Pass 1: Filtering segments...")
    addon = get_addon()
    skip_overlaps = addon.getSettingBool("skip_overlapping_segments")
    
    # Sort parsed segments to process them in order
    segments = sorted(parsed, key=lambda s: s.start_seconds)
    
    filtered_segments = []
    
    for current_seg in segments:
        is_overlapping_with_filtered = False
        # Check if the current segment overlaps with any already-filtered segment
        for existing_seg in filtered_segments:
            if not (current_seg.end_seconds <= existing_seg.start_seconds or current_seg.start_seconds >= existing_seg.end_seconds):
                is_overlapping_with_filtered = True
                break
        
        if is_overlapping_with_filtered and skip_overlaps:
            log(f"🚫 Skipping segment {current_seg.start_seconds}-{current_seg.end_seconds} due to user setting 'skip_overlapping_segments' which detected an overlap.")
            continue
        
        filtered_segments.append(current_seg)
    
    log(f"✅ Pass 1 complete. Filtered segments: {len(filtered_segments)}")

    # --- Pass 2: Enhanced linking for overlapping/nested segments ---
    log("🔗 Pass 2: Linking segments for progressive skipping and detecting overlaps/nested...")
    has_overlap_or_nested = False
    
    # Process segments to identify relationships and set jump points
    for i in range(len(filtered_segments)):
        current_seg = filtered_segments[i]
        
        # Find the next segment that starts within or after this segment
        next_jump_target = None
        next_segment_info = None
        
        for j in range(i + 1, len(filtered_segments)):
            next_seg = filtered_segments[j]
            
            # Check if next segment starts within current segment (overlap or nested)
            if next_seg.start_seconds < current_seg.end_seconds:
                has_overlap_or_nested = True
                
                # Determine relationship type
                if is_nested_segment(current_seg, next_seg):
                    log(f"🔍 Detected NESTED segment: '{next_seg.segment_type_label}' ({next_seg.start_seconds}-{next_seg.end_seconds}) is nested inside '{current_seg.segment_type_label}' ({current_seg.start_seconds}-{current_seg.end_seconds})")
                    
                    # Context-aware linking: only set jump to nested segment if we're before it
                    if current_time is None or current_time < next_seg.start_seconds:
                        # For nested segments, jump to the start of the nested segment
                        next_jump_target = next_seg.start_seconds
                        next_segment_info = f"nested segment '{next_seg.segment_type_label}'"
                        log(f"🔗 Setting jump point for '{current_seg.segment_type_label}' to {next_jump_target}s ({next_segment_info})")
                    else:
                        # We're at or past the nested segment, skip to end of parent
                        log(f"🔗 Context-aware: current time {current_time:.2f} is at or past nested segment, will skip to end of parent")
                        next_jump_target = None  # Will default to end of current segment
                        next_segment_info = None
                    
                    # Also set the nested segment to jump to the end of its own segment (not parent)
                    next_seg.next_segment_start = next_seg.end_seconds
                    next_seg.next_segment_info = f"remaining {current_seg.segment_type_label}"
                    log(f"🔗 Setting jump point for nested '{next_seg.segment_type_label}' to {next_seg.end_seconds}s (remaining {current_seg.segment_type_label})")
                    
                elif is_overlapping_segment(current_seg, next_seg):
                    log(f"🔍 Detected OVERLAPPING segment: '{next_seg.segment_type_label}' ({next_seg.start_seconds}-{next_seg.end_seconds}) overlaps with '{current_seg.segment_type_label}' ({current_seg.start_seconds}-{current_seg.end_seconds})")
                    # For overlapping segments, jump to the start of the overlapping segment
                    next_jump_target = next_seg.start_seconds
                    next_segment_info = f"overlapping segment '{next_seg.segment_type_label}'"
                
                # Set the jump point and break (use the first overlapping/nested segment found)
                if next_jump_target is not None:
                    current_seg.next_segment_start = next_jump_target
                    current_seg.next_segment_info = next_segment_info
                    log(f"🔗 Setting jump point for '{current_seg.segment_type_label}' to {next_jump_target}s ({next_segment_info})")
                    break
            else:
                # No more segments within current segment, break
                break
    
    # Show toast notification if overlaps were found and setting is enabled
    # Don't show toast if any segment has been dismissed by the user, or if playback is paused
    # CRITICAL: Check toast_overlap_shown FIRST to prevent re-evaluation
    if monitor.toast_overlap_shown:
        log_if_changed("toast_already_shown", "🔕 Overlapping segments toast already shown — skipping")
        return filtered_segments
    
    should_show_toast = has_overlap_or_nested and show_overlapping_toast()
    if not should_show_toast:
        return filtered_segments
    
    # CRITICAL: Check if playback is paused FIRST (before any other checks)
    # This is the most important check to prevent toast spamming when paused
    # Double-check pause state right before showing toast (defensive programming)
    try:
        is_playing_toast = player.isPlayingVideo()
        is_paused_toast = xbmc.getCondVisibility("Player.Paused")
        if is_paused_toast or not is_playing_toast:
            # Always log this (not using log_if_changed) to help debug toast spamming
            log(f"🔕 Suppressing overlapping segments toast because playback is paused or not playing (is_playing={is_playing_toast}, is_paused={is_paused_toast})")
            return filtered_segments
    except RuntimeError:
        # Always log this (not using log_if_changed) to help debug toast spamming
        log("🔕 Suppressing overlapping segments toast because player state unavailable")
        return filtered_segments
    
    # If any segment has been dismissed, don't show the overlapping toast
    if monitor.recently_dismissed:
        log_if_changed("toast_dismissed", "🔕 Suppressing overlapping segments toast because user has dismissed a segment dialog")
        return filtered_segments
    
    # All checks passed - show the toast
    # CRITICAL: One final pause check right before showing (triple-check for safety)
    try:
        final_is_playing = player.isPlayingVideo()
        final_is_paused = xbmc.getCondVisibility("Player.Paused")
        if final_is_paused or not final_is_playing:
            log(f"🔕 Final pause check: Suppressing overlapping segments toast because playback is paused or not playing (is_playing={final_is_playing}, is_paused={final_is_paused})")
            return filtered_segments
    except RuntimeError:
        log("🔕 Final pause check: Suppressing overlapping segments toast because player state unavailable")
        return filtered_segments
    
    log("🔔 Attempting to show toast notification for overlapping segments")
    try:
        xbmcgui.Dialog().notification(
            heading="Skippy",
            message="Overlapping/Nested segments detected.",
            icon=ICON_PATH,
            time=4000
        )
        monitor.toast_overlap_shown = True
        log("✅ Toast notification displayed for overlapping segments")
    except Exception as e:
        log(f"❌ Failed to display overlapping segments toast notification (possible Kodi/device limitation): {e}")
        # Don't set toast_overlap_shown = True if the toast failed to display
        # This allows retry on next parse (though parse_and_process_segments shouldn't be called when paused)
        
    log(f"✅ Pass 2 complete. Final segments to process: {len(filtered_segments)}")
    return filtered_segments

log_always("📡 XML-EDL Intro Skipper service started.")

while not monitor.abortRequested():
    if player.isPlayingVideo() or xbmc.getCondVisibility("Player.HasVideo"):
        video = get_video_file()
        if not video:
            log_if_changed("no_video", "⚠ get_video_file() returned None — skipping this cycle")
            # CRITICAL: Don't set last_video to None here - this causes video change detection to trigger incorrectly
            # when video becomes available again (e.g., after pause/resume)
            # Only clear last_video if we're sure playback has actually stopped
            continue

        if video:
            # 🔁 Detect replay of same video
            # CRITICAL: Only check if NOT paused - don't reset state when paused
            # CRITICAL: Do NOT clear recently_dismissed on replay if we have dismissed segments
            # This prevents clearing on resume from pause (which can look like a replay)
            try:
                is_playing_replay = player.isPlayingVideo()
                is_paused_replay = xbmc.getCondVisibility("Player.Paused")
                if not is_paused_replay and is_playing_replay:
                    current_playback_time = player.getTime()
                    if (
                        video == monitor.last_video
                        and monitor.playback_ready
                        and current_playback_time < 5.0
                        and time.time() - monitor.playback_ready_time > 5.0
                    ):
                        # CRITICAL: Double-check pause state right before clearing
                        # CRITICAL: Use last_time to distinguish genuine replay from resume
                        # On genuine replay: playback jumps from higher position to < 5.0 seconds
                        # On resume: playback continues from where it was paused (won't jump to < 5.0)
                        try:
                            final_replay_playing = player.isPlayingVideo()
                            final_replay_paused = xbmc.getCondVisibility("Player.Paused")
                            if final_replay_paused or not final_replay_playing:
                                log(f"🔕 CRITICAL: Replay detected but paused - NOT clearing recently_dismissed (is_playing={final_replay_playing}, is_paused={final_replay_paused})")
                            else:
                                # Check if this is a genuine replay by comparing current position to last known position
                                # If last_time was much higher (> 10s), this is likely a replay, not a resume
                                is_genuine_replay = monitor.last_time > 10.0
                                
                                if not is_genuine_replay:
                                    # last_time is low - might be a resume from early in video
                                    # Also check if we're currently in any active segments
                                    is_in_active_segment = False
                                    if monitor.current_segments:
                                        for seg in monitor.current_segments:
                                            if seg.is_active(current_playback_time):
                                                is_in_active_segment = True
                                                break
                                    
                                    if is_in_active_segment:
                                        log(f"🔒 Replay detected but we're in an active segment at {current_playback_time:.2f}s - NOT clearing (likely resume, not replay)")
                                    else:
                                        # Not in active segment and last_time is low - still might be a replay from very early
                                        # But to be safe, only clear if we're very close to start (< 2.0s) and last_time was at least 5s
                                        if current_playback_time < 2.0 and monitor.last_time >= 5.0:
                                            is_genuine_replay = True
                                            log(f"🔍 Replay detected: current={current_playback_time:.2f}s, last={monitor.last_time:.2f}s - treating as genuine replay")
                                        else:
                                            log(f"🔒 Replay detected but last_time={monitor.last_time:.2f}s is low - NOT clearing (likely resume from early position)")
                                
                                if is_genuine_replay:
                                    # This is a genuine replay - clear dismissed state so dialogs can reappear
                                    log("🔁 Replay of same video detected — resetting monitor state")
                                    log(f"🔍 Debug: About to clear recently_dismissed (currently has {len(monitor.recently_dismissed)} items: {list(monitor.recently_dismissed)})")
                                    log(f"🔍 Debug: Replay detected: current={current_playback_time:.2f}s, last={monitor.last_time:.2f}s")
                                    monitor.shown_missing_file_toast = False
                                    monitor.prompted.clear()
                                    monitor.recently_dismissed.clear()
                                    log(f"🔍 Debug: recently_dismissed cleared - now has {len(monitor.recently_dismissed)} items")
                                    monitor.cleared_parent_dismissals.clear()
                                    monitor.playback_ready = False
                                    monitor.play_start_time = time.time()
                                    monitor.last_time = 0
                                    monitor.last_toast_time = 0
                                    # CRITICAL: Do NOT reset toast_overlap_shown on replay - it should only show once per video
                                    # Only reset on new video (see line 766)
                                    monitor.skipped_to_nested_segment.clear()
                                    # Clear log cache on replay to allow re-logging
                                    monitor._last_log_state.clear()
                                    log(f"✅ Replay state cleared - recently_dismissed now has {len(monitor.recently_dismissed)} items")
                        except RuntimeError:
                            log(f"🔕 CRITICAL: Cannot verify pause state during replay - NOT clearing recently_dismissed to prevent clearing on pause")
            except RuntimeError:
                # Playback may have stopped, skip replay detection
                pass

            # Only log when video changes
            # CRITICAL: Video path change = new video, so clear recently_dismissed
            # The video path does NOT change on pause/resume, only when a different video is playing
            if video != monitor.last_video:
                try:
                    is_playing_new = player.isPlayingVideo()
                    is_paused_new = xbmc.getCondVisibility("Player.Paused")
                    
                    if not is_paused_new and is_playing_new:
                        # CRITICAL: Double-check pause state right before clearing
                        try:
                            final_new_playing = player.isPlayingVideo()
                            final_new_paused = xbmc.getCondVisibility("Player.Paused")
                            if final_new_paused or not final_new_playing:
                                log(f"🔕 CRITICAL: Video path changed but paused - NOT clearing recently_dismissed (is_playing={final_new_playing}, is_paused={final_new_paused})")
                                monitor.last_video = video  # Still update last_video
                            else:
                                # Video path changed and we're playing - this is a new video
                                log(f"🚀 New video detected: {os.path.basename(video)}")
                                log("🆕 New video detected — resetting monitor state")
                                log(f"🔍 Debug: About to clear recently_dismissed (currently has {len(monitor.recently_dismissed)} items: {list(monitor.recently_dismissed)})")
                                monitor.last_video = video
                                monitor.segment_file_found = False
                                monitor.shown_missing_file_toast = False
                                monitor.prompted.clear()
                                monitor.recently_dismissed.clear()
                                log(f"🔍 Debug: recently_dismissed cleared - now has {len(monitor.recently_dismissed)} items")
                                monitor.cleared_parent_dismissals.clear()
                                monitor.playback_ready = False
                                monitor.play_start_time = time.time()
                                monitor.last_time = 0
                                monitor.last_toast_time = 0
                                monitor.toast_overlap_shown = False
                                monitor.skipped_to_nested_segment.clear()
                                # Clear log cache on new video to allow re-logging
                                monitor._last_log_state.clear()
                                log(f"✅ New video state cleared - recently_dismissed now has {len(monitor.recently_dismissed)} items")
                        except RuntimeError:
                            log(f"🔕 CRITICAL: Cannot verify pause state during new video detection - NOT clearing recently_dismissed to prevent clearing on pause/resume")
                            monitor.last_video = video  # Still update last_video
                    else:
                        # Video changed but paused - just update last_video, don't clear state
                        log(f"🚀 Video path changed but paused - updating last_video only (not clearing state)")
                        monitor.last_video = video
                except RuntimeError:
                    # If we can't check pause state, be safe and don't clear
                    log(f"🚀 Video path changed but can't verify pause state - updating last_video only (not clearing state)")
                    monitor.last_video = video
            
            addon = get_addon()
            try:
                allow_toast, item = should_show_missing_file_toast()
                playback_type = infer_playback_type(item) if item else ""
                log_if_changed("playback_type", f"🔍 Playback type: '{playback_type}'")
            except Exception as e:
                log(f"❌ JSON-RPC / toast path failed ({type(e).__name__}): {e}")
                item = None
                playback_type = ""
            if not playback_type and video:
                synthetic = {
                    "file": video,
                    "title": os.path.basename(video),
                    "showtitle": "",
                    "episode": -1,
                }
                playback_type = infer_playback_type(synthetic)
                log_if_changed(
                    "playback_type_fallback",
                    f"🔍 Playback type (fallback from path): '{playback_type}'",
                )

            show_dialogs = is_skip_dialog_enabled(playback_type)
            toast_movies = addon.getSettingBool("show_not_found_toast_for_movies")
            toast_episodes = addon.getSettingBool("show_not_found_toast_for_tv_episodes")

            log_if_changed("settings", f"🧪 Settings → show_dialogs: {show_dialogs}, toast_movies: {toast_movies}, toast_episodes: {toast_episodes}")

        try:
            current_time = player.getTime()
            # Only log time changes, not every second
            log_if_changed("playback_time", f"⏱️ Playback time: {current_time:.2f}s")
        except RuntimeError:
            log("⚠ player.getTime() failed — no media playing")
            continue

        # Check if playback is paused - do this FIRST, before any segment processing
        # Initialize to safe defaults (assume paused to be safe)
        is_playing = False
        is_paused = True
        try:
            is_playing = player.isPlayingVideo()
            is_paused = xbmc.getCondVisibility("Player.Paused")
        except RuntimeError:
            is_playing = False
            is_paused = True
        
        # Log pause state changes for debugging (use log_if_changed to reduce clutter)
        log_if_changed("pause_state", f"⏸️ Playback state: is_playing={is_playing}, is_paused={is_paused}")
        
        # CRITICAL: If video is paused or not playing, skip ALL segment processing
        # This prevents ANY dialogs from appearing when paused, regardless of dismissal status
        # This also prevents parse_and_process_segments from being called when paused, which prevents toast spamming
        if is_paused or not is_playing:
            # Log pause state (use log_if_changed to reduce clutter, but log when state changes)
            log_if_changed("paused_all", f"⏸️ Video paused or not playing — skipping ALL segment processing (is_playing={is_playing}, is_paused={is_paused})")
            # CRITICAL: Don't update last_time when paused - this could cause issues with rewind detection
            # Only update last_time if we were previously playing (to track position)
            if monitor.last_time == 0:
                monitor.last_time = current_time
            continue

        # Only parse segments when NOT paused
        if not playback_type:
            log("⚠ Playback type not detected — skipping segment parsing")
            monitor.current_segments = []
        else:
            # CRITICAL: Only call parse_and_process_segments when NOT paused
            # This prevents toast spamming when paused
            monitor.current_segments = parse_and_process_segments(video, current_time) or []
            log(f"📦 Parsed {len(monitor.current_segments)} segments for playback_type: {playback_type}")

        if not show_dialogs:
            log(f"🚫 Skip dialogs disabled for {playback_type} — segments will not trigger prompts")

        rewind_threshold = get_addon().getSettingInt("rewind_threshold_seconds")
        major_rewind_detected = False
        
        # Check for rewind BEFORE updating last_time
        if monitor.last_time > 0:  # Only check if we have a previous time
            rewind_detected = current_time < monitor.last_time and monitor.last_time - current_time > rewind_threshold
            if rewind_detected:
                log(f"🔍 Rewind check: current={current_time:.2f}, last={monitor.last_time:.2f}, threshold={rewind_threshold}, difference={monitor.last_time - current_time:.2f}")
        else:
            rewind_detected = False
        
        if rewind_detected:
            # CRITICAL: Only clear state if NOT paused - don't clear dismissals when paused
            # The pause check above should prevent this, but add defensive check here too
            try:
                is_playing_rewind = player.isPlayingVideo()
                is_paused_rewind = xbmc.getCondVisibility("Player.Paused")
                if not is_paused_rewind and is_playing_rewind:
                    # CRITICAL: Double-check pause state right before clearing
                    try:
                        final_rewind_playing = player.isPlayingVideo()
                        final_rewind_paused = xbmc.getCondVisibility("Player.Paused")
                        if final_rewind_paused or not final_rewind_playing:
                            log(f"🔕 CRITICAL: Rewind detected but paused - NOT clearing recently_dismissed (is_playing={final_rewind_playing}, is_paused={final_rewind_paused})")
                        else:
                            log(f"⏪ Significant rewind detected ({monitor.last_time:.2f} → {current_time:.2f}) — threshold: {rewind_threshold}s")
                            log(f"🔍 Debug: About to clear recently_dismissed (currently has {len(monitor.recently_dismissed)} items: {list(monitor.recently_dismissed)})")
                            monitor.prompted.clear()
                            monitor.recently_dismissed.clear()
                            log(f"🔍 Debug: recently_dismissed cleared - now has {len(monitor.recently_dismissed)} items")
                            monitor.cleared_parent_dismissals.clear()
                            monitor.skipped_to_nested_segment.clear()
                            
                            # Re-evaluate segment jump points after major rewind to ensure correct jump targets
                            if monitor.current_segments:
                                re_evaluate_segment_jump_points(monitor.current_segments, current_time)
                            
                            major_rewind_detected = True
                            log("🧹 recently_dismissed cleared due to rewind, nested segment tracking cleared, jump points re-evaluated")
                            log(f"✅ Rewind state cleared - recently_dismissed now has {len(monitor.recently_dismissed)} items")
                    except RuntimeError:
                        log(f"🔕 CRITICAL: Cannot verify pause state during rewind - NOT clearing recently_dismissed to prevent clearing on pause")
                else:
                    log(f"⏪ Rewind detected but paused - NOT clearing recently_dismissed")
            except RuntimeError:
                log(f"⏪ Rewind detected but can't verify pause state - NOT clearing recently_dismissed")
        
        # CRITICAL: Check if we're inside a nested segment and clear its parent from recently_dismissed
        # Only clear when we're actually INSIDE the nested segment (current_time is past nested segment start)
        # This allows parent dialog to reappear after nested segment ends
        # CRITICAL: This check happens AFTER the pause check, so it only runs when NOT paused
        # NOTE: This handles natural entry into nested segments (not explicit skips)
        # Explicit skips handle clearing in the skip blocks above
        if monitor.current_segments and monitor.recently_dismissed:
            # Only proceed if we have segments and dismissed items
            log_if_changed("nested_clear_check", f"🔍 Checking nested segment clearing: {len(monitor.current_segments)} segments, {len(monitor.recently_dismissed)} dismissed, current_time={current_time:.2f}")
            
            # CRITICAL: First, identify which segments are actually nested (have a parent)
            # We only want to process segments that are nested inside other segments
            for nested_seg in monitor.current_segments:
                nested_seg_id = (int(round(nested_seg.start_seconds)), int(round(nested_seg.end_seconds)))
                is_inside_nested = (current_time >= nested_seg.start_seconds and current_time <= nested_seg.end_seconds)
                
                # CRITICAL: Only process if we're inside this segment AND it's actually nested (has a parent)
                # Check if this segment has a parent by looking for segments that contain it
                has_parent = False
                parent_seg_for_nested = None
                for potential_parent in monitor.current_segments:
                    if potential_parent != nested_seg and is_nested_segment(potential_parent, nested_seg):
                        has_parent = True
                        parent_seg_for_nested = potential_parent
                        break
                
                if not has_parent:
                    # This segment is not nested, skip it
                    continue
                
                log_if_changed(f"nested_check_{nested_seg_id}", f"🔍 Nested segment {nested_seg_id} ({nested_seg.segment_type_label}): start={nested_seg.start_seconds:.2f}, end={nested_seg.end_seconds:.2f}, current={current_time:.2f}, is_inside={is_inside_nested}, has_parent={has_parent}")
                
                if is_inside_nested:
                    # CRITICAL: When entering a nested segment naturally, ONLY clear the parent segment from recently_dismissed
                    # Do NOT clear the nested segment itself - if it was dismissed, it should stay dismissed until we exit it
                    # The nested segment will be cleared from recently_dismissed when we EXIT it (see exit logic below)
                    
                    # CRITICAL: Check if the parent segment was dismissed and clear it
                    if parent_seg_for_nested:
                        parent_seg_id_check = (int(round(parent_seg_for_nested.start_seconds)), int(round(parent_seg_for_nested.end_seconds)))
                        is_parent_dismissed = parent_seg_id_check in monitor.recently_dismissed
                        
                        log(f"🔍 Inside nested segment {nested_seg_id} ({nested_seg.segment_type_label}) - checking parent {parent_seg_id_check} ({parent_seg_for_nested.segment_type_label}): dismissed={is_parent_dismissed}")
                        log(f"🔍 Debug: recently_dismissed contains: {list(monitor.recently_dismissed)}")
                        
                        if is_parent_dismissed:
                            # Use a key to track that we've cleared this parent for this nested segment
                            clearance_key = (parent_seg_id_check, nested_seg_id)
                            if clearance_key not in monitor.cleared_parent_dismissals:
                                # First time clearing for this parent-nested pair - we're inside the nested segment
                                log(f"🔓 About to clear parent segment {parent_seg_id_check} from recently_dismissed (currently has {len(monitor.recently_dismissed)} items: {list(monitor.recently_dismissed)})")
                                if parent_seg_id_check in monitor.recently_dismissed:
                                    monitor.recently_dismissed.remove(parent_seg_id_check)
                                    monitor.cleared_parent_dismissals.add(clearance_key)
                                    log(f"🔓 SUCCESS: Cleared parent segment {parent_seg_id_check} ({parent_seg_for_nested.segment_type_label}) from recently_dismissed because we're inside nested segment {nested_seg.segment_type_label} (current_time={current_time:.2f})")
                                    log(f"🔍 Debug: recently_dismissed now has {len(monitor.recently_dismissed)} items: {list(monitor.recently_dismissed)}")
                                    # CRITICAL: Also remove parent from prompted so its dialog can show again after nested segment ends
                                    if parent_seg_id_check in monitor.prompted:
                                        monitor.prompted.remove(parent_seg_id_check)
                                        log(f"🔓 Also removed parent segment {parent_seg_id_check} from prompted set so dialog can show again after nested segment ends")
                                        log(f"🔍 Debug: prompted now has {len(monitor.prompted)} items: {list(monitor.prompted)}")
                                else:
                                    log(f"⚠️ WARNING: Parent {parent_seg_id_check} was supposed to be in recently_dismissed but wasn't found!")
                            else:
                                log(f"🔍 Already cleared parent {parent_seg_id_check} for nested {nested_seg_id} - skipping (clearance_key already exists)")
                        else:
                            log(f"🔍 Parent {parent_seg_id_check} is not dismissed, no need to clear")
        
        # CRITICAL: Check if we've exited any nested segments (both skipped-to and naturally entered)
        # and remove them from recently_dismissed if they were dismissed
        # This must happen BEFORE processing segments so that parent dialogs can show immediately
        if monitor.current_segments:
            for nested_seg in monitor.current_segments:
                nested_seg_id_exit = (int(round(nested_seg.start_seconds)), int(round(nested_seg.end_seconds)))
                # Check if we're no longer inside this nested segment
                if current_time > nested_seg.end_seconds:
                    # We've exited this nested segment - clear it from recently_dismissed so it can show again if re-entered
                    if nested_seg_id_exit in monitor.recently_dismissed:
                        monitor.recently_dismissed.remove(nested_seg_id_exit)
                        log(f"🔓 Removed nested segment {nested_seg_id_exit} ({nested_seg.segment_type_label}) from recently_dismissed after exiting nested segment")
                        log(f"🔍 Debug: recently_dismissed now has {len(monitor.recently_dismissed)} items: {list(monitor.recently_dismissed)}")
        
        # Check if we've exited any nested segments we skipped to and need to re-enable parent segment dialogs
        if monitor.skipped_to_nested_segment:
            log_if_changed("checking_nested", f"🔍 Checking {len(monitor.skipped_to_nested_segment)} tracked nested segments at time {current_time:.2f}")
        
        segments_to_remove = []
        for parent_seg_id, nested_segment in monitor.skipped_to_nested_segment.items():
            # Check if we're no longer in the nested segment
            is_nested_active = nested_segment.is_active(current_time)
            log_if_changed(f"nested_check_{parent_seg_id}", f"🔍 Nested segment '{nested_segment.segment_type_label}' ({nested_segment.start_seconds}-{nested_segment.end_seconds}) active at {current_time:.2f}: {is_nested_active}")
            
            if not is_nested_active:
                # We've exited the nested segment, remove from tracking
                segments_to_remove.append(parent_seg_id)
                
                # CRITICAL: Remove nested segment from recently_dismissed if it was dismissed
                # The nested segment dismissal should only last until we exit the nested segment
                nested_seg_id = (int(round(nested_segment.start_seconds)), int(round(nested_segment.end_seconds)))
                if nested_seg_id in monitor.recently_dismissed:
                    monitor.recently_dismissed.remove(nested_seg_id)
                    log(f"🔓 Removed nested segment {nested_seg_id} ({nested_segment.segment_type_label}) from recently_dismissed after exiting nested segment")
                    log(f"🔍 Debug: recently_dismissed now has {len(monitor.recently_dismissed)} items: {list(monitor.recently_dismissed)}")
                
                # Re-enable the parent segment dialog by removing it from prompted set
                # BUT: Only if the parent was NOT dismissed by the user
                if parent_seg_id not in monitor.recently_dismissed:
                    if parent_seg_id in monitor.prompted:
                        monitor.prompted.remove(parent_seg_id)
                        log(f"🔄 Exited nested segment '{nested_segment.segment_type_label}', re-enabled parent segment {parent_seg_id} dialog (removed from prompted)")
                        # CRITICAL: Re-evaluate jump points for the parent segment to ensure it can show its dialog
                        # Find the parent segment in current_segments and update its jump point
                        for seg in monitor.current_segments:
                            # Use same seg_id format as main loop (round then int) for consistent matching
                            seg_id_check = (int(round(seg.start_seconds)), int(round(seg.end_seconds)))
                            if seg_id_check == parent_seg_id:
                                # Re-evaluate jump point for this parent segment
                                seg.next_segment_start = None
                                seg.next_segment_info = None
                                log(f"🔄 Reset jump point for parent segment {parent_seg_id} to allow dialog to show")
                                break
                    else:
                        log(f"🔄 Exited nested segment '{nested_segment.segment_type_label}', parent segment {parent_seg_id} was not in prompted set (will show if active)")
                else:
                    log(f"🔄 Exited nested segment '{nested_segment.segment_type_label}', but parent segment {parent_seg_id} was dismissed — NOT re-enabling")
                
                # Re-evaluate segment jump points since we've exited a nested segment
                if monitor.current_segments:
                    log(f"🔄 Re-evaluating jump points after exiting nested segment '{nested_segment.segment_type_label}'")
                    re_evaluate_segment_jump_points(monitor.current_segments, current_time)
        
        # Remove exited nested segments from tracking
        for seg_id in segments_to_remove:
            del monitor.skipped_to_nested_segment[seg_id]
            log(f"🗑️ Removed parent segment {seg_id} from skipped_to_nested_segment tracking")

        if not monitor.playback_ready and current_time > 0:
            monitor.playback_ready = True
            monitor.playback_ready_time = time.time()
            log("✅ Playback confirmed via getTime() — setting playback_ready = True")

        if (
            monitor.playback_ready
            and not monitor.shown_missing_file_toast
            and time.time() - monitor.playback_ready_time >= 2
            and not monitor.segment_file_found
        ):
            # CRITICAL: Check if playback is paused BEFORE showing toast to prevent spamming when paused
            try:
                toast_is_playing = player.isPlayingVideo()
                toast_is_paused = xbmc.getCondVisibility("Player.Paused")
                if toast_is_paused or not toast_is_playing:
                    log(f"🔕 Missing segments toast suppressed — playback is paused or not playing (is_playing={toast_is_playing}, is_paused={toast_is_paused})")
                    # Don't set shown_missing_file_toast = True here - allow retry when resumed
                    # This prevents the toast from being suppressed permanently when paused
                else:
                    log("⚠ [TOAST BLOCK] Entered toast logic block")
                    try:
                        toast_enabled = (
                            (playback_type == "movie" and toast_movies) or
                            (playback_type == "episode" and toast_episodes)
                        )

                        if toast_enabled:
                            cooldown = 6
                            now = time.time()
                            if now - monitor.last_toast_time >= cooldown:
                                msg_type = "episode" if playback_type == "episode" else "movie"
                                log(f"🔔 Attempting to show toast notification for missing segments ({msg_type})")

                                # CRITICAL: Double-check pause state right before showing toast
                                try:
                                    final_toast_is_playing = player.isPlayingVideo()
                                    final_toast_is_paused = xbmc.getCondVisibility("Player.Paused")
                                    if final_toast_is_paused or not final_toast_is_playing:
                                        log(f"🔕 Missing segments toast suppressed — playback paused right before showing (is_playing={final_toast_is_playing}, is_paused={final_toast_is_paused})")
                                    else:
                                        try:
                                            xbmcgui.Dialog().notification(
                                                heading="Skippy",
                                                message=f"No skip segments found for this {msg_type}.",
                                                icon=ICON_PATH,
                                                time=3000,
                                                sound=False
                                            )
                                            monitor.last_toast_time = now
                                            monitor.shown_missing_file_toast = True
                                            log(f"✅ Toast displayed for {msg_type}")
                                        except Exception as e:
                                            log(f"❌ Failed to display missing segments toast notification (possible Kodi/device limitation): {e}")
                                except RuntimeError:
                                    log("🔕 Missing segments toast suppressed — player state unavailable right before showing")
                            else:
                                log(f"⏳ [TOAST BLOCK] Suppressed — cooldown active ({int(now - monitor.last_toast_time)}s since last toast)")
                        else:
                            log("✅ [TOAST BLOCK] Toast suppressed — toast toggle disabled for this type")
                            monitor.shown_missing_file_toast = True
                    except Exception as e:
                        log(f"❌ [TOAST BLOCK] should_show_missing_file_toast() failed: {e}")
                        monitor.shown_missing_file_toast = True
            except RuntimeError:
                log("🔕 Missing segments toast suppressed — player state unavailable")

        if not monitor.playback_ready:
            log_if_changed("playback_ready", "⏳ Playback not ready — waiting before processing segments")
            monitor.last_time = current_time
            continue

        # Process segments - if major rewind was detected, force re-evaluation of all segments
        segments_to_process = monitor.current_segments
        if major_rewind_detected:
            log("🔄 Major rewind detected — re-evaluating all segments for active dialogs")
            # Clear log cache on major rewind to allow re-logging
            monitor._last_log_state.clear()
        
        # Debug: Show current state of tracking sets (only log when counts change)
        log_if_changed("state_summary", f"📊 Current state: prompted={len(monitor.prompted)} items, recently_dismissed={len(monitor.recently_dismissed)} items, skipped_to_nested={len(monitor.skipped_to_nested_segment)} items")
        
        for segment in segments_to_process:
            # Generate segment ID consistently - use round() then int() to handle floating point precision
            # This ensures consistent matching even if segment times have slight floating point differences
            seg_id = (int(round(segment.start_seconds)), int(round(segment.end_seconds)))
            
            # CRITICAL: Check if dismissed FIRST, before any other checks
            # This ensures dismissed dialogs never reappear, even after pause/resume
            # This check must happen before is_active, prompted, or any other checks
            # This is the ABSOLUTE FIRST check - nothing else matters if the segment was dismissed
            if seg_id in monitor.recently_dismissed:
                # Always log this (not using log_if_changed) to help debug dismissal issues
                # Log every time to catch any cases where this check might be bypassed
                log(f"🚫 Segment {seg_id} ({segment.segment_type_label}) was dismissed — skipping ALL processing (will not reappear after pause/resume)")
                log(f"🔍 Debug: segment.start_seconds={segment.start_seconds}, segment.end_seconds={segment.end_seconds}, seg_id={seg_id}")
                log(f"🔍 Debug: recently_dismissed contains {len(monitor.recently_dismissed)} items: {list(monitor.recently_dismissed)}")
                # Ensure it's also in prompted to prevent any further checks
                monitor.prompted.add(seg_id)
                # CRITICAL: Use continue to skip ALL further processing for this segment
                continue
            
            if seg_id in monitor.prompted:
                # Only log once per segment when it's first marked as prompted
                continue

            if not segment.is_active(current_time):
                # Don't log inactive segments - they're checked every second
                continue
            
            # Check if this segment dialog should be suppressed due to overlapping/nested segments
            # Pass recently_dismissed so nested segments can show even if parent was dismissed
            # The should_suppress_segment_dialog function handles the logic for nested segments in dismissed parents
            if should_suppress_segment_dialog(segment, monitor.current_segments, current_time, monitor.recently_dismissed):
                log_if_changed(f"suppressed_{seg_id}", f"🚫 Segment {seg_id} dialog suppressed due to overlapping/nested segment priority")
                continue
            
            # Check if this segment dialog should be suppressed because we've skipped to a nested segment
            # BUT: Only suppress if we're still within the nested segment
            # If we've exited the nested segment, the parent should show its dialog again
            # NOTE: This check should rarely be needed since we clean up exited nested segments above,
            # but it's here as a defensive check in case we missed something
            if seg_id in monitor.skipped_to_nested_segment:
                nested_segment = monitor.skipped_to_nested_segment[seg_id]
                # Only suppress if we're still in the nested segment
                if nested_segment.is_active(current_time):
                    log_if_changed(f"nested_{seg_id}", f"🚫 Segment {seg_id} dialog suppressed because we're still in nested segment '{nested_segment.segment_type_label}'")
                    continue
                else:
                    # We've exited the nested segment, but the parent is still active
                    # This should have been handled above, but clean up here as well
                    log(f"🔄 Exited nested segment '{nested_segment.segment_type_label}', parent {seg_id} is still active — allowing parent dialog to show (defensive cleanup)")
                    
                    # CRITICAL: Remove nested segment from recently_dismissed if it was dismissed
                    nested_seg_id_defensive = (int(round(nested_segment.start_seconds)), int(round(nested_segment.end_seconds)))
                    if nested_seg_id_defensive in monitor.recently_dismissed:
                        monitor.recently_dismissed.remove(nested_seg_id_defensive)
                        log(f"🔓 Removed nested segment {nested_seg_id_defensive} ({nested_segment.segment_type_label}) from recently_dismissed after exiting nested segment (defensive cleanup)")
                    
                    del monitor.skipped_to_nested_segment[seg_id]
                    # Also remove from prompted if it's there, so the parent dialog can show again
                    # BUT: Only if the parent was NOT dismissed by the user
                    if seg_id not in monitor.recently_dismissed:
                        if seg_id in monitor.prompted:
                            monitor.prompted.remove(seg_id)
                            log(f"🔄 Removed parent segment {seg_id} from prompted set to allow dialog to show (defensive cleanup)")
                    # Don't continue - let the parent segment dialog show
            
            # Only log segment processing when it's a new active segment
            log(f"🔎 Processing active segment: '{segment.segment_type_label}' [{segment.start_seconds}-{segment.end_seconds}]")
            behavior = get_user_skip_mode(segment.segment_type_label)
            log(f"🧪 Segment behavior: {behavior}")

            if not show_dialogs:
                log_if_changed(f"dialogs_disabled_{seg_id}", f"🚫 Dialogs disabled in settings — suppressing dialog for segment {seg_id} (behavior: {behavior})")
                monitor.prompted.add(seg_id)
                continue  
            if behavior == "never":
                log_if_changed(f"never_{seg_id}", f"🚫 Skipping dialog for '{segment.segment_type_label}' (user preference: never)")
                continue

            log(f"🕒 Active segment: {segment.segment_type_label} [{segment.start_seconds}-{segment.end_seconds}] → {behavior}")

            # Check if skipping is enabled for this playback type
            if not is_skip_enabled(playback_type):
                log(f"🚫 Skipping disabled for {playback_type} — segment {seg_id} will not be skipped")
                monitor.prompted.add(seg_id)
                continue

            # Correctly handle jump point from the new logic
            jump_to = segment.next_segment_start if segment.next_segment_start is not None else segment.end_seconds + 1.0

            if behavior == "auto":
                log(f"⚙ Auto-skip behavior triggered for segment ID {seg_id} ({segment.segment_type_label})")
                
                # Track if we're skipping to a nested segment
                if segment.next_segment_start is not None:
                    # Find the target segment we're jumping to
                    target_segment = None
                    for seg in monitor.current_segments:
                        if seg.start_seconds == segment.next_segment_start:
                            target_segment = seg
                            break
                    
                    if target_segment and is_nested_segment(segment, target_segment):
                        # We're skipping to a nested segment, track this
                        monitor.skipped_to_nested_segment[seg_id] = target_segment
                        log(f"🔗 Tracked skip to nested segment: {seg_id} -> {target_segment.segment_type_label}")
                        log(f"🔗 Parent segment {seg_id} will be re-enabled when exiting nested segment {target_segment.start_seconds}-{target_segment.end_seconds}")
                        # CRITICAL: Add parent to prompted to suppress its dialog while in nested segment
                        # This will be removed when nested segment ends (in the cleanup logic above)
                        monitor.prompted.add(seg_id)
                        log(f"🔗 Added parent segment {seg_id} to prompted set to suppress dialog while in nested segment")
                        # CRITICAL: Clear parent from recently_dismissed if it was dismissed
                        # This allows the parent dialog to reappear after the nested segment ends
                        if seg_id in monitor.recently_dismissed:
                            nested_seg_id = (int(round(target_segment.start_seconds)), int(round(target_segment.end_seconds)))
                            clearance_key = (seg_id, nested_seg_id)
                            if clearance_key not in monitor.cleared_parent_dismissals:
                                monitor.recently_dismissed.remove(seg_id)
                                monitor.cleared_parent_dismissals.add(clearance_key)
                                log(f"🔓 Cleared parent segment {seg_id} from recently_dismissed because user skipped to nested segment {target_segment.segment_type_label}")
                                log(f"🔍 Debug: recently_dismissed now has {len(monitor.recently_dismissed)} items: {list(monitor.recently_dismissed)}")
                            else:
                                log(f"🔍 Parent segment {seg_id} dismissal already cleared for nested segment {nested_seg_id}")
                
                player.seekTime(jump_to)
                monitor.last_time = jump_to
                # Only add to prompted if we're NOT skipping to a nested segment
                # (If we are, it was already added above)
                if seg_id not in monitor.prompted:
                    monitor.prompted.add(seg_id)

                if addon.getSettingBool("show_toast_for_skipped_segment"):
                    log("🔔 Showing toast notification for auto-skipped segment")
                    try:
                        xbmcgui.Dialog().notification(
                            heading="Skipped",
                            message=f"{segment.segment_type_label.title()} skipped",
                            icon=ICON_PATH,
                            time=2000,
                            sound=False
                        )
                        log("✅ Toast notification displayed successfully")
                    except Exception as e:
                        log(f"❌ Failed to display toast notification (possible Kodi/device limitation): {e}")
                else:
                    log("🔕 Skipped segment toast disabled by user setting")

                log(f"⚡ Auto-skipped to {jump_to}")

            elif behavior == "ask":
                log(f"🧠 Ask-skip behavior triggered for segment ID {seg_id} ({segment.segment_type_label})")

                # Note: Dismissal check and pause check are already done at the top of the loop
                # This ensures dismissed dialogs never reappear
                # Pause check prevents dialogs from appearing when paused

                # Double-check pause state right before showing dialog (defensive programming)
                try:
                    dialog_is_playing = player.isPlayingVideo()
                    dialog_is_paused = xbmc.getCondVisibility("Player.Paused")
                except RuntimeError:
                    dialog_is_playing = False
                    dialog_is_paused = True
                
                if dialog_is_paused or not dialog_is_playing:
                    log(f"⏸️ Video paused/stopped right before dialog — skipping dialog for segment {seg_id}")
                    # Don't add to prompted, allow retry when resumed
                    continue

                try:
                    log("🛑 Debouncing skip dialog for 300ms")
                    xbmc.sleep(300)

                    dialog_mode = (addon.getSetting("skip_dialog_mode") or "Full").strip()
                    if dialog_mode == "Minimal":
                        layout_value = _skip_dialog_layout_suffix(
                            addon, "minimal_skip_dialog_position"
                        )
                        dialog_name = f"Minimal_Skip_Dialog_{layout_value}.xml"
                    else:
                        layout_value = _skip_dialog_layout_suffix(
                            addon, "skip_dialog_position"
                        )
                        dialog_name = f"SkipDialog_{layout_value}.xml"
                    log(f"📐 Using skip dialog ({dialog_mode}): {dialog_name}")

                    try:
                        if dialog_mode == "Minimal":
                            plate_file = _minimal_plate_filename(addon)
                            _update_minimal_skip_dialog_textures(plate_file)
                            log(f"🎨 Minimal textures set to: {plate_file}")
                        else:
                            focus_texture_file = addon.getSetting("button_focus_style")
                            if focus_texture_file:
                                _update_full_skip_dialog_textures(focus_texture_file)
                                log(f"🎨 Button focus texture set to: {focus_texture_file}")
                    except Exception as e:
                        log(f"⚠️ Failed to update skip dialog skin XML: {e}")

                    log(f"🎬 Attempting to create skip dialog: {dialog_name}")
                    try:
                        dialog = SkipDialog(dialog_name, addon.getAddonInfo("path"), "default", segment=segment)
                        log("✅ Skip dialog created successfully")
                    except Exception as e:
                        log(f"❌ Failed to create skip dialog (possible Kodi/device limitation): {e}")
                        log(f"❌ Dialog creation failed for segment {seg_id} ({segment.segment_type_label})")
                        monitor.prompted.add(seg_id)
                        continue
                    
                    try:
                        log("🔄 Calling dialog.doModal()")
                        dialog.doModal()
                        log("✅ Dialog doModal() completed")
                    except Exception as e:
                        log(f"❌ Dialog doModal() failed (possible Kodi/device limitation): {e}")
                        log(f"❌ Dialog display failed for segment {seg_id} ({segment.segment_type_label})")
                        try:
                            del dialog
                        except:
                            pass
                        monitor.prompted.add(seg_id)
                        continue
                    
                    confirmed = getattr(dialog, "response", None)
                    try:
                        del dialog
                    except:
                        pass

                    if confirmed:
                        log(f"✅ User confirmed skip for segment ID {seg_id}")
                        
                        # Track if we're skipping to a nested segment
                        if segment.next_segment_start is not None:
                            # Find the target segment we're jumping to
                            target_segment = None
                            for seg in monitor.current_segments:
                                if seg.start_seconds == segment.next_segment_start:
                                    target_segment = seg
                                    break
                            
                            if target_segment and is_nested_segment(segment, target_segment):
                                # We're skipping to a nested segment, track this
                                monitor.skipped_to_nested_segment[seg_id] = target_segment
                                log(f"🔗 Tracked skip to nested segment: {seg_id} -> {target_segment.segment_type_label}")
                                log(f"🔗 Parent segment {seg_id} will be re-enabled when exiting nested segment {target_segment.start_seconds}-{target_segment.end_seconds}")
                                # CRITICAL: Add parent to prompted to suppress its dialog while in nested segment
                                # This will be removed when nested segment ends (in the cleanup logic above)
                                monitor.prompted.add(seg_id)
                                log(f"🔗 Added parent segment {seg_id} to prompted set to suppress dialog while in nested segment")
                                # CRITICAL: Clear parent from recently_dismissed if it was dismissed
                                # This allows the parent dialog to reappear after the nested segment ends
                                if seg_id in monitor.recently_dismissed:
                                    nested_seg_id = (int(round(target_segment.start_seconds)), int(round(target_segment.end_seconds)))
                                    clearance_key = (seg_id, nested_seg_id)
                                    if clearance_key not in monitor.cleared_parent_dismissals:
                                        monitor.recently_dismissed.remove(seg_id)
                                        monitor.cleared_parent_dismissals.add(clearance_key)
                                        log(f"🔓 Cleared parent segment {seg_id} from recently_dismissed because user skipped to nested segment {target_segment.segment_type_label}")
                                        log(f"🔍 Debug: recently_dismissed now has {len(monitor.recently_dismissed)} items: {list(monitor.recently_dismissed)}")
                                    else:
                                        log(f"🔍 Parent segment {seg_id} dismissal already cleared for nested segment {nested_seg_id}")
                        
                        # Only add to prompted if we're NOT skipping to a nested segment
                        # (If we are, it was already added above)
                        if seg_id not in monitor.prompted:
                            monitor.prompted.add(seg_id)
                        player.seekTime(jump_to)
                        monitor.last_time = jump_to

                        if addon.getSettingBool("show_toast_for_skipped_segment"):
                            log("🔔 Showing toast notification for user-confirmed skip")
                            try:
                                xbmcgui.Dialog().notification(
                                    heading="Skipped",
                                    message=f"{segment.segment_type_label.title()} skipped",
                                    icon=ICON_PATH,
                                    time=2000,
                                    sound=False
                                )
                                log("✅ Toast notification displayed successfully")
                            except Exception as e:
                                log(f"❌ Failed to display toast notification (possible Kodi/device limitation): {e}")
                        else:
                            log("🔕 Skipped segment toast disabled by user setting")

                        log(f"🚀 Jumped to {jump_to}")
                    else:
                        log(f"🙅 User dismissed skip dialog for segment ID {seg_id}")
                        log(f"🔍 Debug: segment.start_seconds={segment.start_seconds}, segment.end_seconds={segment.end_seconds}, seg_id={seg_id}")
                        # CRITICAL: Use the same seg_id that was calculated at the start of the loop
                        # This ensures perfect matching with the recently_dismissed check
                        # The seg_id was already calculated as (int(round(segment.start_seconds)), int(round(segment.end_seconds)))
                        monitor.recently_dismissed.add(seg_id)
                        monitor.prompted.add(seg_id)
                        log(f"📊 Added {seg_id} to recently_dismissed and prompted sets")
                        log(f"🔍 Debug: recently_dismissed now contains {len(monitor.recently_dismissed)} items: {list(monitor.recently_dismissed)}")
                        log(f"🔒 Segment {seg_id} ({segment.segment_type_label}) is now permanently dismissed for this playback session")
                        log(f"🔒 This segment will NOT reappear after pause/resume unless there is a major rewind")
                        # Verify the dismissal was recorded
                        if seg_id in monitor.recently_dismissed:
                            log(f"✅ Verification: Segment {seg_id} confirmed in recently_dismissed set")
                        else:
                            log(f"❌ ERROR: Segment {seg_id} NOT found in recently_dismissed set after adding!")
                except Exception as e:
                    log(f"❌ Error showing skip dialog: {e}")
                    monitor.prompted.add(seg_id)
                    continue

        # Update last_time at the end of each main loop cycle for next iteration's rewind detection
        monitor.last_time = current_time


    if monitor.waitForAbort(CHECK_INTERVAL):
        log("🛑 Abort requested — exiting monitor loop")