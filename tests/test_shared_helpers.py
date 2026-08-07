# -*- coding: utf-8 -*-
"""Shared segment/time/EDL helpers used by the service, editor, and marker."""

import types
import unittest

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

from edl_format import EDL_DEFAULT_ACTION, parse_edl_line
from segment_relations import (
    JUMP_KIND_NAMED,
    JUMP_KIND_REMAINING,
    RELATION_NESTED,
    RELATION_OVERLAPPING,
    iter_forward_overlaps,
    jump_info_nested,
    jump_info_overlapping,
    jump_info_remaining,
    parse_jump_info,
    segment_id,
)
from time_format import (
    format_clock,
    format_jump_clock,
    hms_to_seconds,
    seconds_to_edl,
    seconds_to_hms,
)


def _seg(start, end, label="intro"):
    return types.SimpleNamespace(
        start_seconds=start, end_seconds=end, segment_type_label=label
    )


class EdlLineTests(unittest.TestCase):
    def test_parses_three_column_row(self):
        self.assertEqual(parse_edl_line("0 60 5"), (0.0, 60.0, 5))

    def test_ignores_comments_and_blanks(self):
        self.assertIsNone(parse_edl_line("# note with words"))
        self.assertIsNone(parse_edl_line("   "))
        self.assertIsNone(parse_edl_line(None))

    def test_missing_action_needs_a_default(self):
        self.assertIsNone(parse_edl_line("0 60"))
        self.assertEqual(
            parse_edl_line("0 60", default_action=EDL_DEFAULT_ACTION), (0.0, 60.0, 4)
        )

    def test_trailing_columns_are_ignored(self):
        self.assertEqual(parse_edl_line("10.5\t20.25\t9\textra"), (10.5, 20.25, 9))

    def test_malformed_row_is_skipped_not_fatal(self):
        rows = ["0 60 5", "not a row at all", "70 80 9"]
        parsed = [parse_edl_line(row) for row in rows]
        self.assertEqual(parsed, [(0.0, 60.0, 5), None, (70.0, 80.0, 9)])


class SegmentRelationTests(unittest.TestCase):
    def test_segment_id_rounds_to_whole_seconds(self):
        self.assertEqual(segment_id(_seg(0.4, 59.6)), (0, 60))

    def test_forward_overlaps_classify_and_stop(self):
        segments = [_seg(0, 60), _seg(20, 40, "recap"), _seg(120, 130, "preview")]
        self.assertEqual(
            [(s.segment_type_label, rel) for s, rel in iter_forward_overlaps(segments, 0)],
            [("recap", RELATION_NESTED)],
        )

    def test_forward_overlaps_reports_partial_overlap(self):
        segments = [_seg(0, 60), _seg(50, 90, "credits")]
        self.assertEqual(
            [rel for _s, rel in iter_forward_overlaps(segments, 0)],
            [RELATION_OVERLAPPING],
        )

    def test_abutting_segments_are_not_related(self):
        segments = [_seg(0, 60), _seg(60, 90, "credits")]
        self.assertEqual(list(iter_forward_overlaps(segments, 0)), [])

    def test_jump_info_round_trips(self):
        self.assertEqual(
            parse_jump_info(jump_info_remaining(_seg(0, 60, "Intro"))),
            (JUMP_KIND_REMAINING, "Intro"),
        )
        self.assertEqual(
            parse_jump_info(jump_info_nested(_seg(20, 40, "recap"))),
            (JUMP_KIND_NAMED, "recap"),
        )
        self.assertEqual(
            parse_jump_info(jump_info_overlapping(_seg(50, 90, "credits"))),
            (JUMP_KIND_NAMED, "credits"),
        )

    def test_unknown_jump_info_has_no_kind(self):
        self.assertEqual(parse_jump_info(""), (None, None))
        self.assertEqual(parse_jump_info("next segment"), (None, None))


class TimeFormatTests(unittest.TestCase):
    def test_chapter_hms_round_trip(self):
        self.assertEqual(seconds_to_hms(3661.5), "01:01:01.500")
        self.assertEqual(hms_to_seconds("01:01:01.500"), 3661.5)

    def test_negative_seconds_clamp_to_zero(self):
        self.assertEqual(seconds_to_hms(-5), "00:00:00.000")

    def test_short_forms_are_accepted(self):
        self.assertEqual(hms_to_seconds("1:30"), 90.0)
        self.assertEqual(hms_to_seconds("42"), 42.0)

    def test_bad_input_raises(self):
        for bad in (None, "", "-1:00", "1:2:3:4", "abc"):
            with self.assertRaises(ValueError):
                hms_to_seconds(bad)

    def test_edl_seconds_are_millisecond_rounded(self):
        self.assertEqual(seconds_to_edl(12.3456), "12.346")

    def test_clock_formats(self):
        self.assertEqual(format_clock(75), "1:15")
        self.assertEqual(format_clock(3675), "1:01:15")
        self.assertEqual(format_jump_clock(75), "01:15")
        self.assertEqual(format_jump_clock(3675), "01:01:15")


if __name__ == "__main__":
    unittest.main()
