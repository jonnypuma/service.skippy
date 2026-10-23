import unittest

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

from skip_dialog_appearance import (  # noqa: E402
    SKIP_BTN_MAX_TEXT_W_720,
    SKIP_WIDTH_STEPS_720,
    full_skip_panel_metrics,
    skip_label_width_720,
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
