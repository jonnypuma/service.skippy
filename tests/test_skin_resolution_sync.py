import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import gen_skin_1080i as gen  # noqa: E402


class SkinResolutionSyncTests(unittest.TestCase):
    def test_1080i_skins_match_720p_layout(self):
        """Layout edits must be made in 720p and mirrored (tools/gen_skin_1080i.py --write)."""
        problems = []
        for name in sorted(os.listdir(gen.SRC)):
            if not name.endswith(".xml") or name.endswith("-Jon.xml") or name in gen.MANUAL:
                continue
            with open(os.path.join(gen.SRC, name), encoding="utf-8") as fh:
                expected = gen.convert(fh.read())
            with open(os.path.join(gen.DST, name), encoding="utf-8") as fh:
                actual = fh.read()
            diffs = gen.drift(expected, actual)
            if diffs:
                problems.append("%s: %s" % (name, diffs[0]))
        self.assertEqual(problems, [])


class SkinCornerDerivationTests(unittest.TestCase):
    def test_corner_files_are_derived_from_top_left(self):
        for name, expected in gen.corner_sources().items():
            with open(os.path.join(gen.SRC, name), encoding="utf-8", newline="") as fh:
                self.assertEqual(fh.read(), expected, name)


class ButtonLabelOffsetTests(unittest.TestCase):
    def test_full_mode_buttons_nudge_the_label_up(self):
        import re

        for res, expected in (("720p", "-3"), ("1080i", "-4")):
            text = open(os.path.join(gen.ROOT, res, "SkipDialog_TopLeft.xml"), encoding="utf-8").read()
            for cid in ("3012", "3013", "3015", "3016"):
                block = re.search(r'<control type="button" id="%s">.*?</control>' % cid, text, re.S).group(0)
                self.assertIn("<textoffsety>%s</textoffsety>" % expected, block, (res, cid))


class PreviewLabelNudgeTests(unittest.TestCase):
    def test_preview_labels_are_raised(self):
        import skip_dialog_appearance as ap

        self.assertEqual(ap.preview_label_nudge(lambda v: int(round(v * 2))), 2)
        self.assertEqual(ap.preview_label_nudge(lambda v: v), 1)
        self.assertEqual(ap.preview_label_nudge(lambda v: v, "button_focus_underline_white.png"), 3)


if __name__ == "__main__":
    unittest.main()
