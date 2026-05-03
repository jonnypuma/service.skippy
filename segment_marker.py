# -*- coding: utf-8 -*-
"""
Segment Marker — manual segment creation via long-press hotkey or remote button.

Flow:
1. First invocation: mark start time, show toast
2. Second invocation: mark end time, show segment type picker
3. Save to EDL and chapters.xml (with optional confirmation)

State is stored in addon settings (pending_marker_start) to persist across invocations.
"""
import json
import os
import stat
import sys
import time
import unicodedata
import xml.etree.ElementTree as ET

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

from keymap_utils import install_marker_keymap
from segment_editor_parser import (
    CHAPTER_XML_SIDECAR_SUFFIXES,
    DEFAULT_NEW_CHAPTER_XML_SUFFIX,
)
from settings_utils import (
    get_edl_label_to_action_map,
    normalize_label,
    get_custom_segment_keyword_labels,
    skippy_notification_icon,
)

ADDON_ID = "service.skippy"

_CANCEL_ACTION_IDS = (10, 92, 216)
_SELECT_ACTION_IDS = (7, 100)
_KEYBOARD_CONFIRM_ACTION_IDS = (7, 100)
_KEYBOARD_CONFIRM_BUTTON_CODES = (13, 61453)
_MARKER_MODAL_PROPERTY = "skippy_marker_modal_open"
_MARKER_POLICY_MERGE = "MergeNonOverlapping"
_MARKER_POLICY_KEEP_BOTH = "KeepBothOldAfterNew"
_MARKER_POLICY_OVERWRITE = "OverwriteOverlapping"
_MARKER_POLICY_APPEND = "AppendAlways"
_MARKER_POLICY_REPLACE = "ReplaceFile"
_MARKER_POLICY_ASK = "AskEachTime"
_MARKER_POLICY_LABELS = {
    _MARKER_POLICY_MERGE: "Merge non-overlapping",
    _MARKER_POLICY_KEEP_BOTH: "Keep both (old starts after new)",
    _MARKER_POLICY_OVERWRITE: "Overwrite overlapping",
    _MARKER_POLICY_APPEND: "Append always",
    _MARKER_POLICY_REPLACE: "Replace file",
}
_MARKER_POLICY_ASK_LABELS = {
    _MARKER_POLICY_MERGE: "Merge non-overlapping",
    _MARKER_POLICY_KEEP_BOTH: "Keep both (old starts after new)",
    _MARKER_POLICY_OVERWRITE: "Overwrite overlapping",
    _MARKER_POLICY_APPEND: "Append",
    _MARKER_POLICY_REPLACE: "Replace file",
}
_CEC_ACTION_TO_REMOTE_TAG = {
    1: "left",
    2: "right",
    3: "up",
    4: "down",
    7: "select",
    11: "info",
    12: "pause",
    13: "stop",
    14: "skipplus",
    15: "skipminus",
    68: "play",
    79: "rewind",
    80: "fastforward",
    117: "contextmenu",
}


def get_addon():
    try:
        return xbmcaddon.Addon(ADDON_ID)
    except Exception:
        return None


def log(msg):
    safe_msg = unicodedata.normalize("NFKD", str(msg)).encode("ascii", "ignore").decode("ascii")
    xbmc.log(f"[{ADDON_ID} - SegmentMarker] {safe_msg}", xbmc.LOGINFO)


def get_localized(addon, string_id):
    try:
        s = addon.getLocalizedString(string_id)
        return s if s else str(string_id)
    except Exception:
        return str(string_id)


def format_time(seconds):
    """Format seconds as H:MM:SS or M:SS."""
    seconds = max(0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def get_current_playback_time():
    """Return current playback time in seconds, or None if not playing."""
    player = xbmc.Player()
    try:
        if player.isPlayingVideo():
            return player.getTime()
    except RuntimeError:
        pass
    return None


def get_video_path():
    """Return the current video file path, or None."""
    player = xbmc.Player()
    try:
        if player.isPlayingVideo():
            return player.getPlayingFile()
    except RuntimeError:
        pass
    return None


def get_pending_start():
    """Retrieve pending start time from window property (persists across script calls)."""
    try:
        val = xbmcgui.Window(10000).getProperty("skippy_marker_start")
        if val:
            return float(val)
    except Exception:
        pass
    return None


def set_pending_start(seconds):
    """Store pending start time in window property."""
    if seconds is None:
        xbmcgui.Window(10000).clearProperty("skippy_marker_start")
        xbmcgui.Window(10000).clearProperty("skippy_marker_path")
    else:
        xbmcgui.Window(10000).setProperty("skippy_marker_start", str(seconds))
        path = get_video_path()
        if path:
            xbmcgui.Window(10000).setProperty("skippy_marker_path", path)


def get_pending_path():
    """Get the video path associated with pending start."""
    try:
        return xbmcgui.Window(10000).getProperty("skippy_marker_path")
    except Exception:
        return None


def show_toast(msg, time_ms=3000):
    addon = get_addon()
    icon = skippy_notification_icon(addon) if addon else ""
    xbmcgui.Dialog().notification("Skippy", msg, icon, time_ms, sound=False)


def set_marker_modal_open(is_open):
    try:
        window = xbmcgui.Window(10000)
        if is_open:
            window.setProperty(_MARKER_MODAL_PROPERTY, "true")
        else:
            window.clearProperty(_MARKER_MODAL_PROPERTY)
    except Exception:
        pass


class ButtonDiscoveryDialog(xbmcgui.WindowDialog):
    """Capture the next remote action and expose its Kodi button code."""

    def __init__(self):
        super().__init__()
        self.button_code = None
        self.remote_tag = None
        self.action_id = None
        self.cancelled = False
        self._build_controls()

    def _addon_media_path(self, filename):
        addon = get_addon()
        if not addon:
            return filename
        path = os.path.join(addon.getAddonInfo("path"), "resources", "skins", "default", "media", filename)
        return path if xbmcvfs.exists(path) else "black.png"

    def _build_controls(self):
        white_texture = self._addon_media_path("white.png")
        try:
            overlay = xbmcgui.ControlImage(0, 0, 1280, 720, white_texture)
            overlay.setColorDiffuse("80000000")
            self.addControl(overlay)
        except Exception:
            pass
        try:
            panel = xbmcgui.ControlImage(250, 220, 780, 280, white_texture)
            panel.setColorDiffuse("F0202020")
            self.addControl(panel)
        except Exception:
            pass

        self.addControl(xbmcgui.ControlLabel(280, 248, 720, 45, "Skippy Remote Button Discovery", "font30", "FFFFFFFF"))
        self.addControl(xbmcgui.ControlLabel(280, 312, 720, 35, "Press the remote button to use for Segment Marker.", "font14", "FFB0D4E8"))
        self.addControl(xbmcgui.ControlLabel(280, 352, 720, 35, "Bluetooth/raw remotes save as key:<code>.", "font14", "FFFFFFFF"))
        self.addControl(xbmcgui.ControlLabel(280, 392, 720, 35, "CEC remotes save as Kodi remote button names when possible.", "font14", "FFFFFFFF"))
        self.addControl(xbmcgui.ControlLabel(280, 442, 720, 30, "Back/Esc cancels.", "font12", "FFB0B0B0"))

    def onAction(self, action):
        try:
            action_id = action.getId()
            button_code = action.getButtonCode()
        except Exception:
            action_id = None
            button_code = None

        if action_id in _CANCEL_ACTION_IDS:
            self.cancelled = True
            self.close()
            return

        if button_code:
            try:
                button_code_int = int(button_code)
            except Exception:
                button_code_int = None
            if action_id in _KEYBOARD_CONFIRM_ACTION_IDS and button_code_int in _KEYBOARD_CONFIRM_BUTTON_CODES:
                log(f"Ignoring keyboard confirm during remote discovery: action_id={action_id}, button_code={button_code}")
                return
            self.action_id = action_id
            self.button_code = button_code
            self.close()
            return

        remote_tag = _CEC_ACTION_TO_REMOTE_TAG.get(action_id)
        if remote_tag:
            self.action_id = action_id
            self.remote_tag = remote_tag
            self.close()
            return

        log(f"Ignoring unmapped discovery input: action_id={action_id}, button_code={button_code}")


class SegmentTypePickerDialog(xbmcgui.WindowXMLDialog):
    """Skinned picker used instead of Kodi's DialogSelect during playback."""

    CONTROL_LIST = 9100
    CONTROL_TITLE = 9101
    CONTROL_SUBTITLE = 9102
    CONTROL_FOOTER = 9103

    def __init__(self, *args, **kwargs):
        try:
            try:
                super().__init__(args[0], args[1], args[2], "720p")
            except TypeError:
                super().__init__(*args)
        except Exception:
            super().__init__(*args)
        self.title = kwargs.get("title", "Choose segment type")
        self.subtitle = kwargs.get("subtitle", "Choose the label for the marked segment.")
        self.footer = kwargs.get("footer", "Enter/OK selects. Back/Esc cancels.")
        self.options = kwargs.get("options", [])
        self.selected_index = -1
        self.cancelled = False
        self.list_control = None

    def onInit(self):
        try:
            self.getControl(self.CONTROL_TITLE).setLabel(self.title)
        except Exception:
            pass
        try:
            self.getControl(self.CONTROL_SUBTITLE).setLabel(self.subtitle)
        except Exception:
            pass
        try:
            self.getControl(self.CONTROL_FOOTER).setLabel(self.footer)
        except Exception:
            pass
        try:
            self.list_control = self.getControl(self.CONTROL_LIST)
            self.list_control.reset()
            self.list_control.addItems([xbmcgui.ListItem(label=label) for label in self.options])
            self.setFocus(self.list_control)
            if self.options:
                self.list_control.selectItem(0)
        except Exception as exc:
            log(f"Failed to initialise segment type picker: {exc}")
            self.cancelled = True
            self.close()

    def _select_current(self):
        if not self.list_control:
            return
        self.selected_index = self.list_control.getSelectedPosition()
        self.close()

    def onClick(self, control_id):
        if control_id == self.CONTROL_LIST:
            self._select_current()

    def onAction(self, action):
        try:
            action_id = action.getId()
        except Exception:
            action_id = None
        if action_id in _CANCEL_ACTION_IDS:
            self.cancelled = True
            self.close()
            return
        if action_id in _SELECT_ACTION_IDS:
            self._select_current()


def discover_remote_button(addon):
    set_marker_modal_open(True)
    dialog = None
    button_code = None
    remote_tag = None
    action_id = None
    cancelled = False
    try:
        dialog = ButtonDiscoveryDialog()
        dialog.doModal()
        button_code = getattr(dialog, "button_code", None)
        remote_tag = getattr(dialog, "remote_tag", None)
        action_id = getattr(dialog, "action_id", None)
        cancelled = getattr(dialog, "cancelled", False)
    finally:
        try:
            if dialog:
                del dialog
        except Exception:
            pass
        set_marker_modal_open(False)

    if cancelled:
        show_toast(get_localized(addon, 36014))
        return
    if remote_tag:
        value = remote_tag
        addon.setSetting("segment_marker_remote_button", value)
        install_marker_keymap(addon, notify=False)
        show_toast(f"CEC remote marker button set: {value}", time_ms=4500)
        log(f"CEC remote marker button discovered: action_id={action_id}, remote_tag={remote_tag}")
        return

    if not button_code:
        show_toast("No button code captured")
        log(f"Button discovery did not capture a usable button code; action_id={action_id}")
        return

    value = f"key:{button_code}"
    addon.setSetting("segment_marker_remote_button", value)
    install_marker_keymap(addon, notify=False)
    show_toast(f"Remote marker button set: {value}", time_ms=4500)
    log(f"Remote marker button discovered: action_id={action_id}, button_code={button_code}")


def get_segment_keywords(addon):
    """Return list of segment type labels from custom_segment_keywords setting."""
    try:
        return get_custom_segment_keyword_labels(addon)
    except Exception:
        return get_custom_segment_keyword_labels(None)


def pick_segment_type(addon):
    """Show dialog to pick segment type. Returns label or None if cancelled."""
    keywords = get_segment_keywords(addon)
    title = get_localized(addon, 36010)
    subtitle = "Choose the label for the marked segment."
    return pick_marker_option(addon, title, subtitle, keywords)


def pick_marker_option(addon, title, subtitle, options, footer="Enter/OK selects. Back/Esc cancels."):
    set_marker_modal_open(True)
    dialog = None
    idx = -1
    try:
        dialog = SegmentTypePickerDialog(
            "SegmentMarkerTypePicker.xml",
            addon.getAddonInfo("path"),
            "default",
            title=title,
            subtitle=subtitle,
            footer=footer,
            options=options,
        )
        dialog.doModal()
        idx = getattr(dialog, "selected_index", -1)
    finally:
        try:
            if dialog:
                del dialog
        except Exception:
            pass
        set_marker_modal_open(False)
    if idx < 0:
        return None
    return options[idx]


def ask_marker_existing_policy(addon, overlaps):
    warning = ""
    if overlaps:
        warning = f"Warning: overlaps existing {', '.join(overlaps)} entries. "
    subtitle = warning + "Choose how Skippy should save this marked range."
    options = [_MARKER_POLICY_ASK_LABELS[key] for key in (
        _MARKER_POLICY_MERGE,
        _MARKER_POLICY_KEEP_BOTH,
        _MARKER_POLICY_OVERWRITE,
        _MARKER_POLICY_APPEND,
        _MARKER_POLICY_REPLACE,
    )]
    choice = pick_marker_option(
        addon,
        "How should this marker be saved?",
        subtitle,
        options,
        footer="Merge is safest. Back/Esc cancels marker save.",
    )
    if choice is None:
        return None
    for key, label in _MARKER_POLICY_ASK_LABELS.items():
        if label == choice:
            return key
    return _MARKER_POLICY_MERGE


def confirm_save(addon, start, end, label):
    """Show confirmation dialog. Returns True if user confirms."""
    title = get_localized(addon, 36011)
    msg = f"{label}: {format_time(start)} -> {format_time(end)}"
    set_marker_modal_open(True)
    try:
        return xbmcgui.Dialog().yesno(title, msg)
    finally:
        set_marker_modal_open(False)


def seconds_to_hms(sec):
    """Convert seconds to HH:MM:SS.mmm format for chapters.xml."""
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def seconds_to_edl(sec):
    """Format seconds for EDL file (plain decimal)."""
    return f"{sec:.3f}"


def hms_to_seconds(hms):
    h, m, s = hms.strip().split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def ranges_overlap(start_a, end_a, start_b, end_b):
    return max(float(start_a), float(start_b)) < min(float(end_a), float(end_b))


def read_vfs_text(path):
    f = xbmcvfs.File(path, "r")
    content = f.read()
    f.close()
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    return content or ""


def write_vfs_text(path, content):
    f = xbmcvfs.File(path, "w")
    f.write(content)
    f.close()


def backup_existing_file(path, enabled):
    if not enabled or not xbmcvfs.exists(path):
        return
    backup_path = f"{path}.bck"
    try:
        if xbmcvfs.exists(backup_path):
            xbmcvfs.delete(backup_path)
        if xbmcvfs.copy(path, backup_path):
            log(f"Backed up existing marker file: {backup_path}")
        else:
            log(f"Backup copy returned false for: {backup_path}")
    except Exception as e:
        log(f"Could not back up {path}: {e}")


def marker_edl_path(video_path):
    base = video_path.rsplit(".", 1)[0]
    return f"{base}.edl"


def marker_chapters_xml_path(video_path):
    base = video_path.rsplit(".", 1)[0]
    for suffix in CHAPTER_XML_SIDECAR_SUFFIXES:
        path = f"{base}{suffix}"
        if xbmcvfs.exists(path):
            return path
    return f"{base}{DEFAULT_NEW_CHAPTER_XML_SUFFIX}"


def backup_marker_files_for_save_format(video_path, save_format, enabled):
    """Back up existing sidecars selected by the marker Save format setting."""
    if not enabled:
        return
    if save_format in ("Both", "EDL"):
        backup_existing_file(marker_edl_path(video_path), True)
    if save_format in ("Both", "XML"):
        backup_existing_file(marker_chapters_xml_path(video_path), True)


def normalize_marker_policy(policy):
    value = (policy or _MARKER_POLICY_MERGE).strip()
    aliases = {
        _MARKER_POLICY_MERGE.lower(): _MARKER_POLICY_MERGE,
        "merge non-overlapping": _MARKER_POLICY_MERGE,
        "merge": _MARKER_POLICY_MERGE,
        "0": _MARKER_POLICY_MERGE,
        _MARKER_POLICY_KEEP_BOTH.lower(): _MARKER_POLICY_KEEP_BOTH,
        "keepbotholdafternew": _MARKER_POLICY_KEEP_BOTH,
        "keep both (old starts after new)": _MARKER_POLICY_KEEP_BOTH,
        _MARKER_POLICY_OVERWRITE.lower(): _MARKER_POLICY_OVERWRITE,
        "overwrite overlapping": _MARKER_POLICY_OVERWRITE,
        "overwrite": _MARKER_POLICY_OVERWRITE,
        "1": _MARKER_POLICY_OVERWRITE,
        _MARKER_POLICY_APPEND.lower(): _MARKER_POLICY_APPEND,
        "append always": _MARKER_POLICY_APPEND,
        "append": _MARKER_POLICY_APPEND,
        "2": _MARKER_POLICY_APPEND,
        _MARKER_POLICY_REPLACE.lower(): _MARKER_POLICY_REPLACE,
        "replace file": _MARKER_POLICY_REPLACE,
        "replace": _MARKER_POLICY_REPLACE,
        "3": _MARKER_POLICY_REPLACE,
        _MARKER_POLICY_ASK.lower(): _MARKER_POLICY_ASK,
        "ask each time": _MARKER_POLICY_ASK,
        "ask": _MARKER_POLICY_ASK,
        "4": _MARKER_POLICY_ASK,
    }
    return aliases.get(value.lower(), _MARKER_POLICY_MERGE)


def existing_edl_overlaps(video_path, start, end):
    edl_path = marker_edl_path(video_path)
    if not xbmcvfs.exists(edl_path):
        return False
    try:
        for line in read_vfs_text(edl_path).splitlines():
            parsed_range = parse_edl_line_range(line.strip())
            if parsed_range and ranges_overlap(start, end, parsed_range[0], parsed_range[1]):
                return True
    except Exception as e:
        log(f"Could not check EDL overlap before marker save: {e}")
    return False


def existing_xml_overlaps(video_path, start, end):
    xml_path = marker_chapters_xml_path(video_path)
    if not xbmcvfs.exists(xml_path):
        return False
    try:
        root = ET.fromstring(read_vfs_text(xml_path))
        for atom in root.findall(".//ChapterAtom"):
            parsed_range = chapter_atom_range(atom)
            if parsed_range and ranges_overlap(start, end, parsed_range[0], parsed_range[1]):
                return True
    except Exception as e:
        log(f"Could not check XML overlap before marker save: {e}")
    return False


def marker_range_overlaps_existing(video_path, save_format, start, end):
    overlaps = []
    if save_format in ("Both", "EDL") and existing_edl_overlaps(video_path, start, end):
        overlaps.append("EDL")
    if save_format in ("Both", "XML") and existing_xml_overlaps(video_path, start, end):
        overlaps.append("chapters.xml")
    return overlaps


def marker_selected_sidecars_exist(video_path, save_format):
    if save_format in ("Both", "EDL") and xbmcvfs.exists(marker_edl_path(video_path)):
        return True
    if save_format in ("Both", "XML") and xbmcvfs.exists(marker_chapters_xml_path(video_path)):
        return True
    return False


def get_edl_action_for_label(addon, label):
    """
    Reverse lookup: find EDL action type for a given label.
    Uses merged defaults + ``edl_action_mapping`` (same as save_edl / service).
    Returns action_type int, or 4 (generic segment) if not found.
    """
    try:
        m = get_edl_label_to_action_map()
        key = normalize_label(label)
        if key in m:
            return m[key]
        log(f"No EDL action mapping found for label '{label}', using default 4")
        return 4
    except Exception as e:
        log(f"Error looking up EDL action for '{label}': {e}")
        return 4


def apply_file_permissions(path, perm_setting):
    """Apply file permissions based on setting (Default/644/666)."""
    if perm_setting == "Default" or not perm_setting:
        return
    try:
        if perm_setting == "644":
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
        elif perm_setting == "666":
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH)
        log(f"Applied permissions {perm_setting} to {path}")
    except Exception as e:
        log(f"Could not set permissions on {path}: {e}")


def parse_edl_line_range(line):
    parts = line.split()
    if len(parts) < 2:
        return None
    try:
        return float(parts[0]), float(parts[1])
    except Exception:
        return None


def trim_overlapping_edl_line(existing_line, new_segment_end, old_end):
    """
    Shorten an EDL line to start at new_segment_end, keeping old_end and action fields.
    Returns None if the overlap leaves no positive-length range (line should be dropped).
    """
    stripped = existing_line.strip()
    parts = stripped.split()
    if len(parts) < 2:
        return None
    try:
        oe = float(old_end)
        trim_start = float(new_segment_end)
    except (TypeError, ValueError):
        return stripped
    if trim_start >= oe:
        return None
    tail = parts[2:] if len(parts) > 2 else ["4"]
    return f"{seconds_to_edl(trim_start)}\t{seconds_to_edl(oe)}\t" + "\t".join(tail)


def sorted_edl_content(content):
    lines = content.splitlines()

    def sort_key(item):
        idx, line = item
        parsed_range = parse_edl_line_range(line.strip())
        if parsed_range:
            return (0, parsed_range[0], idx)
        return (1, 0, idx)

    sorted_lines = [line for _, line in sorted(enumerate(lines), key=sort_key)]
    if not sorted_lines:
        return ""
    return "\n".join(sorted_lines) + "\n"


def save_to_edl(video_path, start, end, label, perm_setting, addon, policy=None, backup_before_write=True):
    """Append segment to EDL file next to video using mapped action type."""
    try:
        policy = normalize_marker_policy(policy)
        edl_path = marker_edl_path(video_path)
        action_type = get_edl_action_for_label(addon, label)
        line = f"{seconds_to_edl(start)}\t{seconds_to_edl(end)}\t{action_type}\n"
        log(f"EDL line: {label} -> action_type {action_type}")

        existing = ""
        existing_lines = []
        if xbmcvfs.exists(edl_path):
            existing = read_vfs_text(edl_path)
            existing_lines = existing.splitlines()

        new_content = line
        if existing_lines and policy != _MARKER_POLICY_REPLACE:
            kept_lines = []
            overlap_found = False
            for existing_line in existing_lines:
                parsed_range = parse_edl_line_range(existing_line.strip())
                if parsed_range and ranges_overlap(start, end, parsed_range[0], parsed_range[1]):
                    overlap_found = True
                    if policy == _MARKER_POLICY_OVERWRITE:
                        log(f"Removing overlapping EDL line before marker save: {existing_line}")
                        continue
                    if policy == _MARKER_POLICY_KEEP_BOTH:
                        trimmed = trim_overlapping_edl_line(existing_line, end, parsed_range[1])
                        if trimmed:
                            log(f"Trimmed overlapping EDL line start to {end}: {trimmed}")
                            kept_lines.append(trimmed)
                        else:
                            log(
                                "Dropping overlapping EDL line (fully covered by new segment)"
                            )
                        continue
                kept_lines.append(existing_line)

            if overlap_found and policy == _MARKER_POLICY_MERGE:
                log("Marked segment overlaps existing EDL entry; merge policy leaves file unchanged")
                return "skipped"

            kept = "\n".join(kept_lines)
            if kept:
                kept += "\n"
            new_content = kept + line
        elif existing and policy == _MARKER_POLICY_REPLACE:
            log("Replacing existing EDL contents with newly marked segment")

        new_content = sorted_edl_content(new_content)

        backup_existing_file(edl_path, backup_before_write)
        write_vfs_text(edl_path, new_content)

        apply_file_permissions(edl_path, perm_setting)
        log(f"Saved segment to EDL: {edl_path}")
        return True
    except Exception as e:
        log(f"Failed to save EDL: {e}")
        return False


def chapter_atom_range(atom):
    start_text = atom.findtext("ChapterTimeStart")
    end_text = atom.findtext("ChapterTimeEnd")
    if not start_text or not end_text:
        return None
    try:
        return hms_to_seconds(start_text), hms_to_seconds(end_text)
    except Exception:
        return None


def sort_chapter_atoms_by_start(edition):
    atoms = list(edition.findall("ChapterAtom"))
    if len(atoms) < 2:
        return

    def sort_key(item):
        idx, atom = item
        parsed_range = chapter_atom_range(atom)
        if parsed_range:
            return (0, parsed_range[0], idx)
        return (1, 0, idx)

    sorted_atoms = [atom for _, atom in sorted(enumerate(atoms), key=sort_key)]
    for atom in atoms:
        edition.remove(atom)
    for atom in sorted_atoms:
        edition.append(atom)


def save_to_chapters_xml(video_path, start, end, label, perm_setting, policy=None, backup_before_write=True):
    """Add segment to chapters.xml next to video."""
    try:
        policy = normalize_marker_policy(policy)
        xml_path = None
        existing_root = None
        candidate_xml_path = marker_chapters_xml_path(video_path)
        if xbmcvfs.exists(candidate_xml_path):
            xml_path = candidate_xml_path
        
        if xml_path and policy != _MARKER_POLICY_REPLACE:
            content = read_vfs_text(xml_path)
            existing_root = ET.fromstring(content)
        elif xml_path and policy == _MARKER_POLICY_REPLACE:
            log("Replacing existing chapters.xml contents with newly marked segment")
            existing_root = ET.Element("Chapters")
        else:
            xml_path = candidate_xml_path
            existing_root = ET.Element("Chapters")
        
        edition = existing_root.find("EditionEntry")
        if edition is None:
            edition = ET.SubElement(existing_root, "EditionEntry")

        if policy != _MARKER_POLICY_REPLACE:
            overlap_found = False
            for existing_atom in list(edition.findall("ChapterAtom")):
                parsed_range = chapter_atom_range(existing_atom)
                if parsed_range and ranges_overlap(start, end, parsed_range[0], parsed_range[1]):
                    overlap_found = True
                    if policy == _MARKER_POLICY_OVERWRITE:
                        log("Removing overlapping XML chapter atom before marker save")
                        edition.remove(existing_atom)
                    elif policy == _MARKER_POLICY_KEEP_BOTH:
                        _, old_end = parsed_range
                        if float(end) >= float(old_end):
                            log(
                                "Removing overlapping XML chapter atom (fully covered by new segment)"
                            )
                            edition.remove(existing_atom)
                        else:
                            st_elem = existing_atom.find("ChapterTimeStart")
                            if st_elem is not None:
                                st_elem.text = seconds_to_hms(end)
                            log(
                                "Trimmed overlapping XML chapter start to end of new segment"
                            )

            if overlap_found and policy == _MARKER_POLICY_MERGE:
                log("Marked segment overlaps existing XML chapter; merge policy leaves file unchanged")
                return "skipped"

        atom = ET.SubElement(edition, "ChapterAtom")
        ET.SubElement(atom, "ChapterTimeStart").text = seconds_to_hms(start)
        ET.SubElement(atom, "ChapterTimeEnd").text = seconds_to_hms(end)
        disp = ET.SubElement(atom, "ChapterDisplay")
        ET.SubElement(disp, "ChapterString").text = label

        sort_chapter_atoms_by_start(edition)

        try:
            ET.indent(existing_root, space="  ")
        except AttributeError:
            pass
        
        xml_str = ET.tostring(existing_root, encoding="unicode")
        xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str

        backup_existing_file(xml_path, backup_before_write)
        write_vfs_text(xml_path, xml_str)

        apply_file_permissions(xml_path, perm_setting)
        log(f"Saved segment to chapters.xml: {xml_path}")
        return True
    except Exception as e:
        log(f"Failed to save chapters.xml: {e}")
        return False


def update_indicator(start_time=None, end_time=None):
    """Update or clear the pending marker indicator (Window 10000 property).

    * ``start_time`` is None: clear the indicator.
    * ``end_time`` is None: show start only (waiting for second press).
    * Both set: show start and end (e.g. while save / type dialogs are open).
    """
    window = xbmcgui.Window(10000)
    if start_time is None:
        window.clearProperty("skippy_marker_indicator")
    elif end_time is None:
        window.setProperty(
            "skippy_marker_indicator",
            f"Start: {format_time(start_time)}",
        )
    else:
        window.setProperty(
            "skippy_marker_indicator",
            f"Start: {format_time(start_time)}  →  End: {format_time(end_time)}",
        )


def main():
    addon = get_addon()
    if not addon:
        log("Could not get addon instance")
        return

    if len(sys.argv) > 1:
        command = (sys.argv[1] or "").strip().lower()
        if command == "discover_button":
            discover_remote_button(addon)
            return
        if command == "install_keymap":
            install_marker_keymap(addon, notify=True)
            return
        if command == "open_segment_editor":
            from segment_editor_session import open_segment_editor

            open_segment_editor()
            return
        if command == "discover_editor_button":
            from segment_editor import discover_editor_remote_button

            discover_editor_remote_button(addon)
            return
        if command == "install_editor_keymap":
            from keymap_utils import install_editor_keymap

            install_editor_keymap(addon, notify=True)
            return

    enabled = addon.getSetting("segment_marker_enabled") == "true"
    if not enabled:
        set_pending_start(None)
        update_indicator(None)
        show_toast(get_localized(addon, 36016))
        log("Segment Marker is disabled in settings")
        return
    
    current_time = get_current_playback_time()
    if current_time is None:
        show_toast(get_localized(addon, 36015))
        log("No video playing")
        return
    
    video_path = get_video_path()
    if not video_path:
        show_toast(get_localized(addon, 36015))
        log("Could not get video path")
        return
    
    pending_start = get_pending_start()
    pending_path = get_pending_path()
    
    show_indicator = addon.getSetting("segment_marker_show_indicator") == "true"
    
    if pending_start is None or pending_path != video_path:
        set_pending_start(current_time)
        toast_msg = f"{get_localized(addon, 36008)}: {format_time(current_time)}"
        show_toast(toast_msg)
        log(f"Start time marked: {current_time} for {video_path}")
        
        if show_indicator:
            update_indicator(current_time)
        else:
            update_indicator(None)
        return
    
    end_time = current_time
    start_time = pending_start
    
    if end_time <= start_time:
        set_pending_start(None)
        update_indicator(None)
        show_toast(
            f"End time must be after start ({format_time(start_time)}). "
            "Pending mark cleared."
        )
        log(f"Invalid end time {end_time} <= start {start_time}; cleared pending mark")
        return
    
    set_pending_start(None)
    if show_indicator:
        update_indicator(start_time, end_time)
    else:
        update_indicator(None)
    
    toast_msg = f"{get_localized(addon, 36009)}: {format_time(end_time)}"
    show_toast(toast_msg, time_ms=1500)
    log(f"End time marked: {end_time}")
    
    xbmc.sleep(500)

    save_format = addon.getSetting("segment_marker_save_format") or "Both"
    existing_policy = addon.getSetting("segment_marker_existing_policy") or _MARKER_POLICY_MERGE
    existing_policy = normalize_marker_policy(existing_policy)
    log(f"Marker save policy setting resolved to: {existing_policy}")
    if existing_policy == _MARKER_POLICY_ASK:
        if marker_selected_sidecars_exist(video_path, save_format):
            overlaps = marker_range_overlaps_existing(video_path, save_format, start_time, end_time)
            chosen_policy = ask_marker_existing_policy(addon, overlaps)
            if not chosen_policy:
                update_indicator(None)
                show_toast(get_localized(addon, 36014))
                log("Marker save policy selection cancelled")
                return
            existing_policy = chosen_policy
        else:
            log("AskEachTime selected but no sidecar exists for save format; skipping save-method picker")
            existing_policy = _MARKER_POLICY_MERGE
    
    label = pick_segment_type(addon)
    if not label:
        update_indicator(None)
        show_toast(get_localized(addon, 36014))
        log("Segment type selection cancelled")
        return
    
    auto_save = addon.getSetting("segment_marker_auto_save") == "true"
    if not auto_save:
        if not confirm_save(addon, start_time, end_time, label):
            update_indicator(None)
            show_toast(get_localized(addon, 36014))
            log("Save cancelled by user")
            return
    
    perm_setting = addon.getSetting("segment_marker_file_permissions") or "Default"
    backup_before_write = addon.getSetting("segment_marker_backup_before_write") == "true"
    
    edl_ok = False
    xml_ok = False
    
    if save_format in ("Both", "EDL"):
        edl_ok = save_to_edl(
            video_path,
            start_time,
            end_time,
            label,
            perm_setting,
            addon,
            policy=existing_policy,
            backup_before_write=backup_before_write,
        )
    
    if save_format in ("Both", "XML"):
        xml_ok = save_to_chapters_xml(
            video_path,
            start_time,
            end_time,
            label,
            perm_setting,
            policy=existing_policy,
            backup_before_write=backup_before_write,
        )

    edl_saved = edl_ok is True
    xml_saved = xml_ok is True
    edl_skipped = edl_ok == "skipped"
    xml_skipped = xml_ok == "skipped"
    
    if save_format == "Both":
        if edl_saved and xml_saved:
            show_toast(f"{get_localized(addon, 36012)}: {label}")
            log(f"Segment saved: {label} [{start_time}-{end_time}]")
        elif (edl_skipped and xml_skipped) or ((edl_skipped or xml_skipped) and not (edl_saved or xml_saved)):
            show_toast("Segment overlaps existing entry; not changed")
            log("Marker save skipped by merge policy because the range overlaps existing entries")
        elif edl_saved or xml_saved:
            partial = "EDL" if edl_saved else "chapters.xml"
            show_toast(f"Partial save ({partial})")
            log(f"Partial save: EDL={edl_ok}, XML={xml_ok}")
        else:
            show_toast(get_localized(addon, 36013))
            log("Failed to save segment to both files")
    elif save_format == "EDL":
        if edl_saved:
            show_toast(f"{get_localized(addon, 36012)}: {label} (EDL)")
            log(f"Segment saved to EDL: {label} [{start_time}-{end_time}]")
        elif edl_skipped:
            show_toast("Segment overlaps existing EDL entry; not changed")
            log("Marker EDL save skipped by merge policy")
        else:
            show_toast(get_localized(addon, 36013))
            log("Failed to save segment to EDL")
    elif save_format == "XML":
        if xml_saved:
            show_toast(f"{get_localized(addon, 36012)}: {label} (XML)")
            log(f"Segment saved to chapters.xml: {label} [{start_time}-{end_time}]")
        elif xml_skipped:
            show_toast("Segment overlaps existing XML chapter; not changed")
            log("Marker XML save skipped by merge policy")
        else:
            show_toast(get_localized(addon, 36013))
            log("Failed to save segment to chapters.xml")

    update_indicator(None)


if __name__ == "__main__":
    main()
