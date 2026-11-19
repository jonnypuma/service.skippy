# -*- coding: utf-8 -*-
"""The drawn skip dialog: the build of the Stack card follows its options, in every look."""
import os
import unittest

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import skip_canvas as cv  # noqa: E402
import skip_canvas_draw as draw  # noqa: E402
import skip_canvas_looks as looks  # noqa: E402
import skip_layouts as sl  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MEDIA = os.path.join(ROOT, "resources", "skins", "default", "media")


def button(drawing, which):
    return next(op for op in drawing.ops if op["t"] == "button" and op["which"] == which)


class StackCardTests(unittest.TestCase):
    def test_the_full_card_is_640_wide_and_64_from_the_corner_as_in_the_mockup(self):
        d = cv.draw(cv.Options(look="fgd"), cv.Texts())
        self.assertEqual(round(d.width), 640)
        self.assertEqual((round(cv.SCREEN_W - d.left - d.width), round(cv.SCREEN_H - d.top - d.height)), (64, 64))
        for key in ("kicker", "range", "heading", "nested", "chip", "fill", "skip_label", "skip_time", "close_label"):
            self.assertIsNotNone(d.find(key), key)

    def test_without_close_skip_takes_the_whole_row(self):
        with_close = cv.draw(cv.Options(look="fgd"), cv.Texts())
        without = cv.draw(cv.Options(look="fgd", close=False), cv.Texts())
        self.assertFalse([op for op in without.ops if op.get("which") == "close"])
        pad = looks.LOOKS["fgd"]["pad"]
        self.assertAlmostEqual(button(without, "skip")["rect"][2], 640 - 2 * pad, places=3)
        self.assertLess(button(with_close, "skip")["rect"][2], button(without, "skip")["rect"][2])

    def test_options_take_parts_away(self):
        plain = cv.draw(cv.Options(look="fgd", icons=False, kicker=False, nested=False, progress="Off"), cv.Texts())
        for key in ("kicker", "range", "nested", "chip", "fill", "skip_icon", "close_icon"):
            self.assertIsNone(plain.find(key), key)
        self.assertLess(plain.height, cv.draw(cv.Options(look="fgd"), cv.Texts()).height)

    def test_aeon_buttons_are_flush_with_the_card(self):
        d = cv.draw(cv.Options(look="aeo"), cv.Texts())
        skip, close = button(d, "skip")["rect"], button(d, "close")["rect"]
        self.assertAlmostEqual(skip[0], d.left, places=3)
        self.assertAlmostEqual(skip[0] + skip[2], close[0], places=3)  # no gap between them
        self.assertAlmostEqual(close[0] + close[2], d.left + d.width, places=3)
        self.assertAlmostEqual(close[1] + close[3], d.top + d.height, places=3)

    def test_nine_places_and_the_size_on_screen(self):
        d = cv.draw(cv.Options(look="fgd", place="TopLeft"), cv.Texts())
        self.assertEqual((round(d.left), round(d.top)), (64, 64))
        d = cv.draw(cv.Options(look="fgd", place="Bottom"), cv.Texts())
        self.assertAlmostEqual(d.left + d.width / 2.0, cv.SCREEN_W / 2.0, places=3)
        big = cv.draw(cv.Options(look="fgd", zoom=125), cv.Texts())
        self.assertEqual(round(big.width), 800)
        self.assertEqual(cv.place_name("bottom right"), "BottomRight")
        self.assertEqual(cv.place_name("nonsense"), "BottomRight")

    def test_small_forms(self):
        compact = cv.draw(cv.Options(look="fgd", size="Compact"), cv.Texts())
        minimal = cv.draw(cv.Options(look="fgd", size="Minimal"), cv.Texts())
        self.assertEqual(round(compact.height), 84)
        self.assertEqual(round(minimal.height), 72)
        self.assertTrue(button(compact, "close")["ghost"])
        self.assertEqual([op["slot"] for op in compact.ops if op["t"] == "slot" and op["slot"].startswith("plate")], ["plate_c"])
        hard = cv.draw(cv.Options(look="aeo", size="Compact"), cv.Texts())
        self.assertEqual([op["slot"] for op in hard.ops if op["t"] == "slot" and op["slot"].startswith("plate")], ["plate_h"])

    def test_capitals_get_room(self):
        self.assertGreater(cv.estimate("CLOSE", 24, True), cv.estimate("Close", 24, True) * 1.2)

    def test_neon_glows_and_brutal_casts_a_hard_shadow(self):
        neon = cv.draw(cv.Options(look="neon"), cv.Texts())
        self.assertEqual(next(op for op in neon.ops if op.get("slot") == "shadow")["tex"], "glow")
        brutal = cv.draw(cv.Options(look="brutal"), cv.Texts())
        shadow = next(op for op in brutal.ops if op.get("slot") == "shadow")
        plate = next(op for op in brutal.ops if op.get("slot") == "plate")
        self.assertEqual(shadow["tex"], "cv_black.png")
        self.assertEqual((round(shadow["rect"][0] - plate["rect"][0]), round(shadow["rect"][1] - plate["rect"][1])), (12, 12))


class PictureTests(unittest.TestCase):
    def test_every_look_has_its_pictures_in_both_folders(self):
        for code in looks.CODES:
            self.assertIn(code, sl.LOOKS)
            for corners in looks.CORNERS:
                for folder in ("1080", "720"):
                    for part in ("plate", "box", "chip", "btn", "foc", "pill", "pillfoc", "platec", "platem"):
                        name = cv.picture(code, corners, part, folder)
                        self.assertTrue(os.path.isfile(os.path.join(MEDIA, name)), name)

    def test_the_skin_file_has_every_slot(self):
        for res in ("720p", "1080i"):
            with open(os.path.join(ROOT, "resources", "skins", "default", res, cv.XML), encoding="utf-8") as handle:
                text = handle.read()
            for slot, cid in cv.SLOT_IDS.items():
                self.assertIn('id="%d"' % cid, text, (res, slot))
            for cid in (cv.ID_SKIP, cv.ID_CLOSE, cv.ID_PROBE, cv.ID_ROOT):
                self.assertIn('id="%d"' % cid, text)


class FontTests(unittest.TestCase):
    FONTS = ('<fonts><fontset id="Default"><font><name>font13</name><filename>Figtree-Regular.ttf</filename><size>25</size></font>'
             '<font><name>font30</name><filename>Figtree-SemiBold.ttf</filename><size>30</size></font>'
             '<font><name>font32</name><filename>special://xbmc/media/Fonts/arial.ttf</filename><size>32</size></font>'
             '<font><name>font10</name><filename>Figtree-Regular.ttf</filename><size>21</size></font>'
             '<font><name>title_50</name><filename>Figtree-Bold.ttf</filename><size>50</size></font></fontset></fonts>')

    def test_one_family_and_weights(self):
        fonts = draw.parse_fonts(self.FONTS)
        self.assertEqual(fonts, {"font13": (25.0, False), "font30": (30.0, True), "font10": (21.0, False)})

    def test_a_bold_text_takes_the_bold_file_and_is_zoomed_to_size(self):
        fonts = draw.parse_fonts(self.FONTS)
        name, zoom, wrap = draw.pick_font(fonts, 32, True)
        self.assertEqual((name, wrap), ("font30", False))
        self.assertAlmostEqual(zoom, 106.67, places=1)
        name, zoom, wrap = draw.pick_font(fonts, 20, False)
        self.assertEqual((name, wrap), ("font10", False))
        self.assertAlmostEqual(zoom, 95.24, places=1)
        self.assertEqual(draw.pick_font(fonts, 25.5, False)[1], 100.0)  # within four percent: no zoom
        self.assertEqual(draw.pick_font({"font13": (25.0, False)}, 25, True), ("font13", 100.0, True))


class LayoutTests(unittest.TestCase):
    def test_stack_is_a_layout_without_a_file_of_its_own(self):
        self.assertEqual(sl.LAYOUT_NAMES[1], ("Stack", "Stack card"))
        self.assertTrue(sl.is_canvas("Stack"))
        self.assertFalse(sl.is_canvas("Poster"))
        for size in sl.SIZES:
            layout = sl.get("Stack", size)
            self.assertTrue(layout.canvas)
            self.assertEqual(layout.xml, cv.XML)
            self.assertNotIn(layout, sl.all_layouts())

class MoreDesignTests(unittest.TestCase):
    TEXTS = dict(kicker="Intermission", ending="Intermission ending in", countdown="2:40", skip="Skip intermission",
                 skip_word="Skip", nested_time="2:20:15", chip="Entr'acte", rest="Part two", percent=50.0)

    def test_every_design_builds_in_every_size_and_look(self):
        for name, _shown in cv.DESIGNS:
            self.assertTrue(sl.is_canvas(name), name)
            for size in ("Full", "Compact", "Minimal"):
                for code in ("fgd", "aeo", "paper"):
                    d = cv.draw(cv.Options(design=name, size=size, look=code), cv.Texts(**self.TEXTS))
                    self.assertGreater(d.width, 0, (name, size, code))
                    self.assertTrue([op for op in d.ops if op["t"] == "button" and op["which"] == "skip"], (name, size))

    def test_the_type_is_said_once(self):
        d = cv.draw(cv.Options(design="Stack", look="fgd"), cv.Texts(**self.TEXTS))
        self.assertEqual(d.find("skip_label")["text"], "Skip")
        d = cv.draw(cv.Options(design="Stack", look="fgd", size="Minimal"), cv.Texts(**self.TEXTS))
        self.assertEqual(d.find("skip_label")["text"], "Skip intermission")  # nothing else names it there
        plain = dict(self.TEXTS, ending="Ends in")
        d = cv.draw(cv.Options(design="Stack", look="fgd", kicker=False), cv.Texts(**plain))
        self.assertEqual(d.find("skip_label")["text"], "Skip intermission")

    def test_the_split_tile_fills_from_its_foot_and_the_timeline_follows_the_playhead(self):
        d = cv.draw(cv.Options(design="Split", look="fgd"), cv.Texts(**self.TEXTS))
        fill = d.find("fill")
        self.assertEqual((fill["t"], fill["slot"], fill["vertical"]), ("fillslot", "fill_v", True))
        self.assertAlmostEqual(fill["rect"][3], fill["track"][3] / 2.0, places=3)
        d = cv.draw(cv.Options(design="Timeline", look="fgd"), cv.Texts(**self.TEXTS))
        for key in ("playhead", "arc", "now"):
            self.assertIn("follow", d.find(key), key)
        self.assertAlmostEqual(d.left + d.width / 2.0, cv.SCREEN_W / 2.0, places=3)  # in the middle of the bottom edge
        rail = cv.draw(cv.Options(design="Rail", look="fgd"), cv.Texts(**self.TEXTS))
        self.assertAlmostEqual(rail.left + rail.width, cv.SCREEN_W, places=3)  # on the screen edge

    def test_text_size_and_text_shadow(self):
        normal = cv.draw(cv.Options(design="Float", look="fgd"), cv.Texts(**self.TEXTS))
        large = cv.draw(cv.Options(design="Float", look="fgd", text_size=130), cv.Texts(**self.TEXTS))
        self.assertAlmostEqual(large.find("lead")["size"], normal.find("lead")["size"] * 1.3, places=3)
        self.assertTrue(normal.find("lead")["shadow"])
        # the words before the time stand still: the time has its own place at the line's end
        self.assertIsNone(normal.find("heading"))
        other = cv.draw(cv.Options(design="Float", look="fgd"), cv.Texts(**dict(self.TEXTS, countdown="1:11")))
        self.assertEqual(other.find("lead")["rect"], normal.find("lead")["rect"])
        self.assertEqual(other.find("countdown")["rect"][0], normal.find("countdown")["rect"][0])
        self.assertEqual(cv.text_size("junk"), 100)
        self.assertEqual(cv.text_size("120"), 115)
        self.assertEqual(cv.estimate("abc", 20), cv.estimate("abc", 20))  # the factor is put back after a drawing
        self.assertEqual(list(draw.SHADES), list(cv.TEXT_SHADOWS))
        counts = [len(draw.SHADES[name][0]) for name in cv.TEXT_SHADOWS]
        self.assertEqual(counts, sorted(counts))

    def test_long_capitals_are_not_cut_off(self):
        d = cv.draw(cv.Options(design="Float", look="aeo"), cv.Texts(**self.TEXTS))
        self.assertGreater(d.width, 760)

class OptionTests(unittest.TestCase):
    TEXTS = dict(kicker="Intro", ending="Intro ending in", countdown="0:42", skip="Skip intro", skip_word="Skip",
                 nested_time="2:11", percent=50.0)

    def test_size_on_screen_zooms_the_whole_and_keeps_its_parts(self):
        full = cv.draw(cv.Options(design="Timeline", look="fgd"), cv.Texts(**self.TEXTS))
        small = cv.draw(cv.Options(design="Timeline", look="fgd", zoom=70), cv.Texts(**self.TEXTS))
        self.assertAlmostEqual(small.width, full.width * 0.7, places=3)
        self.assertEqual(small.zoom, 70.0)
        # the parts are laid out at full size: a button is as high as ever, so its corners keep their shape
        self.assertEqual(button(small, "skip")["rect"], button(full, "skip")["rect"])
        # the foot of the dialog stays where it was
        self.assertAlmostEqual(small.top + small.height, full.top + full.height, places=3)
        self.assertAlmostEqual(small.anchor[1], full.top + full.height, places=3)

    def test_every_panel_casts_a_shade_and_a_low_card_takes_the_small_one(self):
        split = cv.draw(cv.Options(design="Split", look="fgd"), cv.Texts(**self.TEXTS))
        self.assertEqual(len([op for op in split.ops if str(op.get("slot", "")).startswith("shadow")]), 3)
        compact = cv.draw(cv.Options(design="Stack", look="fgd", size="Compact"), cv.Texts(**self.TEXTS))
        self.assertEqual([op["slot"] for op in compact.ops if str(op.get("slot", "")).startswith("shadow")], ["shadow_s"])
        for op in compact.ops + split.ops:
            if str(op.get("slot", "")).startswith("shadow"):
                border = cv.BORDERS["1080"]["shadow_s" if op["slot"].startswith("shadow_s") else "shadow"]
                self.assertGreaterEqual(min(op["rect"][2], op["rect"][3]), 2 * border, op["slot"])

    def test_no_shadow_on_the_time_inside_a_ring_and_a_mild_one_over_a_shade(self):
        dial = cv.draw(cv.Options(design="Dial", look="fgd"), cv.Texts(**self.TEXTS))
        self.assertFalse(dial.find("countdown").get("shadow"))
        self.assertTrue(dial.overlaid)  # the Dial has its rounded shade
        self.assertFalse(cv.draw(cv.Options(design="Float", look="fgd"), cv.Texts(**self.TEXTS)).overlaid)

    def test_progress_styles(self):
        line = cv.draw(cv.Options(design="Stack", look="fgd"), cv.Texts(**self.TEXTS))
        fill = cv.draw(cv.Options(design="Stack", look="fgd", progress="Fill"), cv.Texts(**self.TEXTS))
        ring = cv.draw(cv.Options(design="Stack", look="fgd", progress="Circle"), cv.Texts(**self.TEXTS))
        self.assertEqual(line.find("fill")["t"], "rect")
        self.assertEqual(fill.find("fill")["t"], "fillslot")
        self.assertIsNotNone(ring.find("ring"))
        self.assertIsNone(ring.find("fill"))
        self.assertLess(fill.height, line.height)  # the line has gone into the button
        dial = cv.draw(cv.Options(design="Dial", look="fgd", progress="Fill"), cv.Texts(**self.TEXTS))
        self.assertIsNotNone(dial.find("ring"))  # a ring design keeps its ring

    def test_motion(self):
        shown, leaving, beating = "A", "B", "C"
        plain = cv.motion(cv.Options(), (100, 200), True, shown, leaving, beating)
        # hidden until shown, comes with a fade, goes with a fade; no beat unless asked for
        self.assertEqual([attrs.split(" condition=")[1] for _event, attrs in plain], ["!A", "A", "B"])
        self.assertTrue(all(event == "conditional" for event, _attrs in plain))
        rich = cv.motion(cv.Options(appear="Slide", leave="Shrink", pulse=True), (100, 200), True, shown, leaving, beating)
        text = " | ".join(attrs for _event, attrs in rich)
        self.assertIn("effect=slide start=70,0 end=0,0", text)  # from the side the dialog stands at
        self.assertIn("effect=zoom start=100 end=92 center=100.0,200.0", text)
        self.assertIn("pulse=true condition=C", text)
        left = cv.motion(cv.Options(appear="Slide"), (100, 200), False, shown, leaving, beating, reach=0.5)
        self.assertIn("effect=slide start=-35,0", " | ".join(attrs for _event, attrs in left))
        shade = cv.motion(cv.Options(appear="Pop", leave="Drop", pulse=True), (1, 2), True, shown, leaving, beating, fade_only=True)
        self.assertTrue(all("effect=fade" in attrs for _event, attrs in shade))
        for name in cv.APPEARS:
            self.assertIn(name, cv.APPEAR_MS)
            self.assertIn(name, sl.APPEARS)
        for name in cv.LEAVES:
            self.assertIn(name, cv.LEAVE_MS)
            self.assertIn(name, sl.LEAVES)

    def test_the_gradient_switch_fades_a_square_overlay(self):
        solid = cv.draw(cv.Options(design="Stack", look="fgd", overlay="Square"), cv.Texts(**self.TEXTS))
        faded = cv.draw(cv.Options(design="Stack", look="fgd", overlay="Square", overlay_gradient=True), cv.Texts(**self.TEXTS))
        round_ = cv.draw(cv.Options(design="Stack", look="fgd", overlay="Square", overlay_gradient=True, gradient="Radial"),
                         cv.Texts(**self.TEXTS))
        name = lambda d: next(op["tex"] for op in d.ops if str(op.get("slot", "")).startswith("overlay"))  # noqa: E731
        self.assertEqual(name(solid), "solid")
        self.assertEqual(name(faded), "side_r")
        self.assertTrue(name(round_).startswith("glow_"))


if __name__ == "__main__":
    unittest.main()
