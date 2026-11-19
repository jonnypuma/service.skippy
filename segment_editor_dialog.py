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
import segment_editor_layout
import skippy_modal_style
import copy
import threading
import time

import xbmc
import xbmcgui

from segment_editor_parser import (
    SegmentItem,
    seconds_to_hms,
    hms_to_seconds,
    save_segments,
    parse_embedded_chapters_via_mkvextract,
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
from addon_skin_resolution import (
    init_window_xml_dialog,
    reconcile_window_xml_skin_resolution,
    scale_skin_coord,
    SKIN_RES_720P,
)
from settings_utils import (
    format_segment_label_for_ui,
    get_custom_segment_keyword_labels,
    normalize_label,
    get_localized,
)


def _select_segment_label_from_list(options, style=None):
    """
    Skinned list (same as Segment Marker) so every catalog type is shown.
    xbmcgui.Dialog().select() can omit or mishandle items on some platforms.

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
            skippy_modal_style.xml_name("SegmentMarkerTypePicker.xml", style=style, addon=addon),
            path,
            "default",
            style=style,  # the editor's own look, when it has one
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
    """Catalog display name for the segment list (Behind the scenes, not behind_the_scenes)."""
    return format_segment_label_for_ui(label)


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



def new_segment_source(save_format=None) -> str:
    """The source a segment made in the editor is listed with: the file it will be saved to. Chapter XML is the
    preferred sidecar and EDL the fallback, so it is XML unless the editor saves EDL only (it was EDL unless
    the first segment in the list came from an XML file, so a new segment in an empty list read Local EDL)."""
    try:
        chosen = save_format or get_save_format()
    except Exception:
        chosen = SAVE_FORMAT_BOTH
    return "edl" if str(chosen).lower() == "edl" else "xml"

class SegmentEditorDialog(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        # the look: the List and drawer layout has its own (Fused Glass Dark), the others follow the setting
        self._style = kwargs.get("style", segment_editor_layout.style_for(kwargs.get("layout")))
        skippy_modal_style.apply(self, style=self._style)  # before the window shows
        skin_res = SKIN_RES_720P
        try:
            skin_res = init_window_xml_dialog(super(SegmentEditorDialog, self), args)
        except Exception:
            super().__init__(*args)
        self._skin_resolution = skin_res
        self.video_path = kwargs.get("video_path")
        self._small_video = bool(kwargs.get("small_video", False))  # a plain window lies under it: the video is small
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
        sc = lambda value: scale_skin_coord(value, skin_res)
        self._list_top = sc(110)
        self._list_item_height = sc(50)
        self._list_height = sc(290)
        self._start_curr_btn_left = sc(425)
        self._end_curr_btn_left = sc(532)
        self._snap_start_btn_left = sc(625)
        self._snap_end_btn_left = sc(722)
        self._merge_btn_left = sc(821)
        self._split_btn_left = sc(898)
        self._fix_btn_left = sc(953)
        self._edit_btn_left = sc(1040)
        self._delete_btn_left = sc(1095)
        self._edit_delete_btn_height = sc(30)
        self._selection_sync_timer = None
        self._indicator_win_home = None
        # Layout: only the classic file has row buttons that follow the highlighted row; the drawer's list is horizontal.
        self._layout = segment_editor_layout.normalize(kwargs.get("layout"), segment_editor_layout.LAYOUT_CLASSIC)
        self._row_buttons_follow = self._layout == segment_editor_layout.LAYOUT_CLASSIC
        self._list_is_horizontal = self._layout == segment_editor_layout.LAYOUT_DRAWER
        self._ms_colors = skippy_modal_style.colors(style=self._style)
        self._undo_stack = []
        self._undo_stack_max = 20
        # opened again for another look of the panels: the work in hand comes along
        self._reopen_with = None
        carried = kwargs.get("carried") or {}
        if carried:
            self.segments_modified = bool(carried.get("modified"))
            self.pending_start_time = carried.get("pending_start")
            self.pending_end_time = carried.get("pending_end")
            self._undo_stack = list(carried.get("undo") or [])
            self._carried_selection = carried.get("selected", -1)
            self._carried_focus = carried.get("focus")
        # font10 via setLabel — WindowXML ignores skin <font> on buttons; aspect is in XML.
        self._editor_btn_font = "font10"

        try:
            addon = get_addon()
            self.icon_path = addon.getAddonInfo("icon") or None
        except Exception:
            self.icon_path = None

        log(f"SegmentEditorDialog initialized with {len(self.segments)} segments")

    def _T(self, string_id, default="", *args):
        """Localized UI string with English fallback."""
        return get_localized(get_addon(), string_id, default, *args)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def onInit(self):
        try:
            log_always("onInit called")
            skippy_modal_style.apply(self, style=getattr(self, "_style", None))

            asked = getattr(self, "_skin_resolution", None)
            locked = reconcile_window_xml_skin_resolution(
                self, asked, control_ids=(5000,)
            )
            if locked != asked:
                log(
                    "Skin resolution re-locked: asked %s, controls imply %s"
                    % (asked, locked)
                )
                self._skin_resolution = locked
                sc = lambda value: scale_skin_coord(value, locked)
                self._list_top = sc(110)
                self._list_item_height = sc(50)
                self._list_height = sc(290)
                self._start_curr_btn_left = sc(425)
                self._end_curr_btn_left = sc(532)
                self._snap_start_btn_left = sc(625)
                self._snap_end_btn_left = sc(722)
                self._merge_btn_left = sc(821)
                self._split_btn_left = sc(898)
                self._fix_btn_left = sc(953)
                self._edit_btn_left = sc(1040)
                self._delete_btn_left = sc(1095)
                self._edit_delete_btn_height = sc(30)

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

            # Listener may miss the already-current state; resync after register.
            try:
                self._sync_pause_button_from_player()
            except Exception as e:
                log(f"Error resyncing pause button: {e}")

            try:
                self.setFocusId(5018)
                log_always("Set initial focus to Pause/Resume button (5018)")
            except Exception:
                log_always("Could not set initial focus to Pause/Resume button")
            # opened again for another look: back to the segment and the button the user was on. Last, after
            # the list is filled and the first focus is set, or both would be undone.
            self._restore_carried_place()

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
        """Read Kodi's Player.Paused flag (same as the service loop).

        Avoid sampling ``getTime()``: playhead often does not advance for a
        short window while WindowXML opens, which falsely reported paused and
        left the button labelled Resume while video was still playing.
        """
        try:
            if not self.player.isPlayingVideo():
                return False
            return bool(xbmc.getCondVisibility("Player.Paused"))
        except Exception as e:
            log(f"Error detecting initial pause state: {e}")
            return False

    def _set_pause_state(self, paused):
        if self.is_paused == paused:
            return
        self.is_paused = paused
        log(f"Pause state changed via Player callback: paused={paused}")
        self._update_pause_button_label()

    def _sync_pause_button_from_player(self):
        """Force label to match Player.Paused (used after listener register)."""
        try:
            paused = bool(xbmc.getCondVisibility("Player.Paused")) if self.player.isPlayingVideo() else False
        except Exception:
            paused = False
        if self.is_paused != paused:
            self.is_paused = paused
            log(f"Pause state resynced from Player.Paused: paused={paused}")
        self._update_pause_button_label()

    def _set_button_label_font(self, btn, label=None):
        """Apply editor button font/colors; WindowXML ignores skin <font> tags."""
        if not btn:
            return
        font = self._editor_btn_font
        if label is None:
            label = btn.getLabel() or ""
        try:
            colors = getattr(self, "_ms_colors", None) or skippy_modal_style.colors()
            btn.setLabel(
                label,
                font,
                "0x" + colors["ms_text"],
                "0x" + colors["ms_text3"],
                "0x00000000",
                "0x" + colors["ms_text_focus"],
            )
        except TypeError:
            try:
                btn.setLabel(label, font)
            except Exception:
                pass

    def _apply_editor_button_fonts(self):
        """Apply font10 to every editor button (list row + toolbar rows)."""
        for cid in _EDITOR_BUTTON_IDS:
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
                    self._T(41001, "Pause") if not self.is_paused else self._T(41002, "Resume"),
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
                    self._update_playhead(current)
                    hms = seconds_to_hms(current)

                    try:
                        time_label = self.getControl(5001)
                        if time_label:
                            pause_indicator = self._T(41013, " [PAUSED]") if self.is_paused else ""
                            time_label.setLabel(self._T(41012, "Current Time: %s", hms) + pause_indicator)
                    except Exception:
                        pass

                    status_text = ""
                    if self.pending_start_time is not None:
                        status_text = self._T(41014, "Start: %s", seconds_to_hms(self.pending_start_time))
                    if self.pending_end_time is not None:
                        if status_text:
                            status_text += self._T(41016, " | End: %s", seconds_to_hms(self.pending_end_time))
                        else:
                            status_text = self._T(41015, "End: %s", seconds_to_hms(self.pending_end_time))
                    if (self.pending_start_time is not None
                            and self.pending_end_time is not None
                            and self.pending_end_time <= self.pending_start_time):
                        status_text += self._T(41017, " [INVALID: End must be after Start]")

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
                self._T(41000, "Segment Editor"),
                self._T(41005, "No sidecar segment file was found.\n\nCheck this video for embedded Matroska chapters? This may take a few seconds."),
                yeslabel=self._T(41003, "Check"),
                nolabel=self._T(40000, "Skip"),
            )
        except Exception as err:
            log(f"Embedded chapter preflight prompt failed: {err}")
            return

        if not should_check:
            log("User skipped embedded chapter check")
            return

        try:
            embedded = parse_embedded_chapters_via_mkvextract(self.video_path, timeout=3)
        except Exception as err:
            log(f"Embedded chapter probe failed: {err}")
            return

        if not embedded:
            xbmcgui.Dialog().notification(
                self._T(41000, "Segment Editor"),
                self._T(41006, "No embedded chapters found"),
                icon=self.icon_path,
                time=2000,
            )
            return

        try:
            proceed = xbmcgui.Dialog().yesno(
                self._T(41000, "Segment Editor"),
                self._T(41007, "This video contains %d embedded chapter(s).\n\nImport them as segments?", len(embedded)),
                yeslabel=self._T(41004, "Import"),
                nolabel=self._T(40000, "Skip"),
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

    def refresh_list(self, highlight=None):
        """Fill the list again. ``highlight``: the segment to highlight after it (one just created); the
        focus stays on the button that was pressed."""
        try:
            if not hasattr(self, 'list_control') or not self.list_control:
                log("List control not available, skipping refresh")
                return

            prev_segment = None
            if 0 <= self.selected_index < len(self.segments):
                prev_segment = self.segments[self.selected_index]
            if highlight is not None:
                prev_segment = highlight

            self.segments = segments_chronological(self.segments)

            nested_indices, overlapping_indices = self._compute_segment_overlap_sets()

            items = []
            for i, seg in enumerate(self.segments):
                start_hms = seconds_to_hms(seg.start_seconds)
                end_hms = seconds_to_hms(seg.end_seconds)
                duration = seg.get_duration()

                label = seg.raw_label if hasattr(seg, 'raw_label') else seg.segment_type_label
                list_label = _format_segment_label_list_display(label)
                segment_num = i + 1
                is_nested = i in nested_indices
                is_overlapping = i in overlapping_indices

                line1 = self._T(41008, "Segment %d - %s - %s to %s", segment_num, list_label, start_hms, end_hms)
                line2 = self._T(41009, "Duration: %.1fs | Source: %s", duration, seg.source)
                if is_nested:
                    line2 += self._T(41010, " | Nested")
                elif is_overlapping:
                    line2 += self._T(41011, " | Overlapping")

                item = xbmcgui.ListItem(line1, line2)
                item.setProperty("index", str(i))
                item.setProperty("start", str(seg.start_seconds))
                item.setProperty("end", str(seg.end_seconds))
                item.setProperty("label", list_label)
                item.setProperty("type_chip", segment_editor_layout.chip_texture(label))
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
                # the one-line row of the List and drawer layout
                item.setProperty("range", "%s – %s" % (segment_editor_layout.clock(seg.start_seconds),
                                                       segment_editor_layout.clock(seg.end_seconds)))
                item.setProperty("length", segment_editor_layout.clock(duration))
                item.setProperty("source", segment_editor_layout.source_name(seg.source))
                item.setProperty("flag", self._T(49181, "NESTED") if is_nested
                                 else self._T(49182, "OVERLAP") if is_overlapping else "")
                items.append(item)

            self.list_control.reset()
            self.list_control.addItems(items)
            self._write_editor_words()

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
            self._update_timeline()
            if highlight is not None:
                # Kodi moves the list on its next frame, and the timeline reads the list: once more, a moment later
                threading.Timer(0.4, self._update_timeline).start()

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
            5044: self.toggle_dark_overlay,  # the Look row of the List and drawer layout
            5045: self.cycle_panel_style,
            5046: self.toggle_small_video,
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
            if getattr(self, "_list_is_horizontal", False) and focused == 5000:
                self._schedule_sync_list_selection()  # the drawer's chips move with Left / Right
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

    # ------------------------------------------------------------------
    # Timeline (layouts A and B; the classic file has none of these controls)
    # ------------------------------------------------------------------

    def _timeline_track(self):
        """(left, top, width) of the track, or None when this layout has no timeline."""
        try:
            track = self.getControl(segment_editor_layout.TRACK_ID)
            return track.getX(), track.getY(), track.getWidth()
        except Exception:
            return None

    def _write_editor_words(self):
        """The words of the List and drawer layout: the count, the headers, the tags and the hint line."""
        try:
            count = len(self.segments)
            title = self._T(49170, "1 segment") if count == 1 else self._T(49169, "%d segments", count)
            bold = "[B]%s[/B]"
            self.setProperty("ed_kicker", bold % ("SKIPPY · %s" % self._T(41000, "Segment Editor").upper()))
            self.setProperty("ed_timeline", bold % self._T(49172, "TIMELINE"))
            self.setProperty("ed_seek", bold % self._T(49174, "SEEK"))
            self.setProperty("ed_mark", bold % self._T(49175, "MARK"))
            self.setProperty("ed_file", bold % self._T(49176, "SEGMENTS AND FILE"))
            self.setProperty("ed_live", bold % self._T(49177, "LIVE VIDEO"))
            dark = self.getProperty("EnableFullscreenOverlay") == "true"
            self.setProperty("ed_overlay", bold % (self._T(49178, "DARK OVERLAY: ON") if dark
                                                   else self._T(49179, "DARK OVERLAY: OFF")))
            # the Look row: what its two buttons say now
            self.setProperty("ed_look", bold % self._T(49183, "LOOK"))
            names = {"fg_dark": self._T(49187, "Dark"), "fg_frost": self._T(49188, "Frost"), "fg_clear": self._T(49189, "Clear")}
            small = segment_editor_layout.small_video(get_addon())
            words = (self._T(49184, "Dark overlay: on") if dark else self._T(49185, "Dark overlay: off"),
                     self._T(49186, "Panels: %s", names.get(segment_editor_layout.editor_style(self._style), "")),
                     self._T(49235, "Video: small") if small else self._T(49236, "Video: full screen"))
            # the video window above the timeline shows only over the plain window (else it would show a piece
            # of the full-screen picture)
            self.setProperty("ed_video", "true" if self._small_video else "")
            for cid, word in zip(segment_editor_layout.LOOK_BUTTON_IDS, words):
                try:
                    self._set_button_label_font(self.getControl(cid), word)
                except Exception:
                    pass
            self._fit_small_labels()
            self.setProperty("ed_hint", self._T(
                49180, "[B]OK on a segment[/B]  jumps to its start      [B]Left[/B]  its nine actions      "
                       "[B]Right[/B]  the timeline      [B]Back[/B]  asks to save"))
            self._draw_editor_title(title)
        except Exception:
            pass

    def _restore_carried_place(self):
        """After the editor opened again for another look: the highlighted segment and the focus are where they were."""
        selection = getattr(self, "_carried_selection", None)
        if selection is None:
            return
        self._carried_selection = None
        try:
            if 0 <= selection < len(self.segments):
                self.list_control.selectItem(selection)
                self.selected_index = selection
                # the timeline and the heading follow the highlighted segment. Kodi moves the list on its
                # next frame, and they read the list: so a moment later, not now.
                threading.Timer(0.4, self._update_timeline).start()
            focus = getattr(self, "_carried_focus", None)
            if focus:
                self.setFocusId(int(focus))
        except Exception:
            pass

    def toggle_dark_overlay(self):
        """Look row: the dark overlay behind the editor, on or off. It is the setting of the same name."""
        dark = self.getProperty("EnableFullscreenOverlay") != "true"
        self.setProperty("EnableFullscreenOverlay", "true" if dark else "false")
        try:
            get_addon().setSetting("segment_editor_fullscreen_overlay", "true" if dark else "false")
        except Exception as e:
            log(f"Could not store the dark overlay setting: {e}")
        self._write_editor_words()

    def toggle_small_video(self):
        """Look row: the video small above the timeline, or full screen behind the editor. It is a setting; the
        editor opens again so that the plain window under it can open or close first."""
        addon = get_addon()
        small = not segment_editor_layout.small_video(addon)
        try:
            addon.setSetting(segment_editor_layout.VIDEO_KEY, "true" if small else "false")
        except Exception as e:
            log(f"Could not store the editor's video size: {e}")
            return
        self._reopen(segment_editor_layout.LOOK_BUTTON_IDS[2])

    def _reopen(self, focus):
        """Close and open again with the work in hand (the session does it): for what only a new window can do."""
        self._refresh_selected_index()
        self._reopen_with = {
            "segments": list(self.segments), "modified": self.segments_modified, "pending_start": self.pending_start_time,
            "pending_end": self.pending_end_time, "undo": list(self._undo_stack), "selected": self.selected_index,
            "focus": focus,
        }
        # the session saves on close when this is set: it must not, the editor only changes its clothes
        self.segments_modified = False
        self.close()

    def cycle_panel_style(self):
        """Look row: the next look of the panels (Dark, Frost, Clear). A window takes its pictures from its
        file, so the editor closes and opens again in the file of that look; nothing of the work is lost."""
        style = segment_editor_layout.next_style(self._style)
        try:
            get_addon().setSetting(segment_editor_layout.STYLE_KEY, style)
        except Exception as e:
            log(f"Could not store the editor's panel look: {e}")
            return
        self._refresh_selected_index()
        self._reopen_with = {
            "segments": list(self.segments), "modified": self.segments_modified, "pending_start": self.pending_start_time,
            "pending_end": self.pending_end_time, "undo": list(self._undo_stack), "selected": self.selected_index,
            "focus": segment_editor_layout.LOOK_BUTTON_IDS[1],
        }
        # the session saves on close when this is set: it must not, the editor only changes its clothes
        self.segments_modified = False
        self.close()

    def _fit_small_labels(self):
        """Bring the small labels to the mockup's size: the skin's smallest font is larger than its small
        capitals. A label that stays where it is, is zoomed around the end its text starts from; one the
        editor moves about is zoomed around its own middle. Done once per window."""
        if getattr(self, "_small_fitted", False):
            return
        self._small_fitted = True
        self._small_zoom = 1.0
        lay = segment_editor_layout
        if not self._has_control(lay.TITLE_BOX_ID):
            return  # not the List and drawer layout
        try:
            import skip_canvas_draw

            size = skip_canvas_draw.read_fonts().get(lay.SMALL_FONT, (0, False))[0]
            # font sizes are in pixels of a 1080 screen: so is the wanted size
            zoom = lay.small_zoom(size)
            if zoom >= 0.999:
                return
            self._small_zoom = zoom
            percent = zoom * 100.0
            for cid, align in lay.SMALL_LABELS:
                try:
                    control = self.getControl(cid)
                    x, y, w, h = control.getX(), control.getY(), control.getWidth(), control.getHeight()
                    cx = x if align == "l" else x + w if align == "r" else x + w / 2.0
                    control.setAnimations([("conditional", "effect=zoom start=%.2f end=%.2f center=%.1f,%.1f time=0 condition=true"
                                            % (percent, percent, cx, y + h / 2.0))])
                except Exception:
                    pass
            for cid in lay.MOVING_LABELS:
                try:
                    self.getControl(cid).setAnimations([(
                        "conditional", "effect=zoom start=%.2f end=%.2f center=auto time=0 condition=true" % (percent, percent))])
                except Exception:
                    pass
        except Exception:
            self._small_zoom = 1.0

    def _draw_editor_title(self, text):
        """The large count ("4 segments") at the mockup's size, where the layout keeps a place for it."""
        if getattr(self, "_editor_title", (None, None))[1] == text:
            return
        try:
            box = self.getControl(segment_editor_layout.TITLE_BOX_ID)
        except Exception:
            return  # this layout has no such place
        try:
            import skip_canvas_draw

            old = getattr(self, "_editor_title", (None, None))[0]
            if old is not None:
                self.removeControl(old)
            # the place is inside the list panel, whose corner is the panel's; a control made here counts from the window
            scale = box.getWidth() / float(segment_editor_layout.TITLE_BOX[2])
            left = (segment_editor_layout.PANEL_A[0] + segment_editor_layout.TITLE_BOX[0]) * scale
            top = (segment_editor_layout.PANEL_A[1] + segment_editor_layout.TITLE_BOX[1]) * scale
            colors = getattr(self, "_ms_colors", None) or skippy_modal_style.colors()
            control = skip_canvas_draw.big_label(self, left, top, box.getWidth(), box.getHeight(), text,
                                                 segment_editor_layout.TITLE_SIZE * scale, True, colors["ms_text"])
            self._editor_title = (control, text)
        except Exception:
            self._editor_title = (None, None)

    def _selected_position(self) -> int:
        try:
            return self.list_control.getSelectedPosition() if getattr(self, "list_control", None) else -1
        except Exception:
            return -1

    def _timeline_window(self):
        """The stretch of the file the track shows: around the highlighted segment (see timeline_window)."""
        duration = self._get_playback_duration_seconds()
        if not self._has_control(segment_editor_layout.TIME_START_ID):
            return 0.0, duration  # a layout without the times under its track shows the whole file
        # the highlighted segment and those connected to it, with a little room
        group = segment_editor_layout.connected_span(
            [(seg.start_seconds, seg.end_seconds) for seg in self.segments], self._selected_position())
        return segment_editor_layout.timeline_window(group, duration)

    def _update_timeline(self):
        """Place one coloured block per segment on the track, with its word; write the times; draw the
        thin bar of the whole file."""
        geometry = self._timeline_track()
        if not geometry:
            return
        left, top, width = geometry
        lay = segment_editor_layout
        try:
            duration = self._get_playback_duration_seconds()
            first, last = self._timeline_window()
            self._timeline_span = (first, last)
            parts = [(seg.start_seconds, seg.end_seconds, self._segment_display_label(seg)) for seg in self.segments]
            blocks = lay.window_blocks(parts, first, last, width)
            self._timeline_blocks = blocks
            zoomed = self._has_control(lay.TIME_START_ID)
            for slot, cid in enumerate(lay.BLOCK_IDS):
                try:
                    block_control = self.getControl(cid)
                    if slot < len(blocks):
                        block = blocks[slot]
                        block_control.setPosition(left + block.left, top)
                        block_control.setWidth(block.width)
                        # the zoomed track has blocks with round corners
                        texture = block.texture
                        if zoomed:
                            texture = lay.block_texture(self._segment_display_label(self.segments[block.index]))
                        block_control.setImage(texture, False)
                        block_control.setVisible(True)
                    else:
                        block_control.setVisible(False)
                except Exception:
                    pass
            try:
                if zoomed:
                    self.getControl(lay.END_LABEL_ID).setLabel(
                        self._T(49173, "SHOWING %s – %s", lay.clock(first), lay.clock(last)) if last > first else "")
                    self.getControl(lay.TIME_START_ID).setLabel(lay.clock(first))
                    self.getControl(lay.TIME_END_ID).setLabel(lay.clock(last))
                else:
                    self.getControl(lay.END_LABEL_ID).setLabel(lay.short_time(duration))
            except Exception:
                pass
            self._draw_overview(parts, duration, first, last)
        except Exception as e:
            log_error(f"Error drawing the timeline: {e}")
        self._place_selection()
        self._update_playhead(getattr(self, "current_time", 0) or 0)

    def _has_control(self, cid) -> bool:
        try:
            return self.getControl(cid) is not None
        except Exception:
            return False

    def _draw_overview(self, parts, duration, first, last):
        """The thin bar over the track: every segment of the whole file, and a frame round what the track shows."""
        lay = segment_editor_layout
        try:
            bar = self.getControl(lay.OVERVIEW_ID)
        except Exception:
            return
        try:
            left, top, width = bar.getX(), bar.getY(), bar.getWidth()
            blocks = lay.timeline_blocks(parts, duration, width, max_blocks=len(lay.OVERVIEW_BLOCK_IDS), min_width=2)
            for slot, cid in enumerate(lay.OVERVIEW_BLOCK_IDS):
                control = self.getControl(cid)
                if slot < len(blocks):
                    control.setPosition(left + blocks[slot].left, top)
                    control.setWidth(blocks[slot].width)
                    control.setImage(blocks[slot].texture, False)
                    control.setVisible(True)
                else:
                    control.setVisible(False)
            frame = self.getControl(lay.OVERVIEW_WINDOW_ID)
            if duration > 0 and last > first and (last - first) < duration:
                frame.setPosition(left + int(round(first / duration * width)), frame.getY())
                frame.setWidth(max(8, int(round((last - first) / duration * width))))
                frame.setVisible(True)
            else:
                frame.setVisible(False)
        except Exception:
            pass

    def _place_selection(self):
        """The frame round the block of the highlighted segment, the word in every block, and the line that
        names the highlighted segment over its nine actions."""
        geometry = self._timeline_track()
        if not geometry:
            return
        left, top, width = geometry
        lay = segment_editor_layout
        selected = self._selected_position()
        blocks = getattr(self, "_timeline_blocks", ())
        scale = max(1.0, width / float(lay.TRACK_A_WIDTH))
        # a word in every block that has room for one; the highlighted one adds its length
        for slot, cid in enumerate(lay.BLOCK_LABEL_IDS):
            try:
                control = self.getControl(cid)
            except Exception:
                break
            try:
                word = ""
                if slot < len(blocks):
                    block = blocks[slot]
                    seg = self.segments[block.index]
                    # a word only where it fits whole: the highlighted segment adds its length when there is room
                    # smaller letters: more of a word fits
                    word = lay.block_word(_format_segment_label_list_display(self._segment_display_label(seg)),
                                          lay.clock(seg.get_duration()) if block.index == selected else "",
                                          (block.width / scale - (14 if block.index == selected else 0))
                                          / (getattr(self, "_small_zoom", 1.0) or 1.0))
                if word:
                    # the highlighted block has a handle at its start: its word begins after it
                    pad = int((16 if block.index == selected else 9) * scale)
                    # the word is zoomed around the middle of its box: the box is made so much wider that the
                    # zoomed box is the room in the block, and set back so that the word starts where it should
                    zoom = getattr(self, "_small_zoom", 1.0) or 1.0
                    room = max(10, block.width - pad - 4)
                    box = int(room / zoom)
                    control.setWidth(box)
                    control.setPosition(int(left + block.left + pad - box * (1.0 - zoom) / 2.0), control.getY())
                    control.setLabel("[B]%s[/B]" % word)
                    control.setVisible(True)
                else:
                    control.setVisible(False)
            except Exception:
                pass
        try:
            name = ""
            if 0 <= selected < len(self.segments):
                name = _format_segment_label_list_display(self._segment_display_label(self.segments[selected]))
            self.setProperty("ed_selected", self._T(49171, "HIGHLIGHTED SEGMENT · %s", name.upper()) if name else "")
        except Exception:
            pass
        self._place_segment_marks(left, width, blocks, selected, scale)
        for cid, whole in ((lay.OUTLINE_ID, True), (lay.SELECTED_MARK_ID, False)):
            try:
                mark = self.getControl(cid)
            except Exception:
                continue
            try:
                for block in blocks:
                    if block.index == selected:
                        grow = int(2 * scale) if whole else 0
                        mark.setPosition(left + block.left - grow, mark.getY())
                        mark.setWidth(block.width + 2 * grow)
                        mark.setVisible(True)
                        break
                else:
                    mark.setVisible(False)
            except Exception:
                pass

    def _place_segment_marks(self, left, width, blocks, selected, scale):
        """The two handles inside the highlighted block, and the times under its two ends."""
        lay = segment_editor_layout
        block = next((b for b in blocks if b.index == selected), None)
        try:
            handles = [self.getControl(cid) for cid in lay.HANDLE_IDS]
            times = [self.getControl(lay.TIME_SEG_START_ID), self.getControl(lay.TIME_SEG_END_ID)]
        except Exception:
            return
        try:
            if block is None:
                for control in handles + times:
                    control.setVisible(False)
                self._segment_ticks = ()
                return
            seg = self.segments[block.index]
            inset = int(5 * scale)
            wide = block.width >= int(30 * scale)
            for control, x in zip(handles, (left + block.left + inset, left + block.left + block.width - inset - handles[1].getWidth())):
                control.setPosition(x, control.getY())
                control.setVisible(wide)
            first, last = getattr(self, "_timeline_span", (0.0, 0.0))
            # a time under an end of the segment, unless that end is the end of the track, which has its own
            clear = int(46 * scale)
            ticks = []
            for control, seconds, x in zip(times, (seg.start_seconds, seg.end_seconds),
                                           (left + block.left, left + block.left + block.width)):
                shown = (first < seconds < last) and clear <= x - left <= width - clear \
                    and all(abs(x - other) >= clear for other in ticks)
                if shown:
                    control.setPosition(x - control.getWidth() // 2, control.getY())
                    control.setLabel(lay.clock(seconds))
                    ticks.append(x)
                control.setVisible(shown)
            self._segment_ticks = tuple(ticks)
        except Exception:
            pass

    def _update_timeline_selection(self):
        """The highlighted segment changed: the track may have to show another stretch of the file."""
        if not self._timeline_track():
            return
        try:
            if self._timeline_window() != getattr(self, "_timeline_span", None):
                self._update_timeline()
                return
        except Exception:
            pass
        self._place_selection()

    def _update_playhead(self, current):
        geometry = self._timeline_track()
        if not geometry:
            return
        left, _top, width = geometry
        lay = segment_editor_layout
        try:
            playhead = self.getControl(lay.PLAYHEAD_ID)
            first, last = getattr(self, "_timeline_span", None) or (0.0, self._get_playback_duration_seconds())
            offset = lay.window_offset(current, first, last, width)
            try:
                now = self.getControl(lay.TIME_NOW_ID)
            except Exception:
                now = None
            try:
                head = self.getControl(lay.PLAYHEAD_HEAD_ID)
            except Exception:
                head = None
            if offset < 0:
                playhead.setVisible(False)
                for control in (now, head):
                    if control is not None:
                        control.setVisible(False)
                return
            playhead.setPosition(left + offset - 1, playhead.getY())
            playhead.setVisible(True)
            if head is not None:
                head.setPosition(left + offset - head.getWidth() // 2, head.getY())
                head.setVisible(True)
            if now is not None:
                # the time under the playhead; it gives way to the times of the segment's ends and of the track's
                half = now.getWidth() // 2
                x = left + offset
                clear = int(width * 0.06)
                taken = tuple(getattr(self, "_segment_ticks", ())) + (left, left + width)
                if any(abs(x - other) < clear for other in taken):
                    now.setVisible(False)
                else:
                    now.setPosition(x - half, now.getY())
                    now.setLabel("[B]%s[/B]" % lay.clock(current))
                    now.setVisible(True)
        except Exception:
            pass

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
            self._T(41019, "Merge with previous segment"),
            self._T(41020, "Merge with next segment"),
        ]
        try:
            picked = show_editor_list_pick(self._T(41018, "Merge segment"), options)
        except Exception:
            try:
                picked = xbmcgui.Dialog().select(self._T(41018, "Merge segment"), options)
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
            xbmcgui.Dialog().ok(self._T(41000, "Segment Editor"), self._T(41021, "No segments available."))
            return
        if idx <= 0:
            xbmcgui.Dialog().ok(
                self._T(41000, "Segment Editor"),
                self._T(41022, "Cannot merge with previous segment — there is no prior segment."),
            )
            return
        self._merge_adjacent_segments(idx - 1, idx)

    def merge_with_next_segment(self):
        self._refresh_selected_index()
        idx = self.selected_index
        if not self.segments:
            xbmcgui.Dialog().ok(self._T(41000, "Segment Editor"), self._T(41021, "No segments available."))
            return
        if idx < 0 or idx >= len(self.segments) - 1:
            xbmcgui.Dialog().ok(
                self._T(41000, "Segment Editor"),
                self._T(41023, "Cannot merge with next segment — there is no following segment."),
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
            xbmcgui.Dialog().ok(self._T(41000, "Segment Editor"), self._T(41024, "Cannot merge segments: %s", exc))
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
            xbmcgui.Dialog().ok(self._T(41000, "Segment Editor"), self._T(41025, "Please select a segment first."))
            return
        if not self.player.isPlayingVideo():
            xbmcgui.Dialog().ok(
                self._T(41000, "Segment Editor"),
                self._T(41026, "Cannot split — video is not playing."),
            )
            return
        idx = self.selected_index
        seg = self.segments[idx]
        split_at = float(self.player.getTime())
        if split_at <= seg.start_seconds or split_at >= seg.end_seconds:
            xbmcgui.Dialog().ok(
                self._T(41000, "Segment Editor"),
                self._T(41027, "Playhead must be strictly inside the selected segment.\n\nSegment: %s to %s\nPlayhead: %s",
                    seconds_to_hms(seg.start_seconds), seconds_to_hms(seg.end_seconds), seconds_to_hms(split_at)),
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
            xbmcgui.Dialog().ok(self._T(41000, "Segment Editor"), self._T(41028, "Cannot split segment: %s", exc))
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
            xbmcgui.Dialog().ok(self._T(41000, "Segment Editor"), self._T(41025, "Please select a segment first."))
            return
        idx = self.selected_index
        nested_indices, overlapping_indices = self._compute_segment_overlap_sets()
        if idx in nested_indices:
            xbmcgui.Dialog().ok(
                self._T(41000, "Segment Editor"),
                self._T(41029, "Fix overlap does not apply to nested segments.\nUse merge or manual edit instead."),
            )
            return
        if idx not in overlapping_indices:
            xbmcgui.Dialog().ok(
                self._T(41000, "Segment Editor"),
                self._T(41030, "The selected segment is not flagged as overlapping."),
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
                self._T(41000, "Segment Editor"),
                self._T(41031, "Could not fix overlap automatically for this segment."),
            )
            return
        if new_end <= new_start:
            xbmcgui.Dialog().ok(
                self._T(41000, "Segment Editor"),
                self._T(41032, "Fix overlap would remove the segment entirely.\nUse merge or delete instead."),
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
        self._update_timeline_selection()
        if not getattr(self, "_row_buttons_follow", True):
            return  # the new layouts keep these buttons where the skin file puts them
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
            xbmcgui.Dialog().ok(self._T(41000, "Segment Editor"), self._T(41033, "No current playback time available."))
            return

        duration_str = xbmcgui.Dialog().input(
            self._T(41034, "Segment Duration (seconds)"),
            defaultt="30",
        )
        if not duration_str:
            return

        try:
            duration = float(duration_str)
            if duration <= 0:
                xbmcgui.Dialog().ok(self._T(41000, "Segment Editor"), self._T(41035, "Duration must be greater than zero."))
                return
            start = self.current_time
            end = start + duration

            label = self.get_label_from_user()
            if label is None:
                return

            source = new_segment_source()

            new_seg = SegmentItem(start, end, label, source=source)
            self._push_undo()
            self.segments.append(new_seg)
            self.segments_modified = True
            self.refresh_list(highlight=new_seg)
            log(f"Added segment at current time: {new_seg}")
        except ValueError:
            xbmcgui.Dialog().ok(self._T(41000, "Segment Editor"), self._T(41036, "Invalid duration value."))

    def add_segment(self):
        """Add a new segment via manual start/end entry."""
        if self.pending_start_time is not None and self.pending_end_time is not None:
            if xbmcgui.Dialog().yesno(
                self._T(41000, "Segment Editor"),
                self._T(41037, "You have marked start and end times.\n\nUse 'Add with Marked Times' instead?"),
            ):
                self.add_with_marked_times()
                return

        default_start = "0"
        if self.pending_start_time is not None:
            default_start = seconds_to_hms(self.pending_start_time)
        elif self.current_time > 0:
            default_start = seconds_to_hms(self.current_time)

        start_str = xbmcgui.Dialog().input(
            self._T(41038, "Start Time (HH:MM:SS.mmm or seconds)"),
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
            self._T(41039, "End Time (HH:MM:SS.mmm or seconds)"),
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
                xbmcgui.Dialog().ok(self._T(41000, "Segment Editor"), self._T(41040, "End time must be after start time."))
                return

            source = new_segment_source()

            new_seg = SegmentItem(start, end, label, source=source)
            self._push_undo()
            self.segments.append(new_seg)
            self.segments_modified = True
            self.refresh_list(highlight=new_seg)
            log(f"Added segment: {new_seg}")
        except ValueError as e:
            xbmcgui.Dialog().ok(self._T(41000, "Segment Editor"), self._T(41041, "Invalid input: %s", e))

    def edit_segment(self):
        self._refresh_selected_index()
        if self.selected_index < 0 or self.selected_index >= len(self.segments):
            xbmcgui.Dialog().ok(self._T(41000, "Segment Editor"), self._T(41042, "Please select a segment to edit."))
            return

        seg = self.segments[self.selected_index]

        if self.pending_start_time is not None and self.pending_end_time is not None:
            if xbmcgui.Dialog().yesno(
                self._T(41000, "Segment Editor"),
                self._T(41043, "You have marked start and end times.\n\nUse marked times for this segment?"),
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
                xbmcgui.Dialog().ok(self._T(41000, "Segment Editor"), self._T(41040, "End time must be after start time."))
                return

        default_start = seconds_to_hms(seg.start_seconds)
        if self.pending_start_time is not None:
            default_start = seconds_to_hms(self.pending_start_time)
        start_str = xbmcgui.Dialog().input(
            self._T(41038, "Start Time (HH:MM:SS.mmm or seconds)"),
            defaultt=default_start,
        )
        if not start_str:
            return

        default_end = seconds_to_hms(seg.end_seconds)
        if self.pending_end_time is not None:
            default_end = seconds_to_hms(self.pending_end_time)
        end_str = xbmcgui.Dialog().input(
            self._T(41039, "End Time (HH:MM:SS.mmm or seconds)"),
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
                xbmcgui.Dialog().ok(self._T(41000, "Segment Editor"), self._T(41040, "End time must be after start time."))
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
            xbmcgui.Dialog().ok(self._T(41000, "Segment Editor"), self._T(41041, "Invalid input: %s", e))

    def snap_segment_start(self):
        """Move segment start to 0 (first) or previous segment's end (timeline order)."""
        self._refresh_selected_index()
        if not self.segments or self.selected_index < 0 or self.selected_index >= len(
            self.segments
        ):
            xbmcgui.Dialog().ok(self._T(41000, "Segment Editor"), self._T(41025, "Please select a segment first."))
            return
        idx = self.selected_index
        seg = self.segments[idx]
        if idx == 0:
            new_start = 0.0
        else:
            new_start = float(self.segments[idx - 1].end_seconds)
        if new_start >= seg.end_seconds:
            xbmcgui.Dialog().ok(
                self._T(41000, "Segment Editor"),
                self._T(41044, "Cannot snap: start would not be before the segment end time.\n\nEnd: %s\nSnap target: %s",
                    seconds_to_hms(seg.end_seconds), seconds_to_hms(new_start)),
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
            xbmcgui.Dialog().ok(self._T(41000, "Segment Editor"), self._T(41025, "Please select a segment first."))
            return
        idx = self.selected_index
        n = len(self.segments)
        seg = self.segments[idx]
        if idx == n - 1:
            new_end = self._get_playback_duration_seconds()
            if new_end <= 0:
                xbmcgui.Dialog().ok(
                    self._T(41000, "Segment Editor"),
                    self._T(41045, "Cannot snap end to video length: duration is not available. Ensure the video is playing."),
                )
                return
        else:
            new_end = float(self.segments[idx + 1].start_seconds)
        if new_end <= seg.start_seconds:
            xbmcgui.Dialog().ok(
                self._T(41000, "Segment Editor"),
                self._T(41046, "Cannot snap: end would not be after the segment start time.\n\nStart: %s\nSnap target: %s",
                    seconds_to_hms(seg.start_seconds), seconds_to_hms(new_end)),
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
            xbmcgui.Dialog().ok(self._T(41000, "Segment Editor"), self._T(41025, "Please select a segment first."))
            return
        if not self.player.isPlayingVideo():
            xbmcgui.Dialog().ok(
                self._T(41000, "Segment Editor"),
                self._T(41047, "Cannot set start to current time: video is not playing."),
            )
            return
        idx = self.selected_index
        seg = self.segments[idx]
        new_start = float(self.player.getTime())
        if new_start >= seg.end_seconds:
            xbmcgui.Dialog().ok(
                self._T(41000, "Segment Editor"),
                self._T(41048, "Cannot set start to current time: playhead is not before the segment end.\n\nEnd: %s\nCurrent: %s",
                    seconds_to_hms(seg.end_seconds), seconds_to_hms(new_start)),
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
            xbmcgui.Dialog().ok(self._T(41000, "Segment Editor"), self._T(41025, "Please select a segment first."))
            return
        if not self.player.isPlayingVideo():
            xbmcgui.Dialog().ok(
                self._T(41000, "Segment Editor"),
                self._T(41049, "Cannot set end to current time: video is not playing."),
            )
            return
        idx = self.selected_index
        seg = self.segments[idx]
        new_end = float(self.player.getTime())
        if new_end <= seg.start_seconds:
            xbmcgui.Dialog().ok(
                self._T(41000, "Segment Editor"),
                self._T(41050, "Cannot set end to current time: playhead is not after the segment start.\n\nStart: %s\nCurrent: %s",
                    seconds_to_hms(seg.start_seconds), seconds_to_hms(new_end)),
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
            xbmcgui.Dialog().ok(self._T(41000, "Segment Editor"), self._T(41051, "Please select a segment to delete."))
            return

        seg = self.segments[self.selected_index]
        label = seg.raw_label if hasattr(seg, 'raw_label') else seg.segment_type_label

        if xbmcgui.Dialog().yesno(self._T(41000, "Segment Editor"), self._T(41052, "Delete segment '%s'?", label)):
            self._push_undo()
            del self.segments[self.selected_index]
            self.segments_modified = True
            self.refresh_list()
            log(f"Deleted segment: {label}")

    def delete_all_segments(self):
        if not self.segments:
            xbmcgui.Dialog().ok(self._T(41000, "Segment Editor"), self._T(41053, "There are no segments to delete."))
            return
        if xbmcgui.Dialog().yesno(
            self._T(41000, "Segment Editor"),
            self._T(41054, "Delete all %d segments?", len(self.segments)),
            yeslabel=self._T(41055, "Delete All"),
            nolabel=self._T(35019, "Cancel"),
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
            self._T(41000, "Segment Editor"),
            self._T(41056, "You have unsaved changes.\nExit without saving?"),
            yeslabel=self._T(35018, "Yes"),
            nolabel=self._T(35019, "Cancel"),
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
                xbmcgui.Dialog().ok(self._T(41000, "Segment Editor"), self._T(41057, "Cannot jump - video is not playing."))
                return

            current = self.player.getTime()
            current_hms = seconds_to_hms(current)

            time_str = xbmcgui.Dialog().input(
                self._T(41058, "Jump To Time (HH:MM:SS.mmm or seconds)"),
                defaultt=current_hms,
            )
            if not time_str:
                return

            try:
                target_time = hms_to_seconds(time_str)
                if target_time < 0:
                    xbmcgui.Dialog().ok(self._T(41000, "Segment Editor"), self._T(41059, "Time cannot be negative."))
                    return
                self.player.seekTime(target_time)
                log(f"Jumped to time: {target_time:.2f}s")
                xbmcgui.Dialog().notification(
                    self._T(41000, "Segment Editor"),
                    self._T(41060, "Jumped to %s", seconds_to_hms(target_time)),
                    icon=self.icon_path,
                    time=2000,
                )
            except ValueError as e:
                xbmcgui.Dialog().ok(
                    self._T(41000, "Segment Editor"),
                    self._T(41061, "Invalid time format. %s", e),
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
                    self._T(41000, "Segment Editor"), self._T(41062, "Start time cleared"),
                    icon=self.icon_path, time=2000,
                )
                return

            if self.player.isPlayingVideo():
                new_start = self.player.getTime()
                if (self.pending_end_time is not None
                        and new_start >= self.pending_end_time):
                    xbmcgui.Dialog().ok(
                        self._T(41000, "Segment Editor"),
                        self._T(41063, "Cannot set start time after end time.\n\nStart: %s\nEnd: %s",
                            seconds_to_hms(new_start), seconds_to_hms(self.pending_end_time)),
                    )
                    return
                self.pending_start_time = new_start
                log(f"Marked start time: {self.pending_start_time:.2f}")
                xbmcgui.Dialog().notification(
                    self._T(41000, "Segment Editor"),
                    self._T(41064, "Start marked: %s", seconds_to_hms(self.pending_start_time)),
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
                    self._T(41000, "Segment Editor"), self._T(41065, "End time cleared"),
                    icon=self.icon_path, time=2000,
                )
                return

            if self.player.isPlayingVideo():
                new_end = self.player.getTime()
                if (self.pending_start_time is not None
                        and new_end <= self.pending_start_time):
                    xbmcgui.Dialog().ok(
                        self._T(41000, "Segment Editor"),
                        self._T(41066, "Cannot set end time before start time.\n\nStart: %s\nEnd: %s",
                            seconds_to_hms(self.pending_start_time), seconds_to_hms(new_end)),
                    )
                    return
                self.pending_end_time = new_end
                log(f"Marked end time: {self.pending_end_time:.2f}")
                xbmcgui.Dialog().notification(
                    self._T(41000, "Segment Editor"),
                    self._T(41067, "End marked: %s", seconds_to_hms(self.pending_end_time)),
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
                    self._T(41000, "Segment Editor"),
                    self._T(41063, "Cannot set start time after end time.\n\nStart: %s\nEnd: %s",
                        seconds_to_hms(0.0), seconds_to_hms(self.pending_end_time)),
                )
                return
            self.pending_start_time = 0.0
            log("Marked start time at SOF (0.0)")
            xbmcgui.Dialog().notification(
                self._T(41000, "Segment Editor"),
                self._T(41064, "Start marked: %s", seconds_to_hms(self.pending_start_time)),
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
                    self._T(41000, "Segment Editor"),
                    self._T(41045, "Cannot snap end to video length: duration is not available. Ensure the video is playing."),
                )
                return
            if (self.pending_start_time is not None
                    and duration <= self.pending_start_time):
                xbmcgui.Dialog().ok(
                    self._T(41000, "Segment Editor"),
                    self._T(41066, "Cannot set end time before start time.\n\nStart: %s\nEnd: %s",
                        seconds_to_hms(self.pending_start_time), seconds_to_hms(duration)),
                )
                return
            self.pending_end_time = duration
            log(f"Marked end time at EOF ({duration:.2f})")
            xbmcgui.Dialog().notification(
                self._T(41000, "Segment Editor"),
                self._T(41067, "End marked: %s", seconds_to_hms(self.pending_end_time)),
                icon=self.icon_path, time=2000,
            )
        except Exception as e:
            log_error(f"Error setting end to EOF: {e}")

    def select_segment_from_list(self, title):
        if not self.segments:
            xbmcgui.Dialog().ok(self._T(41000, "Segment Editor"), self._T(41068, "No segments available to select."))
            return None

        options = []
        for i, seg in enumerate(self.segments):
            label = seg.raw_label if hasattr(seg, 'raw_label') else seg.segment_type_label
            options.append(
                self._T(41069, "Segment %d: %s (%s -> %s)", i+1, label,
                    seconds_to_hms(seg.start_seconds), seconds_to_hms(seg.end_seconds))
            )

        selected = xbmcgui.Dialog().select(title, options)
        return selected if selected >= 0 else None

    def start_at_end_of_segment(self):
        if not self.segments:
            xbmcgui.Dialog().ok(self._T(41000, "Segment Editor"), self._T(41021, "No segments available."))
            return
        seg_index = self.select_segment_from_list(self._T(41070, "Select Segment (Start at End)"))
        if seg_index is None:
            return

        selected_seg = self.segments[seg_index]
        new_start = selected_seg.end_seconds
        if (self.pending_end_time is not None
                and new_start >= self.pending_end_time):
            xbmcgui.Dialog().ok(
                self._T(41000, "Segment Editor"),
                self._T(41072, "Cannot set start time after end time.\n\nMarked end: %s\nChosen start: %s",
                    seconds_to_hms(self.pending_end_time), seconds_to_hms(new_start)),
            )
            return
        self.pending_start_time = new_start
        xbmcgui.Dialog().notification(
            self._T(41000, "Segment Editor"),
            self._T(41064, "Start marked: %s", seconds_to_hms(self.pending_start_time)),
            icon=self.icon_path, time=2000,
        )

    def end_at_start_of_segment(self):
        if not self.segments:
            xbmcgui.Dialog().ok(self._T(41000, "Segment Editor"), self._T(41021, "No segments available."))
            return
        seg_index = self.select_segment_from_list(self._T(41071, "Select Segment (End at Start)"))
        if seg_index is None:
            return

        selected_seg = self.segments[seg_index]
        new_end = selected_seg.start_seconds
        if (self.pending_start_time is not None
                and new_end <= self.pending_start_time):
            xbmcgui.Dialog().ok(
                self._T(41000, "Segment Editor"),
                self._T(41073, "Cannot set end time before start time.\n\nMarked start: %s\nChosen end: %s",
                    seconds_to_hms(self.pending_start_time), seconds_to_hms(new_end)),
            )
            return
        self.pending_end_time = new_end
        xbmcgui.Dialog().notification(
            self._T(41000, "Segment Editor"),
            self._T(41067, "End marked: %s", seconds_to_hms(self.pending_end_time)),
            icon=self.icon_path, time=2000,
        )

    def get_predefined_labels(self):
        try:
            return get_custom_segment_keyword_labels(get_addon())
        except Exception:
            return get_custom_segment_keyword_labels(None)

    def get_label_from_user(self, default=""):
        predefined = self.get_predefined_labels()
        options = [self._T(41074, "Custom...")] + predefined
        selected = _select_segment_label_from_list(options, style=getattr(self, "_style", None))
        if selected is None:
            selected = xbmcgui.Dialog().select(self._T(41075, "Select Segment Label"), options)

        if selected == 0:
            label = xbmcgui.Dialog().input(
                self._T(41076, "Enter Custom Label"),
                defaultt=default or "segment",
            )
            return label if label else (default or "segment")
        if selected > 0:
            return predefined[selected - 1]
        return None

    def add_with_marked_times(self):
        if self.pending_start_time is None or self.pending_end_time is None:
            xbmcgui.Dialog().ok(
                self._T(41000, "Segment Editor"),
                self._T(41077, "Please mark both start and end times first."),
            )
            return
        if self.pending_end_time <= self.pending_start_time:
            xbmcgui.Dialog().ok(
                self._T(41000, "Segment Editor"),
                self._T(41040, "End time must be after start time."),
            )
            return

        label = self.get_label_from_user()
        if label is None:
            return

        source = new_segment_source()

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

        self.refresh_list(highlight=new_seg)
        log(f"Added segment with marked times: {new_seg}")
        xbmcgui.Dialog().notification(
            self._T(41000, "Segment Editor"), self._T(41078, "Segment added successfully"),
            icon=self.icon_path, time=2000,
        )

    def save_current_segments(self):
        """Save the current segments via the shared save-format dispatcher."""
        log(f"save_current_segments() called with {len(self.segments)} segments")
        if not self.video_path:
            xbmcgui.Dialog().ok(self._T(41000, "Segment Editor"), self._T(41079, "No video path available for saving."))
            return
        if not self.segments:
            xbmcgui.Dialog().ok(self._T(41000, "Segment Editor"), self._T(41080, "No segments to save."))
            return

        save_format = get_save_format()
        try:
            edl_ok, xml_ok = save_segments(self.video_path, self.segments, save_format)
        except Exception as e:
            log_error(f"Error saving segments: {e}")
            import traceback
            log_error(f"Traceback: {traceback.format_exc()}")
            xbmcgui.Dialog().ok(self._T(41000, "Segment Editor"), self._T(41081, "Error saving segments: %s", e))
            return

        if edl_ok or xml_ok:
            self.segments_modified = False
            self._undo_stack.clear()
            self._update_undo_button()
            if save_format == SAVE_FORMAT_BOTH:
                if edl_ok and xml_ok:
                    msg = self._T(41082, "Segments saved to both formats")
                elif edl_ok:
                    msg = self._T(41083, "Segments saved to EDL (XML failed)")
                else:
                    msg = self._T(41084, "Segments saved to XML (EDL failed)")
            else:
                msg = self._T(41085, "Segments saved successfully")
            xbmcgui.Dialog().notification(
                self._T(41000, "Segment Editor"), msg,
                icon=self.icon_path, time=2000,
            )
        else:
            xbmcgui.Dialog().ok(
                self._T(41000, "Segment Editor"),
                self._T(41086, "Failed to save segments. Check file permissions."),
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
