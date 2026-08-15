# -*- coding: utf-8 -*-
"""Editor must not File() missing sidecar candidates."""

import unittest
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()


class EditorMissingSidecarTests(unittest.TestCase):
    def test_parse_chapters_does_not_open_unlisted_paths(self):
        from segment_editor_parser import parse_chapters

        candidates = [
            "/media/show_chapters.xml",
            "/media/show-chapters.xml",
            "/media/show.edl",
        ]
        opened = []

        class _File:
            def __init__(self, path):
                opened.append(path)

            def read(self):
                return ""

            def close(self):
                return None

        with patch(
            "segment_editor_parser._chapter_xml_paths_to_try",
            create=True,
        ), patch(
            "service_sidecar_paths._chapter_xml_paths_to_try",
            return_value=candidates,
        ), patch(
            "service_sidecar_paths.existing_paths_from_listing",
            return_value=([], []),
        ), patch(
            "service_sidecar_paths.vfs_file_exists",
            return_value=False,
        ), patch("segment_editor_parser.xbmcvfs.File", side_effect=_File):
            result = parse_chapters("/media/show.mkv")
        self.assertTrue(result is None or result == [])
        self.assertEqual(opened, [])

    def test_snapshot_used_for_local_origin(self):
        from types import SimpleNamespace

        import segment_editor_session as session

        segs = [
            SimpleNamespace(
                start_seconds=0.0,
                end_seconds=10.0,
                segment_type_label="intro",
                source="xml",
                action_type="5",
            )
        ]
        cache = {
            "path": "/media/show.mkv",
            "segment_origin": "local",
            "segments": segs,
        }
        with patch.object(session, "get_parse_cache_snapshot", return_value=cache), patch.object(
            session, "paths_refer_to_same_video", return_value=True
        ), patch.object(session, "_get_active_video_player_item", return_value=None):
            loaded = session.get_initial_segments_for_segment_editor("/media/show.mkv")
        self.assertIsNotNone(loaded)
        self.assertEqual(len(loaded), 1)


if __name__ == "__main__":
    unittest.main()
