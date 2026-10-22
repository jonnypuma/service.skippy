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
        self.assertEqual(m["wide_w"], 280)


if __name__ == "__main__":
    unittest.main()
