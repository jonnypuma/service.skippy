import xbmc
import unicodedata

from settings_utils import get_addon, log_segment, log_segment_detail


def log(msg):
    log_segment(msg)


def _ascii_log_text(msg):
    return unicodedata.normalize("NFKD", str(msg)).encode("ascii", "ignore").decode("ascii")


def log_always(msg):
    addon = get_addon()
    aid = addon.getAddonInfo("id") if addon else "service.skippy"
    xbmc.log(f"[{aid} - SegmentItem] {_ascii_log_text(msg)}", xbmc.LOGINFO)

def normalize_label(text):
    # Normalize and lowercase labels for consistent matching
    return unicodedata.normalize("NFKC", text or "").strip().lower()


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

# 🔍 Dialog trigger logic — stateless, no caching
def should_show_skip_dialog(current_time, segments, last_shown_times, debounce_seconds=5):
    for segment in segments:
        if segment_is_active_lenient(segment, current_time):
            segment_id = f"{segment.start_seconds}-{segment.end_seconds}"
            last_shown = last_shown_times.get(segment_id, 0)
            time_since_last = abs(current_time - last_shown)

            if time_since_last > debounce_seconds:
                last_shown_times[segment_id] = current_time
                log_segment(f"📌 Triggering skip dialog for segment: {segment}")
                return segment
            else:
                log_segment_detail(
                    f"⏳ Debounce active for segment {segment_id} — last shown {time_since_last:.2f}s ago"
                )
    log_segment_detail("🔕 No eligible segment found for skip dialog at current time")
    return None

# Optional: Unit test block (can be moved to a separate test file)
if __name__ == "__main__":
    import unittest

    log_always("🧪 Running SegmentItem unit tests")

    class TestSegmentItem(unittest.TestCase):
        def test_valid_segment(self):
            seg = SegmentItem(10, 20, "intro", action_type="skip")
            self.assertEqual(seg.get_duration(), 10)
            self.assertTrue(seg.is_active(15))
            self.assertFalse(seg.is_active(25))
            self.assertEqual(seg.action_type, "skip")
            self.assertEqual(seg.timeout, 5.0)  # default value
            self.assertTrue(seg.allow_input)    # default value

        def test_invalid_segment(self):
            with self.assertRaises(ValueError):
                SegmentItem(30, 10, "bad")

        def test_to_dict(self):
            seg = SegmentItem(5, 15, "credits", "xml", "mute")
            expected = {
                "start": 5,
                "end": 15,
                "label": "credits",
                "source": "xml",
                "action_type": "mute",
                "next_segment_start": None,
                "next_segment_info": None,
            }
            self.assertEqual(seg.to_dict(), expected)

        def test_custom_timeout_and_input(self):
            seg = SegmentItem(0, 10, "ad", action_type="skip", timeout=8.0, allow_input=False)
            self.assertEqual(seg.timeout, 8.0)
            self.assertFalse(seg.allow_input)
            
        def test_with_next_segment_start(self):
            seg = SegmentItem(10, 30, "intro", next_segment_start=20, next_segment_info="nested segment 'recap'")
            self.assertEqual(seg.next_segment_start, 20)
            self.assertEqual(seg.next_segment_info, "nested segment 'recap'")
            expected = {
                "start": 10,
                "end": 30,
                "label": "intro",
                "source": "edl",
                "action_type": None,
                "next_segment_start": 20,
                "next_segment_info": "nested segment 'recap'"
            }
            self.assertEqual(seg.to_dict(), expected)

        def test_segments_active_for_playback_strict(self):
            a = SegmentItem(0, 10, "a")
            b = SegmentItem(10, 20, "b")
            segs = [a, b]
            self.assertEqual(segments_active_for_playback(segs, 5), [a])
            self.assertEqual(len(segments_active_for_playback(segs, 10)), 2)

        def test_segments_active_for_playback_lenient_gap(self):
            a = SegmentItem(0, 10, "a")
            b = SegmentItem(15, 25, "b")
            segs = [a, b]
            # Gap (10, 15): strict none at 10.08; only 'a' overlaps via lenient tail
            act = segments_active_for_playback(segs, 10.08, tol=0.25)
            self.assertEqual(len(act), 1)
            self.assertEqual(act[0].segment_type_label, "a")

        def test_segments_active_for_playback_lenient_before_next(self):
            a = SegmentItem(0, 10, "a")
            b = SegmentItem(15, 25, "b")
            segs = [a, b]
            # Approaching 'b' before strict start
            act = segments_active_for_playback(segs, 14.88, tol=0.25)
            self.assertEqual(len(act), 1)
            self.assertEqual(act[0].segment_type_label, "b")

    unittest.main()