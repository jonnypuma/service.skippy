# -*- coding: utf-8 -*-
"""The live mockup in the Customize next episode popup screen."""

import os
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import next_episode_appearance as app
import next_episode_customize_ui as cust
import next_episode_dialog as dlg_mod
import next_episode_look as look_mod
import next_episode_view as view
from tests.test_next_episode_look import _dialog as _real_dialog

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SKINS = os.path.join(ROOT, "resources", "skins", "default")
MOCK = cust.MOCK_IDS


class _Addon:
    """Just enough of xbmcaddon.Addon: no translations (the English defaults show), real paths."""

    def __init__(self, **settings):
        self.settings = {k: str(v) for k, v in settings.items()}

    def getAddonInfo(self, key):
        return {"path": ROOT, "icon": os.path.join(ROOT, "icon.png")}.get(key, "")

    def getLocalizedString(self, string_id):
        return ""

    def getSetting(self, key):
        return self.settings.get(key, "")

    getSettingString = getSetting


class _Ctrl:
    def __init__(self, cid):
        self.cid = cid
        self.pos = None
        self.width = None
        self.height = None
        self.visible = None
        self.label = None

    def setPosition(self, x, y):
        self.pos = (x, y)

    def setWidth(self, w):
        self.width = w

    def setHeight(self, h):
        self.height = h

    def setVisible(self, flag):
        self.visible = flag

    def setLabel(self, label="", label2=""):
        self.label = label
        self.label2 = label2


def _modal(draft=None, scale=None, addon=None):
    modal = cust.NextEpisodeCustomize.__new__(cust.NextEpisodeCustomize)
    modal.addon = addon or _Addon()
    modal._draft = dict(app.DEFAULT_DRAFT, **(draft or {}))
    modal._original = dict(modal._draft)
    modal._skin_resolution = "720p"
    modal.props = {}
    modal.ctrls = {}
    modal.setProperty = lambda k, v: modal.props.__setitem__(k, v)
    modal._sc = scale or (lambda v: v)
    modal._ctrl = lambda cid: modal.ctrls.setdefault(cid, _Ctrl(cid))
    modal.setFocusId = lambda cid: None
    return modal


def _elements(path):
    root = ET.parse(path).getroot()
    return root, {int(c.get("id")): c for c in root.iter("control") if c.get("id")}


def _num(element, tag):
    text = element.findtext(tag)
    return int(text) if text is not None else None


class ViewIdsTests(unittest.TestCase):
    def test_the_popup_dialog_uses_the_shared_ids(self):
        ids = view.popup_ids()
        self.assertEqual(
            (ids.panel, ids.backdrop, ids.thumb, ids.heading, ids.episode, ids.countdown),
            (dlg_mod.ID_PANEL, dlg_mod.ID_BACKDROP, dlg_mod.ID_THUMB, dlg_mod.ID_HEADING,
             dlg_mod.ID_EPISODE, dlg_mod.ID_COUNTDOWN),
        )
        self.assertEqual((ids.play, ids.close), (dlg_mod.ID_PLAY, dlg_mod.ID_CLOSE))
        self.assertEqual((ids.plate_play, ids.plate_close), (dlg_mod.ID_PLATE_PLAY, dlg_mod.ID_PLATE_CLOSE))
        self.assertEqual((ids.bar_bg, ids.bar_fill, ids.bar_fill_stretch),
                         (dlg_mod.ID_BAR_BG, dlg_mod.ID_BAR_FILL, dlg_mod.ID_BAR_FILL_STRETCH))
        self.assertEqual(dlg_mod.FOCUS_IMAGES, {ids.play: ids.focus_play, ids.close: ids.focus_close})

    def test_the_mockup_copy_is_the_same_ids_shifted(self):
        base, mock = view.popup_ids(), view.popup_ids(view.MOCK_ID_OFFSET)
        for name in view.PopupIds.__dataclass_fields__:
            a, b = getattr(base, name), getattr(mock, name)
            if isinstance(a, tuple):
                self.assertEqual(tuple(x + view.MOCK_ID_OFFSET for x in a), b, name)
            else:
                self.assertEqual(a + view.MOCK_ID_OFFSET, b, name)

    def test_no_id_is_used_twice_in_the_customize_screen(self):
        flat = []
        for name in view.PopupIds.__dataclass_fields__:
            value = getattr(MOCK, name)
            flat.extend(value if isinstance(value, tuple) else [value])
        own = list(cust.ROW_IDS.values()) + list(cust.FOOTER_IDS) + [
            cust.ID_PANEL, cust.ID_BACKDROP, cust.ID_TITLE, cust.ID_STAGE,
        ]
        everything = flat + own
        self.assertEqual(len(set(everything)), len(everything))


class ViewPlacementTests(unittest.TestCase):
    def layout(self, **kw):
        kw.setdefault("thumbnail", True)
        kw.setdefault("countdown", True)
        kw.setdefault("progress", True)
        return app.popup_layout(**kw)

    def test_every_control_of_a_full_popup_is_placed_once(self):
        placed = [p[0] for p in view.popup_placements(self.layout(), MOCK)]
        self.assertEqual(len(placed), len(set(placed)))
        self.assertEqual(len(placed), 18)  # all but the panel group

    def test_a_hidden_row_has_no_placement(self):
        no_thumb = [p[0] for p in view.popup_placements(self.layout(thumbnail=False), MOCK)]
        self.assertNotIn(MOCK.thumb, no_thumb)
        no_count = [p[0] for p in view.popup_placements(self.layout(countdown=False), MOCK)]
        self.assertNotIn(MOCK.countdown, no_count)
        no_bar = [p[0] for p in view.popup_placements(self.layout(progress=False), MOCK)]
        for cid in (MOCK.bar_bg, MOCK.bar_fill, MOCK.bar_fill_stretch):
            self.assertNotIn(cid, no_bar)

    def test_the_dialog_and_the_mockup_place_the_same_things_in_the_same_spots(self):
        lay = self.layout()
        real = view.popup_placements(lay, view.popup_ids())
        mock = view.popup_placements(lay, MOCK)
        self.assertEqual(
            [(c - view.MOCK_ID_OFFSET, x, y, w, h) for c, x, y, w, h in mock], real
        )

    def test_the_buttons_share_the_row_and_the_backdrop_covers_the_panel(self):
        lay = self.layout()
        found = {p[0]: p[1:] for p in view.popup_placements(lay, MOCK)}
        self.assertEqual(found[MOCK.backdrop], (0, 0, lay.panel_w, lay.panel_h))
        self.assertEqual(found[MOCK.play][1], found[MOCK.close][1])
        self.assertLess(found[MOCK.play][0], found[MOCK.close][0])


class ViewHelperTests(unittest.TestCase):
    def test_look_properties_match_what_the_dialog_sets(self):
        for look in ("Default", "Terminal", "Modern"):
            for extra in ({}, {look_mod.KEY_BAR_STYLE: "progress_mid_flat_blue.png",
                              look_mod.KEY_CARD_OPACITY: "35",
                              look_mod.KEY_TEXT_COLOR: "FF1976D2"}):
                draft = dict(app.DEFAULT_DRAFT, **{app.KEY_LOOK: look}, **extra)
                dialog = _real_dialog(_Addon(), look=look)
                dialog.draft = draft
                dialog._apply_look()
                _look, tiled, props = view.look_properties(
                    draft, _Addon(), dialog._sc(app.BAR_H) if hasattr(dialog, "_sc") else app.BAR_H,
                    view.skip_text_color(_Addon()),
                )
                for name, value in props.items():
                    self.assertEqual(dialog.props[name], value, (look, extra, name))
                self.assertEqual(tiled, dialog._bar_tiled)

    def test_a_look_without_a_text_colour_follows_the_fallback(self):
        _look, _tiled, props = view.look_properties(app.DEFAULT_DRAFT, _Addon(), 10, "FF123456")
        self.assertEqual(props["skip_dialog_text_color"], "FF123456")
        draft = dict(app.DEFAULT_DRAFT, **{look_mod.KEY_TEXT_COLOR: "FF1976D2"})
        _look, _tiled, props = view.look_properties(draft, _Addon(), 10, "FF123456")
        self.assertEqual(props["skip_dialog_text_color"], "FF1976D2")

    def test_the_skip_dialogs_font_colour_is_read_from_its_setting(self):
        self.assertEqual(view.skip_text_color(_Addon(skip_dialog_font_color="FFFFD54F")), "FFFFD54F")
        self.assertEqual(view.skip_text_color(_Addon()), "FFFFFFFF")

    def test_popup_texts_for_the_prompt_and_for_still_watching(self):
        episode = {"season": 1, "episode": 2, "title": "Pilot"}
        found = view.popup_texts(_Addon(), False, episode)
        self.assertEqual(found, {
            "heading": "Play next episode?", "label": "S01E02 · Pilot",
            "play": "Play now", "close": "Close",
        })
        asking = view.popup_texts(_Addon(), False, episode, still_watching=True)
        self.assertEqual((asking["heading"], asking["play"], asking["close"]),
                         ("Still watching?", "Continue", "Stop"))

    def test_all_caps_shouts_every_text(self):
        found = view.popup_texts(_Addon(), True, {"season": 1, "episode": 2, "title": "Pilot"})
        for text in found.values():
            self.assertEqual(text, text.upper())
        self.assertEqual(view.countdown_text(_Addon(), True, 42), "EPISODE ENDS IN 00:42")
        self.assertEqual(view.countdown_text(_Addon(), False, 42), "Episode ends in 00:42")

    def test_the_fill_is_whole_segments_when_tiled_and_exact_when_stretched(self):
        tiled = view.fill_width(True, 0.5, 500, 10)
        self.assertEqual(tiled, 248)
        self.assertEqual(view.fill_width(False, 0.5, 500, 10), 250)
        self.assertEqual(view.fill_width(False, 2.0, 500, 10), 500)
        self.assertEqual(view.fill_width(False, -1, 500, 10), 0)
        self.assertEqual(view.fill_width(True, 0, 500, 10), 0)

    def test_the_default_button_comes_from_the_draft(self):
        self.assertFalse(view.focus_is_close({}))
        self.assertFalse(view.focus_is_close(app.DEFAULT_DRAFT))
        self.assertTrue(view.focus_is_close({app.KEY_FOCUS: app.FOCUS_CLOSE}))


class MockDrawingTests(unittest.TestCase):
    def draw(self, draft=None, **kw):
        modal = _modal(draft, **kw)
        modal._refresh_mock()
        return modal

    def test_the_default_draft_shows_a_full_popup_in_the_bottom_right_of_the_stage(self):
        modal = self.draw()
        self.assertEqual(modal.props["next_ep_mock_ready"], "true")
        self.assertEqual(modal.props["next_ep_mock_native"], "false")
        self.assertEqual(modal.props["next_ep_heading"], "Play next episode?")
        self.assertEqual(modal.props["next_ep_label"], "S01E02 · Episode title")
        self.assertEqual(modal.props["next_ep_has_thumb"], "true")
        self.assertEqual(modal.props["next_ep_has_bar"], "true")
        self.assertEqual(modal.props["next_ep_mock_focus"], "play")
        self.assertEqual(modal.props["next_ep_countdown"], "Episode ends in 00:31")
        lay = app.popup_layout(thumbnail=True, countdown=True, progress=True)
        x, y = app.popup_origin("BottomRight", lay.panel_w, lay.panel_h,
                                cust._STAGE_W, cust._STAGE_H, cust._MOCK_MARGIN, cust._MOCK_MARGIN)
        self.assertEqual(modal.ctrls[MOCK.panel].pos, (x, y))
        self.assertEqual((modal.ctrls[MOCK.panel].width, modal.ctrls[MOCK.panel].height),
                         (lay.panel_w, lay.panel_h))
        self.assertEqual(modal.ctrls[MOCK.play].label, "Play now")
        self.assertEqual(modal.ctrls[MOCK.close].label, "Close")

    def test_the_backdrop_is_the_addons_fanart(self):
        modal = self.draw()
        self.assertEqual(modal.props["next_ep_mock_backdrop"], os.path.join(ROOT, "fanart.png"))
        self.assertTrue(os.path.isfile(modal.props["next_ep_mock_backdrop"]))

    def test_it_uses_the_looks_colours_and_textures(self):
        modal = self.draw({app.KEY_LOOK: "Terminal"})
        terminal = look_mod.resolve_look("Terminal", None)
        self.assertEqual(modal.props["skip_dialog_text_color"], "FF39FF14")
        self.assertEqual(modal.props["next_ep_card_color"], terminal.card_color)
        self.assertEqual(modal.props["next_ep_focus_texture"], terminal.focus_texture)
        self.assertEqual(modal.props["next_ep_bar_texture"], terminal.bar_texture)
        self.assertEqual(modal.props["next_ep_heading"], "PLAY NEXT EPISODE?")
        self.assertEqual(modal.ctrls[MOCK.play].label, "PLAY NOW")

    def test_every_override_shows_up_in_the_mockup(self):
        modal = self.draw({
            look_mod.KEY_TEXT_COLOR: "FF1976D2",
            look_mod.KEY_HEADING_COLOR: "FFFFFFFF",
            look_mod.KEY_ALL_CAPS: "On",
            look_mod.KEY_FOCUS_STYLE: "button_focus_3d_cyan.png",
            look_mod.KEY_BAR_STYLE: "progress_mid_flat_blue.png",
            look_mod.KEY_CARD_OPACITY: "50",
        })
        self.assertEqual(modal.props["skip_dialog_text_color"], "FF1976D2")
        self.assertEqual(modal.props["next_ep_heading_color"], "FFFFFFFF")
        self.assertEqual(modal.props["next_ep_focus_texture"], "button_focus_3d_cyan.png")
        self.assertEqual(modal.props["next_ep_focus_border"], "sides")
        self.assertEqual(modal.props["next_ep_bar_texture"], "progress_mid_flat_blue.png")
        self.assertEqual(modal.props["next_ep_bar_tiled"], "false")
        self.assertEqual(modal.props["next_ep_card_color"], look_mod.card_color(True, 50))
        self.assertEqual(modal.props["next_ep_heading"], "PLAY NEXT EPISODE?")

    def test_the_position_moves_the_popup_to_that_corner_of_the_stage(self):
        lay = app.popup_layout(thumbnail=True, countdown=True, progress=True)
        for position, expected in (
            ("TopLeft", (20, 20)),
            ("TopRight", (cust._STAGE_W - lay.panel_w - 20, 20)),
            ("BottomLeft", (20, cust._STAGE_H - lay.panel_h - 20)),
            ("BottomRight", (cust._STAGE_W - lay.panel_w - 20, cust._STAGE_H - lay.panel_h - 20)),
        ):
            modal = self.draw({app.KEY_POSITION: position})
            self.assertEqual(modal.ctrls[MOCK.panel].pos, expected, position)

    def test_the_popup_fits_on_the_stage_in_every_corner(self):
        for position in app.POSITIONS:
            for thumb in (True, False):
                lay = app.popup_layout(thumbnail=thumb, countdown=True, progress=True)
                x, y = app.popup_origin(position, lay.panel_w, lay.panel_h,
                                        cust._STAGE_W, cust._STAGE_H, 20, 20)
                self.assertGreaterEqual(x, 0)
                self.assertGreaterEqual(y, 0)
                self.assertLessEqual(x + lay.panel_w, cust._STAGE_W)
                self.assertLessEqual(y + lay.panel_h, cust._STAGE_H)

    def test_no_picture_moves_the_text_to_the_left_edge(self):
        modal = self.draw({app.KEY_THUMBNAIL: False})
        self.assertEqual(modal.props["next_ep_has_thumb"], "false")
        self.assertEqual(modal.ctrls[MOCK.heading].pos[0], app.PAD)
        self.assertNotIn(MOCK.thumb, modal.ctrls)

    def test_no_time_left_hides_that_row_and_no_bar_hides_the_bar(self):
        modal = self.draw({app.KEY_COUNTDOWN: False})
        self.assertIs(modal.ctrls[MOCK.countdown].visible, False)
        self.assertNotIn("next_ep_countdown", modal.props)
        modal = self.draw({app.KEY_PROGRESS: False})
        self.assertEqual(modal.props["next_ep_has_bar"], "false")
        self.assertIs(modal.ctrls[MOCK.bar_bg].visible, False)
        self.assertNotIn(MOCK.bar_fill, modal.ctrls)
        smaller = app.popup_layout(thumbnail=True, countdown=True, progress=False).panel_h
        self.assertEqual(modal.ctrls[MOCK.panel].height, smaller)

    def test_the_bar_is_part_way_down_and_sized_like_the_real_one(self):
        modal = self.draw()
        fraction = app.window_fraction_left(cust.MOCK_HEAD_S, 0.0, cust.MOCK_WINDOW_S)
        self.assertAlmostEqual(fraction, 31 / 45.0)
        self.assertEqual(modal.ctrls[MOCK.bar_fill].width, view.fill_width(True, fraction, 500, 10))
        self.assertEqual(modal.ctrls[MOCK.bar_fill_stretch].width, view.fill_width(False, fraction, 500, 10))
        self.assertTrue(0 < modal.ctrls[MOCK.bar_fill].width < 500)

    def test_the_two_fills_are_sized_by_their_own_rule(self):
        # Further down the bar the whole-segment fill and the exact one differ.
        with patch.object(cust, "MOCK_HEAD_S", 20.0):
            modal = self.draw()
        fraction = 25 / 45.0
        self.assertEqual(modal.ctrls[MOCK.bar_fill].width, 280)
        self.assertEqual(modal.ctrls[MOCK.bar_fill_stretch].width, 278)
        self.assertEqual(modal.ctrls[MOCK.bar_fill].width, view.fill_width(True, fraction, 500, 10))
        self.assertEqual(modal.ctrls[MOCK.bar_fill_stretch].width, view.fill_width(False, fraction, 500, 10))

    def test_a_1080i_skin_gets_the_scaled_numbers(self):
        modal = self.draw(scale=lambda v: int(v * 1.5 + 0.5))
        fraction = 31 / 45.0
        self.assertEqual(modal.ctrls[MOCK.bar_fill].width, view.fill_width(True, fraction, 750, 15))
        lay = app.popup_layout(thumbnail=True, countdown=True, progress=True)
        self.assertEqual(modal.ctrls[MOCK.panel].width, int(lay.panel_w * 1.5 + 0.5))

    def test_the_default_button_is_highlighted(self):
        self.assertEqual(self.draw({app.KEY_FOCUS: "Close"}).props["next_ep_mock_focus"], "close")
        self.assertEqual(self.draw({app.KEY_FOCUS: "Play"}).props["next_ep_mock_focus"], "play")

    def test_the_toast_style_shows_a_toast_and_no_popup(self):
        modal = self.draw({app.KEY_STYLE: "Native"})
        self.assertEqual(modal.props["next_ep_mock_native"], "true")
        self.assertEqual(modal.props["next_ep_mock_ready"], "true")
        self.assertEqual(modal.props["next_ep_mock_toast_heading"], "Play next episode?")
        self.assertIn("S01E02 · Episode title", modal.props["next_ep_mock_toast_body"])
        self.assertIn("Press OK to play", modal.props["next_ep_mock_toast_body"])
        self.assertEqual(modal.props["next_ep_mock_icon"], os.path.join(ROOT, "icon.png"))
        self.assertNotIn(MOCK.panel, modal.ctrls)

    def test_switching_back_from_the_toast_shows_the_popup_again(self):
        modal = _modal({app.KEY_STYLE: "Native"})
        modal._refresh_mock()
        modal._draft[app.KEY_STYLE] = "Custom"
        modal._refresh_mock()
        self.assertEqual(modal.props["next_ep_mock_native"], "false")
        self.assertIn(MOCK.panel, modal.ctrls)


class DialogUsesTheSamePlacementsTests(unittest.TestCase):
    def test_the_popup_places_exactly_what_the_mockup_places(self):
        for kwargs in (
            {"thumbnail": True, "countdown": True, "progress": True},
            {"thumbnail": False, "countdown": False, "progress": True},
            {"thumbnail": True, "countdown": True, "progress": False},
        ):
            dialog = _real_dialog(_Addon())
            placed = []
            dialog._place = lambda cid, x, y, w=None, h=None: placed.append((cid, x, y, w, h))
            dialog._show = lambda cid, visible: None
            layout = app.popup_layout(**kwargs)
            dialog._apply_layout(layout)
            x, y = app.popup_origin(dialog.draft.get(app.KEY_POSITION), layout.panel_w, layout.panel_h)
            expected = [(dlg_mod.ID_PANEL, x, y, layout.panel_w, layout.panel_h)]
            expected += view.popup_placements(layout, view.popup_ids())
            self.assertEqual(placed, expected, kwargs)


class MockFollowsEveryChangeTests(unittest.TestCase):
    def test_changing_a_row_redraws_the_mockup(self):
        modal = _modal()
        modal._refresh()
        before = modal.props["next_ep_card_color"]
        modal._nudge(cust.ROW_IDS[look_mod.KEY_CARD_OPACITY], 1)  # Same as look -> 0 %
        self.assertEqual(modal._draft[look_mod.KEY_CARD_OPACITY], "0")
        self.assertEqual(modal.props["next_ep_card_color"], "00000000")
        self.assertNotEqual(before, "00000000")
        modal._nudge(cust.ROW_IDS[look_mod.KEY_CARD_OPACITY], 1)  # 5 %
        self.assertEqual(modal.props["next_ep_card_color"], look_mod.card_color(True, 5))

    def test_every_row_changes_something_in_the_mockup(self):
        def snapshot(modal):
            ctrls = {cid: (c.pos, c.width, c.height, c.visible, c.label) for cid, c in modal.ctrls.items()
                     if cid >= 7000}
            return dict(modal.props), ctrls

        for key in cust.customize_rows(app.DEFAULT_DRAFT):
            if key == app.KEY_STYLE:
                continue
            # The first colour in the list is white, which the default font colour already is.
            modal = _modal(addon=_Addon(skip_dialog_font_color="FF3D3D3D"))
            modal._refresh()
            before = snapshot(modal)
            modal._nudge(cust.ROW_IDS[key], 1)
            self.assertNotEqual(snapshot(modal), before, key)

    def test_the_look_row_redraws_with_the_new_look_and_clears_the_overrides(self):
        modal = _modal({look_mod.KEY_TEXT_COLOR: "FF1976D2"})
        modal._refresh()
        self.assertEqual(modal.props["skip_dialog_text_color"], "FF1976D2")
        modal._nudge(cust.ROW_IDS[app.KEY_LOOK], 1)
        self.assertEqual(modal._draft[look_mod.KEY_TEXT_COLOR], look_mod.FOLLOW_LOOK)
        self.assertNotEqual(modal.props["skip_dialog_text_color"], "FF1976D2")

    def test_the_toggles_redraw_the_mockup_too(self):
        modal = _modal()
        modal._refresh()
        modal._nudge(cust.ROW_IDS[app.KEY_PROGRESS], 1)
        self.assertEqual(modal.props["next_ep_has_bar"], "false")
        modal._nudge(cust.ROW_IDS[app.KEY_PROGRESS], 1)
        self.assertEqual(modal.props["next_ep_has_bar"], "true")

    def test_a_failing_mockup_never_stops_the_rows(self):
        modal = _modal()
        logged = []
        with patch.object(cust, "log", lambda text: logged.append(text)), patch.object(
            cust, "popup_layout", side_effect=RuntimeError("boom")
        ):
            modal._refresh()
        self.assertEqual(len(logged), 1)
        self.assertIn("boom", logged[0])
        self.assertEqual(modal.ctrls[cust.ROW_IDS[app.KEY_STYLE]].label, "Popup style")
        self.assertEqual(modal.ctrls[cust.ROW_IDS[app.KEY_STYLE]].label2, "Custom")

    def test_the_panel_stays_at_the_left_whatever_the_rows(self):
        for style in ("Custom", "Native"):
            modal = _modal({app.KEY_STYLE: style})
            modal._refresh()
            self.assertEqual(modal.ctrls[cust.ID_PANEL].pos, (cust._PANEL_X, cust._PANEL_Y))


class MockSkinTests(unittest.TestCase):
    def tree(self, res, name="NextEpisodeCustomize.xml"):
        return _elements(os.path.join(SKINS, res, name))

    def test_the_stage_sits_right_of_the_panel_inside_the_screen(self):
        _root, els = self.tree("720p")
        panel, stage = els[cust.ID_PANEL], els[cust.ID_STAGE]
        self.assertEqual((_num(panel, "posx"), _num(panel, "posy")), (cust._PANEL_X, cust._PANEL_Y))
        self.assertEqual(
            (_num(stage, "posx"), _num(stage, "posy"), _num(stage, "width"), _num(stage, "height")),
            (cust._STAGE_X, cust._STAGE_Y, cust._STAGE_W, cust._STAGE_H),
        )
        self.assertLess(cust._PANEL_X + cust._PANEL_W, cust._STAGE_X)
        self.assertLessEqual(cust._STAGE_X + cust._STAGE_W, app.BASE_SCREEN_W)
        self.assertLessEqual(cust._STAGE_Y + cust._STAGE_H, app.BASE_SCREEN_H)
        self.assertLessEqual(cust._PANEL_Y + cust.row_layout(list(range(13)))[2], app.BASE_SCREEN_H)

    def test_every_control_has_its_own_id_in_both_resolutions(self):
        for res in ("720p", "1080i"):
            root, els = self.tree(res)
            ids = [c.get("id") for c in root.iter("control") if c.get("id")]
            self.assertEqual(len(ids), len(set(ids)), res)
            for name in view.PopupIds.__dataclass_fields__:
                value = getattr(MOCK, name)
                for cid in value if isinstance(value, tuple) else (value,):
                    self.assertIn(cid, els, (res, name))

    def test_the_mockup_has_a_copy_of_every_popup_control(self):
        _root, real = self.tree("720p", "NextEpisodeDialog.xml")
        _root, mock = self.tree("720p")
        for cid, element in real.items():
            copy = mock.get(cid + view.MOCK_ID_OFFSET)
            self.assertIsNotNone(copy, cid)
            self.assertEqual(copy.get("type"), element.get("type"), cid)
            for tag in ("left", "top", "width", "height", "font", "label", "colordiffuse",
                        "textcolor", "align", "wrapmultiline", "aspectratio"):
                self.assertEqual(copy.findtext(tag), element.findtext(tag), (cid, tag))
            texture = element.find("texture")
            if texture is not None:
                self.assertEqual(copy.findtext("texture"), element.findtext("texture"), cid)
                self.assertEqual(copy.find("texture").attrib, texture.attrib, cid)

    def test_the_mockup_buttons_are_only_drawn_never_focusable(self):
        _root, mock = self.tree("720p")
        for cid in (MOCK.play, MOCK.close):
            element = mock[cid]
            self.assertEqual(element.findtext("enable"), "false", cid)
            for tag in ("onleft", "onright", "onup", "ondown"):
                self.assertIsNone(element.find(tag), (cid, tag))
        text = open(os.path.join(SKINS, "720p", "NextEpisodeCustomize.xml"), encoding="utf-8").read()
        self.assertNotIn("Control.HasFocus", text)

    def test_the_focus_highlight_follows_the_default_button_setting(self):
        _root, mock = self.tree("720p")
        for ids, button in ((MOCK.focus_play, "play"), (MOCK.focus_close, "close")):
            for cid in ids:
                condition = mock[cid].findtext("visible")
                self.assertIn("next_ep_mock_focus),%s" % button, condition)
                self.assertIn("next_ep_focus_border", condition)

    def test_the_default_layout_in_the_skin_is_the_full_popup_bottom_right(self):
        _root, mock = self.tree("720p")
        lay = app.popup_layout(thumbnail=True, countdown=True, progress=True)
        x, y = app.popup_origin("BottomRight", lay.panel_w, lay.panel_h,
                                cust._STAGE_W, cust._STAGE_H, 20, 20)
        self.assertEqual((_num(mock[MOCK.panel], "posx"), _num(mock[MOCK.panel], "posy")), (x, y))
        self.assertEqual((_num(mock[MOCK.panel], "width"), _num(mock[MOCK.panel], "height")),
                         (lay.panel_w, lay.panel_h))
        for cid, px, py, pw, ph in view.popup_placements(lay, MOCK):
            element = mock[cid]
            self.assertEqual(
                (_num(element, "left"), _num(element, "top"), _num(element, "width"), _num(element, "height")),
                (px, py, pw, ph), cid,
            )

    def test_the_mockup_waits_for_its_layout_and_hides_for_the_toast_style(self):
        _root, els = self.tree("720p")
        condition = els[MOCK.panel].findtext("visible")
        self.assertIn("next_ep_mock_ready", condition)
        self.assertIn("!String.IsEqual(Window.Property(next_ep_mock_native),true)", condition)
        self.assertIn("next_ep_mock_native),true)", els[7100].findtext("visible"))

    def test_the_1080i_skin_is_the_720p_one_scaled(self):
        _r, small = self.tree("720p")
        _r, big = self.tree("1080i")
        self.assertEqual(set(small), set(big))
        for cid in list(range(7000, 7019)) + [cust.ID_STAGE, 7100, 7104]:
            for tag in ("left", "top", "width", "height", "posx", "posy"):
                if small[cid].findtext(tag) is None or not small[cid].findtext(tag).lstrip("-").isdigit():
                    continue
                self.assertEqual(
                    int(big[cid].findtext(tag)), int(int(small[cid].findtext(tag)) * 1.5 + 0.5), (cid, tag)
                )

    def test_the_stage_is_painted_on_a_solid_texture_so_the_page_behind_never_shows(self):
        from PIL import Image

        for res in ("720p", "1080i"):
            _r, els = self.tree(res)
            name = els[6101].findtext("texture")
            alpha = Image.open(os.path.join(SKINS, "media", name)).convert("RGBA").getchannel("A")
            self.assertEqual(alpha.getextrema(), (255, 255), (res, name))
            colour = els[6101].findtext("colordiffuse")
            self.assertTrue(colour is None or colour.upper().startswith("FF"), res)

    def test_the_toast_mockup_is_inside_the_stage_at_the_top_right(self):
        _r, els = self.tree("720p")
        toast = els[7100]
        x, y = _num(toast, "posx"), _num(toast, "posy")
        self.assertEqual(x + _num(toast, "width") + 20, cust._STAGE_W)
        self.assertEqual(y, 20)
        self.assertLessEqual(y + _num(toast, "height"), cust._STAGE_H)


if __name__ == "__main__":
    unittest.main()
