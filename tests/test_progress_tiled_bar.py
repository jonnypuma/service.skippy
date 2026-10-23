import os
import re
import unittest

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

from skip_dialog_appearance import (  # noqa: E402
    SMOOTH_PROGRESS_TILED_FILL_ID,
    progress_tiled_variant,
)

SKIN = os.path.join(os.path.dirname(__file__), "..", "resources", "skins", "default")


class TiledProgressBarTests(unittest.TestCase):
    def test_segmented_styles_have_a_variant_for_every_supported_height(self):
        for color in ("white", "teal", "green"):
            for h in (5, 16, 24, 32, 48):
                self.assertEqual(
                    progress_tiled_variant("progress_mid_segmented_%s.png" % color, h),
                    "progress_tiled_segmented_%s_h%d.png" % (color, h),
                )

    def test_other_styles_keep_stretching(self):
        self.assertIsNone(progress_tiled_variant("progress_mid.png", 16))
        self.assertIsNone(progress_tiled_variant("progress_mid_flat_teal.png", 16))
        self.assertIsNone(progress_tiled_variant("", 16))
        self.assertIsNone(progress_tiled_variant("progress_mid_segmented_teal.png", 500))

    def test_textures_are_drawn_one_to_one(self):
        """Height equals the bar height and the pitch equals what the dialog snaps to."""
        from PIL import Image

        from skip_dialog_appearance import tiled_segment_pitch_px

        for h in (5, 16, 24, 48):
            path = os.path.join(SKIN, "media", "progress_tiled_segmented_teal_h%d.png" % h)
            img = Image.open(path).convert("RGBA")
            self.assertEqual(img.height, h)
            self.assertGreaterEqual(img.width, 1920)
            row = [img.getpixel((x, h // 2))[3] for x in range(img.width)]
            starts = [x for x in range(1, len(row)) if row[x] and not row[x - 1]]
            self.assertEqual(starts[1] - starts[0], tiled_segment_pitch_px(h))

    def test_every_smooth_fill_has_a_cropped_tiled_twin(self):
        checked = 0
        for res in ("720p", "1080i"):
            for name in sorted(os.listdir(os.path.join(SKIN, res))):
                if not name.endswith(".xml") or name.endswith("-Jon.xml"):
                    continue
                text = open(os.path.join(SKIN, res, name), encoding="utf-8").read()
                if 'id="3031"' not in text:
                    continue
                checked += 1
                self.assertIn('id="%d"' % SMOOTH_PROGRESS_TILED_FILL_ID, text, (res, name))
                twin = re.search(r'<control type="image" id="3032">.*?</control>', text, re.S).group(0)
                self.assertIn('align="left"', twin)
                self.assertIn("skippy_bar_tiled", twin)
                plain = re.search(r'<control type="image" id="3031">.*?</control>', text, re.S).group(0)
                self.assertIn("!String.IsEqual(Window.Property(skippy_bar_tiled),true)", plain)
        self.assertGreaterEqual(checked, 12)


class SnapToSegmentsTests(unittest.TestCase):
    def test_pitch_matches_the_generator(self):
        import importlib.util

        from skip_dialog_appearance import tiled_segment_pitch_px

        spec = importlib.util.spec_from_file_location(
            "gen_tiled", os.path.join(os.path.dirname(__file__), "..", "tools", "gen_progress_tiled_textures.py")
        )
        gen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gen)
        for h in range(4, 65):
            self.assertEqual(gen.pitch_px(h), tiled_segment_pitch_px(h), h)

    def test_default_bar_pitch_is_13px(self):
        from skip_dialog_appearance import tiled_segment_pitch_px

        self.assertEqual(tiled_segment_pitch_px(16), 13)

    def test_widths_move_in_whole_segments(self):
        from skip_dialog_appearance import snap_to_whole_segments

        seen = {snap_to_whole_segments(w, 420, 13) for w in range(0, 421)}
        self.assertEqual(sorted(seen), [13 * k for k in range(0, 33)])

    def test_never_exceeds_the_bar(self):
        from skip_dialog_appearance import snap_to_whole_segments

        self.assertLessEqual(snap_to_whole_segments(420, 420, 13), 420)
        self.assertEqual(snap_to_whole_segments(5, 420, 0), 5)


if __name__ == "__main__":
    unittest.main()
