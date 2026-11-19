# -*- coding: utf-8 -*-
"""The drawn Up Next popup: its designs build for every look, and are entered where the popup is opened."""
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

import next_canvas as nc  # noqa: E402
import next_layouts as nl  # noqa: E402
import skip_canvas as cv  # noqa: E402
import skip_canvas_looks as looks  # noqa: E402

TEXTS = dict(thumb="thumb.jpg", fanart="fanart.jpg", poster="poster.jpg", logo="logo.png")


def drawing(design, size, look="fgd", **options):
    return nc.draw(cv.Options(design=design, size=size, look=look, **options), nc.Texts(**TEXTS))


class DesignTests(unittest.TestCase):
    def test_every_design_builds_in_three_sizes_for_every_look(self):
        for _stored, design, _name, _letter in nc.DESIGNS:
            for size in nc.SIZES:
                for look in looks.CODES:
                    found = drawing(design, size, look)
                    self.assertGreater(found.width, 0, (design, size, look))
                    self.assertTrue(-1 <= found.left and found.left + found.width <= cv.SCREEN_W + 1, (design, size, look))
                    self.assertTrue(-1 <= found.top and found.top + found.height <= cv.SCREEN_H + 1, (design, size, look))
                    # Play now is the engine's Skip button: every form has it
                    self.assertTrue(any(op["t"] == "button" and op["which"] == "skip" for op in found.ops), (design, size))

    def test_the_stored_layouts_are_the_drawn_ones(self):
        self.assertEqual(sorted(stored for stored, _d, _n, _l in nc.DESIGNS), sorted(nl.DRAWN_LAYOUTS))
        names = dict(nl.LAYOUT_NAMES)
        for stored, design, name, _letter in nc.DESIGNS:
            self.assertEqual(names[stored], name)
            self.assertEqual(nc.design_for(stored), design)
            if name != "Card":  # that name is also the stored value of the popup of earlier versions
                self.assertEqual(nc.design_for(name), design)
        self.assertIsNone(nc.design_for("Card"))
        self.assertFalse(nl.is_drawn("Card"))
        self.assertEqual(nc.design_for("Poster"), "NCard")  # the Poster card is the Card with the show's poster
        self.assertEqual(nc.design_for("Queue"), "NQueue")
        self.assertEqual(names[nl.LAYOUT_CARD], "Card (legacy)")
        self.assertEqual(nl.LAYOUTS[0], nl.LAYOUT_CARD)  # the popup people have stays the default

    def test_the_card_has_the_measures_of_the_mockup(self):
        card = drawing("NCard", "Full")
        self.assertEqual(card.width, 780)
        picture = next(op for op in card.ops if op["t"] == "pic")
        self.assertEqual(picture["rect"][2:], (320, 180))
        self.assertEqual(picture["src"], "thumb.jpg")
        self.assertEqual(sum(1 for op in card.ops if op["t"] == "button"), 2)
        # without Cancel, Play now takes the row
        alone = drawing("NCard", "Full", close=False)
        wide = next(op for op in alone.ops if op["t"] == "button")
        self.assertEqual(sum(1 for op in alone.ops if op["t"] == "button"), 1)
        self.assertAlmostEqual(wide["rect"][2], 780 - 2 * looks.LOOKS["fgd"]["pad"])

    def test_options_change_the_build(self):
        full = drawing("NCard", "Full")
        self.assertTrue(any(op["t"] == "para" for op in full.ops))
        self.assertFalse(any(op["t"] == "para" for op in drawing("NCard", "Full", plot=False).ops))
        self.assertFalse(any(op["t"] == "pic" for op in drawing("NCard", "Full", picture="Off").ops))
        self.assertLess(drawing("NCard", "Full", picture="Off").height, full.height)
        self.assertIsNone(drawing("NCard", "Full", progress="Off").find("fill"))
        self.assertIsNotNone(full.find("fill"))

    def test_poster_and_episode_stand_side_by_side_at_one_height(self):
        both = drawing("NCard", "Full", picture="Both")
        pictures = [op for op in both.ops if op["t"] == "pic"]
        self.assertEqual([op["src"] for op in pictures], ["poster.jpg", "thumb.jpg"])
        poster, thumb = (op["rect"] for op in pictures)
        self.assertEqual((poster[1], poster[3]), (thumb[1], thumb[3]))  # the same top and the same height
        self.assertGreaterEqual(thumb[0], poster[0] + poster[2])  # beside it: nothing lies over a picture
        self.assertAlmostEqual(poster[2] / poster[3], 2.0 / 3.0, places=2)
        self.assertEqual(both.width, drawing("NCard", "Full").width + 128)  # the card grows, the words keep their room
        for design in ("NRing", "NRail", "NSlab", "NBand"):
            found = [op["rect"] for op in drawing(design, "Full", picture="Both").ops if op["t"] == "pic"]
            self.assertEqual(len(found), 2, design)
            self.assertEqual((found[0][1], found[0][3]), (found[1][1], found[1][3]), design)
            self.assertLessEqual(found[0][0] + found[0][2], found[1][0], design)
        # the ring of Play ring is centred on the episode picture
        ring = drawing("NRing", "Full", picture="Both")
        thumb = [op["rect"] for op in ring.ops if op["t"] == "pic"][1]
        circle = ring.find("ring")["rect"]
        self.assertAlmostEqual(circle[0] + circle[2] / 2.0, thumb[0] + thumb[2] / 2.0, places=3)
        # no poster: the episode picture alone
        alone = nc.draw(cv.Options(design="NCard", size="Full", look="fgd", picture="Both"), nc.Texts(thumb="thumb.jpg"))
        self.assertEqual(len([op for op in alone.ops if op["t"] == "pic"]), 1)
        self.assertEqual(len([op for op in drawing("NCard", "Full", picture="Poster").ops if op["t"] == "pic"]), 1)

    def test_lines_with_the_time_left_keep_their_template(self):
        for design, size, key in (("NCard", "Compact", "starts_line"), ("NSlab", "Compact", "up_in"),
                                  ("NFloat", "Minimal", "lk"), ("NRail", "Full", "ring_time")):
            op = drawing(design, size).find(key)
            self.assertIsNotNone(op, (design, size))
            self.assertIn("{", op["fmt"])
            self.assertEqual(op["text"], op["fmt"].format(cd="0:20", secs="20"))

    def test_the_queue_has_three_cards_that_take_the_focus_and_a_third_button(self):
        queue = drawing("NQueue", "Full")
        cards = [op for op in queue.ops if op["t"] == "hot"]
        self.assertEqual([op["name"] for op in cards], ["q1", "q2", "q3"])
        self.assertEqual([op["shape"] for op in queue.ops if op["t"] == "pic"], ["r", "r2", "r3"])
        self.assertEqual(sorted(op["which"] for op in queue.ops if op["t"] == "button"), ["close", "more", "skip"])
        self.assertIsNotNone(queue.find("veil2"))
        self.assertAlmostEqual(queue.left + queue.width / 2.0, cv.SCREEN_W / 2.0)  # in the middle of the bottom edge
        self.assertEqual(queue.find("skip_label")["text"], "Play S1 E3")
        # one episode left: one card, and nothing to play later
        alone = nc.draw(cv.Options(design="NQueue", size="Full", look="fgd"), nc.Texts(queue=(("S1 E8", "End", "50 min", ""),)))
        self.assertEqual(len([op for op in alone.ops if op["t"] == "hot"]), 1)
        self.assertNotIn("more", [op["which"] for op in alone.ops if op["t"] == "button"])
        self.assertEqual(len([op for op in drawing("NQueue", "Compact").ops if op["t"] == "hot"]), 3)
        self.assertEqual(len([op for op in drawing("NQueue", "Minimal").ops if op["t"] == "hot"]), 0)

    def test_the_takeover_fills_the_screen_with_the_fanart(self):
        take = drawing("NTake", "Full", zoom=70)
        self.assertEqual((take.left, take.top, take.width, take.height), (0, 0, cv.SCREEN_W, cv.SCREEN_H))
        back = next(op for op in take.ops if op["t"] == "pic" and op["shape"] == "back")
        self.assertEqual(back["src"], "fanart.jpg")
        self.assertTrue(any(op["t"] == "pic" and op["shape"] == "logo" for op in take.ops))
        corner = drawing("NTake", "Compact")
        self.assertEqual(corner.left + corner.width, cv.SCREEN_W)  # the corner panel is flush

    def test_the_rail_and_the_slab_are_flush_and_the_band_spans_the_picture(self):
        self.assertEqual(drawing("NRail", "Full").left + drawing("NRail", "Full").width, cv.SCREEN_W)
        slab = drawing("NSlab", "Full")
        self.assertEqual((slab.left + slab.width, slab.top + slab.height), (cv.SCREEN_W, cv.SCREEN_H))
        band = drawing("NBand", "Full")
        self.assertEqual((band.left, band.width), (64, cv.SCREEN_W - 128))


class PresetTests(unittest.TestCase):
    """The Preset row of Customize Up Next, the Size rows, and a look saved under a name."""

    def setUp(self):
        import next_episode_appearance as app

        self.app = app
        self.draft = dict(app.DEFAULT_DRAFT)

    def test_a_new_draft_is_the_drawn_card_in_fused_glass_dark_at_full_size(self):
        app = self.app
        self.assertEqual((self.draft[app.KEY_LAYOUT], self.draft[app.KEY_LAYOUT_LOOK]), ("CardA", "fgd"))
        self.assertEqual((self.draft[app.KEY_FORM], self.draft[app.KEY_ZOOM]), ("Full", "100"))
        self.assertEqual(app.preset_name(*app.preset_of(self.draft)), "Card · Fused Glass Dark")
        self.assertEqual(app.customize_rows(self.draft)[1:6],
                         [app.KEY_PRESET, app.KEY_LAYOUT, app.KEY_LAYOUT_LOOK, app.KEY_FORM, app.KEY_ZOOM])

    def test_the_presets_are_every_drawn_design_in_every_look_and_the_legacy_card(self):
        import skip_layouts as sl

        app = self.app
        found = app.presets()
        self.assertEqual(len(found), len(nl.DRAWN_LAYOUTS) * len(sl.LOOKS) + 1)
        self.assertEqual(found[-1], (nl.LAYOUT_CARD, None))
        names = [app.preset_name(*item) for item in found]
        self.assertEqual(len(set(names)), len(names))
        self.assertEqual(names[-1], "Card (legacy)")
        # the twelve looks of their own (the "own ideas" boards) are presets of every design
        for own in ("Neon", "Paper", "Sunset", "Ocean", "Brutal", "Terminal", "Wireframe", "Luxe", "Pastel", "Gloss", "Mono", "VHS"):
            self.assertIn("Queue · %s" % own, names, own)
            self.assertIn("Card · %s" % own, names, own)

    def test_the_preset_row_steps_through_all_of_them_and_back(self):
        app = self.app
        seen = []
        for _ in range(len(app.presets())):
            seen.append(app.preset_of(self.draft))
            app.cycle_preset(self.draft, 1)
        self.assertEqual(len(set(seen)), len(app.presets()))
        self.assertEqual(app.preset_of(self.draft), ("CardA", "fgd"))  # once round
        app.cycle_preset(self.draft, -1)
        self.assertEqual(app.preset_of(self.draft), (nl.LAYOUT_CARD, None))
        self.assertEqual(self.draft[app.KEY_LAYOUT_LOOK], "fgd")  # the legacy card leaves the layout look alone
        self.assertNotIn(app.KEY_PRESET, app.draft_setting_payload(self.draft))  # the row is not a setting

    def test_size_and_form_are_stored_and_read_by_the_drawn_popup(self):
        app = self.app
        self.assertEqual(app.cycle_choice(app.KEY_ZOOM, "100", -1), "85")
        self.assertEqual(app.cycle_choice(app.KEY_FORM, "Full", 1), "Compact")
        self.draft.update({app.KEY_FORM: "Compact", app.KEY_ZOOM: "70"})
        payload = app.draft_setting_payload(self.draft)
        self.assertEqual((payload[app.KEY_FORM], payload[app.KEY_ZOOM]), ("Compact", "70"))
        self.assertEqual((app.KEY_FORM, app.KEY_ZOOM), (nc.PREFIX + "form", nc.PREFIX + "zoom"))
        small = nc.draw(cv.Options(design="NCard", size="Full", zoom=70), nc.Texts())
        large = nc.draw(cv.Options(design="NCard", size="Full", zoom=100), nc.Texts())
        self.assertAlmostEqual(small.width, large.width * 0.7, places=3)

    def test_a_look_saved_under_a_name_is_stored_loaded_again_and_deleted(self):
        import tempfile
        from unittest import mock

        from tests.kodi_stubs import install_kodi_stubs

        install_kodi_stubs()
        import next_episode_saved_looks as saved

        app = self.app
        with tempfile.TemporaryDirectory() as folder:
            with mock.patch.object(saved, "_store_path", lambda: os.path.join(folder, saved.USER_LOOKS_FILE)):
                self.draft.update({app.KEY_LAYOUT: "Queue", app.KEY_LAYOUT_LOOK: "neon", app.KEY_FORM: "Compact", app.KEY_ZOOM: "85"})
                self.assertEqual(saved.save_user_look("Test look", self.draft), (True, saved.SAVED))
                self.assertTrue(os.path.isfile(os.path.join(folder, saved.USER_LOOKS_FILE)))
                self.assertEqual([name for name, _values in saved.list_user_looks()], ["Test look"])
                # loaded into a fresh draft: the whole design comes back
                fresh = dict(app.DEFAULT_DRAFT)
                self.assertTrue(saved.apply_look(fresh, saved.load_user_looks()["Test look"]))
                self.assertEqual([fresh[key] for key in (app.KEY_LAYOUT, app.KEY_LAYOUT_LOOK, app.KEY_FORM, app.KEY_ZOOM)],
                                 ["Queue", "neon", "Compact", "85"])
                self.assertEqual(saved.detect_saved_look(fresh), "Test look")
                self.assertTrue(saved.delete_user_look("Test look"))
                self.assertEqual(saved.list_user_looks(), [])
                self.assertIsNone(saved.detect_saved_look(fresh))


class LastRowsTests(unittest.TestCase):
    """Follow the skin style, Keep clear of subtitles, Focus style."""

    def test_the_look_that_goes_with_the_skin(self):
        import skin_look

        def look(skin, flags=(), menu=""):
            return skin_look.look_for(skin, lambda name: name in flags, lambda name: menu)

        self.assertEqual(look("skin.aeon.fuse"), "aeo")
        self.assertEqual(look("skin.aeon.fuse", ("aeon.vglass",)), "agl")
        both = ("aeon.vglass", "aeon.fglass")
        self.assertEqual([look("skin.aeon.fuse", both, menu) for menu in ("", "glass", "frost", "system", "junk")],
                         ["fgd", "fgc", "fgf", "fgs", "fgd"])
        self.assertIsNone(look("skin.estuary", both, "frost"))  # another skin has no style to follow
        self.assertIsNone(look(None))

    def test_a_popup_at_the_bottom_stands_clear_of_the_subtitles(self):
        low = drawing("NCard", "Full")
        high = drawing("NCard", "Full", rise=150.0)
        self.assertEqual(high.top, low.top - 150)
        self.assertEqual(high.left, low.left)
        # one at the top stays, and so does one that fills the screen
        self.assertEqual(drawing("NCard", "Full", place="TopRight", rise=150.0).top, drawing("NCard", "Full", place="TopRight").top)
        self.assertEqual(drawing("NTake", "Full", rise=150.0).top, 0)

    def test_an_outlined_focus_keeps_the_ink_of_the_other_buttons(self):
        look = looks.look("fgd", "Skin")
        self.assertNotEqual(look["foc_ink"], look["btn_ink"])
        seen = {}

        def spy(found, texts, options):
            seen["look"] = found
            return nc.card_full(found, texts, options)

        saved = cv._BUILDERS[("NCard", "Full")]
        cv._BUILDERS[("NCard", "Full")] = spy
        try:
            drawing("NCard", "Full", focus_style="Outline")
            self.assertEqual(seen["look"]["foc_ink"], look["btn_ink"])
            drawing("NCard", "Full", focus_style="Accent")
            self.assertEqual(seen["look"]["foc_ink"], look["foc_ink"])
        finally:
            cv._BUILDERS[("NCard", "Full")] = saved
        for name in ("cv_fgd_focl_1080.png", "cv_fgd_pillfocl_720.png"):
            self.assertTrue(os.path.isfile(os.path.join(ROOT, "resources", "skins", "default", "media", name)), name)


class WiringTests(unittest.TestCase):
    def test_the_popup_opens_a_drawn_layout_with_the_drawn_dialog(self):
        with open(os.path.join(ROOT, "next_episode_dialog.py"), encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn("next_layouts.is_drawn(", source)
        self.assertIn("NextCanvasDialog, skip_canvas.XML", source)

    def test_every_option_is_a_setting(self):
        with open(os.path.join(ROOT, "resources", "settings.xml"), encoding="utf-8") as handle:
            text = handle.read()
        for name in nc.OPTION_KEYS:
            self.assertIn('id="%s%s"' % (nc.PREFIX, name), text)

    def test_the_window_file_has_the_picture_slots(self):
        for res in ("720p", "1080i"):
            with open(os.path.join(ROOT, "resources", "skins", "default", res, cv.XML), encoding="utf-8") as handle:
                text = handle.read()
            for slot in ("back", "back_shade", "pic", "pic_s", "pic_h", "logo"):
                self.assertIn('id="%d"' % cv.SLOT_IDS[slot], text, (res, slot))
            self.assertIn('diffuse="cv_mask_r.png"', text)
            # the picture behind everything lies under the shade and the card
            self.assertLess(text.index('id="%d"' % cv.SLOT_IDS["back"]), text.index('id="%d"' % cv.SLOT_IDS["overlay9"]))
        for name in ("cv_mask_r.png", "cv_mask_s.png", "cv_ov_take.png"):
            self.assertTrue(os.path.isfile(os.path.join(ROOT, "resources", "skins", "default", "media", name)), name)

    def test_the_new_strings_are_in_every_language(self):
        folder = os.path.join(ROOT, "resources", "language")
        for lang in os.listdir(folder):
            with open(os.path.join(folder, lang, "strings.po"), encoding="utf-8") as handle:
                text = handle.read()
            for sid in range(49192, 49197):
                self.assertIn('msgctxt "#%d"' % sid, text, (lang, sid))


if __name__ == "__main__":
    unittest.main()
