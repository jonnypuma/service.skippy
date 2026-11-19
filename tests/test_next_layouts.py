# -*- coding: utf-8 -*-
"""The layouts of the next episode popup besides the classic card."""
import os
import re
import unittest
import xml.etree.ElementTree as ET

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import addon_skin_resolution as resolution  # noqa: E402
import next_episode_appearance as app  # noqa: E402
import next_layout_dialog as dialog  # noqa: E402
import next_layouts as nl  # noqa: E402
import skip_layouts as sl  # noqa: E402
from tools import gen_next_layouts as gen  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SKINS = os.path.join(ROOT, "resources", "skins", "default")
DIALOG_PROPERTIES = {"nl_heading", "nl_label", "nl_play", "nl_close", "nl_picture", "nl_ring", "nl_seconds", "nl_logo",
                     "nl_q0_label", "nl_q1_label", "nl_q2_label", "nl_q0_thumb", "nl_q1_thumb", "nl_q2_thumb",
                     "next_ep_countdown", "skl_top", "skippy_dialog_ready"}


def read(res, name):
    with open(os.path.join(SKINS, res, name), encoding="utf-8") as handle:
        return handle.read()


class ChoiceTests(unittest.TestCase):
    def test_card_is_the_default_and_has_no_file(self):
        self.assertEqual(nl.LAYOUTS[0], nl.LAYOUT_CARD)
        self.assertEqual(nl.normalize_layout(None), nl.LAYOUT_CARD)
        self.assertEqual(nl.normalize_layout("play ring"), "Ring")
        self.assertEqual(nl.normalize_layout("Lower third"), "Band")
        with self.assertRaises(KeyError):
            nl.get(nl.LAYOUT_CARD)
        # a layout is a skin file of its own, or drawn by Skippy (CardA is only drawn)
        self.assertEqual({item.name for item in nl.all_layouts()} | set(nl.DRAWN_LAYOUTS), set(nl.NEW_LAYOUTS))
        self.assertTrue(nl.is_drawn("Play ring") and nl.is_drawn("CardA") and nl.is_drawn("Queue") and nl.is_drawn("Poster") and not nl.is_drawn(None))
        self.assertEqual(nl.get("Ring").xml, "NextLayout_Ring.xml")

    def test_the_draft_carries_layout_and_look(self):
        self.assertEqual(app.DEFAULT_DRAFT[app.KEY_LAYOUT], nl.DEFAULT_LAYOUT)
        self.assertEqual((nl.DEFAULT_LAYOUT, nl.DEFAULT_LOOK), ("CardA", "fgd"))  # the drawn Card in Fused Glass Dark
        self.assertEqual(app.DEFAULT_DRAFT[app.KEY_LAYOUT_LOOK], nl.DEFAULT_LOOK)
        self.assertEqual(app.CHOICE_KEYS[app.KEY_LAYOUT], nl.LAYOUTS)
        self.assertEqual(app.CHOICE_KEYS[app.KEY_LAYOUT_LOOK], sl.LOOKS)
        payload = app.draft_setting_payload({app.KEY_LAYOUT: "ring", app.KEY_LAYOUT_LOOK: "AGL"})
        self.assertEqual((payload[app.KEY_LAYOUT], payload[app.KEY_LAYOUT_LOOK]), ("Ring", "agl"))
        # the Customize screen has the layout as its second row; a new layout shows its own short list
        self.assertEqual(app.customize_rows(app.DEFAULT_DRAFT)[1:3], [app.KEY_PRESET, app.KEY_LAYOUT])  # a drawn design: its preset first
        # a drawn design: the preset, the two it is made of, its form and its size on screen
        self.assertEqual(app.customize_rows(dict(app.DEFAULT_DRAFT, **{app.KEY_LAYOUT: "Queue"})),
                         [app.KEY_STYLE, app.KEY_PRESET, app.KEY_LAYOUT, app.KEY_LAYOUT_LOOK, app.KEY_FORM, app.KEY_ZOOM,
                          app.KEY_POSITION, app.KEY_FOCUS])
        # every layout but the popup of earlier versions is drawn now, the Poster card too
        self.assertIn(app.KEY_FORM, app.customize_rows(dict(app.DEFAULT_DRAFT, **{app.KEY_LAYOUT: "Poster"})))

    def test_the_dialog_keeps_the_card_unless_a_layout_is_chosen(self):
        self.assertIsNone(dialog.layout_for({}))
        self.assertIsNone(dialog.layout_for({nl.KEY_LAYOUT: "Card"}))
        self.assertEqual(dialog.layout_for({nl.KEY_LAYOUT: "Slab"}).xml, "NextLayout_Slab.xml")
        self.assertEqual(dialog.look_code({nl.KEY_LAYOUT_LOOK: "Aeon Glass"}), "agl")
        self.assertEqual(dialog.look_code({}), sl.DEFAULT_LOOK)

    def test_the_settings_lists_are_the_choices_and_sit_above_the_look(self):
        root = ET.parse(os.path.join(ROOT, "resources", "settings.xml")).getroot()
        ids = [s.get("id") for s in root.iter("setting")]
        for key, options, default in ((nl.KEY_LAYOUT, nl.layout_options(), nl.DEFAULT_LAYOUT),
                                      (nl.KEY_LAYOUT_LOOK, nl.look_options(), nl.DEFAULT_LOOK)):
            setting = next(s for s in root.iter("setting") if s.get("id") == key)
            self.assertEqual([(o.get("label"), o.text) for o in setting.iter("option")], options, key)
            self.assertEqual(setting.find("default").text, default, key)
            self.assertLess(ids.index(key), ids.index("next_episode_popup_look"))


class DataTests(unittest.TestCase):
    def test_every_layout_is_on_the_screen_in_every_corner(self):
        for layout in nl.all_layouts():
            for corner in ("TopLeft", "TopRight", "BottomLeft", "BottomRight"):
                left, top = nl.origin(layout, corner)
                self.assertGreaterEqual(min(left, top), 0, (layout.xml, corner))
                self.assertLessEqual(left + layout.width, sl.CANVAS_W, (layout.xml, corner))
                self.assertLessEqual(top + layout.height, sl.CANVAS_H, (layout.xml, corner))

    def test_the_line_shrinks_with_the_countdown(self):
        poster = nl.get("Poster")
        self.assertEqual(nl.fill_width(poster, 100), poster.track[2])
        self.assertEqual(nl.fill_width(poster, 50), poster.track[2] // 2)
        self.assertEqual(nl.fill_width(poster, -5), 0)

    def test_the_picture_of_a_layout_and_its_fallbacks(self):
        episode = {"thumb": "wide.jpg", "poster": "poster.jpg", "fanart": "fan.jpg"}
        self.assertEqual(nl.picture(nl.get("Poster"), episode), "poster.jpg")
        self.assertEqual(nl.picture(nl.get("Slab"), episode), "wide.jpg")
        self.assertEqual(nl.picture(nl.get("Float"), episode), "")
        self.assertEqual(nl.picture(nl.get("Poster"), {"thumb": "wide.jpg"}), "wide.jpg")
        self.assertEqual(nl.picture(nl.get("Slab"), {"fanart": "fan.jpg"}), "fan.jpg")
        self.assertEqual(nl.picture(nl.get("Slab"), {"poster": "poster.jpg"}), "poster.jpg")
        self.assertEqual(nl.picture(nl.get("Slab"), None), "")

    def test_the_look_properties_are_those_of_the_skip_layouts(self):
        props = dialog.look_properties("fgd", "1080i")
        for name, value in sl.properties("fgd", "1080i").items():
            self.assertEqual(props[name], value, name)
        self.assertNotEqual(props["skl_ring_back"], "00000000")


class GeneratedFileTests(unittest.TestCase):
    def test_the_files_are_what_the_generator_writes(self):
        self.assertEqual(gen.stale(), [], "run python tools/gen_next_layouts.py")

    def test_ids_and_stacking(self):
        for res in ("720p", "1080i"):
            for layout in nl.all_layouts():
                root = ET.fromstring(read(res, layout.xml).split("?>", 1)[1])
                ids = [c.get("id") for c in root.iter("control") if c.get("id")]
                self.assertEqual(len(ids), len(set(ids)), (res, layout.xml))
                progress = nl.ID_RING if layout.progress == sl.PROGRESS_RING else nl.ID_BAR_FILL
                for wanted in (nl.ID_ROOT, nl.ID_PROBE, nl.ID_PLAY, nl.ID_CLOSE, progress):
                    self.assertIn(str(wanted), ids, (res, layout.xml, wanted))
                self.assertEqual(root.find("defaultcontrol").text, str(nl.ID_PLAY))
                # above the popup's Customize screen, so its Preview draws on top of it
                customize = ET.fromstring(read(res, "NextEpisodeCustomize.xml").split("?>", 1)[1])
                self.assertGreater(int(root.find("zorder").text), int(customize.find("zorder").text))

    def test_every_property_a_file_reads_is_one_the_dialog_sets(self):
        known = set(dialog.look_properties(sl.DEFAULT_LOOK, "720p")) | DIALOG_PROPERTIES | set(sl.HEAD_PROPERTIES)
        for layout in nl.all_layouts():
            used = set(re.findall(r"Window\.Property\(([A-Za-z0-9_]+)\)", read("720p", layout.xml)))
            self.assertLessEqual(used, known, (layout.xml, sorted(used - known)))

    def test_buttons_stay_inside_and_apart_and_name_their_focused_colour(self):
        for layout in nl.all_layouts():
            text = read("720p", layout.xml)
            root = ET.fromstring(text.split("?>", 1)[1])
            buttons = [tuple(int(c.find(tag).text) for tag in ("left", "top", "width", "height"))
                       for c in root.iter("control") if c.get("type") == "button"]
            wanted = 1 + nl.QUEUE_SIZE if layout.name == "Queue" else 2  # Queue: three cards and Close
            self.assertEqual(len(buttons), wanted, layout.xml)
            for left, top, width, height in buttons:
                self.assertGreaterEqual(min(left, top), 0, layout.xml)
                self.assertLessEqual(left + width, layout.width, layout.xml)
                self.assertLessEqual(top + height, layout.height, layout.xml)
            for first in range(len(buttons)):
                for second in range(first + 1, len(buttons)):
                    (l1, t1, w1, h1), (l2, t2, w2, h2) = buttons[first], buttons[second]
                    self.assertTrue(l1 + w1 <= l2 or l2 + w2 <= l1 or t1 + h1 <= t2 or t2 + h2 <= t1, layout.xml)
            named = 1 if layout.name == "Queue" else 2  # the cards of the Queue carry no text
            self.assertEqual(text.count("<focusedcolor>$INFO[Window.Property(skl_focus_text)]</focusedcolor>"), named)

    def test_the_skin_folder_can_be_told_from_the_probe(self):
        self.assertEqual(resolution.probe_control_ids_for_xml("NextLayout_Ring.xml"), (nl.ID_PROBE,))
        self.assertEqual(resolution.infer_skin_resolution_from_widths([nl.PROBE_W]), resolution.SKIN_RES_720P)
        self.assertEqual(resolution.infer_skin_resolution_from_widths([nl.PROBE_W * 3 // 2]), resolution.SKIN_RES_1080I)


if __name__ == "__main__":
    unittest.main()
