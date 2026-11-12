# -*- coding: utf-8 -*-
"""Time saved per show or film, and the "Current video" window."""

import json
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import service_diagnostics  # noqa: E402
import skippy_diagnostics_ui as diag_ui  # noqa: E402
import skippy_profile_store  # noqa: E402
import skippy_statistics_ui  # noqa: E402
import skippy_stats  # noqa: E402
from segment_types import seeded_builtin_types, set_catalog_for_tests  # noqa: E402


def _addon(**settings):
    addon = MagicMock()
    addon.getSetting.side_effect = lambda key: settings.get(key, "")
    addon.getLocalizedString.side_effect = lambda _sid: ""
    return addon


class _ProfileTempDir(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        patcher = patch.object(skippy_profile_store, "profile_dir", return_value=self._tmp.name)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)
        skippy_stats.clear_cache()
        self.addCleanup(skippy_stats.clear_cache)


class TitleStatisticsTests(_ProfileTempDir):
    def test_skips_add_up_per_title(self):
        skippy_stats.record_skip("intro", 60.0, title=("tv:1", "The Office"))
        skippy_stats.record_skip("recap", 30.5, title=("tv:1", "The Office"))
        skippy_stats.record_skip("intro", 40.0, title=("movie:dune", "Dune"))
        skippy_stats.record_skip("intro", 10.0)  # unknown title: totals only
        stats = skippy_stats.load_statistics()
        self.assertEqual(stats["skips"]["total"], 4)
        self.assertEqual(
            stats["skips"]["by_title"],
            {
                "tv:1": {"name": "The Office", "skips": 2, "seconds_saved": 90.5},
                "movie:dune": {"name": "Dune", "skips": 1, "seconds_saved": 40.0},
            },
        )

    def test_survives_a_reload_and_bad_rows_are_dropped(self):
        skippy_stats.record_skip("intro", 60.0, title=("tv:1", "Arrow"))
        skippy_stats.clear_cache()
        self.assertEqual(skippy_stats.load_statistics()["skips"]["by_title"]["tv:1"]["skips"], 1)
        raw = {"skips": {"by_title": {"ok": {"name": "A", "skips": "3", "seconds_saved": "5"},
                                      "": {"skips": 1}, "bad": "x"}}}
        self.assertEqual(
            skippy_stats._normalized(raw)["skips"]["by_title"],
            {"ok": {"name": "A", "skips": 3, "seconds_saved": 5.0}},
        )

    def test_old_files_without_titles_still_load(self):
        stats = skippy_stats._normalized({"skips": {"total": 4, "seconds_saved": 9}})
        self.assertEqual(stats["skips"]["by_title"], {})

    def test_backup_merge_keeps_the_larger_counts(self):
        skippy_stats.record_skip("intro", 60.0, title=("tv:1", "Arrow"))
        incoming = {"skips": {"total": 9, "by_title": {
            "tv:1": {"name": "Arrow", "skips": 5, "seconds_saved": 30.0},
            "tv:2": {"name": "Lost", "skips": 2, "seconds_saved": 80.0}}}}
        self.assertTrue(skippy_stats.merge_statistics_from_backup(incoming))
        titles = skippy_stats.load_statistics()["skips"]["by_title"]
        self.assertEqual(titles["tv:1"], {"name": "Arrow", "skips": 5, "seconds_saved": 60.0})
        self.assertEqual(titles["tv:2"]["name"], "Lost")
        self.assertFalse(skippy_stats.merge_statistics_from_backup(incoming))

    def test_reset_clears_titles(self):
        skippy_stats.record_skip("intro", 60.0, title=("tv:1", "Arrow"))
        skippy_stats.reset_statistics()
        self.assertEqual(skippy_stats.load_statistics()["skips"]["by_title"], {})


class TitleStatisticsWindowTests(unittest.TestCase):
    def stats(self, by_title):
        return {"since_utc": "2026-01-01", "skips": {"total": 1, "seconds_saved": 60,
                "by_type": {"intro": 1}, "by_title": by_title}, "online": {}}

    def test_section_lists_titles_most_time_saved_first(self):
        rows, _ = skippy_statistics_ui.build_statistics_rows(_addon(), self.stats({
            "tv:1": {"name": "Arrow", "skips": 3, "seconds_saved": 90},
            "tv:2": {"name": "Lost", "skips": 9, "seconds_saved": 3700},
        }))
        labels = [(r.label, r.label2, r.header) for r in rows]
        start = labels.index(("Time saved by show or film", "", True))
        self.assertEqual(labels[start + 1], ("Lost", "1h 01m", False))
        self.assertEqual(labels[start + 2], ("Arrow", "1m 30s", False))

    def test_no_titles_no_section(self):
        rows, _ = skippy_statistics_ui.build_statistics_rows(_addon(), self.stats({}))
        self.assertNotIn("Time saved by show or film", [r.label for r in rows])

    def test_long_lists_end_with_the_rest_summed(self):
        many = {"k%d" % i: {"name": "Show %02d" % i, "skips": 1, "seconds_saved": 100 - i}
                for i in range(30)}
        lines = skippy_statistics_ui._title_lines(_addon(), many)
        self.assertEqual(len(lines), skippy_statistics_ui.MAX_TITLE_ROWS + 1)
        self.assertEqual(lines[0], ("Show 00", "1m 40s"))
        self.assertEqual(lines[-1], ("And 5 more", "6m 05s"))  # 75+74+73+72+71 = 365 s

    def test_text_form_has_the_titles(self):
        text = skippy_statistics_ui.build_statistics_text(_addon(), self.stats({
            "tv:1": {"name": "Arrow", "skips": 3, "seconds_saved": 90}}))
        self.assertIn("Time saved by show or film:", text)
        self.assertIn("  • Arrow: 1m 30s", text)


class _FakeWindow:
    def __init__(self):
        self.props = {}

    def setProperty(self, key, value):
        self.props[key] = value

    def getProperty(self, key):
        return self.props.get(key, "")


class DiagnosticsPublishTests(unittest.TestCase):
    def setUp(self):
        self.win = _FakeWindow()
        patcher = patch.object(service_diagnostics, "_window", return_value=self.win)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_publish_merges_and_writes_only_on_change(self):
        monitor = MagicMock(spec=[])
        service_diagnostics.publish_diagnostics(monitor, video="/a.mkv", binge_position=1)
        first = self.win.props[service_diagnostics.DIAG_WIN_PROP]
        with patch.object(self.win, "setProperty") as write:
            service_diagnostics.publish_diagnostics(monitor, video="/a.mkv")
            write.assert_not_called()
        service_diagnostics.publish_diagnostics(monitor, binge_position=2)
        data = service_diagnostics.read_diagnostics()
        self.assertEqual((data["video"], data["binge_position"]), ("/a.mkv", 2))
        self.assertNotEqual(first, self.win.props[service_diagnostics.DIAG_WIN_PROP])

    def test_last_error_and_bad_payloads(self):
        monitor = MagicMock(spec=[])
        service_diagnostics.note_loop_error(monitor, "NameError: x", now=0)
        error = service_diagnostics.read_diagnostics()["last_error"]
        self.assertEqual((error["text"], error["where"]), ("NameError: x", "playback loop"))
        self.win.props[service_diagnostics.DIAG_WIN_PROP] = "not json"
        self.assertEqual(service_diagnostics.read_diagnostics(), {})
        self.win.props[service_diagnostics.DIAG_WIN_PROP] = json.dumps({"v": 99})
        self.assertEqual(service_diagnostics.read_diagnostics(), {})
        service_diagnostics.publish_diagnostics(None, video="x")


class DiagnosticsWindowTests(unittest.TestCase):
    def setUp(self):
        set_catalog_for_tests(seeded_builtin_types())
        self.addCleanup(set_catalog_for_tests, None)

    def seg(self, start, end, label, source="xml"):
        return SimpleNamespace(start_seconds=start, end_seconds=end, segment_type_label=label, source=source)

    def rows(self, addon, path="/tv/a2.mkv", diag=None, parse=None, override_key=None):
        rows, _ = diag_ui.build_diagnostics_rows(addon, path, diag, parse, override_key=override_key)
        return [(r.label, r.label2) for r in rows]

    def test_nothing_playing(self):
        rows = self.rows(_addon(), path="")
        self.assertEqual(rows[0], ("Nothing is playing.", ""))
        self.assertIn(("None since Kodi started", ""), rows)

    def test_full_picture_for_an_episode(self):
        addon = _addon(binge_mode_enabled="true", enable_skip_episodes="true")
        diag = {"video": "/tv/a2.mkv", "playback_type": "episode", "title": "Arrow",
                "binge_position": 2,
                "last_error": {"text": "NameError: x", "where": "playback loop", "at": "2026-11-12 03:00:00"}}
        parse = {"path": "/tv/a2.mkv", "playback_type": "episode", "segment_origin": "local",
                 "segments": [self.seg(60, 90, "intro"), self.seg(0, 50, "recap"),
                              self.seg(1300, 1400, "credits", "edl")]}
        with patch("segment_types.get_user_skip_mode",
                   side_effect=lambda label: {"credits": "never"}.get(label, "ask")):
            rows = self.rows(addon, diag=diag, parse=parse)
        self.assertIn(("File", "a2.mkv"), rows)
        self.assertIn(("Show", "Arrow"), rows)
        self.assertIn(("Binge run", "Episode 2"), rows)
        self.assertIn(("Segments from", "Sidecar file (.edl, chapters.xml)"), rows)
        self.assertIn(("Recap  0:00–0:50", "Skip automatically (binge mode)"), rows)
        self.assertIn(("Intro  1:00–1:30", "Skip automatically (binge mode)"), rows)
        self.assertIn(("Credits  21:40–23:20", "Never skip"), rows)
        self.assertIn(("2026-11-12 03:00:00", "playback loop"), rows)
        self.assertIn(("NameError: x", ""), rows)

    def test_segments_not_read_yet(self):
        rows = self.rows(_addon(), diag={"video": "/tv/a2.mkv"}, parse={"path": "/other.mkv"})
        self.assertIn(("Segments are still being read. Try again in a moment.", ""), rows)

    def test_no_segments_and_binge_off(self):
        diag = {"video": "/tv/a2.mkv", "playback_type": "episode", "binge_position": 3}
        parse = {"path": "/tv/a2.mkv", "segment_origin": "none", "segments": []}
        rows = self.rows(_addon(), diag=diag, parse=parse)
        self.assertIn(("Binge run", "Off"), rows)
        self.assertIn(("Segments from", "None found"), rows)
        self.assertIn(("No segments for this video.", ""), rows)

    def test_reasons(self):
        addon = _addon(per_show_autoskip_override="true", enable_skip_movies="true")
        with patch("segment_types.get_user_skip_mode", return_value="ask"), \
                patch("per_show_overrides.lookup_override", return_value="auto"):
            self.assertEqual(diag_ui.effective_mode(addon, "intro", "movie", "tmdb:1"), ("auto", "title"))
        with patch("segment_types.get_user_skip_mode", return_value="ask"):
            self.assertEqual(diag_ui.effective_mode(addon, "intro", "movie"), ("ask", None))
            off = _addon(enable_skip_movies="false")
            self.assertEqual(diag_ui.effective_mode(off, "intro", "movie"), ("never", "off"))
        self.assertEqual(diag_ui.mode_text(_addon(), "never", "off"),
                         "Never skip (skipping is off for this kind of video)")
        self.assertEqual(diag_ui.source_name("introdb"), "IntroDB.app")
        self.assertEqual(diag_ui.source_name("embedded"), "Embedded chapters")

    def test_modal_reads_the_mirrors(self):
        with patch.object(diag_ui, "_playing_path", return_value=""), \
                patch("skippy_panel_ui.show_panel_rows") as show:
            diag_ui.show_diagnostics_modal()
        heading, rows = show.call_args.args[:2]
        self.assertEqual(heading, "Current video")
        self.assertEqual(rows[0].label, "Nothing is playing.")


if __name__ == "__main__":
    unittest.main()
