# -*- coding: utf-8 -*-
import unittest

from tests.kodi_stubs import install_kodi_stubs


class TestChapterXmlDefaultPath(unittest.TestCase):
    def setUp(self):
        install_kodi_stubs()

    def test_default_write_suffix(self):
        from segment_editor_parser import (
            CHAPTER_XML_SIDECAR_SUFFIXES,
            DEFAULT_NEW_CHAPTER_XML_SUFFIX,
        )
        from service_sidecar_paths import _default_new_sidecar_chapter_xml_path

        self.assertEqual(DEFAULT_NEW_CHAPTER_XML_SUFFIX, "_chapters.xml")
        self.assertEqual(
            _default_new_sidecar_chapter_xml_path("/media/show.mkv"),
            "/media/show_chapters.xml",
        )

    def test_read_suffixes_include_common_variants(self):
        from segment_editor_parser import CHAPTER_XML_SIDECAR_SUFFIXES

        for suffix in ("_chapters.xml", "-chapters.xml", ".chapters.xml"):
            self.assertIn(suffix, CHAPTER_XML_SIDECAR_SUFFIXES)


if __name__ == "__main__":
    unittest.main()
