import xbmc
import unicodedata

from settings_utils import get_addon, log_segment, normalize_label


def log(msg):
    log_segment(msg)


def _ascii_log_text(msg):
    return unicodedata.normalize("NFKD", str(msg)).encode("ascii", "ignore").decode("ascii")


def log_always(msg):
    addon = get_addon()
    aid = addon.getAddonInfo("id") if addon else "service.skippy"
    xbmc.log(f"[{aid} - SegmentItem] {_ascii_log_text(msg)}", xbmc.LOGINFO)

# Polling / floating-point slack at boundaries so we do not miss a segment when
# getTime() falls just outside [start, end]. Strict match is preferred; lenient
# match picks a single nearest segment when none are strictly active.
SEGMENT_PLAYBACK_TOLERANCE = 0.25


def segment_is_active_lenient(segment, current_time, tol=None):
    """True if current_time is inside [start, end] expanded by tol on both sides."""
    if tol is None:
        tol = SEGMENT_PLAYBACK_TOLERANCE
    t = float(current_time)
    return (segment.start_seconds - tol) <= t <= (segment.end_seconds + tol)


def segments_active_for_playback(segments, current_time, tol=None):
    """
    Segments to treat as active for skip/dialog logic. Uses strict [start, end] first;
    if none match, includes at most one lenient match (nearest nominal interval, then
    latest start) so adjacent chapters do not both prompt after a boundary cross.
    """
    if tol is None:
        tol = SEGMENT_PLAYBACK_TOLERANCE
    t = float(current_time)
    if not segments:
        return []
    strict = [s for s in segments if s.start_seconds <= t <= s.end_seconds]
    if strict:
        return strict
    loose = [
        s for s in segments if (s.start_seconds - tol) <= t <= (s.end_seconds + tol)
    ]
    if not loose:
        return []

    def dist_outside(s):
        if s.start_seconds <= t <= s.end_seconds:
            return 0.0
        if t < s.start_seconds:
            return s.start_seconds - t
        return t - s.end_seconds

    loose.sort(key=lambda s: (dist_outside(s), -s.start_seconds))
    return [loose[0]]


class SegmentItem:
    def __init__(self, start_seconds, end_seconds, label="segment", source="edl", action_type=None, timeout=5.0, allow_input=True, next_segment_start=None, next_segment_info=None):
        if end_seconds < start_seconds:
            raise ValueError(f"Segment end time ({end_seconds}) must be after start time ({start_seconds})")

        self.start_seconds = start_seconds
        self.end_seconds = end_seconds
        self.source = source
        self.segment_type_label = normalize_label(label)
        self.action_type = normalize_label(action_type) if action_type else None
        self.timeout = timeout
        self.allow_input = allow_input
        self.next_segment_start = next_segment_start  # New attribute for overlapping/nested skips
        self.next_segment_info = next_segment_info  # New attribute for describing the next segment

        log_segment(f"🧩 New SegmentItem created: {self}")

    def is_active(self, current_time):
        return self.start_seconds <= current_time <= self.end_seconds

    def get_duration(self):
        return self.end_seconds - self.start_seconds

    def to_dict(self):
        # Convert segment to dictionary format
        result = {
            "start": self.start_seconds,
            "end": self.end_seconds,
            "label": self.segment_type_label,
            "source": self.source,
            "action_type": self.action_type,
            "next_segment_start": self.next_segment_start, # Include new attribute
            "next_segment_info": self.next_segment_info # Include new attribute
        }
        log_segment(f"📦 Converted SegmentItem to dict: {result}")
        return result

    def __str__(self):
        action = f", action={self.action_type}" if self.action_type else ""
        next_jump = f", next_jump={self.next_segment_start}" if self.next_segment_start else ""
        next_info = f", next_info={self.next_segment_info}" if self.next_segment_info else ""
        return f"{self.segment_type_label} [{self.start_seconds}-{self.end_seconds}] ({self.source}{action}{next_jump}{next_info})"
