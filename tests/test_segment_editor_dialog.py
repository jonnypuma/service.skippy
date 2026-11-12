# -*- coding: utf-8 -*-
"""The Segment Editor window: list, selection, every segment operation, marking, undo and save."""

import sys
import types
import unittest
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

from tests import fake_gui  # noqa: E402
from tests.fake_gui import dialog_calls  # noqa: E402

LIST = 5000
UNDO = 5040


def _ok_texts():
    return [args[1] for args in dialog_calls("ok")]


def _notification_texts():
    return [args[1] for args in dialog_calls("notification")]


class _EditorTest(unittest.TestCase):
    def setUp(self):
        fake_gui.reset()
        self.addCleanup(fake_gui.reset)
        self.m = fake_gui.load("segment_editor_dialog", self)
        patcher = patch.object(self.m, "set_editor_modal_open")
        self.modal_flag = patcher.start()
        self.addCleanup(patcher.stop)

    def seg(self, start, end, label="intro", source="edl", action_type=None):
        return self.m.SegmentItem(start, end, label, source=source, action_type=action_type)

    def editor(self, *segments, selected=0, playing=True, time=0.0, duration=0.0):
        d = self.m.SegmentEditorDialog(
            "SegmentEditorDialog.xml", "/addon", "default",
            video_path="/videos/movie.mkv", segments=list(segments),
        )
        d.player = MagicMock()
        d.player.isPlayingVideo.return_value = playing
        d.player.getTime.return_value = time
        d.player.getTotalTime.return_value = duration
        d.list_control = fake_gui.with_id(fake_gui.ControlList(), LIST)
        d.addControl(d.list_control)
        for cid in self.m._LIST_ROW_ACTION_IDS + (UNDO, 5018):
            d.addControl(fake_gui.with_id(fake_gui.ControlButton(0, 0, 10, 10, ""), cid))
        d.refresh_list()
        d.list_control.selectItem(selected)
        d.selected_index = selected if segments else -1
        return d

    def times(self, d):
        return [(s.start_seconds, s.end_seconds) for s in d.segments]

    def answer(self, *values):
        fake_gui.Dialog.answers = list(values)


class ListTests(_EditorTest):
    def test_list_is_sorted_and_labelled(self):
        d = self.editor(self.seg(100, 130, "credits"), self.seg(0, 30, "intro"))
        self.assertEqual(self.times(d), [(0, 30), (100, 130)])
        items = d.list_control.items
        self.assertEqual(len(items), 2)
        self.assertIn("Segment 1", items[0].label)
        self.assertIn("00:00:00.000", items[0].label)
        self.assertIn("Duration: 30.0s | Source: edl", items[0].label2)
        self.assertEqual(items[1].getProperty("segment_num"), "2")
        self.assertEqual(items[1].getProperty("segment_type"), "normal")
        self.assertEqual(d.getProperty("HasSegments"), "true")
        self.assertTrue(d.getControl(5021).visible)

    def test_nested_and_overlapping_rows_are_flagged(self):
        d = self.editor(self.seg(0, 100), self.seg(10, 20), self.seg(90, 150))
        kinds = [i.getProperty("segment_type") for i in d.list_control.items]
        self.assertEqual(kinds, ["overlapping", "nested", "overlapping"])
        self.assertTrue(d.list_control.items[1].label2.endswith(" | Nested"))
        self.assertTrue(d.list_control.items[0].label2.endswith(" | Overlapping"))

    def test_empty_list_hides_the_row_buttons(self):
        d = self.editor()
        self.assertEqual(d.list_control.items, [])
        self.assertEqual(d.selected_index, -1)
        self.assertEqual(d.getProperty("HasSegments"), "false")
        self.assertFalse(d.getControl(5022).visible)
        self.assertFalse(d.getControl(5022).enabled)

    def test_selection_follows_the_same_segment_after_resort(self):
        late = self.seg(500, 520, "credits")
        d = self.editor(self.seg(10, 20), late, selected=1)
        late.start_seconds, late.end_seconds = 1, 5  # now sorts first
        d.refresh_list()
        self.assertIs(d.segments[0], late)
        self.assertEqual(d.selected_index, 0)
        self.assertEqual(d.list_control.selected, 0)

    def test_refresh_without_list_control_is_harmless(self):
        d = self.editor(self.seg(0, 10))
        d.list_control = None
        d.refresh_list()

    def test_overlap_sets(self):
        d = self.editor()
        S = self.seg
        self.assertEqual(d._compute_segment_overlap_sets([S(0, 10), S(10, 20)]), (set(), set()))
        self.assertEqual(d._compute_segment_overlap_sets([S(0, 10), S(5, 20)]), (set(), {0, 1}))
        self.assertEqual(d._compute_segment_overlap_sets([S(0, 10), S(0, 10)]), ({0, 1}, set()))
        # a segment overlapping only a nested one is not flagged
        self.assertEqual(
            d._compute_segment_overlap_sets([S(0, 100), S(50, 60), S(55, 58)]), ({1, 2}, set())
        )

    def test_first_visible_row(self):
        d = self.editor()
        rows = d._visible_list_rows()
        self.assertEqual(rows, 5)
        self.assertEqual(d._first_visible_list_index(0, 0), 0)
        self.assertEqual(d._first_visible_list_index(4, 4), 0)
        self.assertEqual(d._first_visible_list_index(2, 10), 0)
        self.assertEqual(d._first_visible_list_index(7, 10), 3)
        self.assertEqual(d._first_visible_list_index(9, 10), 5)

    def test_row_buttons_follow_the_highlighted_visible_row(self):
        segs = [self.seg(i * 10, i * 10 + 5) for i in range(8)]
        d = self.editor(*segs)
        offset = (d._list_item_height - d._edit_delete_btn_height) // 2
        d.list_control.selectItem(2)
        d._update_edit_delete_positions()
        edit = d.getControl(5021)
        self.assertEqual(edit.x, d._edit_btn_left)
        self.assertEqual(edit.y, d._list_top + 2 * d._list_item_height + offset)
        d.list_control.selectItem(7)  # scrolled: last visible row
        d._update_edit_delete_positions()
        self.assertEqual(d.getControl(5022).y, d._list_top + 4 * d._list_item_height + offset)
        self.assertEqual(d.getControl(5022).x, d._delete_btn_left)

    def test_refresh_selected_index_clamps(self):
        d = self.editor(self.seg(0, 10), self.seg(20, 30))
        d.list_control.selectItem(9)
        d._refresh_selected_index()
        self.assertEqual(d.selected_index, 1)
        d.list_control.selectItem(-1)
        d._refresh_selected_index()
        self.assertEqual(d.selected_index, 0)

    def test_focus_on_list_takes_its_selection(self):
        d = self.editor(self.seg(0, 10), self.seg(20, 30))
        d.list_control.selectItem(1)
        d.onFocus(LIST)
        self.assertEqual(d.selected_index, 1)
        d.list_control.selectItem(0)
        d.onFocus(5002)
        self.assertEqual(d.selected_index, 1)


class UndoTests(_EditorTest):
    def test_undo_restores_the_list_and_selection(self):
        d = self.editor(self.seg(0, 10), self.seg(20, 30), selected=1)
        self.assertFalse(d.getControl(UNDO).enabled is True and d._undo_stack)
        self.answer(True)
        d.delete_segment()
        self.assertEqual(self.times(d), [(0, 10)])
        self.assertTrue(d.getControl(UNDO).enabled)
        d.undo_last_change()
        self.assertEqual(self.times(d), [(0, 10), (20, 30)])
        self.assertEqual(d.selected_index, 1)
        self.assertFalse(d.getControl(UNDO).enabled)
        self.assertTrue(d.segments_modified)

    def test_undo_with_nothing_to_undo(self):
        d = self.editor(self.seg(0, 10))
        d.undo_last_change()
        self.assertFalse(d.segments_modified)

    def test_undo_stack_is_capped(self):
        d = self.editor(self.seg(0, 10))
        for _ in range(d._undo_stack_max + 5):
            d._push_undo()
        self.assertEqual(len(d._undo_stack), d._undo_stack_max)

    def test_undo_snapshot_is_a_copy(self):
        d = self.editor(self.seg(0, 10), self.seg(20, 30), selected=0)
        d.snap_segment_end()  # in place: end -> 20
        self.assertEqual(self.times(d)[0], (0, 20))
        d.undo_last_change()
        self.assertEqual(self.times(d)[0], (0, 10))


class MergeTests(_EditorTest):
    def test_same_label_merges_without_asking(self):
        d = self.editor(self.seg(0, 10, "intro", action_type=5), self.seg(12, 30, "Intro"), selected=1)
        with patch.object(d, "get_label_from_user") as ask:
            d.merge_with_previous_segment()
        ask.assert_not_called()
        self.assertEqual(self.times(d), [(0, 30)])
        self.assertEqual(d.segments[0].raw_label, "intro")
        self.assertEqual(d.segments[0].action_type, 5)
        self.assertEqual(d.selected_index, 0)
        self.assertTrue(d.segments_modified)

    def test_different_labels_ask_and_drop_action_type(self):
        d = self.editor(self.seg(0, 10, "intro", action_type=5), self.seg(12, 30, "recap"), selected=0)
        with patch.object(d, "get_label_from_user", return_value="opening") as ask:
            d.merge_with_next_segment()
        ask.assert_called_once_with(default="intro")
        self.assertEqual(self.times(d), [(0, 30)])
        self.assertEqual(d.segments[0].raw_label, "opening")
        self.assertIsNone(d.segments[0].action_type)

    def test_cancelling_the_label_keeps_both(self):
        d = self.editor(self.seg(0, 10, "intro"), self.seg(12, 30, "recap"), selected=0)
        with patch.object(d, "get_label_from_user", return_value=None):
            d.merge_with_next_segment()
        self.assertEqual(len(d.segments), 2)
        self.assertEqual(d._undo_stack, [])

    def test_no_neighbour_messages(self):
        d = self.editor(self.seg(0, 10), self.seg(20, 30), selected=0)
        d.merge_with_previous_segment()
        d.list_control.selectItem(1)
        d.merge_with_next_segment()
        self.assertEqual(len(d.segments), 2)
        texts = _ok_texts()
        self.assertIn("no prior segment", texts[0])
        self.assertIn("no following segment", texts[1])

    def test_no_segments(self):
        d = self.editor()
        d.merge_with_previous_segment()
        d.merge_with_next_segment()
        self.assertEqual(_ok_texts(), ["No segments available."] * 2)

    def test_non_adjacent_merge_is_refused(self):
        d = self.editor(self.seg(0, 10), self.seg(20, 30), self.seg(40, 50))
        d._merge_adjacent_segments(2, 0)
        self.assertEqual(len(d.segments), 3)

    def test_picker_routes_to_previous_or_next(self):
        d = self.editor(self.seg(0, 10), self.seg(20, 30), self.seg(40, 50), selected=1)
        fake_skin = types.ModuleType("skippy_editor_modal_skin")
        for picked, expected in ((0, "merge_with_previous_segment"), (1, "merge_with_next_segment")):
            fake_skin.show_editor_list_pick = MagicMock(return_value=picked)
            with patch.dict(sys.modules, {"skippy_editor_modal_skin": fake_skin}), \
                    patch.object(d, expected) as handler:
                d.show_merge_picker()
            handler.assert_called_once_with()
        fake_skin.show_editor_list_pick = MagicMock(return_value=-1)
        with patch.dict(sys.modules, {"skippy_editor_modal_skin": fake_skin}), \
                patch.object(d, "merge_with_previous_segment") as prev, \
                patch.object(d, "merge_with_next_segment") as nxt:
            d.show_merge_picker()
        prev.assert_not_called()
        nxt.assert_not_called()

    def test_picker_falls_back_to_kodi_select(self):
        d = self.editor(self.seg(0, 10), self.seg(20, 30), selected=1)
        fake_skin = types.ModuleType("skippy_editor_modal_skin")
        fake_skin.show_editor_list_pick = MagicMock(side_effect=RuntimeError)
        self.answer(0)
        with patch.dict(sys.modules, {"skippy_editor_modal_skin": fake_skin}), \
                patch.object(d, "merge_with_previous_segment") as prev:
            d.show_merge_picker()
        prev.assert_called_once_with()


class SplitAndFixTests(_EditorTest):
    def test_split_at_playhead(self):
        d = self.editor(self.seg(0, 60, "intro", action_type=5), time=25.0)
        d.split_at_playhead()
        self.assertEqual(self.times(d), [(0, 25), (25, 60)])
        self.assertEqual([s.raw_label for s in d.segments], ["intro", "intro"])
        self.assertEqual([s.action_type for s in d.segments], [5, 5])
        self.assertEqual(d.selected_index, 1)

    def test_split_needs_playhead_strictly_inside(self):
        for t in (0.0, 60.0, 90.0):
            d = self.editor(self.seg(0, 60), time=t)
            d.split_at_playhead()
            self.assertEqual(len(d.segments), 1)
        self.assertEqual(len(_ok_texts()), 3)
        self.assertIn("strictly inside", _ok_texts()[0])

    def test_split_needs_playback_and_a_selection(self):
        d = self.editor(self.seg(0, 60), playing=False, time=30.0)
        d.split_at_playhead()
        self.editor().split_at_playhead()
        self.assertEqual(_ok_texts(), ["Cannot split — video is not playing.",
                                       "Please select a segment first."])

    def test_fix_overlap_trims_to_neighbours(self):
        d = self.editor(self.seg(0, 10), self.seg(5, 20, "recap"), self.seg(15, 30, "credits"), selected=1)
        d.fix_overlap_selected()
        self.assertEqual(self.times(d), [(0, 10), (10, 15), (15, 30)])
        self.assertTrue(d.segments_modified)
        d.undo_last_change()
        self.assertEqual(self.times(d)[1], (5, 20))

    def test_fix_overlap_on_first_and_last(self):
        d = self.editor(self.seg(0, 10), self.seg(5, 20), selected=0)
        d.fix_overlap_selected()
        self.assertEqual(self.times(d), [(0, 5), (5, 20)])
        d = self.editor(self.seg(0, 10), self.seg(5, 20), selected=1)
        d.fix_overlap_selected()
        self.assertEqual(self.times(d), [(0, 10), (10, 20)])

    def test_fix_overlap_refuses_nested_and_clean_segments(self):
        d = self.editor(self.seg(0, 100), self.seg(10, 20), selected=1)
        d.fix_overlap_selected()
        d = self.editor(self.seg(0, 10), self.seg(20, 30), selected=0)
        d.fix_overlap_selected()
        texts = _ok_texts()
        self.assertIn("nested", texts[0])
        self.assertIn("not flagged as overlapping", texts[1])


class SnapAndCurrentTimeTests(_EditorTest):
    def test_snap_start(self):
        d = self.editor(self.seg(5, 10), self.seg(20, 30), selected=0)
        d.snap_segment_start()
        self.assertEqual(self.times(d)[0], (0, 10))
        d.list_control.selectItem(1)
        d.snap_segment_start()
        self.assertEqual(self.times(d)[1], (10, 30))

    def test_snap_start_refused_when_previous_ends_after(self):
        d = self.editor(self.seg(0, 50), self.seg(20, 30), selected=1)
        d.snap_segment_start()
        self.assertEqual(self.times(d)[1], (20, 30))
        self.assertIn("Cannot snap", _ok_texts()[0])

    def test_snap_end(self):
        d = self.editor(self.seg(0, 10), self.seg(20, 30), selected=0, duration=3600.0)
        d.snap_segment_end()
        self.assertEqual(self.times(d)[0], (0, 20))
        d.list_control.selectItem(1)
        d.snap_segment_end()
        self.assertEqual(self.times(d)[1], (20, 3600))

    def test_snap_end_of_last_needs_a_duration(self):
        d = self.editor(self.seg(0, 10), duration=0.0)
        d.snap_segment_end()
        self.assertEqual(self.times(d), [(0, 10)])
        self.assertIn("duration is not available", _ok_texts()[0])

    def test_snap_end_refused_when_next_starts_before(self):
        d = self.editor(self.seg(10, 20), self.seg(10, 30), selected=0)
        d.snap_segment_end()
        self.assertIn("Cannot snap", _ok_texts()[0])

    def test_snap_without_selection(self):
        d = self.editor()
        d.snap_segment_start()
        d.snap_segment_end()
        self.assertEqual(_ok_texts(), ["Please select a segment first."] * 2)

    def test_start_and_end_to_current(self):
        d = self.editor(self.seg(10, 60), time=20.0)
        d.set_segment_start_to_current()
        self.assertEqual(self.times(d), [(20, 60)])
        d.player.getTime.return_value = 45.0
        d.set_segment_end_to_current()
        self.assertEqual(self.times(d), [(20, 45)])
        self.assertEqual(len(d._undo_stack), 2)

    def test_current_time_guards(self):
        d = self.editor(self.seg(10, 60), time=70.0)
        d.set_segment_start_to_current()
        d.player.getTime.return_value = 5.0
        d.set_segment_end_to_current()
        self.assertEqual(self.times(d), [(10, 60)])
        d.player.isPlayingVideo.return_value = False
        d.set_segment_start_to_current()
        d.set_segment_end_to_current()
        texts = _ok_texts()
        self.assertIn("not before the segment end", texts[0])
        self.assertIn("not after the segment start", texts[1])
        self.assertIn("video is not playing", texts[2])
        self.assertIn("video is not playing", texts[3])


class AddEditDeleteTests(_EditorTest):
    def test_add_segment_by_typing_times(self):
        d = self.editor(self.seg(0, 10))
        self.answer("100", "1:00:00")
        with patch.object(d, "get_label_from_user", return_value="credits"):
            d.add_segment()
        self.assertEqual(self.times(d), [(0, 10), (100, 3600)])
        self.assertEqual(d.segments[1].source, "edl")
        self.assertTrue(d.segments_modified)

    def test_add_segment_uses_xml_source_when_list_is_xml(self):
        d = self.editor(self.seg(0, 10, source="xml"))
        self.answer("20", "30")
        with patch.object(d, "get_label_from_user", return_value="recap"):
            d.add_segment()
        self.assertEqual(d.segments[1].source, "xml")

    def test_add_segment_defaults_come_from_marks_or_playhead(self):
        d = self.editor()
        d.current_time = 30.0
        with patch.object(d, "get_label_from_user", return_value="x"):
            d.add_segment()  # start input cancelled
        inputs = [kw.get("defaultt") for k, _a, kw in fake_gui.Dialog.calls if k == "input"]
        self.assertEqual(inputs, ["00:00:30.000"])
        fake_gui.Dialog.calls = []
        d.pending_start_time = 5.0
        self.answer("5", "")
        d.add_segment()
        inputs = [kw.get("defaultt") for k, _a, kw in fake_gui.Dialog.calls if k == "input"]
        self.assertEqual(inputs, ["00:00:05.000", "00:01:00.000"])
        self.assertEqual(d.segments, [])

    def test_add_segment_rejects_bad_times(self):
        d = self.editor()
        self.answer("50", "40")
        with patch.object(d, "get_label_from_user", return_value="x"):
            d.add_segment()
        self.answer("abc", "40")
        with patch.object(d, "get_label_from_user", return_value="x"):
            d.add_segment()
        self.assertEqual(d.segments, [])
        texts = _ok_texts()
        self.assertEqual(texts[0], "End time must be after start time.")
        self.assertTrue(texts[1].startswith("Invalid input:"))

    def test_add_segment_offers_marked_times(self):
        d = self.editor()
        d.pending_start_time, d.pending_end_time = 10.0, 20.0
        self.answer(True)
        with patch.object(d, "add_with_marked_times") as marked:
            d.add_segment()
        marked.assert_called_once_with()

    def test_add_at_current_time(self):
        d = self.editor()
        d.current_time = 100.0
        self.answer("45")
        with patch.object(d, "get_label_from_user", return_value="recap"):
            d.add_at_current_time()
        self.assertEqual(self.times(d), [(100, 145)])

    def test_add_at_current_time_guards(self):
        d = self.editor()
        d.add_at_current_time()  # no playback time
        d.current_time = 100.0
        self.answer("0")
        d.add_at_current_time()
        self.answer("soon")
        d.add_at_current_time()
        self.assertEqual(d.segments, [])
        self.assertEqual(_ok_texts(), [
            "No current playback time available.",
            "Duration must be greater than zero.",
            "Invalid duration value.",
        ])

    def test_add_with_marked_times(self):
        d = self.editor(self.seg(0, 5, source="xml"))
        d.pending_start_time, d.pending_end_time = 10.0, 20.0
        with patch.object(d, "get_label_from_user", return_value="recap"):
            d.add_with_marked_times()
        self.assertEqual(self.times(d), [(0, 5), (10, 20)])
        self.assertEqual(d.segments[1].source, "xml")
        self.assertIsNone(d.pending_start_time)
        self.assertIsNone(d.pending_end_time)
        self.assertIn("Segment added successfully", _notification_texts())

    def test_add_with_marked_times_guards(self):
        d = self.editor()
        d.add_with_marked_times()
        d.pending_start_time, d.pending_end_time = 20.0, 10.0
        d.add_with_marked_times()
        d.pending_end_time = 30.0
        with patch.object(d, "get_label_from_user", return_value=None):
            d.add_with_marked_times()
        self.assertEqual(d.segments, [])
        self.assertEqual(d.pending_start_time, 20.0)  # kept when cancelled
        self.assertEqual(_ok_texts(), ["Please mark both start and end times first.",
                                       "End time must be after start time."])

    def test_edit_segment_changes_times_and_label(self):
        d = self.editor(self.seg(10, 20, "intro", action_type=5))
        self.answer("15", "25")
        with patch.object(d, "get_label_from_user", return_value=" Recap ") as ask:
            d.edit_segment()
        ask.assert_called_once_with(default="intro")
        seg = d.segments[0]
        self.assertEqual((seg.start_seconds, seg.end_seconds), (15, 25))
        self.assertEqual(seg.raw_label, "Recap")
        self.assertIsNone(seg.action_type)  # label changed -> mapping decides

    def test_edit_segment_same_label_keeps_action_type(self):
        d = self.editor(self.seg(10, 20, "intro", action_type=5))
        self.answer("10", "30")
        with patch.object(d, "get_label_from_user", return_value="intro"):
            d.edit_segment()
        self.assertEqual(d.segments[0].action_type, 5)

    def test_edit_segment_with_marked_times(self):
        d = self.editor(self.seg(10, 20))
        d.pending_start_time, d.pending_end_time = 30.0, 40.0
        self.answer(True)
        d.edit_segment()
        self.assertEqual(self.times(d), [(30, 40)])
        self.assertIsNone(d.pending_start_time)

    def test_edit_segment_guards(self):
        self.editor().edit_segment()
        d = self.editor(self.seg(10, 20))
        self.answer("30", "25")
        with patch.object(d, "get_label_from_user", return_value="intro"):
            d.edit_segment()
        self.assertEqual(self.times(d), [(10, 20)])
        self.assertEqual(_ok_texts(), ["Please select a segment to edit.",
                                       "End time must be after start time."])

    def test_delete_asks_first(self):
        d = self.editor(self.seg(0, 10, "intro"), self.seg(20, 30, "recap"), selected=1)
        self.answer(False)
        d.delete_segment()
        self.assertEqual(len(d.segments), 2)
        self.answer(True)
        d.delete_segment()
        self.assertEqual([s.raw_label for s in d.segments], ["intro"])
        questions = [a[1] for a in dialog_calls("yesno")]
        self.assertEqual(questions, ["Delete segment 'recap'?"] * 2)

    def test_delete_all(self):
        d = self.editor(self.seg(0, 10), self.seg(20, 30))
        self.answer(True)
        d.delete_all_segments()
        self.assertEqual(d.segments, [])
        self.assertEqual(d.selected_index, -1)
        self.editor().delete_all_segments()
        self.assertEqual(_ok_texts(), ["There are no segments to delete."])
        self.assertIn("Delete all 2 segments?", [a[1] for a in dialog_calls("yesno")])


class LabelPickTests(_EditorTest):
    def test_label_picker(self):
        d = self.editor()
        with patch.object(d, "get_predefined_labels", return_value=["Intro", "Recap"]), \
                patch.object(self.m, "_select_segment_label_from_list", return_value=2):
            self.assertEqual(d.get_label_from_user(), "Recap")
        with patch.object(d, "get_predefined_labels", return_value=["Intro"]), \
                patch.object(self.m, "_select_segment_label_from_list", return_value=-1):
            self.assertIsNone(d.get_label_from_user())

    def test_custom_label(self):
        d = self.editor()
        with patch.object(d, "get_predefined_labels", return_value=["Intro"]), \
                patch.object(self.m, "_select_segment_label_from_list", return_value=0):
            self.answer("Cold open")
            self.assertEqual(d.get_label_from_user(), "Cold open")
            self.answer("")
            self.assertEqual(d.get_label_from_user(default="recap"), "recap")
            self.answer("")
            self.assertEqual(d.get_label_from_user(), "segment")

    def test_falls_back_to_kodi_select(self):
        d = self.editor()
        self.answer(1)
        with patch.object(d, "get_predefined_labels", return_value=["Intro"]), \
                patch.object(self.m, "_select_segment_label_from_list", return_value=None):
            self.assertEqual(d.get_label_from_user(), "Intro")
        options = dialog_calls("select")[0][1]
        self.assertEqual(options, ["Custom...", "Intro"])

    def test_skinned_picker_unavailable_without_addon(self):
        with patch.object(self.m, "get_addon", return_value=None):
            self.assertIsNone(self.m._select_segment_label_from_list(["a"]))


class MarkingTests(_EditorTest):
    def test_mark_start_and_end_then_clear(self):
        d = self.editor(time=12.0)
        d.set_as_start()
        self.assertEqual(d.pending_start_time, 12.0)
        d.player.getTime.return_value = 40.0
        d.set_as_end()
        self.assertEqual(d.pending_end_time, 40.0)
        d.set_as_start()
        d.set_as_end()
        self.assertIsNone(d.pending_start_time)
        self.assertIsNone(d.pending_end_time)
        self.assertEqual(_notification_texts(), [
            "Start marked: 00:00:12.000", "End marked: 00:00:40.000",
            "Start time cleared", "End time cleared",
        ])

    def test_marks_must_stay_in_order(self):
        d = self.editor(time=50.0)
        d.pending_end_time = 40.0
        d.set_as_start()
        self.assertIsNone(d.pending_start_time)
        d = self.editor(time=5.0)
        d.pending_start_time = 10.0
        d.set_as_end()
        self.assertIsNone(d.pending_end_time)
        texts = _ok_texts()
        self.assertTrue(texts[0].startswith("Cannot set start time after end time."))
        self.assertTrue(texts[1].startswith("Cannot set end time before start time."))

    def test_marking_needs_playback(self):
        d = self.editor(playing=False, time=10.0)
        d.set_as_start()
        d.set_as_end()
        self.assertIsNone(d.pending_start_time)
        self.assertIsNone(d.pending_end_time)

    def test_start_and_end_of_file(self):
        d = self.editor(duration=1800.0)
        d.set_pending_to_sof()
        d.set_pending_to_eof()
        self.assertEqual((d.pending_start_time, d.pending_end_time), (0.0, 1800.0))

    def test_end_of_file_needs_duration_and_order(self):
        d = self.editor(duration=0.0)
        d.set_pending_to_eof()
        self.assertIsNone(d.pending_end_time)
        d = self.editor(duration=100.0)
        d.pending_start_time = 200.0
        d.set_pending_to_eof()
        self.assertIsNone(d.pending_end_time)
        d = self.editor()
        d.pending_end_time = 0.0
        d.set_pending_to_sof()
        self.assertIsNone(d.pending_start_time)
        self.assertEqual(len(_ok_texts()), 3)

    def test_mark_from_another_segment(self):
        d = self.editor(self.seg(0, 30, "intro"), self.seg(600, 700, "credits"))
        self.answer(0, 1)
        d.start_at_end_of_segment()
        d.end_at_start_of_segment()
        self.assertEqual((d.pending_start_time, d.pending_end_time), (30, 600))
        options = dialog_calls("select")[0][1]
        self.assertEqual(options[1], "Segment 2: credits (00:10:00.000 -> 00:11:40.000)")

    def test_mark_from_another_segment_guards(self):
        d = self.editor(self.seg(0, 30), self.seg(600, 700))
        d.pending_end_time = 20.0
        self.answer(0)
        d.start_at_end_of_segment()
        self.assertIsNone(d.pending_start_time)
        d.pending_end_time = None
        d.pending_start_time = 650.0
        self.answer(1)
        d.end_at_start_of_segment()
        self.assertIsNone(d.pending_end_time)
        self.answer(-1)
        d.end_at_start_of_segment()
        e = self.editor()
        e.start_at_end_of_segment()
        e.end_at_start_of_segment()
        self.assertIsNone(e.select_segment_from_list("x"))
        self.assertEqual(len(_ok_texts()), 5)


class PlaybackTests(_EditorTest):
    def test_seek_relative_never_goes_negative(self):
        d = self.editor(time=3.0)
        d.seek_relative(-10)
        d.player.seekTime.assert_called_with(0)
        d.seek_relative(30)
        d.player.seekTime.assert_called_with(33.0)
        d.player.isPlayingVideo.return_value = False
        d.player.seekTime.reset_mock()
        d.seek_relative(5)
        d.player.seekTime.assert_not_called()

    def test_jump_to_segment_start(self):
        d = self.editor(self.seg(0, 10), self.seg(42, 50), selected=1)
        d.jump_to_segment_start()
        d.player.seekTime.assert_called_once_with(42)
        d.player.isPlayingVideo.return_value = False
        d.jump_to_segment_start()
        self.assertEqual(d.player.seekTime.call_count, 1)

    def test_jump_to_time(self):
        d = self.editor(time=10.0)
        self.answer("1:30")
        d.jump_to_time()
        d.player.seekTime.assert_called_once_with(90.0)
        self.assertEqual(_notification_texts(), ["Jumped to 00:01:30.000"])
        inputs = [kw.get("defaultt") for k, _a, kw in fake_gui.Dialog.calls if k == "input"]
        self.assertEqual(inputs, ["00:00:10.000"])

    def test_jump_to_time_rejects_bad_input(self):
        d = self.editor(time=10.0)
        self.answer("soon")
        d.jump_to_time()
        self.answer("")
        d.jump_to_time()
        d.player.seekTime.assert_not_called()
        self.assertTrue(_ok_texts()[0].startswith("Invalid time format."))
        d.player.isPlayingVideo.return_value = False
        d.jump_to_time()
        self.assertEqual(_ok_texts()[-1], "Cannot jump - video is not playing.")

    def test_toggle_pause_only_while_playing(self):
        d = self.editor()
        d.toggle_pause()
        d.player.pause.assert_called_once_with()
        d.player.isPlayingVideo.return_value = False
        d.toggle_pause()
        d.player.pause.assert_called_once_with()

    def test_player_events_drive_the_pause_label(self):
        d = self.editor()
        listener = self.m._EditorPlayerListener(d)
        listener.onPlayBackPaused()
        self.assertTrue(d.is_paused)
        self.assertEqual(d.getControl(5018).label, "Resume")
        listener.onPlayBackResumed()
        self.assertFalse(d.is_paused)
        self.assertEqual(d.getControl(5018).label, "Pause")
        listener.onPlayBackPaused()
        listener.onPlayBackStopped()
        self.assertFalse(d.is_paused)

    def test_duration_only_while_playing(self):
        d = self.editor(duration=99.0)
        self.assertEqual(d._get_playback_duration_seconds(), 99.0)
        d.player.isPlayingVideo.return_value = False
        self.assertEqual(d._get_playback_duration_seconds(), 0.0)
        d.player.isPlayingVideo.side_effect = RuntimeError
        self.assertEqual(d._get_playback_duration_seconds(), 0.0)


class InputTests(_EditorTest):
    def test_buttons_reach_their_handlers(self):
        d = self.editor(self.seg(0, 10))
        for cid, name in ((5022, "delete_segment"), (5021, "edit_segment"),
                          (5006, "save_current_segments"), (5040, "undo_last_change"),
                          (5041, "show_merge_picker"), (5000, "jump_to_segment_start")):
            with patch.object(d, name) as handler:
                d.onClick(cid)
            handler.assert_called_once_with()
        with patch.object(d, "seek_relative") as seek:
            for cid in (5031, 5009, 5019, 5020, 5014, 5036):
                d.onClick(cid)
        self.assertEqual([c.args[0] for c in seek.call_args_list], [-600, -5, -1, 1, 30, 600])
        d.onClick(4242)  # unknown: nothing happens

    def test_every_editor_button_has_a_click_handler(self):
        import inspect
        src = inspect.getsource(self.m.SegmentEditorDialog.onClick)
        for cid in self.m._EDITOR_BUTTON_IDS:
            self.assertIn("%d:" % cid, src, "button %d has no click handler" % cid)

    def test_exit_asks_only_with_unsaved_changes(self):
        d = self.editor(self.seg(0, 10))
        d.onClick(5007)
        self.assertTrue(d.closed)
        self.assertEqual(dialog_calls("yesno"), [])
        self.modal_flag.assert_called_with(False)

    def test_back_with_unsaved_changes(self):
        d = self.editor(self.seg(0, 10))
        d.segments_modified = True
        self.answer(False)
        d.act(fake_gui.ACTION_NAV_BACK)
        self.assertFalse(d.closed)
        self.assertTrue(d.segments_modified)
        self.answer(True)
        d.act(fake_gui.ACTION_PREVIOUS_MENU)
        self.assertTrue(d.closed)
        self.assertFalse(d.segments_modified)

    def test_list_shortcuts(self):
        d = self.editor(self.seg(0, 10))
        d.setFocus(d.list_control)
        for aid, name in ((11, "toggle_pause"), (83, "set_as_start"), (19, "set_as_start"),
                          (69, "set_as_end"), (100, "delete_segment")):
            with patch.object(d, name) as handler:
                d.act(aid)
            handler.assert_called_once_with()

    def test_shortcuts_ignored_off_the_list_and_left_right_ignored(self):
        d = self.editor(self.seg(0, 10))
        d.setFocus(d.getControl(5021))
        with patch.object(d, "delete_segment") as delete:
            d.act(100)
        delete.assert_not_called()
        d.setFocus(d.list_control)
        with patch.object(d, "_schedule_sync_list_selection") as sync:
            d.act(fake_gui.ACTION_MOVE_LEFT)
            d.act(fake_gui.ACTION_MOVE_DOWN)
        sync.assert_called_once_with()

    def test_list_navigation_resyncs_selection(self):
        d = self.editor(self.seg(0, 10), self.seg(20, 30))
        d.setFocus(d.list_control)
        timers = []

        class FakeTimer:
            def __init__(self, _delay, fn):
                self.fn = fn
                self.cancelled = False
                timers.append(self)

            def start(self):
                pass

            def cancel(self):
                self.cancelled = True

        with patch.object(self.m.threading, "Timer", FakeTimer):
            d.act(fake_gui.ACTION_MOVE_DOWN)
            d.act(fake_gui.ACTION_MOVE_DOWN)
        self.assertTrue(timers[0].cancelled)
        d.list_control.selectItem(1)
        timers[1].fn()
        self.assertEqual(d.selected_index, 1)
        self.assertIsNone(d._selection_sync_timer)

    def test_close_cancels_the_pending_resync(self):
        d = self.editor()
        timer = MagicMock()
        d._selection_sync_timer = timer
        d.close()
        timer.cancel.assert_called_once_with()
        self.assertTrue(d._closing)
        self.assertIsNone(d._selection_sync_timer)


class SaveTests(_EditorTest):
    def test_save_messages_per_format(self):
        cases = (
            (self.m.SAVE_FORMAT_BOTH, (True, True), "Segments saved to both formats"),
            (self.m.SAVE_FORMAT_BOTH, (True, False), "Segments saved to EDL (XML failed)"),
            (self.m.SAVE_FORMAT_BOTH, (False, True), "Segments saved to XML (EDL failed)"),
            ("edl", (True, False), "Segments saved successfully"),
        )
        for fmt, result, message in cases:
            fake_gui.Dialog.calls = []
            d = self.editor(self.seg(0, 10))
            d.segments_modified = True
            d._push_undo()
            with patch.object(self.m, "get_save_format", return_value=fmt), \
                    patch.object(self.m, "save_segments", return_value=result) as save:
                d.save_current_segments()
            save.assert_called_once_with("/videos/movie.mkv", d.segments, fmt)
            self.assertEqual(_notification_texts(), [message])
            self.assertFalse(d.segments_modified)
            self.assertEqual(d._undo_stack, [])

    def test_save_failure_keeps_changes(self):
        d = self.editor(self.seg(0, 10))
        d.segments_modified = True
        with patch.object(self.m, "get_save_format", return_value="edl"), \
                patch.object(self.m, "save_segments", return_value=(False, False)):
            d.save_current_segments()
        with patch.object(self.m, "get_save_format", return_value="edl"), \
                patch.object(self.m, "save_segments", side_effect=OSError("read-only")):
            d.save_current_segments()
        self.assertTrue(d.segments_modified)
        self.assertEqual(_ok_texts(), ["Failed to save segments. Check file permissions.",
                                       "Error saving segments: read-only"])

    def test_nothing_to_save(self):
        self.editor().save_current_segments()
        d = self.editor(self.seg(0, 10))
        d.video_path = ""
        d.save_current_segments()
        self.assertEqual(_ok_texts(), ["No segments to save.", "No video path available for saving."])


class UploadTests(_EditorTest):
    def _modules(self, picked):
        upload = types.ModuleType("online_segment_upload")
        upload.TARGET_BOTH, upload.TARGET_THEINTRODB, upload.TARGET_INTRODB_APP = "both", "tidb", "app"
        upload.upload_all_segments = MagicMock()
        skin = types.ModuleType("skippy_editor_modal_skin")
        skin.show_editor_list_pick = MagicMock(return_value=picked)
        skin.show_editor_ok = MagicMock()
        return upload, skin

    def _addon(self, enabled, target=""):
        addon = MagicMock()
        addon.getSetting.side_effect = lambda key: {
            "online_upload_enabled": "true" if enabled else "false",
            "online_upload_default_target": target,
        }[key]
        addon.getLocalizedString.side_effect = lambda sid: "s%d" % sid
        return addon

    def run_upload(self, d, enabled, target, picked):
        upload, skin = self._modules(picked)
        with patch.dict(sys.modules, {"online_segment_upload": upload,
                                      "skippy_editor_modal_skin": skin}), \
                patch.object(self.m, "get_addon", return_value=self._addon(enabled, target)):
            d.upload_segments_online()
        return upload, skin

    def test_disabled_upload_explains_and_stops(self):
        d = self.editor(self.seg(0, 10))
        upload, skin = self.run_upload(d, False, "", 0)
        skin.show_editor_ok.assert_called_once_with("s39013", "s39040")
        upload.upload_all_segments.assert_not_called()

    def test_upload_preselects_the_default_target(self):
        d = self.editor(self.seg(0, 10))
        upload, skin = self.run_upload(d, True, "app", 1)
        skin.show_editor_list_pick.assert_called_once_with(
            "s39009", ["s39010", "s39011", "s39012"], preselect=2)
        upload.upload_all_segments.assert_called_once_with("/videos/movie.mkv", d.segments, "tidb")

    def test_upload_cancel_and_unknown_default(self):
        d = self.editor(self.seg(0, 10))
        upload, skin = self.run_upload(d, True, "nonsense", -1)
        self.assertEqual(skin.show_editor_list_pick.call_args.kwargs["preselect"], 0)
        upload.upload_all_segments.assert_not_called()


if __name__ == "__main__":
    unittest.main()
