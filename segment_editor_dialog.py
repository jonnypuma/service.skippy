"""Segment editor dialog.

Responsibilities:
- Show the list of segments for the current video.
- Let the user add / edit / delete segments and mark start/end times.
- Persist changes via ``segment_editor_parser.save_segments``.

Architectural notes:
- Pause/resume state is driven by a subclassed ``xbmc.Player`` that pushes
  callbacks into the dialog; we no longer poll ``getTime()`` to infer pause.
- The time-label updater runs on a single lightweight thread.
- Edit/Delete sit to the right of the list; their vertical position tracks the
  highlighted row in the **visible viewport** (not ``selected_index * row_height``,
  which breaks once the list scrolls). ``onFocus`` only runs when focus moves
  onto the list, not when moving between list items, so we re-sync after list
  navigation actions (debounced timer so ``getSelectedPosition()`` matches Kodi's
  selection).
"""
import copy
import os
import threading
import time

import xbmc
import xbmcgui

from segment_editor_parser import (
    SegmentItem,
    seconds_to_hms,
    hms_to_seconds,
    save_segments,
    parse_embedded_chapters,
    get_save_format,
    segments_chronological,
    SAVE_FORMAT_BOTH,
)
from segment_editor_utils import (
    EDITOR_TOGGLE_CLOSE_REQUESTED,
    get_addon,
    log,
    log_always,
    log_error,
    set_editor_modal_open,
)
from addon_skin_resolution import init_window_xml_dialog, scale_skin_coord
from settings_utils import get_custom_segment_keyword_labels, normalize_label


def _select_segment_label_from_list(options):
    """
    Skinned list (same as Segment Marker) so every keyword from custom_segment_keywords
    is shown. xbmcgui.Dialog().select() can omit or mishandle items on some platforms.

    Returns:
        int: index of selection (0 = Custom..., -1 = user cancelled the picker)
        None: skinned picker unavailable (caller may use Dialog().select())
    """
    addon = get_addon()
    if not addon:
        return None
    try:
        from segment_marker import SegmentTypePickerDialog
    except Exception as exc:
        log_error(f"Cannot load SegmentTypePickerDialog: {exc}")
        return None

    dialog = None
    try:
        path = addon.getAddonInfo("path")
        dialog = SegmentTypePickerDialog(
            "SegmentMarkerTypePicker.xml",
            path,
            "default",
            title="Select Segment Label",
            subtitle="Choose a label from Segment keywords, or Custom to type your own.",
            footer="Enter/OK selects. Back/Esc cancels.",
            options=options,
        )
        dialog.doModal()
        return getattr(dialog, "selected_index", -1)
    except Exception as exc:
        log_error(f"Skinned segment label picker failed: {exc}")
        return None
    finally:
        try:
            if dialog:
                del dialog
        except Exception:
            pass


def _format_segment_label_list_display(label):
    """Capitalize first character for segment list display only; leaves rest unchanged."""
    if label is None:
        return label
    s = str(label)
    if not s:
        return label
    return s[0].upper() + s[1:]


# Floating list-row action buttons (must match SegmentEditorDialog.xml).
_LIST_ROW_ACTION_IDS = (5037, 5038, 5027, 5028, 5041, 5042, 5043, 5021, 5022)

# All editor push buttons — WindowXML ignores <font>; apply via setLabel in onInit.
_EDITOR_BUTTON_IDS = _LIST_ROW_ACTION_IDS + (
    5031, 5032, 5033, 5011, 5010, 5009, 5019, 5018, 5020,
    5012, 5013, 5014, 5034, 5035, 5036,
    5015, 5029, 5016, 5030, 5017, 5023, 5024, 5025,
    5005, 5002, 5004, 5040, 5026, 5006, 5007,
)


class _EditorPlayerListener(xbmc.Player):
    """xbmc.Player subclass that pushes pause/resume events to the dialog."""

    def __init__(self, dialog):
        super().__init__()
        self._dialog = dialog

    def onAVStarted(self):
        self._dialog._set_pause_state(False)

    def onPlayBackResumed(self):
        self._dialog._set_pause_state(False)

    def onPlayBackPaused(self):
        self._dialog._set_pause_state(True)

    def onPlayBackStopped(self):
        self._dialog._set_pause_state(False)

    def onPlayBackEnded(self):
        self._dialog._set_pause_state(False)


class SegmentEditorDialog(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        try:
            init_window_xml_dialog(super(SegmentEditorDialog, self), args)
        except Exception:
            super().__init__(*args)
        self.video_path = kwargs.get("video_path")
        self.segments = kwargs.get("segments", [])
        self.current_time = kwargs.get("current_time", 0)
        self.segments_modified = False
        self.selected_index = -1
        self.player = xbmc.Player()
        self._player_listener = None
        self._closing = False
        self.pending_start_time = None
        self.pending_end_time = None
        self.is_paused = False
        # List row geometry (must match SegmentEditorDialog.xml list + buttons).
        sc = scale_skin_coord
        self._list_top = sc(110)
        self._list_item_height = sc(50)
        self._list_height = sc(290)
        self._start_curr_btn_left = sc(470)
        self._end_curr_btn_left = sc(581)
        self._snap_start_btn_left = sc(676)
        self._snap_end_btn_left = sc(773)
        self._merge_btn_left = sc(873)
        self._split_btn_left = sc(942)
        self._fix_btn_left = sc(990)
        self._edit_btn_left = sc(1075)
        self._delete_btn_left = sc(1127)
        self._edit_delete_btn_height = sc(30)
        self._selection_sync_timer = None
        self._indicator_win_home = None
        self._undo_stack = []
        self._undo_stack_max = 20
        # font12 via setLabel — XML <font> is ignored on WindowXML buttons; smaller at 1080p.
        self._editor_btn_font = "font12"

        try:
            addon = get_addon()
            self.icon_path = addon.getAddonInfo("icon") or None
        except Exception:
            self.icon_path = None

        log(f"SegmentEditorDialog initialized with {len(self.segments)} segments")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def onInit(self):
        try:
            log_always("onInit called")

            # Reinforce IPC flag once the WindowXML exists (helps RunScript callers that
            # check modal state vs. Kodi's fullscreen dialog stacking).
            try:
                set_editor_modal_open(True)
            except Exception:
                pass

            try:
                xbmcgui.Window(10000).clearProperty(EDITOR_TOGGLE_CLOSE_REQUESTED)
            except Exception:
                pass

            try:
                addon = get_addon()
                enable_overlay = addon.getSetting("segment_editor_fullscreen_overlay") == "true"
                self.setProperty("EnableFullscreenOverlay", "true" if enable_overlay else "false")
                log(f"Full-screen overlay setting: {enable_overlay}")
                enable_upl = addon.getSetting("online_upload_enabled") == "true"
                self.setProperty("EnableOnlineUpload", "true" if enable_upl else "false")
                uc = self.getControl(5026)
                if uc:
                    uc.setVisible(enable_upl)
                    try:
                        uc.setLabel(addon.getLocalizedString(39018))
                    except Exception:
                        uc.setLabel("Upload")
                log(f"Online upload button visible: {enable_upl}")
            except Exception as e:
                log(f"Error reading editor display / upload settings: {e}")
                self.setProperty("EnableFullscreenOverlay", "false")
                self.setProperty("EnableOnlineUpload", "false")

            self.list_control = self.getControl(5000)
            if not self.list_control:
                log_always("List control (5000) not found - this is critical!")
            else:
                # Offer to import embedded chapters if the video has none set.
                if not self.segments and self.video_path:
                    self._maybe_import_embedded_chapters()
                self.refresh_list()

            self._apply_editor_button_fonts()
            self._update_undo_button()

            try:
                self.is_paused = self._detect_initial_pause_state()
                self._update_pause_button_label()
                log(f"Initial pause state: {self.is_paused}")
            except Exception as e:
                log(f"Error initializing pause button: {e}")
                self.is_paused = False

            try:
                self._player_listener = _EditorPlayerListener(self)
                log("Registered xbmc.Player listener for pause/resume events")
            except Exception as e:
                log(f"Could not register player listener: {e}")
                self._player_listener = None

            try:
                self.setFocusId(5018)
                log_always("Set initial focus to Pause/Resume button (5018)")
            except Exception:
                log_always("Could not set initial focus to Pause/Resume button")

            threading.Thread(target=self._update_time_display, daemon=True).start()

            log("Dialog onInit completed")
        except Exception as e:
            log_always(f"Error in onInit: {e}")
            import traceback
            log_always(f"Traceback: {traceback.format_exc()}")

    def close(self):
        self._closing = True
        t = getattr(self, "_selection_sync_timer", None)
        if t:
            try:
                t.cancel()
            except Exception:
                pass
            self._selection_sync_timer = None
        # Drop the player listener so Kodi stops delivering events.
        self._player_listener = None
        try:
            super().close()
        finally:
            try:
                set_editor_modal_open(False)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Pause / time display
    # ------------------------------------------------------------------

    def _detect_initial_pause_state(self):
        """Sample getTime() twice to infer initial pause state (cold start)."""
        try:
            if not self.player.isPlayingVideo():
                return False
            t1 = self.player.getTime()
            time.sleep(0.15)
            t2 = self.player.getTime()
            return abs(t2 - t1) < 0.05
        except Exception as e:
            log(f"Error detecting initial pause state: {e}")
            return False

    def _set_pause_state(self, paused):
        if self.is_paused == paused:
            return
        self.is_paused = paused
        log(f"Pause state changed via Player callback: paused={paused}")
        self._update_pause_button_label()

    def _set_button_label_font(self, btn, label=None):
        """Apply editor button font/colors; WindowXML ignores skin <font> tags."""
        if not btn:
            return
        font = self._editor_btn_font
        if label is None:
            label = btn.getLabel() or ""
        try:
            btn.setLabel(
                label,
                font,
                "0xFFC0C0C0",
                "0xFF808080",
                "0xFF000000",
                "0xFFFFFFFF",
            )
        except TypeError:
            try:
                btn.setLabel(label, font)
            except Exception:
                pass

    def _apply_editor_button_fonts(self):
        """Apply font12 to every editor button (list row + toolbar rows)."""
        for cid in _EDITOR_BUTTON_IDS:
            try:
                btn = self.getControl(cid)
                if btn:
                    self._set_button_label_font(btn)
            except Exception:
                pass

    def _apply_list_row_button_fonts(self):
        """Re-apply fonts on list-row action buttons after label changes."""
        for cid in _LIST_ROW_ACTION_IDS:
            try:
                btn = self.getControl(cid)
                if btn:
                    self._set_button_label_font(btn)
            except Exception:
                pass

    def _update_pause_button_label(self):
        try:
            pause_button = self.getControl(5018)
            if pause_button:
                self._set_button_label_font(
                    pause_button,
                    "Pause" if not self.is_paused else "Resume",
                )
        except Exception:
            pass

    def _update_time_display(self):
        """Update the current-time label ~2 Hz. Pause state comes via callbacks."""
        while not self._closing:
            try:
                win = getattr(self, "_indicator_win_home", None)
                if win is None:
                    try:
                        win = xbmcgui.Window(10000)
                        self._indicator_win_home = win
                    except Exception:
                        win = None
                if win is not None and (
                    (win.getProperty(EDITOR_TOGGLE_CLOSE_REQUESTED) or "").strip()
                ):
                    try:
                        win.clearProperty(EDITOR_TOGGLE_CLOSE_REQUESTED)
                    except Exception:
                        pass
                    try:
                        if self.check_unsaved_changes():
                            self.close()
                    except Exception as err:
                        log_error("Segment editor toggle close: %s" % err)
                        try:
                            self.close()
                        except Exception:
                            pass
                    continue
            except Exception:
                pass
            try:
                if self.player.isPlayingVideo():
                    current = self.player.getTime()
                    self.current_time = current
                    hms = seconds_to_hms(current)

                    try:
                        time_label = self.getControl(5001)
                        if time_label:
                            pause_indicator = " [PAUSED]" if self.is_paused else ""
                            time_label.setLabel(f"Current Time: {hms}{pause_indicator}")
                    except Exception:
                        pass

                    status_text = ""
                    if self.pending_start_time is not None:
                        status_text = f"Start: {seconds_to_hms(self.pending_start_time)}"
                    if self.pending_end_time is not None:
                        if status_text:
                            status_text += f" | End: {seconds_to_hms(self.pending_end_time)}"
                        else:
                            status_text = f"End: {seconds_to_hms(self.pending_end_time)}"
                    if (self.pending_start_time is not None
                            and self.pending_end_time is not None
                            and self.pending_end_time <= self.pending_start_time):
                        status_text += " [INVALID: End must be after Start]"

                    try:
                        status_label = self.getControl(5008)
                        if status_label:
                            status_label.setLabel(status_text)
                    except Exception:
                        pass
            except Exception:
                pass

            time.sleep(0.5)

    # ------------------------------------------------------------------
    # Embedded chapter import
    # ------------------------------------------------------------------

    def _maybe_import_embedded_chapters(self):
        try:
            should_check = xbmcgui.Dialog().yesno(
                "Segment Editor",
                "No sidecar segment file was found.\n\n"
                "Check this video for embedded Matroska chapters? "
                "This may take a few seconds.",
                yeslabel="Check",
                nolabel="Skip",
            )
        except Exception as err:
            log(f"Embedded chapter preflight prompt failed: {err}")
            return

        if not should_check:
            log("User skipped embedded chapter check")
            return

        try:
            embedded = parse_embedded_chapters(self.video_path, timeout=3)
        except Exception as err:
            log(f"Embedded chapter probe failed: {err}")
            return

        if not embedded:
            xbmcgui.Dialog().notification(
                "Segment Editor",
                "No embedded chapters found",
                icon=self.icon_path,
                time=2000,
            )
            return

        try:
            proceed = xbmcgui.Dialog().yesno(
                "Segment Editor",
                f"This video contains {len(embedded)} embedded chapter(s).\n\n"
                "Import them as segments?",
                yeslabel="Import",
                nolabel="Skip",
            )
        except Exception as err:
            log(f"Embedded chapter prompt failed: {err}")
            return

        if not proceed:
            log("User skipped embedded chapter import")
            return

        self._push_undo()
        self.segments = embedded
        self.segments_modified = True
        log_always(f"Imported {len(embedded)} embedded chapter(s) as segments")

    # ------------------------------------------------------------------
    # List rendering
    # ------------------------------------------------------------------

    def refresh_list(self):
        try:
            if not hasattr(self, 'list_control') or not self.list_control:
                log("List control not available, skipping refresh")
                return

            prev_segment = None
            if 0 <= self.selected_index < len(self.segments):
                prev_segment = self.segments[self.selected_index]

            self.segments = segments_chronological(self.segments)

            nested_indices, overlapping_indices = self._compute_segment_overlap_sets()

            items = []
            n = len(self.segments)
            for i, seg in enumerate(self.segments):
                start_hms = seconds_to_hms(seg.start_seconds)
                end_hms = seconds_to_hms(seg.end_seconds)
                duration = seg.get_duration()

                label = seg.raw_label if hasattr(seg, 'raw_label') else seg.segment_type_label
                list_label = _format_segment_label_list_display(label)
                segment_num = i + 1
                is_nested = i in nested_indices
                is_overlapping = i in overlapping_indices

                line1 = f"Segment {segment_num} - {list_label} - {start_hms} to {end_hms}"
                line2 = f"Duration: {duration:.1f}s | Source: {seg.source}"
                if is_nested:
                    line2 += " | Nested"
                elif is_overlapping:
                    line2 += " | Overlapping"

                item = xbmcgui.ListItem(line1, line2)
                item.setProperty("index", str(i))
                item.setProperty("start", str(seg.start_seconds))
                item.setProperty("end", str(seg.end_seconds))
                item.setProperty("label", list_label)
                item.setProperty("is_nested", "true" if is_nested else "false")
                item.setProperty("is_overlapping", "true" if is_overlapping else "false")
                if is_nested:
                    item.setProperty("segment_type", "nested")
                elif is_overlapping:
                    item.setProperty("segment_type", "overlapping")
                else:
                    item.setProperty("segment_type", "normal")
                item.setProperty("segment_num", str(segment_num))
                item.setProperty("start_hms", start_hms)
                item.setProperty("end_hms", end_hms)
                items.append(item)

            self.list_control.reset()
            self.list_control.addItems(items)

            try:
                has_segments = len(self.segments) > 0
                self.setProperty("HasSegments", "true" if has_segments else "false")

                for cid in _LIST_ROW_ACTION_IDS:
                    try:
                        btn = self.getControl(cid)
                        if btn:
                            btn.setVisible(has_segments)
                            btn.setEnabled(has_segments)
                    except Exception:
                        pass
            except Exception:
                pass

            if items:
                new_idx = 0
                if prev_segment is not None:
                    try:
                        new_idx = self.segments.index(prev_segment)
                    except ValueError:
                        new_idx = 0
                self.list_control.selectItem(new_idx)
                self.selected_index = new_idx
            else:
                self.selected_index = -1

            self._update_edit_delete_positions()

            log(f"List refreshed with {len(items)} items")
        except Exception as e:
            log_error(f"Error refreshing list: {e}")

    # ------------------------------------------------------------------
    # Input handling
    # ------------------------------------------------------------------

    def onClick(self, controlId):
        log(f"onClick controlId={controlId}")
        try:
            if not self.player.isPlayingVideo():
                log("Video is not playing, some actions may not work")
        except Exception:
            log("Could not check player state")

        handlers = {
            5002: self.add_segment,
            5004: self.delete_all_segments,
            5005: self.add_at_current_time,
            5006: self.save_current_segments,
            5007: self._on_exit_clicked,
            5026: self.upload_segments_online,
            5009: lambda: self.seek_relative(-5),
            5010: lambda: self.seek_relative(-10),
            5011: lambda: self.seek_relative(-30),
            5012: lambda: self.seek_relative(5),
            5013: lambda: self.seek_relative(10),
            5014: lambda: self.seek_relative(30),
            5015: self.set_as_start,
            5016: self.set_as_end,
            5017: self.add_with_marked_times,
            5018: self.toggle_pause,
            5019: lambda: self.seek_relative(-1),
            5020: lambda: self.seek_relative(1),
            5029: self.set_pending_to_sof,
            5030: self.set_pending_to_eof,
            5031: lambda: self.seek_relative(-600),
            5032: lambda: self.seek_relative(-300),
            5033: lambda: self.seek_relative(-60),
            5034: lambda: self.seek_relative(60),
            5035: lambda: self.seek_relative(300),
            5036: lambda: self.seek_relative(600),
            5027: self.snap_segment_start,
            5028: self.snap_segment_end,
            5037: self.set_segment_start_to_current,
            5038: self.set_segment_end_to_current,
            5021: self.edit_segment,
            5022: self.delete_segment,
            5041: self.show_merge_picker,
            5042: self.split_at_playhead,
            5043: self.fix_overlap_selected,
            5023: self.start_at_end_of_segment,
            5024: self.end_at_start_of_segment,
            5025: self.jump_to_time,
            5040: self.undo_last_change,
            5000: self.jump_to_segment_start,  # Select on list
        }

        handler = handlers.get(controlId)
        if handler:
            handler()
        else:
            log(f"Unknown controlId clicked: {controlId}")

    def _on_exit_clicked(self):
        if self.check_unsaved_changes():
            self.close()

    def onAction(self, action):
        action_id = action.getId()
        focused = self.getFocusId()

        # ESC / Back
        if action_id in (10, 92):
            if self.check_unsaved_changes():
                self.close()
            return

        # Don't let Left/Right seek from the list - let XML handle navigation.
        if action_id in (1, 2):
            return

        # List: selection changes without a new onFocus (same control id 5000).
        if focused == 5000:
            nav_actions = (
                getattr(xbmcgui, "ACTION_MOVE_UP", 3),
                getattr(xbmcgui, "ACTION_MOVE_DOWN", 4),
                getattr(xbmcgui, "ACTION_PAGE_UP", 5),
                getattr(xbmcgui, "ACTION_PAGE_DOWN", 6),
            )
            if action_id in nav_actions:
                self._schedule_sync_list_selection()

        # Keyboard shortcuts (only when list is focused).
        if focused == 5000:
            if action_id == 11:  # Space
                self.toggle_pause()
                return
            if action_id in (115, 83, 19):  # S
                self.set_as_start()
                return
            if action_id in (101, 69, 18):  # E
                self.set_as_end()
                return
            if action_id in (100, 68, 20):  # D
                self.delete_segment()
                return

    def onFocus(self, controlId):
        # Track selected index when the list is focused. Kodi fires onFocus when
        # focus moves onto this control, not when moving between list items.
        log(f"Focus -> {controlId}")
        if controlId == 5000:
            try:
                selected = self.list_control.getSelectedPosition()
                if 0 <= selected < len(self.segments):
                    self.selected_index = selected
                self._update_edit_delete_positions()
            except Exception:
                pass

    def _schedule_sync_list_selection(self):
        """After list navigation, Kodi updates selection after this action; sync on a timer."""
        prev_timer = getattr(self, "_selection_sync_timer", None)
        if prev_timer is not None:
            try:
                prev_timer.cancel()
            except Exception:
                pass
            self._selection_sync_timer = None

        def _run():
            self._selection_sync_timer = None
            try:
                if self._closing or self.getFocusId() != 5000:
                    return
                self._refresh_selected_index()
                self._update_edit_delete_positions()
            except Exception:
                pass

        self._selection_sync_timer = threading.Timer(0.05, _run)
        self._selection_sync_timer.daemon = True
        self._selection_sync_timer.start()

    def _visible_list_rows(self) -> int:
        """How many full list rows fit in control 5000 (XML height / itemlayout height)."""
        return max(1, self._list_height // self._list_item_height)

    def _first_visible_list_index(self, selected: int, n_items: int) -> int:
        """
        First list index visible at the top of the scrolled viewport.

        Kodi scrolls so the focused row stays in view; for the default list
        behavior (cursor moves down until it hits the bottom visible row, then
        the window scrolls), this matches ``max(0, selected - rows + 1)`` capped
        so the last page aligns when near the end of the list.
        """
        if n_items <= 0:
            return 0
        rows = self._visible_list_rows()
        if n_items <= rows:
            return 0
        ideal_first = max(0, selected - rows + 1)
        max_first = n_items - rows
        return min(ideal_first, max_first)

    def _get_playback_duration_seconds(self) -> float:
        """Return total video duration when playing, or 0 if unavailable."""
        try:
            if self.player.isPlayingVideo():
                t = self.player.getTotalTime()
                if t is not None and float(t) > 0:
                    return float(t)
        except Exception:
            pass
        return 0.0

    @staticmethod
    def _segment_display_label(seg):
        if hasattr(seg, "raw_label") and seg.raw_label:
            return seg.raw_label
        return seg.segment_type_label or "segment"

    def _segments_same_label(self, seg_a, seg_b):
        return normalize_label(self._segment_display_label(seg_a)) == normalize_label(
            self._segment_display_label(seg_b)
        )

    def _compute_segment_overlap_sets(self, segments=None):
        """Return (nested_indices, overlapping_indices) for segment list overlap UI."""
        if segments is None:
            segments = self.segments
        n = len(segments)
        nested_indices = set()
        for i in range(n):
            seg = segments[i]
            for j in range(n):
                if i == j:
                    continue
                other = segments[j]
                if (other.start_seconds <= seg.start_seconds
                        and seg.end_seconds <= other.end_seconds):
                    nested_indices.add(i)
                    break

        overlapping_indices = set()
        for i in range(n):
            if i in nested_indices:
                continue
            seg = segments[i]
            for j in range(n):
                if i == j or j in nested_indices:
                    continue
                other = segments[j]
                if (seg.start_seconds < other.end_seconds
                        and other.start_seconds < seg.end_seconds):
                    seg_nested_in_other = (
                        other.start_seconds <= seg.start_seconds
                        and seg.end_seconds <= other.end_seconds
                    )
                    other_nested_in_seg = (
                        seg.start_seconds <= other.start_seconds
                        and other.end_seconds <= seg.end_seconds
                    )
                    if not seg_nested_in_other and not other_nested_in_seg:
                        overlapping_indices.add(i)
                        break
        return nested_indices, overlapping_indices

    def _snapshot_segments_for_undo(self):
        return {
            "segments": copy.deepcopy(self.segments),
            "selected_index": self.selected_index,
        }

    def _push_undo(self):
        self._undo_stack.append(self._snapshot_segments_for_undo())
        if len(self._undo_stack) > self._undo_stack_max:
            self._undo_stack.pop(0)
        self._update_undo_button()

    def _update_undo_button(self):
        try:
            undo_btn = self.getControl(5040)
            if undo_btn:
                undo_btn.setEnabled(bool(self._undo_stack))
        except Exception:
            pass

    def undo_last_change(self):
        if not self._undo_stack:
            return
        state = self._undo_stack.pop()
        self.segments = state["segments"]
        self.selected_index = state["selected_index"]
        self.segments_modified = True
        self.refresh_list()
        self._update_undo_button()
        log("Undo restored previous segment list state")

    def show_merge_picker(self):
        """Merge with previous or next segment (list-row Merge button)."""
        try:
            from skippy_editor_modal_skin import show_editor_list_pick
        except Exception as exc:
            log_error(f"show_editor_list_pick import failed: {exc}")
            return

        self._refresh_selected_index()
        options = [
            "Merge with previous segment",
            "Merge with next segment",
        ]
        try:
            picked = show_editor_list_pick("Merge segment", options)
        except Exception:
            try:
                picked = xbmcgui.Dialog().select("Merge segment", options)
            except Exception as exc:
                log_error(f"Merge picker failed: {exc}")
                return
        if picked < 0:
            return
        if picked == 0:
            self.merge_with_previous_segment()
        elif picked == 1:
            self.merge_with_next_segment()

    def merge_with_previous_segment(self):
        self._refresh_selected_index()
        idx = self.selected_index
        if not self.segments:
            xbmcgui.Dialog().ok("Segment Editor", "No segments available.")
            return
        if idx <= 0:
            xbmcgui.Dialog().ok(
                "Segment Editor",
                "Cannot merge with previous segment — there is no prior segment.",
            )
            return
        self._merge_adjacent_segments(idx - 1, idx)

    def merge_with_next_segment(self):
        self._refresh_selected_index()
        idx = self.selected_index
        if not self.segments:
            xbmcgui.Dialog().ok("Segment Editor", "No segments available.")
            return
        if idx < 0 or idx >= len(self.segments) - 1:
            xbmcgui.Dialog().ok(
                "Segment Editor",
                "Cannot merge with next segment — there is no following segment.",
            )
            return
        self._merge_adjacent_segments(idx, idx + 1)

    def _merge_adjacent_segments(self, idx_a, idx_b):
        if idx_a > idx_b:
            idx_a, idx_b = idx_b, idx_a
        if idx_b != idx_a + 1:
            log_error(f"Merge rejected: indices {idx_a} and {idx_b} are not adjacent")
            return
        seg_a = self.segments[idx_a]
        seg_b = self.segments[idx_b]
        new_start = min(seg_a.start_seconds, seg_b.start_seconds)
        new_end = max(seg_a.end_seconds, seg_b.end_seconds)

        if self._segments_same_label(seg_a, seg_b):
            label = self._segment_display_label(seg_a)
            action_type = seg_a.action_type
        else:
            default = self._segment_display_label(
                self.segments[self.selected_index]
            )
            label = self.get_label_from_user(default=default)
            if label is None:
                return
            action_type = None

        source = seg_a.source
        try:
            merged = SegmentItem(
                new_start, new_end, label, source=source, action_type=action_type
            )
        except ValueError as exc:
            xbmcgui.Dialog().ok("Segment Editor", f"Cannot merge segments: {exc}")
            return

        self._push_undo()
        self.segments[idx_a] = merged
        del self.segments[idx_b]
        self.selected_index = idx_a
        self.segments_modified = True
        self.refresh_list()
        log(f"Merged segments at indices {idx_a}+{idx_b} -> {merged}")

    def split_at_playhead(self):
        self._refresh_selected_index()
        if not self.segments or self.selected_index < 0 or self.selected_index >= len(
            self.segments
        ):
            xbmcgui.Dialog().ok("Segment Editor", "Please select a segment first.")
            return
        if not self.player.isPlayingVideo():
            xbmcgui.Dialog().ok(
                "Segment Editor",
                "Cannot split — video is not playing.",
            )
            return
        idx = self.selected_index
        seg = self.segments[idx]
        split_at = float(self.player.getTime())
        if split_at <= seg.start_seconds or split_at >= seg.end_seconds:
            xbmcgui.Dialog().ok(
                "Segment Editor",
                "Playhead must be strictly inside the selected segment.\n\n"
                f"Segment: {seconds_to_hms(seg.start_seconds)} to "
                f"{seconds_to_hms(seg.end_seconds)}\n"
                f"Playhead: {seconds_to_hms(split_at)}",
            )
            return

        label = self._segment_display_label(seg)
        source = seg.source
        action_type = seg.action_type
        try:
            first = SegmentItem(
                seg.start_seconds,
                split_at,
                label,
                source=source,
                action_type=action_type,
            )
            second = SegmentItem(
                split_at,
                seg.end_seconds,
                label,
                source=source,
                action_type=action_type,
            )
        except ValueError as exc:
            xbmcgui.Dialog().ok("Segment Editor", f"Cannot split segment: {exc}")
            return

        self._push_undo()
        self.segments[idx] = first
        self.segments.insert(idx + 1, second)
        self.selected_index = idx + 1
        self.segments_modified = True
        self.refresh_list()
        log(
            f"Split segment {idx} at {split_at:.3f}s into "
            f"[{first.start_seconds:.3f}-{first.end_seconds:.3f}] and "
            f"[{second.start_seconds:.3f}-{second.end_seconds:.3f}]"
        )

    def fix_overlap_selected(self):
        self._refresh_selected_index()
        if not self.segments or self.selected_index < 0 or self.selected_index >= len(
            self.segments
        ):
            xbmcgui.Dialog().ok("Segment Editor", "Please select a segment first.")
            return
        idx = self.selected_index
        nested_indices, overlapping_indices = self._compute_segment_overlap_sets()
        if idx in nested_indices:
            xbmcgui.Dialog().ok(
                "Segment Editor",
                "Fix overlap does not apply to nested segments.\n"
                "Use merge or manual edit instead.",
            )
            return
        if idx not in overlapping_indices:
            xbmcgui.Dialog().ok(
                "Segment Editor",
                "The selected segment is not flagged as overlapping.",
            )
            return

        seg = self.segments[idx]
        new_start = seg.start_seconds
        new_end = seg.end_seconds
        if idx > 0:
            prev = self.segments[idx - 1]
            if new_start < prev.end_seconds:
                candidate = float(prev.end_seconds)
                if candidate < new_end:
                    new_start = candidate
        if idx < len(self.segments) - 1:
            nxt = self.segments[idx + 1]
            if new_end > nxt.start_seconds:
                candidate = float(nxt.start_seconds)
                if candidate > new_start:
                    new_end = candidate

        if new_start == seg.start_seconds and new_end == seg.end_seconds:
            xbmcgui.Dialog().ok(
                "Segment Editor",
                "Could not fix overlap automatically for this segment.",
            )
            return
        if new_end <= new_start:
            xbmcgui.Dialog().ok(
                "Segment Editor",
                "Fix overlap would remove the segment entirely.\n"
                "Use merge or delete instead.",
            )
            return

        self._push_undo()
        seg.start_seconds = new_start
        seg.end_seconds = new_end
        self.segments_modified = True
        self.refresh_list()
        log(
            f"Fixed overlap on segment {idx}: "
            f"{seconds_to_hms(new_start)} to {seconds_to_hms(new_end)}"
        )

    def _update_edit_delete_positions(self):
        """Align list-row action buttons with the highlighted list row (matches skin layout)."""
        try:
            if (
                not hasattr(self, "list_control")
                or not self.list_control
                or not self.segments
            ):
                return
            selected = self.list_control.getSelectedPosition()
            if selected < 0:
                selected = 0
            n = len(self.segments)
            if selected >= n:
                selected = max(0, n - 1)

            first_visible = self._first_visible_list_index(selected, n)
            row_in_view = selected - first_visible
            row_top = (
                self._list_top
                + row_in_view * self._list_item_height
                + (self._list_item_height - self._edit_delete_btn_height) // 2
            )
            max_top = self._list_top + self._list_height - self._edit_delete_btn_height
            row_top = max(self._list_top, min(row_top, max_top))

            btn_positions = (
                (5037, self._start_curr_btn_left),
                (5038, self._end_curr_btn_left),
                (5027, self._snap_start_btn_left),
                (5028, self._snap_end_btn_left),
                (5041, self._merge_btn_left),
                (5042, self._split_btn_left),
                (5043, self._fix_btn_left),
                (5021, self._edit_btn_left),
                (5022, self._delete_btn_left),
            )
            for cid, left in btn_positions:
                try:
                    btn = self.getControl(cid)
                    if btn:
                        btn.setPosition(left, row_top)
                except Exception:
                    pass
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Segment operations
    # ------------------------------------------------------------------

    def _refresh_selected_index(self):
        """Pull the current list selection into ``self.selected_index``."""
        try:
            selected = self.list_control.getSelectedPosition()
            if selected < 0:
                selected = 0
            if selected >= len(self.segments):
                selected = max(0, len(self.segments) - 1)
            self.selected_index = selected
        except Exception:
            pass

    def add_at_current_time(self):
        if not self.current_time or self.current_time <= 0:
            xbmcgui.Dialog().ok("Segment Editor", "No current playback time available.")
            return

        duration_str = xbmcgui.Dialog().input(
            "Segment Duration (seconds)",
            defaultt="30",
        )
        if not duration_str:
            return

        try:
            duration = float(duration_str)
            if duration <= 0:
                xbmcgui.Dialog().ok("Segment Editor", "Duration must be greater than zero.")
                return
            start = self.current_time
            end = start + duration

            label = self.get_label_from_user()
            if label is None:
                return

            source = "edl"
            if self.segments and self.segments[0].source == "xml":
                source = "xml"

            new_seg = SegmentItem(start, end, label, source=source)
            self._push_undo()
            self.segments.append(new_seg)
            self.segments_modified = True
            self.refresh_list()
            log(f"Added segment at current time: {new_seg}")
        except ValueError:
            xbmcgui.Dialog().ok("Segment Editor", "Invalid duration value.")

    def add_segment(self):
        """Add a new segment via manual start/end entry."""
        if self.pending_start_time is not None and self.pending_end_time is not None:
            if xbmcgui.Dialog().yesno(
                "Segment Editor",
                "You have marked start and end times.\n\n"
                "Use 'Add with Marked Times' instead?",
            ):
                self.add_with_marked_times()
                return

        default_start = "0"
        if self.pending_start_time is not None:
            default_start = seconds_to_hms(self.pending_start_time)
        elif self.current_time > 0:
            default_start = seconds_to_hms(self.current_time)

        start_str = xbmcgui.Dialog().input(
            "Start Time (HH:MM:SS.mmm or seconds)",
            defaultt=default_start,
        )
        if not start_str:
            return

        default_end = "30"
        if self.pending_end_time is not None:
            default_end = seconds_to_hms(self.pending_end_time)
        elif self.current_time > 0:
            default_end = seconds_to_hms(self.current_time + 30)

        end_str = xbmcgui.Dialog().input(
            "End Time (HH:MM:SS.mmm or seconds)",
            defaultt=default_end,
        )
        if not end_str:
            return

        label = self.get_label_from_user()
        if label is None:
            return

        try:
            start = hms_to_seconds(start_str)
            end = hms_to_seconds(end_str)

            if end <= start:
                xbmcgui.Dialog().ok("Segment Editor", "End time must be after start time.")
                return

            source = "edl"
            if self.segments and self.segments[0].source == "xml":
                source = "xml"

            new_seg = SegmentItem(start, end, label, source=source)
            self._push_undo()
            self.segments.append(new_seg)
            self.segments_modified = True
            self.refresh_list()
            log(f"Added segment: {new_seg}")
        except ValueError as e:
            xbmcgui.Dialog().ok("Segment Editor", f"Invalid input: {e}")

    def edit_segment(self):
        self._refresh_selected_index()
        if self.selected_index < 0 or self.selected_index >= len(self.segments):
            xbmcgui.Dialog().ok("Segment Editor", "Please select a segment to edit.")
            return

        seg = self.segments[self.selected_index]

        if self.pending_start_time is not None and self.pending_end_time is not None:
            if xbmcgui.Dialog().yesno(
                "Segment Editor",
                "You have marked start and end times.\n\n"
                "Use marked times for this segment?",
            ):
                if self.pending_end_time > self.pending_start_time:
                    self._push_undo()
                    seg.start_seconds = self.pending_start_time
                    seg.end_seconds = self.pending_end_time
                    self.pending_start_time = None
                    self.pending_end_time = None
                    self.segments_modified = True
                    self.refresh_list()
                    log(f"Edited segment with marked times: {seg}")
                    return
                xbmcgui.Dialog().ok("Segment Editor", "End time must be after start time.")
                return

        default_start = seconds_to_hms(seg.start_seconds)
        if self.pending_start_time is not None:
            default_start = seconds_to_hms(self.pending_start_time)
        start_str = xbmcgui.Dialog().input(
            "Start Time (HH:MM:SS.mmm or seconds)",
            defaultt=default_start,
        )
        if not start_str:
            return

        default_end = seconds_to_hms(seg.end_seconds)
        if self.pending_end_time is not None:
            default_end = seconds_to_hms(self.pending_end_time)
        end_str = xbmcgui.Dialog().input(
            "End Time (HH:MM:SS.mmm or seconds)",
            defaultt=default_end,
        )
        if not end_str:
            return

        default_label = seg.raw_label if hasattr(seg, 'raw_label') else seg.segment_type_label
        label = self.get_label_from_user(default=default_label)
        if label is None:
            return

        try:
            start = hms_to_seconds(start_str)
            end = hms_to_seconds(end_str)

            if end <= start:
                xbmcgui.Dialog().ok("Segment Editor", "End time must be after start time.")
                return

            self._push_undo()
            seg.start_seconds = start
            seg.end_seconds = end
            old_label = seg.segment_type_label
            seg.raw_label = label.strip()
            seg.segment_type_label = normalize_label(label)
            # Invalidate stale action_type when the label is changed so that
            # the EDL save-path falls back to the mapping (or default 4),
            # rather than silently reusing the old numeric action.
            if seg.segment_type_label != old_label:
                seg.action_type = None
            self.segments_modified = True
            self.refresh_list()
            log(f"Edited segment: {seg}")
        except ValueError as e:
            xbmcgui.Dialog().ok("Segment Editor", f"Invalid input: {e}")

    def snap_segment_start(self):
        """Move segment start to 0 (first) or previous segment's end (timeline order)."""
        self._refresh_selected_index()
        if not self.segments or self.selected_index < 0 or self.selected_index >= len(
            self.segments
        ):
            xbmcgui.Dialog().ok("Segment Editor", "Please select a segment first.")
            return
        idx = self.selected_index
        seg = self.segments[idx]
        if idx == 0:
            new_start = 0.0
        else:
            new_start = float(self.segments[idx - 1].end_seconds)
        if new_start >= seg.end_seconds:
            xbmcgui.Dialog().ok(
                "Segment Editor",
                "Cannot snap: start would not be before the segment end time.\n\n"
                f"End: {seconds_to_hms(seg.end_seconds)}\n"
                f"Snap target: {seconds_to_hms(new_start)}",
            )
            return
        self._push_undo()
        seg.start_seconds = new_start
        self.segments_modified = True
        self.refresh_list()
        log(f"Snapped segment start (index {idx}) to {new_start:.3f}s")

    def snap_segment_end(self):
        """Move segment end to next segment's start (timeline order) or video duration (last)."""
        self._refresh_selected_index()
        if not self.segments or self.selected_index < 0 or self.selected_index >= len(
            self.segments
        ):
            xbmcgui.Dialog().ok("Segment Editor", "Please select a segment first.")
            return
        idx = self.selected_index
        n = len(self.segments)
        seg = self.segments[idx]
        if idx == n - 1:
            new_end = self._get_playback_duration_seconds()
            if new_end <= 0:
                xbmcgui.Dialog().ok(
                    "Segment Editor",
                    "Cannot snap end to video length: duration is not available. "
                    "Ensure the video is playing.",
                )
                return
        else:
            new_end = float(self.segments[idx + 1].start_seconds)
        if new_end <= seg.start_seconds:
            xbmcgui.Dialog().ok(
                "Segment Editor",
                "Cannot snap: end would not be after the segment start time.\n\n"
                f"Start: {seconds_to_hms(seg.start_seconds)}\n"
                f"Snap target: {seconds_to_hms(new_end)}",
            )
            return
        self._push_undo()
        seg.end_seconds = new_end
        self.segments_modified = True
        self.refresh_list()
        log(f"Snapped segment end (index {idx}) to {new_end:.3f}s")

    def set_segment_start_to_current(self):
        """Set the selected segment's start to the current playback time."""
        self._refresh_selected_index()
        if not self.segments or self.selected_index < 0 or self.selected_index >= len(
            self.segments
        ):
            xbmcgui.Dialog().ok("Segment Editor", "Please select a segment first.")
            return
        if not self.player.isPlayingVideo():
            xbmcgui.Dialog().ok(
                "Segment Editor",
                "Cannot set start to current time: video is not playing.",
            )
            return
        idx = self.selected_index
        seg = self.segments[idx]
        new_start = float(self.player.getTime())
        if new_start >= seg.end_seconds:
            xbmcgui.Dialog().ok(
                "Segment Editor",
                "Cannot set start to current time: playhead is not before the segment end.\n\n"
                f"End: {seconds_to_hms(seg.end_seconds)}\n"
                f"Current: {seconds_to_hms(new_start)}",
            )
            return
        self._push_undo()
        seg.start_seconds = new_start
        self.segments_modified = True
        self.refresh_list()
        log(f"Set segment start (index {idx}) to current time {new_start:.3f}s")

    def set_segment_end_to_current(self):
        """Set the selected segment's end to the current playback time."""
        self._refresh_selected_index()
        if not self.segments or self.selected_index < 0 or self.selected_index >= len(
            self.segments
        ):
            xbmcgui.Dialog().ok("Segment Editor", "Please select a segment first.")
            return
        if not self.player.isPlayingVideo():
            xbmcgui.Dialog().ok(
                "Segment Editor",
                "Cannot set end to current time: video is not playing.",
            )
            return
        idx = self.selected_index
        seg = self.segments[idx]
        new_end = float(self.player.getTime())
        if new_end <= seg.start_seconds:
            xbmcgui.Dialog().ok(
                "Segment Editor",
                "Cannot set end to current time: playhead is not after the segment start.\n\n"
                f"Start: {seconds_to_hms(seg.start_seconds)}\n"
                f"Current: {seconds_to_hms(new_end)}",
            )
            return
        self._push_undo()
        seg.end_seconds = new_end
        self.segments_modified = True
        self.refresh_list()
        log(f"Set segment end (index {idx}) to current time {new_end:.3f}s")

    def delete_segment(self):
        self._refresh_selected_index()
        if self.selected_index < 0 or self.selected_index >= len(self.segments):
            xbmcgui.Dialog().ok("Segment Editor", "Please select a segment to delete.")
            return

        seg = self.segments[self.selected_index]
        label = seg.raw_label if hasattr(seg, 'raw_label') else seg.segment_type_label

        if xbmcgui.Dialog().yesno("Segment Editor", f"Delete segment '{label}'?"):
            self._push_undo()
            del self.segments[self.selected_index]
            self.segments_modified = True
            self.refresh_list()
            log(f"Deleted segment: {label}")

    def delete_all_segments(self):
        if not self.segments:
            xbmcgui.Dialog().ok("Segment Editor", "There are no segments to delete.")
            return
        if xbmcgui.Dialog().yesno(
            "Segment Editor",
            f"Delete all {len(self.segments)} segments?",
            yeslabel="Delete All",
            nolabel="Cancel",
        ):
            self._push_undo()
            self.segments = []
            self.segments_modified = True
            self.refresh_list()
            log("Deleted all segments")

    # ------------------------------------------------------------------
    # Unsaved changes / exit
    # ------------------------------------------------------------------

    def check_unsaved_changes(self):
        if not self.segments_modified:
            log("No unsaved changes - safe to exit")
            return True

        log("Unsaved changes detected - showing warning dialog")
        result = xbmcgui.Dialog().yesno(
            "Segment Editor",
            "You have unsaved changes.\nExit without saving?",
            yeslabel="Yes",
            nolabel="Cancel",
        )
        if result:
            log("User confirmed exit without saving")
            self.segments_modified = False
            return True
        log("User cancelled exit - staying in editor")
        return False

    # ------------------------------------------------------------------
    # Playback helpers
    # ------------------------------------------------------------------

    def jump_to_segment_start(self):
        self._refresh_selected_index()
        if self.selected_index < 0 or self.selected_index >= len(self.segments):
            log("No segment selected to jump to")
            return
        seg = self.segments[self.selected_index]
        try:
            if self.player.isPlayingVideo():
                self.player.seekTime(seg.start_seconds)
                log(f"Jumped to segment start: {seg.start_seconds:.2f}s")
            else:
                log("Cannot jump - video not playing")
        except Exception as e:
            log_error(f"Error jumping to segment start: {e}")
        finally:
            self._update_edit_delete_positions()

    def seek_relative(self, seconds):
        try:
            if self.player.isPlayingVideo():
                current = self.player.getTime()
                new_time = max(0, current + seconds)
                self.player.seekTime(new_time)
                log(f"Seeked {seconds:+d}s: {current:.2f} -> {new_time:.2f}")
        except Exception as e:
            log_error(f"Error seeking: {e}")

    def jump_to_time(self):
        try:
            if not self.player.isPlayingVideo():
                xbmcgui.Dialog().ok("Segment Editor", "Cannot jump - video is not playing.")
                return

            current = self.player.getTime()
            current_hms = seconds_to_hms(current)

            time_str = xbmcgui.Dialog().input(
                "Jump To Time (HH:MM:SS.mmm or seconds)",
                defaultt=current_hms,
            )
            if not time_str:
                return

            try:
                target_time = hms_to_seconds(time_str)
                if target_time < 0:
                    xbmcgui.Dialog().ok("Segment Editor", "Time cannot be negative.")
                    return
                self.player.seekTime(target_time)
                log(f"Jumped to time: {target_time:.2f}s")
                xbmcgui.Dialog().notification(
                    "Segment Editor",
                    f"Jumped to {seconds_to_hms(target_time)}",
                    icon=self.icon_path,
                    time=2000,
                )
            except ValueError as e:
                xbmcgui.Dialog().ok(
                    "Segment Editor",
                    f"Invalid time format. {e}",
                )
        except Exception as e:
            log_error(f"Error in jump_to_time: {e}")

    def toggle_pause(self):
        try:
            if not self.player.isPlayingVideo():
                log("Cannot toggle pause - video is not playing")
                return
            # Kodi's pause() toggles pause/resume. The authoritative new
            # state is pushed back via onPlayBackPaused/onPlayBackResumed,
            # which update the button label for us. Avoid optimistic updates
            # here to sidestep any callback-ordering races.
            self.player.pause()
        except Exception as e:
            log_error(f"Error toggling pause: {e}")

    # ------------------------------------------------------------------
    # Marking / helpers
    # ------------------------------------------------------------------

    def set_as_start(self):
        try:
            if self.pending_start_time is not None:
                log("Start time already marked - clearing it")
                self.pending_start_time = None
                xbmcgui.Dialog().notification(
                    "Segment Editor", "Start time cleared",
                    icon=self.icon_path, time=2000,
                )
                return

            if self.player.isPlayingVideo():
                new_start = self.player.getTime()
                if (self.pending_end_time is not None
                        and new_start >= self.pending_end_time):
                    xbmcgui.Dialog().ok(
                        "Segment Editor",
                        f"Cannot set start time after end time.\n\n"
                        f"Current end: {seconds_to_hms(self.pending_end_time)}\n"
                        f"Attempted start: {seconds_to_hms(new_start)}",
                    )
                    return
                self.pending_start_time = new_start
                log(f"Marked start time: {self.pending_start_time:.2f}")
                xbmcgui.Dialog().notification(
                    "Segment Editor",
                    f"Start marked: {seconds_to_hms(self.pending_start_time)}",
                    icon=self.icon_path, time=2000,
                )
        except Exception as e:
            log_error(f"Error marking start: {e}")

    def set_as_end(self):
        try:
            if self.pending_end_time is not None:
                log("End time already marked - clearing it")
                self.pending_end_time = None
                xbmcgui.Dialog().notification(
                    "Segment Editor", "End time cleared",
                    icon=self.icon_path, time=2000,
                )
                return

            if self.player.isPlayingVideo():
                new_end = self.player.getTime()
                if (self.pending_start_time is not None
                        and new_end <= self.pending_start_time):
                    xbmcgui.Dialog().ok(
                        "Segment Editor",
                        f"Cannot set end time before start time.\n\n"
                        f"Current start: {seconds_to_hms(self.pending_start_time)}\n"
                        f"Attempted end: {seconds_to_hms(new_end)}",
                    )
                    return
                self.pending_end_time = new_end
                log(f"Marked end time: {self.pending_end_time:.2f}")
                xbmcgui.Dialog().notification(
                    "Segment Editor",
                    f"End marked: {seconds_to_hms(self.pending_end_time)}",
                    icon=self.icon_path, time=2000,
                )
        except Exception as e:
            log_error(f"Error marking end: {e}")

    def set_pending_to_sof(self):
        """Set pending start to start-of-file (0.0)."""
        try:
            if (self.pending_end_time is not None
                    and 0.0 >= self.pending_end_time):
                xbmcgui.Dialog().ok(
                    "Segment Editor",
                    f"Cannot set start time after end time.\n\n"
                    f"Current end: {seconds_to_hms(self.pending_end_time)}\n"
                    f"Attempted start: {seconds_to_hms(0.0)}",
                )
                return
            self.pending_start_time = 0.0
            log("Marked start time at SOF (0.0)")
            xbmcgui.Dialog().notification(
                "Segment Editor",
                f"Start marked: {seconds_to_hms(self.pending_start_time)}",
                icon=self.icon_path, time=2000,
            )
        except Exception as e:
            log_error(f"Error setting start to SOF: {e}")

    def set_pending_to_eof(self):
        """Set pending end to end-of-file (video duration)."""
        try:
            duration = self._get_playback_duration_seconds()
            if duration <= 0:
                xbmcgui.Dialog().ok(
                    "Segment Editor",
                    "Cannot set end to EOF — video duration is not available.",
                )
                return
            if (self.pending_start_time is not None
                    and duration <= self.pending_start_time):
                xbmcgui.Dialog().ok(
                    "Segment Editor",
                    f"Cannot set end time before start time.\n\n"
                    f"Current start: {seconds_to_hms(self.pending_start_time)}\n"
                    f"Attempted end: {seconds_to_hms(duration)}",
                )
                return
            self.pending_end_time = duration
            log(f"Marked end time at EOF ({duration:.2f})")
            xbmcgui.Dialog().notification(
                "Segment Editor",
                f"End marked: {seconds_to_hms(self.pending_end_time)}",
                icon=self.icon_path, time=2000,
            )
        except Exception as e:
            log_error(f"Error setting end to EOF: {e}")

    def select_segment_from_list(self, title):
        if not self.segments:
            xbmcgui.Dialog().ok("Segment Editor", "No segments available to select.")
            return None

        options = []
        for i, seg in enumerate(self.segments):
            label = seg.raw_label if hasattr(seg, 'raw_label') else seg.segment_type_label
            options.append(
                f"Segment {i+1}: {label} "
                f"({seconds_to_hms(seg.start_seconds)} -> {seconds_to_hms(seg.end_seconds)})"
            )

        selected = xbmcgui.Dialog().select(title, options)
        return selected if selected >= 0 else None

    def start_at_end_of_segment(self):
        if not self.segments:
            xbmcgui.Dialog().ok("Segment Editor", "No segments available.")
            return
        seg_index = self.select_segment_from_list("Select Segment (Start at End)")
        if seg_index is None:
            return

        selected_seg = self.segments[seg_index]
        new_start = selected_seg.end_seconds
        if (self.pending_end_time is not None
                and new_start >= self.pending_end_time):
            xbmcgui.Dialog().ok(
                "Segment Editor",
                f"Cannot set start time after end time.\n\n"
                f"Current end: {seconds_to_hms(self.pending_end_time)}\n"
                f"Selected start: {seconds_to_hms(new_start)}",
            )
            return
        self.pending_start_time = new_start
        xbmcgui.Dialog().notification(
            "Segment Editor",
            f"Start marked: {seconds_to_hms(self.pending_start_time)}",
            icon=self.icon_path, time=2000,
        )

    def end_at_start_of_segment(self):
        if not self.segments:
            xbmcgui.Dialog().ok("Segment Editor", "No segments available.")
            return
        seg_index = self.select_segment_from_list("Select Segment (End at Start)")
        if seg_index is None:
            return

        selected_seg = self.segments[seg_index]
        new_end = selected_seg.start_seconds
        if (self.pending_start_time is not None
                and new_end <= self.pending_start_time):
            xbmcgui.Dialog().ok(
                "Segment Editor",
                f"Cannot set end time before start time.\n\n"
                f"Current start: {seconds_to_hms(self.pending_start_time)}\n"
                f"Selected end: {seconds_to_hms(new_end)}",
            )
            return
        self.pending_end_time = new_end
        xbmcgui.Dialog().notification(
            "Segment Editor",
            f"End marked: {seconds_to_hms(self.pending_end_time)}",
            icon=self.icon_path, time=2000,
        )

    def get_predefined_labels(self):
        try:
            return get_custom_segment_keyword_labels(get_addon())
        except Exception:
            return get_custom_segment_keyword_labels(None)

    def get_label_from_user(self, default=""):
        predefined = self.get_predefined_labels()
        options = ["Custom..."] + predefined
        selected = _select_segment_label_from_list(options)
        if selected is None:
            selected = xbmcgui.Dialog().select("Select Segment Label", options)

        if selected == 0:
            label = xbmcgui.Dialog().input(
                "Enter Custom Label",
                defaultt=default or "segment",
            )
            return label if label else (default or "segment")
        if selected > 0:
            return predefined[selected - 1]
        return None

    def add_with_marked_times(self):
        if self.pending_start_time is None or self.pending_end_time is None:
            xbmcgui.Dialog().ok(
                "Segment Editor",
                "Please mark both start and end times first.",
            )
            return
        if self.pending_end_time <= self.pending_start_time:
            xbmcgui.Dialog().ok(
                "Segment Editor",
                "End time must be after start time.",
            )
            return

        label = self.get_label_from_user()
        if label is None:
            return

        source = "edl"
        if self.segments and self.segments[0].source == "xml":
            source = "xml"

        new_seg = SegmentItem(
            self.pending_start_time,
            self.pending_end_time,
            label,
            source=source,
        )
        self._push_undo()
        self.segments.append(new_seg)
        self.segments_modified = True

        self.pending_start_time = None
        self.pending_end_time = None

        self.refresh_list()
        log(f"Added segment with marked times: {new_seg}")
        xbmcgui.Dialog().notification(
            "Segment Editor", "Segment added successfully",
            icon=self.icon_path, time=2000,
        )

    def save_current_segments(self):
        """Save the current segments via the shared save-format dispatcher."""
        log(f"save_current_segments() called with {len(self.segments)} segments")
        if not self.video_path:
            xbmcgui.Dialog().ok("Segment Editor", "No video path available for saving.")
            return
        if not self.segments:
            xbmcgui.Dialog().ok("Segment Editor", "No segments to save.")
            return

        save_format = get_save_format()
        try:
            edl_ok, xml_ok = save_segments(self.video_path, self.segments, save_format)
        except Exception as e:
            log_error(f"Error saving segments: {e}")
            import traceback
            log_error(f"Traceback: {traceback.format_exc()}")
            xbmcgui.Dialog().ok("Segment Editor", f"Error saving segments: {e}")
            return

        if edl_ok or xml_ok:
            self.segments_modified = False
            self._undo_stack.clear()
            self._update_undo_button()
            if save_format == SAVE_FORMAT_BOTH:
                if edl_ok and xml_ok:
                    msg = "Segments saved to both formats"
                elif edl_ok:
                    msg = "Segments saved to EDL (XML failed)"
                else:
                    msg = "Segments saved to XML (EDL failed)"
            else:
                msg = "Segments saved successfully"
            xbmcgui.Dialog().notification(
                "Segment Editor", msg,
                icon=self.icon_path, time=2000,
            )
        else:
            xbmcgui.Dialog().ok(
                "Segment Editor",
                "Failed to save segments. Check file permissions.",
            )

    def upload_segments_online(self):
        """POST segments to TheIntroDB.org / IntroDB.app (optional APIs)."""
        try:
            from online_segment_upload import (
                TARGET_BOTH,
                TARGET_INTRODB_APP,
                TARGET_THEINTRODB,
                upload_all_segments,
            )
            from skippy_editor_modal_skin import show_editor_list_pick, show_editor_ok
        except Exception as exc:
            log_error("online_segment_upload import failed: %s" % exc)
            return
        addon = get_addon()
        if not addon:
            return
        if addon.getSetting("online_upload_enabled") != "true":
            try:
                show_editor_ok(
                    addon.getLocalizedString(39013),
                    addon.getLocalizedString(39040),
                )
            except Exception:
                pass
            return
        order = [TARGET_BOTH, TARGET_THEINTRODB, TARGET_INTRODB_APP]
        raw = addon.getSetting("online_upload_default_target") or TARGET_BOTH
        try:
            pre = order.index(raw)
        except ValueError:
            pre = 0
        labels = [
            addon.getLocalizedString(39010),
            addon.getLocalizedString(39011),
            addon.getLocalizedString(39012),
        ]
        heading = addon.getLocalizedString(39009)
        try:
            idx = show_editor_list_pick(heading, labels, preselect=pre)
        except Exception:
            try:
                idx = xbmcgui.Dialog().select(heading, labels, preselect=pre)
            except TypeError:
                idx = xbmcgui.Dialog().select(heading, labels)
        if idx < 0:
            return
        upload_all_segments(self.video_path, self.segments, order[idx])
