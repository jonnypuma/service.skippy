# -*- coding: utf-8 -*-
"""A segment made in the editor is listed under the file it will be saved to: Chapter file for XML or Both,
Local EDL only when the editor saves EDL only."""

import unittest

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import segment_editor_dialog as dlg  # noqa: E402
import segment_editor_layout as lay  # noqa: E402


class NewSegmentSourceTests(unittest.TestCase):
    def test_xml_and_both_list_a_chapter_file(self):
        for chosen in ("xml", "both", "XML", "Both"):
            self.assertEqual(dlg.new_segment_source(chosen), "xml", chosen)
            self.assertEqual(lay.source_name(dlg.new_segment_source(chosen)), "Chapter file")

    def test_edl_only_lists_local_edl(self):
        self.assertEqual(dlg.new_segment_source("edl"), "edl")
        self.assertEqual(lay.source_name(dlg.new_segment_source("EDL")), "Local EDL")

    def test_the_setting_decides_when_none_is_given(self):
        original = dlg.get_save_format
        try:
            dlg.get_save_format = lambda: "edl"
            self.assertEqual(dlg.new_segment_source(), "edl")
            dlg.get_save_format = lambda: "both"
            self.assertEqual(dlg.new_segment_source(), "xml")
        finally:
            dlg.get_save_format = original


if __name__ == "__main__":
    unittest.main()
