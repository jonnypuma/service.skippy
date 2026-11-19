# -*- coding: utf-8 -*-
"""The Studio: the Customize screen of the skip dialog (geometry, generated file, rows and tabs)."""
import os
import re
import unittest
import xml.etree.ElementTree as ET

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import skip_dialog_customize_ui as base  # noqa: E402
import skip_dialog_presets as sp  # noqa: E402
import skip_layouts as sl  # noqa: E402
import skip_studio as st  # noqa: E402
import skip_studio_ui as ui  # noqa: E402
from tools import gen_skip_studio as gen  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SKINS = os.path.join(ROOT, "resources", "skins", "default")
MEDIA = os.path.join(SKINS, "media")


def read(res):
    with open(os.path.join(SKINS, res, st.XML), encoding="utf-8") as handle:
        return handle.read()


def inside(inner, outer):
    return (inner[0] >= outer[0] and inner[1] >= outer[1] and inner[0] + inner[2] <= outer[0] + outer[2]
            and inner[1] + inner[3] <= outer[1] + outer[3])


class GeometryTests(unittest.TestCase):
    def test_the_three_panels_are_on_the_screen_and_apart(self):
        for rect in (st.PANEL, st.STAGE, st.STRIP):
            self.assertTrue(inside(rect, (0, 0, st.CANVAS_W, st.CANVAS_H)), rect)
        self.assertLessEqual(st.PANEL[0] + st.PANEL[2], st.STAGE[0])
        self.assertLessEqual(st.STAGE[1] + st.STAGE[3], st.STRIP[1])
        self.assertEqual(st.STAGE[0], st.STRIP[0])
        self.assertEqual(st.PANEL[1] + st.PANEL[3], st.STRIP[1] + st.STRIP[3])

    def test_tabs_rows_and_buttons_stay_inside_the_panel(self):
        boxes = [st.tab_box(i) for i in range(len(st.TABS))] + [st.row_box(i) for i in range(st.ROWS)]
        boxes += list(st.foot_boxes())
        for rect in boxes:
            self.assertTrue(inside(rect, st.PANEL), rect)
        self.assertLessEqual(st.tab_box(0)[1] + st.TAB_H, st.row_box(0)[1])
        self.assertLessEqual(st.row_box(st.ROWS - 1)[1] + st.ROW_H, st.foot_boxes()[0][1])
        self.assertLessEqual(st.ROW_H, st.ROW_STEP)
        self.assertEqual(st.foot_boxes()[2][0] + st.foot_boxes()[2][2], st.ROW_LEFT + st.ROW_W)

    def test_a_switch_and_a_toggle_sit_inside_their_row(self):
        for row in (0, st.ROWS - 1):
            for option in range(st.SEG_OPTIONS):
                self.assertTrue(inside(st.seg_box(row, option), st.row_box(row)))
            self.assertTrue(inside(st.toggle_box(row), st.row_box(row)))
        first, second = st.seg_box(0, 0), st.seg_box(0, 1)
        self.assertEqual(first[0] + first[2] + st.SEG_GAP, second[0])
        # the name of the row keeps room at the left
        self.assertGreaterEqual(first[0] - st.row_box(0)[0], 150)

    def test_the_small_screen_fits_the_stage(self):
        left, top = st.screen_origin()
        rect = (left, top, st.CANVAS_W * st.SCREEN_ZOOM // 100, st.CANVAS_H * st.SCREEN_ZOOM // 100)
        self.assertTrue(inside(rect, st.STAGE), rect)

    def test_the_tiles_fit_the_strip(self):
        for index in range(st.TILES):
            self.assertTrue(inside(st.tile_box(index), st.STRIP))
        self.assertEqual(st.TILES % 2, 1)

    def test_window_of(self):
        self.assertEqual(st.window_of("abcdefg", 0), ["f", "g", "a", "b", "c"])
        self.assertEqual(st.window_of("abcdefg", 3), ["b", "c", "d", "e", "f"])
        self.assertEqual(st.window_of("ab", 0), [None, None, "a", "b", None])
        self.assertEqual(st.window_of("ab", 1), [None, "a", "b", None, None])
        self.assertEqual(st.window_of([], 0), [None] * st.TILES)


class GeneratedFileTests(unittest.TestCase):
    def test_the_files_are_what_the_generator_writes(self):
        self.assertEqual(gen.stale(), [], "run python tools/gen_skip_layouts.py, then tools/gen_skip_studio.py")

    def test_ids(self):
        for res in ("720p", "1080i"):
            root = ET.fromstring(read(res).split("?>", 1)[1])
            ids = [c.get("id") for c in root.iter("control") if c.get("id")]
            self.assertEqual(len(ids), len(set(ids)), res)
            wanted = [st.tab_id(i) for i in range(len(st.TABS))] + [st.row_id(i) for i in range(st.ROWS)]
            wanted += [st.ID_SAVE, st.ID_SAVE_PRESET, st.ID_RESET, st.ID_SCREEN, st.ID_FANART, 3080, 3081, 5090]
            for cid in wanted:
                self.assertIn(str(cid), ids, (res, cid))
            for index in range(len(sl.all_layouts())):
                self.assertIn(str(sl.ID_ROOT + sl.mock_offset(index)), ids, (res, index))
            self.assertEqual(root.find("defaultcontrol").text, str(st.row_id(0)))

    def test_it_is_always_fused_glass_dark_with_shadows(self):
        text = read("720p")
        self.assertEqual(text.count("ms_fgd_panel.png"), 3)
        self.assertEqual(text.count("st_shadow.png"), 3)
        self.assertNotIn("ms_fgf_", text)
        for name in gen.pictures():
            self.assertTrue(os.path.isfile(os.path.join(MEDIA, name)), name)

    def test_the_only_buttons_are_tabs_rows_and_the_three_at_the_bottom(self):
        root = ET.fromstring(read("720p").split("?>", 1)[1])
        buttons = sorted(int(c.get("id")) for c in root.iter("control") if c.get("type") == "button")
        expected = [st.tab_id(i) for i in range(len(st.TABS))] + [st.row_id(i) for i in range(st.ROWS)]
        self.assertEqual(buttons, sorted(expected + [st.ID_SAVE, st.ID_SAVE_PRESET, st.ID_RESET]))

    def test_every_property_read_is_set_by_the_screen(self):
        used = set(re.findall(r"Window\.Property\((st_[A-Za-z0-9_]+)\)", read("720p")))
        known = {"st_tab", "st_well", "st_chip", "st_hint", "st_strip", "st_kicker", "st_tag", "st_mode",
                 "st_about", "st_more"}
        known |= {"st_tab%d" % i for i in range(len(st.TABS))}
        known |= {"st_tag%d" % i for i in range(st.PREVIEWS)}
        for row in range(st.ROWS):
            known |= {"st_r%d_%s" % (row, part) for part in ("n", "on", "tog", "name", "kind", "val", "con", "pos", "dim")}
            known |= {"st_r%d_s%d" % (row, o) for o in range(st.SEG_OPTIONS)}
            known |= {"st_r%d_%s%d" % (row, part, i) for part in ("t", "c") for i in range(st.SWATCHES)}
        # every one of them is written by the screen
        with open(os.path.join(ROOT, "skip_studio_ui.py"), encoding="utf-8") as handle:
            source = handle.read()
        for name in ("st_kicker", "st_tag", "st_mode", "st_about", "st_strip", "st_hint", "st_tab"):
            self.assertIn('"%s"' % name, source, name)
        for tile in range(st.TILES):
            known |= {"st_t%d_%s" % (tile, part) for part in ("name", "thumb", "plate", "tint", "pill", "bar", "bartint")}
        self.assertEqual(used - known, set())

    def test_the_strings_are_in_every_language(self):
        lang_root = os.path.join(ROOT, "resources", "language")
        for folder in sorted(os.listdir(lang_root)):
            with open(os.path.join(lang_root, folder, "strings.po"), encoding="utf-8") as handle:
                text = handle.read()
            for sid in list(st.TAB_LABEL_IDS) + [49025, 49026, 49027, 49028, 49029, 49030]:
                self.assertIn('msgctxt "#%d"' % sid, text, (folder, sid))


class RowTests(unittest.TestCase):
    def test_every_classic_row_has_a_tab(self):
        placed = [cid for ids in ui.TAB_ROWS for cid in ids]
        self.assertEqual(len(placed), len(set(placed)))
        self.assertEqual(len(ui.TAB_ROWS), len(st.TABS))
        for draft in ({"skip_dialog_mode": "Full"}, {"skip_dialog_mode": "CompactFull"}, {"skip_dialog_mode": "Minimal"},
                      {"skip_dialog_mode": "Full", "compact_full_combined": True},
                      {"skip_dialog_mode": "Full", sl.KEY_LAYOUT: "Dial"}):
            shown = set(base.customize_nav_ids(draft)) | set(base.customize_picker_ids(draft))
            shown -= {base.ID_SAVE, base.ID_CANCEL}
            self.assertEqual(shown - set(placed), set(), draft)
            for rows in ui.tab_rows_all(draft):
                self.assertEqual(len(rows), len(set(rows)), draft)  # a long tab scrolls; no row twice

    def test_a_tab_shows_only_what_the_classic_screen_would(self):
        full = ui.tab_rows({"skip_dialog_mode": "Full"})
        self.assertEqual(full[0][:3], [base.ID_PRESET, base.ID_LAYOUT, base.ID_MODE])  # Design is the second row of Look
        dial = ui.tab_rows({"skip_dialog_mode": "Full", sl.KEY_LAYOUT: "Poster"})
        self.assertEqual(dial[0], [base.ID_PRESET, base.ID_LAYOUT, base.ID_MODE, base.ID_PREVIEW_TYPE, base.ID_LOOK,
                                   base.ID_OVERLAY, base.ID_BAR_COLOR])
        self.assertEqual(dial[4], [base.ID_APPEAR, base.ID_LEAVE, base.ID_PULSE])  # Motion
        drawn = ui.tab_rows({"skip_dialog_mode": "Full", sl.KEY_LAYOUT: "Stack"})
        self.assertEqual(drawn[4], [base.ID_APPEAR, base.ID_LEAVE, base.ID_PULSE])  # a drawn design moves too
        self.assertIn(base.ID_CV_PROGRESS, drawn[0])
        self.assertNotIn(base.ID_CV_GRADIENT_TYPE, drawn[0])  # only with the gradient switched on
        self.assertIn(base.ID_CV_GRADIENT_TYPE,
                      ui.tab_rows({"skip_dialog_mode": "Full", sl.KEY_LAYOUT: "Stack", "skip_canvas_overlay_gradient": True})[0])
        self.assertNotIn(base.ID_BAR_COLOR, full[0])
        self.assertEqual(dial[3], [])
        minimal = ui.tab_rows({"skip_dialog_mode": "Minimal"})
        self.assertIn(base.ID_LAYOUT, minimal[0])  # every layout has a Minimal form
        self.assertIn(base.ID_PLATE, minimal[0])
        rail = ui.tab_rows({"skip_dialog_mode": "Minimal", sl.KEY_LAYOUT: "Rail"})
        self.assertIn(base.ID_LOOK, rail[0])
        self.assertNotIn(base.ID_PLATE, rail[0])

    def test_no_row_is_left_out_a_row_that_does_not_apply_is_dimmed(self):
        card = ui.tab_rows_all({"skip_dialog_mode": "CompactFull"})
        # the Look tab of the classic card shows every row of the tab, the drawn designs' ones dimmed
        self.assertEqual([cid for cid, _why in card[0]], list(ui.TAB_ROWS[0]))
        why = dict(card[0])
        self.assertEqual(why[base.ID_PRESET], "")
        self.assertEqual(why[base.ID_LAYOUT], "")
        self.assertEqual(why[base.ID_CORNERS], "drawn")
        self.assertEqual(why[base.ID_CV_ACCENT], "drawn")
        drawn = ui.tab_rows_all({"skip_dialog_mode": "Full", sl.KEY_LAYOUT: "Stack"})
        self.assertEqual(dict(drawn[0])[base.ID_CORNERS], "")
        self.assertEqual(dict(drawn[0])[base.ID_CARD], "card")
        self.assertEqual([why for _cid, why in drawn[4]], [""] * 3)  # Motion applies to a drawn design
        self.assertEqual([why for _cid, why in card[4]], ["drawn"] * 3)  # and not to the classic card
        for reason in set(w for rows in card + drawn for _c, w in rows) - {""}:
            self.assertIn(reason, ui.WHY)

    def test_a_long_tab_scrolls(self):
        self.assertEqual(ui.scroll_for(0, 0, 14, 10), 0)
        self.assertEqual(ui.scroll_for(10, 0, 14, 10), 1)
        self.assertEqual(ui.scroll_for(13, 0, 14, 10), 4)
        self.assertEqual(ui.scroll_for(2, 4, 14, 10), 2)
        self.assertEqual(ui.scroll_for(5, 3, 8, 10), 0)  # a short tab does not scroll

    def test_tabs_without_rows_are_passed_over(self):
        rows = [[1], [], [], [2], []]
        self.assertEqual(ui.first_tab_with_rows(rows, 0), 0)
        self.assertEqual(ui.first_tab_with_rows(rows, 1), 0)
        self.assertEqual(ui.next_tab(rows, 0, 1), 3)
        self.assertEqual(ui.next_tab(rows, 3, 1), 0)
        self.assertEqual(ui.next_tab(rows, 0, -1), 3)
        self.assertEqual(ui.next_tab([[1], [], [], [], []], 0, 1), 0)

    def test_toggle_rows_are_rows_of_the_classic_screen(self):
        placed = {cid for ids in ui.TAB_ROWS for cid in ids}
        self.assertLessEqual(ui.TOGGLE_ROWS, placed)

    def test_the_three_sizes_fit_a_switch_row(self):
        choices = ui.mode_choices(None)
        self.assertEqual([stored for stored, _name in choices], list(base.MODES))
        self.assertLessEqual(len(choices), st.SEG_OPTIONS)


class TileTests(unittest.TestCase):
    def test_a_preset_tile_shows_its_card_focus_and_bar(self):
        values = dict(sp.builtin_presets())["Fused Glass Frost"]
        tile = ui.preset_tile(values)
        self.assertEqual(tile["plate"], "skip_card_fgf.png")
        self.assertEqual(tile["tint"], "FFFFFFFF")
        self.assertEqual(tile["pill"], values["button_focus_style"])
        self.assertEqual(tile["bar"], values["progress_bar_style"])

    def test_no_card_and_minimal_tiles(self):
        bare = ui.preset_tile(dict(sp.builtin_presets())["Aeon Bare"])
        self.assertEqual(bare["plate"], "")
        compact = ui.preset_tile(dict(sp.builtin_presets())["Aeon Compact"])
        self.assertEqual(compact["plate"], "")
        chip = ui.preset_tile(dict(sp.builtin_presets())["Aeon Minimal"])
        self.assertEqual((chip["plate"], chip["bar"]), ("", ""))
        self.assertEqual(chip["pill"], "minimal_fuse_square_640.png")

    def test_every_tile_picture_exists(self):
        for _name, values in sp.builtin_presets():
            tile = ui.preset_tile(values)
            for part in ("plate", "pill", "bar"):
                if tile[part]:
                    self.assertTrue(os.path.isfile(os.path.join(MEDIA, tile[part])), tile[part])
        for code in sl.LOOKS:
            tile = ui.look_tile(code, "1080i")
            for part in ("plate", "pill", "bar"):
                self.assertTrue(os.path.isfile(os.path.join(MEDIA, tile[part])), tile[part])

    def test_customize_opens_the_studio_and_keeps_the_classic_screen(self):
        self.assertTrue(callable(base.show_skip_dialog_customize_classic))
        self.assertTrue(issubclass(ui.SkipStudio, base.SkipDialogCustomize))


if __name__ == "__main__":
    unittest.main()
