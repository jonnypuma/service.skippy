"""Pre-render pixel-exact, repeating variants of the segmented progress textures.

The smooth progress bar shows a *cropped* wide texture (instead of stretching a short one),
so segments keep their size while the bar fills or empties. For the crop to be crisp the
texture must be drawn 1:1, so one file is rendered per bar height (in screen pixels):
``progress_tiled_segmented_<color>_h<height>.png``, TILED_W px wide, one segment + gap per
``pitch_px(height)`` (same proportions as the stretched 512x32 originals on the default
bar: pitch 13 / gap 3 at height 16).
"""
import os
import sys

from PIL import Image

MEDIA = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "resources", "skins", "default", "media"
)
COLORS = ("white", "teal", "green")
HEIGHTS = range(4, 65)
TILED_W = 2048
PITCH_PER_HEIGHT = 0.8125  # 13 px pitch at height 16
GAP_PER_HEIGHT = 0.1625  # 3 px gap at height 16


def pitch_px(height):
    return max(3, int(round(PITCH_PER_HEIGHT * height)))


def gap_px(height):
    return max(1, int(round(GAP_PER_HEIGHT * height)))


def build(color, height):
    src = Image.open(os.path.join(MEDIA, "progress_mid_segmented_%s.png" % color)).convert("RGBA")
    rgba = src.getpixel((0, src.height // 2))
    pitch, gap = pitch_px(height), gap_px(height)
    out = Image.new("RGBA", (TILED_W, height), (0, 0, 0, 0))
    solid = Image.new("RGBA", (pitch - gap, height), rgba)
    for x in range(0, TILED_W, pitch):
        out.paste(solid, (x, 0))
    path = os.path.join(MEDIA, "progress_tiled_segmented_%s_h%d.png" % (color, height))
    out.save(path, optimize=True)
    return path


if __name__ == "__main__":
    for c in COLORS:
        for h in HEIGHTS:
            build(c, h)
    print("Wrote %d textures" % (len(COLORS) * len(HEIGHTS)))
    sys.exit(0)
