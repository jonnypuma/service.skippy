# -*- coding: utf-8 -*-
"""Home window properties for skins, the skin's own skip button and skip_current."""

import time
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import skin_properties as sp  # noqa: E402
from segment_item import SegmentItem  # noqa: E402
from segment_types import seeded_builtin_types, set_catalog_for_tests  # noqa: E402


class _Win:
    def __init__(self, **props):
        self.props = dict(props)
        self.writes = 0

    def setProperty(self, key, value):
        self.props[key] = value
        self.writes += 1

    def clearProperty(self, key):
        self.props.pop(key, None)
        self.writes += 1

    def getProperty(self, key):
        return self.props.get(key, "")


def _addon(**settings):
    addon = MagicMock()
    addon.getSetting.side_effect = lambda key: settings.get(key, "")
    return addon


class _Catalog(unittest.TestCase):
    def setUp(self):
        set_catalog_for_tests(seeded_builtin_types())
        self.addCleanup(set_catalog_for_tests, None)


class BuildTests(_Catalog):
    def segs(self):
        return [SegmentItem(0, 50, "recap"), SegmentItem(60, 120, "Opening"),
                SegmentItem(2500, 2600, "credits")]

    def test_inside_a_segment(self):
        props = sp.build_skin_properties(self.segs(), 78.4, lambda s: "ask")
        self.assertEqual(props["Skippy.HasSegments"], "true")
        self.assertEqual(props["Skippy.Segment.Type"], "Intro")
        self.assertEqual(props["Skippy.Segment.TypeId"], "intro")
        self.assertEqual(props["Skippy.Segment.Mode"], "ask")
        self.assertEqual(props["Skippy.Segment.Start"], "01:00")
        self.assertEqual(props["Skippy.Segment.End"], "02:00")
        self.assertEqual(props["Skippy.Segment.Remaining"], "0:41")
        self.assertEqual(props["Skippy.Segment.RemainingSeconds"], "42")
        self.assertEqual(props["Skippy.Segment.Progress"], "31")
        self.assertEqual(props["Skippy.Segment.Next.Type"], "Credits")
        self.assertEqual(props["Skippy.Segment.Next.Start"], "41:40")
        self.assertEqual(set(props), {sp.PREFIX + k for k in sp.KEYS})

    def test_between_segments_and_without_any(self):
        props = sp.build_skin_properties(self.segs(), 55.0)
        self.assertEqual(props["Skippy.Segment.Type"], "")
        self.assertEqual(props["Skippy.Segment.Mode"], "")
        self.assertEqual(props["Skippy.Segment.Next.Type"], "Intro")
        empty = sp.build_skin_properties([], 10.0)
        self.assertTrue(all(v == "" for v in empty.values()))
        self.assertEqual(sp.build_skin_properties(self.segs(), 3000.0)["Skippy.Segment.Next.Type"], "")

    def test_innermost_segment_wins(self):
        segs = [SegmentItem(0, 600, "commercial"), SegmentItem(100, 160, "intro")]
        self.assertEqual(sp.active_segment(segs, 120).segment_type_label, "intro")
        self.assertEqual(sp.active_segment(segs, 300).segment_type_label, "commercial")
        self.assertIsNone(sp.active_segment(segs, "x"))
        self.assertIsNone(sp.active_segment(segs, 600))  # the end belongs to what follows

    def test_next_episode(self):
        state = SimpleNamespace(next_item={"season": 2, "episode": 5, "title": "The Return",
                                           "art": {"thumb": "image://t.jpg/"}})
        monitor = SimpleNamespace(next_episode_state=state)
        props = sp.build_skin_properties([], 0, monitor=monitor, next_due=True)
        self.assertEqual(props["Skippy.NextEpisode.Label"], "S02E05 · The Return")
        self.assertEqual(props["Skippy.NextEpisode.Thumb"], "image://t.jpg/")
        self.assertEqual(props["Skippy.NextEpisode.Due"], "true")
        props = sp.build_skin_properties([], 0, monitor=SimpleNamespace(next_episode_state=None))
        self.assertEqual((props["Skippy.NextEpisode.Label"], props["Skippy.NextEpisode.Due"]), ("", ""))


class PublishTests(unittest.TestCase):
    def test_only_changes_are_written_and_clear_empties(self):
        win, monitor = _Win(), SimpleNamespace()
        props = {sp.PREFIX + k: "" for k in sp.KEYS}
        props["Skippy.Segment.Type"] = "Intro"
        props["Skippy.Segment.Remaining"] = "0:42"
        self.assertEqual(sp.publish(win, monitor, props), len(sp.KEYS))  # first call writes all
        props["Skippy.Segment.Remaining"] = "0:41"
        self.assertEqual(sp.publish(win, monitor, props), 1)
        self.assertEqual(sp.publish(win, monitor, props), 0)
        self.assertEqual(win.props["Skippy.Segment.Remaining"], "0:41")
        sp.clear(win, monitor)
        self.assertNotIn("Skippy.Segment.Type", win.props)
        self.assertEqual(sp.clear(win, SimpleNamespace()), 0)
        self.assertEqual(sp.publish(None, monitor, props), 0)

    def test_skin_button_handshake(self):
        self.assertTrue(sp.skin_draws_skip_button(_Win(**{"Skippy.SkinSkipButton": "True"})))
        self.assertFalse(sp.skin_draws_skip_button(_Win()))
        self.assertFalse(sp.skin_draws_skip_button(None))


def _monitor(segments):
    monitor = MagicMock()
    monitor.playback_ready = True
    monitor.prompted = set()
    monitor.recently_dismissed = set()
    monitor.skipped_to_nested_segment = {}
    monitor.last_skipped_seg_id = None
    monitor.last_skipped_seg_bounds = None
    monitor.current_segments = segments
    monitor._last_log_state = {}
    monitor.skip_current_requested = None
    return monitor


class SkipLoopTests(_Catalog):
    def test_skin_button_replaces_the_ask_dialog(self):
        import service_loop_skip as mod

        intro = SegmentItem(0.0, 60.0, "intro")
        monitor = _monitor([intro])
        ctx = MagicMock(monitor=monitor)
        ctx.should_suppress_segment_dialog = MagicMock(return_value=False)
        for skin_button, asked in ((True, 0), (False, 1)):
            win = _Win(**({"Skippy.SkinSkipButton": "true"} if skin_button else {}))
            with patch("service_loop_skip.get_addon", return_value=_addon()), \
                    patch("service_loop_skip.get_home_window", return_value=win), \
                    patch("service_loop_skip.get_user_skip_mode", return_value="ask"), \
                    patch("service_loop_skip.is_skip_enabled", return_value=True), \
                    patch("service_loop_skip._handle_ask_skip", return_value=None) as ask:
                mod.process_segment_skips(ctx, video="/v.mkv", playback_type="episode",
                                          show_dialogs=True, current_time=10.0,
                                          major_rewind_detected=False)
            self.assertEqual(ask.call_count, asked)
        self.assertNotIn((0, 60), monitor.prompted)

    def test_skip_current_request(self):
        import service_loop_skip as mod

        intro = SegmentItem(60.0, 120.0, "intro")
        monitor = _monitor([intro])
        ctx = MagicMock(monitor=monitor)
        with patch("service_loop_skip.get_addon", return_value=_addon()), \
                patch("service_loop_skip.compute_skip_seek_destination_seconds", return_value=121.0), \
                patch("service_loop_skip._handle_auto_skip", return_value=121.0) as auto:
            self.assertIsNone(mod.handle_skip_current_request(ctx, "/v.mkv", "episode", 70.0))
            mod.request_skip_current(monitor)
            self.assertEqual(mod.handle_skip_current_request(ctx, "/v.mkv", "episode", 70.0), 121.0)
            self.assertIsNone(monitor.skip_current_requested)
            args = auto.call_args
            self.assertIs(args.args[1], intro)
            self.assertEqual(args.args[3], 121.0)
            self.assertEqual(args.kwargs, {"video": "/v.mkv", "playback_type": "episode"})
            mod.request_skip_current(monitor)  # outside any segment: nothing
            self.assertIsNone(mod.handle_skip_current_request(ctx, "/v.mkv", "episode", 10.0))
            monitor.skip_current_requested = time.monotonic() - mod.SKIP_REQUEST_MAX_AGE_S - 1
            self.assertIsNone(mod.handle_skip_current_request(ctx, "/v.mkv", "episode", 70.0))
        self.assertEqual(auto.call_count, 1)
        mod.request_skip_current(None)

    def test_mode_for_matches_the_loop_and_is_cached(self):
        import service_loop_skip as mod

        monitor = SimpleNamespace()
        intro = SegmentItem(0.0, 60.0, "intro")
        with patch("segment_types.get_user_skip_mode", return_value="ask") as catalog, \
                patch("service_loop_skip.apply_per_show_override", side_effect=lambda *a: a[-1]), \
                patch("service_loop_skip.is_skip_enabled", return_value=True):
            mode_for = mod.skin_mode_for(monitor, _addon(), "/v.mkv", "episode")
            self.assertEqual(mode_for(intro), "ask")
            self.assertEqual(mode_for(intro), "ask")
            self.assertEqual(catalog.call_count, 1)
            again = mod.skin_mode_for(monitor, _addon(), "/v.mkv", "episode")
            again(intro)
            self.assertEqual(catalog.call_count, 1)
            mod.skin_mode_for(monitor, _addon(), "/w.mkv", "episode")(intro)
            self.assertEqual(catalog.call_count, 2)
        with patch("segment_types.get_user_skip_mode", return_value="auto"), \
                patch("service_loop_skip.apply_per_show_override", side_effect=lambda *a: a[-1]), \
                patch("service_loop_skip.is_skip_enabled", return_value=False):
            off = mod.skin_mode_for(SimpleNamespace(), _addon(), "/v.mkv", "movie")
            self.assertEqual(off(intro), "never")


class MainLoopTests(_Catalog):
    def test_publish_and_clear_through_the_loop_helpers(self):
        import service_main_loop as loop

        win = _Win()
        monitor = SimpleNamespace(current_segments=[SegmentItem(0, 60, "intro")])
        with patch.object(loop, "get_home_window", return_value=win), \
                patch.object(loop, "get_addon", return_value=_addon()), \
                patch("service_loop_skip.get_user_skip_mode", return_value="ask"), \
                patch("service_loop_skip.is_skip_enabled", return_value=True):
            loop._publish_skin_properties(monitor, "/v.mkv", "movie", 30.0, False)
            self.assertEqual(win.props["Skippy.Segment.Type"], "Intro")
            self.assertEqual(win.props["Skippy.Segment.Mode"], "ask")
            loop._clear_skin_properties(monitor)
        self.assertNotIn("Skippy.Segment.Type", win.props)


class RunScriptTests(unittest.TestCase):
    def test_skip_current_notifies_the_service(self):
        import sys
        import skippy_runscript_entry as entry

        with patch.object(sys, "argv", ["x", "skip_current"]), \
                patch("xbmc.executebuiltin") as builtin:
            entry.main()
        builtin.assert_called_once_with("NotifyAll(service.skippy,skip_current)")


if __name__ == "__main__":
    unittest.main()
