# -*- coding: utf-8 -*-
"""Per-show autoplay: the store, the autoplay decision, the question and the Manage window."""

import os
import re
import sys
import tempfile
import types
import unittest
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import next_episode_shows as shows
import next_episode_shows_ui as ui
import service_loop_next_episode as step
import skippy_profile_backup as backup
import skippy_profile_store
from next_episode_state import LOOKUP_FOUND, LOOKUP_IDLE, NextEpisodeState

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

NEXT = {"source": "library", "episodeid": 8, "title": "Two", "season": 1, "episode": 2}


class _ProfileTempDir(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        patcher = patch.object(skippy_profile_store, "profile_dir", return_value=self._tmp.name)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)
        shows.clear_cache()
        self.addCleanup(shows.clear_cache)

    def path(self):
        return os.path.join(self._tmp.name, shows.SHOWS_FILENAME)


class ResolveAutoplayTests(unittest.TestCase):
    def test_a_show_without_a_choice_follows_the_global_setting(self):
        self.assertTrue(shows.resolve_autoplay(True, True, None))
        self.assertFalse(shows.resolve_autoplay(False, True, None))

    def test_the_show_choice_wins_when_per_show_is_on(self):
        self.assertTrue(shows.resolve_autoplay(False, True, shows.MODE_AUTO))
        self.assertFalse(shows.resolve_autoplay(True, True, shows.MODE_ASK))

    def test_the_show_choice_is_ignored_when_per_show_is_off(self):
        self.assertFalse(shows.resolve_autoplay(False, False, shows.MODE_AUTO))
        self.assertTrue(shows.resolve_autoplay(True, False, shows.MODE_ASK))

    def test_the_result_is_always_a_bool(self):
        self.assertIs(shows.resolve_autoplay(1, False, None), True)
        self.assertIs(shows.resolve_autoplay(None, True, None), False)

    def test_a_show_set_to_never_offer_does_not_autoplay_either(self):
        self.assertFalse(shows.resolve_autoplay(True, True, shows.MODE_NEVER))
        self.assertFalse(shows.resolve_autoplay(False, True, shows.MODE_NEVER))

    def test_never_offer_only_counts_while_per_show_is_on(self):
        self.assertTrue(shows.never_offer(True, shows.MODE_NEVER))
        self.assertFalse(shows.never_offer(False, shows.MODE_NEVER))
        self.assertFalse(shows.never_offer(True, shows.MODE_ASK))
        self.assertFalse(shows.never_offer(True, shows.MODE_AUTO))
        self.assertFalse(shows.never_offer(True, None))
        self.assertIs(shows.never_offer(1, shows.MODE_NEVER), True)

    def test_there_are_three_modes_in_the_order_the_windows_list_them(self):
        self.assertEqual(shows.MODES, ("auto", "ask", "never"))


class ShowKeyTests(unittest.TestCase):
    def test_an_episode_is_keyed_on_the_show_tmdb_id(self):
        self.assertEqual(
            shows.show_key_for_identity({"type": "episode", "tmdb_id": 1396}), "tv_tmdb_1396"
        )

    def test_imdb_is_the_fallback(self):
        self.assertEqual(
            shows.show_key_for_identity({"type": "episode", "tmdb_id": None, "imdb_id": "tt0903747"}),
            "tv_imdb_tt0903747",
        )

    def test_it_matches_the_key_the_auto_skip_rules_use(self):
        from per_show_overrides import override_key_for_identity

        identity = {"type": "episode", "tmdb_id": 1396, "imdb_id": "tt0903747"}
        self.assertEqual(shows.show_key_for_identity(identity), override_key_for_identity(identity))

    def test_movies_and_unknown_shows_have_no_key(self):
        self.assertIsNone(shows.show_key_for_identity({"type": "movie", "tmdb_id": 603}))
        self.assertIsNone(shows.show_key_for_identity({"type": "episode"}))
        self.assertIsNone(shows.show_key_for_identity(None))


class StoreTests(_ProfileTempDir):
    def test_nothing_is_saved_at_first(self):
        self.assertEqual(shows.load_shows(), {})
        self.assertIsNone(shows.lookup_mode("tv_tmdb_1"))
        self.assertEqual(shows.list_entries(), [])

    def test_save_and_look_up(self):
        self.assertTrue(shows.save_mode("tv_tmdb_1", shows.MODE_AUTO, "Friends"))
        self.assertEqual(shows.lookup_mode("tv_tmdb_1"), "auto")
        self.assertEqual(
            shows.list_entries(),
            [{"key": "tv_tmdb_1", "title": "Friends", "mode": "auto"}],
        )

    def test_never_offer_is_saved_and_listed(self):
        self.assertTrue(shows.save_mode("tv_tmdb_9", shows.MODE_NEVER, "Arrow"))
        self.assertEqual(shows.lookup_mode("tv_tmdb_9"), "never")
        self.assertEqual(
            shows.list_entries(), [{"key": "tv_tmdb_9", "title": "Arrow", "mode": "never"}]
        )
        shows.clear_cache()
        self.assertEqual(shows.lookup_mode("tv_tmdb_9"), "never")

    def test_a_change_keeps_the_saved_title(self):
        shows.save_mode("tv_tmdb_1", shows.MODE_AUTO, "Friends")
        shows.save_mode("tv_tmdb_1", shows.MODE_ASK)
        self.assertEqual(shows.lookup_mode("tv_tmdb_1"), "ask")
        self.assertEqual(shows.list_entries()[0]["title"], "Friends")

    def test_a_show_without_a_title_gets_a_readable_id(self):
        shows.save_mode("tv_tmdb_1396", shows.MODE_ASK)
        self.assertEqual(shows.list_entries()[0]["title"], "TV · TMDB 1396")

    def test_entries_are_sorted_by_title(self):
        shows.save_mode("tv_tmdb_1", shows.MODE_AUTO, "breaking Bad")
        shows.save_mode("tv_tmdb_2", shows.MODE_ASK, "Arrow")
        self.assertEqual([e["title"] for e in shows.list_entries()], ["Arrow", "breaking Bad"])

    def test_bad_input_is_refused(self):
        self.assertFalse(shows.save_mode("", shows.MODE_AUTO))
        self.assertFalse(shows.save_mode("tv/../x", shows.MODE_AUTO))
        self.assertFalse(shows.save_mode("tv_tmdb_1", "declined"))
        self.assertFalse(shows.save_mode(None, shows.MODE_AUTO))
        self.assertEqual(shows.load_shows(), {})

    def test_delete_forgets_one_show(self):
        shows.save_mode("tv_tmdb_1", shows.MODE_AUTO, "A")
        shows.save_mode("tv_tmdb_2", shows.MODE_AUTO, "B")
        self.assertTrue(shows.delete_show("tv_tmdb_1"))
        self.assertFalse(shows.delete_show("tv_tmdb_1"))
        self.assertIsNone(shows.lookup_mode("tv_tmdb_1"))
        self.assertEqual(shows.lookup_mode("tv_tmdb_2"), "auto")

    def test_clear_all_counts_and_removes(self):
        self.assertEqual(shows.clear_all(), 0)
        shows.save_mode("tv_tmdb_1", shows.MODE_AUTO)
        shows.save_mode("tv_tmdb_2", shows.MODE_ASK)
        self.assertEqual(shows.clear_all(), 2)
        self.assertEqual(shows.load_shows(), {})
        self.assertFalse(os.path.exists(self.path()))

    def test_our_own_write_is_seen_even_when_the_file_stamp_does_not_move(self):
        with patch.object(shows, "file_stamp", return_value=(1, 1)):
            shows.save_mode("tv_tmdb_1", shows.MODE_AUTO)
            self.assertEqual(shows.lookup_mode("tv_tmdb_1"), "auto")
            shows.save_mode("tv_tmdb_1", shows.MODE_ASK)
            self.assertEqual(shows.lookup_mode("tv_tmdb_1"), "ask")
            shows.delete_show("tv_tmdb_1")
            self.assertIsNone(shows.lookup_mode("tv_tmdb_1"))

    def test_another_script_changing_the_file_is_seen(self):
        shows.save_mode("tv_tmdb_1", shows.MODE_AUTO)
        self.assertEqual(shows.lookup_mode("tv_tmdb_1"), "auto")
        with open(self.path(), "w", encoding="utf-8") as handle:
            handle.write(
                '{"schema": "x", "shows": {"tv_tmdb_1": {"mode": "ask"}, "tv_tmdb_99": {"mode": "auto"}}}'
            )
        self.assertEqual(shows.lookup_mode("tv_tmdb_1"), "ask")
        self.assertEqual(shows.lookup_mode("tv_tmdb_99"), "auto")

    def test_unusable_rows_in_the_file_are_dropped(self):
        with open(self.path(), "w", encoding="utf-8") as handle:
            handle.write(
                '{"shows": {"tv_tmdb_1": {"mode": "auto", "title": "  Friends  "},'
                ' "tv_tmdb_2": {"mode": "declined"}, "tv_tmdb_3": "auto", "a/b": {"mode": "auto"},'
                ' "tv_tmdb_4": {"mode": "ask", "title": 5}}}'
            )
        self.assertEqual(
            shows.load_shows(),
            {"tv_tmdb_1": {"mode": "auto", "title": "Friends"}, "tv_tmdb_4": {"mode": "ask"}},
        )

    def test_a_corrupt_file_falls_back_to_the_last_good_copy(self):
        shows.save_mode("tv_tmdb_1", shows.MODE_AUTO, "A")
        shows.save_mode("tv_tmdb_2", shows.MODE_AUTO, "B")  # the first state is now the .bak
        with open(self.path(), "w", encoding="utf-8") as handle:
            handle.write("{not json")
        self.assertEqual(shows.lookup_mode("tv_tmdb_1"), "auto")
        self.assertTrue(os.path.exists(self.path() + ".corrupt"))

    def test_a_corrupt_file_without_a_copy_is_empty_not_fatal(self):
        with open(self.path(), "w", encoding="utf-8") as handle:
            handle.write("")
        self.assertEqual(shows.load_shows(), {})

    def test_a_failed_write_reports_false(self):
        with patch.object(shows, "write_json", return_value=False):
            self.assertFalse(shows.save_mode("tv_tmdb_1", shows.MODE_AUTO))
        self.assertIsNone(shows.lookup_mode("tv_tmdb_1"))


class BackupTests(_ProfileTempDir):
    def test_export_is_a_copy(self):
        shows.save_mode("tv_tmdb_1", shows.MODE_AUTO, "A")
        exported = shows.export_all()
        exported["tv_tmdb_1"]["mode"] = "ask"
        self.assertEqual(shows.lookup_mode("tv_tmdb_1"), "auto")

    def test_merge_adds_updates_and_keeps_the_rest(self):
        shows.save_mode("tv_tmdb_1", shows.MODE_AUTO, "A")
        shows.save_mode("tv_tmdb_2", shows.MODE_AUTO, "B")
        incoming = {
            "tv_tmdb_1": {"mode": "ask", "title": "A"},
            "tv_tmdb_3": {"mode": "auto", "title": "C"},
            "junk": "x",
            "tv_tmdb_4": {"mode": "sometimes"},
        }
        self.assertEqual(shows.merge_from_backup(incoming), (1, 1))
        self.assertEqual(shows.lookup_mode("tv_tmdb_1"), "ask")
        self.assertEqual(shows.lookup_mode("tv_tmdb_2"), "auto")
        self.assertEqual(shows.lookup_mode("tv_tmdb_3"), "auto")
        self.assertIsNone(shows.lookup_mode("tv_tmdb_4"))

    def test_the_backup_carries_never_offer(self):
        shows.save_mode("tv_tmdb_1", shows.MODE_NEVER, "A")
        exported = shows.export_all()
        self.assertEqual(exported["tv_tmdb_1"]["mode"], "never")
        shows.clear_all()
        self.assertEqual(shows.merge_from_backup(exported), (1, 0))
        self.assertEqual(shows.lookup_mode("tv_tmdb_1"), "never")

    def test_merge_keeps_a_local_title_the_backup_lacks(self):
        shows.save_mode("tv_tmdb_1", shows.MODE_AUTO, "Friends")
        shows.merge_from_backup({"tv_tmdb_1": {"mode": "ask"}})
        self.assertEqual(shows.list_entries()[0]["title"], "Friends")

    def test_merging_the_same_data_changes_nothing(self):
        shows.save_mode("tv_tmdb_1", shows.MODE_AUTO, "A")
        with patch.object(shows, "write_json") as write:
            self.assertEqual(shows.merge_from_backup(shows.export_all()), (0, 0))
        write.assert_not_called()

    def test_merge_ignores_non_dicts(self):
        self.assertEqual(shows.merge_from_backup(None), (0, 0))
        self.assertEqual(shows.merge_from_backup(["a"]), (0, 0))

    def test_the_profile_backup_round_trips_the_shows(self):
        shows.save_mode("tv_tmdb_1", shows.MODE_AUTO, "A")
        dump = os.path.join(self._tmp.name, "backup.json")
        addon = MagicMock()
        addon.getAddonInfo.return_value = "7.4.0"
        backup.export_to_path(addon, dump)
        shows.clear_all()
        summary, _note = backup.import_merge_from_path(addon, dump)
        self.assertEqual(shows.lookup_mode("tv_tmdb_1"), "auto")
        self.assertEqual(summary["autoplay_shows"], 1)

    def test_an_older_backup_without_shows_restores_fine(self):
        shows.save_mode("tv_tmdb_1", shows.MODE_AUTO, "A")
        dump = os.path.join(self._tmp.name, "backup.json")
        addon = MagicMock()
        addon.getAddonInfo.return_value = "7.3.4"
        backup.export_to_path(addon, dump)
        import json

        with open(dump, encoding="utf-8") as handle:
            data = json.load(handle)
        del data["next_episode_shows"]
        with open(dump, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        summary, _note = backup.import_merge_from_path(addon, dump)
        self.assertEqual(summary["autoplay_shows"], 0)
        self.assertEqual(shows.lookup_mode("tv_tmdb_1"), "auto")


class _Player:
    def __init__(self, total=1500.0):
        self.total = total

    def getTotalTime(self):
        return self.total

    def isPlayingVideo(self):
        return True


SETTINGS = {
    "next_episode_enabled": True,
    "next_episode_autoplay": False,
    "next_episode_lead_seconds": 45,
    "next_episode_still_watching": True,
    "next_episode_still_watching_after": 3,
    "next_episode_start_at_credits": False,
    "next_episode_hide_skip_dialogs": True,
    "next_episode_mark_watched": True,
    "next_episode_skip_watched": False,
    "next_episode_resume": True,
}


class HandlerTests(unittest.TestCase):
    """The service step with per-show autoplay; the lookup and the player are faked."""

    def setUp(self):
        self.monitor = types.SimpleNamespace(next_episode_state=None)
        self.ctx = types.SimpleNamespace(monitor=self.monitor, player=_Player(), icon_path="")
        self.settings = dict(SETTINGS)
        self.per_show = True
        self.modes = {}
        self.answers = []
        self.prompts = []
        self.plays = []
        self.play_result = True
        self.asked = []
        self.lookups = []
        self.guard_ask = False
        self.now = 1000.0
        stack = [
            patch.object(step, "get_addon", lambda: object()),
            patch.object(
                step, "addon_get_bool", lambda _a, key, default=False: self.settings.get(key, default)
            ),
            patch.object(
                step,
                "addon_get_int",
                lambda _a, key, default=0, minimum=None, maximum=None: self.settings.get(key, default),
            ),
            patch.object(step, "countdown_settings", lambda _a: (0, "Close")),
            patch.object(step, "per_show_autoplay_enabled", lambda _a: self.per_show),
            patch.object(step, "lookup_mode", lambda key: self.modes.get(key)),
            patch.object(step, "_upnext_enabled", lambda: False),
            patch.object(step, "_still_watching_due", lambda *_a: self.guard_ask),
            patch.object(step, "_arm_stop_watchdog", lambda *a: None),
            patch.object(step, "_stand_down_watchdog", lambda *a: None),
            patch.object(step, "show_next_episode_prompt", self._prompt),
            patch.object(step, "play_next", self._play),
            patch.object(step, "schedule_mark_watched", lambda *a: None),
            patch.object(step, "_start_lookup", lambda *a, **k: self.lookups.append((a, k))),
            patch.object(step.time, "monotonic", lambda: self.now),
            patch.object(step, "log"),
            patch.object(step, "log_error"),
            patch.object(ui, "ask_autoplay_for_show", lambda *a: self.asked.append(a)),
        ]
        for p in stack:
            p.start()
            self.addCleanup(p.stop)

    def _prompt(
        self, addon, player, item, start, total, still_watching=False, timed=False, end_action="Close"
    ):
        self.prompts.append(still_watching)
        return self.answers.pop(0) if self.answers else None

    def _play(self, item, resume=True):
        self.plays.append(item)
        return self.play_result

    def found_state(self, video="ep.mkv", key="tv_tmdb_1", title="Friends"):
        state = NextEpisodeState(
            video=video,
            lookup=LOOKUP_FOUND,
            next_item=NEXT,
            current_episode_id=7,
            current_playcount=1,
            show_key=key,
            show_title=title,
        )
        self.monitor.next_episode_state = state
        return state

    def tick(self, current_time, video="ep.mkv"):
        return step.handle_next_episode(
            self.ctx,
            video=video,
            playback_type="episode",
            current_time=current_time,
            player_item={"type": "episode", "id": 7},
        )

    # --- which way a show goes -------------------------------------------------

    def test_a_show_set_to_autoplay_starts_by_itself_while_global_autoplay_is_off(self):
        self.found_state()
        self.modes["tv_tmdb_1"] = shows.MODE_AUTO
        result = self.tick(1460.0)
        self.assertTrue(result.switched)
        self.assertEqual((self.prompts, self.plays), ([], [NEXT]))
        self.assertTrue(self.monitor.next_episode_chain.autoplay_pending)

    def test_a_show_set_to_ask_first_still_prompts_when_global_autoplay_is_on(self):
        self.settings["next_episode_autoplay"] = True
        self.found_state()
        self.modes["tv_tmdb_1"] = shows.MODE_ASK
        self.answers = [False]
        self.tick(1460.0)
        self.assertEqual((self.prompts, self.plays), ([False], []))

    def test_a_show_set_to_never_offer_gets_no_prompt_and_no_autoplay(self):
        self.settings["next_episode_autoplay"] = True
        self.found_state()
        self.modes["tv_tmdb_1"] = shows.MODE_NEVER
        result = self.tick(1460.0)
        self.assertEqual((self.prompts, self.plays), ([], []))
        self.assertFalse(result.switched)

    def test_a_show_set_to_never_offer_leaves_the_skip_dialogs_alone(self):
        self.found_state()
        self.modes["tv_tmdb_1"] = shows.MODE_NEVER
        self.assertFalse(self.tick(1460.0).hide_skip_dialogs)

    def test_a_show_that_is_not_set_to_never_offer_still_hides_the_skip_dialogs(self):
        self.found_state()
        self.answers = [None]
        self.assertTrue(self.tick(1460.0).hide_skip_dialogs)

    def test_never_offer_is_ignored_when_per_show_is_off(self):
        self.per_show = False
        self.found_state()
        self.modes["tv_tmdb_1"] = shows.MODE_NEVER
        self.answers = [False]
        self.tick(1460.0)
        self.assertEqual(self.prompts, [False])

    def test_an_unidentified_show_is_not_affected_by_never_offer(self):
        self.found_state(key=None, title="")
        self.modes["tv_tmdb_1"] = shows.MODE_NEVER
        self.answers = [False]
        self.tick(1460.0)
        self.assertEqual(self.prompts, [False])

    def test_another_show_is_not_affected_by_never_offer(self):
        self.found_state(key="tv_tmdb_2")
        self.modes["tv_tmdb_1"] = shows.MODE_NEVER
        self.answers = [False]
        self.tick(1460.0)
        self.assertEqual(self.prompts, [False])

    def test_switching_never_offer_on_and_off_applies_to_the_running_episode(self):
        self.found_state()
        self.modes["tv_tmdb_1"] = shows.MODE_NEVER
        self.tick(1460.0)
        self.assertEqual(self.prompts, [])
        self.now += 60
        del self.modes["tv_tmdb_1"]
        self.answers = [None]
        self.tick(1470.0)
        self.assertEqual(self.prompts, [False])
        self.now += 60
        self.modes["tv_tmdb_1"] = shows.MODE_NEVER
        self.tick(1480.0)
        self.assertEqual(self.prompts, [False])

    def test_a_show_without_a_choice_follows_global_autoplay(self):
        self.settings["next_episode_autoplay"] = True
        self.found_state()
        self.assertTrue(self.tick(1460.0).switched)
        self.assertEqual(self.prompts, [])

    def test_a_show_without_a_choice_prompts_when_global_autoplay_is_off(self):
        self.found_state()
        self.answers = [False]
        self.tick(1460.0)
        self.assertEqual(self.prompts, [False])

    def test_saved_choices_are_ignored_when_per_show_is_off(self):
        self.per_show = False
        self.found_state()
        self.modes["tv_tmdb_1"] = shows.MODE_AUTO
        self.answers = [False]
        self.tick(1460.0)
        self.assertEqual((self.prompts, self.plays), ([False], []))

    def test_an_unidentified_show_follows_global_autoplay(self):
        self.found_state(key=None, title="")
        self.modes["tv_tmdb_1"] = shows.MODE_AUTO
        self.answers = [False]
        self.tick(1460.0)
        self.assertEqual(self.prompts, [False])

    def test_a_choice_changed_in_the_manage_window_applies_to_the_running_episode(self):
        self.found_state()
        self.answers = [None]
        self.tick(1460.0)
        self.assertEqual(self.plays, [])
        self.now += 60
        self.modes["tv_tmdb_1"] = shows.MODE_AUTO
        self.assertTrue(self.tick(1470.0).switched)

    def test_a_show_set_to_autoplay_still_gets_the_still_watching_question(self):
        self.found_state()
        self.modes["tv_tmdb_1"] = shows.MODE_AUTO
        self.guard_ask = True
        self.answers = [True]
        self.tick(1460.0)
        self.assertEqual(self.prompts, [True])
        self.assertEqual(len(self.plays), 1)

    # --- the question after Play now ------------------------------------------

    def test_play_now_for_a_show_without_a_choice_queues_the_question(self):
        self.found_state()
        self.answers = [True]
        self.assertTrue(self.tick(1460.0).switched)
        self.assertEqual(
            self.monitor.next_episode_remember,
            {"key": "tv_tmdb_1", "title": "Friends", "video": "ep.mkv", "mono": 1000.0},
        )

    def test_no_question_when_the_show_already_has_a_choice(self):
        self.found_state()
        self.modes["tv_tmdb_1"] = shows.MODE_ASK
        self.answers = [True]
        self.tick(1460.0)
        self.assertFalse(getattr(self.monitor, "next_episode_remember", None))

    def test_no_question_when_per_show_is_off(self):
        self.per_show = False
        self.found_state()
        self.answers = [True]
        self.tick(1460.0)
        self.assertFalse(getattr(self.monitor, "next_episode_remember", None))

    def test_no_question_when_global_autoplay_is_on(self):
        self.settings["next_episode_autoplay"] = True
        self.found_state()
        self.guard_ask = True  # the "still watching?" prompt: Play now is not a choice about the show
        self.answers = [True]
        self.tick(1460.0)
        self.assertFalse(getattr(self.monitor, "next_episode_remember", None))

    def test_no_question_after_continue_with_global_autoplay_off(self):
        self.found_state()
        self.guard_ask = True  # the "still watching?" question, asked although nothing autoplays
        self.answers = [True]
        self.assertTrue(self.tick(1460.0).switched)
        self.assertEqual(self.prompts, [True])
        self.assertFalse(getattr(self.monitor, "next_episode_remember", None))

    def test_no_question_for_an_unidentified_show(self):
        self.found_state(key=None, title="")
        self.answers = [True]
        self.tick(1460.0)
        self.assertFalse(getattr(self.monitor, "next_episode_remember", None))

    def test_no_question_when_the_next_episode_did_not_start(self):
        self.found_state()
        self.play_result = False
        self.answers = [True]
        self.assertFalse(self.tick(1460.0).switched)
        self.assertFalse(getattr(self.monitor, "next_episode_remember", None))

    def test_closing_the_prompt_queues_nothing(self):
        self.found_state()
        self.answers = [False]
        self.tick(1460.0)
        self.assertFalse(getattr(self.monitor, "next_episode_remember", None))

    def queue(self, video="ep.mkv"):
        self.monitor.next_episode_remember = {
            "key": "tv_tmdb_1",
            "title": "Friends",
            "video": video,
            "mono": self.now,
        }

    def test_the_question_waits_until_the_next_episode_is_playing(self):
        self.queue()
        self.tick(3.0, video="next.mkv")
        self.assertEqual(self.asked, [])
        self.assertTrue(self.monitor.next_episode_remember)
        self.tick(step.REMEMBER_DELAY_S + 1, video="next.mkv")
        self.assertEqual(len(self.asked), 1)
        self.assertEqual(self.asked[0][2:], ("tv_tmdb_1", "Friends"))
        self.assertIsNone(self.monitor.next_episode_remember)

    def test_it_is_asked_only_once(self):
        self.queue()
        self.tick(10.0, video="next.mkv")
        self.tick(11.0, video="next.mkv")
        self.assertEqual(len(self.asked), 1)

    def test_it_is_not_asked_while_the_old_episode_still_plays(self):
        self.queue()
        self.found_state(video="ep.mkv")
        self.tick(1400.0, video="ep.mkv")
        self.assertEqual(self.asked, [])
        self.assertTrue(self.monitor.next_episode_remember)

    def test_it_is_dropped_when_no_episode_followed(self):
        self.queue()
        self.now += step.REMEMBER_EXPIRES_S + 1
        self.tick(30.0, video="other.mkv")
        self.assertEqual(self.asked, [])
        self.assertIsNone(self.monitor.next_episode_remember)

    def test_it_is_dropped_when_a_choice_was_saved_meanwhile(self):
        self.queue()
        self.modes["tv_tmdb_1"] = shows.MODE_AUTO
        self.tick(20.0, video="next.mkv")
        self.assertEqual(self.asked, [])
        self.assertIsNone(self.monitor.next_episode_remember)

    def test_it_is_dropped_when_per_show_was_turned_off_meanwhile(self):
        self.queue()
        self.per_show = False
        self.tick(20.0, video="next.mkv")
        self.assertEqual(self.asked, [])
        self.assertIsNone(self.monitor.next_episode_remember)

    # --- finding the show ------------------------------------------------------

    def test_the_lookup_is_asked_to_identify_the_show_only_when_per_show_is_on(self):
        self.tick(10.0)
        self.assertTrue(self.lookups[0][1]["resolve_show"])
        self.monitor.next_episode_state = None
        self.per_show = False
        self.tick(10.0)
        self.assertFalse(self.lookups[1][1]["resolve_show"])


class RunLookupTests(unittest.TestCase):
    def run_lookup(self, identity=None, resolve=True, raises=None, item=None):
        state = NextEpisodeState(video="v")
        current = {"id": 7, "playcount": 1, "tvshowid": 42}
        patches = [
            patch.object(step, "describe_current_episode", return_value=current),
            patch.object(step, "find_next_episode", return_value=NEXT),
            patch.object(step, "log"),
        ]
        fake = MagicMock(return_value=identity, side_effect=raises)
        with patch("remote_library.library_title_identity", fake):
            for p in patches:
                p.start()
            try:
                step.run_lookup(state, item if item is not None else {"id": 7}, False, resolve)
            finally:
                for p in patches:
                    p.stop()
        return state, fake

    def test_the_show_is_identified_with_the_library_show_id(self):
        state, fake = self.run_lookup({"type": "episode", "tmdb_id": 1396, "title": "Breaking Bad"})
        self.assertEqual((state.show_key, state.show_title), ("tv_tmdb_1396", "Breaking Bad"))
        asked = fake.call_args.args[0]
        self.assertEqual((asked["tvshowid"], asked["type"]), (42, "episode"))
        self.assertEqual(state.lookup, LOOKUP_FOUND)

    def test_the_player_title_fills_in_when_the_library_has_none(self):
        state, _fake = self.run_lookup(
            {"type": "episode", "tmdb_id": 5, "title": ""}, item={"showtitle": " Arrow "}
        )
        self.assertEqual(state.show_title, "Arrow")

    def test_nothing_is_looked_up_when_per_show_is_off(self):
        state, fake = self.run_lookup({"type": "episode", "tmdb_id": 1}, resolve=False)
        fake.assert_not_called()
        self.assertIsNone(state.show_key)
        self.assertEqual(state.lookup, LOOKUP_FOUND)

    def test_an_unknown_show_has_no_key(self):
        state, _fake = self.run_lookup({"type": "episode", "tmdb_id": None, "imdb_id": None})
        self.assertIsNone(state.show_key)

    def test_a_failure_to_identify_does_not_lose_the_next_episode(self):
        state, _fake = self.run_lookup(raises=RuntimeError("rpc"))
        self.assertIsNone(state.show_key)
        self.assertEqual(state.lookup, LOOKUP_FOUND)
        self.assertEqual(state.next_item, NEXT)


class _FakeModal:
    """Stands in for skippy_editor_modal_skin so the windows can be driven by a script."""

    def __init__(self, yesno=True, picks=()):
        self.yesno = yesno
        self.picks = list(picks)
        self.pick_calls = []
        self.yesno_calls = []

    def sidecar_overwrite_yesno_show(self, heading, message, yes, no):
        self.yesno_calls.append((heading, message, yes, no))
        return self.yesno

    def show_editor_list_pick(self, heading, options, subtitle="", preselect=0, cancel_label=None):
        self.pick_calls.append((heading, list(options), preselect))
        return self.picks.pop(0) if self.picks else -1

    show_panel_list_pick = show_editor_list_pick


class _UiTests(_ProfileTempDir):
    def install(self, modal):
        fake = types.ModuleType("skippy_editor_modal_skin")
        fake.sidecar_overwrite_yesno_show = modal.sidecar_overwrite_yesno_show
        fake.show_editor_list_pick = modal.show_editor_list_pick
        panel = types.ModuleType("skippy_panel_ui")
        panel.show_panel_list_pick = modal.show_panel_list_pick
        patcher = patch.dict(sys.modules, {"skippy_editor_modal_skin": fake, "skippy_panel_ui": panel})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.toasts = []
        for p in (
            patch.object(ui, "get_addon", lambda: None),
            patch.object(ui, "notify_skippy", lambda addon, message, title="": self.toasts.append(message)),
            patch.object(ui, "log"),
        ):
            p.start()
            self.addCleanup(p.stop)


class QuestionTests(_UiTests):
    def ctx(self, playing=True):
        player = types.SimpleNamespace(isPlayingVideo=lambda: playing)
        monitor = types.SimpleNamespace(skip_dialog_modal_active=False)
        return types.SimpleNamespace(monitor=monitor, player=player, icon_path="")

    def ask(self, modal, ctx=None, title="Friends"):
        self.install(modal)
        ctx = ctx or self.ctx()
        with patch.object(ui.xbmcgui, "Dialog") as dialog:
            ui.ask_autoplay_for_show(ctx, None, "tv_tmdb_1", title)
        return ctx, dialog

    def test_yes_saves_autoplay_and_says_so(self):
        modal = _FakeModal(yesno=True)
        _ctx, dialog = self.ask(modal)
        self.assertEqual(shows.lookup_mode("tv_tmdb_1"), "auto")
        dialog.return_value.notification.assert_called_once()
        self.assertIn("Friends", modal.yesno_calls[0][1])

    def test_keep_asking_is_remembered_too(self):
        modal = _FakeModal(yesno=False)
        _ctx, dialog = self.ask(modal)
        self.assertEqual(shows.lookup_mode("tv_tmdb_1"), "ask")
        dialog.return_value.notification.assert_not_called()

    def test_the_buttons_say_what_they_do(self):
        modal = _FakeModal()
        self.ask(modal)
        _heading, _message, yes, no = modal.yesno_calls[0]
        self.assertEqual((yes, no), ("Yes", "Keep asking"))

    def test_a_missing_title_gets_the_general_wording(self):
        modal = _FakeModal()
        self.ask(modal, title="")
        self.assertIn("this show", modal.yesno_calls[0][1])

    def test_the_modal_flag_is_held_only_while_it_is_open(self):
        modal = _FakeModal()
        ctx = self.ctx()
        seen = []
        original = modal.sidecar_overwrite_yesno_show

        def spy(*args):
            seen.append(ctx.monitor.skip_dialog_modal_active)
            return original(*args)

        modal.sidecar_overwrite_yesno_show = spy
        self.ask(modal, ctx=ctx)
        self.assertEqual(seen, [True])
        self.assertFalse(ctx.monitor.skip_dialog_modal_active)

    def test_nothing_is_asked_when_playback_has_ended(self):
        modal = _FakeModal()
        self.ask(modal, ctx=self.ctx(playing=False))
        self.assertEqual(modal.yesno_calls, [])
        self.assertIsNone(shows.lookup_mode("tv_tmdb_1"))

    def test_a_broken_modal_falls_back_to_the_stock_yes_no(self):
        modal = _FakeModal()

        def boom(*args):
            raise RuntimeError("skin")

        modal.sidecar_overwrite_yesno_show = boom
        self.install(modal)
        with patch.object(ui.xbmcgui, "Dialog") as dialog:
            dialog.return_value.yesno.return_value = True
            ui.ask_autoplay_for_show(self.ctx(), None, "tv_tmdb_1", "Friends")
        self.assertEqual(shows.lookup_mode("tv_tmdb_1"), "auto")


class ManageTests(_UiTests):
    def test_the_rows_name_the_show_and_its_choice(self):
        self.assertEqual(
            ui.format_entry_label(None, {"title": "Friends", "mode": "auto"}),
            "Friends — Play automatically",
        )
        self.assertEqual(
            ui.format_entry_label(None, {"title": "Arrow", "mode": "ask"}), "Arrow — Ask first"
        )

    def test_the_first_row_adds_a_show_and_the_rest_are_the_saved_shows(self):
        shows.save_mode("tv_tmdb_1", shows.MODE_AUTO, "Friends")
        modal = _FakeModal(picks=[-1])
        self.install(modal)
        ui.show_manage_next_episode_shows_modal()
        _heading, options, _pre = modal.pick_calls[0]
        self.assertEqual(options, ["Add a show...", ("Friends", "Play automatically")])

    def test_a_row_is_the_show_at_the_left_and_its_choice_at_the_right(self):
        self.assertEqual(
            ui.entry_row(None, {"title": "Friends", "mode": "auto"}), ("Friends", "Play automatically")
        )
        self.assertEqual(ui.entry_row(None, {"title": "Arrow", "mode": "never"}), ("Arrow", "Never offer"))
        self.assertEqual(ui.entry_row(None, {"key": "tv_tmdb_1", "mode": "ask"}), ("tv_tmdb_1", "Ask first"))

    def test_changing_a_choice(self):
        shows.save_mode("tv_tmdb_1", shows.MODE_AUTO, "Friends")
        modal = _FakeModal(picks=[1, 1, -1])  # the show, Ask first, close
        self.install(modal)
        ui.show_manage_next_episode_shows_modal()
        self.assertEqual(shows.lookup_mode("tv_tmdb_1"), "ask")
        self.assertEqual(shows.list_entries()[0]["title"], "Friends")
        heading, options, preselect = modal.pick_calls[1]
        self.assertEqual(
            (heading, options, preselect),
            ("Friends", ["Play automatically", "Ask first", "Never offer", "Forget this show"], 0),
        )

    def test_a_show_can_be_set_to_never_offer(self):
        shows.save_mode("tv_tmdb_1", shows.MODE_AUTO, "Friends")
        modal = _FakeModal(picks=[1, 2, -1])
        self.install(modal)
        ui.show_manage_next_episode_shows_modal()
        self.assertEqual(shows.lookup_mode("tv_tmdb_1"), "never")
        self.assertEqual(shows.list_entries()[0]["title"], "Friends")

    def test_the_row_of_a_show_set_to_never_offer_says_so(self):
        self.assertEqual(
            ui.format_entry_label(None, {"title": "Arrow", "mode": "never"}), "Arrow — Never offer"
        )

    def test_never_offer_is_preselected_for_such_a_show(self):
        shows.save_mode("tv_tmdb_1", shows.MODE_NEVER, "Friends")
        modal = _FakeModal(picks=[1, -1, -1])
        self.install(modal)
        ui.show_manage_next_episode_shows_modal()
        self.assertEqual(modal.pick_calls[1][2], 2)

    def test_a_new_show_can_be_set_to_never_offer(self):
        library = [{"tvshowid": 4, "title": "Arrow"}]
        self.add_show(library, ("tv_tmdb_1", "Arrow"), [0, 0, 2, -1])
        self.assertEqual(shows.lookup_mode("tv_tmdb_1"), "never")

    def test_a_pick_beyond_the_modes_for_a_new_show_saves_nothing(self):
        library = [{"tvshowid": 4, "title": "Arrow"}]
        self.add_show(library, ("tv_tmdb_1", "Arrow"), [0, 0, 3, -1])
        self.assertEqual(shows.load_shows(), {})

    def test_a_pick_beyond_the_modes_changes_nothing(self):
        shows.save_mode("tv_tmdb_1", shows.MODE_AUTO, "Friends")
        modal = _FakeModal(picks=[1, 7, -1])
        self.install(modal)
        ui.show_manage_next_episode_shows_modal()
        self.assertEqual(shows.lookup_mode("tv_tmdb_1"), "auto")

    def test_the_current_choice_is_preselected(self):
        shows.save_mode("tv_tmdb_1", shows.MODE_ASK, "Friends")
        modal = _FakeModal(picks=[1, -1, -1])
        self.install(modal)
        ui.show_manage_next_episode_shows_modal()
        self.assertEqual(modal.pick_calls[1][2], 1)

    def test_forgetting_a_show(self):
        shows.save_mode("tv_tmdb_1", shows.MODE_AUTO, "Friends")
        modal = _FakeModal(picks=[1, 3, -1])
        self.install(modal)
        ui.show_manage_next_episode_shows_modal()
        self.assertIsNone(shows.lookup_mode("tv_tmdb_1"))
        self.assertEqual(self.toasts, ["Forgot the autoplay choice for Friends"])
        self.assertEqual(modal.pick_calls[2][1], ["Add a show..."])

    def test_backing_out_of_a_choice_changes_nothing(self):
        shows.save_mode("tv_tmdb_1", shows.MODE_AUTO, "Friends")
        modal = _FakeModal(picks=[1, -1, -1])
        self.install(modal)
        ui.show_manage_next_episode_shows_modal()
        self.assertEqual(shows.lookup_mode("tv_tmdb_1"), "auto")

    def add_show(self, shows_in_library, identity, picks):
        """Drive the Manage window: ``picks`` are the answers of every list, in order."""
        modal = _FakeModal(picks=picks)
        self.install(modal)
        for p in (
            patch.object(ui, "_library_shows", return_value=shows_in_library),
            patch.object(ui, "_identify_show", return_value=identity),
        ):
            p.start()
            self.addCleanup(p.stop)
        ui.show_manage_next_episode_shows_modal()
        return modal

    def test_adding_a_show_from_the_library(self):
        library = [{"tvshowid": 4, "title": "Arrow"}, {"tvshowid": 5, "title": "Friends"}]
        # add a show, pick Friends, Play automatically, close
        modal = self.add_show(library, ("tv_tmdb_1668", "Friends"), [0, 1, 0, -1])
        self.assertEqual(shows.lookup_mode("tv_tmdb_1668"), "auto")
        self.assertEqual(shows.list_entries()[0]["title"], "Friends")
        self.assertEqual(modal.pick_calls[1][1], ["Arrow", "Friends"])
        self.assertEqual(modal.pick_calls[2][1], ["Play automatically", "Ask first", "Never offer"])

    def test_the_library_list_is_the_panel_not_the_stock_select(self):
        library = [{"tvshowid": 4, "title": "Arrow"}]
        with patch.object(ui.xbmcgui, "Dialog") as dialog:
            self.add_show(library, ("tv_tmdb_1", "Arrow"), [0, -1, -1])
        dialog.assert_not_called()

    def test_a_new_show_can_be_set_to_ask_first(self):
        library = [{"tvshowid": 4, "title": "Arrow"}]
        self.add_show(library, ("tv_tmdb_1", "Arrow"), [0, 0, 1, -1])
        self.assertEqual(shows.lookup_mode("tv_tmdb_1"), "ask")

    def test_cancelling_the_choice_of_a_new_show_saves_nothing(self):
        library = [{"tvshowid": 4, "title": "Arrow"}]
        self.add_show(library, ("tv_tmdb_1", "Arrow"), [0, 0, -1, -1])
        self.assertEqual(shows.load_shows(), {})

    def test_cancelling_the_library_list_saves_nothing(self):
        library = [{"tvshowid": 4, "title": "Arrow"}]
        modal = self.add_show(library, ("tv_tmdb_1", "Arrow"), [0, -1, -1])
        self.assertEqual(shows.load_shows(), {})
        # Manage list, library list, Manage list again (closed)
        self.assertEqual(len(modal.pick_calls), 3)

    def test_an_empty_library_says_so(self):
        self.add_show([], ("x", "y"), [0, -1])
        self.assertEqual(self.toasts, ["No TV shows in your library yet."])

    def test_a_show_without_an_id_cannot_be_saved(self):
        library = [{"tvshowid": 4, "title": "Home Video"}]
        self.add_show(library, (None, "Home Video"), [0, 0, -1])
        self.assertEqual(self.toasts, ["Could not tell which show that is."])
        self.assertEqual(shows.load_shows(), {})

    def test_a_list_that_fails_to_open_closes_the_window_quietly(self):
        modal = _FakeModal()

        def boom(*args, **kwargs):
            raise RuntimeError("skin")

        modal.show_panel_list_pick = boom
        self.install(modal)
        ui.show_manage_next_episode_shows_modal()
        self.assertEqual(modal.pick_calls, [])


class LibraryShowTests(unittest.TestCase):
    def test_rows_without_an_id_or_title_are_skipped(self):
        rows = {
            "result": {
                "tvshows": [
                    {"tvshowid": 4, "title": " Arrow "},
                    {"tvshowid": "x", "title": "Bad id"},
                    {"tvshowid": 6, "title": ""},
                    {"tvshowid": 7, "label": "Labelled"},
                ]
            }
        }
        with patch.object(ui, "jsonrpc", return_value=rows) as rpc:
            found = ui._library_shows()
        self.assertEqual(
            found, [{"tvshowid": 4, "title": "Arrow"}, {"tvshowid": 7, "title": "Labelled"}]
        )
        self.assertEqual(rpc.call_args.args[0], "VideoLibrary.GetTVShows")

    def test_no_answer_means_no_shows(self):
        with patch.object(ui, "jsonrpc", return_value={}):
            self.assertEqual(ui._library_shows(), [])

    def test_a_show_is_identified_from_its_library_id(self):
        identity = {"type": "episode", "tmdb_id": 1396, "title": "Breaking Bad"}
        with patch("remote_library.library_title_identity", return_value=identity) as fake:
            key, title = ui._identify_show({"tvshowid": 9, "title": "Breaking bad"})
        self.assertEqual((key, title), ("tv_tmdb_1396", "Breaking Bad"))
        self.assertEqual(fake.call_args.args[0]["tvshowid"], 9)


def _po_entries(pack):
    path = os.path.join(ROOT, "resources", "language", pack, "strings.po")
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    return {
        int(sid): msgstr
        for sid, msgstr in re.findall(r'msgctxt "#(\d+)"\nmsgid ".*"\nmsgstr "(.*)"', text)
    }


class NeverOfferStringsTests(unittest.TestCase):
    def packs(self):
        langs = os.path.join(ROOT, "resources", "language")
        return sorted(p for p in os.listdir(langs) if os.path.exists(os.path.join(langs, p, "strings.po")))

    def test_the_mode_word_is_in_every_pack_and_translated(self):
        english = _po_entries("resource.language.en_gb")[47145]
        self.assertEqual(english, "Never offer")
        for pack in self.packs():
            word = _po_entries(pack).get(47145)
            self.assertTrue(word, pack)
            if not pack.endswith("en_gb"):
                self.assertNotEqual(word, english, pack)

    def test_the_help_texts_name_the_mode_the_way_the_pack_does(self):
        for pack in self.packs():
            entries = _po_entries(pack)
            for sid in (47083, 47085):
                self.assertIn(entries[47145], entries[sid], (pack, sid))

    def test_the_mode_word_is_what_the_window_shows(self):
        self.assertEqual(ui.mode_word(None, shows.MODE_NEVER), "Never offer")


class RunScriptTests(_ProfileTempDir):
    def test_the_manage_and_clear_commands_are_routed(self):
        with open(os.path.join(ROOT, "skippy_runscript_entry.py"), encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn('command == "manage_next_episode_shows"', text)
        self.assertIn('command == "clear_next_episode_shows"', text)

    def test_clearing_reports_how_many_were_forgotten(self):
        import skippy_runscript_entry as entry

        shows.save_mode("tv_tmdb_1", shows.MODE_AUTO)
        shows.save_mode("tv_tmdb_2", shows.MODE_ASK)
        notes = []
        with patch.object(entry, "_addon", lambda: None), patch(
            "settings_utils.notify_skippy", lambda addon, message, title="": notes.append(message)
        ):
            self.run_command(entry, "clear_next_episode_shows")
            self.run_command(entry, "clear_next_episode_shows")
        self.assertEqual(
            notes,
            ["Cleared 2 saved autoplay choice(s).", "No saved autoplay choices to clear."],
        )

    def run_command(self, entry, command):
        with patch.object(sys, "argv", ["default.py", command]):
            entry.main()


if __name__ == "__main__":
    unittest.main()
