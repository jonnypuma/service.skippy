# -*- coding: utf-8 -*-
"""Pass 1/2 segment processing."""

import copy
import types
import unittest
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

from segment_item import SegmentItem
from service_segment_processed_cache import (
    store_segment_processed_cache,
    try_get_processed_cache,
)
from service_segment_processing import (
    parse_and_process_segments,
    re_evaluate_segment_jump_points,
)
from service_segment_sources import parse_edl
from service_segment_processing import (
    build_nested_parent_map,
    is_nested_segment,
    should_suppress_segment_dialog,
)
from skip_dialog_appearance import format_next_jump_label


class ParseAndProcessTests(unittest.TestCase):
    def test_exact_nested_edl_links_remaining_parent_label(self):
        """The reported 0-60 Intro / 20-40 Recap flow renders end-to-end."""
        with patch(
            "service_segment_sources.safe_file_read",
            return_value="0 60 5\n20 40 9\n",
        ), patch(
            "service_segment_sources.get_edl_type_map",
            return_value={5: "Intro", 9: "Recap"},
        ), patch("service_segment_sources.get_addon", return_value=None):
            segments = parse_edl("episode.mkv", update_monitor=False)

        self.assertEqual(
            [(s.start_seconds, s.end_seconds, s.segment_type_label) for s in segments],
            [(0.0, 60.0, "intro"), (20.0, 40.0, "recap")],
        )

        # At the nested segment, its skip lands at 40s inside the parent.
        re_evaluate_segment_jump_points(segments, current_time=20.0)
        recap = segments[1]
        self.assertEqual(recap.next_segment_start, 40.0)
        self.assertEqual(recap.next_segment_info, "remaining 'intro'")
        self.assertEqual(
            format_next_jump_label(
                None, recap.next_segment_info, recap.next_segment_start
            ),
            "Skip to remaining Intro at 00:40",
        )

    def test_nested_detection(self):
        parent = SegmentItem(0.0, 100.0, "recap", source="xml")
        child = SegmentItem(10.0, 50.0, "prologue", source="xml")
        self.assertTrue(is_nested_segment(parent, child))

    def test_suppress_parent_when_nested_active(self):
        parent = SegmentItem(0.0, 100.0, "recap", source="xml")
        child = SegmentItem(10.0, 50.0, "prologue", source="xml")
        segs = [parent, child]
        self.assertTrue(
            should_suppress_segment_dialog(parent, segs, 25.0, recently_dismissed=set())
        )

    def test_parent_map_matches_nested(self):
        parent = SegmentItem(0.0, 100.0, "recap", source="xml")
        child = SegmentItem(10.0, 50.0, "prologue", source="xml")
        parent_map = build_nested_parent_map([parent, child])
        self.assertEqual(parent_map[(10, 50)], (0, 100))

    def test_parse_edl_skips_exists_when_probe_confirmed(self):
        from unittest.mock import MagicMock

        from service_sidecar_probe_cache import SidecarProbeResult
        from service_segment_sources import parse_edl

        monitor = MagicMock()
        probe = SidecarProbeResult(
            chapter_path=None, edl_path="/media/show.edl", probed=True
        )

        class _File:
            def read(self):
                return "0 60 5\n"

            def close(self):
                return None

        with patch(
            "service_sidecar_probe_cache.resolve_sidecar_paths", return_value=probe
        ), patch("service_sidecar_paths.vfs_file_exists") as exists, patch(
            "service_segment_sources.xbmcvfs.File", return_value=_File()
        ), patch(
            "service_segment_sources.get_edl_type_map", return_value={5: "Intro"}
        ), patch(
            "service_segment_sources.get_addon", return_value=None
        ):
            segments = parse_edl(
                "/media/show.mkv", update_monitor=False, segment_monitor=monitor
            )
        exists.assert_not_called()
        self.assertEqual(
            [(s.start_seconds, s.end_seconds, s.segment_type_label) for s in segments],
            [(0.0, 60.0, "intro")],
        )

    def test_parse_chapters_skips_exists_when_probe_confirmed(self):
        from unittest.mock import MagicMock

        from service_sidecar_probe_cache import SidecarProbeResult
        from service_segment_sources import parse_chapters

        xml_text = (
            '<?xml version="1.0"?>'
            "<Chapters><EditionEntry><ChapterAtom>"
            "<ChapterTimeStart>00:00:00.000000000</ChapterTimeStart>"
            "<ChapterTimeEnd>00:00:10.000000000</ChapterTimeEnd>"
            "<ChapterDisplay><ChapterString>Intro</ChapterString></ChapterDisplay>"
            "</ChapterAtom></EditionEntry></Chapters>"
        )
        monitor = MagicMock()
        probe = SidecarProbeResult(
            chapter_path="/media/show_chapters.xml", edl_path=None, probed=True
        )

        class _File:
            def read(self):
                return xml_text

            def close(self):
                return None

        with patch(
            "service_sidecar_probe_cache.resolve_sidecar_paths", return_value=probe
        ), patch("service_segment_sources.xbmcvfs.exists") as exists, patch(
            "service_segment_sources.xbmcvfs.File", return_value=_File()
        ):
            segments = parse_chapters(
                "/media/show.mkv", update_monitor=True, segment_monitor=monitor
            )
        exists.assert_not_called()
        self.assertTrue(monitor.segment_file_found)
        self.assertEqual(
            [(s.start_seconds, s.end_seconds, s.segment_type_label) for s in segments],
            [(0.0, 10.0, "intro")],
        )


def _layout(*rows):
    return [SegmentItem(s, e, label, source="xml") for s, e, label in rows]


def _first_parse(rows, current_time):
    """Run the real parse-and-link pipeline over ``rows`` with overlaps kept."""
    segments = _layout(*rows)
    monitor = types.SimpleNamespace(
        segment_parse_cache=None,
        skippy_skipping_since=None,
        toast_overlap_shown=True,
        overlap_editor_opened_for_path=None,
    )
    player = types.SimpleNamespace(isPlayingVideo=lambda: True)
    with patch.multiple(
        "service_segment_processing",
        get_addon=lambda: MagicMock(),
        addon_get_bool=lambda _addon, _key, default=False: False,
        show_overlapping_toast=lambda: False,
        try_get_processed_cache=lambda *a, **k: (None, "miss"),
        store_segment_processed_cache=lambda *a, **k: None,
        _source_settings_signature=lambda *a, **k: (),
    ):
        return parse_and_process_segments(
            "episode.mkv",
            current_time,
            "episode",
            get_cached_source_segments=lambda _path, _type: segments,
            segment_monitor=monitor,
            segment_player=player,
            overlap_toast_icon_path="",
            log_if_changed=lambda _key, _msg: None,
        )


def _link(segment):
    return segment.next_segment_start, segment.next_segment_info


# A recap with two nested segments: the case where the parse-time linking and the
# rewind-time re-evaluation used to disagree.
TWO_NESTED = (
    (0.0, 100.0, "recap"),
    (10.0, 20.0, "prologue"),
    (50.0, 60.0, "ad"),
)
PLAYHEADS = (None, 0.0, 5.0, 10.0, 15.0, 20.0, 30.0, 50.0, 55.0, 60.0, 70.0, 99.0)


class MultipleNestedSegmentTests(unittest.TestCase):
    def test_parent_skip_stops_at_each_nested_segment_in_turn(self):
        expected = {
            None: (10.0, "nested segment 'prologue'"),
            5.0: (10.0, "nested segment 'prologue'"),
            15.0: (50.0, "nested segment 'ad'"),
            30.0: (50.0, "nested segment 'ad'"),
            55.0: (None, None),
            70.0: (None, None),
        }
        for current_time, link in expected.items():
            with self.subTest(current_time=current_time):
                recap = _first_parse(TWO_NESTED, current_time)[0]
                self.assertEqual(_link(recap), link)

    def test_rewind_reevaluation_agrees_with_the_first_parse(self):
        for current_time in PLAYHEADS:
            if current_time is None:
                continue
            with self.subTest(current_time=current_time):
                parsed = _first_parse(TWO_NESTED, current_time)
                rewound = _layout(*TWO_NESTED)
                re_evaluate_segment_jump_points(rewound, current_time)
                self.assertEqual(_link(parsed[0]), _link(rewound[0]))

    def test_every_nested_segment_lands_back_inside_the_parent(self):
        for current_time in PLAYHEADS:
            with self.subTest(current_time=current_time):
                _recap, prologue, ad = _first_parse(TWO_NESTED, current_time)
                self.assertEqual(_link(prologue), (20.0, "remaining 'recap'"))
                self.assertEqual(_link(ad), (60.0, "remaining 'recap'"))

    def test_leaving_a_nested_segment_points_the_parent_at_the_next_one(self):
        segments = _first_parse(TWO_NESTED, 0.0)
        recap = segments[0]
        self.assertEqual(_link(recap), (10.0, "nested segment 'prologue'"))

        # The playhead leaves the prologue: the service re-evaluates at that point.
        recap.next_segment_start = None
        recap.next_segment_info = None
        re_evaluate_segment_jump_points(segments, 20.5)
        self.assertEqual(_link(recap), (50.0, "nested segment 'ad'"))

        # ...and once the ad is behind as well, the parent skips straight to its end.
        re_evaluate_segment_jump_points(segments, 60.5)
        self.assertEqual(_link(recap), (None, None))

    def test_overlap_after_a_passed_nested_segment_is_still_the_next_stop(self):
        rows = (
            (0.0, 100.0, "recap"),
            (10.0, 20.0, "prologue"),
            (90.0, 130.0, "credits"),
        )
        expected = (90.0, "overlapping segment 'credits'")
        parsed = _first_parse(rows, 15.0)
        rewound = _layout(*rows)
        re_evaluate_segment_jump_points(rewound, 15.0)
        self.assertEqual(_link(parsed[0]), expected)
        self.assertEqual(_link(rewound[0]), expected)

    def test_single_nested_segment_keeps_its_behaviour(self):
        rows = ((0.0, 50.0, "intro"), (20.0, 40.0, "recap"))
        self.assertEqual(
            _link(_first_parse(rows, 0.0)[0]), (20.0, "nested segment 'recap'")
        )
        self.assertEqual(_link(_first_parse(rows, 30.0)[0]), (None, None))
        self.assertEqual(
            _link(_first_parse(rows, 0.0)[1]), (40.0, "remaining 'intro'")
        )

    def test_cached_links_follow_the_same_rule_when_the_playhead_moves(self):
        monitor = types.SimpleNamespace(segment_processed_cache=None)
        pass1 = _layout(*TWO_NESTED)
        processed = _first_parse(TWO_NESTED, 0.0)
        kwargs = dict(source_settings_sig=(), sidecar_signature="sig")
        store_segment_processed_cache(
            monitor, "episode.mkv", "episode", pass1, pass1, processed, 0.0, **kwargs
        )

        def cached_recap_link(current_time):
            result, status = try_get_processed_cache(
                monitor,
                "episode.mkv",
                "episode",
                pass1,
                current_time,
                clone_pass1_fn=lambda segs: [copy.copy(s) for s in segs],
                log_if_changed=lambda _key, _msg: None,
                **kwargs,
            )
            return status, _link(result[0])

        self.assertEqual(
            cached_recap_link(15.0), ("phase_reeval", (50.0, "nested segment 'ad'"))
        )
        self.assertEqual(cached_recap_link(55.0), ("phase_reeval", (None, None)))


if __name__ == "__main__":
    unittest.main()
