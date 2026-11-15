# -*- coding: utf-8 -*-
"""Smooth progress: the frame-rate driver, Skippy's own dialogs, and a skin's driven control."""

import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import skin_progress  # noqa: E402
import smooth_progress as sp  # noqa: E402


class _Clock:
    """A fake monotonic clock; waiting moves it on."""

    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def wait(self, seconds):
        self.t += seconds
        return False


def _driver(clock, *, until=1.0, rate=23.976, paused=False, position=None, percent_at=None,
            apply=None, **kw):
    applied = []
    driver = sp.ProgressDriver(
        "test",
        percent_at or (lambda pos: pos),
        apply or applied.append,
        position=position or (lambda: clock.t * 10.0),
        still_wanted=lambda: clock.t < until,
        rate=lambda: rate,
        paused=lambda: paused,
        clock=clock,
        wait=clock.wait,
        **kw
    )
    return driver, applied


class HelperTests(unittest.TestCase):
    def test_parse_rate(self):
        self.assertEqual(sp.parse_rate("23.976"), 23.976)
        self.assertEqual(sp.parse_rate("23,976"), 23.976)
        self.assertEqual(sp.parse_rate("59.94 fps"), 59.94)
        self.assertIsNone(sp.parse_rate(""))
        self.assertIsNone(sp.parse_rate("0"))
        self.assertIsNone(sp.parse_rate(None))

    def test_frame_rate_falls_back_from_the_video_to_the_screen_to_25(self):
        labels = {"Player.Process(videofps)": "23.976", "System.FPS": "59.9"}
        self.assertEqual(sp.video_frame_rate(labels.get), 23.976)
        labels["Player.Process(videofps)"] = ""
        self.assertEqual(sp.video_frame_rate(labels.get), 59.9)
        labels["System.FPS"] = ""
        self.assertEqual(sp.video_frame_rate(labels.get), 25.0)
        self.assertEqual(sp.video_frame_rate({"Player.Process(videofps)": "240"}.get), 120.0)
        self.assertEqual(sp.video_frame_rate(lambda _l: 1 / 0), 25.0)

    def test_hold_back_only_small_steps_back(self):
        self.assertEqual(sp.held_position(100.0, 99.996), 100.0)   # pause wobble
        self.assertEqual(sp.held_position(100.0, 99.0), 99.0)      # a real seek back
        self.assertEqual(sp.held_position(100.0, 100.5), 100.5)
        self.assertEqual(sp.held_position(None, 5.0), 5.0)

    def test_segment_percent(self):
        self.assertEqual(sp.segment_percent(15, 10, 30), 25.0)
        self.assertEqual(sp.segment_percent(15, 10, 30, countdown=True), 75.0)
        self.assertEqual(sp.segment_percent(5, 10, 30), 0.0)
        self.assertEqual(sp.segment_percent(50, 10, 30), 100.0)
        self.assertEqual(sp.segment_percent(10, 10, 10), 100.0)
        self.assertAlmostEqual(sp.segment_percent(10.4, 10, 30), 2.0)


class DriverTests(unittest.TestCase):
    def test_one_update_per_video_frame_on_a_steady_clock(self):
        clock = _Clock()
        driver, applied = _driver(clock, rate=23.976)
        driver.run()
        self.assertEqual(len([p for p in applied if p < 10.0]), 24)  # updates in the first second
        self.assertEqual(driver.stopped_because, "no longer wanted")
        steps = [b - a for a, b in zip(applied, applied[1:])]
        self.assertTrue(all(abs(s - 10.0 / 23.976) < 1e-6 for s in steps))  # even, fractional

    def test_paused_four_a_second(self):
        clock = _Clock()
        driver, applied = _driver(clock, paused=True)
        driver.run()
        self.assertEqual(len([p for p in applied if p < 10.0]), 4)

    def test_slow_work_does_not_lower_the_rate(self):
        clock = _Clock()

        times = []

        def apply(_pct):
            times.append(clock.t)
            clock.t += 0.01  # each update takes 10 ms

        driver, _ = _driver(clock, rate=25.0, apply=apply)
        driver.run()
        self.assertEqual(len([t for t in times if t < 1.0]), 25)

    def test_falling_behind_starts_counting_again(self):
        clock = _Clock()
        calls = []

        def apply(_pct):
            calls.append(clock.t)
            if len(calls) == 3:
                clock.t += 0.5  # a busy moment
        driver, _ = _driver(clock, rate=10.0, apply=apply)
        driver.run()
        # after the busy moment the next update comes at once, then the steady 0.1 s again:
        # no burst of updates to catch up on the time lost
        self.assertAlmostEqual(calls[3] - calls[2], 0.501, places=6)
        self.assertAlmostEqual(calls[4] - calls[3], 0.1, places=2)

    def test_stops_when_the_bar_is_done_the_control_is_gone_or_on_error(self):
        clock = _Clock()
        driver, _ = _driver(clock, percent_at=lambda pos: None if pos >= 3 else pos)
        driver.run()
        self.assertEqual(driver.stopped_because, "bar finished")
        driver, _ = _driver(_Clock(), apply=lambda _p: False)
        driver.run()
        self.assertEqual((driver.stopped_because, driver.updates), ("control gone", 0))
        driver, _ = _driver(_Clock(), apply=lambda _p: 1 / 0)
        driver.run()
        self.assertTrue(driver.stopped_because.startswith("error"))

        def gone():
            raise RuntimeError("no playback")
        driver, _ = _driver(_Clock(), position=gone)
        driver.run()
        self.assertEqual(driver.stopped_because, "playback ended")

    def test_clamps_and_holds_back(self):
        clock = _Clock()
        positions = iter([10.0, 9.999, 9.998, 3.0, 200.0])
        driver, applied = _driver(clock, until=0.2, rate=25.0, position=lambda: next(positions))
        driver.run()
        self.assertEqual(applied, [10.0, 10.0, 10.0, 3.0, 100.0])

    def test_first_and_stop_callbacks(self):
        events = []
        driver, _ = _driver(_Clock(), on_first=lambda: events.append("first"),
                            on_stop=lambda: events.append("stop"))
        driver.run()
        self.assertEqual(events, ["first", "stop"])

    def test_a_real_thread_stops_and_is_joined(self):
        applied = []
        driver = sp.ProgressDriver("skippy-test", lambda p: 50.0, applied.append,
                                   position=lambda: 1.0, rate=lambda: 100.0, paused=lambda: False)
        driver.start()
        deadline = time.monotonic() + 2
        while not applied and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(driver.running)
        driver.stop()
        self.assertFalse(driver.running)
        count = len(applied)
        time.sleep(0.05)
        self.assertEqual(len(applied), count)  # nothing after stop()
        self.assertNotIn("skippy-test", [t.name for t in threading.enumerate()])


class _Home:
    def __init__(self, **props):
        self.props = dict(props)

    def getProperty(self, key):
        return self.props.get(key, "")

    def setProperty(self, key, value):
        self.props[key] = value

    def clearProperty(self, key):
        self.props.pop(key, None)


class _FakeDriver:
    """Records what a SkinBar would drive; ``step(pct)`` plays one update."""

    made = []

    def __init__(self, name, percent_at, apply, **kw):
        self.name, self.percent_at, self.apply, self.kw = name, percent_at, apply, kw
        self.running = False
        self.first = False
        _FakeDriver.made.append(self)

    def start(self):
        self.running = True
        return self

    def stop(self):
        if self.running and self.kw.get("on_stop"):
            self.kw["on_stop"]()
        self.running = False

    def step(self, position):
        pct = self.percent_at(position)
        self.apply(pct)
        if not self.first:
            self.first = True
            self.kw["on_first"]()
        return pct


class SkinBarTests(unittest.TestCase):
    def setUp(self):
        _FakeDriver.made = []
        self.control = MagicMock()
        self.window = MagicMock()
        self.window.getControl.return_value = self.control
        self.home = _Home(**{
            "Skippy.SkinSkipProgress.Window": "1167",
            "Skippy.SkinSkipProgress.Control": "4801",
            "Skippy.SkinSkipProgress.Frames": "11",
            "Skippy.SkinNextEpisodeProgress.Window": "1168",
            "Skippy.SkinNextEpisodeProgress.Control": "4802",
        })
        self.visible = {1167: True, 1168: True}
        self.monitor = SimpleNamespace()
        self.kw = dict(visible=lambda wid: self.visible.get(wid, False),
                       window_factory=lambda _wid: self.window, driver_factory=_FakeDriver)

    def segment(self, start=60.0, end=120.0):
        return SimpleNamespace(start_seconds=start, end_seconds=end)

    def test_targets(self):
        self.assertEqual(skin_progress.read_target(self.home, skin_progress.SKIP), (1167, 4801, 11))
        self.assertEqual(skin_progress.read_target(self.home, skin_progress.NEXT), (1168, 4802, 0))
        self.assertIsNone(skin_progress.read_target(_Home(), skin_progress.SKIP))
        self.assertEqual(skin_progress.frame_for(50, 11), 5)
        self.assertEqual(skin_progress.frame_for(100, 11), 10)
        self.assertEqual(skin_progress.frame_for(50, 0), 0)

    def test_ask_segment_with_the_skin_dialog_visible_is_driven(self):
        skin_progress.sync_skip_bar(self.monitor, self.home, self.segment(), "ask", False,
                                    skin_button=True, **self.kw)
        self.assertEqual(len(_FakeDriver.made), 1)
        driver = _FakeDriver.made[0]
        self.assertAlmostEqual(driver.step(75.0), 25.0)
        self.control.setPercent.assert_called_once_with(25.0)
        self.window.getControl.assert_called_with(4801)
        self.assertEqual(self.home.props["Skippy.Segment.SmoothProgress"], "true")
        self.assertEqual(self.home.props["Skippy.Segment.Frame"], "2")
        self.assertIsNone(driver.percent_at(120.0))  # the segment end stops it
        # the same segment on the next tick keeps the same driver
        skin_progress.sync_skip_bar(self.monitor, self.home, self.segment(), "ask", False,
                                    skin_button=True, **self.kw)
        self.assertEqual(len(_FakeDriver.made), 1)

    def test_frame_written_only_when_it_changes(self):
        skin_progress.sync_skip_bar(self.monitor, self.home, self.segment(), "ask", False,
                                    skin_button=True, **self.kw)
        driver = _FakeDriver.made[0]
        with patch.object(self.home, "setProperty", wraps=self.home.setProperty) as setp:
            driver.step(61.0)
            driver.step(61.1)
            frames = [c for c in setp.call_args_list if c.args[0] == "Skippy.Segment.Frame"]
        self.assertEqual(len(frames), 1)

    def test_not_driven_without_ask_button_target_or_visible_window(self):
        for mode, button, visible in (("auto", True, True), ("ask", False, True), ("ask", True, False)):
            self.visible[1167] = visible
            skin_progress.sync_skip_bar(self.monitor, self.home, self.segment(), mode, False,
                                        skin_button=button, **self.kw)
        self.assertEqual(_FakeDriver.made, [])
        skin_progress.sync_skip_bar(self.monitor, self.home, None, "", False, skin_button=True, **self.kw)
        self.assertEqual(_FakeDriver.made, [])

    def test_stops_and_clears_when_the_segment_goes(self):
        skin_progress.sync_skip_bar(self.monitor, self.home, self.segment(), "ask",
                                    skin_button=True, **self.kw)
        driver = _FakeDriver.made[0]
        self.assertAlmostEqual(driver.step(75.0), 25.0)  # percent played, like Segment.Progress
        skin_progress.sync_skip_bar(self.monitor, self.home, None, "", True, skin_button=True, **self.kw)
        self.assertFalse(driver.running)
        self.assertNotIn("Skippy.Segment.SmoothProgress", self.home.props)
        self.assertNotIn("Skippy.Segment.Frame", self.home.props)

    def test_a_new_segment_restarts_and_still_wanted_asks_the_window(self):
        skin_progress.sync_skip_bar(self.monitor, self.home, self.segment(), "ask", False,
                                    skin_button=True, **self.kw)
        skin_progress.sync_skip_bar(self.monitor, self.home, self.segment(200, 260), "ask", False,
                                    skin_button=True, **self.kw)
        self.assertEqual(len(_FakeDriver.made), 2)
        self.assertFalse(_FakeDriver.made[0].running)
        still = _FakeDriver.made[1].kw["still_wanted"]
        self.assertTrue(still())
        self.visible[1167] = False
        self.assertFalse(still())

    def test_next_episode_bar_follows_the_countdown_and_stops_with_the_prompt(self):
        prompt = SimpleNamespace(begin=1455.0, end=1500.0, timed=False, finished=False)
        skin_progress.sync_next_bar(self.monitor, self.home, prompt, skin_popup=True, **self.kw)
        driver = _FakeDriver.made[0]
        self.assertAlmostEqual(driver.step(1464.0), 20.0)  # percent gone, like NextEpisode.Progress
        self.assertEqual(self.home.props["Skippy.NextEpisode.SmoothProgress"], "true")
        self.assertNotIn("Skippy.NextEpisode.Frame", self.home.props)
        self.assertIsNone(driver.percent_at(1499.0))
        skin_progress.stop_bar(self.monitor, skin_progress.NEXT)
        self.assertNotIn("Skippy.NextEpisode.SmoothProgress", self.home.props)
        prompt.finished = True
        skin_progress.sync_next_bar(self.monitor, self.home, prompt, skin_popup=True, **self.kw)
        self.assertEqual(len(_FakeDriver.made), 1)
        skin_progress.stop_bar(None, skin_progress.NEXT)


class SkipDialogDriverTests(unittest.TestCase):
    """Skippy's own skip dialog: which control the driver moves, and that closing stops it."""

    def dialog(self, **attrs):
        import skipdialog

        d = object.__new__(skipdialog.SkipDialog)
        d._minimal_mode = False
        d._combined_mode = False
        d._closing = False
        d._skip_tiled_pitch = 0
        d._skip_progress_bar_width = 420
        d.segment = SimpleNamespace(start_seconds=100.0, end_seconds=160.0)
        d.player = MagicMock()
        d.player.getTime.return_value = 115.0
        d.controls = {}
        d.getControl = lambda cid: d.controls.setdefault(cid, MagicMock())
        d.getProperty = lambda _k: ""
        d.close = MagicMock()
        d.setProperty = MagicMock()
        for key, value in attrs.items():
            setattr(d, key, value)
        return d

    def addon(self, **settings):
        addon = MagicMock()
        addon.getSetting.side_effect = lambda k: settings.get(k, "")
        return addon

    def start(self, d, addon):
        made = []

        class Recorder:
            def __init__(self, name, percent_at, apply, **kw):
                self.percent_at, self.apply, self.kw = percent_at, apply, kw
                self.running = True
                self.stopped = False
                self.updates, self.stopped_because = 0, ""
                made.append(self)

            def start(self):
                return self

            def stop(self):
                self.stopped, self.running = True, False

        with patch("skipdialog.ProgressDriver", Recorder):
            d._start_progress_driver(addon)
        return made

    def test_plain_bar_gets_float_percent_on_the_progress_control(self):
        d = self.dialog()
        made = self.start(d, self.addon())
        driver = made[0]
        pct = driver.percent_at(115.0)
        self.assertAlmostEqual(pct, 25.0)
        driver.apply(pct)
        d.controls[3014].setPercent.assert_called_once_with(pct)
        self.assertIsNone(driver.percent_at(160.0))
        self.assertAlmostEqual(self.start(self.dialog(), self.addon(progress_bar_countdown="true"))[0]
                               .percent_at(115.0), 75.0)

    def test_tiled_and_combined_bars_move_their_images(self):
        import skipdialog

        d = self.dialog(_skip_tiled_pitch=12)
        driver = self.start(d, self.addon())[0]
        driver.apply(50.0)
        d.controls[skipdialog._SMOOTH_PROGRESS_TILED_FILL_ID].setWidth.assert_called_once()
        driver.apply(50.01)  # same width: not set again
        self.assertEqual(d.controls[skipdialog._SMOOTH_PROGRESS_TILED_FILL_ID].setWidth.call_count, 1)
        d = self.dialog(_combined_mode=True)
        driver = self.start(d, self.addon())[0]
        driver.apply(50.0)
        d.controls[skipdialog.COMBINED_FILL_STRETCH_ID].setWidth.assert_called_once_with(210)

    def test_no_driver_when_off_hidden_or_minimal(self):
        self.assertEqual(self.start(self.dialog(), self.addon(smooth_progress_bar="false")), [])
        self.assertEqual(self.start(self.dialog(), self.addon(show_progress_bar="false")), [])
        self.assertEqual(self.start(self.dialog(_minimal_mode=True), self.addon()), [])

    def test_closing_stops_the_driver_before_close(self):
        d = self.dialog()
        driver = self.start(d, self.addon())[0]
        order = []
        d.close = lambda: order.append(("close", driver.stopped))
        d._finish_dialog(False)
        self.assertEqual(order, [("close", True)])
        self.assertIsNone(d._progress_driver)


class NextEpisodeDialogDriverTests(unittest.TestCase):
    def dialog(self, **attrs):
        import next_episode_dialog as ned

        d = object.__new__(ned.NextEpisodeDialog)
        d.window_start, d.total, d.timed, d.preview = 1455.0, 1500.0, False, False
        d._closing = False
        d._bar_tiled = False
        d._layout = SimpleNamespace(bar_y=10, bar_w=400)
        d._skin_resolution = "720p"
        d.controls = {}
        d.getControl = lambda cid: d.controls.setdefault(cid, MagicMock())
        for key, value in attrs.items():
            setattr(d, key, value)
        return d

    def test_bar_percent_shrinks_and_ends_before_the_file_does(self):
        d = self.dialog()
        self.assertAlmostEqual(d._bar_percent(1455.0), 100.0)
        self.assertAlmostEqual(d._bar_percent(1477.5), 50.0)
        self.assertIsNone(d._bar_percent(1499.0))
        timed = self.dialog(timed=True, total=1475.0)
        self.assertIsNotNone(timed._bar_percent(1474.9))
        self.assertIsNone(timed._bar_percent(1475.0))

    def test_set_bar_percent_moves_the_fill_once_per_width(self):
        import next_episode_dialog as ned

        d = self.dialog()
        d._set_bar_percent(50.0)
        d._set_bar_percent(50.01)
        fill = d.controls[ned.ID_BAR_FILL_STRETCH]
        self.assertEqual(fill.setWidth.call_count, 1)

    def test_finish_stops_the_driver(self):
        d = self.dialog(_stop=threading.Event(), close=MagicMock())
        driver = MagicMock()
        d._progress_driver = driver
        d._finish(True)
        driver.stop.assert_called_once_with()
        self.assertIsNone(d._progress_driver)
        self.assertTrue(d.result)


class ServiceWiringTests(unittest.TestCase):
    def test_skip_current_stops_the_skin_bar_before_skipping(self):
        import service_loop_skip as mod
        from segment_item import SegmentItem

        monitor = MagicMock()
        monitor.current_segments = [SegmentItem(60.0, 120.0, "intro")]
        mod.request_skip_current(monitor)
        order = []
        with patch("skin_progress.stop_bar", lambda m, kind: order.append(("stop", kind))), \
                patch("service_loop_skip.get_addon", return_value=MagicMock()), \
                patch("service_loop_skip.compute_skip_seek_destination_seconds", return_value=121.0), \
                patch("service_loop_skip._handle_auto_skip", lambda *a, **k: order.append("skip")):
            mod.handle_skip_current_request(MagicMock(monitor=monitor), "/v.mkv", "episode", 70.0)
        self.assertEqual(order, [("stop", "skip"), "skip"])

    def test_main_loop_syncs_both_skin_bars(self):
        import service_main_loop as loop
        from segment_item import SegmentItem

        win = _Home(**{"Skippy.SkinSkipButton": "true"})
        monitor = SimpleNamespace(current_segments=[SegmentItem(0, 60, "intro")])
        with patch.object(loop, "get_home_window", return_value=win), \
                patch.object(loop, "get_addon", return_value=MagicMock()), \
                patch.object(loop, "skin_mode_for", return_value=lambda _s: "ask"), \
                patch.object(loop.skin_progress, "sync_skip_bar") as skip_bar, \
                patch.object(loop.skin_progress, "sync_next_bar") as next_bar:
            loop._publish_skin_properties(monitor, "/v.mkv", "episode", 30.0, False)
        args, kwargs = skip_bar.call_args
        self.assertEqual((args[3], kwargs["skin_button"]), ("ask", True))
        self.assertIs(args[2], monitor.current_segments[0])
        self.assertFalse(next_bar.call_args.kwargs["skin_popup"])


if __name__ == "__main__":
    unittest.main()
