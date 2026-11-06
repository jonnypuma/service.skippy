# -*- coding: utf-8 -*-
"""Next episode popup: layout, settings, skin XML, dialog behaviour, Customize modal."""

import os
import re
import threading
import types
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import addon_skin_resolution as skin_res
import next_episode_appearance as app
import next_episode_customize_ui as cust
import next_episode_dialog as dlg_mod
import next_episode_lookup as lookup
import next_episode_prompt as prompt

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SKINS = os.path.join(ROOT, "resources", "skins", "default")


def _controls(path):
    """``{control id: {tag: number}}`` for every control with an id in a skin XML."""
    out = {}
    for ctrl in ET.parse(path).getroot().iter("control"):
        cid = ctrl.get("id")
        if cid is None:
            continue
        values = {}
        for tag in ("left", "top", "width", "height", "posx", "posy"):
            text = ctrl.findtext(tag)
            if text is not None:
                values[tag] = int(text)
        out[int(cid)] = values
    return out


class PopupLayoutTests(unittest.TestCase):
    def layout(self, thumbnail=True, countdown=True, progress=True):
        return app.popup_layout(thumbnail=thumbnail, countdown=countdown, progress=progress)

    def test_everything_on_stacks_the_rows_in_order(self):
        lay = self.layout()
        ys = [lay.heading_y, lay.episode_y, lay.countdown_y, lay.bar_y, lay.buttons_y]
        self.assertEqual(ys, sorted(ys))
        self.assertEqual(len(set(ys)), len(ys))
        self.assertEqual(lay.panel_h, lay.buttons_y + app.BUTTON_H + app.PAD)

    def test_rows_never_overlap(self):
        lay = self.layout()
        self.assertGreaterEqual(lay.episode_y, lay.heading_y + app.HEADING_H)
        self.assertGreaterEqual(lay.countdown_y, lay.episode_y + app.EPISODE_H)
        self.assertGreaterEqual(lay.bar_y, lay.countdown_y + app.COUNTDOWN_H)
        self.assertGreaterEqual(lay.buttons_y, lay.bar_y + app.BAR_H)

    def test_hidden_rows_leave_no_gap(self):
        full = self.layout()
        no_countdown = self.layout(countdown=False)
        self.assertIsNone(no_countdown.countdown_y)
        self.assertEqual(no_countdown.bar_y, full.countdown_y)
        self.assertLess(no_countdown.panel_h, full.panel_h)
        bare = self.layout(countdown=False, progress=False)
        self.assertEqual((bare.countdown_y, bare.bar_y), (None, None))
        self.assertLess(bare.panel_h, no_countdown.panel_h)

    def test_picture_narrows_the_text_column(self):
        with_pic, without = self.layout(), self.layout(thumbnail=False)
        self.assertEqual(without.text_x, app.PAD)
        self.assertEqual(with_pic.text_x, app.PAD + app.THUMB_W + app.TEXT_GAP)
        self.assertEqual(with_pic.text_x + with_pic.text_w, without.text_x + without.text_w)

    def test_picture_never_overhangs_the_rows_beside_it(self):
        lay = self.layout()
        self.assertGreaterEqual(lay.countdown_y, app.PAD + app.THUMB_H)

    def test_two_buttons_fit_inside_the_panel(self):
        lay = self.layout()
        self.assertLessEqual(2 * lay.button_w + app.BUTTON_GAP, lay.panel_w - 2 * app.PAD)


class PopupOriginTests(unittest.TestCase):
    def test_corners(self):
        w, h = app.PANEL_W, 180
        self.assertEqual(app.popup_origin("TopLeft", w, h), (20, 20))
        self.assertEqual(app.popup_origin("TopRight", w, h), (1280 - w - 20, 20))
        self.assertEqual(app.popup_origin("BottomLeft", w, h), (20, 720 - h - 20))
        self.assertEqual(app.popup_origin("BottomRight", w, h), (1280 - w - 20, 720 - h - 20))

    def test_unknown_position_falls_back_to_bottom_right(self):
        self.assertEqual(
            app.popup_origin("Middle", 520, 180), app.popup_origin("BottomRight", 520, 180)
        )

    def test_a_display_text_with_a_space_is_accepted(self):
        self.assertEqual(app.popup_origin("Top Left", 520, 180), (20, 20))

    def test_a_panel_larger_than_the_screen_stays_on_screen(self):
        self.assertEqual(app.popup_origin("BottomRight", 2000, 900), (20, 20))


class DraftTests(unittest.TestCase):
    def test_defaults(self):
        draft = app.draft_from_reader(lambda k, d: d, lambda k, d: d)
        self.assertEqual(draft, app.DEFAULT_DRAFT)

    def test_stored_text_is_normalised(self):
        texts = {app.KEY_STYLE: "native", app.KEY_POSITION: "top left", app.KEY_FOCUS: "CLOSE"}
        draft = app.draft_from_reader(lambda k, d: texts.get(k, d), lambda k, d: False)
        self.assertEqual(draft[app.KEY_STYLE], app.STYLE_NATIVE)
        self.assertEqual(draft[app.KEY_POSITION], "TopLeft")
        self.assertEqual(draft[app.KEY_FOCUS], app.FOCUS_CLOSE)
        self.assertFalse(draft[app.KEY_THUMBNAIL])

    def test_garbage_falls_back_to_the_default(self):
        draft = app.draft_from_reader(lambda k, d: "???", lambda k, d: d)
        self.assertEqual(draft[app.KEY_STYLE], app.DEFAULT_DRAFT[app.KEY_STYLE])
        self.assertEqual(draft[app.KEY_POSITION], app.DEFAULT_DRAFT[app.KEY_POSITION])

    def test_payload_is_what_setsetting_stores(self):
        draft = dict(app.DEFAULT_DRAFT, **{app.KEY_THUMBNAIL: False, app.KEY_POSITION: "TopRight"})
        payload = app.draft_setting_payload(draft)
        self.assertEqual(payload[app.KEY_THUMBNAIL], "false")
        self.assertEqual(payload[app.KEY_COUNTDOWN], "true")
        self.assertEqual(payload[app.KEY_POSITION], "TopRight")
        self.assertEqual(set(payload), set(app.DEFAULT_DRAFT))

    def test_load_draft_without_an_addon(self):
        self.assertEqual(app.load_popup_draft(None), app.DEFAULT_DRAFT)

    def test_cycle_wraps_in_both_directions(self):
        self.assertEqual(app.cycle_choice(app.KEY_POSITION, "BottomLeft", 1), "BottomRight")
        self.assertEqual(app.cycle_choice(app.KEY_POSITION, "BottomRight", -1), "BottomLeft")
        self.assertEqual(app.cycle_choice(app.KEY_STYLE, "Native", 1), "Custom")
        self.assertEqual(app.cycle_choice(app.KEY_FOCUS, "Play", 1), "Close")

    def test_customize_rows_hide_the_custom_only_rows_for_the_toast(self):
        self.assertEqual(
            app.customize_rows({app.KEY_STYLE: "Native"}), [app.KEY_STYLE]
        )
        custom = app.customize_rows(app.DEFAULT_DRAFT)
        self.assertEqual(custom[0], app.KEY_STYLE)
        self.assertEqual(len(custom), 6)

    def test_every_default_is_a_known_option(self):
        for key, options in app.CHOICE_KEYS.items():
            self.assertIn(app.DEFAULT_DRAFT[key], options)


class CountdownMathTests(unittest.TestCase):
    def test_seconds_left(self):
        self.assertEqual(app.seconds_left(1400, 1500), 100.0)
        self.assertEqual(app.seconds_left(1600, 1500), 0.0)
        self.assertEqual(app.seconds_left("x", 1500), 0.0)

    def test_fraction_left_is_clamped(self):
        self.assertEqual(app.window_fraction_left(1455, 1455, 1500), 1.0)
        self.assertAlmostEqual(app.window_fraction_left(1477.5, 1455, 1500), 0.5)
        self.assertEqual(app.window_fraction_left(1500, 1455, 1500), 0.0)
        self.assertEqual(app.window_fraction_left(1400, 1455, 1500), 1.0)
        self.assertEqual(app.window_fraction_left(1600, 1455, 1500), 0.0)
        self.assertEqual(app.window_fraction_left(10, 1500, 1500), 0.0)

    def test_the_segment_pitch_matches_the_skip_dialogs_segmented_bar(self):
        """The tiled textures are generated for that pitch, so the two must not drift apart."""
        import skip_dialog_appearance as skip_app

        self.assertEqual(app.SEGMENT_PITCH_PER_HEIGHT, skip_app.TILED_PITCH_PER_HEIGHT)
        for height in (10, 15, 16, 24):
            self.assertEqual(app.segment_pitch(height), skip_app.tiled_segment_pitch_px(height))

    def test_bar_fill_width_is_a_whole_number_of_segments(self):
        pitch = app.segment_pitch(10)
        self.assertEqual(pitch, 8)
        for fraction in (0.0, 0.1, 0.37, 0.5, 0.99, 1.0):
            width = app.bar_fill_width(fraction, 500, 10)
            self.assertEqual(width % pitch, 0, fraction)
            self.assertLessEqual(width, 500)
        self.assertEqual(app.bar_fill_width(1.0, 500, 10), 62 * pitch)
        self.assertEqual(app.bar_fill_width(0.5, 500, 10), 31 * pitch)

    def test_bar_fill_width_only_ever_shrinks_as_the_fraction_falls(self):
        widths = [app.bar_fill_width(f / 200.0, 500, 10) for f in range(200, -1, -1)]
        self.assertEqual(widths, sorted(widths, reverse=True))
        self.assertEqual(widths[-1], 0)

    def test_bar_fill_width_is_clamped(self):
        self.assertEqual(app.bar_fill_width(2.0, 500, 10), app.bar_fill_width(1.0, 500, 10))
        self.assertEqual(app.bar_fill_width(-1.0, 500, 10), 0)


class PopupSkinTests(unittest.TestCase):
    def path(self, res, name):
        return os.path.join(SKINS, res, name)

    def test_default_geometry_matches_the_layout_maths(self):
        lay = app.popup_layout(thumbnail=True, countdown=True, progress=True)
        x, y = app.popup_origin("BottomRight", lay.panel_w, lay.panel_h)
        c = _controls(self.path("720p", "NextEpisodeDialog.xml"))
        self.assertEqual((c[dlg_mod.ID_PANEL]["posx"], c[dlg_mod.ID_PANEL]["posy"]), (x, y))
        self.assertEqual(
            (c[dlg_mod.ID_BACKDROP]["width"], c[dlg_mod.ID_BACKDROP]["height"]),
            (lay.panel_w, lay.panel_h),
        )
        self.assertEqual(
            (c[dlg_mod.ID_THUMB]["left"], c[dlg_mod.ID_THUMB]["top"]), (app.PAD, app.PAD)
        )
        self.assertEqual(
            (c[dlg_mod.ID_HEADING]["left"], c[dlg_mod.ID_HEADING]["top"], c[dlg_mod.ID_HEADING]["width"]),
            (lay.text_x, lay.heading_y, lay.text_w),
        )
        self.assertEqual(c[dlg_mod.ID_EPISODE]["top"], lay.episode_y)
        self.assertEqual(c[dlg_mod.ID_COUNTDOWN]["top"], lay.countdown_y)
        self.assertEqual(c[dlg_mod.ID_BAR_FILL]["top"], lay.bar_y)
        self.assertEqual(c[dlg_mod.ID_BAR_FILL]["width"], lay.bar_w)
        for cid in (dlg_mod.ID_PLAY, dlg_mod.ID_PLATE_PLAY):
            self.assertEqual((c[cid]["left"], c[cid]["top"], c[cid]["width"]),
                             (app.PAD, lay.buttons_y, lay.button_w))
        for cid in (dlg_mod.ID_CLOSE, dlg_mod.ID_PLATE_CLOSE):
            self.assertEqual(
                (c[cid]["left"], c[cid]["top"], c[cid]["width"]),
                (app.PAD + lay.button_w + app.BUTTON_GAP, lay.buttons_y, lay.button_w),
            )

    def test_every_control_the_dialogs_use_exists_in_both_skins(self):
        want = {
            "NextEpisodeDialog.xml": {
                getattr(dlg_mod, n) for n in dir(dlg_mod) if n.startswith("ID_")
            },
            "NextEpisodeCustomize.xml": (
                set(cust.ROW_IDS.values())
                | set(cust.FOOTER_IDS)
                | {cust.ID_PANEL, cust.ID_BACKDROP, cust.ID_TITLE}
            ),
        }
        for res in ("720p", "1080i"):
            for name, ids in want.items():
                have = set(_controls(self.path(res, name)))
                self.assertEqual(sorted(ids - have), [], "%s/%s" % (res, name))

    def test_1080i_is_the_720p_layout_scaled_by_one_and_a_half(self):
        for name in ("NextEpisodeDialog.xml", "NextEpisodeCustomize.xml"):
            small = _controls(self.path("720p", name))
            big = _controls(self.path("1080i", name))
            self.assertEqual(set(small), set(big))
            for cid, values in small.items():
                for tag, number in values.items():
                    self.assertLessEqual(abs(big[cid][tag] - number * 1.5), 1.0, (name, cid, tag))

    def test_probe_widths_pick_the_right_skin_folder(self):
        for name, probe in (
            ("NextEpisodeDialog.xml", skin_res.NEXT_EPISODE_PROBE_ID),
            ("NextEpisodeCustomize.xml", skin_res.NEXT_EPISODE_CUSTOMIZE_PROBE_ID),
        ):
            self.assertEqual(skin_res.probe_control_ids_for_xml(name), (probe,))
            small = _controls(self.path("720p", name))[probe]["width"]
            big = _controls(self.path("1080i", name))[probe]["width"]
            self.assertEqual(skin_res.infer_skin_resolution_from_widths([small]), "720p", name)
            self.assertEqual(skin_res.infer_skin_resolution_from_widths([big]), "1080i", name)

    def test_the_new_probe_widths_do_not_change_the_old_ones(self):
        infer = skin_res.infer_skin_resolution_from_widths
        for width, res in ((430, "720p"), (645, "1080i"), (120, "720p"), (180, "1080i"),
                           (1140, "720p"), (1710, "1080i"), (960, "720p"), (1440, "1080i")):
            self.assertEqual(infer([width]), res, width)

    def test_the_popup_is_drawn_above_the_customize_screen_that_previews_it(self):
        """Otherwise the Customize dim layer covers the preview and washes it out."""
        def zorder(res, name):
            with open(self.path(res, name), encoding="utf-8") as fh:
                return int(re.search(r"<zorder>(\d+)</zorder>", fh.read()).group(1))

        for res in ("720p", "1080i"):
            self.assertGreater(
                zorder(res, "NextEpisodeDialog.xml"), zorder(res, "NextEpisodeCustomize.xml"), res
            )

    def test_the_bar_fill_is_a_cropped_tiled_image(self):
        """A stretched image is squeezed as it shrinks; a left-aligned crop of a tiled one is not."""
        for res in ("720p", "1080i"):
            root = ET.parse(self.path(res, "NextEpisodeDialog.xml")).getroot()
            fill = [c for c in root.iter("control") if c.get("id") == str(dlg_mod.ID_BAR_FILL)][0]
            self.assertEqual(fill.get("type"), "image", res)
            aspect = fill.find("aspectratio")
            self.assertEqual((aspect.text, aspect.get("align")), ("scale", "left"), res)
            height = int(fill.findtext("height"))
            texture = fill.findtext("texture")
            self.assertEqual(texture, "progress_tiled_segmented_teal_h%d.png" % height, res)
            self.assertTrue(
                os.path.isfile(os.path.join(SKINS, "media", texture)), "%s: %s" % (res, texture)
            )

    def test_the_customize_skin_leaves_focus_movement_to_python(self):
        """Native onup/ondown links as well as the Python handler would move focus twice per key."""
        for res in ("720p", "1080i"):
            with open(self.path(res, "NextEpisodeCustomize.xml"), encoding="utf-8") as fh:
                text = fh.read()
            self.assertIsNone(re.search(r"<on(up|down|left|right)>", text), res)

    def test_text_colour_and_hidden_rows_use_properties_only(self):
        with open(self.path("720p", "NextEpisodeDialog.xml"), encoding="utf-8") as fh:
            text = fh.read()
        for prop in ("next_ep_heading", "next_ep_label", "next_ep_countdown", "next_ep_thumb",
                     "next_ep_has_thumb", "skip_dialog_text_color", "skippy_dialog_ready"):
            self.assertIn("Window.Property(%s)" % prop, text)


class PopupSettingsTests(unittest.TestCase):
    def settings(self):
        tree = ET.parse(os.path.join(ROOT, "resources", "settings.xml"))
        for cat in tree.getroot().iter("category"):
            if cat.get("id") == "next_episode":
                return {s.get("id"): s for s in cat.iter("setting")}
        self.fail("category missing")

    def test_defaults_match_the_draft_defaults(self):
        found = self.settings()
        for key, default in app.DEFAULT_DRAFT.items():
            stored = found[key].findtext("default")
            want = ("true" if default else "false") if key in app.BOOL_KEYS else default
            self.assertEqual(stored, want, key)

    def test_options_match_the_choice_lists(self):
        found = self.settings()
        for key, options in app.CHOICE_KEYS.items():
            stored = [o.text for o in found[key].iter("option")]
            self.assertEqual(stored, list(options), key)

    def test_the_popup_look_only_shows_for_the_custom_style(self):
        found = self.settings()
        look = (app.KEY_POSITION, app.KEY_THUMBNAIL, app.KEY_COUNTDOWN, app.KEY_PROGRESS, app.KEY_FOCUS)
        for key in look:
            deps = {(d.get("setting"), d.text) for d in found[key].iter("dependency")}
            self.assertIn((app.KEY_STYLE, "Custom"), deps, key)
        for key in (app.KEY_STYLE, "settings_action_customize_next_episode_popup"):
            deps = {(d.get("setting"), d.text) for d in found[key].iter("dependency")}
            self.assertNotIn((app.KEY_STYLE, "Custom"), deps, key)

    def test_the_customize_button_runs_the_script_command(self):
        action = self.settings()["settings_action_customize_next_episode_popup"]
        self.assertEqual(
            action.find("control").findtext("data"),
            "RunScript(service.skippy,customize_next_episode_popup)",
        )
        with open(os.path.join(ROOT, "skippy_runscript_entry.py"), encoding="utf-8") as fh:
            self.assertIn('"customize_next_episode_popup"', fh.read())

    def test_every_new_runtime_string_has_an_english_text(self):
        with open(
            os.path.join(ROOT, "resources", "language", "resource.language.en_gb", "strings.po"),
            encoding="utf-8",
        ) as fh:
            ids = set(re.findall(r'msgctxt "#(\d+)"', fh.read()))
        used = set()
        for name in ("next_episode_dialog.py", "next_episode_customize_ui.py"):
            with open(os.path.join(ROOT, name), encoding="utf-8") as fh:
                used.update(re.findall(r"get_localized\(\s*\w+,\s*(\d+)", fh.read()))
        with open(os.path.join(ROOT, "next_episode_customize_ui.py"), encoding="utf-8") as fh:
            used.update(re.findall(r"\(\s*(47\d{3}),", fh.read()))
        self.assertTrue(used)
        self.assertEqual(sorted(i for i in used if i not in ids), [])


class ThumbLookupTests(unittest.TestCase):
    def test_pick_thumb_prefers_the_episode_picture(self):
        art = {"thumb": " a.jpg ", "fanart": "b.jpg", "poster": "p.jpg"}
        self.assertEqual(lookup.pick_thumb(art), "a.jpg")

    def test_pick_thumb_falls_back_to_wide_art_only(self):
        self.assertEqual(lookup.pick_thumb({"fanart": "b.jpg"}), "b.jpg")
        self.assertEqual(lookup.pick_thumb({"tvshow.fanart": "s.jpg"}), "s.jpg")
        self.assertEqual(lookup.pick_thumb({"poster": "p.jpg", "tvshow.poster": "q.jpg"}), "")

    def test_pick_thumb_ignores_junk(self):
        for art in (None, [], "x", {}, {"thumb": ""}, {"thumb": 3}, {"thumb": "  "}):
            self.assertEqual(lookup.pick_thumb(art), "")

    def test_art_is_requested_and_returned_for_library_and_playlist(self):
        self.assertIn("art", lookup._DETAIL_PROPERTIES)
        self.assertIn("art", lookup._PLAYLIST_PROPERTIES)

        def rpc(method, params=None, log_errors=True):
            if method == "Player.GetActivePlayers":
                return {"result": [{"playerid": 1, "type": "video"}]}
            if method == "Player.GetProperties":
                return {"result": {"playlistid": 1, "position": 0}}
            if method == "Playlist.GetItems":
                return {"result": {"items": [{"title": "Q", "art": {"thumb": "q.jpg"}}]}}
            return {}

        with patch.object(lookup, "jsonrpc", rpc):
            self.assertEqual(lookup.find_playlist_successor()["thumb"], "q.jpg")


class PromptDispatchTests(unittest.TestCase):
    def run_prompt(self, style, dialog=None):
        calls = []
        toast = MagicMock(return_value="toast")
        dialog = dialog or MagicMock(return_value="dialog")
        text = lambda _addon, key, default="": style if key == app.KEY_STYLE else default
        with patch.object(prompt, "addon_get_setting_text", text), patch.object(
            prompt, "show_next_episode_toast", toast
        ), patch.object(prompt, "load_popup_draft", lambda a: {"d": 1}), patch.object(
            prompt, "log_error", lambda m: calls.append(m)
        ), patch.dict(
            "sys.modules",
            {"next_episode_dialog": types.SimpleNamespace(show_next_episode_dialog=dialog)},
        ):
            answer = prompt.show_next_episode_prompt("addon", "player", {"t": 1}, 10.0, 60.0)
        return answer, toast, dialog, calls

    def test_custom_style_shows_the_dialog_with_the_draft(self):
        answer, toast, dialog, calls = self.run_prompt("Custom")
        self.assertEqual(answer, "dialog")
        toast.assert_not_called()
        dialog.assert_called_once_with(
            "addon", "player", {"t": 1}, 10.0, 60.0, draft={"d": 1}, still_watching=False
        )
        self.assertEqual(calls, [])

    def test_native_style_shows_the_toast(self):
        answer, toast, dialog, _ = self.run_prompt("Native")
        self.assertEqual(answer, "toast")
        dialog.assert_not_called()
        toast.assert_called_once_with(
            "addon", "player", {"t": 1}, 10.0, 60.0, still_watching=False
        )

    def test_an_unset_style_means_custom(self):
        answer, *_ = self.run_prompt("")
        self.assertEqual(answer, "dialog")

    def test_a_failing_dialog_falls_back_to_the_toast_and_is_logged(self):
        answer, toast, _dialog, calls = self.run_prompt("Custom", MagicMock(side_effect=RuntimeError("x")))
        self.assertEqual(answer, "toast")
        toast.assert_called_once()
        self.assertEqual(len(calls), 1)
        self.assertIn("RuntimeError", calls[0])


class CustomizeHelperTests(unittest.TestCase):
    def test_footer_sits_under_the_visible_rows(self):
        for n in (1, 6):
            tops, footer, height = cust.row_layout(list(range(n)))
            self.assertEqual(len(tops), n)
            self.assertGreaterEqual(footer, tops[-1] + 40)
            self.assertGreater(height, footer + 40)

    def test_full_layout_matches_the_skin_defaults(self):
        c = _controls(os.path.join(SKINS, "720p", "NextEpisodeCustomize.xml"))
        rows = app.customize_rows(app.DEFAULT_DRAFT)
        tops, footer, height = cust.row_layout(rows)
        for key, top in zip(rows, tops):
            self.assertEqual(c[cust.ROW_IDS[key]]["top"], top, key)
        for cid in cust.FOOTER_IDS:
            self.assertEqual(c[cid]["top"], footer)
        self.assertEqual(c[cust.ID_BACKDROP]["height"], height)
        self.assertEqual(c[cust.ID_BACKDROP]["width"], cust._PANEL_W)
        self.assertEqual(c[cust.ID_PANEL]["posy"], (app.BASE_SCREEN_H - height) // 2)

    def test_focus_order_follows_the_visible_rows(self):
        ids = cust.nav_ids(app.DEFAULT_DRAFT)
        self.assertEqual(ids[:-1], [cust.ROW_IDS[k] for k in app.customize_rows(app.DEFAULT_DRAFT)])
        self.assertEqual(ids[-1], cust.ID_PREVIEW)
        self.assertEqual(cust.nav_ids({app.KEY_STYLE: "Native"}), [cust.ROW_IDS[app.KEY_STYLE], cust.ID_PREVIEW])

    def test_nudge_flips_toggles_and_cycles_choices(self):
        draft = dict(app.DEFAULT_DRAFT)
        cust.nudge(draft, app.KEY_THUMBNAIL, 1)
        self.assertFalse(draft[app.KEY_THUMBNAIL])
        cust.nudge(draft, app.KEY_THUMBNAIL, -1)
        self.assertTrue(draft[app.KEY_THUMBNAIL])
        cust.nudge(draft, app.KEY_POSITION, 1)
        self.assertEqual(draft[app.KEY_POSITION], app.cycle_choice(app.KEY_POSITION, "BottomRight", 1))
        self.assertNotEqual(draft[app.KEY_POSITION], "BottomRight")
        cust.nudge(draft, app.KEY_STYLE, 1)
        self.assertEqual(draft[app.KEY_STYLE], "Native")

    def test_only_changed_settings_are_saved(self):
        original = dict(app.DEFAULT_DRAFT)
        draft = dict(original, **{app.KEY_COUNTDOWN: False, app.KEY_POSITION: "TopLeft"})
        self.assertEqual(
            cust.changed_payload(draft, original),
            {app.KEY_COUNTDOWN: "false", app.KEY_POSITION: "TopLeft"},
        )
        self.assertEqual(cust.changed_payload(original, original), {})

    def test_value_text(self):
        with patch.object(cust, "get_localized", lambda a, i, d, *r: d):
            self.assertEqual(cust.value_text(None, app.DEFAULT_DRAFT, app.KEY_THUMBNAIL), "Yes")
            self.assertEqual(cust.value_text(None, {app.KEY_COUNTDOWN: False}, app.KEY_COUNTDOWN), "No")
            self.assertEqual(cust.value_text(None, {app.KEY_STYLE: "Native"}, app.KEY_STYLE), "Native toast")
            self.assertEqual(cust.value_text(None, {app.KEY_POSITION: "TopLeft"}, app.KEY_POSITION), "Top Left")
            self.assertEqual(cust.value_text(None, {app.KEY_FOCUS: "Play"}, app.KEY_FOCUS), "Play now")

    def test_save_writes_only_the_changes_and_closes(self):
        modal = cust.NextEpisodeCustomize.__new__(cust.NextEpisodeCustomize)
        modal.addon = MagicMock()
        modal._original = dict(app.DEFAULT_DRAFT)
        modal._draft = dict(app.DEFAULT_DRAFT, **{app.KEY_PROGRESS: False})
        modal._saved = False
        modal.close = MagicMock()
        modal._save_and_close()
        modal.addon.setSetting.assert_called_once_with(app.KEY_PROGRESS, "false")
        modal.close.assert_called_once()
        self.assertTrue(modal._saved)

    def test_cancel_writes_nothing(self):
        modal = cust.NextEpisodeCustomize.__new__(cust.NextEpisodeCustomize)
        modal.addon = MagicMock()
        modal._saved = False
        modal.close = MagicMock()
        modal.onClick(cust.ID_CANCEL)
        modal.addon.setSetting.assert_not_called()
        modal.close.assert_called_once()
        self.assertFalse(modal._saved)


class _Player:
    def __init__(self, head=1470.0, playing=True):
        self.head, self.playing = head, playing

    def getTime(self):
        return self.head

    def isPlaying(self):
        return self.playing


def _dialog(player=None, **kw):
    dialog = dlg_mod.NextEpisodeDialog.__new__(dlg_mod.NextEpisodeDialog)
    dialog.player = player or _Player()
    dialog.window_start = 1455.0
    dialog.total = 1500.0
    dialog.preview = False
    dialog.result = None
    dialog._closing = False
    dialog._stop = threading.Event()
    dialog._layout = None
    dialog.close = MagicMock()
    for key, value in kw.items():
        setattr(dialog, key, value)
    return dialog


class DialogBehaviourTests(unittest.TestCase):
    def test_play_now_answers_true(self):
        dialog = _dialog()
        dialog.onClick(dlg_mod.ID_PLAY)
        self.assertIs(dialog.result, True)
        dialog.close.assert_called_once()

    def test_close_answers_false(self):
        dialog = _dialog()
        dialog.onClick(dlg_mod.ID_CLOSE)
        self.assertIs(dialog.result, False)

    def test_back_answers_false_and_other_actions_do_nothing(self):
        for action_id in (10, 92, 216):
            dialog = _dialog()
            dialog.onAction(types.SimpleNamespace(getId=lambda a=action_id: a))
            self.assertIs(dialog.result, False, action_id)
        dialog = _dialog()
        dialog.onAction(types.SimpleNamespace(getId=lambda: 1))
        self.assertIsNone(dialog.result)
        dialog.close.assert_not_called()

    def test_the_first_answer_wins(self):
        dialog = _dialog()
        dialog.onClick(dlg_mod.ID_PLAY)
        dialog.onClick(dlg_mod.ID_CLOSE)
        self.assertIs(dialog.result, True)
        self.assertEqual(dialog.close.call_count, 1)

    def test_unknown_control_is_ignored(self):
        dialog = _dialog()
        dialog.onClick(9999)
        dialog.onClick("x")
        self.assertIsNone(dialog.result)

    def watch(self, player, ticks=3):
        dialog = _dialog(player)
        seen = []

        def update(head):
            seen.append(head)
            if len(seen) >= ticks:
                dialog._stop.set()

        dialog._update_countdown = update
        with patch.object(dlg_mod, "_TICK_S", 0.0):
            dialog._watch()
        return dialog, seen

    def test_the_watcher_keeps_updating_while_the_prompt_applies(self):
        dialog, seen = self.watch(_Player(1470.0))
        self.assertEqual(seen, [1470.0] * 3)
        self.assertFalse(dialog._closing)

    def test_the_watcher_closes_when_playback_stops(self):
        dialog, seen = self.watch(_Player(1470.0, playing=False))
        self.assertIsNone(dialog.result)
        self.assertTrue(dialog._closing)
        dialog.close.assert_called_once()
        self.assertEqual(seen, [])

    def test_the_watcher_closes_at_the_end_of_the_file(self):
        dialog, _ = self.watch(_Player(1499.5))
        self.assertTrue(dialog._closing)
        self.assertIsNone(dialog.result)

    def test_the_watcher_closes_when_the_playhead_goes_back_before_the_window(self):
        dialog, _ = self.watch(_Player(1400.0))
        self.assertTrue(dialog._closing)
        dialog.close.assert_called_once()

    def test_the_countdown_text_and_bar_follow_the_playhead(self):
        dialog = _dialog()
        dialog._layout = app.popup_layout(thumbnail=False, countdown=True, progress=True)
        dialog.addon = None
        props = {}
        dialog.setProperty = lambda k, v: props.__setitem__(k, v)
        fill = MagicMock()
        dialog._ctrl = lambda cid: fill if cid == dlg_mod.ID_BAR_FILL else None
        dialog._sc = lambda v: v
        dialog._update_countdown(1477.5)
        self.assertIn("00:22", props["next_ep_countdown"])
        # Half of the 500 px bar is 250 px: 31 whole segments of 8 px (pitch of a 10 px bar).
        fill.setWidth.assert_called_once_with(248)
        fill.setPercent.assert_not_called()
        dialog._update_countdown(1477.5)
        fill.setWidth.assert_called_once_with(248)
        dialog._update_countdown(1470.0)
        self.assertEqual(fill.setWidth.call_count, 2)

    def test_hidden_countdown_and_bar_are_not_touched(self):
        dialog = _dialog()
        dialog._layout = app.popup_layout(thumbnail=False, countdown=False, progress=False)
        dialog.setProperty = MagicMock()
        dialog._ctrl = MagicMock()
        dialog._update_countdown(1470.0)
        dialog.setProperty.assert_not_called()
        dialog._ctrl.assert_not_called()

    def test_preview_head_loops_inside_the_window(self):
        dialog = _dialog(preview=True, window_start=0.0, total=45.0)
        for now in (0.0, 10.0, 44.9, 45.0, 90.5):
            dialog._started = 100.0
            with patch.object(dlg_mod.time, "monotonic", lambda n=now: 100.0 + n):
                head = dialog._head()
            self.assertGreaterEqual(head, 0.0)
            self.assertLess(head, 45.0)

    def test_show_dialog_returns_the_recorded_answer(self):
        created = {}

        class Fake(dlg_mod.NextEpisodeDialog):
            def __init__(self, *args, **kwargs):
                created["args"], created["kwargs"] = args, kwargs
                self.result = True
                self._stop = threading.Event()

            def doModal(self):
                created["modal"] = True

        addon = MagicMock()
        addon.getAddonInfo.return_value = "/addon"
        with patch.object(dlg_mod, "NextEpisodeDialog", Fake):
            answer = dlg_mod.show_next_episode_dialog(
                addon, "player", {"title": "x"}, 1.0, 2.0, draft={"d": 1}
            )
        self.assertIs(answer, True)
        self.assertTrue(created["modal"])
        self.assertEqual(created["args"], ("NextEpisodeDialog.xml", "/addon", "default"))
        self.assertEqual(created["kwargs"]["draft"], {"d": 1})
        self.assertFalse(created["kwargs"]["preview"])

    def test_mock_episode_has_a_label(self):
        addon = MagicMock()
        addon.getAddonInfo.return_value = ROOT
        with patch.object(dlg_mod, "get_localized", lambda a, i, d, *r: d):
            episode = dlg_mod.mock_episode(addon)
        self.assertEqual((episode["season"], episode["episode"]), (1, 2))
        self.assertEqual(episode["title"], "Episode title")
        self.assertTrue(episode["thumb"].endswith("fanart.png"))


if __name__ == "__main__":
    unittest.main()
