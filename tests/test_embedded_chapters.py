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


def _big_size(n: int) -> bytes:
    """8-byte EBML size vint (what muxers write for multi-GB Segments)."""
    return b"\x01" + int(n).to_bytes(7, "big")


def _chapters_element():
    intro = _elem(
        b"\xb6",
        _elem(b"\x91", _uint(79 * 10**9, 5))
        + _elem(b"\x92", _uint(170 * 10**9, 5))
        + _elem(b"\x80", _elem(b"\x85", b"Intro")),
    )
    credits = _elem(
        b"\xb6",
        _elem(b"\x91", _uint(2634 * 10**9, 6))
        + _elem(b"\x80", _elem(b"\x85", b"Ending Credits")),
    )
    return _elem(b"\x10\x43\xa7\x70", _elem(b"\x45\xb9", intro + credits))


_EBML_HEADER = _elem(b"\x1a\x45\xdf\xa3", _elem(b"\x42\x86", b"\x01"))
_HUGE_SEGMENT_SIZE = 2_904_795_982


def _seekhead(chapters_rel: int) -> bytes:
    seek = _elem(
        b"\x4d\xbb",
        _elem(b"\x53\xab", b"\x10\x43\xa7\x70")
        + _elem(b"\x53\xac", _uint(chapters_rel, 4)),
    )
    return _elem(b"\x11\x4d\x9b\x74", seek)


class LargeSegmentTests(unittest.TestCase):
    """Segment declares far more bytes than the header read holds (large file)."""

    def test_chapters_inside_buffer_with_huge_declared_segment(self):
        chapters = _chapters_element()
        body = _seekhead(0) + chapters
        # Cluster header declares a size that is not in the buffer either.
        cluster = b"\x1f\x43\xb6\x75" + _big_size(500_000_000) + b"\x00" * 16
        buf = _EBML_HEADER + b"\x18\x53\x80\x67" + _big_size(_HUGE_SEGMENT_SIZE) + body + cluster
        rows = parse_matroska_chapters_from_bytes(buf)
        self.assertEqual(
            [(r["name"], r["start"], r["end"]) for r in rows],
            [("Intro", 79.0, 170.0), ("Ending Credits", 2634.0, None)],
        )

    def test_chapters_beyond_first_read_found_via_seekhead(self):
        from mkv_chapter_parse import parse_matroska_chapters_via_vfs

        chapters = _chapters_element()
        padding = _elem(b"\xec", b"\x00" * 400)  # Void, pushes Chapters past the first read
        seekhead_len = len(_seekhead(0))
        chapters_rel = seekhead_len + len(padding)
        segment_body = _seekhead(chapters_rel) + padding + chapters
        data = _EBML_HEADER + b"\x18\x53\x80\x67" + _big_size(_HUGE_SEGMENT_SIZE) + segment_body

        class FakeFile:
            def __init__(self, _path):
                self.pos = 0

            def readBytes(self, n):
                chunk = data[self.pos : self.pos + n]
                self.pos += len(chunk)
                return bytearray(chunk)

            def seek(self, offset, _whence=0):
                self.pos = offset

            def close(self):
                pass

        first_read = len(_EBML_HEADER) + 12 + len(_seekhead(0)) + 100
        self.assertLess(first_read, len(data) - len(chapters))
        import xbmcvfs

        with patch.object(xbmcvfs, "File", FakeFile, create=True):
            rows = parse_matroska_chapters_via_vfs("nfs://x/episode.mkv", max_bytes=first_read)
        self.assertEqual([r["name"] for r in rows], ["Intro", "Ending Credits"])


def _atom(name, start_s, *, enabled=None, hidden=False, end_s=None, children=b""):
    body = _elem(b"\x91", _uint(int(start_s * 10**9), 8))
    if end_s is not None:
        body += _elem(b"\x92", _uint(int(end_s * 10**9), 8))
    if hidden:
        body += _elem(b"\x98", b"\x01")
    if enabled is not None:
        body += _elem(b"\x45\x98", b"\x01" if enabled else b"\x00")
    body += _elem(b"\x80", _elem(b"\x85", name.encode()))
    return _elem(b"\xb6", body + children)


def _edition(atoms, *, default=None, hidden=None):
    body = b""
    if default is not None:
        body += _elem(b"\x45\xdb", b"\x01" if default else b"\x00")
    if hidden is not None:
        body += _elem(b"\x45\xbd", b"\x01" if hidden else b"\x00")
    return _elem(b"\x45\xb9", body + b"".join(atoms))


def _mkv(chapters_payload):
    return (
        _EBML_HEADER
        + _elem(b"\x18\x53\x80\x67", _elem(b"\x10\x43\xa7\x70", chapters_payload))
    )


class EditionAndEnabledTests(unittest.TestCase):
    def test_default_edition_wins_over_first(self):
        first = _edition([_atom("Director Intro", 5)], default=False)
        second = _edition([_atom("Intro", 0), _atom("Credits", 90)], default=True)
        rows = parse_matroska_chapters_from_bytes(_mkv(first + second))
        self.assertEqual([r["name"] for r in rows], ["Intro", "Credits"])

    def test_hidden_edition_is_ignored(self):
        hidden = _edition([_atom("Secret", 1)], default=True, hidden=True)
        visible = _edition([_atom("Intro", 0)], default=False)
        rows = parse_matroska_chapters_from_bytes(_mkv(hidden + visible))
        self.assertEqual([r["name"] for r in rows], ["Intro"])

    def test_first_edition_used_when_none_default(self):
        one = _edition([_atom("A", 0)])
        two = _edition([_atom("B", 0)])
        rows = parse_matroska_chapters_from_bytes(_mkv(one + two))
        self.assertEqual([r["name"] for r in rows], ["A"])

    def test_disabled_chapter_is_skipped(self):
        edition = _edition([_atom("Intro", 0), _atom("Gone", 30, enabled=False), _atom("Credits", 90)])
        rows = parse_matroska_chapters_from_bytes(_mkv(edition))
        self.assertEqual([r["name"] for r in rows], ["Intro", "Credits"])

    def test_disabled_parent_drops_children(self):
        child = _atom("Child", 10)
        edition = _edition([_atom("Parent", 0, enabled=False, children=child), _atom("Credits", 90)])
        rows = parse_matroska_chapters_from_bytes(_mkv(edition))
        self.assertEqual([r["name"] for r in rows], ["Credits"])


def _seek_entry(target_id: bytes, rel: int) -> bytes:
    return _elem(
        b"\x4d\xbb", _elem(b"\x53\xab", target_id) + _elem(b"\x53\xac", _uint(rel, 4))
    )


_SEEKHEAD_ID = b"\x11\x4d\x9b\x74"
_CHAPTERS_ID = b"\x10\x43\xa7\x70"


class SeekHeadTests(unittest.TestCase):
    def test_second_seekhead_without_chapters_does_not_hide_first(self):
        first = _elem(_SEEKHEAD_ID, _seek_entry(_CHAPTERS_ID, 0))
        second = _elem(_SEEKHEAD_ID, _seek_entry(b"\x16\x54\xae\x6b", 999))
        # first SeekHead says Chapters at rel (after both heads + chapters placed later)
        rel = len(first) + len(second)
        first = _elem(_SEEKHEAD_ID, _seek_entry(_CHAPTERS_ID, rel))
        from mkv_chapter_parse import _chapters_seek_location

        buf = _EBML_HEADER + b"\x18\x53\x80\x67" + _big_size(10**9) + first + second
        found, _start = _chapters_seek_location(buf)
        self.assertEqual(found, rel)

    def test_chain_of_seekheads_is_followed(self):
        from mkv_chapter_parse import parse_matroska_chapters_via_vfs

        chapters = _chapters_element()
        padding = _elem(b"\xec", b"\x00" * 400)
        head2_len = len(_elem(_SEEKHEAD_ID, _seek_entry(_CHAPTERS_ID, 0)))
        head1_len = len(_elem(_SEEKHEAD_ID, _seek_entry(_SEEKHEAD_ID, 0)))
        head2_rel = head1_len + len(padding)
        chapters_rel = head2_rel + head2_len
        head1 = _elem(_SEEKHEAD_ID, _seek_entry(_SEEKHEAD_ID, head2_rel))
        head2 = _elem(_SEEKHEAD_ID, _seek_entry(_CHAPTERS_ID, chapters_rel))
        data = (
            _EBML_HEADER + b"\x18\x53\x80\x67" + _big_size(_HUGE_SEGMENT_SIZE)
            + head1 + padding + head2 + chapters
        )

        class FakeFile:
            def __init__(self, _path):
                self.pos = 0

            def readBytes(self, n):
                chunk = data[self.pos : self.pos + n]
                self.pos += len(chunk)
                return bytearray(chunk)

            def seek(self, offset, _whence=0):
                self.pos = offset

            def close(self):
                pass

        import xbmcvfs

        first_read = len(_EBML_HEADER) + 12 + head1_len + 50
        with patch("mkv_chapter_parse._FIRST_READ_BYTES", first_read):
            with patch.object(xbmcvfs, "File", FakeFile, create=True):
                rows = parse_matroska_chapters_via_vfs("smb://x/episode.mkv")
        self.assertEqual([r["name"] for r in rows], ["Intro", "Ending Credits"])

    def test_extension_ignores_query_and_headers(self):
        from mkv_chapter_parse import _path_extension

        self.assertEqual(_path_extension("http://h/a/b.MKV?token=1|User-Agent=x"), "mkv")
        self.assertEqual(_path_extension("smb://h/a.mp4"), "mp4")


class EmbeddedChaptersJsonRpcTests(unittest.TestCase):
    def setUp(self):
        self.addon = install_kodi_stubs()
        self.addon.getSetting = lambda key: (
            "intro,credits,recap"
            if key == "custom_segment_keywords"
            else "false"
        )
        from segment_types import seeded_builtin_types, set_catalog_for_tests

        set_catalog_for_tests(seeded_builtin_types())

    def tearDown(self):
        from segment_types import set_catalog_for_tests

        set_catalog_for_tests(None)

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
        ) as vfs, patch(
            "service_embedded_chapters.parse_embedded_chapters_via_mkvextract",
            return_value=None,
        ):
            segs = parse_embedded_chapters(player, player_id=1, video_path="nfs://x.mkv")
        vfs.assert_not_called()
        self.assertEqual(
            [
                (s.segment_type_label, s.start_seconds, s.end_seconds, s.source)
                for s in segs
            ],
            [
                ("intro", 0.0, 67.0, "embedded"),
                ("main", 67.0, 8500.0, "embedded"),
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

    def test_get_chapters_empty_falls_back_to_vfs(self):
        player = MagicMock()
        player.getTotalTime.return_value = 100.0
        rows = [{"name": "Intro", "start": 0.0, "end": 67.0}]

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
            "service_embedded_chapters.parse_matroska_chapters_via_vfs",
            return_value=rows,
        ) as vfs, patch(
            "service_embedded_chapters.parse_embedded_chapters_via_mkvextract",
            return_value=None,
        ) as extract:
            segs = parse_embedded_chapters(player, player_id=1, video_path="nfs://x.mkv")
        vfs.assert_called_once()
        extract.assert_not_called()
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0].segment_type_label, "intro")

    def _segments_for(self, rows, total):
        from service_embedded_chapters import _segments_from_rows

        player = MagicMock()
        player.getTotalTime.return_value = total
        return _segments_from_rows(rows, player)

    def test_last_chapter_ends_at_total_time(self):
        segs = self._segments_for(
            [{"name": "Intro", "start": 0.0, "end": None},
             {"name": "Credits", "start": 90.0, "end": None}],
            120.0,
        )
        self.assertEqual(
            [(s.segment_type_label, s.start_seconds, s.end_seconds) for s in segs],
            [("intro", 0.0, 90.0), ("credits", 90.0, 120.0)],
        )

    def test_last_chapter_is_dropped_when_total_time_is_unknown(self):
        for total in (0.0, None):
            segs = self._segments_for(
                [{"name": "Intro", "start": 0.0, "end": None},
                 {"name": "Credits", "start": 90.0, "end": None}],
                total,
            )
            # The first chapter's end is the next chapter's start, so it is known.
            self.assertEqual(
                [(s.segment_type_label, s.start_seconds, s.end_seconds) for s in segs],
                [("intro", 0.0, 90.0)],
            )

    def test_last_chapter_with_its_own_end_is_kept_without_total_time(self):
        segs = self._segments_for(
            [{"name": "Intro", "start": 0.0, "end": 60.0},
             {"name": "Credits", "start": 90.0, "end": 100.0}],
            0.0,
        )
        self.assertEqual(
            [(s.segment_type_label, s.end_seconds) for s in segs],
            [("intro", 60.0), ("credits", 100.0)],
        )

    def test_unknown_embedded_names_are_kept(self):
        player = MagicMock()
        player.getTotalTime.return_value = 100.0

        def rpc(payload):
            data = json.loads(payload)
            if data["method"] == "Player.GetChapters":
                return json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": "EmbeddedChaptersList",
                        "result": {
                            "chapters": [
                                {"index": 1, "name": "Scene 7", "time": 0},
                                {"index": 2, "name": "Opening", "time": 40},
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
            [(s.segment_type_label, s.start_seconds, s.end_seconds) for s in segs],
            [("scene 7", 0.0, 40.0), ("intro", 40.0, 100.0)],
        )


if __name__ == "__main__":
    unittest.main()
