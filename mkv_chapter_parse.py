# -*- coding: utf-8 -*-
"""Read Matroska/WebM embedded chapters from bytes or Kodi VFS (NFS-safe header scan)."""

from __future__ import annotations

from typing import Optional

# EBML element IDs (descriptor bits included).
_ID_EBML = 0x1A45DFA3
_ID_SEGMENT = 0x18538067
_ID_SEEKHEAD = 0x114D9B74
_ID_SEEK = 0x4DBB
_ID_SEEK_ID = 0x53AB
_ID_SEEK_POSITION = 0x53AC
_ID_CHAPTERS = 0x1043A770
_ID_CLUSTER = 0x1F43B675
_ID_EDITION = 0x45B9
_ID_ATOM = 0xB6
_ID_TIME_START = 0x91
_ID_TIME_END = 0x92
_ID_DISPLAY = 0x80
_ID_STRING = 0x85
_ID_FLAG_HIDDEN = 0x98

_UNKNOWN_SIZE = object()
_MAX_HEADER_BYTES = 8 * 1024 * 1024
_MAX_CHAPTERS_BYTES = 512 * 1024


def _vint_len(first: int) -> int:
    if first == 0:
        return 0
    length = 1
    mask = 0x80
    while length <= 8 and (first & mask) == 0:
        length += 1
        mask >>= 1
    return length if length <= 8 else 0


def _read_vint(buf: bytes, offset: int, keep_descriptor: bool):
    if offset >= len(buf):
        return None, offset
    length = _vint_len(buf[offset])
    if length < 1 or offset + length > len(buf):
        return None, offset
    raw = buf[offset : offset + length]
    value = int.from_bytes(raw, "big")
    if not keep_descriptor:
        length_bit = 0x80 >> (length - 1)
        data_bits = length_bit - 1
        unknown = ((raw[0] & data_bits) == data_bits) and all(
            b == 0xFF for b in raw[1:]
        )
        if unknown:
            return _UNKNOWN_SIZE, offset + length
        value &= (1 << (7 * length)) - 1
    return value, offset + length


def _read_element(buf: bytes, offset: int):
    elem_id, mid = _read_vint(buf, offset, True)
    if elem_id is None:
        return None, None, None, offset
    size, end = _read_vint(buf, mid, False)
    if size is None:
        return None, None, None, offset
    if size is _UNKNOWN_SIZE:
        return elem_id, None, None, end
    payload_end = end + int(size)
    if payload_end > len(buf):
        return None, None, None, offset
    return elem_id, int(size), buf[end:payload_end], payload_end


def _uint_from_bytes(payload: bytes) -> int:
    if not payload:
        return 0
    return int.from_bytes(payload, "big")


def _ns_to_seconds(ns: int) -> float:
    return float(ns) / 1e9


def _walk_atoms(payload: bytes, out: list) -> None:
    offset = 0
    while offset < len(payload):
        elem_id, _size, data, nxt = _read_element(payload, offset)
        if elem_id is None or data is None:
            break
        offset = nxt
        if elem_id == _ID_ATOM:
            _parse_atom(data, out)
        elif elem_id == _ID_EDITION:
            _walk_atoms(data, out)


def _parse_atom(payload: bytes, out: list) -> None:
    start_ns = None
    end_ns = None
    label = ""
    hidden = False
    offset = 0
    while offset < len(payload):
        elem_id, _size, data, nxt = _read_element(payload, offset)
        if elem_id is None or data is None:
            break
        offset = nxt
        if elem_id == _ID_TIME_START:
            start_ns = _uint_from_bytes(data)
        elif elem_id == _ID_TIME_END:
            end_ns = _uint_from_bytes(data)
        elif elem_id == _ID_FLAG_HIDDEN:
            hidden = _uint_from_bytes(data) == 1
        elif elem_id == _ID_DISPLAY:
            d_off = 0
            while d_off < len(data):
                did, _ds, dpay, dnxt = _read_element(data, d_off)
                if did is None or dpay is None:
                    break
                d_off = dnxt
                if did == _ID_STRING and not label:
                    try:
                        label = dpay.decode("utf-8", errors="replace").strip()
                    except Exception:
                        label = ""
        elif elem_id == _ID_ATOM:
            _parse_atom(data, out)
    if hidden or start_ns is None:
        return
    out.append(
        {
            "name": label or "chapter",
            "start": _ns_to_seconds(start_ns),
            "end": _ns_to_seconds(end_ns) if end_ns is not None else None,
        }
    )


def _parse_chapters_payload(payload: bytes) -> list:
    rows = []
    _walk_atoms(payload, rows)
    rows.sort(key=lambda item: item["start"])
    return rows


def _seekhead_chapter_offset(payload: bytes) -> Optional[int]:
    """Return Segment-relative offset of Chapters from SeekHead, if listed."""
    offset = 0
    while offset < len(payload):
        elem_id, _size, data, nxt = _read_element(payload, offset)
        if elem_id is None or data is None:
            break
        offset = nxt
        if elem_id != _ID_SEEK:
            continue
        seek_id = None
        seek_pos = None
        s_off = 0
        while s_off < len(data):
            sid, _ss, spay, snxt = _read_element(data, s_off)
            if sid is None or spay is None:
                break
            s_off = snxt
            if sid == _ID_SEEK_ID:
                seek_id = int.from_bytes(spay, "big") if spay else None
            elif sid == _ID_SEEK_POSITION:
                seek_pos = _uint_from_bytes(spay)
        if seek_id == _ID_CHAPTERS and seek_pos is not None:
            return int(seek_pos)
    return None


def parse_matroska_chapters_from_bytes(buf: bytes) -> list:
    """Return chapter dicts ``{name, start, end}`` from a Matroska header buffer."""
    if not buf:
        return []
    offset = 0
    segment_data_start = None
    while offset < len(buf):
        elem_id, size, data, nxt = _read_element(buf, offset)
        if elem_id is None:
            break
        if elem_id == _ID_EBML:
            offset = nxt
            continue
        if elem_id == _ID_SEGMENT:
            if data is None:
                segment_data_start = nxt
                data = buf[nxt:]
            else:
                segment_data_start = nxt - len(data)
            return _parse_segment(data, buf, segment_data_start)
        offset = nxt
    # Header-only snippet that starts at Chapters.
    if buf[0:4] == b"\x10\x43\xa7\x70":
        _eid, _sz, payload, _n = _read_element(buf, 0)
        if payload:
            return _parse_chapters_payload(payload)
    return []


def _parse_segment(segment: bytes, whole: bytes, segment_data_start: int) -> list:
    offset = 0
    seek_chapter_rel = None
    while offset < len(segment):
        elem_id, size, data, nxt = _read_element(segment, offset)
        if elem_id is None:
            break
        if elem_id == _ID_CLUSTER:
            break
        if elem_id == _ID_CHAPTERS and data is not None:
            return _parse_chapters_payload(data)
        if elem_id == _ID_SEEKHEAD and data is not None:
            seek_chapter_rel = _seekhead_chapter_offset(data)
        offset = nxt if size is not None else len(segment)
    if seek_chapter_rel is None:
        return []
    abs_off = segment_data_start + seek_chapter_rel
    if abs_off < 0 or abs_off >= len(whole):
        return []
    _eid, _sz, payload, _n = _read_element(whole, abs_off)
    if _eid != _ID_CHAPTERS or payload is None:
        return []
    return _parse_chapters_payload(payload)


def parse_matroska_chapters_via_vfs(video_path: str, max_bytes: int = _MAX_HEADER_BYTES) -> list:
    """Read the start of a Matroska file through xbmcvfs and parse chapter atoms."""
    if not video_path:
        return []
    ext = video_path.rsplit(".", 1)[-1].lower() if "." in video_path else ""
    if ext not in ("mkv", "mka", "mks", "mk3d", "webm"):
        return []
    try:
        import xbmcvfs
    except ImportError:
        return []
    handle = None
    try:
        handle = xbmcvfs.File(video_path)
        chunk = _vfs_read(handle, max_bytes)
        if not chunk:
            return []
        rows = parse_matroska_chapters_from_bytes(chunk)
        if rows:
            return rows
        # SeekHead may point past the first chunk; retry a targeted read.
        seek_rel, seg_start = _chapters_seek_location(chunk)
        if seek_rel is None:
            return []
        abs_off = seg_start + seek_rel
        if hasattr(handle, "seek"):
            handle.seek(abs_off, 0)
            extra = _vfs_read(handle, _MAX_CHAPTERS_BYTES)
            if extra:
                eid, _sz, payload, _n = _read_element(extra, 0)
                if eid == _ID_CHAPTERS and payload is not None:
                    return _parse_chapters_payload(payload)
                return parse_matroska_chapters_from_bytes(extra)
        return []
    except Exception:
        return []
    finally:
        if handle is not None:
            try:
                handle.close()
            except Exception:
                pass


def _chapters_seek_location(buf: bytes):
    offset = 0
    while offset < len(buf):
        elem_id, size, data, nxt = _read_element(buf, offset)
        if elem_id is None:
            return None, 0
        if elem_id == _ID_EBML:
            offset = nxt
            continue
        if elem_id == _ID_SEGMENT:
            seg_start = nxt if data is None else nxt - len(data)
            payload = data if data is not None else buf[nxt:]
            s_off = 0
            while s_off < len(payload):
                sid, _ss, spay, snxt = _read_element(payload, s_off)
                if sid is None:
                    break
                if sid == _ID_SEEKHEAD and spay is not None:
                    rel = _seekhead_chapter_offset(spay)
                    return rel, seg_start
                if sid == _ID_CLUSTER:
                    break
                s_off = snxt
            return None, seg_start
        offset = nxt
    return None, 0


def _vfs_read(handle, nbytes: int) -> bytes:
    data = b""
    if hasattr(handle, "readBytes"):
        try:
            raw = handle.readBytes(nbytes)
            if raw:
                data = bytes(raw)
        except Exception:
            data = b""
    if not data and hasattr(handle, "read"):
        try:
            raw = handle.read(nbytes)
            if isinstance(raw, bytes):
                data = raw
            elif isinstance(raw, bytearray):
                data = bytes(raw)
            elif isinstance(raw, str):
                data = raw.encode("latin-1", errors="replace")
        except Exception:
            data = b""
    return data
