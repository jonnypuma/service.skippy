# -*- coding: utf-8 -*-
"""Open the segment editor dialog (integrated in Skippy)."""
import os

import xbmc
import xbmcgui

from segment_editor_dialog import SegmentEditorDialog
from segment_editor_parser import (
    delete_segment_files,
    parse_chapters,
    parse_edl,
    save_segments,
)
from segment_editor_utils import (
    get_addon,
    log,
    log_always,
    log_error,
    get_video_file,
    set_editor_modal_open,
)

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
        return

    if _editor_active:
        log_always("Editor already open, ignoring request")
        return

    if not video_path:
        video_path = get_video_file()

    if not video_path:
        log_always("No video file available for editing")
        xbmcgui.Dialog().ok("Segment Editor", "No video is currently playing.")
        return

    log_always(f"Opening segment editor for: {os.path.basename(video_path)}")
    _editor_active = True
    set_editor_modal_open(True)

    try:
        segments = None
        try:
            from service import get_initial_segments_for_segment_editor

            segments = get_initial_segments_for_segment_editor(video_path)
        except Exception as exc:
            log_always(f"No service online segment bootstrap ({exc})")

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


def main():
    open_segment_editor()
