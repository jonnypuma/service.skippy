# -*- coding: utf-8 -*-
import unittest


class LogIfChangedTests(unittest.TestCase):
    def test_dedupes_repeated_messages(self):
        messages = []

        class Monitor:
            _last_log_state = {}

        monitor = Monitor()

        def log_if_changed(key, msg):
            if key not in monitor._last_log_state or monitor._last_log_state[key] != msg:
                monitor._last_log_state[key] = msg
                messages.append(msg)

        log_if_changed("playback_path", "path: /a.mkv")
        log_if_changed("playback_path", "path: /a.mkv")
        log_if_changed("playback_path", "path: /b.mkv")

        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0], "path: /a.mkv")
        self.assertEqual(messages[1], "path: /b.mkv")


if __name__ == "__main__":
    unittest.main()
