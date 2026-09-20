# -*- coding: utf-8 -*-
"""SkipDialog result stash."""

import unittest
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()


class SkipDialogResultTests(unittest.TestCase):
    @patch("skipdialog.xbmcgui")
    def test_finish_dialog_stashes_result(self, _gui):
        from skipdialog import SkipDialog

        dlg = SkipDialog.__new__(SkipDialog)
        dlg.response = None
        dlg._skippy_dialog_result = None
        dlg.close = MagicMock()

        # Minimal _finish_dialog body if exists
        if hasattr(SkipDialog, "_finish_dialog"):
            dlg._finish_dialog(76.751)
            self.assertEqual(getattr(dlg, "_skippy_dialog_result", None), 76.751)

    @patch("skipdialog.xbmcgui")
    def test_onclick_stashes_computed_seek_destination(self, _gui):
        from segment_item import SegmentItem
        from skipdialog import SkipDialog

        dlg = SkipDialog.__new__(SkipDialog)
        dlg.segment = SegmentItem(0.0, 119.0, "intro", source="xml")
        dlg._finish_dialog = MagicMock()
        with patch("skipdialog.get_addon", return_value=MagicMock()), patch(
            "skipdialog.compute_skip_seek_destination_seconds", return_value=122.0
        ) as dest, patch("skipdialog.log") as logged:
            dlg.onClick(3012)
        dest.assert_called_once()
        dlg._finish_dialog.assert_called_once_with(122.0)
        self.assertIn("122", str(logged.call_args))


class SkipSeekDestinationTests(unittest.TestCase):
    def test_zero_next_start_is_kept(self):
        from segment_item import SegmentItem
        from settings_utils import compute_skip_seek_destination_seconds

        seg = SegmentItem(0.0, 40.0, "recap", source="xml")
        seg.next_segment_start = 0.0
        self.assertEqual(compute_skip_seek_destination_seconds(seg, None), 0.0)

    def test_jump_offset_is_added(self):
        from segment_item import SegmentItem
        from settings_utils import compute_skip_seek_destination_seconds

        seg = SegmentItem(0.0, 119.0, "intro", source="xml")
        addon = MagicMock()
        with patch("settings_utils.addon_get_int", return_value=2):
            self.assertEqual(compute_skip_seek_destination_seconds(seg, addon), 122.0)


if __name__ == "__main__":
    unittest.main()
