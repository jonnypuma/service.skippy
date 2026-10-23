import unittest
from unittest.mock import MagicMock

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import skip_label_width_probe as probe  # noqa: E402


class FakeWindow:
    """Controls whose getWidth() mimics Kodi: auto grows with text, fixed stays put."""

    def __init__(self, auto_follows_text=True):
        self.text = {}
        self.auto_follows_text = auto_follows_text

    def getControl(self, cid):
        win = self
        ctrl = MagicMock()
        ctrl.setLabel.side_effect = lambda t, *a, **k: win.text.__setitem__(cid, t)

        def width():
            if cid == probe.FIXED_LABEL_ID:
                return 600
            if not win.auto_follows_text:
                return 1200
            return 20 + 9 * len(win.text.get(cid, ""))

        ctrl.getWidth.side_effect = width
        return ctrl


class LabelWidthProbeTests(unittest.TestCase):
    def test_measure_reads_every_sample_after_settling(self):
        slept = []
        rows = probe.measure(FakeWindow(), sleep=slept.append)
        self.assertEqual([r["text"] for r in rows], list(probe.SAMPLES))
        self.assertEqual(len(slept), len(probe.SAMPLES))
        self.assertEqual({r["fixed_label"] for r in rows}, {600})

    def test_verdict_reports_auto_controls_that_follow_text(self):
        rows = probe.measure(FakeWindow(True), sleep=lambda _ms: None)
        parts = probe.verdict(rows, 600)
        self.assertIn("auto label: getWidth() follows the text", parts)
        self.assertIn("auto button: getWidth() follows the text", parts)

    def test_verdict_flags_auto_controls_that_report_a_fixed_width(self):
        rows = probe.measure(FakeWindow(False), sleep=lambda _ms: None)
        parts = probe.verdict(rows, 600)
        self.assertTrue(any("auto label" in p and "does NOT follow" in p for p in parts))

    def test_report_lists_estimate_and_measured_widths(self):
        rows = probe.measure(FakeWindow(), sleep=lambda _ms: None)
        text = probe.format_report(rows, probe.verdict(rows, 600), 1.0)
        self.assertIn("Skip Commercial", text)
        self.assertIn("estim.", text)


if __name__ == "__main__":
    unittest.main()
