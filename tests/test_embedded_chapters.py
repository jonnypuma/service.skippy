# -*- coding: utf-8 -*-
"""Matroska chapter header parse and embedded-chapter JSON-RPC fallback."""

import json
import unittest
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

from mkv_chapter_parse import parse_matroska_chapters_from_bytes
from service_embedded_chapters import parse_embedded_chapters
from settings_utils import normalize_label


def _vint_size(n):
    if n < 127:
        return bytes([0x80 | n])
    if n < 16383:
        return bytes([0x40 | (n >> 8), n & 0xFF])
    raise AssertionError("test payload too large")


def _elem(eid: bytes, payload: bytes) -> bytes:
    return eid + _vint_size(len(payload)) + payload


def _uint(n: int, width: int) -> bytes:
    return n.to_bytes(width, "big")


def _minimal_mkv_with_chapters():
    """EBML+Segment with Intro at 0s and Credits at 90s."""
    intro_start = _elem(b"\x91", _uint(0, 1))
    intro_name = _elem(b"\x85", b"Intro")
    intro_disp = _elem(b"\x80", intro_name)
    intro = _elem(b"\xb6", intro_start + intro_disp)

    credits_ns = 90 * 10**9
    credits_start = _elem(b"\x91", _uint(credits_ns, 8))
    credits_name = _elem(b"\x85", b"Credits")
    credits_disp = _elem(b"\x80", credits_name)
    credits = _elem(b"\xb6", credits_start + credits_disp)

    edition = _elem(b"\x45\xb9", intro + credits)
    chapters = _elem(b"\x10\x43\xa7\x70", edition)
    # Dummy EBML header + Segment wrapping chapters.
    ebml = _elem(b"\x1a\x45\xdf\xa3", _elem(b"\x42\x86", b"\x01"))
    segment = _elem(b"\x18\x53\x80\x67", chapters)
    return ebml + segment


class MkvChapterParseTests(unittest.TestCase):
    def test_parses_intro_and_credits(self):
        rows = parse_matroska_chapters_from_bytes(_minimal_mkv_with_chapters())
        self.assertEqual(
            [(r["name"], r["start"], r["end"]) for r in rows],
            [("Intro", 0.0, None), ("Credits", 90.0, None)],
        )

    def test_unknown_size_segment(self):
        intro_start = _elem(b"\x91", _uint(0, 1))
        intro_name = _elem(b"\x85", b"Intro")
        intro = _elem(b"\xb6", intro_start + _elem(b"\x80", intro_name))
        edition = _elem(b"\x45\xb9", intro)
        chapters = _elem(b"\x10\x43\xa7\x70", edition)
        ebml = _elem(b"\x1a\x45\xdf\xa3", _elem(b"\x42\x86", b"\x01"))
        segment = b"\x18\x53\x80\x67\xff" + chapters
        rows = parse_matroska_chapters_from_bytes(ebml + segment)
        self.assertEqual(rows[0]["name"], "Intro")


class EmbeddedChaptersJsonRpcTests(unittest.TestCase):
    def setUp(self):
        self.addon = install_kodi_stubs()
        self.addon.getSetting = lambda key: (
            "intro,credits,recap"
            if key == "custom_segment_keywords"
            else "false"
        )

    def test_get_chapters_maps_keyword_matches(self):
        player = MagicMock()
        player.getTotalTime.return_value = 8700.0

        def rpc(payload):
            data = json.loads(payload)
            if data["method"] == "Player.GetChapters":
                return json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": "EmbeddedChaptersList",
                        "result": {
                            "chapters": [
                                {"index": 1, "name": "Intro", "time": 0},
                                {"index": 2, "name": "Main", "time": 67},
                                {"index": 3, "name": "Credits", "time": 8500},
                            ]
                        },
                    }
                )
            self.fail("unexpected method %s" % data["method"])

        with patch("service_embedded_chapters.xbmc.executeJSONRPC", side_effect=rpc), patch(
            "service_embedded_chapters.parse_matroska_chapters_via_vfs", return_value=[]
        ), patch(
            "service_embedded_chapters.parse_embedded_chapters_via_mkvextract",
            return_value=None,
        ):
            segs = parse_embedded_chapters(player, player_id=1, video_path="nfs://x.mkv")
        self.assertEqual(
            [
                (s.segment_type_label, s.start_seconds, s.end_seconds, s.source)
                for s in segs
            ],
            [
                ("intro", 0.0, 67.0, "embedded"),
                ("credits", 8500.0, 8700.0, "embedded"),
            ],
        )

    def test_omega_invalid_getchapters_falls_back_to_vfs(self):
        player = MagicMock()
        player.getTotalTime.return_value = 120.0
        rows = [{"name": "Intro", "start": 0.0, "end": 67.0}]

        def rpc(payload):
            data = json.loads(payload)
            if data["method"] == "Player.GetChapters":
                return json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": "EmbeddedChaptersList",
                        "error": {
                            "code": -32601,
                            "message": "Method not found.",
                        },
                    }
                )
            if data["method"] == "Player.GetProperties":
                self.fail("must not call GetProperties chapters")
            self.fail("unexpected method %s" % data["method"])

        with patch("service_embedded_chapters.xbmc.executeJSONRPC", side_effect=rpc), patch(
            "service_embedded_chapters.parse_matroska_chapters_via_vfs",
            return_value=rows,
        ) as vfs, patch(
            "service_embedded_chapters.parse_embedded_chapters_via_mkvextract",
            return_value=None,
        ):
            segs = parse_embedded_chapters(
                player, player_id=1, video_path="nfs://share/movie.mkv"
            )
        vfs.assert_called_once()
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0].segment_type_label, "intro")
        self.assertEqual(normalize_label("Intro"), "intro")

    def test_get_chapters_empty_does_not_scan_vfs(self):
        player = MagicMock()
        player.getTotalTime.return_value = 100.0

        def rpc(payload):
            data = json.loads(payload)
            if data["method"] == "Player.GetChapters":
                return json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": "EmbeddedChaptersList",
                        "result": {"chapters": []},
                    }
                )
            self.fail("unexpected method %s" % data["method"])

        with patch("service_embedded_chapters.xbmc.executeJSONRPC", side_effect=rpc), patch(
            "service_embedded_chapters.parse_matroska_chapters_via_vfs", return_value=[]
        ) as vfs, patch(
            "service_embedded_chapters.parse_embedded_chapters_via_mkvextract",
            return_value=None,
        ) as extract:
            segs = parse_embedded_chapters(player, player_id=1, video_path="nfs://x.mkv")
        self.assertEqual(segs, [])
        vfs.assert_not_called()
        extract.assert_not_called()


if __name__ == "__main__":
    unittest.main()
