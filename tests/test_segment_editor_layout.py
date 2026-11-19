# -*- coding: utf-8 -*-
"""The segment editor's three layouts: the setting, the two generated skin files and the timeline."""
import os
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

from tests import fake_gui  # noqa: E402

import addon_skin_resolution as resolution  # noqa: E402
import segment_editor_layout as lay  # noqa: E402
import skippy_modal_style as style  # noqa: E402
from tools import gen_segment_editor_layouts as gen  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SKINS = os.path.join(ROOT, "resources", "skins", "default")
NEW_FILES = (lay.XML_FILES[lay.LAYOUT_SIDE], lay.XML_FILES[lay.LAYOUT_DRAWER])
ALL_BUTTONS = gen.ROW_ACTIONS + gen.SEEK + gen.MARK + gen.FILE


class FakeAddon:
    def __init__(self, value):
        self.value = value

    def getSetting(self, key):
        assert key == lay.SETTING_KEY
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


def controls(res, name):
    root = ET.parse(os.path.join(SKINS, res, name)).getroot()
    return root, {c.get("id"): c for c in root.iter("control") if c.get("id")}


class ChoiceTests(unittest.TestCase):
    def test_three_layouts_and_list_and_drawer_is_the_default(self):
        self.assertEqual(lay.LAYOUTS, ("side", "drawer", "classic"))
        self.assertEqual(lay.DEFAULT_LAYOUT, "side")
        self.assertEqual(lay.current_layout(FakeAddon("drawer")), "drawer")
        self.assertEqual(lay.current_layout(FakeAddon(" Classic ")), "classic")
        for bad in ("", None, "b", 2):
            self.assertEqual(lay.current_layout(FakeAddon(bad)), "side", bad)
        self.assertEqual(lay.current_layout(FakeAddon(RuntimeError("no settings"))), "side")

    def test_each_layout_has_its_file_and_the_classic_file_is_the_old_one(self):
        self.assertEqual(lay.xml_base("classic"), "SegmentEditorDialog.xml")
        self.assertEqual(lay.xml_base("side"), "SegmentEditorDialogA.xml")
        self.assertEqual(lay.xml_base("drawer"), "SegmentEditorDialogB.xml")
        self.assertEqual(lay.xml_base("nonsense"), "SegmentEditorDialogA.xml")
        for name in lay.XML_FILES.values():
            self.assertIn(name, style.STYLED_WINDOWS)
            self.assertEqual(resolution.probe_control_ids_for_xml(style.xml_name(name, "aeon")), (resolution.EDITOR_LIST_PROBE_ID,))

    def test_the_settings_file_offers_the_three_layouts(self):
        root = ET.parse(os.path.join(ROOT, "resources", "settings.xml")).getroot()
        setting = [s for s in root.iter("setting") if s.get("id") == lay.SETTING_KEY][0]
        self.assertEqual(setting.findtext("default"), lay.DEFAULT_LAYOUT)
        options = setting.find("constraints").find("options").findall("option")
        self.assertEqual([o.text for o in options], list(lay.LAYOUTS))
        self.assertTrue(all(o.get("label").isdigit() for o in options))

    def test_the_session_opens_the_file_of_the_chosen_layout(self):
        with open(os.path.join(ROOT, "segment_editor_session.py"), encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn("segment_editor_layout.current_layout(addon)", source)
        self.assertIn("skippy_modal_style.xml_name(segment_editor_layout.xml_base(layout),", source)
        self.assertIn("style = segment_editor_layout.style_for(layout, addon)", source)
        self.assertIn("style=style, addon=addon)", source)
        self.assertIn('carried = getattr(dialog, "_reopen_with", None)', source)  # another look: the editor opens again
        self.assertIn("layout=layout", source)


class ChipTests(unittest.TestCase):
    def test_built_in_types_have_their_own_chip(self):
        for label, key in (("intro", "intro"), ("Recap", "recap"), ("Behind The Scenes", "bts"), ("behind_the_scenes", "bts"),
                           ("cold open", "prologue"), ("Epilogue", "epilogue"), ("credits", "credits"), ("segment", "segment")):
            self.assertEqual(lay.chip_key(label), key, label)
            self.assertEqual(lay.chip_texture(label), "seg_%s.png" % key)

    def test_no_name_is_grey_and_a_type_of_the_users_own_has_a_colour_it_keeps(self):
        for label in ("", None):
            self.assertEqual(lay.chip_texture(label), "seg_other.png", label)
        for label in ("My own type", "sponsor read", "Song", "extra3"):
            key = lay.chip_key(label)
            self.assertRegex(key, r"^extra[1-8]$", label)
            self.assertEqual(lay.chip_key(label.upper()), key)  # the same name, the same colour
            self.assertNotEqual(lay.CHIP_COLORS[key], lay.CHIP_COLORS["other"])
        spare = [lay.CHIP_COLORS["extra%d" % n] for n in range(1, lay.EXTRA_COLOURS + 1)]
        self.assertEqual(len(set(spare)), lay.EXTRA_COLOURS)
        self.assertFalse(set(spare) & {v for k, v in lay.CHIP_COLORS.items() if not k.startswith("extra")})

    def test_every_chip_texture_exists_and_prologue_and_epilogue_differ(self):
        for key in lay.CHIP_COLORS:
            self.assertTrue(os.path.isfile(os.path.join(SKINS, "media", "seg_%s.png" % key)), key)
        colours = [lay.CHIP_COLORS[k] for k in ("intro", "recap", "commercial", "prologue", "preview", "credits", "epilogue",
                                                 "bts", "featurette")]
        self.assertEqual(len(set(colours)), len(colours))


class TimelineMathTests(unittest.TestCase):
    def test_blocks_are_placed_in_proportion(self):
        blocks = lay.timeline_blocks([(0, 100, "recap"), (100, 300, "intro"), (900, 1000, "credits")], 1000, 500)
        self.assertEqual([(b.left, b.width, b.index) for b in blocks], [(0, 50, 0), (50, 100, 1), (450, 50, 2)])
        self.assertEqual([b.texture for b in blocks], ["seg_recap.png", "seg_intro.png", "seg_credits.png"])

    def test_a_short_segment_stays_visible_and_inside_the_track(self):
        blocks = lay.timeline_blocks([(10, 11, "intro"), (2999, 3000, "credits")], 3000, 600)
        self.assertEqual(blocks[0].width, lay.MIN_BLOCK_WIDTH)
        self.assertEqual(blocks[1].left + blocks[1].width, 600)

    def test_times_outside_the_video_are_clamped(self):
        blocks = lay.timeline_blocks([(-5, 50, "intro"), (90, 400, "credits")], 100, 200)
        self.assertEqual((blocks[0].left, blocks[0].width), (0, 100))
        self.assertEqual((blocks[1].left, blocks[1].width), (180, 20))

    def test_no_duration_or_no_track_draws_nothing(self):
        self.assertEqual(lay.timeline_blocks([(0, 10, "intro")], 0, 500), [])
        self.assertEqual(lay.timeline_blocks([(0, 10, "intro")], 100, 0), [])
        self.assertEqual(lay.timeline_blocks([(0, 10, "intro")], None, None), [])
        self.assertEqual(lay.timeline_blocks([("x", 10, "intro"), (0, 10, "intro")], 100, 100)[0].index, 1)

    def test_only_as_many_blocks_as_there_are_controls(self):
        many = [(i, i + 1, "intro") for i in range(40)]
        blocks = lay.timeline_blocks(many, 100, 1000)
        self.assertEqual(len(blocks), len(lay.BLOCK_IDS))
        self.assertEqual(blocks[-1].index, len(lay.BLOCK_IDS) - 1)

    def test_playhead(self):
        self.assertEqual(lay.playhead_left(0, 100, 400), 0)
        self.assertEqual(lay.playhead_left(25, 100, 400), 100)
        self.assertEqual(lay.playhead_left(500, 100, 400), 400)
        self.assertEqual(lay.playhead_left(10, 0, 400), -1)
        self.assertEqual(lay.playhead_left("x", 100, 400), -1)

    def test_short_time(self):
        self.assertEqual(lay.short_time(3072), "51:12")
        self.assertEqual(lay.short_time(13680), "3:48:00")
        self.assertEqual(lay.short_time(59.6), "1:00")
        self.assertEqual(lay.short_time(0), "")
        self.assertEqual(lay.short_time(None), "")


class SkinFileTests(unittest.TestCase):
    def test_the_generated_files_are_up_to_date(self):
        self.assertEqual(gen.stale(), [], "run python3 tools/gen_segment_editor_layouts.py")

    def test_every_button_of_the_editor_is_in_both_layouts_once(self):
        fake_gui.reset()
        self.addCleanup(fake_gui.reset)
        module = fake_gui.load("segment_editor_dialog", self)
        self.assertEqual(set(ALL_BUTTONS), set(module._EDITOR_BUTTON_IDS))
        self.assertEqual(len(ALL_BUTTONS), 39)
        for res in ("720p", "1080i"):
            for name in NEW_FILES:
                root, found = controls(res, name)
                ids = [c.get("id") for c in root.iter("control") if c.get("id")]
                self.assertEqual(len(ids), len(set(ids)), (res, name))
                buttons = sorted(int(c.get("id")) for c in root.iter("control") if c.get("type") == "button")
                # List and drawer has two more: its Look row (the dark overlay, the look of the panels)
                extra = list(lay.LOOK_BUTTON_IDS) if name == lay.XML_FILES[lay.LAYOUT_SIDE] else []
                self.assertEqual(buttons, sorted(list(ALL_BUTTONS) + extra), (res, name))
                for cid in ("5000", "5001", "5008"):
                    self.assertIn(cid, found, (res, name))
                self.assertEqual(found["5000"].get("type"), "list")
                self.assertEqual(root.findtext("defaultcontrol"), "5018")

    def test_navigation_only_points_at_controls_that_exist_and_every_button_can_be_reached(self):
        for res in ("720p", "1080i"):
            for name in NEW_FILES:
                root, found = controls(res, name)
                reached = {"5018"}
                edges = {}
                for cid, ctrl in found.items():
                    targets = [ctrl.findtext(t) for t in ("onup", "ondown", "onleft", "onright") if ctrl.findtext(t)]
                    for target in targets:
                        self.assertIn(target, found, (res, name, cid))
                    edges[cid] = targets
                todo = ["5018"]
                while todo:
                    for target in edges.get(todo.pop(), ()):
                        if target not in reached:
                            reached.add(target)
                            todo.append(target)
                self.assertLessEqual({str(i) for i in ALL_BUTTONS} | {"5000"}, reached, (res, name))

    def test_the_list_width_tells_the_resolution(self):
        for res in ("720p", "1080i"):
            for name in NEW_FILES:
                _root, found = controls(res, name)
                width = int(found["5000"].findtext("width"))
                self.assertEqual(resolution.infer_skin_resolution_from_widths([width]), res, (name, width))

    def test_the_drawer_list_is_horizontal_and_the_side_list_is_not(self):
        _root, found = controls("720p", lay.XML_FILES[lay.LAYOUT_DRAWER])
        self.assertEqual(found["5000"].findtext("orientation"), "horizontal")
        _root, found = controls("720p", lay.XML_FILES[lay.LAYOUT_SIDE])
        self.assertIsNone(found["5000"].find("orientation"))

    def test_the_timeline_controls_are_there(self):
        for res in ("720p", "1080i"):
            for name in NEW_FILES:
                _root, found = controls(res, name)
                for cid in (lay.TRACK_ID, lay.PLAYHEAD_ID, lay.SELECTED_MARK_ID, lay.END_LABEL_ID) + lay.BLOCK_IDS:
                    self.assertIn(str(cid), found, (res, name, cid))
                # the List and drawer layout has blocks with round corners (a larger picture, a larger border)
                border = "10" if name == lay.XML_FILES[lay.LAYOUT_SIDE] else "4"
                self.assertEqual(found[str(lay.BLOCK_IDS[0])].find("texture").get("border"), border)
                self.assertLess(int(found[str(lay.BLOCK_IDS[0])].findtext("left")), 0)  # parked until Python places it

    def test_the_overlay_is_first_and_nothing_leaves_the_screen(self):
        for res, (width, height) in (("720p", (1280, 720)), ("1080i", (1920, 1080))):
            for name in NEW_FILES:
                root, _found = controls(res, name)
                first = root.find("controls").find("control")
                self.assertEqual((first.get("type"), first.findtext("width"), first.findtext("height")), ("image", str(width), str(height)))
                self.assertIn("EnableFullscreenOverlay", first.findtext("visible"))
                for group in root.find("controls").findall("control")[1:]:
                    left, top = int(group.findtext("left")), int(group.findtext("top"))
                    self.assertLessEqual(left + int(group.findtext("width")), width, (res, name))
                    self.assertLessEqual(top + int(group.findtext("height")), height, (res, name))
                    inner_w, inner_h = int(group.findtext("width")), int(group.findtext("height"))
                    for ctrl in group.findall("control"):
                        if ctrl.get("type") != "button":
                            continue
                        self.assertLessEqual(int(ctrl.findtext("left")) + int(ctrl.findtext("width")), inner_w, (res, name, ctrl.get("id")))
                        self.assertLessEqual(int(ctrl.findtext("top")) + int(ctrl.findtext("height")), inner_h, (res, name, ctrl.get("id")))

    def test_buttons_do_not_overlap(self):
        for name in NEW_FILES:
            root, _found = controls("720p", name)
            for group in root.find("controls").findall("control")[1:]:
                boxes = [(int(c.findtext("left")), int(c.findtext("top")), int(c.findtext("width")), int(c.findtext("height")), c.get("id"))
                         for c in group.findall("control") if c.get("type") == "button"]
                for i, a in enumerate(boxes):
                    for b in boxes[i + 1:]:
                        apart = a[0] + a[2] <= b[0] or b[0] + b[2] <= a[0] or a[1] + a[3] <= b[1] or b[1] + b[3] <= a[1]
                        self.assertTrue(apart, (name, a[4], b[4]))


class DialogTests(unittest.TestCase):
    def setUp(self):
        fake_gui.reset()
        self.addCleanup(fake_gui.reset)
        self.m = fake_gui.load("segment_editor_dialog", self)
        patcher = patch.object(self.m, "set_editor_modal_open")
        patcher.start()
        self.addCleanup(patcher.stop)

    def editor(self, layout, *segments, duration=1000.0, timeline=True):
        kwargs = dict(video_path="/videos/movie.mkv", segments=list(segments))
        if layout is not None:
            kwargs["layout"] = layout
        d = self.m.SegmentEditorDialog("SegmentEditorDialogA.xml", "/addon", "default", **kwargs)
        d.player = MagicMock()
        d.player.isPlayingVideo.return_value = True
        d.player.getTime.return_value = 0.0
        d.player.getTotalTime.return_value = duration
        d.list_control = fake_gui.with_id(fake_gui.ControlList(), 5000)
        d.addControl(d.list_control)
        for cid in self.m._LIST_ROW_ACTION_IDS + (5040, 5018):
            d.addControl(fake_gui.with_id(fake_gui.ControlButton(7, 9, 10, 10, ""), cid))
        if timeline:
            d.addControl(fake_gui.with_id(fake_gui.ControlImage(16, 32, 500, 30, ""), lay.TRACK_ID))
            for cid in lay.BLOCK_IDS:
                d.addControl(fake_gui.with_id(fake_gui.ControlImage(-9999, 32, 10, 30, ""), cid))
            d.addControl(fake_gui.with_id(fake_gui.ControlImage(-9999, 64, 10, 3, ""), lay.SELECTED_MARK_ID))
            d.addControl(fake_gui.with_id(fake_gui.ControlImage(-9999, 27, 2, 40, ""), lay.PLAYHEAD_ID))
            d.addControl(fake_gui.with_id(fake_gui.ControlLabel(0, 0, 10, 10, ""), lay.END_LABEL_ID))
        with patch.object(d, "_get_playback_duration_seconds", return_value=duration):
            d.refresh_list()
        return d

    def seg(self, start, end, label="intro"):
        return self.m.SegmentItem(start, end, label, source="edl")

    def test_without_a_layout_the_dialog_is_the_classic_one(self):
        d = self.editor(None, self.seg(0, 10), timeline=False)
        self.assertEqual(d._layout, "classic")
        self.assertTrue(d._row_buttons_follow)
        self.assertEqual(d.getControl(5021).x, d._edit_btn_left)  # moved to the highlighted row, as before

    def test_the_new_layouts_leave_the_row_buttons_where_the_skin_put_them(self):
        for layout in ("side", "drawer"):
            d = self.editor(layout, self.seg(0, 10), self.seg(20, 30))
            self.assertFalse(d._row_buttons_follow)
            d._update_edit_delete_positions()
            self.assertEqual((d.getControl(5021).x, d.getControl(5021).y), (7, 9), layout)
            self.assertTrue(d.getControl(5021).visible)

    def test_only_the_drawer_resyncs_on_left_and_right(self):
        for layout, expected in (("side", 0), ("classic", 0), ("drawer", 2)):
            d = self.editor(layout, self.seg(0, 10), timeline=layout != "classic")
            d.setFocus(d.list_control)
            with patch.object(d, "_schedule_sync_list_selection") as sync:
                d.act(fake_gui.ACTION_MOVE_LEFT)
                d.act(fake_gui.ACTION_MOVE_RIGHT)
            self.assertEqual(sync.call_count, expected, layout)

    def test_rows_carry_the_chip_of_their_type(self):
        d = self.editor("side", self.seg(0, 10, "intro"), self.seg(20, 30, "credits"), self.seg(40, 50, "my type"))
        chips = [d.list_control.getListItem(i).getProperty("type_chip") for i in range(3)]
        self.assertEqual(chips, ["seg_intro.png", "seg_credits.png", lay.chip_texture("my type")])

    def test_the_timeline_gets_a_block_per_segment_and_hides_the_rest(self):
        d = self.editor("side", self.seg(0, 100, "recap"), self.seg(100, 300, "intro"), duration=1000.0)
        first, second, third = (d.getControl(cid) for cid in lay.BLOCK_IDS[:3])
        self.assertEqual((first.x, first.y, first.getWidth(), first.visible), (16, 32, 50, True))
        self.assertEqual((second.x, second.getWidth()), (16 + 50, 100))
        self.assertFalse(third.visible)
        self.assertEqual(d.getControl(lay.END_LABEL_ID).label, "16:40")

    def test_the_mark_sits_under_the_highlighted_segment_and_the_playhead_moves(self):
        d = self.editor("drawer", self.seg(0, 100, "recap"), self.seg(100, 300, "intro"), duration=1000.0)
        mark = d.getControl(lay.SELECTED_MARK_ID)
        self.assertEqual((mark.x, mark.getWidth(), mark.visible), (16, 50, True))
        d.list_control.selectItem(1)
        d._update_edit_delete_positions()
        self.assertEqual((mark.x, mark.getWidth()), (16 + 50, 100))
        with patch.object(d, "_get_playback_duration_seconds", return_value=1000.0):
            d._update_playhead(500.0)
        playhead = d.getControl(lay.PLAYHEAD_ID)
        self.assertEqual((playhead.x, playhead.visible), (16 + 250 - 1, True))

    def test_a_layout_without_timeline_controls_is_left_alone(self):
        d = self.editor("classic", self.seg(0, 10), timeline=False)
        d._update_timeline()
        d._update_playhead(5.0)
        d._update_timeline_selection()  # nothing to do, and nothing raised

    def test_buttons_take_their_colours_from_the_window_look(self):
        d = self.editor("side", self.seg(0, 10))
        button = MagicMock()
        button.getLabel.return_value = "Save"
        d._set_button_label_font(button)
        args = button.setLabel.call_args[0]
        colours = style.colors()
        self.assertEqual(args[0:2], ("Save", "font10"))
        self.assertEqual(args[2], "0x" + colours["ms_text"])
        self.assertEqual(args[5], "0x" + colours["ms_text_focus"])
        self.assertEqual(args[4], "0x00000000")

class WindowTests(unittest.TestCase):
    def test_clock(self):
        self.assertEqual(lay.clock(0), "0:00")
        self.assertEqual(lay.clock(134.9), "2:14")
        self.assertEqual(lay.clock(3725), "1:02:05")
        self.assertEqual(lay.clock("junk"), "0:00")

    def test_the_track_shows_the_stretch_around_the_highlighted_segment(self):
        # the mockup: a recap (0:00 - 0:46) and the intro right after it (0:46 - 2:14) are shown on 0:00 - 3:00
        parts = [(0, 46), (46, 134), (2860, 3072), (3020, 3072)]
        self.assertEqual(lay.connected_span(parts, 1), (0.0, 134.0))  # the intro with the recap it follows
        self.assertEqual(lay.connected_span(parts, 0), (0.0, 134.0))
        self.assertEqual(lay.connected_span(parts, 3), (2860.0, 3072.0))  # a preview inside the credits
        self.assertIsNone(lay.connected_span(parts, 9))
        self.assertEqual(lay.connected_span([(0, 10), (30, 40)], 0), (0.0, 10.0))  # apart: not connected
        first, last = lay.timeline_window(lay.connected_span(parts, 1), 3072)
        self.assertEqual(first, 0.0)
        self.assertAlmostEqual(last, 180.0, delta=1.0)
        first, last = lay.timeline_window((2860, 3072), 3072)  # the credits at the end: the stretch ends with the file
        self.assertEqual(last, 3072.0)
        self.assertAlmostEqual(last - first, 212 * 1.34, delta=1.0)
        long_first, long_last = lay.timeline_window((600, 1500), 7200)  # in the middle: room at both sides
        self.assertAlmostEqual(600 - long_first, long_last - 1500, delta=0.01)
        self.assertAlmostEqual(long_last - long_first, 900 * 1.34, delta=0.01)
        # the box test: a recap of 12 s and an intro of 28 s are shown on under a minute, not on three
        first, last = lay.timeline_window(lay.connected_span([(0, 12), (12, 40), (50, 62)], 1), 250)
        self.assertEqual(first, 0.0)
        self.assertLess(last, 60.0)
        self.assertEqual(lay.timeline_window((3, 5), 3072)[1] - lay.timeline_window((3, 5), 3072)[0], lay.MIN_SPAN)
        self.assertEqual(lay.timeline_window(None, 3072), (0.0, 3072.0))  # nothing highlighted: the whole file
        self.assertEqual(lay.timeline_window((10, 20), 15), (0.0, 15.0))  # a clip shorter than the least stretch
        self.assertEqual(lay.timeline_window((10, 20), 0), (0.0, 0.0))

    def test_small_labels_are_brought_to_the_mockup_s_size(self):
        self.assertAlmostEqual(lay.small_zoom(21), 15 / 21.0)  # Aeon Fuse: font10 is 21 pixels
        self.assertEqual(lay.small_zoom(15), 1.0)
        self.assertEqual(lay.small_zoom(12), 1.0)  # already small: left alone
        self.assertEqual(lay.small_zoom(None), 1.0)
        self.assertEqual(lay.small_zoom(60), 0.5)  # never below half
        ids = [cid for cid, _align in lay.SMALL_LABELS] + list(lay.MOVING_LABELS)
        self.assertEqual(len(ids), len(set(ids)))
        for res in ("720p", "1080i"):
            _root, found = controls(res, lay.XML_FILES[lay.LAYOUT_SIDE])
            for cid in ids:
                self.assertEqual(found[str(cid)].get("type"), "label", (res, cid))
                self.assertEqual(found[str(cid)].findtext("font"), lay.SMALL_FONT, (res, cid))

    def test_the_list_and_drawer_layout_has_a_look_of_its_own(self):
        import skippy_modal_style as style

        class Addon:
            def __init__(self, value):
                self.value = value

            def getSetting(self, key):
                return self.value if key == lay.STYLE_KEY else ""

        self.assertEqual(lay.style_for("side"), "fg_dark")  # Fused Glass Dark unless another is chosen
        self.assertEqual(lay.style_for("side", Addon("fg_frost")), "fg_frost")
        self.assertEqual(lay.style_for("side", Addon("aeon")), "fg_dark")  # only the three Fused Glass looks
        self.assertIsNone(lay.style_for("drawer", Addon("fg_frost")))
        self.assertEqual([lay.next_style(s) for s in ("fg_dark", "fg_frost", "fg_clear", "junk")],
                         ["fg_frost", "fg_clear", "fg_dark", "fg_frost"])
        for code in ("fgd", "fgc"):
            for res in ("720p", "1080i"):
                self.assertTrue(os.path.isfile(os.path.join(SKINS, res, "SegmentEditorDialogA_%s.xml" % code)))
        _root, found = controls("720p", lay.XML_FILES[lay.LAYOUT_SIDE])
        overlay, panels = (found[str(cid)] for cid in lay.LOOK_BUTTON_IDS)
        self.assertEqual((overlay.findtext("onright"), panels.findtext("onleft")), (str(lay.LOOK_BUTTON_IDS[1]), str(lay.LOOK_BUTTON_IDS[0])))
        self.assertEqual((overlay.findtext("onup"), overlay.findtext("ondown")), ("5000", "5037"))
        self.assertEqual(found["5000"].findtext("ondown"), str(lay.LOOK_BUTTON_IDS[0]))
        self.assertEqual(found["5037"].findtext("onup"), str(lay.LOOK_BUTTON_IDS[0]))
        self.assertIsNone(lay.style_for("drawer"))
        self.assertIsNone(lay.style_for("classic"))
        self.assertEqual(style.xml_name(lay.xml_base("side"), style=lay.style_for("side")), "SegmentEditorDialogA_fgd.xml")
        for res in ("720p", "1080i"):
            self.assertTrue(os.path.isfile(os.path.join(SKINS, res, "SegmentEditorDialogA_fgd.xml")))

    def test_a_row_has_room_for_the_flag_and_the_source(self):
        from tools import gen_segment_editor_layouts as gen_editor

        # the text of a row is smaller than the skin's fonts, as in the mockup
        self.assertEqual(sorted(gen_editor.ROW_ZOOM), ["flag", "length", "name", "range", "source"])
        self.assertTrue(all(60 <= zoom <= 95 for zoom in gen_editor.ROW_ZOOM.values()))
        with open(os.path.join(SKINS, "720p", lay.XML_FILES[lay.LAYOUT_SIDE]), encoding="utf-8") as handle:
            text = handle.read()
        rows = text[text.index('<control type="list" id="5000">'):text.index("</focusedlayout>")]
        # the source is drawn beside a flag as well as without one
        self.assertEqual(rows.count("ListItem.Property(source)"), 4)  # two per layout: plain and flagged
        self.assertEqual(rows.count('center="auto"'), 2 * 6)

    def test_sources_are_written_in_words(self):
        self.assertEqual(lay.source_name("edl"), "Local EDL")
        self.assertEqual(lay.source_name("Chapters"), "Chapters")
        self.assertEqual(lay.source_name("theintrodb"), "TheIntroDB")
        self.assertEqual(lay.source_name("my tool"), "my tool")
        self.assertEqual(lay.block_texture("Intro"), "segb_intro.png")

    def test_blocks_on_a_stretch_are_cut_at_its_ends_and_left_out_beyond_them(self):
        blocks = lay.window_blocks([(0, 46, "recap"), (46, 134, "intro"), (2860, 3072, "credits")], 0, 180, 720)
        self.assertEqual([(b.index, b.left, b.width) for b in blocks], [(0, 0, 184), (1, 184, 352)])
        cut = lay.window_blocks([(100, 400, "intro")], 200, 300, 500)
        self.assertEqual((cut[0].left, cut[0].width), (0, 500))
        self.assertEqual(lay.window_blocks([(0, 10, "intro")], 50, 50, 500), [])

    def test_a_block_has_a_word_only_when_it_fits_whole(self):
        self.assertEqual(lay.block_word("Intro", "1:28", 300), "INTRO · 1:28")
        self.assertEqual(lay.block_word("Intro", "1:28", 70), "INTRO")
        self.assertEqual(lay.block_word("Recap", "", 51), "")  # 51 units is too narrow for RECAP: seen on the box
        self.assertEqual(lay.block_word("Commercial", "", 60), "")  # no cut-off word
        self.assertEqual(lay.block_word("Recap", "", 300), "RECAP")

    def test_where_a_time_stands_on_the_stretch(self):
        self.assertEqual(lay.window_offset(92, 0, 180, 720), 368)
        self.assertEqual(lay.window_offset(200, 0, 180, 720), -1)
        self.assertEqual(lay.window_offset(5, 10, 20, 100), -1)


class LayoutATests(unittest.TestCase):
    def test_the_file_has_the_parts_of_the_mockup(self):
        for res in ("720p", "1080i"):
            _root, found = controls(res, lay.XML_FILES[lay.LAYOUT_SIDE])
            ids = (lay.TIME_START_ID, lay.TIME_END_ID, lay.TIME_NOW_ID, lay.OUTLINE_ID, lay.OVERVIEW_ID, lay.OVERVIEW_WINDOW_ID,
                   lay.TITLE_BOX_ID, lay.TIME_SEG_START_ID, lay.TIME_SEG_END_ID, lay.PLAYHEAD_HEAD_ID)
            ids += lay.BLOCK_LABEL_IDS + lay.OVERVIEW_BLOCK_IDS + lay.HANDLE_IDS
            for cid in ids:
                self.assertIn(str(cid), found, (res, cid))
            # from a segment: Left to its nine actions, Right to the seek and jump controls
            self.assertEqual((found["5000"].findtext("onleft"), found["5000"].findtext("onright")), ("5037", "5018"))
        with open(os.path.join(SKINS, "720p", lay.XML_FILES[lay.LAYOUT_SIDE]), encoding="utf-8") as handle:
            text = handle.read()
        for word in ("Start = now", "Start of file", "Type start + end", "ListItem.Property(range)", "ListItem.Property(source)",
                     "ed_selected", "ed_hint", "VideoPlayer.Title", "segb_other.png", "seg_tag.png"):
            self.assertIn(word, text, word)
        # white.png is a gradient: only the dark overlay behind the editor uses it; flags, tags and fills are flat
        self.assertEqual(text.count(">white.png<"), 1)
        _root, found = controls("720p", lay.XML_FILES[lay.LAYOUT_SIDE])
        self.assertEqual(int(found[str(lay.TRACK_ID)].findtext("width")), lay.TRACK_A_WIDTH)
        self.assertEqual(int(found[str(lay.TITLE_BOX_ID)].findtext("width")), lay.TITLE_BOX[2])


if __name__ == "__main__":
    unittest.main()
