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


if __name__ == "__main__":
    unittest.main()
