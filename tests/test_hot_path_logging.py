# -*- coding: utf-8 -*-
"""Hot-path logging should not spam on every is_active call."""

import unittest
from unittest.mock import patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

from segment_item import SegmentItem


class HotPathLoggingTests(unittest.TestCase):
    @patch("segment_item.log_segment_detail")
    def test_is_active_does_not_log(self, mock_detail):
        seg = SegmentItem(0.0, 60.0, "intro", source="xml")
        for t in range(100):
            seg.is_active(float(t))
        mock_detail.assert_not_called()

    @patch("segment_item.log_segment_detail")
    def test_get_duration_does_not_log(self, mock_detail):
        seg = SegmentItem(0.0, 60.0, "intro", source="xml")
        for _ in range(50):
            seg.get_duration()
        mock_detail.assert_not_called()


if __name__ == "__main__":
    unittest.main()
