# -*- coding: utf-8 -*-
"""Regression: segment ids are (start, end) tuples; must not break % formatting."""

import unittest


class SegIdFormattingTests(unittest.TestCase):
    def test_single_placeholder_with_tuple_seg_id(self):
        seg_id = (0, 76)
        msg = "User confirmed skip for segment ID %s" % (seg_id,)
        self.assertEqual(msg, "User confirmed skip for segment ID (0, 76)")

    def test_broken_pattern_raises(self):
        seg_id = (0, 76)
        with self.assertRaises(TypeError):
            _ = "User confirmed skip for segment ID %s" % seg_id


if __name__ == "__main__":
    unittest.main()
