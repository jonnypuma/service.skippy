# -*- coding: utf-8 -*-
"""The Skippy panel: the list / message window with the look of the Customize screens."""

import os
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import next_episode_customize_ui as ne_ui
import skippy_panel_ui as panel
from addon_skin_resolution import (
    SKIN_RES_1080I,
    SKIN_RES_720P,
    infer_skin_resolution_from_widths,
    probe_control_ids_for_xml,
)
from skippy_panel_ui import PanelRow

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SKINS = os.path.join(ROOT, "resources", "skins", "default")
FACTORS = (("720p", SKIN_RES_720P, 1), ("1080i", SKIN_RES_1080I, 1.5))


def load(name, res):
    root = ET.parse(os.path.join(SKINS, res, name)).getroot()
    return root, {c.get("id"): c for c in root.iter("control") if c.get("id")}


def button_style(ctrl):
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
    }


class SkinTests(unittest.TestCase):
    def test_every_control_the_code_uses_exists_in_both_resolutions(self):
        wanted = {
            str(n)
            for n in (
                panel.ID_PANEL,
                panel.ID_BACKDROP,
                panel.ID_TITLE,
                panel.ID_SUBTITLE,
                panel.ID_MESSAGE,
                panel.ID_FOOTNOTE,
                panel.ID_LIST,
                panel.ID_SCROLL,
            )
            + panel.FOOTER_IDS
        }
        for res, _resolution, _factor in FACTORS:
            _root, found = load(panel.XML_NAME, res)
            self.assertLessEqual(wanted, set(found), res)

    def test_panel_and_rows_have_the_look_of_the_next_episode_customize_screen(self):
        _root, ne = load("NextEpisodeCustomize.xml", "720p")
        _root, sp = load(panel.XML_NAME, "720p")
        self.assertEqual(
            sp[str(panel.ID_BACKDROP)].findtext("colordiffuse"),
            ne["6001"].findtext("colordiffuse"),
        )
        self.assertEqual(sp[str(panel.ID_TITLE)].findtext("textcolor"), ne["6002"].findtext("textcolor"))
        self.assertEqual(sp[str(panel.ID_TITLE)].findtext("font"), ne["6002"].findtext("font"))
        self.assertEqual(sp[str(panel.ID_BACKDROP)].findtext("width"), ne["6001"].findtext("width"))
        row = button_style(ne["6011"])
        focused = sp[str(panel.ID_LIST)].find("focusedlayout")
        images = {img.findtext("texture"): img.find("texture") for img in focused.findall("control")
                  if img.get("type") == "image"}
        self.assertEqual(images["button_focus_flat_teal.png"].get("border"), row["focus"][1])
        self.assertEqual(images["white.png"].get("colordiffuse"), row["nofocus"][2])
        label = [c for c in focused.findall("control") if c.get("type") == "label"][0]
        self.assertEqual(label.findtext("font"), row["font"])
        self.assertEqual(label.findtext("textcolor"), row["textcolor"])
        self.assertEqual(label.findtext("shadowcolor"), row["shadow"][0])

    def test_footer_buttons_are_the_customize_buttons(self):
        for res, _resolution, _factor in FACTORS:
            _root, ne = load("NextEpisodeCustomize.xml", res)
            expected = button_style(ne["6021"])
            _root, sp = load(panel.XML_NAME, res)
            for cid in panel.FOOTER_IDS:
                self.assertEqual(button_style(sp[str(cid)]), expected, (res, cid))

    def test_1080i_is_the_720p_layout_times_one_and_a_half(self):
        _root, low = load(panel.XML_NAME, "720p")
        _root, high = load(panel.XML_NAME, "1080i")
        for cid in (panel.ID_BACKDROP, panel.ID_LIST, panel.ID_SCROLL, panel.FOOTER_IDS[0]):
            for tag in ("width", "height"):
                a = int(low[str(cid)].findtext(tag))
                b = int(high[str(cid)].findtext(tag))
                self.assertLessEqual(abs(b - a * 1.5), 1, (cid, tag))

    def test_the_resolution_is_recognised_from_the_backdrop(self):
        self.assertEqual(probe_control_ids_for_xml("SkippyPanel.xml"), (panel.ID_BACKDROP,))
        _root, low = load(panel.XML_NAME, "720p")
        _root, high = load(panel.XML_NAME, "1080i")
        self.assertEqual(
            infer_skin_resolution_from_widths([int(low[str(panel.ID_BACKDROP)].findtext("width"))]),
            SKIN_RES_720P,
        )
        self.assertEqual(
            infer_skin_resolution_from_widths([int(high[str(panel.ID_BACKDROP)].findtext("width"))]),
            SKIN_RES_1080I,
        )

    def test_the_layout_numbers_match_the_skin(self):
        _root, sp = load(panel.XML_NAME, "720p")
        self.assertEqual(int(sp[str(panel.ID_BACKDROP)].findtext("width")), panel.PANEL_W)
        self.assertEqual(int(sp[str(panel.ID_LIST)].findtext("width")), panel.INNER_W)
        self.assertEqual(
            int(sp[str(panel.ID_LIST)].find("itemlayout").get("height")), panel.ROW_STEP
        )
        self.assertEqual(int(sp[str(panel.FOOTER_IDS[0])].findtext("height")), panel.FOOTER_H)
        self.assertEqual(panel.PANEL_X * 2 + panel.PANEL_W, 1280)

    def test_the_panel_is_centred_and_matches_the_customize_row_numbers(self):
        self.assertEqual(
            (panel.ROW_TOP, panel.ROW_H, panel.ROW_STEP, panel.FOOTER_H, panel.INNER_W),
            (ne_ui._ROW_TOP, ne_ui._ROW_H, ne_ui._ROW_STEP, ne_ui._FOOTER_H, 520),
        )

    def test_headings_have_no_highlight(self):
        _root, sp = load(panel.XML_NAME, "720p")
        focused = sp[str(panel.ID_LIST)].find("focusedlayout")
        for img in focused.findall("control"):
            if img.get("type") == "image":
                self.assertIn("!String.IsEqual(ListItem.Property(header),true)", img.findtext("visible"))


class LayoutTests(unittest.TestCase):
    def test_a_short_list_is_as_high_as_its_rows(self):
        lay = panel.panel_layout(5, False, 0, False, 1)
        self.assertEqual(lay["list_top"], 60)
        self.assertEqual(lay["body_h"], 5 * 44)
        self.assertEqual(lay["footer_top"], 60 + 5 * 44 + 10)
        self.assertEqual(lay["panel_h"], lay["footer_top"] + 40 + 20)
        self.assertFalse(lay["scrolls"])
        self.assertEqual(lay["panel_y"], (720 - lay["panel_h"]) // 2)

    def test_a_subtitle_and_a_footnote_make_room(self):
        plain = panel.panel_layout(5, False, 0, False, 1)
        both = panel.panel_layout(5, True, 0, True, 1)
        self.assertEqual(both["list_top"], plain["list_top"] + panel.SUBTITLE_EXTRA)
        self.assertEqual(
            both["panel_h"],
            plain["panel_h"] + panel.SUBTITLE_EXTRA + panel.FOOTNOTE_H + panel.FOOTNOTE_GAP,
        )
        self.assertEqual(both["footnote_top"], both["list_top"] + both["body_h"])
        self.assertGreater(both["footer_top"], both["footnote_top"] + panel.FOOTNOTE_H)

    def test_a_long_list_scrolls_and_the_panel_fits_the_screen(self):
        for rows in (11, 12, 40, 500):
            for subtitle in (False, True):
                for footnote in (False, True):
                    lay = panel.panel_layout(rows, subtitle, 0, footnote, 2)
                    self.assertLessEqual(lay["panel_h"], panel.MAX_PANEL_H, (rows, subtitle, footnote))
                    self.assertGreaterEqual(lay["panel_y"], panel.SCREEN_MARGIN)
                    self.assertLessEqual(lay["panel_y"] + lay["panel_h"], 720 - panel.SCREEN_MARGIN)
                    self.assertGreaterEqual(lay["visible_rows"], panel.MIN_ROWS)
        lay = panel.panel_layout(40, False, 0, False, 1)
        self.assertTrue(lay["scrolls"])
        self.assertEqual(lay["body_h"], lay["visible_rows"] * 44)

    def test_at_least_three_rows_are_shown_however_little_room_there_is(self):
        with patch.object(panel, "MAX_PANEL_H", 250):
            lay = panel.panel_layout(40, False, 0, False, 1)
        self.assertEqual(lay["visible_rows"], panel.MIN_ROWS)
        self.assertTrue(lay["scrolls"])
        with patch.object(panel, "MAX_PANEL_H", 250):
            self.assertEqual(panel.panel_layout(2, False, 0, False, 1)["visible_rows"], 2)

    def test_a_message_grows_with_its_lines_up_to_the_screen(self):
        short = panel.panel_layout(0, False, 1, False, 2)
        three = panel.panel_layout(0, False, 3, False, 2)
        self.assertGreater(three["body_h"], short["body_h"])
        huge = panel.panel_layout(0, False, 500, False, 2)
        self.assertLessEqual(huge["panel_h"], panel.MAX_PANEL_H)

    def test_message_lines_count_wrapped_and_empty_lines(self):
        self.assertEqual(panel.message_line_count("one"), 1)
        self.assertEqual(panel.message_line_count("one\n\ntwo"), 3)
        self.assertEqual(panel.message_line_count("x" * 53), 2)
        self.assertEqual(panel.message_line_count(""), 1)

    def test_buttons_share_the_row(self):
        for count in (1, 2, 3):
            lay = panel.panel_layout(3, False, 0, False, count)
            self.assertEqual(len(lay["button_xs"]), count)
            self.assertEqual(lay["button_xs"][0], panel.INNER_X)
            last = lay["button_xs"][-1] + lay["button_ws"][-1]
            self.assertEqual(last, panel.INNER_X + panel.INNER_W)
            for a, b, w in zip(lay["button_xs"], lay["button_xs"][1:], lay["button_ws"]):
                self.assertEqual(b - (a + w), panel.FOOTER_GAP)
        two = panel.panel_layout(3, False, 0, False, 2)
        self.assertEqual(two["button_ws"], [255, 255])

    def test_more_than_three_buttons_are_three(self):
        self.assertEqual(len(panel.panel_layout(3, False, 0, False, 9)["button_xs"]), 3)


class RowTests(unittest.TestCase):
    def test_rows_from_text_pairs_dicts_and_rows(self):
        rows = panel.normalize_rows(
            ["Add", ("Friends", "Auto"), ["Solo"], {"label": "H", "header": True}, PanelRow("Z", "9")]
        )
        self.assertEqual(
            rows,
            [
                PanelRow("Add"),
                PanelRow("Friends", "Auto"),
                PanelRow("Solo"),
                PanelRow("H", "", True),
                PanelRow("Z", "9"),
            ],
        )
        self.assertEqual(panel.normalize_rows(None), [])

    def test_one_line_text_of_a_row(self):
        self.assertEqual(panel.row_text(PanelRow("Friends", "Auto")), "Friends: Auto")
        self.assertEqual(panel.row_text(PanelRow("Add")), "Add")

    def test_a_heading_is_skipped_the_way_the_user_was_going(self):
        rows = [PanelRow("a"), PanelRow("h", header=True), PanelRow("b")]
        self.assertEqual(panel.next_selectable(rows, 1, 1), 2)
        self.assertEqual(panel.next_selectable(rows, 1, -1), 0)

    def test_a_heading_at_an_end_goes_back_to_the_nearest_row(self):
        rows = [PanelRow("h", header=True), PanelRow("a"), PanelRow("b")]
        self.assertEqual(panel.next_selectable(rows, 0, -1), 1)
        rows = [PanelRow("a"), PanelRow("h", header=True)]
        self.assertEqual(panel.next_selectable(rows, 1, 1), 0)
        rows = [PanelRow("h", header=True)]
        self.assertEqual(panel.next_selectable(rows, 0, 1), 0)

    def test_several_headings_in_a_row_are_all_skipped(self):
        rows = [PanelRow("a"), PanelRow("h", header=True), PanelRow("", header=True), PanelRow("b")]
        self.assertEqual(panel.next_selectable(rows, 1, 1), 3)
        self.assertEqual(panel.next_selectable(rows, 2, -1), 0)

    def test_the_first_row_to_land_on_is_not_a_heading(self):
        rows = [PanelRow("h", header=True), PanelRow("a"), PanelRow("b")]
        self.assertEqual(panel.first_selectable(rows, 0), 1)
        self.assertEqual(panel.first_selectable(rows, 2), 2)
        self.assertEqual(panel.first_selectable(rows, 99), 2)
        self.assertEqual(panel.first_selectable([], 0), 0)
        self.assertEqual(panel.first_selectable([PanelRow("h", header=True), PanelRow("a")], 0), 1)


class _Ctl:
    """Stands in for a Kodi control and remembers what was done to it."""

    def __init__(self):
        self.x = self.y = self.w = self.h = None
        self.label = None
        self.text = None
        self.visible = True
        self.items = []
        self.selected = 0
        self.links = {}

    def setPosition(self, x, y):
        self.x, self.y = x, y

    def setWidth(self, w):
        self.w = w

    def setHeight(self, h):
        self.h = h

    def setVisible(self, flag):
        self.visible = bool(flag)

    def setLabel(self, label="", *a, **k):
        self.label = label

    def setText(self, text):
        self.text = text

    def reset(self):
        self.items = []

    def addItem(self, item):
        self.items.append(item)

    def selectItem(self, index):
        self.selected = index

    def getSelectedPosition(self):
        return self.selected

    def getId(self):
        return 0

    def __getattr__(self, name):
        if name.startswith("control"):
            return lambda other: self.links.__setitem__(name, other)
        raise AttributeError(name)


class _Item:
    def __init__(self, label="", label2=""):
        self.label, self.label2, self.props = label, label2, {}

    def setProperty(self, key, value):
        self.props[key] = value


class _Action:
    def __init__(self, aid):
        self._id = aid

    def getId(self):
        return self._id


def make_panel(**kwargs):
    kwargs.setdefault("addon", MagicMock())
    with patch.object(panel, "init_window_xml_dialog", return_value="720p"):
        win = panel.SkippyPanel(panel.XML_NAME, "path", "default", **kwargs)
    ctls = {}
    win.getControl = lambda cid: ctls.setdefault(cid, _Ctl())
    win.focus = None
    win.setFocusId = lambda cid: setattr(win, "focus", cid)
    win.getFocusId = lambda: win.focus
    win.closed = 0
    win.close = lambda: setattr(win, "closed", win.closed + 1)
    return win, ctls


def opened(**kwargs):
    win, ctls = make_panel(**kwargs)
    with patch.object(panel.xbmcgui, "ListItem", _Item), patch.object(
        panel, "reconcile_window_xml_skin_resolution", return_value="720p"
    ):
        win.onInit()
    return win, ctls


ROWS = [PanelRow("Friends", "Intro, Recap"), PanelRow("Star Wars", "Intro")]


class WindowTests(unittest.TestCase):
    def test_a_list_window_shows_the_rows_the_texts_and_the_buttons(self):
        win, c = opened(heading="Title autoskip", subtitle="Pick one", rows=ROWS, buttons=["Close"],
                        footnote="Counting since today")
        self.assertEqual(c[panel.ID_TITLE].label, "Title autoskip")
        self.assertEqual(c[panel.ID_SUBTITLE].label, "Pick one")
        self.assertEqual(c[panel.ID_FOOTNOTE].label, "Counting since today")
        self.assertEqual([(i.label, i.label2) for i in c[panel.ID_LIST].items], [("Friends", "Intro, Recap"), ("Star Wars", "Intro")])
        self.assertEqual(c[panel.FOOTER_IDS[0]].label, "Close")
        self.assertTrue(c[panel.ID_LIST].visible)
        self.assertFalse(c[panel.ID_MESSAGE].visible)
        self.assertTrue(c[panel.FOOTER_IDS[0]].visible)
        self.assertFalse(c[panel.FOOTER_IDS[1]].visible)
        self.assertFalse(c[panel.FOOTER_IDS[2]].visible)
        self.assertEqual(win.focus, panel.ID_LIST)

    def test_headings_are_marked_and_the_first_row_is_selected(self):
        rows = [PanelRow("Skips by type", header=True), PanelRow("Intro", "3")]
        win, c = opened(heading="x", rows=rows, buttons=["Close"])
        self.assertEqual(c[panel.ID_LIST].items[0].props, {"header": "true"})
        self.assertEqual(c[panel.ID_LIST].items[1].props, {})
        self.assertEqual(c[panel.ID_LIST].selected, 1)

    def test_the_preselected_row_is_selected(self):
        win, c = opened(heading="x", rows=[PanelRow("a"), PanelRow("b"), PanelRow("c")], preselect=2, buttons=["Cancel"])
        self.assertEqual(c[panel.ID_LIST].selected, 2)

    def test_no_subtitle_and_no_footnote_hide_their_labels(self):
        win, c = opened(heading="x", rows=ROWS, buttons=["Close"])
        self.assertFalse(c[panel.ID_SUBTITLE].visible)
        self.assertFalse(c[panel.ID_FOOTNOTE].visible)

    def test_a_message_window_shows_the_text_and_focuses_a_button(self):
        win, c = opened(heading="Reset?", message="Sure?", buttons=["Reset", "Cancel"], focus_button=1)
        self.assertEqual(c[panel.ID_MESSAGE].text, "Sure?")
        self.assertTrue(c[panel.ID_MESSAGE].visible)
        self.assertFalse(c[panel.ID_LIST].visible)
        self.assertFalse(c[panel.ID_SCROLL].visible)
        self.assertEqual(win.focus, panel.FOOTER_IDS[1])
        self.assertTrue(c[panel.FOOTER_IDS[1]].visible)
        self.assertFalse(c[panel.FOOTER_IDS[2]].visible)

    def test_the_panel_buttons_and_list_are_placed_by_the_layout(self):
        win, c = opened(heading="x", rows=ROWS, subtitle="s", buttons=["A", "B"], footnote="f")
        lay = panel.panel_layout(2, True, 0, True, 2)
        self.assertEqual((c[panel.ID_PANEL].x, c[panel.ID_PANEL].y), (panel.PANEL_X, lay["panel_y"]))
        self.assertEqual((c[panel.ID_BACKDROP].w, c[panel.ID_BACKDROP].h), (panel.PANEL_W, lay["panel_h"]))
        self.assertEqual((c[panel.ID_LIST].y, c[panel.ID_LIST].h), (lay["list_top"], lay["body_h"]))
        self.assertEqual((c[panel.ID_FOOTNOTE].y, c[panel.ID_FOOTNOTE].h), (lay["footnote_top"], panel.FOOTNOTE_H))
        for n in range(2):
            ctl = c[panel.FOOTER_IDS[n]]
            self.assertEqual((ctl.x, ctl.y, ctl.w, ctl.h), (lay["button_xs"][n], lay["footer_top"], lay["button_ws"][n], 40))

    def test_everything_is_scaled_for_1080i(self):
        win, c = make_panel(heading="x", rows=ROWS, buttons=["Close"])
        win._skin_resolution = "1080i"
        with patch.object(panel.xbmcgui, "ListItem", _Item), patch.object(
            panel, "reconcile_window_xml_skin_resolution", return_value="1080i"
        ):
            win.onInit()
        lay = panel.panel_layout(2, False, 0, False, 1)
        self.assertEqual(c[panel.ID_BACKDROP].w, round(panel.PANEL_W * 1.5))
        self.assertEqual(c[panel.ID_LIST].h, round(lay["body_h"] * 1.5))
        self.assertEqual(c[panel.ID_PANEL].x, round(panel.PANEL_X * 1.5))

    def test_a_scrollbar_only_for_a_long_list(self):
        _win, c = opened(heading="x", rows=ROWS, buttons=["Close"])
        self.assertFalse(c[panel.ID_SCROLL].visible)
        _win, c = opened(heading="x", rows=[PanelRow("r%d" % n) for n in range(60)], buttons=["Close"])
        self.assertTrue(c[panel.ID_SCROLL].visible)

    def test_up_and_down_link_the_list_and_the_buttons(self):
        win, c = opened(heading="x", rows=ROWS, buttons=["A", "B"])
        b0, b1 = c[panel.FOOTER_IDS[0]], c[panel.FOOTER_IDS[1]]
        self.assertIs(b0.links["controlUp"], c[panel.ID_LIST])
        self.assertIs(c[panel.ID_LIST].links["controlDown"], b0)
        self.assertIs(b0.links["controlRight"], b1)
        self.assertIs(b1.links["controlLeft"], b0)
        self.assertIs(b0.links["controlLeft"], b0)
        self.assertIs(b1.links["controlRight"], b1)
        self.assertIs(b0.links["controlDown"], b0)

    def test_without_a_list_up_stays_on_the_button(self):
        win, c = opened(heading="x", message="m", buttons=["A"])
        b0 = c[panel.FOOTER_IDS[0]]
        self.assertIs(b0.links["controlUp"], b0)

    def test_clicking_a_row_answers_with_its_index(self):
        win, c = opened(heading="x", rows=ROWS, buttons=["Close"])
        c[panel.ID_LIST].selected = 1
        win.onClick(panel.ID_LIST)
        self.assertEqual(win.outcome, (panel.RESULT_ROW, 1))
        self.assertEqual(win.closed, 1)

    def test_clicking_a_heading_does_nothing(self):
        win, c = opened(heading="x", rows=[PanelRow("h", header=True), PanelRow("a")], buttons=["Close"])
        c[panel.ID_LIST].selected = 0
        win.onClick(panel.ID_LIST)
        self.assertEqual(win.outcome, (panel.RESULT_CANCEL, -1))
        self.assertEqual(win.closed, 0)

    def test_clicking_a_button_answers_with_its_index(self):
        win, _c = opened(heading="x", message="m", buttons=["Yes", "No"])
        win.onClick(panel.FOOTER_IDS[1])
        self.assertEqual(win.outcome, (panel.RESULT_BUTTON, 1))

    def test_a_button_that_is_not_shown_is_not_answered(self):
        win, _c = opened(heading="x", message="m", buttons=["Yes"])
        win.onClick(panel.FOOTER_IDS[2])
        self.assertEqual(win.closed, 0)

    def test_back_closes_with_no_answer(self):
        for aid in (10, 92, 216):
            win, _c = opened(heading="x", rows=ROWS, buttons=["Close"])
            win.onAction(_Action(aid))
            self.assertEqual(win.outcome, (panel.RESULT_CANCEL, -1))
            self.assertEqual(win.closed, 1)

    def test_it_closes_only_once(self):
        win, _c = opened(heading="x", rows=ROWS, buttons=["Close"])
        win.onClick(panel.FOOTER_IDS[0])
        win.onAction(_Action(10))
        self.assertEqual(win.closed, 1)
        self.assertEqual(win.outcome, (panel.RESULT_BUTTON, 0))

    def test_moving_onto_a_heading_goes_on_to_the_next_row(self):
        rows = [PanelRow("a", "1"), PanelRow("h", header=True), PanelRow("b", "2")]
        win, c = opened(heading="x", rows=rows, buttons=["Close"])
        c[panel.ID_LIST].selected = 1  # Kodi has just moved down onto the heading
        win.onAction(_Action(panel._MOVE_DOWN))
        self.assertEqual(c[panel.ID_LIST].selected, 2)
        c[panel.ID_LIST].selected = 1  # and up onto it from below
        win.onAction(_Action(panel._MOVE_UP))
        self.assertEqual(c[panel.ID_LIST].selected, 0)

    def test_moving_between_rows_is_left_to_kodi(self):
        rows = [PanelRow("a"), PanelRow("h", header=True), PanelRow("b")]
        win, c = opened(heading="x", rows=rows, buttons=["Close"])
        c[panel.ID_LIST].selected = 2
        win.onAction(_Action(panel._MOVE_DOWN))
        self.assertEqual(c[panel.ID_LIST].selected, 2)

    def test_headings_are_not_looked_at_when_the_focus_is_on_a_button(self):
        rows = [PanelRow("a"), PanelRow("h", header=True), PanelRow("b")]
        win, c = opened(heading="x", rows=rows, buttons=["Close"])
        win.focus = panel.FOOTER_IDS[0]
        c[panel.ID_LIST].selected = 1
        win.onAction(_Action(panel._MOVE_DOWN))
        self.assertEqual(c[panel.ID_LIST].selected, 1)

    def test_a_window_without_buttons_gets_a_close_button(self):
        win, c = opened(heading="x", rows=ROWS)
        self.assertEqual(c[panel.FOOTER_IDS[0]].label, win._buttons[0])
        self.assertEqual(len(win._buttons), 1)

    def test_a_failing_control_does_not_stop_the_others(self):
        win, c = make_panel(heading="x", rows=ROWS, buttons=["Close"])

        def broken(cid):
            if cid == panel.ID_SUBTITLE:
                raise RuntimeError("missing")
            return c.setdefault(cid, _Ctl())

        win.getControl = broken
        with patch.object(panel.xbmcgui, "ListItem", _Item), patch.object(
            panel, "reconcile_window_xml_skin_resolution", return_value="720p"
        ):
            win.onInit()
        self.assertEqual(c[panel.ID_TITLE].label, "x")
        self.assertEqual(len(c[panel.ID_LIST].items), 2)


class ShowTests(unittest.TestCase):
    def shown(self, outcome=(panel.RESULT_CANCEL, -1)):
        """Patch show_panel to answer ``outcome`` and remember what it was asked."""
        return patch.object(panel, "show_panel", return_value=outcome)

    def test_a_list_pick_returns_the_row(self):
        with self.shown((panel.RESULT_ROW, 2)) as show:
            index = panel.show_panel_list_pick("H", ["a", "b", ("c", "v")], subtitle="s", preselect=1, cancel_label="Close")
        self.assertEqual(index, 2)
        args, kwargs = show.call_args
        self.assertEqual(args[0], "H")
        self.assertEqual(kwargs["rows"], [PanelRow("a"), PanelRow("b"), PanelRow("c", "v")])
        self.assertEqual((kwargs["subtitle"], kwargs["preselect"], kwargs["buttons"]), ("s", 1, ["Close"]))

    def test_a_list_pick_closed_or_cancelled_is_minus_one(self):
        with self.shown((panel.RESULT_CANCEL, -1)):
            self.assertEqual(panel.show_panel_list_pick("H", ["a"]), -1)
        with self.shown((panel.RESULT_BUTTON, 0)):
            self.assertEqual(panel.show_panel_list_pick("H", ["a"]), -1)

    def test_a_list_pick_without_a_cancel_label_says_cancel(self):
        with self.shown() as show:
            panel.show_panel_list_pick("H", ["a"])
        self.assertEqual(show.call_args.kwargs["buttons"], ["Cancel"])

    def test_rows_are_shown_with_a_close_button_and_the_footnote(self):
        with self.shown() as show:
            panel.show_panel_rows("Stats", [("Time saved", "2m")], "Close", footnote="since")
        self.assertEqual(show.call_args.kwargs["rows"], [PanelRow("Time saved", "2m")])
        self.assertEqual(show.call_args.kwargs["buttons"], ["Close"])
        self.assertEqual(show.call_args.kwargs["footnote"], "since")

    def test_a_message_has_one_button(self):
        with self.shown() as show:
            panel.show_panel_message("H", "Nothing here", "Close")
        self.assertEqual(show.call_args.kwargs["message"], "Nothing here")
        self.assertEqual(show.call_args.kwargs["buttons"], ["Close"])

    def test_a_question_is_true_only_for_the_first_button(self):
        with self.shown((panel.RESULT_BUTTON, 0)) as show:
            self.assertTrue(panel.show_panel_yesno("H", "m", "Delete", "Cancel"))
        self.assertEqual(show.call_args.kwargs["buttons"], ["Delete", "Cancel"])
        with self.shown((panel.RESULT_BUTTON, 1)):
            self.assertFalse(panel.show_panel_yesno("H", "m", "Delete", "Cancel"))
        with self.shown((panel.RESULT_CANCEL, -1)):
            self.assertFalse(panel.show_panel_yesno("H", "m", "Delete", "Cancel"))

    def test_show_panel_opens_the_window_modally_and_returns_its_answer(self):
        class Fake:
            created = None

            opens = True

            def __init__(self, *args, **kwargs):
                Fake.created = (args, kwargs)
                self.outcome = (panel.RESULT_ROW, 3)
                self.opened = False

            def doModal(self):
                self.opened = Fake.opens

        addon = MagicMock()
        addon.getAddonInfo.return_value = "w:/addon"
        with patch.object(panel, "SkippyPanel", Fake), patch.object(panel, "get_addon", return_value=addon):
            out = panel.show_panel("H", rows=["a"], buttons=["Close"])
        self.assertEqual(out, (panel.RESULT_ROW, 3))
        args, kwargs = Fake.created
        self.assertEqual(args, (panel.XML_NAME, "w:/addon", "default"))
        self.assertEqual(kwargs["heading"], "H")

    def test_a_window_that_never_opened_is_an_error_so_the_fallback_takes_over(self):
        class Silent:
            def __init__(self, *args, **kwargs):
                self.opened = False
                self.outcome = (panel.RESULT_CANCEL, -1)

            def doModal(self):
                pass

        addon = MagicMock()
        addon.getAddonInfo.return_value = "w:/addon"
        with patch.object(panel, "SkippyPanel", Silent), patch.object(panel, "get_addon", return_value=addon):
            with self.assertRaises(RuntimeError):
                panel.show_panel("H", rows=["a"], buttons=["Close"])

    def test_the_real_window_marks_itself_opened(self):
        win, _c = opened(heading="x", rows=ROWS, buttons=["Close"])
        self.assertTrue(win.opened)
        self.assertFalse(make_panel(heading="x", rows=ROWS)[0].opened)


class FallbackTests(unittest.TestCase):
    """If the panel cannot open, the grey editor dialogs, then Kodi's own, take over."""

    def boom(self):
        return patch.object(panel, "show_panel", side_effect=RuntimeError("no skin"))

    def editor(self, **funcs):
        import sys
        import types

        module = types.ModuleType("skippy_editor_modal_skin")
        for name, func in funcs.items():
            setattr(module, name, func)
        return patch.dict(sys.modules, {"skippy_editor_modal_skin": module})

    def test_a_list_falls_back_to_the_editor_list_with_one_line_rows(self):
        seen = {}

        def pick(heading, options, subtitle="", preselect=0, cancel_label=None):
            seen.update(heading=heading, options=options, subtitle=subtitle, cancel=cancel_label)
            return 1

        with self.boom(), self.editor(show_editor_list_pick=pick):
            index = panel.show_panel_list_pick("H", [("Friends", "Intro"), "Add"], subtitle="s", cancel_label="Close")
        self.assertEqual(index, 1)
        self.assertEqual(seen["options"], ["Friends: Intro", "Add"])
        self.assertEqual((seen["subtitle"], seen["cancel"]), ("s", "Close"))

    def test_a_list_falls_back_to_the_stock_select_last(self):
        def broken(*a, **k):
            raise RuntimeError("editor")

        with self.boom(), self.editor(show_editor_list_pick=broken), patch.object(panel.xbmcgui, "Dialog") as dialog:
            dialog.return_value.select.return_value = 0
            self.assertEqual(panel.show_panel_list_pick("H", ["a", "b"]), 0)

    def test_rows_fall_back_to_the_editor_message(self):
        shown = []
        with self.boom(), self.editor(show_editor_ok=lambda h, m, ok=None: shown.append((h, m, ok))):
            panel.show_panel_rows("Stats", [("Time saved", "2m"), PanelRow("Skips", header=True), PanelRow("Intro", "3")],
                                  "Close", footnote="since")
        heading, body, ok = shown[0]
        self.assertEqual((heading, ok), ("Stats", "Close"))
        self.assertIn("Time saved: 2m", body)
        self.assertIn("Intro: 3", body)
        self.assertTrue(body.endswith("since"))

    def test_a_message_falls_back_to_the_editor_message(self):
        shown = []
        with self.boom(), self.editor(show_editor_ok=lambda h, m, ok=None: shown.append((h, m, ok))):
            panel.show_panel_message("H", "text", "Close")
        self.assertEqual(shown, [("H", "text", "Close")])

    def test_a_question_falls_back_to_the_editor_question(self):
        with self.boom(), self.editor(sidecar_overwrite_yesno_show=lambda h, m, y, n: True):
            self.assertTrue(panel.show_panel_yesno("H", "m", "Yes", "No"))
        with self.boom(), self.editor(sidecar_overwrite_yesno_show=lambda h, m, y, n: False):
            self.assertFalse(panel.show_panel_yesno("H", "m", "Yes", "No"))

    def test_a_question_falls_back_to_the_stock_yesno_last(self):
        def broken(*a, **k):
            raise RuntimeError("editor")

        with self.boom(), self.editor(sidecar_overwrite_yesno_show=broken), patch.object(panel.xbmcgui, "Dialog") as dialog:
            dialog.return_value.yesno.return_value = True
            self.assertTrue(panel.show_panel_yesno("H", "m", "Yes", "No"))


if __name__ == "__main__":
    unittest.main()
