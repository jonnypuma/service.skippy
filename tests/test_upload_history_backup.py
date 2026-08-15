# -*- coding: utf-8 -*-
"""Profile-data backup: upload history, title autoskip, statistics."""

import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()


class UploadHistoryMergeTests(unittest.TestCase):
    def test_merge_unions_fingerprints(self):
        from online_segment_upload import (
            load_upload_submission_history,
            merge_upload_submission_history,
        )

        with tempfile.TemporaryDirectory() as tmp:
            prof = os.path.join(tmp, "profile")
            os.makedirs(prof)
            hist_path = os.path.join(prof, "online_upload_submissions.json")
            with open(hist_path, "w", encoding="utf-8") as fp:
                json.dump(
                    {
                        "v": 1,
                        "theintrodb": ["aaa"],
                        "introdb": [],
                    },
                    fp,
                )

            with patch("online_segment_upload._history_path", return_value=hist_path):
                added, already = merge_upload_submission_history(
                    {
                        "v": 1,
                        "theintrodb": ["aaa", "bbb"],
                        "introdb": ["ccc"],
                    }
                )
                self.assertEqual(added, 2)
                self.assertEqual(already, 1)
                data = load_upload_submission_history()
                self.assertEqual(sorted(data["theintrodb"]), ["aaa", "bbb"])
                self.assertEqual(data["introdb"], ["ccc"])


class ProfileDataBackupFileTests(unittest.TestCase):
    def test_export_and_merge_includes_overrides_and_stats(self):
        import per_show_overrides
        import skippy_profile_store
        import skippy_stats
        from skippy_profile_backup import (
            SCHEMA,
            export_to_path,
            import_merge_from_path,
        )

        with tempfile.TemporaryDirectory() as tmp:
            prof = os.path.join(tmp, "profile")
            os.makedirs(prof)
            hist_path = os.path.join(prof, "online_upload_submissions.json")
            backup_path = os.path.join(tmp, "backup.json")

            with open(hist_path, "w", encoding="utf-8") as fp:
                json.dump({"v": 1, "theintrodb": ["fp1"], "introdb": []}, fp)

            with patch("online_segment_upload._history_path", return_value=hist_path):
                with patch.object(
                    skippy_profile_store, "profile_dir", return_value=prof
                ):
                    skippy_stats.clear_cache()
                    per_show_overrides.clear_cache()
                    skippy_stats.record_skip("Intro", 30.0)
                    skippy_stats.record_online_segment_uploaded()
                    per_show_overrides.save_override(
                        "tv_tmdb_1396",
                        "Intro",
                        per_show_overrides.MODE_AUTO,
                        title="Friends",
                    )

                    addon = MagicMock()
                    addon.getAddonInfo.side_effect = lambda k: {
                        "version": "5.5.2",
                        "profile": prof,
                    }.get(k, "")

                    counts = export_to_path(addon, backup_path)
                    self.assertEqual(counts["fingerprints"], 1)
                    self.assertEqual(counts["override_titles"], 1)
                    self.assertEqual(counts["skip_total"], 1)

                    with open(backup_path, encoding="utf-8") as fp:
                        payload = json.load(fp)
                    self.assertEqual(payload["schema"], SCHEMA)
                    self.assertIn("show_overrides", payload)
                    self.assertIn("statistics", payload)
                    self.assertEqual(
                        payload["show_overrides"]["tv_tmdb_1396"]["segments"]["intro"],
                        "auto",
                    )

                    # Local machine has different history + empty overrides/stats after wipe.
                    with open(hist_path, "w", encoding="utf-8") as fp:
                        json.dump(
                            {"v": 1, "theintrodb": ["existing"], "introdb": []},
                            fp,
                        )
                    for path in per_show_overrides.stored_override_files():
                        os.remove(path)
                    per_show_overrides.clear_cache()
                    skippy_stats.reset_statistics()
                    skippy_stats.record_skip("Recap", 10.0)  # lower totals than backup

                    payload["online_upload_submissions"]["theintrodb"] = [
                        "existing",
                        "fp1",
                    ]
                    with open(backup_path, "w", encoding="utf-8") as fp:
                        json.dump(payload, fp)

                    summary, _note = import_merge_from_path(addon, backup_path)
                    self.assertEqual(summary["history_added"], 1)
                    self.assertEqual(summary["history_already"], 1)
                    self.assertEqual(summary["override_titles"], 1)
                    self.assertGreaterEqual(summary["override_segments_added"], 1)
                    self.assertTrue(summary["stats_merged"])

                    self.assertEqual(
                        per_show_overrides.lookup_override("tv_tmdb_1396", "Intro"),
                        per_show_overrides.MODE_AUTO,
                    )
                    stats = skippy_stats.load_statistics()
                    self.assertEqual(stats["skips"]["by_type"]["intro"], 1)
                    self.assertEqual(stats["skips"]["by_type"]["recap"], 1)
                    self.assertEqual(stats["skips"]["total"], 2)
                    self.assertGreaterEqual(stats["skips"]["seconds_saved"], 30.0)
                    self.assertEqual(stats["online"]["segments_uploaded"], 1)

    def test_legacy_upload_history_schema_still_merges(self):
        from skippy_profile_backup import LEGACY_SCHEMA, import_merge_from_path

        with tempfile.TemporaryDirectory() as tmp:
            prof = os.path.join(tmp, "profile")
            os.makedirs(prof)
            hist_path = os.path.join(prof, "online_upload_submissions.json")
            backup_path = os.path.join(tmp, "legacy.json")
            with open(hist_path, "w", encoding="utf-8") as fp:
                json.dump({"v": 1, "theintrodb": ["aaa"], "introdb": []}, fp)
            with open(backup_path, "w", encoding="utf-8") as fp:
                json.dump(
                    {
                        "schema": LEGACY_SCHEMA,
                        "addon_id": "service.skippy",
                        "addon_version_exported": "5.2.0",
                        "online_upload_submissions": {
                            "v": 1,
                            "theintrodb": ["aaa", "bbb"],
                            "introdb": [],
                        },
                    },
                    fp,
                )

            addon = MagicMock()
            addon.getAddonInfo.return_value = "5.5.2"
            with patch("online_segment_upload._history_path", return_value=hist_path):
                summary, _note = import_merge_from_path(addon, backup_path)
            self.assertEqual(summary["history_added"], 1)
            self.assertEqual(summary["history_already"], 1)
            self.assertEqual(summary["override_titles"], 0)
            self.assertFalse(summary["stats_merged"])


if __name__ == "__main__":
    unittest.main()
