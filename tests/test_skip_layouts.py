# -*- coding: utf-8 -*-
"""The skip dialog layouts besides the classic card: the data, the generated files and the dialog."""
import os
import re
import unittest
import xml.etree.ElementTree as ET

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import addon_skin_resolution as resolution  # noqa: E402
import skip_layout_dialog as dialog  # noqa: E402
import skip_layouts as sl  # noqa: E402
from tools import gen_skip_layouts as gen  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SKINS = os.path.join(ROOT, "resources", "skins", "default")
MEDIA = os.path.join(SKINS, "media")
# Properties the dialog sets besides those of a look.
DIALOG_PROPERTIES = {
    "skl_skip", "skl_skip_short", "skl_skip_word", "skl_close", "skl_kicker", "skl_range", "skl_heading", "skl_t0",
    "skl_t1", "skl_seconds", "skl_ring", "skl_top", "skl_mock", "skl_poster", "countdown", "next_jump_label", "show_next_jump",
    "skippy_dialog_ready",
}


class _Addon:
    def __init__(self, **values):
        self.values = values

    def getSetting(self, key):
        return self.values.get(key, "")

    def getSettingString(self, key):
        return self.values.get(key, "")


def read(res, name):
    with open(os.path.join(SKINS, res, name), encoding="utf-8") as handle:
        return handle.read()


def controls(res, layout):
    root = ET.fromstring(read(res, layout.xml).split("?>", 1)[1])
    group = next(c for c in root.iter("control") if c.get("id") == str(sl.ID_ROOT))
    return root, [c for c in group.findall("control")]


def rect(control):
    return tuple(int(control.find(tag).text) for tag in ("left", "top", "width", "height"))


class ChoiceTests(unittest.TestCase):
    def test_card_is_the_default_and_has_no_file(self):
        self.assertEqual(sl.LAYOUTS[0], sl.LAYOUT_CARD)
        self.assertEqual(sl.normalize_layout(None), sl.LAYOUT_CARD)
        self.assertEqual(sl.normalize_layout("nonsense"), sl.LAYOUT_CARD)
        self.assertTrue(sl.is_card(""))
        with self.assertRaises(KeyError):
            sl.get(sl.LAYOUT_CARD, sl.SIZE_FULL)

    def test_normalize_takes_stored_values_and_names(self):
        self.assertEqual(sl.normalize_layout("dial"), "Dial")
        self.assertEqual(sl.normalize_layout("Corner slab"), "Slab")
        self.assertEqual(sl.normalize_layout(" side rail "), "Rail")
        self.assertEqual(sl.normalize_look("Fused Glass Dark"), "fgd")
        self.assertEqual(sl.normalize_look("AGL"), "agl")
        self.assertEqual(sl.normalize_look("junk"), sl.DEFAULT_LOOK)

    def test_every_new_layout_has_a_full_a_compact_and_a_minimal_file(self):
        # the skin files: three per name (a design that is drawn now keeps its earlier files for the preview copies)
        files = sorted({item.name for item in sl.all_layouts()})
        self.assertEqual(len(sl.all_layouts()), 3 * len(files))
        # the Minimal forms come last: the preview copies of the others keep their ids
        self.assertTrue(all(item.size == sl.SIZE_MINIMAL for item in sl.all_layouts()[2 * len(files):]))
        self.assertEqual(sl.get("Poster", sl.SIZE_MINIMAL).xml, "SkipLayout_PosterMinimal.xml")
        names = set()
        for name in sl.NEW_LAYOUTS:
            for size in sl.SIZES:
                layout = sl.get(name, size)
                self.assertEqual((layout.name, layout.size), (name, size))
                if not layout.canvas:
                    names.add(layout.xml)
        self.assertEqual(len({item.xml for item in sl.all_layouts()}), len(sl.all_layouts()))
        self.assertLessEqual(names, {item.xml for item in sl.all_layouts()})
        self.assertEqual(sl.get("Poster", sl.SIZE_FULL).xml, "SkipLayout_Poster.xml")
        self.assertEqual(sl.get("Poster", sl.SIZE_COMPACT).xml, "SkipLayout_PosterCompact.xml")

    def test_the_mode_picks_the_size(self):
        self.assertEqual(sl.size_for_mode("Full"), sl.SIZE_FULL)
        self.assertEqual(sl.size_for_mode("CompactFull"), sl.SIZE_COMPACT)
        self.assertEqual(sl.size_for_mode("Compact Full"), sl.SIZE_COMPACT)
        self.assertEqual(sl.size_for_mode(None), sl.SIZE_FULL)

    def test_the_dialog_keeps_the_card_for_card_only(self):
        self.assertIsNone(dialog.layout_for(_Addon(skip_dialog_mode="Full")))
        self.assertIsNone(dialog.layout_for(_Addon(skip_dialog_mode="Full", skip_dialog_layout="Card")))
        self.assertIsNone(dialog.layout_for(_Addon(skip_dialog_mode="Minimal", skip_dialog_layout="Card")))
        self.assertEqual(dialog.layout_for(_Addon(skip_dialog_mode="Minimal", skip_dialog_layout="Poster")).xml,
                         "SkipLayout_PosterMinimal.xml")
        self.assertEqual(dialog.layout_for(_Addon(skip_dialog_mode="Full", skip_dialog_layout="Poster")).xml,
                         "SkipLayout_Poster.xml")
        self.assertEqual(dialog.layout_for(_Addon(skip_dialog_mode="CompactFull", skip_dialog_layout="Poster")).xml,
                         "SkipLayout_PosterCompact.xml")

    def test_the_settings_lists_are_the_choices(self):
        root = ET.parse(os.path.join(ROOT, "resources", "settings.xml")).getroot()
        for key, options, default in ((sl.KEY_LAYOUT, sl.layout_options(), sl.DEFAULT_LAYOUT),
                                      (sl.KEY_LOOK, sl.look_options(), sl.DEFAULT_SKIP_LOOK)):
            setting = next(s for s in root.iter("setting") if s.get("id") == key)
            self.assertEqual([(o.get("label"), o.text) for o in setting.iter("option")], options, key)
            self.assertEqual(setting.find("default").text, default, key)


class PlacementTests(unittest.TestCase):
    def test_a_corner_layout_keeps_the_margin(self):
        dial = sl.get("Dial", sl.SIZE_FULL)
        self.assertEqual(sl.origin(dial, "BottomRight"),
                         (sl.CANVAS_W - sl.MARGIN - dial.width, sl.CANVAS_H - sl.MARGIN - dial.height))
        self.assertEqual(sl.origin(dial, "TopLeft"), (sl.MARGIN, sl.MARGIN))
        self.assertEqual(sl.origin(dial, None), sl.origin(dial, "BottomRight"))

    def test_the_slab_sits_in_the_corner_itself(self):
        slab = sl.get("Slab", sl.SIZE_FULL)
        self.assertEqual(sl.origin(slab, "BottomRight"), (sl.CANVAS_W - slab.width, sl.CANVAS_H - slab.height))
        self.assertEqual(sl.origin(slab, "TopLeft"), (0, 0))

    def test_band_rail_and_timeline(self):
        band = sl.get("Band", sl.SIZE_FULL)
        self.assertEqual(sl.origin(band, "BottomLeft"), (0, sl.CANVAS_H - band.height))
        self.assertEqual(sl.origin(band, "TopRight"), (0, 0))
        rail = sl.get("Rail", sl.SIZE_FULL)
        self.assertEqual(sl.origin(rail, "TopRight"), (sl.CANVAS_W - rail.width, (sl.CANVAS_H - rail.height) // 2))
        self.assertEqual(sl.origin(rail, "BottomLeft")[0], 0)
        line = next(item for item in sl.all_layouts() if (item.name, item.size) == ("Timeline", sl.SIZE_FULL))
        self.assertEqual(sl.origin(line, "BottomRight")[0], (sl.CANVAS_W - line.width) // 2)
        self.assertEqual(sl.origin(line, "TopLeft")[1], sl.MARGIN)

    def test_every_layout_is_on_the_screen_in_every_corner(self):
        for layout in sl.all_layouts():
            for corner in ("TopLeft", "TopRight", "BottomLeft", "BottomRight"):
                left, top = sl.origin(layout, corner)
                self.assertGreaterEqual(left, 0, (layout.xml, corner))
                self.assertGreaterEqual(top, 0, (layout.xml, corner))
                self.assertLessEqual(left + layout.width, sl.CANVAS_W, (layout.xml, corner))
                self.assertLessEqual(top + layout.height, sl.CANVAS_H, (layout.xml, corner))


class ProgressTests(unittest.TestCase):
    def test_a_line_grows_to_the_right(self):
        poster = sl.get("Poster", sl.SIZE_FULL)  # a layout that is still a skin file with a line
        self.assertEqual(sl.fill_size(poster, 0), (116, 100, 0, 4))
        self.assertEqual(sl.fill_size(poster, 50), (116, 100, 194, 4))
        self.assertEqual(sl.fill_size(poster, 250), (116, 100, 388, 4))

    def test_the_full_tile_fills_up_from_its_bottom(self):
        split = sl.get("Split", sl.SIZE_FULL)
        left, top, width, height = split.track
        self.assertEqual(sl.fill_size(split, 0), (left, top + height, width, 0))
        self.assertEqual(sl.fill_size(split, 50), (left, top + height // 2, width, height // 2))
        self.assertEqual(sl.fill_size(split, 100), (left, top, width, height))

    def test_the_compact_tile_fills_up_from_its_left(self):
        split = sl.get("Split", sl.SIZE_COMPACT)
        left, top, width, height = split.track
        self.assertEqual(sl.fill_size(split, 50), (left, top, width // 2, height))

    def test_ring_frames(self):
        self.assertEqual(sl.ring_frame(0), "sl_ring_00.png")
        self.assertEqual(sl.ring_frame(100), "sl_ring_%02d.png" % sl.RING_FRAMES)
        self.assertEqual(sl.ring_frame(50), "sl_ring_25.png")
        self.assertEqual(sl.ring_frame("junk"), "sl_ring_00.png")
        self.assertEqual(sl.ring_frame(400), "sl_ring_%02d.png" % sl.RING_FRAMES)
        for step in range(sl.RING_FRAMES + 1):
            self.assertTrue(os.path.isfile(os.path.join(MEDIA, "sl_ring_%02d.png" % step)), step)

    def test_the_timeline_spans_the_segment(self):
        line = next(item for item in sl.all_layouts() if (item.name, item.size) == ("Timeline", sl.SIZE_FULL))
        left, _top, width, _height = line.track
        parts = sl.timeline_parts(line, 5, 70, 37.5, jump=25)
        self.assertEqual(parts["playhead"], left + width // 2)
        self.assertEqual(parts["jump_width"], sl.JUMP_MARK_W)
        self.assertEqual(parts["jump_left"], left + int(round(20 / 65.0 * width)))

    def test_a_jump_outside_the_segment_has_no_mark(self):
        line = next(item for item in sl.all_layouts() if (item.name, item.size) == ("Timeline", sl.SIZE_FULL))
        for jump in (None, 70, 5, 200, "junk"):
            self.assertEqual(sl.timeline_parts(line, 5, 70, 10, jump=jump)["jump_width"], 0, jump)
        self.assertEqual(sl.timeline_parts(line, 5, 5, 5)["jump_width"], 0)

    def test_clock_and_seconds_left(self):
        self.assertEqual(sl.clock(65), "01:05")
        self.assertEqual(sl.clock(3725), "1:02:05")
        self.assertEqual(sl.clock("junk"), "00:00")
        self.assertEqual(sl.seconds_left("00:59"), "59")
        self.assertEqual(sl.seconds_left("01:05"), "1:05")
        self.assertEqual(sl.seconds_left(""), "")


class LookTests(unittest.TestCase):
    def test_every_look_has_its_pictures(self):
        for code in sl.LOOKS:
            for res in ("720p", "1080i"):
                for name, value in sl.properties(code, res).items():
                    if value.endswith(".png"):
                        self.assertTrue(os.path.isfile(os.path.join(MEDIA, value)), (code, name, value))
        self.assertEqual(sl.texture("fgf", "button", "720p"), "sl_fgf_button_720.png")
        self.assertEqual(sl.texture("fgf", "focus", "1080i"), "sl_fgf_focus_1080.png")
        self.assertEqual(sl.texture("fgf", "plate", "720p"), sl.texture("fgf", "plate", "1080i"))

    def test_text_on_a_white_focus_is_dark_and_the_caps_looks_are_the_square_ones(self):
        for code in ("fgd", "fgf", "fgc", "aeo"):
            self.assertLess(int(sl.look(code).focus_text[2:4], 16), 0x40, code)
        for code in ("fgs", "agl"):
            self.assertEqual(sl.look(code).focus_text, "FFFFFFFF", code)
        self.assertEqual({code for code in sl.FUSE_LOOKS if sl.look(code).caps}, {"fgs", "aeo"})

    def test_no_colour_is_all_zero(self):
        # Kodi draws a colordiffuse of 00000000 as white.
        for code in sl.LOOKS:
            for name, value in sl.properties(code).items():
                self.assertNotEqual(value, "00000000", (code, name))


class GeneratedFileTests(unittest.TestCase):
    def test_the_files_are_what_the_generator_writes(self):
        self.assertEqual(gen.stale(), [], "run python tools/gen_skip_layouts.py")

    def test_every_property_a_file_reads_is_one_the_dialog_sets(self):
        known = set(sl.properties(sl.DEFAULT_LOOK)) | DIALOG_PROPERTIES | set(sl.HEAD_PROPERTIES)
        for layout in sl.all_layouts():
            used = set(re.findall(r"Window\.Property\(([A-Za-z0-9_]+)\)", read("720p", layout.xml)))
            self.assertLessEqual(used, known, (layout.xml, sorted(used - known)))

    def test_ids_of_every_file(self):
        for res in ("720p", "1080i"):
            for layout in sl.all_layouts():
                root, inside = controls(res, layout)
                ids = [c.get("id") for c in root.iter("control") if c.get("id")]
                self.assertEqual(len(ids), len(set(ids)), (res, layout.xml))
                for wanted in (sl.ID_ROOT, sl.ID_PROBE, sl.ID_SKIP):
                    self.assertIn(str(wanted), ids, (res, layout.xml))
                self.assertEqual(str(sl.ID_CLOSE) in ids, layout.has_close, (res, layout.xml))
                self.assertEqual(root.find("defaultcontrol").text, str(sl.ID_SKIP))
                progress_id = sl.ID_RING if layout.progress == sl.PROGRESS_RING else sl.ID_BAR_FILL
                self.assertIn(str(progress_id), ids, (res, layout.xml))
                self.assertEqual(str(sl.ID_PLAYHEAD) in ids, layout.progress == sl.PROGRESS_TIMELINE)
                self.assertTrue(inside)

    def test_buttons_stay_inside_the_layout_and_do_not_overlap(self):
        for layout in sl.all_layouts():
            _root, inside = controls("720p", layout)
            buttons = [rect(c) for c in inside if c.get("type") == "button"]
            for left, top, width, height in buttons:
                self.assertGreaterEqual(left, 0, layout.xml)
                self.assertGreaterEqual(top, 0, layout.xml)
                self.assertLessEqual(left + width, layout.width, layout.xml)
                self.assertLessEqual(top + height, layout.height, layout.xml)
            if len(buttons) == 2:
                (l1, t1, w1, h1), (l2, t2, w2, h2) = buttons
                apart = l1 + w1 <= l2 or l2 + w2 <= l1 or t1 + h1 <= t2 or t2 + h2 <= t1
                self.assertTrue(apart, layout.xml)

    def test_the_track_is_where_the_data_says(self):
        for layout in sl.all_layouts():
            _root, inside = controls("720p", layout)
            wanted = sl.ID_RING if layout.progress == sl.PROGRESS_RING else sl.ID_BAR_FILL
            fill = next(c for c in inside if c.get("id") == str(wanted))
            left, top, width, height = rect(fill)
            if layout.progress == sl.PROGRESS_RING:
                self.assertEqual((left, top, width, height), layout.track, layout.xml)
            else:
                self.assertEqual((left, top), layout.track[:2], layout.xml)
            self.assertLessEqual(layout.track[0] + layout.track[2], layout.width, layout.xml)
            self.assertLessEqual(layout.track[1] + layout.track[3], layout.height, layout.xml)

    def test_pill_buttons_have_the_border_of_their_folder(self):
        for res, border in (("720p", sl.BUTTON_BORDER_720), ("1080i", sl.BUTTON_BORDER_1080)):
            text = read(res, "SkipLayout_Slab.xml")
            self.assertIn('<texture border="%d">$INFO[Window.Property(skl_focus)]</texture>' % border, text)
            self.assertNotIn("BTN", text)
        self.assertEqual(2 * sl.BUTTON_BORDER_720, sl.BUTTON_H)
        self.assertEqual(2 * sl.BUTTON_BORDER_1080, sl.BUTTON_H * 3 // 2)

    def test_the_buttons_name_their_focused_colour(self):
        # A skin's default focused colour would win otherwise (see the skip dialog files).
        for layout in sl.all_layouts():
            text = read("720p", layout.xml)
            self.assertEqual(text.count("<focusedcolor>$INFO[Window.Property(skl_focus_text)]</focusedcolor>"),
                             2 if layout.has_close else 1, layout.xml)

    def test_the_skin_folder_can_be_told_from_the_probe(self):
        self.assertEqual(resolution.probe_control_ids_for_xml("SkipLayout_Dial.xml"), (sl.ID_PROBE,))
        self.assertEqual(resolution.infer_skin_resolution_from_widths([sl.PROBE_W]), resolution.SKIN_RES_720P)
        self.assertEqual(resolution.infer_skin_resolution_from_widths([sl.PROBE_W * 3 // 2]), resolution.SKIN_RES_1080I)
        for res, width in (("720p", sl.PROBE_W), ("1080i", sl.PROBE_W * 3 // 2)):
            root = ET.fromstring(read(res, "SkipLayout_Dial.xml").split("?>", 1)[1])
            probe = next(c for c in root.iter("control") if c.get("id") == str(sl.ID_PROBE))
            self.assertEqual(int(probe.find("width").text), width, res)


class CustomizeTests(unittest.TestCase):
    """Customize Skip Dialog picks a layout and its look and shows a small copy of it."""

    @classmethod
    def setUpClass(cls):
        import skip_dialog_customize_ui as ui

        cls.ui = ui

    def test_the_draft_carries_layout_and_look(self):
        ui = self.ui
        self.assertEqual((sl.DEFAULT_LAYOUT, sl.DEFAULT_SKIP_LOOK), ("Stack", "fgd"))  # the Stack card in Fused Glass Dark
        for key, default in ((sl.KEY_LAYOUT, sl.DEFAULT_LAYOUT), (sl.KEY_LOOK, sl.DEFAULT_SKIP_LOOK)):
            self.assertIn(key, ui.DRAFT_TEXT_KEYS)
            self.assertEqual(ui._TEXT_DEFAULTS[key], default)

    def test_the_layout_of_a_draft(self):
        ui = self.ui
        self.assertIsNone(ui.draft_layout({"skip_dialog_mode": "Full"}))
        self.assertIsNone(ui.draft_layout({"skip_dialog_mode": "Minimal"}))
        self.assertEqual(ui.draft_layout({"skip_dialog_mode": "Minimal", sl.KEY_LAYOUT: "Poster"}).xml,
                         "SkipLayout_PosterMinimal.xml")
        self.assertEqual(ui.draft_layout({"skip_dialog_mode": "Full", sl.KEY_LAYOUT: "Poster"}).xml, "SkipLayout_Poster.xml")
        self.assertEqual(ui.draft_layout({"skip_dialog_mode": "CompactFull", sl.KEY_LAYOUT: "Poster"}).xml,
                         "SkipLayout_PosterCompact.xml")

    def test_the_pickers_in_focus_order(self):
        ui = self.ui
        self.assertEqual(ui.customize_picker_ids({"skip_dialog_mode": "Full"}), [ui.ID_PREVIEW_TYPE, ui.ID_LAYOUT])
        self.assertEqual(ui.customize_picker_ids({"skip_dialog_mode": "Full", sl.KEY_LAYOUT: "Rail"}),
                         [ui.ID_PREVIEW_TYPE, ui.ID_LAYOUT, ui.ID_LOOK])
        # Minimal mode has a form of every layout too, so the pickers stay
        self.assertEqual(ui.customize_picker_ids({"skip_dialog_mode": "Minimal", sl.KEY_LAYOUT: "Rail"}),
                         [ui.ID_PREVIEW_TYPE, ui.ID_LAYOUT, ui.ID_LOOK])
        self.assertEqual(ui.customize_picker_ids({"skip_dialog_mode": "Minimal"}), [ui.ID_PREVIEW_TYPE, ui.ID_LAYOUT])

    def test_a_new_layout_shows_only_the_rows_that_apply_to_it(self):
        ui = self.ui
        ids = ui.customize_nav_ids({"skip_dialog_mode": "Full", sl.KEY_LAYOUT: "Dial",
                                    "skip_button_format": "Skip + Type"})
        self.assertEqual(ids, [ui.ID_PRESET, ui.ID_MODE, ui.ID_OVERLAP, ui.ID_COUNTDOWN, ui.ID_POSITION, ui.ID_SKIP_FORMAT,
                               ui.ID_SAVE, ui.ID_CANCEL])
        with_duration = ui.customize_nav_ids({"skip_dialog_mode": "Full", sl.KEY_LAYOUT: "Dial",
                                              "skip_button_format": "Skip + Type + Duration"})
        self.assertIn(ui.ID_DURATION_FORMAT, with_duration)
        for card_only in (ui.ID_FONT, ui.ID_CARD, ui.ID_PROGRESS_STYLE, ui.ID_FOCUS_STYLE):
            self.assertNotIn(card_only, with_duration)

    def test_the_card_keeps_its_rows(self):
        ui = self.ui
        plain = ui.customize_nav_ids({"skip_dialog_mode": "Full"})
        self.assertEqual(plain, ui.customize_nav_ids({"skip_dialog_mode": "Full", sl.KEY_LAYOUT: "Card"}))
        self.assertEqual(plain[:2], [ui.ID_PRESET, ui.ID_MODE])

    def test_the_screen_holds_the_pickers_and_a_copy_of_every_layout(self):
        for res in ("720p", "1080i"):
            text = read(res, gen.CUSTOMIZE)
            root = ET.fromstring(text.split("?>", 1)[1])
            ids = [c.get("id") for c in root.iter("control") if c.get("id")]
            for wanted in (sl.ID_PICK_LAYOUT, sl.ID_PICK_LOOK, sl.ID_MOCK_SCREEN):
                self.assertEqual(ids.count(str(wanted)), 1, (res, wanted))
            for index, layout in enumerate(sl.all_layouts()):
                offset = sl.mock_offset(index)
                self.assertEqual(ids.count(str(sl.ID_ROOT + offset)), 1, (res, layout.xml))
                progress = sl.ID_RING if layout.progress == sl.PROGRESS_RING else sl.ID_BAR_FILL
                self.assertEqual(ids.count(str(progress + offset)), 1, (res, layout.xml))
                self.assertIn("String.IsEqual(Window.Property(skl_mock),%s)" % layout.xml[:-4], text)
            # a preview copy has no button of its own: nothing in it can take the focus
            screen = next(c for c in root.iter("control") if c.get("id") == str(sl.ID_MOCK_SCREEN))
            self.assertEqual([c for c in screen.iter("control") if c.get("type") == "button"], [], res)

    def test_preview_ids_do_not_meet_each_other_or_the_screen(self):
        offsets = [sl.mock_offset(i) for i in range(len(sl.all_layouts()))]
        self.assertTrue(all(b - a >= 100 for a, b in zip(offsets, offsets[1:])))
        self.assertGreater(sl.ID_ROOT + offsets[0], sl.ID_MOCK_SCREEN)

    def test_the_small_screen_fits_the_stage(self):
        self.assertLessEqual(sl.MOCK_LEFT + sl.CANVAS_W * sl.MOCK_ZOOM / 100.0, sl.STAGE_W)
        self.assertLessEqual(sl.MOCK_TOP + sl.CANVAS_H * sl.MOCK_ZOOM / 100.0, sl.STAGE_H)
        self.assertLessEqual(2 * sl.CHIP_W + 8, sl.STAGE_W)


if __name__ == "__main__":
    unittest.main()
