# -*- coding: utf-8 -*-
"""Statistics counters, the statistics modal text, and per-title override storage."""

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import per_show_overrides
import skippy_profile_store
import skippy_statistics_ui
import skippy_stats


class _ProfileTempDir(unittest.TestCase):
    """Point the profile store at a throwaway directory for each test."""

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


class StatisticsTests(_ProfileTempDir):
    def test_skips_accumulate_per_type_and_total(self):
        skippy_stats.record_skip("Intro", 62.5)
        skippy_stats.record_skip("intro", 30.0)
        skippy_stats.record_skip("Recap", 20.25)

        stats = skippy_stats.load_statistics()
        self.assertEqual(stats["skips"]["total"], 3)
        self.assertEqual(stats["skips"]["by_type"], {"intro": 2, "recap": 1})
        self.assertAlmostEqual(stats["skips"]["seconds_saved"], 112.75, places=3)

    def test_online_counters_are_separate(self):
        skippy_stats.record_online_segments_downloaded(4)
        skippy_stats.record_online_segments_downloaded(0)
        skippy_stats.record_online_segment_uploaded()

        stats = skippy_stats.load_statistics()
        self.assertEqual(stats["online"]["segments_downloaded"], 4)
        self.assertEqual(stats["online"]["segments_uploaded"], 1)

    def test_counters_survive_a_cache_drop(self):
        skippy_stats.record_skip("Intro", 10.0)
        skippy_stats.clear_cache()
        self.assertEqual(skippy_stats.load_statistics()["skips"]["total"], 1)

    def test_returned_stats_are_a_copy(self):
        skippy_stats.record_skip("Intro", 10.0)
        stats = skippy_stats.load_statistics()
        stats["skips"]["by_type"]["intro"] = 99
        stats["skips"]["total"] = 99
        self.assertEqual(
            skippy_stats.load_statistics()["skips"]["by_type"], {"intro": 1}
        )
        self.assertEqual(skippy_stats.load_statistics()["skips"]["total"], 1)

    def test_reset_zeroes_everything(self):
        skippy_stats.record_skip("Intro", 10.0)
        skippy_stats.record_online_segment_uploaded()
        skippy_stats.reset_statistics()

        stats = skippy_stats.load_statistics()
        self.assertEqual(stats["skips"]["total"], 0)
        self.assertEqual(stats["skips"]["by_type"], {})
        self.assertEqual(stats["online"]["segments_uploaded"], 0)

    def test_corrupt_file_falls_back_to_empty(self):
        path = skippy_profile_store.profile_path(skippy_stats.STATS_FILENAME)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("{not json")
        self.assertEqual(skippy_stats.load_statistics()["skips"]["total"], 0)


class StatisticsTextTests(_ProfileTempDir):
    def test_saved_time_units(self):
        addon = None
        self.assertEqual(skippy_statistics_ui.format_saved_time(addon, 45), "45s")
        self.assertEqual(skippy_statistics_ui.format_saved_time(addon, 125), "2m 05s")
        self.assertEqual(skippy_statistics_ui.format_saved_time(addon, 8100), "2h 15m")
        self.assertEqual(skippy_statistics_ui.format_saved_time(addon, -5), "0s")
        self.assertEqual(skippy_statistics_ui.format_saved_time(addon, None), "0s")

    def test_body_lists_totals_and_types(self):
        skippy_stats.record_skip("Intro", 90.0)
        skippy_stats.record_skip("Intro", 30.0)
        skippy_stats.record_skip("Recap", 20.0)
        skippy_stats.record_online_segments_downloaded(7)
        skippy_stats.record_online_segment_uploaded(2)

        text = skippy_statistics_ui.build_statistics_text(None)
        self.assertIn("Time saved: 2m 20s", text)
        self.assertIn("Segments skipped: 3", text)
        self.assertIn("Intro: 2", text)
        self.assertIn("Recap: 1", text)
        self.assertIn("Online segments downloaded: 7", text)
        self.assertIn("Online segments uploaded: 2", text)
        self.assertLess(text.index("Intro: 2"), text.index("Recap: 1"))

    def test_body_without_skips_shows_placeholder(self):
        text = skippy_statistics_ui.build_statistics_text(None)
        self.assertIn("No skips recorded yet", text)
        self.assertIn("Segments skipped: 0", text)

    def test_modal_is_read_only(self):
        skippy_stats.record_skip("Intro", 30.0)
        skin = MagicMock()
        with patch.dict(
            "sys.modules", {"skippy_editor_modal_skin": skin}, clear=False
        ):
            skippy_statistics_ui.show_statistics_modal()
        heading, body = skin.show_editor_ok.call_args[0][:2]
        self.assertIn("Statistics", heading)
        self.assertIn("Segments skipped: 1", body)
        self.assertEqual(skippy_stats.load_statistics()["skips"]["total"], 1)

    def test_reset_needs_confirmation(self):
        skippy_stats.record_skip("Intro", 30.0)
        skin = MagicMock()
        skin.sidecar_overwrite_yesno_show.return_value = False
        with patch.dict(
            "sys.modules", {"skippy_editor_modal_skin": skin}, clear=False
        ):
            skippy_statistics_ui.confirm_and_reset_statistics()
        self.assertEqual(skippy_stats.load_statistics()["skips"]["total"], 1)

        skin.sidecar_overwrite_yesno_show.return_value = True
        with patch.dict(
            "sys.modules", {"skippy_editor_modal_skin": skin}, clear=False
        ):
            skippy_statistics_ui.confirm_and_reset_statistics()
        self.assertEqual(skippy_stats.load_statistics()["skips"]["total"], 0)


class OverrideKeyTests(unittest.TestCase):
    def test_tmdb_id_preferred_over_imdb(self):
        key = per_show_overrides.override_key_for_identity(
            {"type": "episode", "tmdb_id": 1396, "imdb_id": "tt0903747"}
        )
        self.assertEqual(key, "tv_tmdb_1396")

    def test_imdb_fallback_and_movie_kind(self):
        key = per_show_overrides.override_key_for_identity(
            {"type": "movie", "imdb_id": "tt0133093"}
        )
        self.assertEqual(key, "movie_imdb_tt0133093")

    def test_no_ids_gives_no_key(self):
        self.assertIsNone(
            per_show_overrides.override_key_for_identity({"type": "movie"})
        )
        self.assertIsNone(per_show_overrides.override_key_for_identity(None))


class OverrideStoreTests(_ProfileTempDir):
    def test_save_and_lookup_is_label_normalized(self):
        self.assertTrue(
            per_show_overrides.save_override(
                "tv_tmdb_1396", "Intro", per_show_overrides.MODE_AUTO, title="Friends"
            )
        )
        self.assertEqual(
            per_show_overrides.lookup_override("tv_tmdb_1396", "intro"),
            per_show_overrides.MODE_AUTO,
        )
        self.assertIsNone(
            per_show_overrides.lookup_override("tv_tmdb_1396", "Recap")
        )
        self.assertIsNone(per_show_overrides.lookup_override("tv_tmdb_9999", "Intro"))

    def test_declined_is_remembered_so_we_stop_asking(self):
        per_show_overrides.save_override(
            "movie_tmdb_603", "Credits", per_show_overrides.MODE_DECLINED
        )
        self.assertEqual(
            per_show_overrides.lookup_override("movie_tmdb_603", "credits"),
            per_show_overrides.MODE_DECLINED,
        )

    def test_second_segment_type_keeps_the_first(self):
        per_show_overrides.save_override(
            "tv_tmdb_1396", "Intro", per_show_overrides.MODE_AUTO
        )
        per_show_overrides.save_override(
            "tv_tmdb_1396", "Recap", per_show_overrides.MODE_DECLINED
        )
        per_show_overrides.clear_cache()
        stored = per_show_overrides.load_overrides("tv_tmdb_1396")
        self.assertEqual(
            stored,
            {
                "intro": per_show_overrides.MODE_AUTO,
                "recap": per_show_overrides.MODE_DECLINED,
            },
        )

    def test_one_file_per_title(self):
        per_show_overrides.save_override(
            "tv_tmdb_1396", "Intro", per_show_overrides.MODE_AUTO
        )
        per_show_overrides.save_override(
            "movie_tmdb_603", "Intro", per_show_overrides.MODE_AUTO
        )
        files = [
            os.path.basename(p) for p in per_show_overrides.stored_override_files()
        ]
        self.assertEqual(files, ["movie_tmdb_603.json", "tv_tmdb_1396.json"])

    def test_path_traversal_keys_are_refused(self):
        self.assertFalse(
            per_show_overrides.save_override(
                "../evil", "Intro", per_show_overrides.MODE_AUTO
            )
        )
        self.assertEqual(per_show_overrides.stored_override_files(), [])

    def test_invalid_mode_is_refused(self):
        self.assertFalse(
            per_show_overrides.save_override("tv_tmdb_1396", "Intro", "maybe")
        )
        self.assertEqual(per_show_overrides.stored_override_files(), [])

    def test_clear_all_removes_every_file(self):
        per_show_overrides.save_override(
            "tv_tmdb_1396", "Intro", per_show_overrides.MODE_AUTO
        )
        per_show_overrides.save_override(
            "movie_tmdb_603", "Intro", per_show_overrides.MODE_DECLINED
        )
        self.assertEqual(per_show_overrides.clear_all_overrides(), 2)
        self.assertEqual(per_show_overrides.stored_override_files(), [])
        self.assertIsNone(per_show_overrides.lookup_override("tv_tmdb_1396", "Intro"))
        self.assertEqual(per_show_overrides.clear_all_overrides(), 0)

    def test_list_title_entries_auto_only_and_sorted(self):
        per_show_overrides.save_override(
            "tv_tmdb_1396", "Intro", per_show_overrides.MODE_AUTO, title="Friends"
        )
        per_show_overrides.save_override(
            "tv_tmdb_1396", "Recap", per_show_overrides.MODE_AUTO, title="Friends"
        )
        per_show_overrides.save_override(
            "movie_tmdb_603", "Credits", per_show_overrides.MODE_DECLINED, title="The Matrix"
        )
        per_show_overrides.save_override(
            "movie_tmdb_11", "Intro", per_show_overrides.MODE_AUTO, title="Star Wars"
        )

        entries = per_show_overrides.list_title_entries(auto_only=True)
        self.assertEqual([e["title"] for e in entries], ["Friends", "Star Wars"])
        self.assertEqual(entries[0]["auto_labels"], ["intro", "recap"])
        self.assertEqual(entries[0]["key"], "tv_tmdb_1396")

        all_entries = per_show_overrides.list_title_entries(auto_only=False)
        self.assertEqual(
            [e["title"] for e in all_entries],
            ["Friends", "Star Wars", "The Matrix"],
        )

    def test_list_falls_back_to_id_when_title_missing(self):
        per_show_overrides.save_override(
            "tv_tmdb_1396", "Intro", per_show_overrides.MODE_AUTO
        )
        entries = per_show_overrides.list_title_entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["title"], "TV · TMDB 1396")

    def test_delete_override_removes_one_title(self):
        per_show_overrides.save_override(
            "tv_tmdb_1396", "Intro", per_show_overrides.MODE_AUTO, title="Friends"
        )
        per_show_overrides.save_override(
            "movie_tmdb_11", "Intro", per_show_overrides.MODE_AUTO, title="Star Wars"
        )
        self.assertTrue(per_show_overrides.delete_override("tv_tmdb_1396"))
        self.assertIsNone(per_show_overrides.lookup_override("tv_tmdb_1396", "Intro"))
        self.assertEqual(
            per_show_overrides.lookup_override("movie_tmdb_11", "Intro"),
            per_show_overrides.MODE_AUTO,
        )
        self.assertFalse(per_show_overrides.delete_override("tv_tmdb_1396"))
        self.assertFalse(per_show_overrides.delete_override("../evil"))


class ManageTitleAutoskipUiTests(_ProfileTempDir):
    def test_format_title_entry_label(self):
        from per_show_overrides_ui import format_title_entry_label

        label = format_title_entry_label(
            {
                "title": "Friends",
                "auto_labels": ["intro", "recap"],
            }
        )
        self.assertEqual(label, "Friends — Intro, Recap")

    def test_manage_modal_deletes_selected_title_and_loops(self):
        import per_show_overrides_ui

        per_show_overrides.save_override(
            "tv_tmdb_1396", "Intro", per_show_overrides.MODE_AUTO, title="Friends"
        )
        per_show_overrides.save_override(
            "movie_tmdb_11", "Intro", per_show_overrides.MODE_AUTO, title="Star Wars"
        )

        skin = MagicMock()
        # First open: pick Friends (index 0), confirm delete.
        # Second open: only Star Wars left — cancel/close.
        skin.show_editor_list_pick.side_effect = [0, -1]
        skin.sidecar_overwrite_yesno_show.return_value = True

        with patch.dict("sys.modules", {"skippy_editor_modal_skin": skin}, clear=False):
            with patch.object(per_show_overrides_ui, "notify_skippy") as notify:
                per_show_overrides_ui.show_manage_title_autoskip_modal()

        self.assertIsNone(per_show_overrides.lookup_override("tv_tmdb_1396", "Intro"))
        self.assertEqual(
            per_show_overrides.lookup_override("movie_tmdb_11", "Intro"),
            per_show_overrides.MODE_AUTO,
        )
        self.assertEqual(skin.show_editor_list_pick.call_count, 2)
        notify.assert_called()

    def test_manage_modal_empty_shows_ok(self):
        import per_show_overrides_ui

        skin = MagicMock()
        with patch.dict("sys.modules", {"skippy_editor_modal_skin": skin}, clear=False):
            per_show_overrides_ui.show_manage_title_autoskip_modal()
        skin.show_editor_ok.assert_called_once()
        skin.show_editor_list_pick.assert_not_called()

    def test_manage_modal_cancel_delete_keeps_entry(self):
        import per_show_overrides_ui

        per_show_overrides.save_override(
            "tv_tmdb_1396", "Intro", per_show_overrides.MODE_AUTO, title="Friends"
        )
        skin = MagicMock()
        skin.show_editor_list_pick.side_effect = [0, -1]
        skin.sidecar_overwrite_yesno_show.return_value = False
        with patch.dict("sys.modules", {"skippy_editor_modal_skin": skin}, clear=False):
            per_show_overrides_ui.show_manage_title_autoskip_modal()
        self.assertEqual(
            per_show_overrides.lookup_override("tv_tmdb_1396", "Intro"),
            per_show_overrides.MODE_AUTO,
        )


if __name__ == "__main__":
    unittest.main()
