# -*- coding: utf-8 -*-
"""Make a custom dialog, save it, choose a preset, load the custom one again: it comes back whole."""
import unittest
from unittest.mock import patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import next_episode_appearance as app  # noqa: E402
import next_episode_saved_looks as looks  # noqa: E402
import skip_dialog_customize_ui as ui  # noqa: E402
import skip_dialog_presets as sp  # noqa: E402
import skip_layouts as sl  # noqa: E402


def skip_draft(**values):
    draft = dict(ui._TEXT_DEFAULTS)
    draft.update(ui._BOOL_DEFAULTS)
    draft.update(values)
    return draft


class SkipDialogRoundTrip(unittest.TestCase):
    def setUp(self):
        self.store = {}
        self._patches = [
            patch.object(sp, "load_user_presets", lambda: dict(self.store)),
            patch.object(sp, "_write_user_presets", lambda presets: self.store.clear() or self.store.update(presets) or True),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()

    CUSTOM = {
        "skip_dialog_mode": "CompactFull", sl.KEY_LAYOUT: "Dial", sl.KEY_LOOK: "neon", sl.KEY_BAR_COLOR: sl.BAR_LOOK,
        sl.KEY_OVERLAY: "Round", sl.KEY_APPEAR: "Pop", sl.KEY_LEAVE: "Shrink", sl.KEY_PULSE: True,
    }

    def test_a_custom_layout_dialog_comes_back_whole(self):
        draft = skip_draft(**self.CUSTOM)
        self.assertEqual(sp.save_user_preset("My evening", draft), (True, ""))
        self.assertEqual(sp.detect_preset(draft), "My evening")
        # choose a built-in layout preset, then a card preset
        other = dict(sp.layout_presets())["Timeline" + sp.LAYOUT_PRESET_SEP + "Fused Glass Dark"]
        sp.apply_preset(draft, other)
        self.assertEqual(draft[sl.KEY_LAYOUT], "Timeline")
        self.assertNotEqual(sp.detect_preset(draft), "My evening")
        sp.apply_preset(draft, sp.builtin_presets()[0][1])
        self.assertEqual(draft[sl.KEY_LAYOUT], sl.LAYOUT_CARD)
        draft[sl.KEY_OVERLAY], draft[sl.KEY_PULSE], draft["skip_dialog_mode"] = "Band", False, "Full"
        # load the custom one again
        saved = dict((name, values) for name, values, _b in sp.list_presets())["My evening"]
        sp.apply_preset(draft, saved)
        for key, value in self.CUSTOM.items():
            self.assertEqual(draft[key], value, key)
        self.assertEqual(sp.detect_preset(draft), "My evening")

    def test_a_built_in_layout_preset_leaves_size_overlay_and_motion_alone(self):
        draft = skip_draft(**self.CUSTOM)
        sp.apply_preset(draft, dict(sp.layout_presets())["Float" + sp.LAYOUT_PRESET_SEP + "Aeon"])
        self.assertEqual((draft[sl.KEY_LAYOUT], draft[sl.KEY_LOOK]), ("Float", "aeo"))
        self.assertEqual((draft["skip_dialog_mode"], draft[sl.KEY_OVERLAY], draft[sl.KEY_PULSE]), ("CompactFull", "Round", True))
        self.assertEqual(sp.detect_preset(draft), "Float" + sp.LAYOUT_PRESET_SEP + "Aeon")

    def test_a_custom_minimal_form_is_saved_with_its_layout(self):
        draft = skip_draft(**dict(self.CUSTOM, skip_dialog_mode="Minimal"))
        sp.save_user_preset("Tiny", draft)
        sp.apply_preset(draft, sp.builtin_presets()[0][1])
        sp.apply_preset(draft, self.store["Tiny"])
        self.assertEqual((draft["skip_dialog_mode"], draft[sl.KEY_LAYOUT], draft[sl.KEY_LOOK]), ("Minimal", "Dial", "neon"))
        self.assertEqual(sp.detect_preset(draft), "Tiny")

    def test_a_preset_saved_before_this_version_still_loads(self):
        old = {"skip_dialog_mode": "Full", sl.KEY_LAYOUT: "Rail", sl.KEY_LOOK: "agl", sl.KEY_BAR_COLOR: sl.BAR_TYPE}
        self.store["Old one"] = sp.sanitize_values(old)
        draft = skip_draft(**self.CUSTOM)
        sp.apply_preset(draft, self.store["Old one"])
        self.assertEqual((draft[sl.KEY_LAYOUT], draft[sl.KEY_LOOK], draft["skip_dialog_mode"]), ("Rail", "agl", "Full"))
        self.assertEqual(draft[sl.KEY_OVERLAY], "Round")  # it never stored one, so it leaves it

    def test_a_custom_card_dialog_comes_back_whole(self):
        draft = skip_draft(skip_dialog_mode="Full", skip_card_style="Rounded", skip_card_opacity=60,
                           skip_dialog_font_color="FFFFD700", progress_bar_height=9, skip_dialog_layout="Card")
        sp.save_user_preset("Gold card", draft)
        sp.apply_preset(draft, dict(sp.layout_presets())["Dial" + sp.LAYOUT_PRESET_SEP + "Neon"])
        sp.apply_preset(draft, self.store["Gold card"])
        self.assertEqual(draft[sl.KEY_LAYOUT], sl.LAYOUT_CARD)
        self.assertEqual((draft["skip_card_style"], draft["skip_card_opacity"], draft["skip_dialog_font_color"],
                          draft["progress_bar_height"]), ("Rounded", 60, "FFFFD700", 9))
        self.assertEqual(sp.detect_preset(draft), "Gold card")


class DesignOptionTests(unittest.TestCase):
    def setUp(self):
        self.store = {}
        self._patches = [
            patch.object(sp, "load_user_presets", lambda: dict(self.store)),
            patch.object(sp, "_write_user_presets", lambda presets: self.store.update(presets) or True),
        ]
        for item in self._patches:
            item.start()

    def tearDown(self):
        for item in self._patches:
            item.stop()

    def test_the_default_is_the_stack_card_in_fused_glass_dark(self):
        draft = skip_draft()
        self.assertEqual((draft[sl.KEY_LAYOUT], draft[sl.KEY_LOOK]), ("Stack", "fgd"))
        self.assertEqual(sp.detect_preset(draft), "Stack card" + sp.LAYOUT_PRESET_SEP + "Fused Glass Dark")

    def test_a_changed_option_makes_it_custom_and_one_step_goes_back_to_the_design_as_drawn(self):
        draft = skip_draft()
        home = "Stack card" + sp.LAYOUT_PRESET_SEP + "Fused Glass Dark"
        draft["skip_canvas_corners"] = "Hard"
        draft["skip_canvas_accent"] = "Blue"
        self.assertIsNone(sp.detect_preset(draft))
        for delta in (1, -1):
            trial = dict(draft)
            name, values = sp.cycle_preset(trial, delta)
            self.assertEqual(name, home)  # not the classic card that is also called Fused Glass Dark
            sp.apply_preset(trial, values)
            self.assertEqual((trial[sl.KEY_LAYOUT], trial["skip_canvas_corners"], trial["skip_canvas_accent"]),
                             ("Stack", "Skin", "Auto"))
            self.assertEqual(sp.detect_preset(trial), home)

    def test_a_saved_preset_keeps_the_options_of_the_design(self):
        draft = skip_draft(skip_canvas_corners="Rounded", skip_canvas_zoom="85", skip_canvas_outline="Light",
                           skip_canvas_distance=96, skip_canvas_time=False)
        sp.save_user_preset("Mine", draft)
        sp.apply_preset(draft, dict(sp.layout_presets())["Dial" + sp.LAYOUT_PRESET_SEP + "Neon"])
        self.assertEqual(draft["skip_canvas_corners"], "Skin")
        sp.apply_preset(draft, self.store["Mine"])
        self.assertEqual((draft[sl.KEY_LAYOUT], draft["skip_canvas_corners"], draft["skip_canvas_zoom"],
                          draft["skip_canvas_outline"], draft["skip_canvas_distance"], draft["skip_canvas_time"]),
                         ("Stack", "Rounded", "85", "Light", 96, False))
        self.assertEqual(sp.detect_preset(draft), "Mine")


class UpNextRoundTrip(unittest.TestCase):
    def setUp(self):
        self.store = {}
        self._patches = [
            patch.object(looks, "load_user_looks", lambda: dict(self.store)),
            patch.object(looks, "_write_user_looks", lambda found: self.store.clear() or self.store.update(found) or True),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()

    def test_a_custom_layout_popup_comes_back_whole(self):
        draft = dict(app.DEFAULT_DRAFT, **{app.KEY_LAYOUT: "Queue", app.KEY_LAYOUT_LOOK: "paper", app.KEY_POSITION: "TopLeft"})
        self.assertEqual(looks.save_user_look("Sofa", draft)[0], True)
        self.assertEqual(looks.detect_saved_look(draft), "Sofa")
        draft.update({app.KEY_LAYOUT: "Takeover", app.KEY_LAYOUT_LOOK: "fgd"})
        self.assertIsNone(looks.detect_saved_look(draft))
        self.assertTrue(looks.apply_look(draft, self.store["Sofa"]))
        self.assertEqual((draft[app.KEY_LAYOUT], draft[app.KEY_LAYOUT_LOOK]), ("Queue", "paper"))
        self.assertEqual(draft[app.KEY_POSITION], "TopLeft")  # where it sits is not part of a look
        self.assertEqual(looks.detect_saved_look(draft), "Sofa")

    def test_a_custom_card_popup_keeps_its_picture(self):
        draft = dict(app.DEFAULT_DRAFT, **{app.KEY_PICTURE: app.PICTURE_BOTH, app.KEY_THUMBNAIL: True})
        looks.save_user_look("Pair", draft)
        draft.update({app.KEY_LAYOUT: "Ring", app.KEY_PICTURE: app.PICTURE_FANART, app.KEY_THUMBNAIL: False})
        looks.apply_look(draft, self.store["Pair"])
        self.assertEqual((draft[app.KEY_LAYOUT], draft[app.KEY_PICTURE], draft[app.KEY_THUMBNAIL]),
                         ("Card", app.PICTURE_BOTH, True))

    def test_a_look_saved_before_the_layouts_leaves_them_alone(self):
        old = looks.sanitize_values({key: app.DEFAULT_DRAFT[key] for key in looks.LOOK_KEYS})
        self.assertEqual(set(old), set(looks.LOOK_KEYS))
        self.store["Old"] = old
        draft = dict(app.DEFAULT_DRAFT, **{app.KEY_LAYOUT: "Queue"})
        looks.apply_look(draft, old)
        self.assertEqual(draft[app.KEY_LAYOUT], "Queue")
        self.assertEqual(looks.detect_saved_look(draft), "Old")



# these tests are about the popup of earlier versions: a draft starts with it while they run
def setUpModule():
    from tests import legacy_card

    legacy_card.use_legacy_card()


def tearDownModule():
    from tests import legacy_card

    legacy_card.restore_default()


if __name__ == "__main__":
    unittest.main()
