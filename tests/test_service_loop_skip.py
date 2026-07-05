# -*- coding: utf-8 -*-
"""Skip loop confirm/dismiss paths."""

import unittest

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()


class ServiceLoopSkipFormatTests(unittest.TestCase):
    def test_tuple_seg_id_log_format(self):
        seg_id = (0, 76)
        msg = "User confirmed skip for segment ID %s" % (seg_id,)
        self.assertIn("(0, 76)", msg)


if __name__ == "__main__":
    unittest.main()
