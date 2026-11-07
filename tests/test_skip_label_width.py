import unittest

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

from skip_dialog_appearance import (  # noqa: E402
    FULL_SKIP_PANEL_BACKDROP_ID,
    FULL_SKIP_PANEL_GROUP_ID,
    SKIP_BTN_MAX_TEXT_W_720,
    SKIP_WIDTH_STEPS_720,
    full_skip_panel_metrics,
    skip_label_width_720,
    skip_rows_min_content_w_720,
)

FMT_SKIP = "Skip"
FMT_TYPE = "Skip + Type"
FMT_DUR = "Skip + Type + Duration"


class SkipLabelWidthTests(unittest.TestCase):
    def test_plain_skip_is_the_narrowest_tier(self):
        self.assertEqual(skip_label_width_720("Skip", FMT_SKIP), min(SKIP_WIDTH_STEPS_720[FMT_SKIP]))
        self.assertLess(
            skip_label_width_720("Skip", FMT_SKIP), skip_label_width_720("Skip Intro", FMT_TYPE) + 1
        )

    def test_longer_type_name_picks_a_wider_rung(self):
        short = skip_label_width_720("Skip Intro", FMT_TYPE)
        long_ = skip_label_width_720("Skip Commercial Break", FMT_TYPE)
        self.assertLess(short, long_)
        self.assertIn(short, SKIP_WIDTH_STEPS_720[FMT_TYPE])

    def test_duration_tier_is_wider_than_type_tier(self):
        self.assertGreater(
            skip_label_width_720("Skip Intro (1m30s)", FMT_DUR),
            skip_label_width_720("Skip Intro", FMT_TYPE),
        )

    def test_all_caps_needs_more_room(self):
        self.assertGreaterEqual(
            skip_label_width_720("SKIP COMMERCIAL (2M10S)", FMT_DUR),
            skip_label_width_720("Skip Commercial (2m10s)", FMT_DUR),
        )

    def test_width_never_exceeds_cap(self):
        self.assertLessEqual(skip_label_width_720("x" * 200, FMT_DUR), SKIP_BTN_MAX_TEXT_W_720)

    def test_full_panel_without_close_is_narrower_for_plain_skip(self):
        ident = lambda v: v  # noqa: E731
        narrow = full_skip_panel_metrics(ident, False, True, False, 96)
        wide = full_skip_panel_metrics(ident, False, True, False, 270)
        self.assertLess(narrow["panel_w"], wide["panel_w"])
        self.assertEqual(narrow["content_w"], narrow["panel_w"] - 10)

    def test_close_button_row_fits_inside_panel(self):
        ident = lambda v: v  # noqa: E731
        m = full_skip_panel_metrics(ident, False, False, False, 190)
        self.assertEqual(m["close_x"] + m["close_w"] + 5, m["panel_w"])
        self.assertEqual(m["close_icon_x"], m["skip_x"] + m["skip_w"])

    def test_min_content_widens_a_narrow_panel(self):
        ident = lambda v: v  # noqa: E731
        m = full_skip_panel_metrics(ident, False, True, False, 96, min_content_w=280)
        self.assertEqual(m["content_w"], 280)
        # The focus texture starts after the Skip icon slot (icons stay outside it).
        self.assertEqual(m["wide_w"], 280 - 30)
        self.assertEqual(m["wide_x"], 5 + 30)
        no_icon = full_skip_panel_metrics(ident, False, True, True, 96, min_content_w=280)
        self.assertEqual(no_icon["wide_w"], 280)


class _Ctrl:
    def __init__(self):
        self.w = None

    def setWidth(self, w):
        self.w = w

    def __getattr__(self, name):
        return lambda *a, **k: None


def _preview_panel_w(preview_type, **draft):
    """Width (720p px) of the Customize preview panel for a preview segment type."""
    import skip_dialog_customize_ui as ui

    win = ui.SkipDialogCustomize.__new__(ui.SkipDialogCustomize)
    ctrls = {}
    props = {}
    win._ctrl = lambda cid: ctrls.setdefault(cid, _Ctrl())
    win.getControl = win._ctrl
    win._skin_resolution = None
    win._sc = lambda v: v
    win.addon = None
    win._preview_type = preview_type
    win._draft = dict(
        {
            "skip_dialog_mode": "Full",
            "skip_button_format": FMT_TYPE,
            "hide_close_button": True,
            "hide_skip_icon": True,
            "skip_overlapping_segments": True,
        },
        **draft,
    )
    win.setProperty = lambda k, v: props.__setitem__(k, v)
    win.getProperty = lambda k: props.get(k, "")
    win._layout_left_pane = lambda: None
    win._refresh_row_labels = lambda: None
    win.refresh_mockup()
    return win._skip_panel_w, ctrls


class SkipRowsWidthTests(unittest.TestCase):
    """The rows under the button are sized by their text, so the panel follows the type."""

    # Widths measured on screen (720p px) in Kodi with the default skin fonts.
    MEASURED_ENDING = {
        "Commercial ending in: 01:07": 202,
        "Prologue ending in: 01:07": 182,
        "Recap ending in: 01:07": 159,
    }
    MEASURED_JUMP = {"Skip to Recap at 00:30": 219}

    def test_no_rows_means_no_minimum(self):
        self.assertEqual(skip_rows_min_content_w_720("", ""), 0)

    def test_a_longer_ending_line_needs_more_room(self):
        short = skip_rows_min_content_w_720("", "Intro ending in: 01:07")
        long_ = skip_rows_min_content_w_720("", "Commercial ending in: 01:07")
        self.assertLess(short, long_)

    def test_the_widest_row_decides(self):
        both = skip_rows_min_content_w_720("Skip to Recap at 00:30", "Intro ending in: 01:07")
        self.assertEqual(both, skip_rows_min_content_w_720("Skip to Recap at 00:30", ""))

    def test_rows_are_never_clipped_but_not_much_wider_than_their_text(self):
        for text, measured in self.MEASURED_ENDING.items():
            need = skip_rows_min_content_w_720("", text)
            self.assertGreaterEqual(need, measured + 8, text)
            self.assertLessEqual(need, measured + 40, text)
        for text, measured in self.MEASURED_JUMP.items():
            need = skip_rows_min_content_w_720(text, "")
            self.assertGreaterEqual(need, measured + 8, text)
            self.assertLessEqual(need, measured + 40, text)

    def test_all_caps_rows_need_more_room(self):
        self.assertGreater(
            skip_rows_min_content_w_720("", "COMMERCIAL ENDING IN: 01:07"),
            skip_rows_min_content_w_720("", "Commercial ending in: 01:07"),
        )

    def test_rows_never_exceed_the_cap(self):
        self.assertEqual(skip_rows_min_content_w_720("x" * 300, "y" * 300), SKIP_BTN_MAX_TEXT_W_720)

    def test_preview_width_follows_the_type_with_the_ending_line(self):
        widths = {t: _preview_panel_w(t)[0] for t in ("intro", "commercial", "behind_the_scenes")}
        self.assertLess(widths["intro"], widths["commercial"])
        self.assertLess(widths["commercial"], widths["behind_the_scenes"])

    def test_preview_width_follows_the_type_without_rows(self):
        widths = {t: _preview_panel_w(t, hide_ending_text=True)[0] for t in ("intro", "commercial")}
        self.assertLessEqual(widths["intro"], widths["commercial"])

    def test_preview_shows_the_whole_ending_line(self):
        for ptype, text in (
            ("commercial", "Commercial ending in: 01:07"),
            ("prologue", "Prologue ending in: 01:07"),
            ("intro", "Intro ending in: 01:07"),
        ):
            panel_w, _ctrls = _preview_panel_w(ptype)
            self.assertGreaterEqual(panel_w - 10, skip_rows_min_content_w_720("", text) - 1, ptype)

    def test_the_next_jump_line_is_not_clipped_in_the_preview(self):
        panel_w, _ctrls = _preview_panel_w("intro", skip_overlapping_segments=False)
        self.assertGreaterEqual(panel_w - 10, skip_rows_min_content_w_720("Skip to Recap at 00:30", ""))
        self.assertGreaterEqual(panel_w - 10, 219 + 5)

    def test_the_card_and_the_button_use_the_panel_width(self):
        panel_w, ctrls = _preview_panel_w("commercial")
        self.assertEqual(ctrls[FULL_SKIP_PANEL_BACKDROP_ID].w, panel_w)
        self.assertEqual(ctrls[FULL_SKIP_PANEL_GROUP_ID].w, panel_w)
        self.assertEqual(ctrls[3015].w, panel_w - 10)

    def test_the_live_dialog_sizes_the_same_way(self):
        from skip_dialog_appearance import (
            DictSettingsReader,
            apply_full_skip_layout,
            apply_jump_properties,
            build_customize_mock_segment,
            ending_text_for_segment,
        )

        class Win:
            def __init__(self):
                self.props = {}
                self.ctrls = {}

            def setProperty(self, k, v):
                self.props[k] = v

            def getProperty(self, k):
                return self.props.get(k, "")

            def getControl(self, cid):
                return self.ctrls.setdefault(cid, _Ctrl())

        widths = []
        for kind in ("intro", "commercial"):
            seg = build_customize_mock_segment(True, kind)
            win = Win()
            win.props["hide_ending_text"] = "false"
            win.props["ending_text"] = ending_text_for_segment(None, seg)
            apply_jump_properties(win, None, seg)
            settings = DictSettingsReader(
                {
                    "skip_dialog_mode": "Full",
                    "skip_button_format": FMT_TYPE,
                    "hide_close_button": True,
                    "hide_skip_icon": True,
                }
            )
            apply_full_skip_layout(win, settings, 0, seg, lambda v: v, addon=None)
            widths.append(win._skip_panel_w)
        self.assertLess(widths[0], widths[1])


if __name__ == "__main__":
    unittest.main()


class MinimalPlateWidthTests(unittest.TestCase):
    def _settings(self, fmt, caps=False):
        from skip_dialog_appearance import DictSettingsReader

        return DictSettingsReader(
            {
                "minimal_skip_button_format": fmt,
                "skip_dialog_all_caps": caps,
                "minimal_skip_dialog_position": "BottomRight",
            }
        )

    def test_plain_skip_keeps_classic_plate(self):
        from skip_dialog_appearance import MINIMAL_MOCK_W_720, build_customize_mock_segment, minimal_plate_width_720

        seg = build_customize_mock_segment(True)
        self.assertEqual(minimal_plate_width_720(seg, self._settings("Skip")), MINIMAL_MOCK_W_720)

    def test_commercial_type_needs_a_wider_plate(self):
        from skip_dialog_appearance import MINIMAL_MOCK_W_720, build_customize_mock_segment, minimal_plate_width_720

        seg = build_customize_mock_segment(True, "commercial")
        wide = minimal_plate_width_720(seg, self._settings("Skip + Type"))
        self.assertGreater(wide, MINIMAL_MOCK_W_720)
        longer = minimal_plate_width_720(seg, self._settings("Skip + Type + Duration"))
        self.assertGreater(longer, wide)

    def test_layout_resizes_plate_and_keeps_right_edge(self):
        from unittest.mock import MagicMock

        from skip_dialog_appearance import (
            MINIMAL_MOCK_W_720,
            apply_minimal_skip_layout,
            build_customize_mock_segment,
            minimal_plate_width_720,
        )

        window = MagicMock()
        controls = {}
        window.getControl.side_effect = lambda cid: controls.setdefault(cid, MagicMock())
        window.getControl(3090).getPosition.return_value = (1045, 674)
        seg = build_customize_mock_segment(True, "commercial")
        settings = self._settings("Skip + Type")
        w = apply_minimal_skip_layout(window, settings, seg, lambda v: v)
        self.assertEqual(w, minimal_plate_width_720(seg, settings))
        controls[3090].setWidth.assert_called_with(w)
        controls[3090].setPosition.assert_called_with(1045 + MINIMAL_MOCK_W_720 - w, 674)
        controls[3021].setWidth.assert_called_with(w)
        controls[3012].setWidth.assert_called_with(w)

    def test_left_corner_is_not_moved(self):
        from unittest.mock import MagicMock

        from skip_dialog_appearance import DictSettingsReader, apply_minimal_skip_layout, build_customize_mock_segment

        window = MagicMock()
        controls = {}
        window.getControl.side_effect = lambda cid: controls.setdefault(cid, MagicMock())
        window.getControl(3090).getPosition.return_value = (10, 674)
        settings = DictSettingsReader(
            {"minimal_skip_button_format": "Skip + Type", "minimal_skip_dialog_position": "BottomLeft"}
        )
        apply_minimal_skip_layout(
            window, settings, build_customize_mock_segment(True, "commercial"), lambda v: v
        )
        controls[3090].setPosition.assert_not_called()


class PreviewTypeTests(unittest.TestCase):
    def test_mock_segment_takes_the_chosen_type(self):
        from skip_dialog_appearance import build_customize_mock_segment

        self.assertEqual(build_customize_mock_segment(True, "recap").segment_type_label, "recap")
        self.assertEqual(build_customize_mock_segment(True).segment_type_label, "commercial")

    def test_picker_lists_catalog_types_and_commercial(self):
        from skip_dialog_customize_ui import preview_type_ids

        ids = preview_type_ids()
        self.assertIn("commercial", ids)
        self.assertIn("intro", ids)


class MinimalPlateVariantTests(unittest.TestCase):
    def test_variant_path_for_known_plate(self):
        from skip_dialog_appearance import minimal_plate_variant

        self.assertEqual(
            minimal_plate_variant("minimal_flat_blue_640.png", 240),
            "plates/minimal_flat_blue_640_w240.png",
        )

    def test_unknown_plate_or_width_falls_back_to_original(self):
        from skip_dialog_appearance import minimal_plate_variant

        self.assertEqual(minimal_plate_variant("my_custom_plate.png", 240), "my_custom_plate.png")
        self.assertEqual(minimal_plate_variant("minimal_flat_blue_640.png", 123), "minimal_flat_blue_640.png")

    def test_every_plate_has_a_variant_for_every_width(self):
        import glob
        import os

        from skip_dialog_appearance import MINIMAL_PLATE_WIDTHS_720

        media = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "resources", "skins", "default", "media",
        )
        plates = glob.glob(os.path.join(media, "minimal_*.png"))
        self.assertTrue(plates)
        for path in plates:
            stem = os.path.splitext(os.path.basename(path))[0]
            for width in MINIMAL_PLATE_WIDTHS_720:
                self.assertTrue(
                    os.path.isfile(os.path.join(media, "plates", "%s_w%d.png" % (stem, width))),
                    (stem, width),
                )

    def test_generator_and_dialog_use_the_same_widths(self):
        import importlib.util
        import os

        from skip_dialog_appearance import MINIMAL_PLATE_WIDTHS_720

        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "tools", "gen_minimal_plate_variants.py",
        )
        spec = importlib.util.spec_from_file_location("gen_plates", path)
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except ImportError:
            self.skipTest("Pillow not installed")
        self.assertEqual(tuple(mod.WIDTHS_720), tuple(MINIMAL_PLATE_WIDTHS_720))

    def test_minimal_plate_width_is_a_prerendered_step(self):
        from skip_dialog_appearance import (
            DictSettingsReader,
            MINIMAL_PLATE_WIDTHS_720,
            build_customize_mock_segment,
            minimal_plate_width_720,
        )

        for fmt in ("Skip", "Skip + Type", "Skip + Type + Duration"):
            settings = DictSettingsReader({"minimal_skip_button_format": fmt})
            for label in ("intro", "commercial"):
                seg = build_customize_mock_segment(True, label)
                self.assertIn(minimal_plate_width_720(seg, settings), MINIMAL_PLATE_WIDTHS_720)
