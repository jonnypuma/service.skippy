# -*- coding: utf-8 -*-
"""Ask dialog next-jump subtext (named segment / remaining parent)."""

import unittest

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

from skipdialog import format_next_jump_label


class _Addon:
    def getLocalizedString(self, _sid):
        return ""


class FormatNextJumpLabelTests(unittest.TestCase):
    def test_none_when_no_jump_target(self):
        self.assertIsNone(format_next_jump_label(_Addon(), "remaining 'Intro'", None))

    def test_remaining_quoted(self):
        self.assertEqual(
            format_next_jump_label(_Addon(), "remaining 'Intro'", 40.0),
            "Skip to remaining Intro at 00:40",
        )

    def test_remaining_unquoted_legacy(self):
        self.assertEqual(
            format_next_jump_label(_Addon(), "remaining Intro", 40.0),
            "Skip to remaining Intro at 00:40",
        )

    def test_remaining_recap_preview(self):
        self.assertEqual(
            format_next_jump_label(_Addon(), "remaining 'Recap'", 90.5),
            "Skip to remaining Recap at 01:30",
        )
        self.assertEqual(
            format_next_jump_label(_Addon(), "remaining 'Preview'", 125.0),
            "Skip to remaining Preview at 02:05",
        )

    def test_preserves_configured_label_casing(self):
        self.assertEqual(
            format_next_jump_label(_Addon(), "remaining 'TV OVA'", 40.0),
            "Skip to remaining TV OVA at 00:40",
        )
        self.assertEqual(
            format_next_jump_label(_Addon(), "nested segment 'Behind-the-Scenes'", 20.0),
            "Skip to Behind the scenes at 00:20",
        )

    def test_formats_hours_only_when_needed(self):
        self.assertEqual(
            format_next_jump_label(_Addon(), "remaining 'Intro'", 3600.0),
            "Skip to remaining Intro at 01:00:00",
        )

    def test_nested_quoted_destination(self):
        self.assertEqual(
            format_next_jump_label(_Addon(), "nested segment 'recap'", 20.0),
            "Skip to Recap at 00:20",
        )

    def test_overlapping_quoted_destination(self):
        self.assertEqual(
            format_next_jump_label(_Addon(), "overlapping segment 'Preview'", 80.0),
            "Skip to Preview at 01:20",
        )

    def test_generic_fallback(self):
        self.assertEqual(
            format_next_jump_label(_Addon(), None, 65.0),
            "Skip to next segment at 01:05",
        )
        self.assertEqual(
            format_next_jump_label(_Addon(), "something opaque", 65.0),
            "Skip to next segment at 01:05",
        )


class ApplyJumpPropertiesOffsetTests(unittest.TestCase):
    def test_next_jump_time_uses_seek_destination(self):
        from segment_item import SegmentItem
        from unittest.mock import MagicMock, patch

        import skip_dialog_appearance as appearance

        seg = SegmentItem(0.0, 50.0, "intro", source="xml")
        seg.next_segment_start = 20.0
        seg.next_segment_info = "nested segment 'recap'"
        window = MagicMock()
        with patch.object(
            appearance,
            "compute_skip_seek_destination_seconds",
            return_value=18.0,
        ):
            label = appearance.apply_jump_properties(window, _Addon(), seg)
        self.assertEqual(label, "Skip to Recap at 00:18")
        window.setProperty.assert_any_call("next_jump_label", "Skip to Recap at 00:18")


if __name__ == "__main__":
    unittest.main()
