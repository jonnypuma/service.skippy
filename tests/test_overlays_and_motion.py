# -*- coding: utf-8 -*-
"""Background overlays and motion of the skip dialog layouts."""
import os
import unittest

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import skip_dialog_customize_ui as base  # noqa: E402
import skip_layouts as sl  # noqa: E402
import skip_studio_ui as studio  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SKINS = os.path.join(ROOT, "resources", "skins", "default")
MEDIA = os.path.join(SKINS, "media")
POSITIONS = ("BottomRight", "TopRight", "TopLeft", "BottomLeft")


class OverlayTests(unittest.TestCase):
    def test_none_and_the_band_layout_take_no_shade(self):
        for layout in sl.all_layouts():
            self.assertIsNone(sl.overlay_box(layout, "BottomRight", "None"))
            if layout.anchor == sl.ANCHOR_BAND:
                for kind in sl.OVERLAYS:
                    self.assertIsNone(sl.overlay_box(layout, "BottomRight", kind))

    def test_every_shade_has_its_picture_and_stays_on_the_screen(self):
        for layout in sl.all_layouts():
            if layout.anchor == sl.ANCHOR_BAND:
                continue
            for position in POSITIONS:
                for kind in [k for k in sl.OVERLAYS if k not in ("None", "Auto")]:
                    found = sl.overlay_box(layout, position, kind)
                    self.assertIsNotNone(found, (layout.xml, position, kind))
                    self.assertTrue(os.path.isfile(os.path.join(MEDIA, found["texture"])), found["texture"])
                    left, top, width, height = found["box"]
                    self.assertGreater(width, 0)
                    self.assertGreater(height, 0)
                    self.assertGreaterEqual(left, -sl.OVERLAY_MARGIN)
                    self.assertLessEqual(left + width, sl.CANVAS_W + sl.OVERLAY_MARGIN)
                    self.assertLessEqual(top + height, sl.CANVAS_H + sl.OVERLAY_MARGIN)
                    # the dialog lies inside its shade
                    ox, oy = sl.origin(layout, position)
                    self.assertLessEqual(left, ox, (layout.xml, position, kind))
                    self.assertGreaterEqual(left + width, ox + layout.width, (layout.xml, position, kind))
                    self.assertGreaterEqual(top + height, oy + layout.height, (layout.xml, position, kind))

    def test_the_rounded_shades_hug_the_dialog(self):
        layout = sl.get("Dial", sl.SIZE_FULL)
        ox, oy = sl.origin(layout, "BottomRight")
        for kind in ("Round", "RoundFade"):
            found = sl.overlay_box(layout, "BottomRight", kind)
            self.assertTrue(found["nine"])
            m = sl.OVERLAY_MARGIN
            self.assertEqual(found["box"], (ox - m, oy - m, layout.width + 2 * m, layout.height + 2 * m))

    def test_a_square_runs_out_to_the_corner_it_sits_in(self):
        layout = sl.get("Dial", sl.SIZE_FULL)
        left, top, width, height = sl.overlay_box(layout, "BottomRight", "Square")["box"]
        self.assertEqual((left + width, top + height), (sl.CANVAS_W, sl.CANVAS_H))
        left, top, _w, _h = sl.overlay_box(layout, "TopLeft", "Square")["box"]
        self.assertEqual((left, top), (0, 0))

    def test_fades_and_glows_follow_the_side(self):
        layout = sl.get("Dial", sl.SIZE_FULL)
        self.assertEqual(sl.overlay_box(layout, "BottomRight", "SquareFade")["texture"], "ov_fade_r.png")
        self.assertEqual(sl.overlay_box(layout, "BottomLeft", "SquareFade")["texture"], "ov_fade_l.png")
        self.assertEqual(sl.overlay_box(layout, "TopLeft", "Glow")["texture"], "ov_glow_tl.png")
        self.assertEqual(sl.overlay_box(layout, "BottomRight", "Band")["texture"], "sl_band.png")
        self.assertEqual(sl.overlay_box(layout, "TopRight", "Band")["texture"], "sl_band_top.png")
        centred = sl.get("Timeline", sl.SIZE_FULL)
        self.assertEqual(sl.overlay_box(centred, "BottomRight", "Glow")["texture"], "ov_glow_bc.png")
        rail = sl.get("Rail", sl.SIZE_FULL)
        found = sl.overlay_box(rail, "BottomRight", "Band")  # half way up an edge: a fade from that side
        self.assertEqual(found["texture"], "ov_fade_r.png")
        self.assertEqual((found["box"][1], found["box"][3]), (0, sl.CANVAS_H))


class MotionTests(unittest.TestCase):
    def test_choices_and_defaults(self):
        self.assertEqual(sl.normalize_appear(None), "Fade")
        self.assertEqual(sl.normalize_appear("slide"), "Slide")
        self.assertEqual(sl.normalize_leave("nonsense"), "Fade")
        self.assertEqual(sl.normalize_overlay("round fade"), "RoundFade")

    def test_slide_comes_from_the_side_the_dialog_sits_at(self):
        layout = sl.get("Dial", sl.SIZE_FULL)
        self.assertEqual(sl.appear_value(layout, "BottomRight", "Slide"), "SlideRight")
        self.assertEqual(sl.appear_value(layout, "TopLeft", "Slide"), "SlideLeft")
        self.assertEqual(sl.appear_value(layout, "TopLeft", "Rise"), "Rise")

    def test_the_pulse_runs_in_the_last_five_seconds_only(self):
        self.assertTrue(sl.pulses("00:05", True))
        self.assertTrue(sl.pulses("00:01", True))
        self.assertFalse(sl.pulses("00:06", True))
        self.assertFalse(sl.pulses("00:00", True))
        self.assertFalse(sl.pulses("01:03", True))
        self.assertFalse(sl.pulses("00:03", False))
        self.assertFalse(sl.pulses("", True))

    def test_every_layout_file_has_the_shades_and_the_motion(self):
        for res in ("720p", "1080i"):
            for layout in sl.all_layouts():
                with open(os.path.join(SKINS, res, layout.xml), encoding="utf-8") as handle:
                    text = handle.read()
                for wanted in ('id="%d"' % sl.ID_OVERLAY, 'id="%d"' % sl.ID_OVERLAY_PLAIN, "skl_in),Rise", "skl_in),Pop",
                               "skl_in),SlideRight", "skl_in),SlideLeft", "skl_out),Drop", "skl_out),Shrink", "skl_pulse"):
                    self.assertIn(wanted, text, (res, layout.xml, wanted))
        with open(os.path.join(SKINS, "1080i", sl.all_layouts()[0].xml), encoding="utf-8") as handle:
            self.assertIn('start="60,0"', handle.read())  # the slide of 40 units, scaled

    def test_the_studio_has_the_rows_on_its_layout_tab_for_a_new_layout_only(self):
        draft = dict(base._TEXT_DEFAULTS)
        draft.update(base._BOOL_DEFAULTS)
        draft[sl.KEY_LAYOUT] = "Poster"
        rows = studio.tab_rows(draft)
        self.assertIn(base.ID_OVERLAY, rows[0])  # Look
        for cid in (base.ID_APPEAR, base.ID_LEAVE, base.ID_PULSE):
            self.assertIn(cid, rows[4])  # Motion
        draft[sl.KEY_LAYOUT] = sl.LAYOUT_CARD
        rows = studio.tab_rows(draft)
        for cid in (base.ID_OVERLAY, base.ID_APPEAR, base.ID_LEAVE, base.ID_PULSE):
            self.assertNotIn(cid, rows[0] + rows[4])
        self.assertIn(base.ID_PULSE, studio.TOGGLE_ROWS)
        for key in (sl.KEY_OVERLAY, sl.KEY_APPEAR, sl.KEY_LEAVE):
            self.assertIn(key, base.DRAFT_TEXT_KEYS)
        self.assertIn(sl.KEY_PULSE, base.DRAFT_BOOL_KEYS)


if __name__ == "__main__":
    unittest.main()
