import copy
import os
import re
import stat
import subprocess
import time
import xml.etree.ElementTree as ET
import xbmcvfs
import unicodedata

from segment_editor_utils import get_addon, log
from settings_utils import get_edl_label_to_action_map, get_edl_type_map

# Matroska-style chapter sidecars next to ``video.mkv`` (also used by ``service`` / Segment Marker).
CHAPTER_XML_SIDECAR_SUFFIXES = (
    "-chapters.xml",
    "_chapters.xml",
    ".chapters.xml",
    "-chapter.xml",
    "_chapter.xml",
    ".chapter.xml",
)
DEFAULT_NEW_CHAPTER_XML_SUFFIX = "-chapters.xml"


def _apply_skippy_file_permissions(path):
    """Apply Default / 644 / 666 from Skippy settings (same as segment marker)."""
    try:
        addon = get_addon()
        perm = (addon.getSetting("segment_editor_file_permissions") or "Default").strip()
    except Exception:
        return
    if perm == "Default" or not perm:
        return
    if path.startswith("nfs://") or path.startswith("smb://") or "://" in path:
        log(f"Skipping chmod for non-local path: {path}")
        return
    try:
        if perm == "644":
            os.chmod(
                path,
                stat.S_IRUSR
                | stat.S_IWUSR
                | stat.S_IRGRP
                | stat.S_IROTH,
            )
        elif perm == "666":
            os.chmod(
                path,
                stat.S_IRUSR
                | stat.S_IWUSR
                | stat.S_IRGRP
                | stat.S_IWGRP
                | stat.S_IROTH
                | stat.S_IWOTH,
            )
        else:
            return
        log(f"Applied permissions {perm} to {path}")
    except Exception as chmod_err:
        log(f"Could not set permissions ({chmod_err}) for {path}")


def remap_nfs_path_for_write(path):
    """Return a list of NFS path variations to try when writing.

    Kodi's NFS client sometimes strips subdirectories from mount paths on
    write; trying a few variants gives us a chance to recover automatically.
    """
    if not path.startswith('nfs://'):
        return [path]

    variations = [path]
    try:
        parts = path.split('/', 4)
        if len(parts) >= 5:
            remapped = f"{parts[0]}//{parts[2]}/{parts[4]}"
            variations.append(remapped)
            log(f"NFS path remap variation: {remapped}")
    except Exception:
        pass

    try:
        parts = path.split('/')
        if len(parts) >= 4:
            filename = parts[-1]
            server_part = '/'.join(parts[:3])
            root_path = f"{server_part}/{filename}"
            if root_path not in variations:
                variations.append(root_path)
                log(f"NFS path remap variation (root): {root_path}")
    except Exception:
        pass

    return variations


def safe_file_write(path, content, is_bytes=False):
    """Safely write a file using Kodi's VFS, falling back through NFS remaps.

    Returns ``(success, bytes_written_or_None)``.
    """
    if not is_bytes and isinstance(content, str):
        content_bytes = content.encode('utf-8')
    else:
        content_bytes = content

    path_variations = remap_nfs_path_for_write(path)
    last_error = None

    for attempt_path in path_variations:
        try:
            log(f"Attempting to write to: {attempt_path}")

            # Kodi VFS may not truncate on overwrite (NFS, SMB, some local backends);
            # delete first so a shorter file does not leave stale bytes at EOF.
            if xbmcvfs.exists(attempt_path):
                try:
                    log(f"Deleting existing file before write: {attempt_path}")
                    xbmcvfs.delete(attempt_path)
                    time.sleep(0.05)
                except Exception as del_err:
                    log(f"Could not delete existing file before write: {del_err}")

            f = xbmcvfs.File(attempt_path, 'w')
            if not f:
                log(f"Failed to create file object for: {attempt_path}")
                last_error = "Failed to create file object"
                continue

            result = f.write(content_bytes)
            f.close()

            # Kodi VFS may return bytes-written, True, None or False. Always
            # verify with xbmcvfs.exists() as a fallback check.
            if result or xbmcvfs.exists(attempt_path):
                if xbmcvfs.exists(attempt_path):
                    _apply_skippy_file_permissions(attempt_path)
                    if attempt_path != path:
                        log(f"Write succeeded with remapped path: {attempt_path} (original: {path})")
                    else:
                        log(f"Write succeeded: {path}")
                    written = result if isinstance(result, int) else len(content_bytes)
                    return True, written
                log(f"Write returned {result!r} but file doesn't exist: {attempt_path}")
                if attempt_path.startswith('nfs://') and attempt_path != path_variations[-1]:
                    log("NFS write apparently failed, trying next path variation")
                    continue

        except Exception as e:
            last_error = e
            error_msg = str(e)
            log(f"Write exception for {attempt_path}: {error_msg}")
            if ("NFS" in error_msg or "ACCESS denied" in error_msg or "NFS3ERR" in error_msg):
                if attempt_path != path_variations[-1]:
                    log("NFS error detected, trying next path variation")
                    continue
            if attempt_path == path_variations[-1]:
                break

    if last_error:
        log(f"All write attempts failed. Last error: {last_error}")
    else:
        log("All write attempts failed. Write() returned no bytes for all paths.")
        if path.startswith('nfs://'):
            log("NFS write issue detected. Check: (1) server 'rw' export, "
                "(2) 'insecure' flag, (3) path normalization in Kodi NFS client.")
    return False, None


def normalize_label(text):
    """Normalize and lowercase labels for consistent matching."""
    return unicodedata.normalize("NFKC", text or "").strip().lower()


_NUMERIC_TIME_RE = re.compile(r"^\d+(?:\.\d+)?$")


def hms_to_seconds(hms):
    """Convert HH:MM:SS.mmm, MM:SS, or plain seconds to a non-negative float.

    Raises ValueError on negative, empty, or otherwise malformed input.
    """
    if hms is None:
        raise ValueError("Time input is empty")

    text = str(hms).strip()
    if not text:
        raise ValueError("Time input is empty")
    if text.startswith("-"):
        raise ValueError(f"Time cannot be negative: {hms!r}")
    if text.startswith("+"):
        text = text[1:].strip()
        if not text:
            raise ValueError("Time input is empty")

    parts = text.split(":")
    if len(parts) > 3:
        raise ValueError(f"Invalid time format: {hms!r}")

    # Each part except possibly the last must be a plain integer, and the last
    # component may be a decimal number.
    for segment in parts[:-1]:
        if not segment or not segment.isdigit():
            raise ValueError(f"Invalid time component {segment!r} in {hms!r}")
    last = parts[-1]
    if not _NUMERIC_TIME_RE.match(last):
        raise ValueError(f"Invalid seconds component {last!r} in {hms!r}")

    if len(parts) == 3:
        h, m, s = parts
        total = int(h) * 3600 + int(m) * 60 + float(s)
    elif len(parts) == 2:
        m, s = parts
        total = int(m) * 60 + float(s)
    else:
        total = float(parts[0])

    if total < 0:
        raise ValueError(f"Time cannot be negative: {hms!r}")
    return total


def seconds_to_hms(seconds):
    """Convert seconds to HH:MM:SS.mmm format."""
    if seconds < 0:
        seconds = 0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def indent_xml(elem, level=0, indent="  "):
    """Manually indent an ElementTree (Python 3.8 compatible)."""
    i = "\n" + level * indent
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + indent
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for child in elem:
            indent_xml(child, level + 1, indent)
        if not child.tail or not child.tail.strip():
            child.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


class SegmentItem:
    def __init__(self, start_seconds, end_seconds, label="segment", source="edl", action_type=None):
        start_seconds = float(start_seconds)
        end_seconds = float(end_seconds)

        if start_seconds < 0 or end_seconds < 0:
            raise ValueError(
                f"Segment times must be non-negative (got start={start_seconds}, end={end_seconds})"
            )
        if end_seconds <= start_seconds:
            raise ValueError(
                f"Segment end time ({end_seconds}) must be strictly after start time ({start_seconds})"
            )

        self.start_seconds = start_seconds
        self.end_seconds = end_seconds
        self.source = source
        self.segment_type_label = normalize_label(label)
        self.action_type = action_type
        self.raw_label = label

    def is_active(self, current_time):
        return self.start_seconds <= current_time <= self.end_seconds

    def get_duration(self):
        return self.end_seconds - self.start_seconds

    def __str__(self):
        return f"{self.raw_label} [{self.start_seconds:.2f}-{self.end_seconds:.2f}]"


def safe_file_read(*paths):
    """Read the first readable path. Returns content or None."""
    for path in paths:
        if path:
            log(f"Attempting to read: {path}")
            try:
                f = xbmcvfs.File(path)
                content = f.read()
                f.close()
                if isinstance(content, bytes):
                    content = content.decode('utf-8', errors='replace')
                if content:
                    log(f"Successfully read file: {path}")
                    return content
            except Exception as e:
                log(f"Failed to read {path}: {e}")
    return None


def _segments_from_chapter_xml(xml_data, source_label):
    """Parse Matroska-style chapter XML into SegmentItems; empty list if none."""
    try:
        root = ET.fromstring(xml_data)
    except Exception as e:
        log(f"XML parse failed ({source_label}): {e}")
        return []

    result = []
    for atom in root.findall(".//ChapterAtom"):
        raw_label = atom.findtext(".//ChapterDisplay/ChapterString", default="")
        label = raw_label.strip() if raw_label else "segment"
        start = atom.findtext("ChapterTimeStart")
        end = atom.findtext("ChapterTimeEnd")
        if start and end:
            try:
                result.append(SegmentItem(
                    hms_to_seconds(start),
                    hms_to_seconds(end),
                    label,
                    source="xml"
                ))
                log(f"Parsed XML segment: {start} -> {end} | label='{label}' ({source_label})")
            except ValueError as ve:
                log(f"Skipping invalid chapter atom ({source_label}): {ve}")
    return result


def parse_chapters(video_path):
    """Parse chapter XML file and return list of SegmentItem objects.

    Tries each known sidecar path in order. If the first file with content
    yields no ChapterAtom segments (placeholder or different schema), later
    paths are still tried so XML is preferred over falling back to EDL.
    """
    base = os.path.splitext(video_path)[0]
    video_dir = os.path.dirname(video_path)
    suffixes = list(CHAPTER_XML_SIDECAR_SUFFIXES)

    paths_to_try = [f"{base}{s}" for s in suffixes]
    if video_dir:
        paths_to_try.append(os.path.join(video_dir, "chapters.xml"))

    log(f"Attempting chapter XML paths: {paths_to_try}")

    for path in paths_to_try:
        if not path:
            continue
        try:
            f = xbmcvfs.File(path)
            data = f.read()
            f.close()
            if isinstance(data, bytes):
                data = data.decode("utf-8", errors="replace")
        except Exception as e:
            log(f"Failed to read {path}: {e}")
            continue

        if not data or not data.strip():
            continue
        log(f"Successfully read file: {path}")

        segments = _segments_from_chapter_xml(data, path)
        if segments:
            segments = dedupe_overlapping_same_label_segments(segments)
            log(f"Total segments parsed from XML: {len(segments)} (using {path})")
            return segments
        log(f"No usable ChapterAtom entries in {path}, trying next chapter path if any")

    log("No chapter XML with segments found")
    return None


def parse_edl(video_path):
    """Parse .edl file and return list of SegmentItem objects."""
    base = video_path.rsplit('.', 1)[0]
    paths_to_try = [f"{base}.edl"]

    log(f"Attempting EDL paths: {paths_to_try}")
    edl_data = safe_file_read(*paths_to_try)
    if not edl_data:
        log("No EDL file found")
        return []

    log(f"Raw EDL content:\n{edl_data}")

    segments = []
    try:
        for line in edl_data.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            parts = line.split()
            if len(parts) >= 2:
                try:
                    s = float(parts[0])
                    e = float(parts[1])
                    action = int(parts[2]) if len(parts) > 2 else 4
                    try:
                        type_map = get_edl_type_map()
                        label = type_map.get(action) or "segment"
                    except Exception:
                        label = "segment"

                    segments.append(SegmentItem(s, e, label, source="edl", action_type=action))
                    log(f"Parsed EDL line: {s} -> {e} | action={action} | label='{label}'")
                except (ValueError, IndexError) as e:
                    log(f"Skipped invalid EDL line: {line} ({e})")
    except Exception as e:
        log(f"EDL parse failed: {e}")

    log(f"Total segments parsed from EDL: {len(segments)}")
    return segments


def _mkvextract_chapters_xml(video_path, timeout=3):
    """Try to extract embedded Matroska chapters as XML using mkvextract.

    Returns the XML string if successful, otherwise None. Requires
    ``mkvextract`` to be on PATH; silently returns None if the tool is
    missing (which is the common case on Kodi boxes).
    """
    # Only supports local paths; resolve through Kodi's VFS translator.
    try:
        local_path = xbmcvfs.translatePath(video_path)
    except Exception:
        local_path = video_path

    if "://" in local_path:
        # Still a remote URI after translation; mkvextract can't read it.
        return None
    if not os.path.isfile(local_path):
        return None

    try:
        completed = subprocess.run(
            ["mkvextract", local_path, "chapters", "-"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as err:
        log(f"mkvextract not available or failed ({err})")
        return None

    if completed.returncode != 0:
        log(f"mkvextract exit {completed.returncode}: {completed.stderr.decode('utf-8', errors='replace')[:200]}")
        return None

    data = completed.stdout.decode("utf-8", errors="replace").strip()
    if not data or "<Chapters" not in data:
        return None
    return data


def parse_embedded_chapters(video_path, timeout=3):
    """Return a list of SegmentItem from chapters embedded in the video container.

    Supports Matroska/WebM via ``mkvextract`` if available. Returns None if the
    video has no embedded chapters or the tool is unavailable.
    """
    xml_data = _mkvextract_chapters_xml(video_path, timeout=timeout)
    if not xml_data:
        return None

    try:
        root = ET.fromstring(xml_data)
    except Exception as e:
        log(f"Embedded chapter XML parse failed: {e}")
        return None

    raw_chapters = []
    for atom in root.findall(".//ChapterAtom"):
        raw_label = atom.findtext(".//ChapterDisplay/ChapterString", default="")
        label = raw_label.strip() if raw_label else "chapter"
        start = atom.findtext("ChapterTimeStart")
        end = atom.findtext("ChapterTimeEnd")
        if not start:
            continue
        try:
            start_s = hms_to_seconds(start)
        except ValueError:
            continue
        end_s = None
        if end:
            try:
                end_s = hms_to_seconds(end)
            except ValueError:
                # Invalid explicit end: skip the chapter rather than guessing.
                continue
        raw_chapters.append({
            "start": start_s,
            "end": end_s,
            "label": label,
            "missing_end": end_s is None,
        })

    raw_chapters.sort(key=lambda item: item["start"])

    result = []
    for i, item in enumerate(raw_chapters):
        start_s = item["start"]
        end_s = item["end"]
        if item["missing_end"]:
            # Matroska allows chapters without an explicit end. Fill those from
            # the next chapter start; keep explicit one-second chapters intact.
            if i + 1 < len(raw_chapters) and raw_chapters[i + 1]["start"] > start_s:
                end_s = raw_chapters[i + 1]["start"]
            else:
                end_s = start_s + 1
        try:
            result.append(SegmentItem(start_s, end_s, item["label"], source="xml"))
        except ValueError:
            log(f"Skipping invalid embedded chapter at {start_s}: end={end_s}")
            continue

    if not result:
        return None
    result = dedupe_overlapping_same_label_segments(result)
    return result


def segments_chronological(segments):
    """Return segments sorted by start time, then end time (stable sidecar/UI order)."""
    if not segments:
        return segments
    return sorted(segments, key=lambda s: (s.start_seconds, s.end_seconds))


def _intervals_overlap_or_touch(s1, e1, s2, e2, tolerance=1.5):
    """True when [s1,e1] and [s2,e2] overlap or are within ``tolerance`` seconds of touching."""
    return not (e1 + tolerance <= s2 or e2 + tolerance <= s1)


def dedupe_overlapping_same_label_segments(segments, tolerance=1.5):
    """Merge consecutive same-label windows that overlap or touch (common bad chapter XML).

    Operates on objects with ``start_seconds``, ``end_seconds``, and
    ``segment_type_label``. Uses :func:`copy.copy` on the first segment of each
    merged pair so constructors / logging are not re-run.
    """
    if not segments:
        return []
    if len(segments) == 1:
        return list(segments)

    sorted_segs = sorted(
        segments,
        key=lambda s: (float(s.start_seconds), float(s.end_seconds)),
    )
    out = []
    for seg in sorted_segs:
        raw_lab = getattr(seg, "segment_type_label", None)
        lab_key = normalize_label(raw_lab) if raw_lab is not None else ""
        if not lab_key:
            out.append(seg)
            continue
        if out:
            prev = out[-1]
            prev_raw = getattr(prev, "segment_type_label", None)
            prev_key = (
                normalize_label(prev_raw) if prev_raw is not None else ""
            )
            if prev_key == lab_key:
                ps = float(prev.start_seconds)
                pe = float(prev.end_seconds)
                ss = float(seg.start_seconds)
                se = float(seg.end_seconds)
                if _intervals_overlap_or_touch(ps, pe, ss, se, tolerance):
                    merged = copy.copy(prev)
                    merged.start_seconds = min(ps, ss)
                    merged.end_seconds = max(pe, se)
                    if hasattr(merged, "next_segment_start"):
                        merged.next_segment_start = None
                    if hasattr(merged, "next_segment_info"):
                        merged.next_segment_info = None
                    out[-1] = merged
                    continue
        out.append(seg)

    if len(out) < len(segments):
        log(
            "Deduped overlapping same-label segments: %d -> %d"
            % (len(segments), len(out))
        )
    return out


def save_chapters(video_path, segments):
    """Save segments to chapter.xml file."""
    if '.' in video_path:
        base = video_path.rsplit('.', 1)[0]
    else:
        base = video_path

    output_path = None
    for suffix in CHAPTER_XML_SIDECAR_SUFFIXES:
        path = f"{base}{suffix}"
        if xbmcvfs.exists(path):
            output_path = path
            break
    if not output_path:
        output_path = f"{base}{DEFAULT_NEW_CHAPTER_XML_SUFFIX}"

    log(f"Saving {len(segments)} segments to: {output_path}")

    try:
        action_mapping = get_edl_type_map()
    except Exception:
        action_mapping = {}

    root = ET.Element("Chapters")
    edition = ET.SubElement(root, "EditionEntry")

    for seg in segments:
        atom = ET.SubElement(edition, "ChapterAtom")
        ET.SubElement(atom, "ChapterTimeStart").text = seconds_to_hms(seg.start_seconds)
        ET.SubElement(atom, "ChapterTimeEnd").text = seconds_to_hms(seg.end_seconds)

        display = ET.SubElement(atom, "ChapterDisplay")
        if seg.action_type is not None and seg.action_type in action_mapping:
            label = action_mapping[seg.action_type]
        else:
            label = seg.raw_label if hasattr(seg, 'raw_label') else seg.segment_type_label
        ET.SubElement(display, "ChapterString").text = label

    try:
        try:
            dir_path = '/'.join(output_path.split('/')[:-1])
            if dir_path and not xbmcvfs.exists(dir_path):
                log(f"Creating directory: {dir_path}")
                xbmcvfs.mkdirs(dir_path)
        except Exception as dir_err:
            log(f"Could not ensure directory exists: {dir_err}")

        indent_xml(root, indent="  ")
        xml_str = ET.tostring(root, encoding='unicode')
        xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str

        log(f"Writing XML content to: {output_path} ({len(xml_str)} bytes)")
        success, bytes_written = safe_file_write(output_path, xml_str, is_bytes=False)

        if success:
            log(f"Successfully saved chapter XML to: {output_path} ({bytes_written} bytes)")
            return True
        log(f"Failed to write chapter XML to: {output_path}")
        return False
    except Exception as e:
        log(f"Failed to save chapter XML: {e}")
        import traceback
        log(f"Traceback: {traceback.format_exc()}")
        return False


def save_edl(video_path, segments):
    """Save segments to .edl file."""
    if '.' in video_path:
        base = video_path.rsplit('.', 1)[0]
    else:
        base = video_path
    output_path = f"{base}.edl"

    if xbmcvfs.exists(output_path):
        log(f"Existing EDL file found, using its path format: {output_path}")
    else:
        log(f"EDL file does not exist, will create: {output_path}")

    log(f"Saving {len(segments)} segments to: {output_path}")

    try:
        label_to_action = get_edl_label_to_action_map()
    except Exception:
        label_to_action = {}

    try:
        lines = []
        for seg in segments:
            seg_label = seg.segment_type_label
            if seg_label in label_to_action:
                action = label_to_action[seg_label]
            elif seg.action_type is not None:
                try:
                    action = int(seg.action_type)
                except (TypeError, ValueError):
                    action = 4
            else:
                action = 4
            lines.append(f"{seg.start_seconds:.3f}\t{seg.end_seconds:.3f}\t{action}")

        content = "\n".join(lines) + "\n"

        try:
            dir_path = '/'.join(output_path.split('/')[:-1])
            if dir_path and not xbmcvfs.exists(dir_path):
                log(f"Creating directory: {dir_path}")
                xbmcvfs.mkdirs(dir_path)
        except Exception as dir_err:
            log(f"Could not ensure directory exists: {dir_err}")

        log(f"Writing EDL content to: {output_path} ({len(content)} bytes)")
        success, bytes_written = safe_file_write(output_path, content, is_bytes=False)

        if success:
            log(f"Successfully saved EDL to: {output_path} ({bytes_written} bytes)")
            return True
        log(f"Failed to write EDL to: {output_path}")
        return False
    except Exception as e:
        log(f"Failed to save EDL: {e}")
        import traceback
        log(f"Traceback: {traceback.format_exc()}")
        return False


# ---------------------------------------------------------------------------
# Save-format dispatcher
# ---------------------------------------------------------------------------

SAVE_FORMAT_EDL = "edl"
SAVE_FORMAT_XML = "xml"
SAVE_FORMAT_BOTH = "both"

_SAVE_FORMAT_ALIASES = {
    "auto detect": SAVE_FORMAT_BOTH,
    "auto": SAVE_FORMAT_BOTH,
    "edl only": SAVE_FORMAT_EDL,
    "edl": SAVE_FORMAT_EDL,
    "chapter xml only": SAVE_FORMAT_XML,
    "xml": SAVE_FORMAT_XML,
    "both formats": SAVE_FORMAT_BOTH,
    "both": SAVE_FORMAT_BOTH,
}


def normalize_save_format(raw):
    """Map settings / legacy labels to an internal format key."""
    if not raw:
        return SAVE_FORMAT_BOTH
    key = str(raw).strip().lower()
    if key in _SAVE_FORMAT_ALIASES:
        return _SAVE_FORMAT_ALIASES[key]
    return SAVE_FORMAT_BOTH


def get_save_format():
    try:
        raw = get_addon().getSetting("segment_editor_save_format") or "Both"
    except Exception:
        raw = "Both"
    return normalize_save_format(raw)


def _backup_file(path, enabled):
    if not enabled or not path or not xbmcvfs.exists(path):
        return
    backup_path = f"{path}.bck"
    try:
        if xbmcvfs.exists(backup_path):
            xbmcvfs.delete(backup_path)
        if xbmcvfs.copy(path, backup_path):
            log(f"Backed up existing file: {backup_path}")
    except Exception as err:
        log(f"Could not back up {path}: {err}")


def _backup_editor_sidecars(video_path, save_format, enabled):
    if not enabled:
        return
    base = os.path.splitext(video_path)[0]
    if save_format in (SAVE_FORMAT_BOTH, SAVE_FORMAT_EDL):
        _backup_file(f"{base}.edl", True)
    if save_format in (SAVE_FORMAT_BOTH, SAVE_FORMAT_XML):
        for suffix in CHAPTER_XML_SIDECAR_SUFFIXES:
            _backup_file(f"{base}{suffix}", True)


def save_segments(video_path, segments, save_format=None):
    """Persist ``segments`` for ``video_path`` according to ``save_format``.

    Returns a tuple ``(edl_success, xml_success)``. Either may be False even
    when the overall write succeeded (for example in "edl" mode ``xml_success``
    will always be False). The caller is expected to decide what to show the
    user based on the returned flags.
    """
    if save_format is None:
        save_format = get_save_format()
    else:
        save_format = normalize_save_format(save_format)

    try:
        backup_on = get_addon().getSetting("segment_editor_backup_before_write") == "true"
    except Exception:
        backup_on = True
    _backup_editor_sidecars(video_path, save_format, backup_on)

    segments = segments_chronological(segments)
    segments = dedupe_overlapping_same_label_segments(segments)

    edl_success = False
    xml_success = False

    if save_format == SAVE_FORMAT_BOTH:
        edl_success = save_edl(video_path, segments)
        xml_success = save_chapters(video_path, segments)
    elif save_format == SAVE_FORMAT_XML:
        xml_success = save_chapters(video_path, segments)
    elif save_format == SAVE_FORMAT_EDL:
        edl_success = save_edl(video_path, segments)

    return edl_success, xml_success


def delete_segment_files(video_path, save_format=None):
    """Remove any segment files Kodi would otherwise re-use for this video."""
    if save_format is None:
        save_format = get_save_format()
    else:
        save_format = normalize_save_format(save_format)

    base = os.path.splitext(video_path)[0]
    all_xml = [f"{base}{s}" for s in CHAPTER_XML_SIDECAR_SUFFIXES]
    all_edl = [f"{base}.edl"]

    if save_format == SAVE_FORMAT_BOTH:
        candidates = all_xml + all_edl
    elif save_format == SAVE_FORMAT_XML:
        candidates = all_xml
    elif save_format == SAVE_FORMAT_EDL:
        candidates = all_edl
    else:
        candidates = all_xml + all_edl

    deleted = []
    for path in candidates:
        if xbmcvfs.exists(path):
            try:
                xbmcvfs.delete(path)
                deleted.append(path)
                log(f"Deleted empty segment file: {path}")
            except Exception as err:
                log(f"Failed to delete {path}: {err}")
    return deleted
