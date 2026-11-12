# -*- coding: utf-8 -*-
"""The editor's own Yes/No, OK and list-pick dialogs: what each button, key and back press returns."""

import unittest
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

from tests import fake_gui  # noqa: E402

SELECT = fake_gui.ACTION_SELECT_ITEM
BACK = fake_gui.ACTION_NAV_BACK
PREVIOUS_MENU = fake_gui.ACTION_PREVIOUS_MENU
PAGE_UP = fake_gui.ACTION_PAGE_UP
PAGE_DOWN = fake_gui.ACTION_PAGE_DOWN
UP = fake_gui.ACTION_MOVE_UP
DOWN = fake_gui.ACTION_MOVE_DOWN


class _Base(unittest.TestCase):
    def setUp(self):
        fake_gui.reset()
        self.addCleanup(fake_gui.reset)
        self.m = fake_gui.load("skippy_editor_modal_skin", self)


class YesNoTests(_Base):
    def dialog(self, message="body"):
        return self.m.EditorTallYesNoDialog("Heading", message, "Overwrite", "Keep")

    def test_labels_and_body_text(self):
        d = self.dialog("Replace the file?")
        self.assertEqual(d._btn_yes.label, "Overwrite")
        self.assertEqual(d._btn_cancel.label, "Keep")
        self.assertEqual(d._body.text, "Replace the file?")
        self.assertFalse(d.result)

    def test_blank_labels_fall_back(self):
        d = self.m.EditorTallYesNoDialog("H", None, "  ", "")
        self.assertEqual(d._btn_yes.label, "Yes")
        self.assertEqual(d._btn_cancel.label, "Cancel")
        self.assertEqual(d._body.text, "")

    def test_opens_with_yes_focused(self):
        d = self.dialog()
        d.onInit()
        self.assertIs(d.getFocus(), d._btn_yes)

    def test_yes_and_cancel_clicks(self):
        d = self.dialog()
        d.onClick(d._yes_id)
        self.assertTrue(d.result)
        self.assertTrue(d.closed)
        d = self.dialog()
        d.onClick(d._btn_cancel)  # a control object works too
        self.assertFalse(d.result)
        self.assertTrue(d.closed)

    def test_on_control_yes_and_cancel(self):
        d = self.dialog()
        d.onControl(d._btn_yes)
        self.assertTrue(d.result)
        d = self.dialog()
        d.onControl(d._btn_cancel)
        self.assertFalse(d.result)
        self.assertTrue(d.closed)

    def test_scroll_buttons_page_and_never_go_below_zero(self):
        d = self.dialog()
        d.onClick(d._scroll_down_id)
        d.onClick(d._scroll_down_id)
        self.assertEqual(d._body_scroll_pos, 2 * self.m._BODY_SCROLL_PAGE)
        self.assertEqual(d._body.scrolled_to, 2 * self.m._BODY_SCROLL_PAGE)
        for _ in range(5):
            d.onClick(d._scroll_up_id)
        self.assertEqual(d._body_scroll_pos, 0)
        self.assertFalse(d.closed)

    def test_back_and_previous_menu_cancel(self):
        for aid in (BACK, PREVIOUS_MENU, 216):
            d = self.dialog()
            d.result = True
            d.act(aid)
            self.assertFalse(d.result)
            self.assertTrue(d.closed)

    def test_page_and_arrow_keys_scroll_when_a_button_has_focus(self):
        d = self.dialog()
        d.setFocus(d._btn_yes)
        d.act(PAGE_DOWN)
        self.assertEqual(d._body_scroll_pos, self.m._BODY_SCROLL_PAGE)
        d.act(UP)
        self.assertEqual(d._body_scroll_pos, self.m._BODY_SCROLL_PAGE - 1)
        d.act(DOWN)
        d.act(DOWN)
        self.assertEqual(d._body_scroll_pos, self.m._BODY_SCROLL_PAGE + 1)
        d.act(PAGE_UP)
        d.act(PAGE_UP)
        self.assertEqual(d._body_scroll_pos, 0)
        self.assertFalse(d.closed)

    def test_keys_do_not_scroll_without_button_focus(self):
        d = self.dialog()
        d.setFocus(d._body)
        d.act(PAGE_DOWN)
        d.act(DOWN)
        self.assertEqual(d._body_scroll_pos, 0)

    def test_select_acts_on_the_focused_button(self):
        d = self.dialog()
        d.setFocus(d._btn_cancel)
        d.act(SELECT)
        self.assertFalse(d.result)
        self.assertTrue(d.closed)
        d = self.dialog()
        d.setFocus(d._btn_yes)
        d.act(SELECT)
        self.assertTrue(d.result)
        d = self.dialog()
        d.setFocus(d._btn_scroll_down)
        d.act(SELECT)
        self.assertEqual(d._body_scroll_pos, self.m._BODY_SCROLL_PAGE)
        self.assertFalse(d.closed)

    def test_select_on_the_body_does_nothing(self):
        d = self.dialog()
        d.setFocus(d._body)
        d.act(SELECT)
        self.assertFalse(d.closed)

    def test_select_with_no_focus_uses_the_default_yes(self):
        d = self.dialog()
        d.focus = None
        d.act(SELECT)
        self.assertTrue(d.result)
        self.assertTrue(d.closed)

    def test_navigation_links_the_button_row(self):
        d = self.dialog()
        self.assertEqual(d._btn_yes.navigation[2], d._btn_scroll_down)
        self.assertEqual(d._btn_yes.navigation[3], d._btn_cancel)
        self.assertEqual(d._btn_cancel.navigation[2], d._btn_yes)

    def test_show_returns_the_user_choice(self):
        fake_gui.on_modal = lambda w: w.onClick(w._yes_id)
        self.assertTrue(self.m.sidecar_overwrite_yesno_show("H", "M", "Yes", "No"))
        fake_gui.on_modal = lambda w: w.act(BACK)
        self.assertFalse(self.m.sidecar_overwrite_yesno_show("H", "M", "Yes", "No"))


class OkScrollTests(_Base):
    def test_ok_closes(self):
        d = self.m.EditorOkScrollDialog("H", "Line\n" * 50, "Got it")
        self.assertEqual(d._btn_ok.label, "Got it")
        d.onInit()
        self.assertIs(d.getFocus(), d._btn_ok)
        d.onClick(d._btn_ok.getId())
        self.assertTrue(d.closed)

    def test_back_closes_and_scroll_stays_open(self):
        d = self.m.EditorOkScrollDialog("H", "text")
        d.setFocus(d._btn_ok)
        d.act(PAGE_DOWN)
        d.act(DOWN)
        self.assertEqual(d._body_scroll_pos, self.m._BODY_SCROLL_PAGE + 1)
        self.assertFalse(d.closed)
        d.act(BACK)
        self.assertTrue(d.closed)

    def test_select_on_ok_closes(self):
        d = self.m.EditorOkScrollDialog("H", "text")
        d.setFocus(d._btn_ok)
        d.act(SELECT)
        self.assertTrue(d.closed)

    def test_show_editor_ok_runs_modal_and_blank_label_is_ok(self):
        seen = []
        fake_gui.on_modal = seen.append
        self.m.show_editor_ok("H", None, ok_label=" ")
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0]._btn_ok.label, "OK")
        self.assertEqual(seen[0]._body.text, "")


class ListPickTests(_Base):
    OPTIONS = ["Intro", "Recap", "Credits"]

    def dialog(self, preselect=0, options=None, subtitle=""):
        return self.m.EditorListPickDialog(
            "Pick", self.OPTIONS if options is None else options,
            subtitle=subtitle, preselect=preselect, cancel_label="Back",
        )

    def test_one_button_per_option(self):
        d = self.dialog()
        self.assertEqual([b.label for b in d._option_buttons], self.OPTIONS)
        self.assertEqual(d._btn_cancel.label, "Back")
        self.assertEqual(d.selected_index, -1)

    def test_subtitle_adds_a_label(self):
        plain = self.dialog()
        with_sub = self.dialog(subtitle="Choose one")
        texts = [c.label for c in with_sub.controls if isinstance(c, fake_gui.ControlLabel)]
        self.assertIn("Choose one", texts)
        self.assertEqual(len(with_sub.controls), len(plain.controls) + 1)

    def test_preselect_is_clamped_and_focused(self):
        d = self.dialog(preselect=99)
        self.assertEqual(d._preselect, 2)
        d.onInit()
        self.assertIs(d.getFocus(), d._option_buttons[2])
        self.assertEqual(self.dialog(preselect=-4)._preselect, 0)

    def test_empty_options_focus_cancel(self):
        d = self.dialog(options=[])
        d.onInit()
        self.assertIs(d.getFocus(), d._btn_cancel)
        d.setFocus(None)
        d.act(SELECT)
        self.assertEqual(d.selected_index, -1)
        self.assertTrue(d.closed)

    def test_click_picks_the_option(self):
        d = self.dialog()
        d.onClick(d._option_buttons[1].getId())
        self.assertEqual(d.selected_index, 1)
        self.assertTrue(d.closed)

    def test_on_control_picks_the_option_and_cancel(self):
        d = self.dialog()
        d.onControl(d._option_buttons[2])
        self.assertEqual(d.selected_index, 2)
        d = self.dialog()
        d.selected_index = 1
        d.onControl(d._btn_cancel)
        self.assertEqual(d.selected_index, -1)
        self.assertTrue(d.closed)

    def test_cancel_click_and_back(self):
        d = self.dialog()
        d.onClick(d._cancel_id)
        self.assertEqual(d.selected_index, -1)
        for aid in (BACK, PREVIOUS_MENU):
            d = self.dialog()
            d.act(aid)
            self.assertEqual(d.selected_index, -1)
            self.assertTrue(d.closed)

    def test_select_picks_focused_option(self):
        d = self.dialog()
        d.setFocus(d._option_buttons[1])
        d.act(SELECT)
        self.assertEqual(d.selected_index, 1)
        d = self.dialog()
        d.setFocus(d._btn_cancel)
        d.act(SELECT)
        self.assertEqual(d.selected_index, -1)

    def test_select_without_a_matching_focus_takes_preselect(self):
        d = self.dialog(preselect=2)
        d.setFocus(None)
        d.act(SELECT)
        self.assertEqual(d.selected_index, 2)

    def test_unrelated_click_and_key_do_nothing(self):
        d = self.dialog()
        d.onClick(999999)
        d.act(UP)
        self.assertFalse(d.closed)
        self.assertEqual(d.selected_index, -1)

    def test_navigation_runs_down_the_list_into_cancel(self):
        d = self.dialog()
        b = d._option_buttons
        self.assertEqual(b[0].navigation[0], b[0])
        self.assertEqual(b[0].navigation[1], b[1])
        self.assertEqual(b[2].navigation[1], d._btn_cancel)
        self.assertEqual(d._btn_cancel.navigation[0], b[2])

    def test_show_editor_list_pick_returns_the_pick(self):
        fake_gui.on_modal = lambda w: w.onClick(w._option_buttons[1].getId())
        self.assertEqual(self.m.show_editor_list_pick("H", self.OPTIONS), 1)
        fake_gui.on_modal = lambda w: w.act(BACK)
        self.assertEqual(self.m.show_editor_list_pick("H", self.OPTIONS), -1)

    def test_show_editor_list_pick_focuses_preselect_before_modal(self):
        seen = []
        fake_gui.on_modal = lambda w: seen.append(w.getFocus())
        self.m.show_editor_list_pick("H", self.OPTIONS, preselect=1)
        # onInit runs inside doModal and focuses the same button
        self.assertEqual(seen[0].label, "Recap")

    def test_cancel_label_from_strings_and_fallback(self):
        labels = []
        fake_gui.on_modal = lambda w: labels.append(w._btn_cancel.label)
        addon = MagicMock()
        addon.getLocalizedString.return_value = "Annuleren"
        with patch.object(self.m, "get_addon", return_value=addon):
            self.m.show_editor_list_pick("H", self.OPTIONS)
        addon.getLocalizedString.assert_called_with(35019)
        addon.getLocalizedString.return_value = ""
        with patch.object(self.m, "get_addon", return_value=addon):
            self.m.show_editor_list_pick("H", self.OPTIONS)
        broken = MagicMock()
        broken.getLocalizedString.side_effect = RuntimeError
        with patch.object(self.m, "get_addon", return_value=broken):
            self.m.show_editor_list_pick("H", self.OPTIONS)
        self.m.show_editor_list_pick("H", self.OPTIONS, cancel_label="Close")
        self.assertEqual(labels, ["Annuleren", "Cancel", "Cancel", "Close"])


class HelperTests(_Base):
    def test_addon_skin_media(self):
        addon = MagicMock()
        addon.getAddonInfo.return_value = "/addon"
        with patch.object(self.m, "get_addon", return_value=addon), \
                patch.object(self.m.xbmcvfs, "exists", return_value=True):
            path = self.m.addon_skin_media("white.png")
        self.assertTrue(path.replace("\\", "/").endswith(
            "/addon/resources/skins/default/media/white.png"))
        with patch.object(self.m, "get_addon", return_value=addon), \
                patch.object(self.m.xbmcvfs, "exists", return_value=False):
            self.assertEqual(self.m.addon_skin_media("white.png"), "-")
        with patch.object(self.m, "get_addon", return_value=None):
            self.assertEqual(self.m.addon_skin_media("white.png"), "white.png")

    def test_push_button_falls_back_on_older_signatures(self):
        calls = []

        class Picky(fake_gui.ControlButton):
            def __init__(self, *args, **kwargs):
                calls.append((len(args), sorted(kwargs)))
                if kwargs or len(args) > 7:
                    raise TypeError("old Kodi")
                super().__init__(*args)

        with patch.object(fake_gui, "ControlButton", Picky):
            b = self.m.segment_style_push_button(1, 2, 3, 4, "Go", "focus.png")
        self.assertEqual(len(calls), 3)
        self.assertEqual(b.label, "Go")
        self.assertEqual((b.x, b.y, b.w, b.h), (1, 2, 3, 4))

    def test_push_button_first_signature(self):
        b = self.m.segment_style_push_button(0, 0, 10, 10, "OK", "f.png")
        self.assertEqual(b.kwargs.get("font"), "font10")


if __name__ == "__main__":
    unittest.main()
