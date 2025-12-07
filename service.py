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

from settings_utils import is_skip_dialog_enabled
from skipdialog import SkipDialog
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

def _update_button_textures(texture_path):
    """Update button textures in XML files dynamically"""
    try:
        import os
        import re
        
        # Get the addon path
        addon = get_addon()
        addon_path = addon.getAddonInfo('path')
        xml_dir = os.path.join(addon_path, 'resources', 'skins', 'default', '720p')
        
        # List of XML files to update
        xml_files = [
            'SkipDialog_BottomRight.xml',
            'SkipDialog_BottomLeft.xml', 
            'SkipDialog_TopLeft.xml',
            'SkipDialog_TopRight.xml'
        ]
        
        for xml_file in xml_files:
            xml_path = os.path.join(xml_dir, xml_file)
            if os.path.exists(xml_path):
                # Read the file
                with open(xml_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Replace the texture path
                content = re.sub(
                    r'<texturefocus>.*?</texturefocus>',
                    f'<texturefocus>{texture_path}</texturefocus>',
                    content
                )
                
                # Write back to file
                with open(xml_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                log(f"📝 Updated {xml_file} with texture: {texture_path}")
                
    except Exception as e:
        log(f"⚠️ Failed to update XML files: {e}")

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
    try:
        if not player.isPlayingVideo():
            return None
        path = player.getPlayingFile()
    except RuntimeError:
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

    if not item or "title" not in item:
        log("⚠ Player.GetItem returned empty or missing title — metadata not ready")
        return False, {}

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

def should_suppress_segment_dialog(current_segment, all_segments, current_time):
    """
    Check if the current segment dialog should be suppressed because we're inside
    a nested or overlapping segment that should take priority.
    
    Returns True if the dialog should be suppressed.
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
    
    # Check if there are any segments that start after the current segment
    # and are nested within it - these should take priority
    for i in range(current_index + 1, len(active_segments)):
        later_segment = active_segments[i]
        
        # If the later segment is nested within the current segment, suppress current
        if is_nested_segment(current_segment, later_segment):
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
    if has_overlap_or_nested and show_overlapping_toast() and not monitor.toast_overlap_shown:
        xbmcgui.Dialog().notification(
            heading="Skippy",
            message="Overlapping/Nested segments detected.",
            icon=ICON_PATH,
            time=4000
        )
        monitor.toast_overlap_shown = True
        log("Toast notification displayed for overlapping segments.")
        
    log(f"✅ Pass 2 complete. Final segments to process: {len(filtered_segments)}")
    return filtered_segments

log_always("📡 XML-EDL Intro Skipper service started.")

while not monitor.abortRequested():
    if player.isPlayingVideo() or xbmc.getCondVisibility("Player.HasVideo"):
        video = get_video_file()
        if not video:
            log("⚠ get_video_file() returned None — skipping this cycle")
            monitor.last_video = None

        if video:
            # 🔁 Detect replay of same video
            try:
                current_playback_time = player.getTime()
                if (
                    video == monitor.last_video
                    and monitor.playback_ready
                    and current_playback_time < 5.0
                    and time.time() - monitor.playback_ready_time > 5.0
                ):
                    log("🔁 Replay of same video detected — resetting monitor state")
                    monitor.shown_missing_file_toast = False
                    monitor.prompted.clear()
                    monitor.recently_dismissed.clear()
                    monitor.playback_ready = False
                    monitor.play_start_time = time.time()
                    monitor.last_time = 0
                    monitor.last_toast_time = 0
                    monitor.toast_overlap_shown = False
                    monitor.skipped_to_nested_segment.clear()
            except RuntimeError:
                # Playback may have stopped, skip replay detection
                pass

            log(f"🚀 Entered video block — video={video}, last_video={monitor.last_video}")
            log(f"🎬 Now playing: {os.path.basename(video)}")

            if video != monitor.last_video:
                log("🆕 New video detected — resetting monitor state")
                monitor.last_video = video
                monitor.segment_file_found = False
                monitor.shown_missing_file_toast = False
                monitor.prompted.clear()
                monitor.recently_dismissed.clear()
                monitor.playback_ready = False
                monitor.play_start_time = time.time()
                monitor.last_time = 0
                monitor.last_toast_time = 0
                monitor.toast_overlap_shown = False
                monitor.skipped_to_nested_segment.clear()
            
            addon = get_addon()
            try:
                allow_toast, item = should_show_missing_file_toast()
                playback_type = infer_playback_type(item)
                log(f"🔍 Playback type inferred via toast logic: '{playback_type}'")
            except Exception as e:
                log(f"❌ Failed to infer playback type via toast logic: {e}")
                playback_type = ""
                item = None

            show_dialogs = is_skip_dialog_enabled(playback_type)
            toast_movies = addon.getSettingBool("show_not_found_toast_for_movies")
            toast_episodes = addon.getSettingBool("show_not_found_toast_for_tv_episodes")

            log(f"🧪 Raw setting values → show_dialogs: {show_dialogs}, show_not_found_toast_for_movies: {toast_movies}, show_not_found_toast_for_tv_episodes: {toast_episodes}")

        try:
            current_time = player.getTime()
            log(f"🧪 Current playback time: {current_time}, last_time: {monitor.last_time}")
        except RuntimeError:
            log("⚠ player.getTime() failed — no media playing")
            continue

        if not playback_type:
            log("⚠ Playback type not detected — skipping segment parsing")
            monitor.current_segments = []
        else:
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
            log(f"⏪ Significant rewind detected ({monitor.last_time:.2f} → {current_time:.2f}) — threshold: {rewind_threshold}s")
            monitor.prompted.clear()
            monitor.recently_dismissed.clear()
            monitor.skipped_to_nested_segment.clear()
            
            # Re-evaluate segment jump points after major rewind to ensure correct jump targets
            if monitor.current_segments:
                re_evaluate_segment_jump_points(monitor.current_segments, current_time)
            
            major_rewind_detected = True
            log("🧹 recently_dismissed cleared due to rewind, nested segment tracking cleared, jump points re-evaluated")
        
        # Check if we've exited any nested segments and need to re-enable parent segment dialogs
        if monitor.skipped_to_nested_segment:
            log(f"🔍 Checking {len(monitor.skipped_to_nested_segment)} tracked nested segments at time {current_time:.2f}")
        
        segments_to_remove = []
        for parent_seg_id, nested_segment in monitor.skipped_to_nested_segment.items():
            # Check if we're no longer in the nested segment
            is_nested_active = nested_segment.is_active(current_time)
            log(f"🔍 Nested segment '{nested_segment.segment_type_label}' ({nested_segment.start_seconds}-{nested_segment.end_seconds}) active at {current_time:.2f}: {is_nested_active}")
            
            if not is_nested_active:
                # We've exited the nested segment, remove from tracking
                segments_to_remove.append(parent_seg_id)
                # Re-enable the parent segment dialog by removing it from prompted set
                if parent_seg_id in monitor.prompted:
                    monitor.prompted.remove(parent_seg_id)
                    log(f"🔄 Exited nested segment '{nested_segment.segment_type_label}', re-enabled parent segment {parent_seg_id} dialog")
                else:
                    log(f"🔄 Exited nested segment '{nested_segment.segment_type_label}', parent segment {parent_seg_id} was not in prompted set")
                
                # Re-evaluate segment jump points since we've exited a nested segment
                if monitor.current_segments:
                    log(f"🔄 Re-evaluating jump points after exiting nested segment '{nested_segment.segment_type_label}'")
                    re_evaluate_segment_jump_points(monitor.current_segments, current_time)
        
        # Remove exited nested segments from tracking
        for seg_id in segments_to_remove:
            del monitor.skipped_to_nested_segment[seg_id]

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

                        xbmcgui.Dialog().notification(
                            heading="Skippy",
                            message=f"No skip segments found for this {msg_type}.",
                            icon=ICON_PATH,
                            time=3000,
                            sound=False
                        )
                        monitor.last_toast_time = now
                        monitor.shown_missing_file_toast = True
                        log(f"⚠ [TOAST BLOCK] Toast displayed for {msg_type}")
                    else:
                        log(f"⏳ [TOAST BLOCK] Suppressed — cooldown active ({int(now - monitor.last_toast_time)}s since last toast)")
                else:
                    log("✅ [TOAST BLOCK] Toast suppressed — toast toggle disabled for this type")
                    monitor.shown_missing_file_toast = True
            except Exception as e:
                log(f"❌ [TOAST BLOCK] should_show_missing_file_toast() failed: {e}")
                monitor.shown_missing_file_toast = True

        if not monitor.playback_ready:
            log("⏳ Playback not ready — waiting before processing segments")
            monitor.last_time = current_time
            continue

        # Process segments - if major rewind was detected, force re-evaluation of all segments
        segments_to_process = monitor.current_segments
        if major_rewind_detected:
            log("🔄 Major rewind detected — re-evaluating all segments for active dialogs")
        
        # Debug: Show current state of tracking sets
        log(f"📊 Current state: prompted={len(monitor.prompted)} items, recently_dismissed={len(monitor.recently_dismissed)} items, skipped_to_nested={len(monitor.skipped_to_nested_segment)} items")
        if monitor.recently_dismissed:
            log(f"📊 Recently dismissed segments: {list(monitor.recently_dismissed)}")
        
        for segment in segments_to_process:
            seg_id = (int(segment.start_seconds), int(segment.end_seconds))
            
            if seg_id in monitor.prompted:
                log(f"⏭ Segment {seg_id} already prompted — skipping")
                continue
                
            if seg_id in monitor.recently_dismissed:
                log(f"🙅 Segment {seg_id} is in recently_dismissed — skipping")
                continue

            if not segment.is_active(current_time):
                log(f"⏳ Segment {seg_id} not active at {current_time:.2f} — skipping")
                continue
            
            # Check if this segment dialog should be suppressed due to overlapping/nested segments
            if should_suppress_segment_dialog(segment, monitor.current_segments, current_time):
                log(f"🚫 Segment {seg_id} dialog suppressed due to overlapping/nested segment priority")
                continue
            
            # Check if this segment dialog should be suppressed because we've skipped to a nested segment
            if seg_id in monitor.skipped_to_nested_segment:
                log(f"🚫 Segment {seg_id} dialog suppressed because we've skipped to nested segment")
                continue
            
            log(f"🔎 Raw segment label before skip mode check: '{segment.segment_type_label}'")
            behavior = get_user_skip_mode(segment.segment_type_label)
            log(f"🧪 Segment behavior for '{segment.segment_type_label}': {behavior}")

            if not show_dialogs:
                log(f"🚫 Dialogs disabled in settings — suppressing dialog for segment {seg_id} (behavior: {behavior})")
                monitor.prompted.add(seg_id)
                continue  
            if behavior == "never":
                log(f"🚫 Skipping dialog for '{segment.segment_type_label}' (user preference: never)")
                continue

            log(f"🕒 Active segment: {segment.segment_type_label} [{segment.start_seconds}-{segment.end_seconds}] → {behavior}")
            log(f"📘 Segment source: {segment.source}")

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
                
                player.seekTime(jump_to)
                monitor.last_time = jump_to
                monitor.prompted.add(seg_id)

                if addon.getSettingBool("show_toast_for_skipped_segment"):
                    log("🔔 Showing toast notification for auto-skipped segment")
                    xbmcgui.Dialog().notification(
                        heading="Skipped",
                        message=f"{segment.segment_type_label.title()} skipped",
                        icon=ICON_PATH,
                        time=2000,
                        sound=False
                    )
                else:
                    log("🔕 Skipped segment toast disabled by user setting")

                log(f"⚡ Auto-skipped to {jump_to}")

            elif behavior == "ask":
                log(f"🧠 Ask-skip behavior triggered for segment ID {seg_id} ({segment.segment_type_label})")

                if not player.isPlayingVideo():
                    log("⚠ Playback not active — skipping dialog")
                    monitor.prompted.add(seg_id)
                    continue

                try:
                    log("🛑 Debouncing skip dialog for 300ms")
                    xbmc.sleep(300)

                    layout_value = addon.getSetting("skip_dialog_position").replace(" ", "")
                    dialog_name = f"SkipDialog_{layout_value}.xml"
                    log(f"📐 Using skip dialog layout: {dialog_name}")

                    # 🎨 Update button focus texture before creating dialog
                    try:
                        focus_texture_file = addon.getSetting("button_focus_style")
                        if focus_texture_file:
                            _update_button_textures(focus_texture_file)
                            log(f"🎨 Button focus texture set to: {focus_texture_file}")
                    except Exception as e:
                        log(f"⚠️ Failed to set button focus texture: {e}")

                    dialog = SkipDialog(dialog_name, addon.getAddonInfo("path"), "default", segment=segment)
                    dialog.doModal()
                    confirmed = getattr(dialog, "response", None)
                    del dialog

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
                        
                        monitor.prompted.add(seg_id)
                        player.seekTime(jump_to)
                        monitor.last_time = jump_to

                        if addon.getSettingBool("show_toast_for_skipped_segment"):
                            log("🔔 Showing toast notification for user-confirmed skip")
                            xbmcgui.Dialog().notification(
                                heading="Skipped",
                                message=f"{segment.segment_type_label.title()} skipped",
                                icon=ICON_PATH,
                                time=2000,
                                sound=False
                            )
                        else:
                            log("🔕 Skipped segment toast disabled by user setting")

                        log(f"🚀 Jumped to {jump_to}")
                    else:
                        log(f"🙅 User dismissed skip dialog for segment ID {seg_id}")
                        monitor.recently_dismissed.add(seg_id)
                        monitor.prompted.add(seg_id)
                        log(f"📊 Added {seg_id} to recently_dismissed and prompted sets")
                except Exception as e:
                    log(f"❌ Error showing skip dialog: {e}")
                    monitor.prompted.add(seg_id)
                    continue

        # Update last_time at the end of each main loop cycle for next iteration's rewind detection
        monitor.last_time = current_time


    if monitor.waitForAbort(CHECK_INTERVAL):
        log("🛑 Abort requested — exiting monitor loop")