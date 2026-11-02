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
_ID_FLAG_ENABLED = 0x4598
_ID_EDITION_FLAG_HIDDEN = 0x45BD
_ID_EDITION_FLAG_DEFAULT = 0x45DB

_UNKNOWN_SIZE = object()
_MAX_HEADER_BYTES = 8 * 1024 * 1024
# Chapters almost always sit within the first few hundred KB, so read that much first
# and only read further when nothing was found.
_FIRST_READ_BYTES = 256 * 1024
_SEEKHEAD_READ_BYTES = 64 * 1024
_CHAPTERS_READ_BYTES = 64 * 1024
_MAX_CHAPTERS_BYTES = 4 * 1024 * 1024
_MAX_SEEKHEAD_HOPS = 3


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
        if elem_id == _ID_SEGMENT:
            # Only the start of the file is read, so the top-level Segment almost
            # always declares more bytes than the buffer holds. Treat it like an
            # unknown-size Segment (children are parsed from what is available)
            # instead of rejecting the whole file.
            return elem_id, None, None, end
        return None, None, None, offset
    return elem_id, int(size), buf[end:payload_end], payload_end


def _uint_from_bytes(payload: bytes) -> int:
    if not payload:
        return 0
    return int.from_bytes(payload, "big")


def _ns_to_seconds(ns: int) -> float:
    return float(ns) / 1e9


def _parse_atom(payload: bytes, out: list) -> None:
    start_ns = None
    end_ns = None
    label = ""
    hidden = False
    enabled = True
    children: list = []
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
        elif elem_id == _ID_FLAG_ENABLED:
            enabled = _uint_from_bytes(data) != 0
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
            _parse_atom(data, children)
    if hidden or not enabled:
        # A disabled or hidden chapter hides its sub-chapters too.
        return
    out.extend(children)
    if start_ns is None:
        return
    out.append(
        {
            "name": label or "chapter",
            "start": _ns_to_seconds(start_ns),
            "end": _ns_to_seconds(end_ns) if end_ns is not None else None,
        }
    )


def _parse_edition(payload: bytes):
    """Return ``(is_default, is_hidden, rows)`` for one EditionEntry."""
    is_default = False
    is_hidden = False
    rows: list = []
    offset = 0
    while offset < len(payload):
        elem_id, _size, data, nxt = _read_element(payload, offset)
        if elem_id is None or data is None:
            break
        offset = nxt
        if elem_id == _ID_EDITION_FLAG_DEFAULT:
            is_default = _uint_from_bytes(data) == 1
        elif elem_id == _ID_EDITION_FLAG_HIDDEN:
            is_hidden = _uint_from_bytes(data) == 1
        elif elem_id == _ID_ATOM:
            _parse_atom(data, rows)
    return is_default, is_hidden, rows


def _parse_chapters_payload(payload: bytes) -> list:
    """Chapter rows of ONE edition: the default one, else the first visible one.

    Files can carry several editions (e.g. a commentary or alternative cut); merging
    them would duplicate and overlap segments.
    """
    editions = []
    loose: list = []
    offset = 0
    while offset < len(payload):
        elem_id, _size, data, nxt = _read_element(payload, offset)
        if elem_id is None or data is None:
            break
        offset = nxt
        if elem_id == _ID_EDITION:
            editions.append(_parse_edition(data))
        elif elem_id == _ID_ATOM:
            _parse_atom(data, loose)
    if editions:
        visible = [e for e in editions if not e[1]] or editions
        chosen = next((e for e in visible if e[0]), visible[0])
        rows = chosen[2]
    else:
        rows = loose
    rows.sort(key=lambda item: item["start"])
    return rows


def _seekhead_positions(payload: bytes) -> dict:
    """``{element id: Segment-relative position}`` from one SeekHead (first entry wins)."""
    positions: dict = {}
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
        if seek_id is not None and seek_pos is not None and seek_id not in positions:
            positions[seek_id] = int(seek_pos)
    return positions


def _seekhead_chapter_offset(payload: bytes) -> Optional[int]:
    """Return Segment-relative offset of Chapters from SeekHead, if listed."""
    return _seekhead_positions(payload).get(_ID_CHAPTERS)


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
        if elem_id == _ID_SEEKHEAD and data is not None and seek_chapter_rel is None:
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
    ext = _path_extension(video_path)
    if ext not in ("mkv", "mka", "mks", "mk3d", "webm"):
        return []
    try:
        import xbmcvfs
    except ImportError:
        return []
    handle = None
    try:
        handle = xbmcvfs.File(video_path)
        first = max(1, min(_FIRST_READ_BYTES, int(max_bytes)))
        chunk = _vfs_read(handle, first)
        if not chunk:
            return []
        rows = parse_matroska_chapters_from_bytes(chunk)
        if rows:
            return rows
        positions, seg_start = _segment_seek_positions(chunk)
        if seg_start is None:
            return []
        if (
            _ID_CHAPTERS not in positions
            and _ID_SEEKHEAD not in positions
            and len(chunk) >= first
            and max_bytes > first
        ):
            # No SeekHead pointers in the first read: read on (sequentially) and
            # scan the larger header, as before.
            more = _vfs_read(handle, int(max_bytes) - first)
            if more:
                chunk += more
                return parse_matroska_chapters_from_bytes(chunk)
            return []
        if not hasattr(handle, "seek"):
            return []
        rel = positions.get(_ID_CHAPTERS)
        next_head = positions.get(_ID_SEEKHEAD)
        hops = 0
        # A SeekHead may only point at another SeekHead (meta seek); follow it.
        while rel is None and next_head is not None and hops < _MAX_SEEKHEAD_HOPS:
            hops += 1
            head = _read_element_at(handle, seg_start + next_head, _SEEKHEAD_READ_BYTES)
            if head is None or head[0] != _ID_SEEKHEAD:
                return []
            more_positions = _seekhead_positions(head[1])
            rel = more_positions.get(_ID_CHAPTERS)
            following = more_positions.get(_ID_SEEKHEAD)
            next_head = following if following != next_head else None
        if rel is None:
            return []
        found = _read_element_at(
            handle, seg_start + rel, _CHAPTERS_READ_BYTES, _MAX_CHAPTERS_BYTES
        )
        if found is None or found[0] != _ID_CHAPTERS:
            return []
        return _parse_chapters_payload(found[1])
    except Exception:
        return []
    finally:
        if handle is not None:
            try:
                handle.close()
            except Exception:
                pass


def _path_extension(video_path: str) -> str:
    """Lower-case file extension, ignoring ``?query``, ``#fragment`` and ``|headers``."""
    path = str(video_path or "")
    for sep in ("|", "?", "#"):
        path = path.split(sep, 1)[0]
    name = path.rstrip("/").rsplit("/", 1)[-1]
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def _read_element_at(handle, abs_offset: int, first_read: int, max_total: int = 0):
    """Seek to ``abs_offset`` and return ``(element id, payload)``, or None.

    Reads ``first_read`` bytes; when the element is larger (and at most
    ``max_total`` bytes in all), reads the whole element.
    """
    if abs_offset < 0:
        return None
    handle.seek(abs_offset, 0)
    buf = _vfs_read(handle, first_read)
    if not buf:
        return None
    elem_id, mid = _read_vint(buf, 0, True)
    if elem_id is None:
        return None
    size, end = _read_vint(buf, mid, False)
    if size is None or size is _UNKNOWN_SIZE:
        return None
    total = end + int(size)
    if total > len(buf):
        if not max_total or total > max_total:
            return None
        handle.seek(abs_offset, 0)
        buf = _vfs_read(handle, total)
        if len(buf) < total:
            return None
    return elem_id, buf[end:total]


def _segment_seek_positions(buf: bytes):
    """``(positions, segment_data_start)`` from every SeekHead before the first Cluster.

    ``positions`` maps element id to Segment-relative position; ``segment_data_start``
    is None when ``buf`` holds no Segment.
    """
    offset = 0
    while offset < len(buf):
        elem_id, size, data, nxt = _read_element(buf, offset)
        if elem_id is None:
            return {}, None
        if elem_id == _ID_EBML:
            offset = nxt
            continue
        if elem_id == _ID_SEGMENT:
            seg_start = nxt if data is None else nxt - len(data)
            payload = data if data is not None else buf[nxt:]
            positions: dict = {}
            s_off = 0
            while s_off < len(payload):
                sid, _ss, spay, snxt = _read_element(payload, s_off)
                if sid is None or sid == _ID_CLUSTER:
                    break
                if sid == _ID_SEEKHEAD and spay is not None:
                    for key, value in _seekhead_positions(spay).items():
                        positions.setdefault(key, value)
                s_off = snxt
            return positions, seg_start
        offset = nxt
    return {}, None


def _chapters_seek_location(buf: bytes):
    """``(Chapters position relative to the Segment, Segment data start)``."""
    positions, seg_start = _segment_seek_positions(buf)
    return positions.get(_ID_CHAPTERS), (seg_start or 0)


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
