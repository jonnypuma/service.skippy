# -*- coding: utf-8 -*-
"""Malformed sidecars, stale cross-script caches, dialog lifecycle and safe writes."""

import json
import os
import tempfile
import types
import unittest
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import per_show_overrides
import segment_editor_parser
import segment_marker
import service_loop_nested
import service_main_loop
import service_segment_sources as sources
import skipdialog
import skippy_profile_store
import skippy_stats
import xbmcvfs
from segment_item import SegmentItem
from segment_types import seeded_builtin_types, set_catalog_for_tests
from service_segment_processing import build_nested_parent_map
from tests.test_main_loop_dedup import _Monitor, _Player, _bindings, _segment

_CHAPTER = (
    "<ChapterAtom><ChapterTimeStart>%s</ChapterTimeStart>"
    "<ChapterTimeEnd>%s</ChapterTimeEnd><ChapterDisplay>"
    "<ChapterString>%s</ChapterString></ChapterDisplay></ChapterAtom>"
)


def _chapters_xml(*atoms):
    return "<Chapters><EditionEntry>%s</EditionEntry></Chapters>" % "".join(atoms)


class MalformedChapterAndEdlTests(unittest.TestCase):
    def setUp(self):
        set_catalog_for_tests(seeded_builtin_types())
        self.addCleanup(set_catalog_for_tests, None)

    def _parse_chapter_file(self, xml):
        class _File:
            def __init__(self, _path):
                pass

            def read(self):
                return xml

            def close(self):
                pass

        with patch.object(xbmcvfs, "File", _File, create=True), patch.object(
            xbmcvfs, "exists", lambda _p: True, create=True
        ), patch.object(sources, "xbmcvfs", xbmcvfs), patch.object(
            sources, "_chapter_xml_paths_to_try", lambda _v: ["/v_chapters.xml"]
        ):
            return sources.parse_chapters("/v.mkv", update_monitor=False)

    def test_chapter_with_end_before_start_does_not_drop_the_file(self):
        xml = _chapters_xml(
            _CHAPTER % ("00:00:10.000", "00:00:20.000", "Intro"),
            _CHAPTER % ("00:01:40.000", "00:00:50.000", "Broken"),
            _CHAPTER % ("00:10:00.000", "00:11:00.000", "Credits"),
        )
        rows = self._parse_chapter_file(xml)
        self.assertEqual(
            [(r.start_seconds, r.end_seconds) for r in rows],
            [(10.0, 20.0), (600.0, 660.0)],
        )

    def test_chapter_with_unreadable_time_is_skipped(self):
        xml = _chapters_xml(
            _CHAPTER % ("soon", "00:00:20.000", "Bad"),
            _CHAPTER % ("00:00:10.000", "00:00:20.000", "Intro"),
        )
        rows = self._parse_chapter_file(xml)
        self.assertEqual([r.segment_type_label for r in rows], ["intro"])

    def test_chapter_string_parser_matches(self):
        xml = _chapters_xml(
            _CHAPTER % ("00:01:40.000", "00:00:50.000", "Broken"),
            _CHAPTER % ("00:00:10.000", "00:00:20.000", "Intro"),
        )
        rows = sources._parse_chapter_xml_string(xml)
        self.assertEqual([(r.start_seconds, r.end_seconds) for r in rows], [(10.0, 20.0)])

    def test_edl_row_with_end_before_start_keeps_the_other_rows(self):
        text = "10 20 4\n100 50 4\n30 40 4\n60 70 4\n"
        with patch.object(sources, "safe_file_read", lambda *a, **k: text):
            rows = sources.parse_edl("/v.mkv", update_monitor=False)
        self.assertEqual(
            [(r.start_seconds, r.end_seconds) for r in rows],
            [(10.0, 20.0), (30.0, 40.0), (60.0, 70.0)],
        )

    def test_edl_rejects_non_finite_and_negative_times(self):
        from edl_format import parse_edl_line

        self.assertIsNone(parse_edl_line("nan 5 4"))
        self.assertIsNone(parse_edl_line("1 inf 4"))
        self.assertIsNone(parse_edl_line("-1 5 4"))
        self.assertEqual(parse_edl_line("1 5 4"), (1.0, 5.0, 4))


class MainLoopSurvivesTickErrorTests(unittest.TestCase):
    def test_exception_in_a_tick_does_not_end_the_loop(self):
        monitor = _Monitor([_segment(0.0, 60.0)])
        monitor._aborts = [False, False, True]
        calls = []

        def _boom(_ctx):
            calls.append(1)
            if len(calls) == 1:
                raise ValueError("Segment end time (50.0) must be after start time (100.0)")
            return None

        with patch.object(service_main_loop, "refresh_playback_context", _boom), patch.object(
            service_main_loop, "log_error"
        ) as logged:
            service_main_loop.run_service_main_loop(_bindings(monitor, _Player(10.0)))

        self.assertEqual(len(calls), 2, "the loop must go on after the failed tick")
        self.assertEqual(logged.call_count, 1)
        self.assertIn("ValueError", logged.call_args[0][0])

    def test_same_error_is_logged_once(self):
        monitor = _Monitor([_segment(0.0, 60.0)])
        monitor._aborts = [False, False, False, True]

        def _boom(_ctx):
            raise RuntimeError("same every tick")

        with patch.object(service_main_loop, "refresh_playback_context", _boom), patch.object(
            service_main_loop, "log_error"
        ) as logged:
            service_main_loop.run_service_main_loop(_bindings(monitor, _Player(10.0)))
        self.assertEqual(logged.call_count, 1)


class _ProfileTempDir(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        patcher = patch.object(
            skippy_profile_store, "profile_dir", return_value=self._tmp.name
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)
        skippy_stats.clear_cache()
        per_show_overrides.clear_cache()
        self.addCleanup(skippy_stats.clear_cache)
        self.addCleanup(per_show_overrides.clear_cache)


class CrossScriptCacheTests(_ProfileTempDir):
    """The Manage/Statistics windows are separate scripts: the service must notice."""

    def test_override_deleted_by_another_script_is_forgotten(self):
        per_show_overrides.save_override("tv_tmdb_1", "intro", per_show_overrides.MODE_AUTO)
        self.assertEqual(per_show_overrides.lookup_override("tv_tmdb_1", "intro"), "auto")
        os.remove(per_show_overrides._store_path("tv_tmdb_1"))
        self.assertIsNone(per_show_overrides.lookup_override("tv_tmdb_1", "intro"))

    def test_override_rewritten_by_another_script_is_reread(self):
        per_show_overrides.save_override("tv_tmdb_1", "intro", per_show_overrides.MODE_AUTO)
        per_show_overrides.lookup_override("tv_tmdb_1", "intro")
        path = per_show_overrides._store_path("tv_tmdb_1")
        skippy_profile_store.write_json(
            path,
            {"schema": per_show_overrides.SCHEMA, "key": "tv_tmdb_1",
             "segments": {"intro": per_show_overrides.MODE_DECLINED}},
        )
        self.assertEqual(
            per_show_overrides.lookup_override("tv_tmdb_1", "intro"), "declined"
        )

    def test_override_is_cached_while_the_file_is_unchanged(self):
        per_show_overrides.save_override("tv_tmdb_1", "intro", per_show_overrides.MODE_AUTO)
        per_show_overrides.lookup_override("tv_tmdb_1", "intro")
        with patch.object(per_show_overrides, "read_json") as read:
            per_show_overrides.lookup_override("tv_tmdb_1", "intro")
        read.assert_not_called()

    def test_statistics_reset_by_another_script_is_not_undone(self):
        for _ in range(5):
            skippy_stats.record_skip("Intro", 10.0)
        # Another script resets the counters by writing the file directly.
        fresh = skippy_stats._empty_stats()
        skippy_profile_store.write_json(skippy_stats._stats_path(), fresh)
        skippy_stats.record_skip("Intro", 10.0)
        stats = skippy_stats.load_statistics()
        self.assertEqual(stats["skips"]["total"], 1)
        self.assertEqual(stats["skips"]["by_type"], {"intro": 1})

    def test_statistics_merged_by_another_script_survive_the_next_skip(self):
        skippy_stats.record_skip("Intro", 10.0)
        merged = skippy_stats._empty_stats()
        merged["skips"].update(total=40, seconds_saved=900.0, by_type={"intro": 40})
        skippy_profile_store.write_json(skippy_stats._stats_path(), merged)
        skippy_stats.record_skip("Intro", 10.0)
        self.assertEqual(skippy_stats.load_statistics()["skips"]["total"], 41)


class WriteJsonDurabilityTests(unittest.TestCase):
    def test_write_json_fsyncs_the_file_before_replacing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "data.json")
            order = []
            real_fsync, real_replace = os.fsync, os.replace
            with patch("os.fsync", side_effect=lambda fd: (order.append("fsync"), real_fsync(fd))[1]), patch(
                "os.replace", side_effect=lambda a, b: (order.append("replace"), real_replace(a, b))[1]
            ):
                self.assertTrue(skippy_profile_store.write_json(path, {"a": 1}))
            self.assertEqual(order[0], "fsync")
            self.assertLess(order.index("fsync"), order.index("replace"))
            with open(path, encoding="utf-8") as handle:
                self.assertEqual(json.load(handle), {"a": 1})

    def test_unserializable_data_keeps_original_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "data.json")
            self.assertTrue(skippy_profile_store.write_json(path, {"keep": True}))
            self.assertFalse(skippy_profile_store.write_json(path, {"bad": object()}))
            self.assertEqual(os.listdir(tmp), ["data.json"])
            with open(path, encoding="utf-8") as handle:
                self.assertEqual(json.load(handle), {"keep": True})


class SkipDialogLifecycleTests(unittest.TestCase):
    def _dialog(self, player):
        dlg = skipdialog.SkipDialog.__new__(skipdialog.SkipDialog)
        dlg.segment = SegmentItem(10.0, 40.0, "intro", source="xml")
        dlg._total_duration = 30.0
        dlg._minimal_mode = True
        dlg._closing = False
        dlg._start_time = 0.0
        dlg.player = player
        dlg.response = "unset"
        dlg._skippy_dialog_result = "unset"
        dlg.close = MagicMock()
        dlg.setProperty = MagicMock()
        dlg._refresh_countdown_label = MagicMock()
        dlg._refresh_skip_duration_label = MagicMock()
        return dlg

    def test_active_elapsed_ignores_paused_time(self):
        self.assertEqual(skipdialog.advance_active_elapsed(3.0, 2.0, paused=False), 5.0)
        self.assertEqual(skipdialog.advance_active_elapsed(3.0, 2.0, paused=True), 3.0)
        self.assertEqual(skipdialog.advance_active_elapsed(3.0, -1.0, paused=False), 3.0)

    def test_playback_gone_needs_the_grace_period(self):
        self.assertFalse(skipdialog.playback_gone_long_enough(None, 100.0))
        self.assertFalse(skipdialog.playback_gone_long_enough(100.0, 100.2))
        self.assertTrue(skipdialog.playback_gone_long_enough(100.0, 101.0))

    def test_dialog_closes_without_a_choice_when_playback_stops(self):
        player = MagicMock()
        player.isPlaying.return_value = False
        dlg = self._dialog(player)
        with patch.object(skipdialog, "PLAYBACK_STOP_GRACE_S", 0.0), patch.object(
            skipdialog, "log"
        ):
            dlg._monitor_segment_end()
        dlg.close.assert_called_once()
        self.assertIsNone(dlg._skippy_dialog_result)
        self.assertIsNone(dlg.response)

    def test_get_time_error_closes_instead_of_sticking(self):
        player = MagicMock()
        player.isPlaying.return_value = True
        player.getTime.side_effect = RuntimeError("playback ended")
        dlg = self._dialog(player)
        with patch.object(skipdialog, "PLAYBACK_STOP_GRACE_S", 0.0), patch.object(
            skipdialog, "log"
        ):
            dlg._monitor_segment_end()
        dlg.close.assert_called_once()
        self.assertIsNone(dlg._skippy_dialog_result)

    def test_unexpected_error_in_the_monitor_closes_the_dialog(self):
        player = MagicMock()
        player.isPlaying.side_effect = ValueError("boom")
        dlg = self._dialog(player)
        with patch.object(skipdialog, "log_always"):
            dlg._monitor_segment_end()
        dlg.close.assert_called_once()
        self.assertIsNone(dlg._skippy_dialog_result)

    def test_paused_dialog_is_not_declined_by_the_timeout(self):
        player = MagicMock()
        player.isPlaying.return_value = True
        times = iter([12.0, 12.0, 12.0, 12.0, 41.0])
        player.getTime.side_effect = lambda: next(times)
        dlg = self._dialog(player)
        dlg._total_duration = 0.0  # timeout would be 5 s of dialog time
        clock = {"t": 1000.0}

        def _time():
            clock["t"] += 60.0  # every poll is a minute later on the wall clock
            return clock["t"]

        with patch.object(skipdialog.time, "time", _time), patch.object(
            skipdialog.time, "sleep", lambda _s: None
        ), patch.object(
            skipdialog.xbmc, "getCondVisibility", lambda cond: cond == "Player.Paused"
        ), patch.object(skipdialog, "log"):
            dlg._monitor_segment_end()
        # Ended because the playhead reached the segment end, not the timeout.
        self.assertEqual(dlg._skippy_dialog_result, False)
        self.assertEqual(player.getTime.call_count, 5)


class NestedSelfParentTests(unittest.TestCase):
    def test_near_identical_nested_segments_get_no_self_parent(self):
        parent = SegmentItem(10.2, 20.4, "intro", source="xml")
        child = SegmentItem(10.4, 20.1, "recap", source="xml")
        self.assertEqual(build_nested_parent_map([parent, child]), {})

    def test_dismissal_is_kept_for_near_identical_nested_segments(self):
        parent = SegmentItem(10.2, 20.4, "intro", source="xml")
        child = SegmentItem(10.4, 20.1, "recap", source="xml")
        monitor = types.SimpleNamespace(
            current_segments=[parent, child],
            recently_dismissed={(10, 20)},
            prompted={(10, 20)},
            cleared_parent_dismissals=set(),
            # A map written by an older build, with the self-parent entry.
            nested_parent_map={(10, 20): (10, 20)},
        )
        ctx = types.SimpleNamespace(monitor=monitor, log_if_changed=lambda *a, **k: None)
        service_loop_nested._clear_parent_dismissals_when_inside_nested(ctx, 15.0)
        self.assertEqual(monitor.recently_dismissed, {(10, 20)})
        self.assertEqual(monitor.prompted, {(10, 20)})

    def test_real_parent_dismissal_is_still_cleared_inside_the_nested_child(self):
        parent = SegmentItem(0.0, 100.0, "recap", source="xml")
        child = SegmentItem(75.0, 90.0, "prologue", source="xml")
        monitor = types.SimpleNamespace(
            current_segments=[parent, child],
            recently_dismissed={(0, 100)},
            prompted={(0, 100)},
            cleared_parent_dismissals=set(),
            nested_parent_map=build_nested_parent_map([parent, child]),
        )
        ctx = types.SimpleNamespace(monitor=monitor, log_if_changed=lambda *a, **k: None)
        service_loop_nested._clear_parent_dismissals_when_inside_nested(ctx, 80.0)
        self.assertEqual(monitor.recently_dismissed, set())


class _FakeVfs:
    """Dict-backed xbmcvfs for the write paths."""

    def __init__(self, files=None, fail_writes=False):
        self.files = dict(files or {})
        self.fail_writes = fail_writes
        outer = self

        class File:
            def __init__(self, path, mode="r"):
                self.path, self.mode = path, mode
                if "w" in mode:
                    outer.files[path] = b""  # opening for write creates an empty file

            def write(self, data):
                if outer.fail_writes:
                    return False
                if isinstance(data, str):
                    data = data.encode("utf-8")
                outer.files[self.path] = bytes(data)
                return True

            def readBytes(self):
                return bytearray(outer.files.get(self.path, b""))

            def read(self):
                return outer.files.get(self.path, b"").decode("utf-8")

            def close(self):
                pass

        self.File = File

    def exists(self, path):
        return path in self.files

    def delete(self, path):
        self.files.pop(path, None)
        return True


class SafeWriteTests(unittest.TestCase):
    def _patched(self, fake):
        return patch.multiple(
            segment_editor_parser,
            xbmcvfs=fake,
            _apply_skippy_file_permissions=lambda _p: None,
            log=lambda *a, **k: None,
        )

    def test_successful_overwrite_replaces_the_content(self):
        fake = _FakeVfs({"/v.edl": b"old old old old"})
        with self._patched(fake), patch.object(segment_editor_parser.time, "sleep", lambda _s: None):
            ok, _n = segment_editor_parser.safe_file_write("/v.edl", "new")
        self.assertTrue(ok)
        self.assertEqual(fake.files["/v.edl"], b"new")

    def test_failed_write_with_missing_file_restores_original_bytes(self):
        fake = _FakeVfs({"/v.edl": b"10 20 4\n"})
        original_file = fake.File

        class _NoCreate(original_file):
            def __init__(self, path, mode="r"):
                self.path, self.mode = path, mode
                if "w" in mode and fake.fail_writes:
                    raise OSError("share is read-only")
                super().__init__(path, mode)

        fake.File = _NoCreate
        fake.fail_writes = True
        with self._patched(fake), patch.object(segment_editor_parser.time, "sleep", lambda _s: None):
            # The restore itself must still be allowed to write.
            real_restore = segment_editor_parser._restore_vfs_bytes

            def _restore(path, data):
                fake.fail_writes = False
                return real_restore(path, data)

            with patch.object(segment_editor_parser, "_restore_vfs_bytes", _restore):
                ok, _n = segment_editor_parser.safe_file_write("/v.edl", "new")
        self.assertFalse(ok)
        self.assertEqual(fake.files["/v.edl"], b"10 20 4\n")

    def test_marker_write_raises_when_the_write_fails(self):
        with patch.object(
            segment_marker, "safe_file_write", return_value=(False, None)
        ):
            with self.assertRaises(OSError):
                segment_marker.write_vfs_text("/v.edl", "10 20 4\n")

    def test_marker_write_passes_text_to_the_safe_writer(self):
        with patch.object(
            segment_marker, "safe_file_write", return_value=(True, 7)
        ) as writer:
            segment_marker.write_vfs_text("/v.edl", "10 20 4\n")
        writer.assert_called_once_with("/v.edl", "10 20 4\n", is_bytes=False)


if __name__ == "__main__":
    unittest.main()
