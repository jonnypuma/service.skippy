# -*- coding: utf-8 -*-
"""The Normal / Large size of the next episode popup."""

import os
import re
import sys
import unittest
import xml.etree.ElementTree as ET

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import next_episode_appearance as app
import next_episode_customize_ui as cust
import next_episode_view as view
from tests.test_next_episode_look import _dialog
from tests.test_next_episode_mock import SKINS, _Addon, _elements, _modal, _num

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import gen_skin_1080i as gen  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
POSITIONS = ("BottomRight", "TopRight", "TopLeft", "BottomLeft")


class DraftTests(unittest.TestCase):
    def test_the_size_is_normal_unless_chosen(self):
        self.assertEqual(app.DEFAULT_DRAFT[app.KEY_SIZE], "Normal")
        self.assertEqual(app.KEY_SIZE, "next_episode_popup_size")
        self.assertEqual(app.SIZES, ("Normal", "Large"))
        self.assertEqual(app.CHOICE_KEYS[app.KEY_SIZE], app.SIZES)

    def test_a_stored_size_is_read_loosely_and_garbage_means_normal(self):
        for text, want in (("Large", "Large"), ("large", "Large"), (" LARGE ", "Large"), ("Normal", "Normal"),
                           ("", "Normal"), ("Huge", "Normal"), (None, "Normal")):
            self.assertEqual(app.normalize_choice(app.KEY_SIZE, text), want, text)

    def test_the_size_is_loaded_and_saved_like_the_other_choices(self):
        draft = app.draft_from_reader(
            lambda key, default: "Large" if key == app.KEY_SIZE else default, lambda key, default: default
        )
        self.assertEqual(draft[app.KEY_SIZE], "Large")
        self.assertEqual(app.draft_setting_payload(draft)[app.KEY_SIZE], "Large")
        self.assertEqual(app.draft_setting_payload({})[app.KEY_SIZE], "Normal")

    def test_save_stores_the_size_only_when_it_changed(self):
        original = dict(app.DEFAULT_DRAFT)
        self.assertEqual(cust.changed_payload(original, original), {})
        changed = dict(original, **{app.KEY_SIZE: "Large"})
        self.assertEqual(cust.changed_payload(changed, original), {app.KEY_SIZE: "Large"})

    def test_cycling_goes_round_in_both_directions(self):
        self.assertEqual(app.cycle_choice(app.KEY_SIZE, "Normal", 1), "Large")
        self.assertEqual(app.cycle_choice(app.KEY_SIZE, "Large", 1), "Normal")
        self.assertEqual(app.cycle_choice(app.KEY_SIZE, "Normal", -1), "Large")

    def test_the_row_sits_right_after_the_position_and_only_for_the_custom_style(self):
        rows = app.customize_rows(app.DEFAULT_DRAFT)
        self.assertEqual(rows.index(app.KEY_SIZE), rows.index(app.KEY_POSITION) + 1)
        self.assertNotIn(app.KEY_SIZE, app.customize_rows({app.KEY_STYLE: "Native"}))


class ZoomCornerTests(unittest.TestCase):
    def test_a_normal_popup_is_not_zoomed(self):
        for position in POSITIONS:
            self.assertEqual(app.zoom_corner({app.KEY_SIZE: "Normal", app.KEY_POSITION: position}), "", position)
        self.assertEqual(app.zoom_corner(app.DEFAULT_DRAFT), "")
        self.assertEqual(app.zoom_corner({}), "")

    def test_a_large_popup_grows_from_the_corner_it_sits_in(self):
        for position in POSITIONS:
            self.assertEqual(app.zoom_corner({app.KEY_SIZE: "Large", app.KEY_POSITION: position}), position)

    def test_a_size_and_a_position_can_be_given_apart(self):
        self.assertEqual(app.zoom_corner({app.KEY_SIZE: "Large", app.KEY_POSITION: "TopLeft"}, "TopRight"), "TopRight")
        self.assertEqual(app.zoom_corner("Large", "TopLeft"), "TopLeft")
        self.assertEqual(app.zoom_corner("Normal", "TopLeft"), "")
        self.assertEqual(app.zoom_corner("Large"), "BottomRight")

    def test_odd_values_fall_back_to_the_defaults(self):
        self.assertEqual(app.zoom_corner({app.KEY_SIZE: "Large", app.KEY_POSITION: "Middle"}), "BottomRight")
        self.assertEqual(app.zoom_corner({app.KEY_SIZE: "Huge", app.KEY_POSITION: "TopLeft"}), "")
        self.assertEqual(app.zoom_corner({app.KEY_SIZE: "large", app.KEY_POSITION: "top left"}), "TopLeft")

    def test_the_zoom_keeps_the_corner_of_the_popup_in_place(self):
        self.assertEqual(app.zoom_center("BottomRight"), (1260, 700))
        self.assertEqual(app.zoom_center("TopRight"), (1260, 20))
        self.assertEqual(app.zoom_center("TopLeft"), (20, 20))
        self.assertEqual(app.zoom_center("BottomLeft"), (20, 700))
        self.assertEqual(app.zoom_center("Middle"), (1260, 700))
        self.assertEqual(app.zoom_center("TopLeft", 672, 504, 20, 20), (20, 20))
        self.assertEqual(app.zoom_center("BottomRight", 672, 504, 20, 20), (652, 484))

    def test_the_kept_corner_is_the_corner_of_the_unzoomed_popup(self):
        layout = app.popup_layout(thumbnail=True, countdown=True, progress=True)
        for position in POSITIONS:
            x, y = app.popup_origin(position, layout.panel_w, layout.panel_h)
            cx, cy = app.zoom_center(position)
            corner_x = x + layout.panel_w if position.endswith("Right") else x
            corner_y = y + layout.panel_h if position.startswith("Bottom") else y
            self.assertEqual((corner_x, corner_y), (cx, cy), position)


def _zoomed(rect, center, percent):
    (x, y, w, h), (cx, cy), f = rect, center, percent / 100.0
    return (cx + (x - cx) * f, cy + (y - cy) * f, w * f, h * f)


class FitTests(unittest.TestCase):
    """A large popup still fits the screen (and the mockup's stage) in every corner."""

    def layouts(self):
        for thumb in (True, False):
            for countdown in (True, False):
                for progress in (True, False):
                    yield app.popup_layout(thumbnail=thumb, countdown=countdown, progress=progress)

    def test_the_zoom_percent_is_a_real_enlargement(self):
        self.assertGreater(app.LARGE_ZOOM_PERCENT, 100)
        self.assertLessEqual(app.LARGE_ZOOM_PERCENT, 150)

    def check(self, screen_w, screen_h, margin):
        for layout in self.layouts():
            for position in POSITIONS:
                x, y = app.popup_origin(position, layout.panel_w, layout.panel_h, screen_w, screen_h, margin, margin)
                center = app.zoom_center(position, screen_w, screen_h, margin, margin)
                zx, zy, zw, zh = _zoomed((x, y, layout.panel_w, layout.panel_h), center, app.LARGE_ZOOM_PERCENT)
                self.assertGreater(zw, layout.panel_w)
                self.assertGreaterEqual(zx, 0, (position, layout))
                self.assertGreaterEqual(zy, 0, (position, layout))
                self.assertLessEqual(zx + zw, screen_w, (position, layout))
                self.assertLessEqual(zy + zh, screen_h, (position, layout))
                # the margin to the screen edge of the corner it grows from is unchanged
                if position.endswith("Right"):
                    self.assertAlmostEqual(screen_w - (zx + zw), margin)
                else:
                    self.assertAlmostEqual(zx, margin)
                if position.startswith("Bottom"):
                    self.assertAlmostEqual(screen_h - (zy + zh), margin)
                else:
                    self.assertAlmostEqual(zy, margin)

    def test_a_large_popup_fits_the_screen_in_every_corner(self):
        self.check(app.BASE_SCREEN_W, app.BASE_SCREEN_H, app.SCREEN_MARGIN_X)

    def test_a_large_popup_fits_the_mockup_stage_in_every_corner(self):
        self.check(cust._STAGE_W, cust._STAGE_H, cust._MOCK_MARGIN)


def _wrapper(res, name, wrapper_id):
    root, els = _elements(os.path.join(SKINS, res, name))
    return root, els, els[wrapper_id]


class SkinTests(unittest.TestCase):
    CASES = (
        ("NextEpisodeDialog.xml", view.popup_ids().zoom, view.popup_ids().panel, (1280, 720), app.SCREEN_MARGIN_X),
        ("NextEpisodeCustomize.xml", cust.MOCK_IDS.zoom, cust.MOCK_IDS.panel, (cust._STAGE_W, cust._STAGE_H),
         cust._MOCK_MARGIN),
    )

    def test_the_ids(self):
        self.assertEqual(view.popup_ids().zoom, 5099)
        self.assertEqual(cust.MOCK_IDS.zoom, 5099 + view.MOCK_ID_OFFSET)

    def test_the_size_group_covers_the_screen_or_the_stage_and_holds_the_popup(self):
        for res, factor in (("720p", 1), ("1080i", 1.5)):
            for name, zoom_id, panel_id, (w, h), _margin in self.CASES:
                _root, els, wrapper = _wrapper(res, name, zoom_id)
                self.assertEqual(wrapper.get("type"), "group", (res, name))
                self.assertEqual((_num(wrapper, "posx"), _num(wrapper, "posy")), (0, 0), (res, name))
                self.assertEqual(
                    (_num(wrapper, "width"), _num(wrapper, "height")),
                    (int(w * factor + 0.5), int(h * factor + 0.5)),
                    (res, name),
                )
                inside = {int(c.get("id")) for c in wrapper.iter("control") if c.get("id")}
                self.assertIn(panel_id, inside, (res, name))

    def test_the_wrapper_is_a_direct_child_of_the_window_or_the_stage(self):
        for res in ("720p", "1080i"):
            root = ET.parse(os.path.join(SKINS, res, "NextEpisodeDialog.xml")).getroot()
            self.assertIn(view.popup_ids().zoom, [int(c.get("id")) for c in root.find("controls")])
            root = ET.parse(os.path.join(SKINS, res, "NextEpisodeCustomize.xml")).getroot()
            _r, els = _elements(os.path.join(SKINS, res, "NextEpisodeCustomize.xml"))
            stage = els[cust.ID_STAGE]
            self.assertIn(cust.MOCK_IDS.zoom, [int(c.get("id")) for c in stage.findall("control")])

    def test_the_toast_mockup_is_not_zoomed(self):
        _root, els, wrapper = _wrapper("720p", "NextEpisodeCustomize.xml", cust.MOCK_IDS.zoom)
        inside = {int(c.get("id")) for c in wrapper.iter("control") if c.get("id")}
        toast = {cid for cid in els if 7100 <= cid <= 7199}
        self.assertTrue(toast)
        self.assertEqual(inside & toast, set())

    def test_one_zoom_per_corner_with_the_percent_and_the_corner_as_centre(self):
        for res, factor in (("720p", 1), ("1080i", 1.5)):
            for name, zoom_id, _panel, (w, h), margin in self.CASES:
                _root, _els, wrapper = _wrapper(res, name, zoom_id)
                seen = {}
                for animation in wrapper.findall("animation"):
                    self.assertEqual(animation.get("type"), "Conditional", (res, name))
                    match = re.fullmatch(
                        r"String\.IsEqual\(Window\.Property\(next_ep_zoom\),(\w+)\)", animation.get("condition", "")
                    )
                    self.assertIsNotNone(match, (res, name, animation.get("condition")))
                    effects = animation.findall("effect")
                    self.assertEqual(len(effects), 1)
                    effect = effects[0]
                    self.assertEqual(effect.get("type"), "zoom")
                    self.assertEqual(effect.get("start"), str(app.LARGE_ZOOM_PERCENT))
                    self.assertEqual(effect.get("end"), str(app.LARGE_ZOOM_PERCENT))
                    self.assertEqual(effect.get("time"), "0")
                    seen[match.group(1)] = effect.get("center")
                self.assertEqual(sorted(seen), sorted(POSITIONS), (res, name))
                for position, center in seen.items():
                    cx, cy = app.zoom_center(position, w, h, margin, margin)
                    want = "%d,%d" % (int(cx * factor + 0.5), int(cy * factor + 0.5))
                    self.assertEqual(center, want, (res, name, position))

    def test_the_dialog_sets_the_property_the_skin_listens_to(self):
        text = open(os.path.join(ROOT, "next_episode_dialog.py"), encoding="utf-8").read()
        self.assertIn('"next_ep_zoom"', text)
        for name in ("NextEpisodeDialog.xml", "NextEpisodeCustomize.xml"):
            self.assertIn("Window.Property(next_ep_zoom)", open(os.path.join(SKINS, "720p", name), encoding="utf-8").read())

    def test_the_generator_scales_the_centre_but_not_the_percent(self):
        out = gen.convert('<effect type="zoom" start="125" end="125" time="0" center="1260,700" />')
        self.assertEqual(out, '<effect type="zoom" start="125" end="125" time="0" center="1890,1050" />')
        self.assertEqual(
            gen.convert('<effect type="fade" start="0" end="100" time="300" center="5,5" />'),
            '<effect type="fade" start="0" end="100" time="300" center="5,5" />',
        )
        self.assertEqual(
            gen.convert('<effect type="zoom" start="80" end="100" center="auto" time="200" />'),
            '<effect type="zoom" start="80" end="100" center="auto" time="200" />',
        )
        self.assertEqual(
            gen.convert('<effect type="slide" start="0,-150" end="0,0" time="200" />'),
            '<effect type="slide" start="0,-225" end="0,0" time="200" />',
        )


class DialogTests(unittest.TestCase):
    def apply(self, **draft):
        dialog = _dialog(_Addon())
        dialog.draft.update(draft)
        dialog._place = lambda *a, **k: None
        dialog._show = lambda *a, **k: None
        dialog._apply_layout(app.popup_layout(thumbnail=True, countdown=True, progress=True))
        return dialog.props

    def test_a_normal_popup_has_no_zoom(self):
        self.assertEqual(self.apply()["next_ep_zoom"], "")
        self.assertEqual(self.apply(**{app.KEY_SIZE: "Normal", app.KEY_POSITION: "TopLeft"})["next_ep_zoom"], "")

    def test_a_large_popup_names_its_corner(self):
        for position in POSITIONS:
            props = self.apply(**{app.KEY_SIZE: "Large", app.KEY_POSITION: position})
            self.assertEqual(props["next_ep_zoom"], position)

    def test_the_layout_is_the_same_for_both_sizes(self):
        placed = {}
        for size in ("Normal", "Large"):
            dialog = _dialog(_Addon())
            dialog.draft[app.KEY_SIZE] = size
            calls = []
            dialog._place = lambda cid, x, y, w=None, h=None, calls=calls: calls.append((cid, x, y, w, h))
            dialog._show = lambda *a, **k: None
            dialog._apply_layout(app.popup_layout(thumbnail=True, countdown=True, progress=True))
            placed[size] = calls
        self.assertEqual(placed["Normal"], placed["Large"])


class CustomizeTests(unittest.TestCase):
    def test_the_row_exists_with_its_label_and_value_texts(self):
        self.assertEqual(cust.ROW_IDS[app.KEY_SIZE], 6036)
        self.assertEqual(cust.ROW_LABEL_IDS[app.KEY_SIZE], (47151, "Popup size"))
        addon = _Addon()
        self.assertEqual(cust.value_text(addon, {app.KEY_SIZE: "Normal"}, app.KEY_SIZE), "Normal")
        self.assertEqual(cust.value_text(addon, {app.KEY_SIZE: "Large"}, app.KEY_SIZE), "Large")

    def test_the_value_texts_come_from_the_translations(self):
        class Addon(_Addon):
            def getLocalizedString(self, string_id):
                return "#%d" % string_id

        addon = Addon()
        self.assertEqual(cust.value_text(addon, {app.KEY_SIZE: "Normal"}, app.KEY_SIZE), "#47153")
        self.assertEqual(cust.value_text(addon, {app.KEY_SIZE: "Large"}, app.KEY_SIZE), "#47154")

    def test_the_row_is_in_the_navigation_after_the_position(self):
        ids = cust.nav_ids(app.DEFAULT_DRAFT)
        self.assertEqual(ids.index(cust.ROW_IDS[app.KEY_SIZE]), ids.index(cust.ROW_IDS[app.KEY_POSITION]) + 1)
        self.assertNotIn(cust.ROW_IDS[app.KEY_SIZE], cust.nav_ids({app.KEY_STYLE: "Native"}))

    def test_nudging_the_row_switches_the_size(self):
        draft = dict(app.DEFAULT_DRAFT)
        cust.nudge(draft, app.KEY_SIZE, 1)
        self.assertEqual(draft[app.KEY_SIZE], "Large")
        cust.nudge(draft, app.KEY_SIZE, 1)
        self.assertEqual(draft[app.KEY_SIZE], "Normal")

    def test_the_mockup_follows_the_size_and_the_corner(self):
        modal = _modal({app.KEY_SIZE: "Large", app.KEY_POSITION: "TopRight"})
        modal._draw_mock()
        self.assertEqual(modal.props["next_ep_zoom"], "TopRight")
        modal._draft[app.KEY_POSITION] = "BottomLeft"
        modal._draw_mock()
        self.assertEqual(modal.props["next_ep_zoom"], "BottomLeft")
        modal._draft[app.KEY_SIZE] = "Normal"
        modal._draw_mock()
        self.assertEqual(modal.props["next_ep_zoom"], "")

    def test_nudging_the_size_row_redraws_the_mockup(self):
        modal = _modal()
        modal._refresh()
        self.assertEqual(modal.props["next_ep_zoom"], "")
        modal._nudge(cust.ROW_IDS[app.KEY_SIZE], 1)
        self.assertEqual(modal._draft[app.KEY_SIZE], "Large")
        self.assertEqual(modal.props["next_ep_zoom"], "BottomRight")

    def test_the_row_control_exists_in_both_skins_like_the_other_rows(self):
        for res in ("720p", "1080i"):
            _root, els = _elements(os.path.join(SKINS, res, "NextEpisodeCustomize.xml"))
            self.assertEqual(els[cust.ROW_IDS[app.KEY_SIZE]].get("type"), "button", res)


class SettingsFileTests(unittest.TestCase):
    def test_settings_xml_is_what_the_generator_writes(self):
        """The file in the repo is generated: edit tools/gen_settings_v1.py, then run it."""
        import shutil
        import subprocess
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "tools"))
            os.makedirs(os.path.join(tmp, "resources"))
            script = os.path.join(tmp, "tools", "gen_settings_v1.py")
            shutil.copyfile(os.path.join(ROOT, "tools", "gen_settings_v1.py"), script)
            env = dict(os.environ, PYTHONPATH=ROOT, PYTHONDONTWRITEBYTECODE="1")
            run = subprocess.run([sys.executable, script], capture_output=True, text=True, env=env, cwd=tmp)
            self.assertEqual(run.returncode, 0, run.stderr)
            with open(os.path.join(tmp, "resources", "settings.xml"), encoding="utf-8", newline="") as fh:
                generated = fh.read()
        with open(os.path.join(ROOT, "resources", "settings.xml"), encoding="utf-8", newline="") as fh:
            current = fh.read()
        self.assertEqual(current.replace("\r\n", "\n"), generated)


class StringsAndSettingTests(unittest.TestCase):
    def entries(self, pack):
        path = os.path.join(ROOT, "resources", "language", pack, "strings.po")
        text = open(path, encoding="utf-8").read()
        return {int(a): b for a, b in re.findall(r'msgctxt "#(\d+)"\nmsgid ".*"\nmsgstr "(.*)"', text)}

    def packs(self):
        base = os.path.join(ROOT, "resources", "language")
        return sorted(p for p in os.listdir(base) if os.path.exists(os.path.join(base, p, "strings.po")))

    def test_every_pack_has_the_four_strings_in_its_own_language(self):
        english = self.entries("resource.language.en_gb")
        self.assertEqual(
            [english[i] for i in (47151, 47153, 47154)], ["Popup size", "Normal", "Large"]
        )
        self.assertIn("quarter", english[47152])
        self.assertEqual(len(self.packs()), 11)
        for pack in self.packs():
            entries = self.entries(pack)
            for sid in range(47151, 47155):
                self.assertTrue(entries.get(sid, "").strip(), (pack, sid))
                self.assertNotIn("%", entries[sid], (pack, sid))
                # "Normal" is the same word in several languages
                if not pack.endswith("en_gb") and sid != 47153:
                    self.assertNotEqual(entries[sid], english[sid], (pack, sid))

    def test_the_setting_is_defined_with_its_strings(self):
        found = {s.get("id"): s for s in ET.parse(os.path.join(ROOT, "resources", "settings.xml")).getroot().iter("setting")}
        setting = found[app.KEY_SIZE]
        self.assertEqual((setting.get("label"), setting.get("help")), ("47151", "47152"))
        self.assertEqual((setting.findtext("level"), setting.findtext("default")), ("1", "Normal"))
        self.assertEqual(
            [(o.get("label"), o.text) for o in setting.iter("option")], [("47153", "Normal"), ("47154", "Large")]
        )
        deps = {(d.get("setting"), d.text) for d in setting.iter("dependency")}
        self.assertIn(("next_episode_enabled", "true"), deps)
        self.assertIn((app.KEY_STYLE, "Custom"), deps)

    def test_the_setting_sits_right_after_the_position_on_the_settings_page(self):
        ids = [s.get("id") for s in ET.parse(os.path.join(ROOT, "resources", "settings.xml")).getroot().iter("setting")]
        self.assertEqual(ids.index(app.KEY_SIZE), ids.index(app.KEY_POSITION) + 1)


if __name__ == "__main__":
    unittest.main()
