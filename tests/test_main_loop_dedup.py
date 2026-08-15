# -*- coding: utf-8 -*-
"""One monitor tick must not repeat rewind/skip work when nothing changed."""

import types
import unittest
from unittest.mock import patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import service_main_loop
from service_main_loop import ServiceLoopBindings, run_service_main_loop


class _Monitor:
    def __init__(self, segments):
        self.current_segments = segments
        self.playback_ready = True
        self.last_time = 0.0
        self.skippy_skipping_since = None
        self._aborts = [False, True]

    def abortRequested(self):
        return self._aborts.pop(0) if self._aborts else True

    def waitForAbort(self, _seconds):
        return False


class _Player:
    def __init__(self, current_time):
        self._time = current_time

    def isPlayingVideo(self):
        return True

    def isPlaying(self):
        return True

    def getTime(self):
        return self._time


def _segment(start, end, label="intro"):
    return types.SimpleNamespace(
        start_seconds=start,
        end_seconds=end,
        segment_type_label=label,
        next_segment_start=None,
        next_segment_info=None,
    )


def _bindings(monitor, player):
    noop = lambda *a, **k: None
    return ServiceLoopBindings(
        monitor=monitor,
        player=player,
        check_interval=1,
        icon_path="",
        get_video_file=lambda *a, **k: "episode.mkv",
        skippy_skip_ui_suppression_state=lambda _win: types.SimpleNamespace(
            suppress=False, pending_marker_blocks=False
        ),
        log_if_changed=noop,
        infer_playback_type=lambda *a, **k: "episode",
        should_show_missing_file_toast=lambda *a, **k: False,
        both_segment_sources_disabled_for_playback=lambda *a, **k: False,
        missing_segments_toast_message=lambda *a, **k: "",
        parse_and_process_segments=lambda *a, **k: monitor.current_segments,
        should_suppress_segment_dialog=lambda *a, **k: False,
        re_evaluate_segment_jump_points=noop,
        is_nested_segment=lambda *a, **k: False,
        skip_dialog_layout_suffix=lambda *a, **k: "BottomRight",
        warm_skip_dialog_skin_textures=noop,
        process_deferred_remote_probe=noop,
        clear_deferred_remote_probe_state=noop,
    )


def _run_one_tick(monitor, player, *, parsed_time=10.0, parse_fn=None):
    if parse_fn is None:
        def parse_fn(_ctx, _video, _current_time, _playback_type):
            return parsed_time

    with patch.object(service_main_loop, "refresh_playback_context") as refresh, patch.object(
        service_main_loop, "handle_replay_detection"
    ), patch.object(service_main_loop, "handle_video_change"), patch.object(
        service_main_loop, "try_show_missing_segments_toast"
    ), patch.object(
        service_main_loop, "_parse_segments_with_deferred_probe", parse_fn
    ), patch.object(
        service_main_loop, "handle_rewind_and_nested_segments", return_value=False
    ) as rewind, patch.object(
        service_main_loop, "process_segment_skips"
    ) as skips:
        refresh.return_value = types.SimpleNamespace(
            video_path="episode.mkv",
            current_time=10.0,
            playback_type="episode",
            show_dialogs=True,
            is_paused=False,
            is_playing=True,
            used_pause_fast_path=False,
            toast_movies=False,
            toast_episodes=False,
        )
        run_service_main_loop(_bindings(monitor, player))
    return rewind.call_count, skips.call_count


class MainLoopDedupTests(unittest.TestCase):
    def test_steady_tick_processes_segments_once(self):
        monitor = _Monitor([_segment(0.0, 60.0)])
        rewinds, skips = _run_one_tick(monitor, _Player(10.0), parsed_time=10.0)
        self.assertEqual(rewinds, 1)
        self.assertEqual(skips, 1)

    def test_playhead_move_during_parse_reprocesses(self):
        monitor = _Monitor([_segment(0.0, 60.0)])
        rewinds, skips = _run_one_tick(monitor, _Player(10.0), parsed_time=41.0)
        self.assertEqual(rewinds, 2)
        self.assertEqual(skips, 2)

    def test_new_segments_after_parse_reprocesses(self):
        monitor = _Monitor([_segment(0.0, 60.0)])

        def _grow_segments(ctx, _video, _current_time, _playback_type):
            ctx.monitor.current_segments = [_segment(0.0, 60.0), _segment(90.0, 120.0, "recap")]
            return 10.0

        rewinds, skips = _run_one_tick(monitor, _Player(10.0), parse_fn=_grow_segments)
        self.assertEqual(rewinds, 2)
        self.assertEqual(skips, 2)

    def test_first_tick_without_segments_still_processes(self):
        monitor = _Monitor([])
        rewinds, skips = _run_one_tick(monitor, _Player(10.0), parsed_time=10.0)
        self.assertEqual(rewinds, 1)
        self.assertEqual(skips, 1)


class IdleParseSkipTests(unittest.TestCase):
    def _ctx(self, monitor):
        return _bindings(monitor, _Player(200.0))

    def test_idle_far_from_segments_skips_parse(self):
        import time

        monitor = _Monitor([_segment(0.0, 20.0)])
        monitor.segment_parse_cache = {
            "path": "episode.mkv",
            "playback_type": "episode",
            "last_sidecar_check": time.time(),
            "segments": [_segment(0.0, 20.0)],
        }
        monitor.segment_processed_cache = {"link_boundaries": ()}
        monitor.deferred_remote_playback_stash = None
        ctx = self._ctx(monitor)
        self.assertFalse(
            service_main_loop._should_parse_segments(ctx, "episode.mkv", 200.0, "episode")
        )

    def test_near_segment_forces_parse(self):
        import time

        monitor = _Monitor([_segment(0.0, 20.0)])
        monitor.segment_parse_cache = {
            "path": "episode.mkv",
            "playback_type": "episode",
            "last_sidecar_check": time.time(),
            "segments": [_segment(0.0, 20.0)],
        }
        monitor.segment_processed_cache = {"link_boundaries": ()}
        ctx = self._ctx(monitor)
        self.assertTrue(
            service_main_loop._should_parse_segments(ctx, "episode.mkv", 10.0, "episode")
        )

    def test_seek_grace_forces_parse(self):
        import time

        monitor = _Monitor([_segment(0.0, 20.0)])
        monitor.skippy_skipping_since = time.monotonic()
        monitor.segment_parse_cache = {
            "path": "episode.mkv",
            "playback_type": "episode",
            "last_sidecar_check": time.time(),
            "segments": [_segment(0.0, 20.0)],
        }
        monitor.segment_processed_cache = {"link_boundaries": ()}
        ctx = self._ctx(monitor)
        self.assertTrue(
            service_main_loop._should_parse_segments(ctx, "episode.mkv", 200.0, "episode")
        )


if __name__ == "__main__":
    unittest.main()
