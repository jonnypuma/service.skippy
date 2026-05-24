# -*- coding: utf-8 -*-
"""Open the segment editor dialog (integrated in Skippy)."""
import copy
import json
import os

import time

import xbmc
import xbmcgui

from playback_segment_cache import get_parse_cache_snapshot
from remote_segments import paths_refer_to_same_video
from segment_editor_dialog import SegmentEditorDialog
from segment_editor_parser import (
    SegmentItem as EditorSegmentItem,
    delete_segment_files,
    parse_chapters,
    parse_edl,
    save_segments,
)
from segment_editor_utils import (
    EDITOR_LAUNCH_DEBOUNCE_SECONDS,
    EDITOR_LAUNCH_DEBOUNCE_TS,
    EDITOR_TOGGLE_CLOSE_REQUESTED,
    get_addon,
    log,
    log_always,
    log_error,
    get_video_file,
    set_editor_modal_open,
)
from settings_utils import format_segment_label_for_ui


def _clone_playback_segments_for_editor(segments):
    cloned = []
    for seg in segments or []:
        item = copy.copy(seg)
        if hasattr(item, "next_segment_start"):
            item.next_segment_start = None
        if hasattr(item, "next_segment_info"):
            item.next_segment_info = None
        cloned.append(item)
    return cloned


def _get_active_video_player_item():
    try:
        active_result = json.loads(
            xbmc.executeJSONRPC(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "Player.GetActivePlayers",
                    }
                )
            )
        )
        players = active_result.get("result") or []
        video_player = next((p for p in players if p.get("type") == "video"), None)
        if not video_player:
            return None
        pid = video_player.get("playerid")
        item_result = json.loads(
            xbmc.executeJSONRPC(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "Player.GetItem",
                        "params": {
                            "playerid": pid,
                            "properties": ["file", "title", "showtitle", "episode"],
                        },
                    }
                )
            )
        )
        return item_result.get("result", {}).get("item") or None
    except Exception:
        return None


def get_initial_segments_for_segment_editor(video_path):
    """Build editor segments from published playback cache when origin is remote."""
    if not video_path:
        return None
    cache = get_parse_cache_snapshot()
    cache_path = (cache or {}).get("path")
    if not cache or not cache_path:
        log_always("Segment editor: no playback parse cache snapshot")
        return None
    if not paths_refer_to_same_video(cache_path, video_path):
        log_always(
            "Segment editor: cache path differs from playing path "
            "(not using online snapshot) cache=%r play=%r"
            % (cache_path, video_path)
        )
        return None
    if cache.get("segment_origin") != "remote":
        log_always(
            "Segment editor: snapshot segment_origin=%r (need remote) — loading from disk"
            % (cache.get("segment_origin"),)
        )
        return None
    raw_segs = cache.get("segments") or []
    if not raw_segs:
        return None

    item = _get_active_video_player_item()
    file_from_player = (item or {}).get("file")
    if file_from_player and not paths_refer_to_same_video(
        file_from_player, video_path
    ):
        log_always(
            "Segment editor: Player.GetItem file differs from editor path "
            "(not using online cache snapshot) item=%r editor=%r"
            % (file_from_player, video_path)
        )
        return None

    editor_segments = []
    for seg in _clone_playback_segments_for_editor(raw_segs):
        try:
            label_ui = format_segment_label_for_ui(seg.segment_type_label)
            src = getattr(seg, "source", None) or "online"
            editor_segments.append(
                EditorSegmentItem(
                    seg.start_seconds,
                    seg.end_seconds,
                    label_ui,
                    source=src,
                    action_type=seg.action_type,
                )
            )
        except (TypeError, ValueError) as err:
            log_always(f"Segment editor: skip invalid online segment: {err}")
    if editor_segments:
        log_always(
            f"Segment editor: loaded {len(editor_segments)} segment(s) "
            "from playback online cache (per-row source preserved)"
        )
    return editor_segments or None

_editor_active = False


def open_segment_editor(video_path=None):
    global _editor_active
    log_always("open_segment_editor() called")

    addon = get_addon()
    if not addon or addon.getSetting("segment_editor_enabled") != "true":
        log_always("Segment Editor is disabled in settings")
        try:
            xbmcgui.Dialog().notification(
                "Skippy",
                "Segment Editor is disabled in settings",
                time=3000,
                sound=False,
            )
        except Exception:
            pass
        # Undo optimistic skippy_editor_modal_open from overlap auto-launch (service thread).
        set_editor_modal_open(False)
        return

    win_home = None
    try:
        win_home = xbmcgui.Window(10000)
    except Exception:
        win_home = None

    # Second hotkey press while modal is flagged: close the existing editor instead of stacking.
    if win_home is not None and (
        (win_home.getProperty("skippy_editor_modal_open") or "").strip() == "true"
    ):
        win_home.setProperty(EDITOR_TOGGLE_CLOSE_REQUESTED, "1")
        log_always("Segment editor toggle: close requested (modal already open)")
        return

    if _editor_active:
        log_always("Editor already open in this interpreter, ignoring request")
        return

    if not video_path:
        video_path = get_video_file()

    if not video_path:
        log_always("No video file available for editing")
        xbmcgui.Dialog().ok("Segment Editor", "No video is currently playing.")
        set_editor_modal_open(False)
        return

    now = time.time()
    if win_home is not None:
        try:
            prev = float(win_home.getProperty(EDITOR_LAUNCH_DEBOUNCE_TS) or 0)
        except ValueError:
            prev = 0.0
        if prev > 0 and (now - prev) < EDITOR_LAUNCH_DEBOUNCE_SECONDS:
            log_always(
                "Segment editor launch debounced (< %.1fs since last)"
                % (EDITOR_LAUNCH_DEBOUNCE_SECONDS,)
            )
            return
        win_home.setProperty(EDITOR_LAUNCH_DEBOUNCE_TS, str(now))
        try:
            win_home.clearProperty(EDITOR_TOGGLE_CLOSE_REQUESTED)
        except Exception:
            pass

    log_always(f"Opening segment editor for: {os.path.basename(video_path)}")
    _editor_active = True
    set_editor_modal_open(True)

    try:
        segments = get_initial_segments_for_segment_editor(video_path)

        if not segments:
            segments = parse_chapters(video_path)
            if not segments:
                segments = parse_edl(video_path)

        segments = segments or []
        current_time = None
        try:
            player = xbmc.Player()
            if player.isPlayingVideo():
                current_time = player.getTime()
        except Exception:
            pass

        addon = get_addon()
        dialog = SegmentEditorDialog(
            "SegmentEditorDialog.xml",
            addon.getAddonInfo("path"),
            "default",
            video_path=video_path,
            segments=segments or [],
            current_time=current_time,
        )
        try:
            dialog.doModal()
        except Exception as dialog_err:
            log_error(f"Error creating/showing dialog: {dialog_err}")
            import traceback

            log_error(f"Traceback: {traceback.format_exc()}")
            raise

        if dialog.segments_modified:
            log("Segments were modified, saving...")
            if dialog.segments:
                edl_ok, xml_ok = save_segments(video_path, dialog.segments)
                if edl_ok or xml_ok:
                    xbmcgui.Dialog().notification(
                        "Segment Editor",
                        "Segments saved successfully",
                        time=2000,
                    )
                else:
                    xbmcgui.Dialog().ok(
                        "Segment Editor",
                        "Failed to save segments. Check file permissions.",
                    )
            else:
                delete_segment_files(video_path)

        del dialog
    except Exception as e:
        log_error(f"Error opening editor: {e}")
        import traceback

        log_error(f"Traceback: {traceback.format_exc()}")
        xbmcgui.Dialog().ok("Segment Editor", f"Error opening editor: {str(e)}")
    finally:
        _editor_active = False
        set_editor_modal_open(False)
        if win_home is not None:
            try:
                win_home.clearProperty(EDITOR_LAUNCH_DEBOUNCE_TS)
            except Exception:
                pass


def main():
    open_segment_editor()
