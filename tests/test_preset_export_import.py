import json
import unittest
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import skip_dialog_presets_ui as ui  # noqa: E402


class FakeFile:
    store = {}

    def __init__(self, path, mode="r"):
        self.path, self.mode = path, mode

    def write(self, text):
        FakeFile.store[self.path] = text
        return True

    def read(self, *_a):
        return FakeFile.store.get(self.path, "")

    def close(self):
        pass


class PresetExportImportTests(unittest.TestCase):
    def setUp(self):
        FakeFile.store = {}

    def test_export_writes_saved_presets_json(self):
        blob = {"schema": 1, "presets": {"Mine": {"values": {"skip_dialog_mode": "Full"}}}}
        with patch.object(ui.sp, "export_user_presets", return_value=blob), \
             patch.object(ui.xbmcvfs, "File", FakeFile), \
             patch.object(ui.xbmcgui, "Dialog") as dlg, \
             patch.object(ui, "notify_skippy") as notify:
            dlg.return_value.browse.return_value = "special://home/"
            ui._export_saved(MagicMock())
        (path, text), = FakeFile.store.items()
        self.assertTrue(path.startswith("special://home/skippy-presets-") and path.endswith(".json"))
        self.assertEqual(json.loads(text), blob)
        notify.assert_called_once()

    def test_export_with_no_saved_presets_does_not_browse(self):
        with patch.object(ui.sp, "export_user_presets", return_value={"presets": {}}), \
             patch.object(ui.xbmcgui, "Dialog") as dlg, \
             patch.object(ui, "notify_skippy"):
            ui._export_saved(MagicMock())
        dlg.return_value.browse.assert_not_called()

    def test_import_merges_presets_from_file(self):
        FakeFile.store["/x/p.json"] = json.dumps({"presets": {}})
        with patch.object(ui.xbmcvfs, "File", FakeFile), \
             patch("settings_backup._restore_browse_result_is_json_file", return_value=True), \
             patch.object(ui.xbmcgui, "Dialog") as dlg, \
             patch.object(ui.sp, "merge_user_presets_from_backup", return_value=2) as merge, \
             patch.object(ui, "notify_skippy"):
            dlg.return_value.browse.return_value = "/x/p.json"
            ui._import_presets(MagicMock())
        merge.assert_called_once_with({"presets": {}})


if __name__ == "__main__":
    unittest.main()
