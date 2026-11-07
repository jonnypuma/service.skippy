# -*- coding: utf-8 -*-
"""The prompt time cannot be longer than the time before the end the prompt appears."""

import os
import re
import unittest
from unittest.mock import patch

from tests.kodi_stubs import import_fresh, install_kodi_stubs

install_kodi_stubs()

import next_episode_limits as limits
import next_episode_state as state_mod

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class _Addon:
    def __init__(self, **settings):
        self.settings = {k: str(v) for k, v in settings.items()}
        self.writes = []

    def getLocalizedString(self, string_id):
        return ""

    def getSetting(self, key):
        return self.settings.get(key, "")

    getSettingString = getSetting

    def setSetting(self, key, value):
        self.writes.append((key, value))
        self.settings[key] = value


def _addon(duration, lead=45, credits="false", enabled="true"):
    return _Addon(
        next_episode_enabled=enabled,
        next_episode_popup_duration=duration,
        next_episode_lead_seconds=lead,
        next_episode_start_at_credits=credits,
    )


class AllowedDurationTests(unittest.TestCase):
    def test_a_time_within_the_lead_time_is_kept(self):
        self.assertEqual(limits.allowed_popup_duration(20, 45, False), 20)
        self.assertEqual(limits.allowed_popup_duration(45, 45, False), 45)

    def test_a_longer_time_is_lowered_to_the_lead_time(self):
        self.assertEqual(limits.allowed_popup_duration(60, 45, False), 45)
        self.assertEqual(limits.allowed_popup_duration(120, 30, False), 30)

    def test_zero_means_until_the_end_and_stays(self):
        self.assertEqual(limits.allowed_popup_duration(0, 45, False), 0)
        self.assertEqual(limits.allowed_popup_duration(-5, 45, False), 0)

    def test_the_credits_start_leaves_it_alone_because_the_window_is_not_known(self):
        self.assertEqual(limits.allowed_popup_duration(60, 45, True), 60)
        self.assertEqual(limits.allowed_popup_duration(500, 45, True), state_mod.MAX_POPUP_DURATION_S)

    def test_nonsense_is_zero(self):
        self.assertEqual(limits.allowed_popup_duration("x", 45, False), 0)
        self.assertEqual(limits.allowed_popup_duration(30, None, False), 0)


class EnforceTests(unittest.TestCase):
    def run_enforce(self, addon):
        with patch("settings_utils.notify_skippy") as notify:
            result = limits.enforce_popup_duration_limit(addon)
        self.notify = notify
        return result

    def test_a_longer_prompt_time_is_lowered_and_the_user_is_told(self):
        addon = _addon(60, lead=45)
        self.assertEqual(self.run_enforce(addon), 45)
        self.assertEqual(addon.writes, [("next_episode_popup_duration", "45")])
        message = self.notify.call_args.args[1]
        self.assertIn("45", message)
        self.assertIn("Show the prompt for", message)
        self.assertIs(self.notify.call_args.kwargs.get("prefer_builtin"), True)

    def test_lowering_the_lead_time_below_the_prompt_time_lowers_the_prompt_time(self):
        addon = _addon(45, lead=30)
        self.assertEqual(self.run_enforce(addon), 30)
        self.assertEqual(addon.settings["next_episode_popup_duration"], "30")

    def test_nothing_changes_when_the_time_fits(self):
        for duration, lead in ((20, 45), (45, 45), (0, 45)):
            addon = _addon(duration, lead)
            self.assertIsNone(self.run_enforce(addon), (duration, lead))
            self.assertEqual(addon.writes, [])
            self.notify.assert_not_called()

    def test_with_the_credits_start_on_a_long_time_is_allowed(self):
        addon = _addon(90, lead=45, credits="true")
        self.assertIsNone(self.run_enforce(addon))
        self.assertEqual(addon.writes, [])

    def test_nothing_is_touched_while_the_feature_is_off(self):
        addon = _addon(90, lead=45, enabled="false")
        self.assertIsNone(self.run_enforce(addon))
        self.assertEqual(addon.writes, [])
        self.notify.assert_not_called()

    def test_a_second_check_after_the_change_does_nothing(self):
        addon = _addon(60, lead=45)
        self.run_enforce(addon)
        addon.writes.clear()
        self.assertIsNone(self.run_enforce(addon))
        self.assertEqual(addon.writes, [])

    def test_the_default_lead_time_applies_when_none_is_stored(self):
        addon = _Addon(next_episode_enabled="true", next_episode_popup_duration="60")
        self.assertEqual(self.run_enforce(addon), 45)

    def test_no_addon_does_nothing(self):
        with patch("settings_utils.get_addon", return_value=None):
            self.assertIsNone(limits.enforce_popup_duration_limit())


class RuntimeTests(unittest.TestCase):
    def test_a_prompt_time_longer_than_the_window_runs_to_the_end_without_a_timeout(self):
        # Credits start 80 s before the end of a 1500 s file, but only 45 s are left of the window.
        begin, end, timed = state_mod.popup_span(1455.0, 1455.0, 1500.0, 60)
        self.assertEqual((begin, end, timed), (1455.0, 1500.0, False))

    def test_a_window_shorter_than_the_stored_time_after_a_late_start_still_works(self):
        begin, end, timed = state_mod.popup_span(1400.0, 1470.0, 1500.0, 120)
        self.assertEqual((begin, end, timed), (1470.0, 1500.0, False))


def _po_entries(pack):
    path = os.path.join(ROOT, "resources", "language", pack, "strings.po")
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    return {
        int(sid): msgstr
        for sid, msgstr in re.findall(r'msgctxt "#(\d+)"\nmsgid ".*"\nmsgstr "(.*)"', text)
    }


class StringsTests(unittest.TestCase):
    def packs(self):
        langs = os.path.join(ROOT, "resources", "language")
        return sorted(p for p in os.listdir(langs) if os.path.exists(os.path.join(langs, p, "strings.po")))

    def test_the_message_is_in_every_pack_with_one_number_in_it(self):
        english = _po_entries("resource.language.en_gb")[limits.TOAST_ID]
        self.assertEqual(english, limits.TOAST_DEFAULT)
        for pack in self.packs():
            text = _po_entries(pack).get(limits.TOAST_ID)
            self.assertTrue(text, pack)
            self.assertEqual(text.count("%s"), 1, pack)
            self.assertEqual(text.count("%"), 1, pack)
            if not pack.endswith("en_gb"):
                self.assertNotEqual(text, english, pack)

    def test_the_message_and_the_help_name_the_lead_time_setting_the_way_the_pack_does(self):
        for pack in self.packs():
            entries = _po_entries(pack)
            self.assertIn(entries[47005], entries[limits.TOAST_ID], pack)
            self.assertIn(entries[47005], entries[47119], pack)

    def test_the_help_of_the_prompt_time_mentions_the_credits_start_in_every_pack(self):
        for pack in self.packs():
            entries = _po_entries(pack)
            self.assertIn(entries[47064], entries[47119], pack)


class ServiceHookTests(unittest.TestCase):
    def test_changing_a_setting_checks_the_prompt_time(self):
        install_kodi_stubs()
        import_fresh("service_main_loop")
        with patch("service_main_loop.run_service_main_loop", lambda _ctx: None):
            service = import_fresh("service")
        with patch("next_episode_limits.enforce_popup_duration_limit") as enforce:
            service.PlayerMonitor.onSettingsChanged(object.__new__(service.PlayerMonitor))
        enforce.assert_called_once_with()

    def test_a_failing_check_does_not_break_the_other_settings_work(self):
        install_kodi_stubs()
        import_fresh("service_main_loop")
        with patch("service_main_loop.run_service_main_loop", lambda _ctx: None):
            service = import_fresh("service")
        with patch("next_episode_limits.enforce_popup_duration_limit", side_effect=RuntimeError("boom")):
            service.PlayerMonitor.onSettingsChanged(object.__new__(service.PlayerMonitor))


if __name__ == "__main__":
    unittest.main()
