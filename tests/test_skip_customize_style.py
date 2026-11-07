# -*- coding: utf-8 -*-
"""The skip dialog's Customize screen looks like the next episode one (same colours, rows, buttons)."""

import os
import unittest
import xml.etree.ElementTree as ET

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import next_episode_customize_ui as ne_ui
import skip_dialog_customize_ui as ui
import skip_dialog_presets_ui as presets_ui
from addon_skin_resolution import SKIN_RES_1080I, SKIN_RES_720P, scale_skin_coord

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SKINS = os.path.join(ROOT, "resources", "skins", "default")
FACTORS = (("720p", SKIN_RES_720P, 1), ("1080i", SKIN_RES_1080I, 1.5))

FULL_DRAFT = {
    "skip_dialog_mode": "Full",
    "skip_button_format": "Skip + Type + Duration",
    "hide_close_button": False,
    "show_progress_bar": True,
    "skip_overlapping_segments": True,
    "skip_dialog_font_color": "FFFFFFFF",
    "progress_bar_style": "progress_mid.png",
    "skip_dialog_position": "BottomRight",
    "button_focus_style": "button_focus.png",
}


def drafts():
    out = []
    for mode in ("Full", "CompactFull", "Minimal"):
        for fmt in ("Skip", "Skip + Type + Duration"):
            for hide_close in (False, True):
                for combined in (False, True):
                    out.append(
                        {
                            "skip_dialog_mode": mode,
                            "skip_button_format": fmt,
                            "minimal_skip_button_format": fmt,
                            "hide_close_button": hide_close,
                            "compact_full_combined": combined,
                            "show_progress_bar": True,
                        }
                    )
    return out


def load(name, res):
    root = ET.parse(os.path.join(SKINS, res, name)).getroot()
    return root, {c.get("id"): c for c in root.iter("control") if c.get("id")}


def style(ctrl):
    """Everything that makes a button look the way it does (not where it is or what it says)."""

    def texture(tag):
        el = ctrl.find(tag)
        return None if el is None else (el.text, el.get("border"), el.get("colordiffuse"))

    return {
        "font": ctrl.findtext("font"),
        "focus": texture("texturefocus"),
        "nofocus": texture("texturenofocus"),
        "textcolor": ctrl.findtext("textcolor"),
        "focusedcolor": ctrl.findtext("focusedcolor"),
        "shadow": (
            ctrl.findtext("shadowcolor"),
            ctrl.findtext("shadowoffsetx"),
            ctrl.findtext("shadowoffsety"),
        ),
        "align": ctrl.findtext("align"),
        "aligny": ctrl.findtext("aligny"),
        "textoffsetx": ctrl.findtext("textoffsetx"),
    }


def skip_pane(res):
    root, found = load("SkipDialogCustomize.xml", res)
    pane = found["4080"]
    buttons = [c for c in pane.iter("control") if c.get("type") == "button"]
    rows = [c for c in buttons if c.get("id") not in (str(ui.ID_SAVE), str(ui.ID_CANCEL))]
    footers = [c for c in buttons if c.get("id") in (str(ui.ID_SAVE), str(ui.ID_CANCEL))]
    return root, found, rows, footers


class _Rec:
    """Stands in for a Kodi control and remembers what was done to it."""

    def __init__(self):
        self.x = self.y = self.w = self.h = None
        self.label = self.label2 = None
        self.visible = None

    def setPosition(self, x, y):
        self.x, self.y = x, y

    def setWidth(self, w):
        self.w = w

    def setHeight(self, h):
        self.h = h

    def setVisible(self, flag):
        self.visible = bool(flag)

    def setLabel(self, label="", *args, label2="", **kwargs):
        self.label, self.label2 = label, label2


def window(draft):
    win = ui.SkipDialogCustomize.__new__(ui.SkipDialogCustomize)
    recs = {}
    win._ctrl = lambda cid: recs.setdefault(cid, _Rec())
    win._sc = lambda value: value
    win._draft = dict(draft)
    win.addon = None
    win._preview_type = "commercial"
    return win, recs


class SkinStyleTests(unittest.TestCase):
    def test_every_row_has_the_next_episode_row_style(self):
        for res, _resolution, _factor in FACTORS:
            _root, ne = load("NextEpisodeCustomize.xml", res)
            expected = style(ne[str(ne_ui.ROW_IDS[ne_ui.KEY_STYLE])])
            self.assertEqual(expected["focus"][0], "button_focus_flat_teal.png")
            _root, _found, rows, _footers = skip_pane(res)
            self.assertEqual(len(rows), 25)
            for ctrl in rows:
                self.assertEqual(style(ctrl), expected, (res, ctrl.get("id")))

    def test_save_and_cancel_have_the_next_episode_button_style(self):
        for res, _resolution, _factor in FACTORS:
            _root, ne = load("NextEpisodeCustomize.xml", res)
            expected = style(ne[str(ne_ui.ID_SAVE)])
            self.assertEqual(expected["align"], "center")
            _root, _found, _rows, footers = skip_pane(res)
            self.assertEqual(len(footers), 2)
            for ctrl in footers:
                self.assertEqual(style(ctrl), expected, (res, ctrl.get("id")))

    def test_panel_dimming_and_heading_colours_are_the_next_episode_ones(self):
        for res, _resolution, _factor in FACTORS:
            ne_root, ne = load("NextEpisodeCustomize.xml", res)
            skip_root, skip, _rows, _footers = skip_pane(res)
            self.assertEqual(
                skip["4081"].findtext("colordiffuse"), ne[str(ne_ui.ID_BACKDROP)].findtext("colordiffuse")
            )
            dim = lambda root: root.find("controls").find("control[@type='image']").findtext("colordiffuse")
            self.assertEqual(dim(skip_root), dim(ne_root))
            title = ne[str(ne_ui.ID_TITLE)]
            for cid in (ui.ID_TITLE, ui.ID_FULL_HEADER, ui.ID_MIN_HEADER):
                label = skip[str(cid)]
                self.assertEqual(label.findtext("textcolor"), title.findtext("textcolor"), (res, cid))
                self.assertEqual(label.findtext("font"), title.findtext("font"), (res, cid))

    def test_the_panel_backdrop_can_be_found_by_python(self):
        for res, _resolution, _factor in FACTORS:
            _root, skip, _rows, _footers = skip_pane(res)
            self.assertEqual(skip[str(ui.ID_PANEL_BG)].get("type"), "image", res)

    def test_a_row_in_the_skin_is_as_high_as_the_layout_draws_it(self):
        for res, resolution, _factor in FACTORS:
            sc = lambda value, resolution=resolution: scale_skin_coord(value, resolution)
            plain = ui.customize_left_pane_layout(
                ui.customize_nav_ids({"skip_dialog_mode": "Minimal"}), sc
            )
            _root, _found, rows, _footers = skip_pane(res)
            heights = {int(ctrl.findtext("height")) for ctrl in rows if ctrl.findtext("width") == str(sc(468))}
            self.assertEqual(heights, {plain["button_h"]}, res)

    def test_the_buttons_in_the_skin_match_the_layout(self):
        for res, resolution, _factor in FACTORS:
            sc = lambda value, resolution=resolution: scale_skin_coord(value, resolution)
            m = ui.customize_left_pane_layout(ui.customize_nav_ids(FULL_DRAFT), sc)
            _root, _found, _rows, footers = skip_pane(res)
            save, cancel = sorted(footers, key=lambda c: int(c.findtext("left")))
            # the generator rounds 1.5 x 229 up where the layout divides the row width: 1 px apart at most
            for ctrl, left in ((save, m["left"]), (cancel, m["cancel_x"])):
                self.assertLessEqual(abs(int(ctrl.findtext("left")) - left), 1, (res, ctrl.get("id")))
                self.assertLessEqual(abs(int(ctrl.findtext("width")) - m["save_w"]), 1, (res, ctrl.get("id")))
                self.assertEqual(int(ctrl.findtext("height")), m["save_h"], (res, ctrl.get("id")))


class LayoutTests(unittest.TestCase):
    def layouts(self):
        for _res, resolution, _factor in FACTORS:
            sc = lambda value, resolution=resolution: scale_skin_coord(value, resolution)
            for draft in drafts():
                yield sc, draft, ui.customize_left_pane_layout(ui.customize_nav_ids(draft), sc)

    def test_the_panel_never_gets_taller_than_the_screen_allows(self):
        for sc, draft, m in self.layouts():
            self.assertLessEqual(m["panel_h"], sc(688), draft)

    def test_the_buttons_sit_right_below_the_rows(self):
        for sc, draft, m in self.layouts():
            self.assertEqual(m["save_y"], m["content_bottom"] + m["gap"], draft)
            self.assertEqual(m["panel_h"] - (m["save_y"] + m["save_h"]), sc(16), draft)

    def test_the_panel_follows_the_rows(self):
        sc = lambda value: value
        few = ui.customize_left_pane_layout(ui.customize_nav_ids({"skip_dialog_mode": "Minimal"}), sc)
        many = ui.customize_left_pane_layout(ui.customize_nav_ids(FULL_DRAFT), sc)
        self.assertLess(few["panel_h"], many["panel_h"])
        self.assertEqual(few["panel_h"], few["content_bottom"] + few["gap"] + few["save_h"] + 16)

    def test_rows_are_drawn_shorter_than_their_step_and_still_hold_the_focus_frame(self):
        for sc, draft, m in self.layouts():
            self.assertEqual(m["button_h"], m["row_h"] - m["row_gap"], draft)
            self.assertGreaterEqual(m["row_gap"], sc(2), draft)
            # the focus texture has 12 px corners: a row must be at least 2 x 12 high
            self.assertGreaterEqual(m["button_h"], sc(24), draft)

    def test_the_gap_between_rows_is_the_next_episode_four_pixels_while_there_is_room(self):
        sc = lambda value: value
        roomy = ui.customize_left_pane_layout(ui.customize_nav_ids({"skip_dialog_mode": "Minimal"}), sc)
        self.assertEqual((roomy["row_h"], roomy["row_gap"], roomy["button_h"]), (34, 4, 30))
        # 14 px from the last row to the buttons, as in the next episode modal
        self.assertEqual(roomy["save_y"] - (roomy["content_bottom"] - roomy["row_gap"]), 14)
        tight = ui.customize_left_pane_layout(
            ui.customize_nav_ids(dict(FULL_DRAFT, hide_close_button=True)), sc
        )
        self.assertEqual((tight["row_h"], tight["row_gap"]), (26, 2))

    def test_rows_never_get_lower_than_the_minimum_whatever_their_number(self):
        for sc in (lambda value: value, lambda value: scale_skin_coord(value, SKIN_RES_1080I)):
            m = ui.customize_left_pane_layout(list(range(5000, 5040)), sc)
            self.assertEqual(m["row_h"], sc(26))
            self.assertGreaterEqual(m["button_h"], sc(24))

    def test_save_and_cancel_share_the_width_of_the_rows(self):
        for sc, draft, m in self.layouts():
            self.assertEqual(m["cancel_x"] + m["save_w"], m["left"] + sc(468), draft)
            self.assertEqual(m["save_h"], sc(40), draft)
            between = m["cancel_x"] - (m["left"] + m["save_w"])
            self.assertLessEqual(abs(between - sc(10)), 1, draft)


class WindowTests(unittest.TestCase):
    def test_every_row_shows_its_name_and_its_value_apart(self):
        win, recs = window(FULL_DRAFT)
        win._refresh_row_labels()
        ids = [cid for cid in ui.customize_nav_ids(FULL_DRAFT) if cid not in (ui.ID_SAVE, ui.ID_CANCEL)]
        for cid in ids + [ui.ID_PREVIEW_TYPE]:
            rec = recs[cid]
            self.assertTrue(rec.label, cid)
            self.assertNotEqual(rec.label2, "", cid)
            self.assertNotIn(": ", rec.label, cid)

    def test_some_rows_exactly(self):
        win, recs = window(FULL_DRAFT)
        win._draft["skip_card_opacity"] = 95
        win._draft["skip_card_enabled"] = True
        win._refresh_row_labels()
        self.assertEqual((recs[ui.ID_CARD].label, recs[ui.ID_CARD].label2), ("Show card background", "Yes"))
        self.assertEqual((recs[ui.ID_OPACITY].label, recs[ui.ID_OPACITY].label2), ("Card opacity (%)", "95"))
        self.assertEqual((recs[ui.ID_PRESET].label, recs[ui.ID_PRESET].label2), ("Preset", "Custom"))
        self.assertEqual(
            (recs[ui.ID_PREVIEW_TYPE].label, recs[ui.ID_PREVIEW_TYPE].label2[:1]), ("Preview type", "C")
        )
        self.assertEqual(
            (recs[ui.ID_SKIP_FORMAT].label, recs[ui.ID_SKIP_FORMAT].label2),
            ("Skip button format", "Skip + Type + Duration"),
        )

    def test_a_value_that_is_a_number_is_shown_as_text(self):
        win, recs = window(FULL_DRAFT)
        win._draft["progress_bar_height"] = 16
        win._refresh_row_labels()
        self.assertEqual(recs[ui.ID_HEIGHT].label2, "16")

    def test_a_row_that_cannot_be_labelled_does_not_stop_the_others(self):
        win, recs = window(FULL_DRAFT)

        def broken(cid):
            rec = recs.setdefault(cid, _Rec())
            if cid == ui.ID_CARD:
                rec.setLabel = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no"))
            return rec

        win._ctrl = broken
        win._refresh_row_labels()
        self.assertEqual(recs[ui.ID_OPACITY].label, "Card opacity (%)")

    def test_the_preset_row_parts_match_its_one_line_label(self):
        name, value = presets_ui.preset_row_parts(None, FULL_DRAFT)
        self.assertEqual((name, value), ("Preset", "Custom"))
        self.assertEqual(presets_ui.preset_row_label(None, FULL_DRAFT), "Preset: Custom")

    def test_the_layout_sizes_rows_buttons_and_panel(self):
        win, recs = window(FULL_DRAFT)
        win.setProperty = lambda *a, **k: None
        win._layout_left_pane()
        m = ui.customize_left_pane_layout(ui.customize_nav_ids(FULL_DRAFT), lambda v: v)
        for cid in m["ids"]:
            self.assertEqual(recs[cid].h, m["button_h"], cid)
            self.assertTrue(recs[cid].visible, cid)
        tops = [recs[cid].y for cid in m["ids"] if cid in recs]
        self.assertEqual(tops, sorted(tops))
        # a row starts one step after the one above it (a header makes it a little more)
        steps = {b - a for a, b in zip(tops, tops[1:])}
        self.assertEqual(steps, {m["row_h"], m["row_h"] + m["header_h"]})
        self.assertEqual((recs[ui.ID_SAVE].x, recs[ui.ID_SAVE].y), (m["left"], m["save_y"]))
        self.assertEqual((recs[ui.ID_CANCEL].x, recs[ui.ID_CANCEL].y), (m["cancel_x"], m["save_y"]))
        for cid in (ui.ID_SAVE, ui.ID_CANCEL):
            self.assertEqual((recs[cid].w, recs[cid].h), (m["save_w"], m["save_h"]))
        self.assertEqual(recs[ui.ID_PANEL_BG].h, m["panel_h"])

    def test_rows_that_do_not_apply_are_hidden(self):
        win, recs = window({"skip_dialog_mode": "Minimal"})
        win.setProperty = lambda *a, **k: None
        win._layout_left_pane()
        self.assertFalse(recs[ui.ID_PROGRESS].visible)
        self.assertTrue(recs[ui.ID_PLATE].visible)


if __name__ == "__main__":
    unittest.main()
