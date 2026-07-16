# -*- coding: utf-8 -*-
"""Upload submission history backup/merge."""

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


class UploadHistoryBackupFileTests(unittest.TestCase):
    def test_import_merge_from_path(self):
        from upload_history_backup import export_to_path, import_merge_from_path

        with tempfile.TemporaryDirectory() as tmp:
            prof = os.path.join(tmp, "profile")
            os.makedirs(prof)
            hist_path = os.path.join(prof, "online_upload_submissions.json")
            backup_path = os.path.join(tmp, "backup.json")

            with patch("online_segment_upload._history_path", return_value=hist_path):
                addon = MagicMock()
                addon.getAddonInfo.side_effect = lambda k: {
                    "version": "5.2.0",
                    "profile": prof,
                }.get(k, "")

                export_to_path(
                    addon,
                    backup_path,
                )
                with open(hist_path, "w", encoding="utf-8") as fp:
                    json.dump(
                        {"v": 1, "theintrodb": ["existing"], "introdb": []},
                        fp,
                    )
                with open(backup_path, encoding="utf-8") as fp:
                    payload = json.load(fp)
                payload["online_upload_submissions"]["theintrodb"] = [
                    "existing",
                    "newfp",
                ]
                with open(backup_path, "w", encoding="utf-8") as fp:
                    json.dump(payload, fp)

                added, already, _note = import_merge_from_path(addon, backup_path)
                self.assertEqual(added, 1)
                self.assertEqual(already, 1)


if __name__ == "__main__":
    unittest.main()
