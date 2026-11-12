# -*- coding: utf-8 -*-
"""Binge mode: runs of episodes, which intro and recap are skipped, and the playback hook."""

import unittest
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import binge_mode as binge  # noqa: E402
from playback_identity import show_folder_name, title_identity  # noqa: E402
from segment_item import SegmentItem  # noqa: E402
from segment_types import seeded_builtin_types, set_catalog_for_tests  # noqa: E402

GAP = 600.0


def _addon(**settings):
    addon = MagicMock()
    addon.getSetting.side_effect = lambda key: settings.get(key, "")
    return addon


class TitleIdentityTests(unittest.TestCase):
    def test_library_show_uses_its_id(self):
        item = {"tvshowid": 42, "showtitle": "The Office"}
        self.assertEqual(title_identity(item, "/tv/x.mkv", "episode"), ("tv:42", "The Office"))

    def test_show_title_without_library_id(self):
        item = {"tvshowid": -1, "showtitle": "The  Office"}
        self.assertEqual(title_identity(item, "", "episode"), ("show:the office", "The Office"))

    def test_folder_name_for_files_outside_the_library(self):
        path = "nfs://nas/tv/Doctor Who (2005)/Season 03/Doctor.Who.S03E01.mkv"
        self.assertEqual(title_identity({}, path, "episode"), ("show:doctor who (2005)", "Doctor Who (2005)"))
        self.assertEqual(show_folder_name("C:\\TV\\Arrow\\S02\\Arrow.S02E05.mkv"), "Arrow")
        self.assertEqual(show_folder_name("/tv/Lost/Specials/Lost.S00E01.mkv"), "Lost")
        self.assertEqual(show_folder_name("/tv/Lost/Staffel 1/x.mkv"), "Lost")
        self.assertEqual(show_folder_name("x.mkv"), "")

    def test_movies_and_unknowns(self):
        self.assertEqual(title_identity({"title": "Dune"}, "/m/Dune.mkv", "movie"), ("movie:dune", "Dune"))
        self.assertEqual(title_identity({}, "", "movie"), (None, ""))
        self.assertEqual(title_identity({}, "x.mkv", "episode"), (None, ""))
        self.assertEqual(title_identity(None, "", ""), (None, ""))


class RunTests(unittest.TestCase):
    def setUp(self):
        self.monitor = MagicMock(spec=[])

    def play(self, video, show="tv:1", now=0.0, kind="episode"):
        return binge.note_playback(self.monitor, video, kind, show, "Show", GAP, now=now)

    def test_episodes_in_a_row_count_up(self):
        self.assertEqual(self.play("e1", now=0), 1)
        self.assertEqual(self.play("e1", now=500), 1)  # ticks of the same episode
        self.assertEqual(self.play("e2", now=600), 2)
        self.assertEqual(self.play("e2", now=1100), 2)
        self.assertEqual(self.play("e3", now=1200), 3)
        self.assertEqual(binge.binge_position(self.monitor), 3)

    def test_another_show_or_a_film_starts_over(self):
        self.play("e1", now=0)
        self.play("e2", now=10)
        self.assertEqual(self.play("x1", show="tv:2", now=20), 1)
        self.assertEqual(self.play("m", show="movie:dune", kind="movie", now=30), 0)
        self.assertEqual(self.play("x2", show="tv:2", now=40), 1)

    def test_a_long_pause_starts_over(self):
        self.play("e1", now=0)
        self.assertEqual(self.play("e2", now=GAP + 1), 1)
        self.assertEqual(self.play("e2", now=3 * GAP), 1)  # same file the next day

    def test_unknown_show_is_not_a_run(self):
        self.assertEqual(self.play("e1", show=None), 0)
        self.assertEqual(self.play("e2", now=5), 1)

    def test_no_monitor(self):
        self.assertEqual(binge.note_playback(None, "e", "episode", "tv:1"), 0)
        self.assertEqual(binge.binge_position(MagicMock(spec=[])), 0)


class BehaviorTests(unittest.TestCase):
    def test_intro_plays_first_then_skips(self):
        for mode in ("ask", "auto", "never"):
            self.assertEqual(binge.binge_behavior("intro", mode, 1, True, True)[0], "never")
            self.assertEqual(binge.binge_behavior("intro", mode, 2, True, True)[0], "auto")
        self.assertEqual(binge.binge_behavior("intro", "ask", 2, True, True), ("auto", binge.REASON_LATER))
        self.assertEqual(binge.binge_behavior("intro", "never", 1, True, True), ("never", None))

    def test_recap_only_with_the_option_and_after_the_first(self):
        self.assertEqual(binge.binge_behavior("recap", "ask", 1, True, True), ("ask", None))
        self.assertEqual(binge.binge_behavior("recap", "ask", 2, True, True), ("auto", binge.REASON_LATER))
        self.assertEqual(binge.binge_behavior("recap", "ask", 2, True, False), ("ask", None))

    def test_other_types_off_and_no_run_are_untouched(self):
        self.assertEqual(binge.binge_behavior("credits", "ask", 3, True, True), ("ask", None))
        self.assertEqual(binge.binge_behavior("intro", "ask", 3, False, True), ("ask", None))
        self.assertEqual(binge.binge_behavior("intro", "ask", 0, True, True), ("ask", None))

    def test_settings(self):
        self.assertEqual(binge.binge_settings(_addon()), (False, True, 600.0))
        self.assertEqual(
            binge.binge_settings(_addon(binge_mode_enabled="true", binge_mode_skip_recap="false",
                                        binge_mode_gap_minutes="25")),
            (True, False, 1500.0),
        )
        self.assertEqual(binge.binge_settings(_addon(binge_mode_gap_minutes="0"))[2], 60.0)

    def test_apply_uses_the_catalog_type_and_the_run(self):
        set_catalog_for_tests(seeded_builtin_types())
        self.addCleanup(set_catalog_for_tests, None)
        monitor = MagicMock(spec=[])
        binge.note_playback(monitor, "e1", "episode", "tv:1", "S", GAP, now=0)
        binge.note_playback(monitor, "e2", "episode", "tv:1", "S", GAP, now=5)
        on = _addon(binge_mode_enabled="true")
        self.assertEqual(binge.apply_binge_mode(monitor, on, "episode", "Opening", "ask"), "auto")
        self.assertEqual(binge.apply_binge_mode(monitor, on, "episode", "previously on", "ask"), "auto")
        self.assertEqual(binge.apply_binge_mode(monitor, on, "movie", "intro", "ask"), "ask")
        self.assertEqual(binge.apply_binge_mode(monitor, _addon(), "episode", "intro", "ask"), "ask")


class PlaybackHookTests(unittest.TestCase):
    """The skip loop asks binge mode after the segment type and the per-title choice."""

    def _monitor(self, segment, position):
        monitor = MagicMock()
        monitor.playback_ready = True
        monitor.prompted = set()
        monitor.recently_dismissed = set()
        monitor.skipped_to_nested_segment = {}
        monitor.last_skipped_seg_id = None
        monitor.last_skipped_seg_bounds = None
        monitor.current_segments = [segment]
        monitor._last_log_state = {}
        monitor.binge_run = binge.BingeRun(show_key="tv:1", video="/v.mkv", position=position)
        return monitor

    def run_tick(self, position, enabled="true"):
        import service_loop_skip as mod

        set_catalog_for_tests(seeded_builtin_types())
        self.addCleanup(set_catalog_for_tests, None)
        intro = SegmentItem(0.0, 60.0, "intro", source="xml")
        monitor = self._monitor(intro, position)
        ctx = MagicMock()
        ctx.monitor = monitor
        ctx.should_suppress_segment_dialog = MagicMock(return_value=False)
        addon = _addon(binge_mode_enabled=enabled, enable_skip_episodes="true")
        with patch("service_loop_skip.get_addon", return_value=addon), \
                patch("service_loop_skip.get_user_skip_mode", return_value="ask"), \
                patch("service_loop_skip.apply_per_show_override", side_effect=lambda *a: a[-1]), \
                patch("service_loop_skip.is_skip_enabled", return_value=True), \
                patch("service_loop_skip._handle_auto_skip", return_value=None) as auto, \
                patch("service_loop_skip._handle_ask_skip", return_value=None) as ask:
            mod.process_segment_skips(
                ctx, video="/v.mkv", playback_type="episode", show_dialogs=True,
                current_time=10.0, major_rewind_detected=False,
            )
        return auto, ask, monitor

    def test_second_episode_skips_the_intro_without_asking(self):
        auto, ask, _ = self.run_tick(2)
        auto.assert_called_once()
        ask.assert_not_called()

    def test_first_episode_lets_the_intro_play(self):
        auto, ask, monitor = self.run_tick(1)
        auto.assert_not_called()
        ask.assert_not_called()
        self.assertIn((0, 60), monitor.prompted)

    def test_off_asks_as_usual(self):
        auto, ask, _ = self.run_tick(2, enabled="false")
        auto.assert_not_called()
        ask.assert_called_once()


class MainLoopNoteTests(unittest.TestCase):
    def test_note_updates_the_run_and_the_diagnostics(self):
        import service_main_loop as loop

        monitor = MagicMock(spec=[])
        item = {"tvshowid": 7, "showtitle": "Arrow"}
        with patch.object(loop, "get_addon", return_value=_addon()), \
                patch.object(loop, "publish_diagnostics") as publish:
            loop._note_title_and_binge(monitor, "/tv/a1.mkv", "episode", item)
        self.assertEqual(binge.binge_position(monitor), 1)
        publish.assert_called_once_with(
            monitor, video="/tv/a1.mkv", playback_type="episode", title="Arrow",
            title_key="tv:7", binge_position=1,
        )


if __name__ == "__main__":
    unittest.main()
