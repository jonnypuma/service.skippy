# -*- coding: utf-8 -*-
"""Skip Dialog Customize mock helpers and draft save payload."""

import ast
import os
import struct
import unittest
from unittest.mock import MagicMock

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

from skip_dialog_appearance import (
    COMBINED_FILL_SLICE_ID,
    COMBINED_FILL_STRETCH_ID,
    COMBINED_TRACK_ID,
    COMBINED_TRACK_SLICE_ID,
    COMPACT_PROGRESS_H_720,
    COMPACT_SKIP_CLOSE_W_720,
    COMPACT_SKIP_CONTENT_W_720,
    COMPACT_SKIP_GAP_720,
    FULL_SKIP_MARGIN_720,
    FULL_SKIP_PANEL_W_720,
    FULL_SKIP_PROGRESS_BAR_WIDTH,
    ENDING_TEXT_ARGB,
    JUMP_LABEL_ARGB,
    JUMP_LABEL_FONT,
    MOCK_INTRO_END,
    MOCK_PLAYHEAD,
    MOCK_RECAP_START,
    SKIP_DIALOG_CANVAS_W_720,
    SKIP_DIALOG_SCREEN_MARGIN_720,
    DictSettingsReader,
    apply_full_skip_layout,
    apply_mock_textures,
    apply_skip_dialog_caps,
    build_customize_mock_segment,
    build_skip_button_label,
    button_focus_nine_slice_border,
    countdown_mmss,
    duration_label,
    elapsed_progress_percent_float,
    format_next_jump_label,
    format_skip_duration,
    is_compact_combined,
    is_compact_full_mode,
    mock_corner_pos,
    progress_display_percent_float,
    progress_mid_filename,
    skip_dialog_mode_name,
    skip_dialog_panel_left_720,
    skip_duration_for_playhead,
    skip_format_includes_duration,
)
from skip_dialog_customize_ui import (
    ID_ALL_CAPS,
    ID_COMBINED,
    ID_COUNTDOWN,
    ID_DURATION_CONTENT,
    ID_DURATION_FORMAT,
    ID_FONT,
    ID_FOCUS_FRAME,
    ID_HIDE_ENDING,
    ID_HIDE_ICONS,
    ID_HEIGHT,
    ID_HIDE_CLOSE,
    ID_MODE,
    ID_OVERLAP,
    ID_PROGRESS,
    ID_PROGRESS_STYLE,
    ID_FOCUS_STYLE,
    ID_SKIP_FORMAT,
    MODES,
    PROGRESS_STYLES,
    _cycle,
    customize_left_pane_layout,
    customize_nav_ids,
    customize_section_header_before,
    draft_setting_payload,
    load_skip_dialog_draft,
)


class _Addon:
    def getLocalizedString(self, _sid):
        return ""

    def getSetting(self, key):
        return {
            "skip_dialog_mode": "Full",
            "hide_ending_text": "false",
            "skip_dialog_font_color": "FFFFFFFF",
            "skip_overlapping_segments": "true",
            "show_progress_bar": "true",
            "progress_bar_countdown": "false",
            "progress_bar_height": "16",
            "skip_dialog_position": "BottomRight",
            "button_focus_style": "button_focus.png",
            "skip_button_format": "Skip + Type + Duration",
            "hide_close_button": "false",
            "show_skip_button_focus_texture": "true",
            "hide_skip_icon": "false",
            "skip_dialog_all_caps": "false",
            "smooth_progress_bar": "false",
            "minimal_button_style": "minimal_rounded_gray_640.png",
            "minimal_skip_button_format": "Skip + Type",
            "minimal_skip_dialog_position": "BottomRight",
            "progress_bar_style": "progress_mid.png",
        }.get(key, "")


class CustomizeMockSegmentTests(unittest.TestCase):
    def test_overlapping_on_hides_jump(self):
        seg = build_customize_mock_segment(True)
        self.assertEqual(seg.segment_type_label, "intro")
        self.assertEqual(seg.start_seconds, 0.0)
        self.assertEqual(seg.end_seconds, 90.0)
        self.assertIsNone(seg.next_segment_start)
        self.assertIsNone(format_next_jump_label(_Addon(), seg.next_segment_info, seg.next_segment_start))

    def test_overlapping_off_shows_skip_to_recap(self):
        seg = build_customize_mock_segment(False)
        self.assertEqual(seg.next_segment_start, MOCK_RECAP_START)
        self.assertIn("recap", (seg.next_segment_info or "").lower())
        self.assertEqual(
            format_next_jump_label(_Addon(), seg.next_segment_info, seg.next_segment_start),
            "Skip to Recap at 00:30",
        )


class CustomizeLabelAndProgressTests(unittest.TestCase):
    def test_duration_is_1m30s(self):
        self.assertEqual(duration_label(MOCK_INTRO_END), "1m30s")

    def test_button_formats(self):
        seg = build_customize_mock_segment(True)
        dur = duration_label(MOCK_INTRO_END)
        addon = _Addon()
        self.assertEqual(build_skip_button_label(seg, "Skip", dur, addon), "Skip")
        self.assertEqual(build_skip_button_label(seg, "Skip + Type", dur, addon), "Skip Intro")
        self.assertEqual(
            build_skip_button_label(seg, "Skip + Type + Duration", dur, addon),
            "Skip Intro (1m30s)",
        )

    def test_progress_25_vs_countdown_75(self):
        elapsed = elapsed_progress_percent_float(MOCK_PLAYHEAD, 0.0, MOCK_INTRO_END)
        self.assertAlmostEqual(elapsed, 25.0, places=4)
        self.assertAlmostEqual(progress_display_percent_float(elapsed, False), 25.0, places=4)
        self.assertAlmostEqual(progress_display_percent_float(elapsed, True), 75.0, places=4)

    def test_frozen_countdown_mmss(self):
        self.assertEqual(countdown_mmss(MOCK_INTRO_END - MOCK_PLAYHEAD), "01:07")

    def test_corner_positions(self):
        self.assertEqual(mock_corner_pos("TopLeft", 720, 540, 430, 100), (8, 8))
        self.assertEqual(mock_corner_pos("BottomRight", 720, 540, 430, 100), (282, 432))


class CustomizeDraftTests(unittest.TestCase):
    def test_load_and_payload_roundtrip_types(self):
        draft = load_skip_dialog_draft(_Addon())
        self.assertEqual(draft["skip_dialog_mode"], "Full")
        self.assertTrue(draft["skip_overlapping_segments"])
        self.assertEqual(draft["progress_bar_height"], 16)
        payload = draft_setting_payload(draft)
        self.assertEqual(payload["skip_overlapping_segments"], "true")
        self.assertEqual(payload["hide_ending_text"], "false")
        self.assertEqual(payload["progress_bar_height"], "16")
        draft["hide_ending_text"] = True
        draft["progress_bar_height"] = 24
        payload2 = draft_setting_payload(draft)
        self.assertEqual(payload2["hide_ending_text"], "true")
        self.assertEqual(payload2["progress_bar_height"], "24")

    def test_payload_includes_progress_style_and_hide_icons(self):
        draft = load_skip_dialog_draft(_Addon())
        payload = draft_setting_payload(draft)
        self.assertEqual(payload["progress_bar_style"], "progress_mid.png")
        self.assertEqual(payload["hide_skip_icon"], "false")
        draft["progress_bar_style"] = "progress_mid_pink.png"
        draft["hide_skip_icon"] = True
        payload2 = draft_setting_payload(draft)
        self.assertEqual(payload2["progress_bar_style"], "progress_mid_pink.png")
        self.assertEqual(payload2["hide_skip_icon"], "true")


class CustomizeNavAndStyleTests(unittest.TestCase):
    def test_full_nav_visits_every_row_without_skipping(self):
        ids = customize_nav_ids({"skip_dialog_mode": "Full", "hide_close_button": False})
        self.assertEqual(ids[0], ID_MODE)
        self.assertEqual(ids[1], ID_HIDE_ENDING)
        self.assertEqual(ids[2], ID_FONT)
        self.assertEqual(ids[3], ID_ALL_CAPS)
        self.assertEqual(ids[4], ID_OVERLAP)
        self.assertIn(ID_COMBINED, ids)
        self.assertEqual(ids[ids.index(ID_OVERLAP) + 1], ID_COMBINED)
        self.assertIn(ID_PROGRESS_STYLE, ids)
        self.assertIn(ID_HIDE_ICONS, ids)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids[ids.index(ID_MODE) + 1], ID_HIDE_ENDING)

    def test_minimal_nav_omits_ending_and_overlap(self):
        ids = customize_nav_ids({"skip_dialog_mode": "Minimal"})
        self.assertNotIn(ID_HIDE_ENDING, ids)
        self.assertNotIn(ID_OVERLAP, ids)
        self.assertEqual(ids[0], ID_MODE)
        self.assertEqual(ids[1], ID_FONT)
        self.assertEqual(ids[2], ID_ALL_CAPS)

    def test_compact_full_nav_omits_ending_icons_and_height(self):
        ids = customize_nav_ids({"skip_dialog_mode": "CompactFull", "hide_close_button": False})
        self.assertNotIn(ID_HIDE_ENDING, ids)
        self.assertNotIn(ID_HIDE_ICONS, ids)
        self.assertNotIn(ID_HEIGHT, ids)
        self.assertIn(ID_OVERLAP, ids)
        self.assertIn(ID_COMBINED, ids)
        self.assertIn(ID_PROGRESS, ids)
        self.assertIn(ID_FOCUS_STYLE, ids)
        self.assertIn(ID_HIDE_CLOSE, ids)
        self.assertEqual(ids[0], ID_MODE)
        self.assertEqual(ids[1], ID_FONT)

    def test_mode_cycle_includes_compact_full(self):
        self.assertEqual(MODES, ("Full", "CompactFull", "Minimal"))
        self.assertEqual(_cycle(MODES, "Full", 1), "CompactFull")
        self.assertEqual(_cycle(MODES, "CompactFull", 1), "Minimal")
        self.assertEqual(skip_dialog_mode_name("Compact Full"), "CompactFull")
        self.assertTrue(is_compact_full_mode("CompactFull"))

    def test_all_caps_keeps_duration_units_lowercase(self):
        self.assertEqual(
            apply_skip_dialog_caps("Skip Intro (1m30s)", True),
            "SKIP INTRO (1m30s)",
        )
        self.assertEqual(
            apply_skip_dialog_caps("Skip Intro (22s / 1m30s)", True),
            "SKIP INTRO (22s / 1m30s)",
        )
        self.assertEqual(apply_skip_dialog_caps("Skip to Recap at 00:30", True), "SKIP TO RECAP AT 00:30")
        self.assertEqual(apply_skip_dialog_caps("Skip Intro (1m30s)", False), "Skip Intro (1m30s)")

    def test_duration_format_and_content(self):
        self.assertEqual(format_skip_duration(90, "1m30s"), "1m30s")
        self.assertEqual(format_skip_duration(90, "mm:ss"), "01:30")
        self.assertEqual(format_skip_duration(22, "mm:ss"), "00:22")
        self.assertEqual(format_skip_duration(3661, "mm:ss"), "1:01:01")
        self.assertTrue(skip_format_includes_duration("Skip + Type + Duration"))
        self.assertFalse(skip_format_includes_duration("Skip + Type"))
        settings = DictSettingsReader(
            {
                "skip_duration_format": "1m30s",
                "skip_duration_content": "elapsed_total",
            }
        )
        seg = build_customize_mock_segment(True)
        self.assertEqual(skip_duration_for_playhead(MOCK_PLAYHEAD, seg, settings), "22s / 1m30s")
        settings = DictSettingsReader(
            {
                "skip_duration_format": "mm:ss",
                "skip_duration_content": "elapsed_up",
            }
        )
        self.assertEqual(skip_duration_for_playhead(MOCK_PLAYHEAD, seg, settings), "00:22")
        settings = DictSettingsReader(
            {
                "skip_duration_format": "mm:ss",
                "skip_duration_content": "elapsed_down",
            }
        )
        self.assertEqual(skip_duration_for_playhead(MOCK_PLAYHEAD, seg, settings), "01:08")
        settings = DictSettingsReader(
            {
                "skip_duration_format": "1m30s",
                "skip_duration_content": "total",
            }
        )
        self.assertEqual(skip_duration_for_playhead(MOCK_PLAYHEAD, seg, settings), "1m30s")

    def test_compact_combined_nav_hides_close_and_separate_bar(self):
        ids = customize_nav_ids(
            {
                "skip_dialog_mode": "CompactFull",
                "compact_full_combined": True,
                "skip_button_format": "Skip + Type + Duration",
            }
        )
        self.assertIn(ID_COMBINED, ids)
        self.assertIn(ID_COUNTDOWN, ids)
        self.assertIn(ID_DURATION_FORMAT, ids)
        self.assertIn(ID_DURATION_CONTENT, ids)
        self.assertNotIn(ID_PROGRESS, ids)
        self.assertNotIn(ID_PROGRESS_STYLE, ids)
        self.assertNotIn(ID_HIDE_CLOSE, ids)
        self.assertNotIn(ID_HIDE_ICONS, ids)
        self.assertTrue(is_compact_combined(DictSettingsReader({
            "skip_dialog_mode": "CompactFull",
            "compact_full_combined": True,
        })))

    def test_full_combined_nav_keeps_icons_hides_close_and_bar(self):
        ids = customize_nav_ids(
            {
                "skip_dialog_mode": "Full",
                "compact_full_combined": True,
                "skip_button_format": "Skip + Type + Duration",
            }
        )
        self.assertIn(ID_COMBINED, ids)
        self.assertIn(ID_HIDE_ENDING, ids)
        self.assertIn(ID_HIDE_ICONS, ids)
        self.assertIn(ID_COUNTDOWN, ids)
        self.assertNotIn(ID_PROGRESS, ids)
        self.assertNotIn(ID_HEIGHT, ids)
        self.assertNotIn(ID_HIDE_CLOSE, ids)
        self.assertTrue(is_compact_combined(DictSettingsReader({
            "skip_dialog_mode": "Full",
            "compact_full_combined": True,
        })))
        self.assertFalse(is_compact_combined(DictSettingsReader({
            "skip_dialog_mode": "Minimal",
            "compact_full_combined": True,
        })))

    def test_combined_is_not_full_section_header(self):
        full_ids = customize_nav_ids({"skip_dialog_mode": "Full", "hide_close_button": False})
        self.assertEqual(full_ids[full_ids.index(ID_OVERLAP) + 1], ID_COMBINED)
        starts = customize_section_header_before(full_ids)
        self.assertNotIn(ID_COMBINED, starts)
        self.assertIn(ID_PROGRESS, starts)
        combined_ids = customize_nav_ids(
            {
                "skip_dialog_mode": "Full",
                "compact_full_combined": True,
                "skip_button_format": "Skip + Type",
            }
        )
        combined_starts = customize_section_header_before(combined_ids)
        self.assertNotIn(ID_COMBINED, combined_starts)
        self.assertIn(ID_COUNTDOWN, combined_starts)
        self.assertEqual(combined_ids[combined_ids.index(ID_COMBINED) + 1], ID_COUNTDOWN)

    def test_full_nav_includes_duration_when_format_has_it(self):
        ids = customize_nav_ids(
            {
                "skip_dialog_mode": "Full",
                "skip_button_format": "Skip + Type + Duration",
                "hide_close_button": False,
            }
        )
        self.assertEqual(ids[ids.index(ID_SKIP_FORMAT) + 1], ID_DURATION_FORMAT)
        self.assertEqual(ids[ids.index(ID_SKIP_FORMAT) + 2], ID_DURATION_CONTENT)
        ids2 = customize_nav_ids(
            {
                "skip_dialog_mode": "Full",
                "skip_button_format": "Skip + Type",
                "hide_close_button": False,
            }
        )
        self.assertNotIn(ID_DURATION_FORMAT, ids2)

    def test_left_pane_rows_stay_above_save_cancel(self):
        from addon_skin_resolution import SKIN_RES_1080I, SKIN_RES_720P, scale_skin_coord

        drafts = (
            {
                "skip_dialog_mode": "Full",
                "skip_button_format": "Skip + Type + Duration",
                "hide_close_button": False,
            },
            {
                "skip_dialog_mode": "Full",
                "skip_button_format": "Skip + Type + Duration",
                "hide_close_button": True,
            },
            {
                "skip_dialog_mode": "Full",
                "compact_full_combined": True,
                "skip_button_format": "Skip + Type + Duration",
            },
            {
                "skip_dialog_mode": "CompactFull",
                "skip_button_format": "Skip + Type + Duration",
                "hide_close_button": False,
            },
            {
                "skip_dialog_mode": "CompactFull",
                "compact_full_combined": True,
                "skip_button_format": "Skip + Type + Duration",
            },
            {"skip_dialog_mode": "Minimal", "minimal_skip_button_format": "Skip + Type + Duration"},
        )
        for res in (SKIN_RES_720P, SKIN_RES_1080I):
            sc = lambda value, resolution=res: scale_skin_coord(value, resolution)
            for draft in drafts:
                ids = customize_nav_ids(draft)
                metrics = customize_left_pane_layout(ids, sc)
                self.assertGreaterEqual(
                    metrics["save_y"] - metrics["gap"],
                    metrics["content_bottom"],
                    msg="%s %s" % (res, draft),
                )
                self.assertIn(ID_DURATION_FORMAT, metrics["ids"])
                self.assertGreaterEqual(metrics["row_h"], sc(26))
                self.assertLessEqual(metrics["row_h"], sc(34))
        full_duration = customize_left_pane_layout(
            customize_nav_ids(
                {
                    "skip_dialog_mode": "Full",
                    "skip_button_format": "Skip + Type + Duration",
                    "hide_close_button": True,
                }
            ),
            lambda value: scale_skin_coord(value, SKIN_RES_720P),
        )
        self.assertLess(full_duration["row_h"], 34)
        self.assertIn(ID_FOCUS_FRAME, full_duration["ids"])
        compact_plain = customize_left_pane_layout(
            customize_nav_ids(
                {
                    "skip_dialog_mode": "CompactFull",
                    "skip_button_format": "Skip + Type",
                    "hide_close_button": False,
                }
            ),
            lambda value: scale_skin_coord(value, SKIN_RES_720P),
        )
        self.assertEqual(compact_plain["row_h"], 34)

    def test_progress_style_cycles_mid_textures(self):
        stored = [pair[1] for pair in PROGRESS_STYLES]
        self.assertEqual(stored[0], "progress_mid.png")
        self.assertEqual(_cycle(stored, "progress_mid.png", 1), "progress_mid_blue_purple.png")
        reader = DictSettingsReader({"progress_bar_style": "progress_mid_pink.png"})
        self.assertEqual(progress_mid_filename(reader), "progress_mid_pink.png")

    def test_jump_label_matches_live_dialog_accent(self):
        self.assertEqual(JUMP_LABEL_ARGB, "FFB0D4E8")
        self.assertEqual(JUMP_LABEL_FONT, "font11")
        self.assertEqual(ENDING_TEXT_ARGB, "FFFFFFFF")

    def test_ending_text_xml_is_white(self):
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        names = (
            "SkipDialog.xml",
            "SkipDialog_BottomRight.xml",
            "SkipDialog_BottomLeft.xml",
            "SkipDialog_TopRight.xml",
            "SkipDialog_TopLeft.xml",
            "SkipDialogCustomize.xml",
        )
        marker = "$INFO[Window.Property(ending_text)] $INFO[Window.Property(countdown)]"
        for folder in ("720p", "1080i"):
            for name in names:
                path = os.path.join(root, "resources", "skins", "default", folder, name)
                with open(path, encoding="utf-8") as handle:
                    text = handle.read()
                idx = text.find(marker)
                self.assertNotEqual(idx, -1, path)
                snippet = text[idx : idx + 280]
                self.assertIn("<textcolor>FFFFFFFF</textcolor>", snippet, path)
                self.assertNotIn(
                    "$INFO[Window.Property(skip_dialog_text_color)]",
                    snippet,
                    path,
                )

    def test_customize_xml_self_binds_nav_and_has_new_rows(self):
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        for folder in ("720p", "1080i"):
            path = os.path.join(
                root, "resources", "skins", "default", folder, "SkipDialogCustomize.xml"
            )
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
            self.assertIn('id="4114"', text)
            self.assertIn('id="4120"', text)
            self.assertIn('id="4121"', text)
            self.assertIn('id="4122"', text)
            self.assertIn('id="4123"', text)
            self.assertIn('id="4104"', text)
            self.assertIn('id="3050"', text)
            self.assertIn('id="3051"', text)
            self.assertIn('id="3052"', text)
            self.assertIn('id="3053"', text)
            if folder == "720p":
                self.assertIn("<width>420</width>", text)
            else:
                self.assertIn("<width>630</width>", text)
            self.assertIn("<onup>4100</onup><ondown>4100</ondown>", text)
            self.assertIn("<onup>4101</onup><ondown>4101</ondown>", text)
            self.assertIn("FFB0D4E8", text)
            self.assertIn("skippy_mock_focus", text)
            self.assertIn("skippy_mock_focus_slice", text)
            self.assertIn("skippy_progress_mid", text)
            self.assertIn('id="3042"', text)
            self.assertIn('id="3043"', text)
            self.assertIn('border="12,0,12,0"', text)
            self.assertIn(
                "!String.IsEqual(Window.Property(skippy_customize_mode),Minimal)",
                text,
            )

    def test_dict_reader_progress_percent(self):
        reader = DictSettingsReader(
            {"progress_bar_countdown": True, "progress_bar_height": "20"}
        )
        self.assertTrue(reader.get_bool("progress_bar_countdown"))
        self.assertEqual(reader.get_int("progress_bar_height", 16, minimum=5, maximum=32), 20)


class NineSliceFocusTextureTests(unittest.TestCase):
    _SLICE = (
        "button_focus_aqua_bevel.png",
        "button_focus_aqua_rounded.png",
        "button_focus_blue_rounded_3d.png",
        "button_focus_gold_rectangular_3d.png",
        "button_focus_3d_green.png",
        "button_focus_3d_pink.png",
        "button_focus_3d_light_pink.png",
        "button_focus_3d_cyan.png",
        "button_focus_3d_silver.png",
        "button_focus_3d_orange.png",
        "button_focus_3d_violet.png",
        "button_focus_3d_graphite.png",
        "button_focus_3d_ice.png",
    )

    def test_border_map(self):
        for name in self._SLICE:
            self.assertEqual(button_focus_nine_slice_border(name), "12,0,12,0")
        self.assertEqual(
            button_focus_nine_slice_border(r"C:\skin\button_focus_3d_green.png"),
            "12,0,12,0",
        )
        self.assertIsNone(button_focus_nine_slice_border("button_focus.png"))
        self.assertIsNone(button_focus_nine_slice_border("button_focus_aqua.png"))
        self.assertIsNone(button_focus_nine_slice_border("button_focus_aqua_dark.png"))
        self.assertIsNone(button_focus_nine_slice_border("button_focus_aqua_vignette.png"))
        self.assertIsNone(button_focus_nine_slice_border("-"))

    def test_aqua_vignette_keeps_full_width_gradient(self):
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        path = os.path.join(
            root, "resources", "skins", "default", "media", "button_focus_aqua_vignette.png"
        )
        with open(path, "rb") as handle:
            handle.read(16)
            width, height = struct.unpack(">II", handle.read(8))
        self.assertEqual(height, 25)
        self.assertGreaterEqual(width, 200)

    def test_templates_are_64x25(self):
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        media = os.path.join(root, "resources", "skins", "default", "media")
        for name in self._SLICE:
            path = os.path.join(media, name)
            with open(path, "rb") as handle:
                handle.read(16)
                width, height = struct.unpack(">II", handle.read(8))
            self.assertEqual((width, height), (64, 25), name)

    def test_apply_mock_enables_sliced_overlays(self):
        window = MagicMock()
        props = {}
        window.setProperty.side_effect = lambda key, value: props.__setitem__(key, value)
        controls = {}

        def _get_control(cid):
            if cid not in controls:
                controls[cid] = MagicMock()
            return controls[cid]

        window.getControl.side_effect = _get_control
        settings = DictSettingsReader(
            {
                "button_focus_style": "button_focus_3d_green.png",
                "hide_close_button": False,
                "show_skip_button_focus_texture": True,
                "progress_bar_style": "progress_mid.png",
                "show_progress_bar": False,
                "minimal_button_style": "minimal_rounded_gray_640.png",
            }
        )
        apply_mock_textures(window, settings, False)
        self.assertEqual(props["skippy_mock_focus_slice"], "true")
        self.assertEqual(props["skippy_mock_focus_narrow"], "true")
        controls[3040].setVisible.assert_called_with(False)
        controls[3042].setVisible.assert_called_with(True)
        controls[3041].setVisible.assert_called_with(False)
        controls[3043].setVisible.assert_called_with(False)

    def test_apply_mock_default_style_uses_stretch_overlays(self):
        window = MagicMock()
        props = {}
        window.setProperty.side_effect = lambda key, value: props.__setitem__(key, value)
        controls = {}

        def _get_control(cid):
            if cid not in controls:
                controls[cid] = MagicMock()
            return controls[cid]

        window.getControl.side_effect = _get_control
        settings = DictSettingsReader(
            {
                "button_focus_style": "button_focus.png",
                "hide_close_button": False,
                "show_skip_button_focus_texture": True,
                "show_progress_bar": False,
            }
        )
        apply_mock_textures(window, settings, False)
        self.assertEqual(props["skippy_mock_focus_slice"], "false")
        controls[3040].setVisible.assert_called_with(True)
        controls[3042].setVisible.assert_called_with(False)


class CompactFullLayoutTests(unittest.TestCase):
    def test_compact_hides_card_and_uses_thin_bar(self):
        window = MagicMock()
        props = {}
        window.setProperty.side_effect = lambda key, value: props.__setitem__(key, value)
        window.getProperty.side_effect = lambda key: props.get(key, "")
        controls = {}

        def _get_control(cid):
            if cid not in controls:
                controls[cid] = MagicMock()
            return controls[cid]

        window.getControl.side_effect = _get_control
        settings = DictSettingsReader(
            {
                "skip_dialog_mode": "CompactFull",
                "hide_close_button": False,
                "show_progress_bar": True,
                "progress_bar_countdown": False,
                "progress_bar_height": 16,
                "skip_dialog_position": "BottomRight",
                "smooth_progress_bar": False,
            }
        )
        seg = build_customize_mock_segment(False)
        apply_full_skip_layout(window, settings, MOCK_PLAYHEAD, seg, scale_fn=lambda value: value)
        self.assertEqual(props["skippy_compact_full"], "true")
        self.assertEqual(props["hide_ending_text"], "true")
        self.assertEqual(props["hide_skip_icon"], "true")
        controls[3081].setVisible.assert_called_with(False)
        skip_w = COMPACT_SKIP_CONTENT_W_720 - COMPACT_SKIP_CLOSE_W_720 - COMPACT_SKIP_GAP_720
        controls[3012].setWidth.assert_called_with(skip_w)
        controls[3014].setHeight.assert_called_with(COMPACT_PROGRESS_H_720)
        self.assertEqual(window._skip_progress_bar_width, COMPACT_SKIP_CONTENT_W_720)

    def test_full_layout_restores_card(self):
        window = MagicMock()
        props = {"hide_ending_text": "false", "show_next_jump": "false"}
        window.setProperty.side_effect = lambda key, value: props.__setitem__(key, value)
        window.getProperty.side_effect = lambda key: props.get(key, "")
        controls = {}

        def _get_control(cid):
            if cid not in controls:
                controls[cid] = MagicMock()
            return controls[cid]

        window.getControl.side_effect = _get_control
        settings = DictSettingsReader(
            {
                "skip_dialog_mode": "Full",
                "hide_close_button": False,
                "show_progress_bar": False,
                "skip_dialog_position": "BottomRight",
            }
        )
        seg = build_customize_mock_segment(True)
        apply_full_skip_layout(window, settings, MOCK_PLAYHEAD, seg, scale_fn=lambda value: value)
        self.assertEqual(props["skippy_compact_full"], "false")
        controls[3081].setVisible.assert_called_with(True)
        controls[3012].setWidth.assert_called_with(290)

    def test_layout_pins_right_panel_inside_canvas(self):
        window = MagicMock()
        props = {"hide_ending_text": "false", "show_next_jump": "false"}
        window.setProperty.side_effect = lambda key, value: props.__setitem__(key, value)
        window.getProperty.side_effect = lambda key: props.get(key, "")
        controls = {}

        def _get_control(cid):
            if cid not in controls:
                controls[cid] = MagicMock()
            return controls[cid]

        window.getControl.side_effect = _get_control
        panel = _get_control(3080)
        panel.getPosition.return_value = [895, 620]
        settings = DictSettingsReader(
            {
                "skip_dialog_mode": "Full",
                "hide_close_button": False,
                "show_progress_bar": False,
                "skip_dialog_position": "BottomRight",
            }
        )
        seg = build_customize_mock_segment(True)
        apply_full_skip_layout(window, settings, MOCK_PLAYHEAD, seg, scale_fn=lambda value: value)
        controls[3080].setPosition.assert_called_with(840, 620)
        controls[3080].setWidth.assert_called_with(FULL_SKIP_PANEL_W_720)
        left_settings = DictSettingsReader(
            {
                "skip_dialog_mode": "Full",
                "hide_close_button": False,
                "show_progress_bar": False,
                "skip_dialog_position": "BottomLeft",
            }
        )
        controls[3080].getPosition.return_value = [10, 620]
        apply_full_skip_layout(
            window, left_settings, MOCK_PLAYHEAD, seg, scale_fn=lambda value: value
        )
        controls[3080].setPosition.assert_called_with(10, 620)


class CombinedCompactLayoutTests(unittest.TestCase):
    def test_combined_forces_skip_only_and_hides_separate_bar(self):
        window = MagicMock()
        props = {}
        window.setProperty.side_effect = lambda key, value: props.__setitem__(key, value)
        window.getProperty.side_effect = lambda key: props.get(key, "")
        controls = {}

        def _get_control(cid):
            if cid not in controls:
                controls[cid] = MagicMock()
            return controls[cid]

        window.getControl.side_effect = _get_control
        settings = DictSettingsReader(
            {
                "skip_dialog_mode": "CompactFull",
                "compact_full_combined": True,
                "hide_close_button": False,
                "show_progress_bar": True,
                "progress_bar_countdown": False,
                "skip_dialog_position": "BottomRight",
                "button_focus_style": "button_focus.png",
            }
        )
        seg = build_customize_mock_segment(False)
        apply_full_skip_layout(window, settings, MOCK_PLAYHEAD, seg, scale_fn=lambda value: value)
        self.assertEqual(props["skippy_combined"], "true")
        self.assertEqual(props["hide_close_button"], "true")
        self.assertEqual(props["skippy_combined_slice"], "false")
        controls[3081].setVisible.assert_called_with(False)
        controls[3012].setWidth.assert_called_with(COMPACT_SKIP_CONTENT_W_720)
        controls[3014].setVisible.assert_called_with(False)
        controls[COMBINED_TRACK_ID].setVisible.assert_called_with(True)
        controls[COMBINED_TRACK_SLICE_ID].setVisible.assert_called_with(False)
        controls[COMBINED_FILL_STRETCH_ID].setWidth.assert_called_with(75)
        self.assertEqual(window._skip_progress_bar_width, COMPACT_SKIP_CONTENT_W_720)

    def test_combined_sliced_style_nine_slices_track_and_fill(self):
        window = MagicMock()
        props = {}
        window.setProperty.side_effect = lambda key, value: props.__setitem__(key, value)
        window.getProperty.side_effect = lambda key: props.get(key, "")
        controls = {}

        def _get_control(cid):
            if cid not in controls:
                controls[cid] = MagicMock()
            return controls[cid]

        window.getControl.side_effect = _get_control
        settings = DictSettingsReader(
            {
                "skip_dialog_mode": "CompactFull",
                "compact_full_combined": True,
                "show_progress_bar": True,
                "progress_bar_countdown": False,
                "skip_dialog_position": "BottomRight",
                "button_focus_style": "button_focus_3d_green.png",
            }
        )
        seg = build_customize_mock_segment(False)
        apply_full_skip_layout(window, settings, MOCK_PLAYHEAD, seg, scale_fn=lambda value: value)
        self.assertEqual(props["skippy_combined_slice"], "true")
        controls[COMBINED_TRACK_ID].setVisible.assert_called_with(False)
        controls[COMBINED_TRACK_SLICE_ID].setVisible.assert_called_with(True)
        controls[COMBINED_FILL_STRETCH_ID].setVisible.assert_called_with(False)
        controls[COMBINED_FILL_SLICE_ID].setVisible.assert_called_with(True)
        apply_mock_textures(window, settings, False)
        controls[COMBINED_TRACK_SLICE_ID].setColorDiffuse.assert_called_with("66FFFFFF")

    def test_full_combined_keeps_card_and_fills_wide_skip(self):
        window = MagicMock()
        props = {}
        window.setProperty.side_effect = lambda key, value: props.__setitem__(key, value)
        window.getProperty.side_effect = lambda key: props.get(key, "")
        controls = {}

        def _get_control(cid):
            if cid not in controls:
                controls[cid] = MagicMock()
            return controls[cid]

        window.getControl.side_effect = _get_control
        settings = DictSettingsReader(
            {
                "skip_dialog_mode": "Full",
                "compact_full_combined": True,
                "hide_close_button": False,
                "hide_ending_text": False,
                "show_progress_bar": True,
                "progress_bar_countdown": False,
                "skip_dialog_position": "BottomRight",
                "button_focus_style": "button_focus.png",
            }
        )
        seg = build_customize_mock_segment(True)
        apply_full_skip_layout(window, settings, MOCK_PLAYHEAD, seg, scale_fn=lambda value: value)
        self.assertEqual(props["skippy_combined"], "true")
        self.assertEqual(props["skippy_compact_full"], "false")
        self.assertEqual(props["hide_close_button"], "true")
        controls[3081].setVisible.assert_called_with(True)
        controls[3014].setVisible.assert_called_with(False)
        controls[3016].setWidth.assert_called_with(FULL_SKIP_PROGRESS_BAR_WIDTH)
        controls[COMBINED_TRACK_ID].setPosition.assert_called_with(
            FULL_SKIP_MARGIN_720, 10
        )
        controls[COMBINED_FILL_STRETCH_ID].setWidth.assert_called_with(105)
        self.assertEqual(window._skip_progress_bar_width, FULL_SKIP_PROGRESS_BAR_WIDTH)

    def test_right_corner_xml_fits_canvas(self):
        self.assertEqual(skip_dialog_panel_left_720(False), SKIP_DIALOG_SCREEN_MARGIN_720)
        self.assertEqual(
            skip_dialog_panel_left_720(True),
            SKIP_DIALOG_CANVAS_W_720 - FULL_SKIP_PANEL_W_720 - SKIP_DIALOG_SCREEN_MARGIN_720,
        )
        self.assertEqual(skip_dialog_panel_left_720(True), 840)
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        right_files = (
            "SkipDialog.xml",
            "SkipDialog_BottomRight.xml",
            "SkipDialog_TopRight.xml",
        )
        for folder, canvas, expected_x in (("720p", 1280, 840), ("1080i", 1920, 1260)):
            for name in right_files:
                path = os.path.join(root, "resources", "skins", "default", folder, name)
                with open(path, encoding="utf-8") as handle:
                    text = handle.read()
                marker = '<control type="group" id="3080">'
                idx = text.find(marker)
                self.assertNotEqual(idx, -1, path)
                snippet = text[idx : idx + 250]
                self.assertIn("<posx>%s</posx>" % expected_x, snippet)
                self.assertIn("<width>%s</width>" % (430 if folder == "720p" else 645), snippet)
                self.assertLessEqual(expected_x + (430 if folder == "720p" else 645), canvas)

    def test_skip_dialogs_drop_progress_endcaps(self):
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        for folder in ("720p", "1080i"):
            path = os.path.join(root, "resources", "skins", "default", folder, "SkipDialog.xml")
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
            self.assertIn("<textureleft>-</textureleft>", text)
            self.assertIn("<textureright>-</textureright>", text)
            self.assertNotIn("progress_left.png", text)
            self.assertIn('id="3050"', text)
            self.assertIn('id="3053"', text)
            self.assertIn(
                '<texture border="12,0,12,0">$INFO[Window.Property(skippy_combined_fill)]</texture>',
                text,
            )


class CustomizeImportIsolationTests(unittest.TestCase):
    def test_service_modules_do_not_import_customize_ui(self):
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        for name in ("service.py", "service_main_loop.py"):
            path = os.path.join(root, name)
            with open(path, encoding="utf-8") as handle:
                src = handle.read()
            tree = ast.parse(src)
            imported = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.extend(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.append(node.module.split(".")[0])
            self.assertNotIn("skip_dialog_customize_ui", imported, name)


if __name__ == "__main__":
    unittest.main()
