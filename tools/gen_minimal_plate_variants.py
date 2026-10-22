# -*- coding: utf-8 -*-
"""Pre-render every Minimal plate at each width the dialog can use.

The plates are drawn at a fixed height and several widths. Stretching one image
to every width distorts the rounded ends, so each plate is rendered per width:
the end caps keep their shape and only the flat middle stretches.

Output: ``resources/skins/default/media/plates/<stem>_w<width720>.png`` at 1080i
height (69px), so the 720p dialog downsamples and 1080i is 1:1.
Run from the add-on root: ``python tools/gen_minimal_plate_variants.py``.
"""
from __future__ import annotations

import glob
import os

from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MEDIA = os.path.join(ROOT, "resources", "skins", "default", "media")
OUT = os.path.join(MEDIA, "plates")

# Must match MINIMAL_PLATE_WIDTHS_720 in skip_dialog_appearance.py.
WIDTHS_720 = (120, 150, 190, 240, 270, 320, 380, 420)
HEIGHT_720 = 46
SCALE = 1.5  # 1080i output
ALPHA_MIN = 8


def _bbox(im):
    return im.split()[3].point(lambda v: 255 if v > ALPHA_MIN else 0).getbbox() or (
        0,
        0,
        im.width,
        im.height,
    )


def render_variant(src: Image.Image, width_720: int) -> Image.Image:
    """Nine-slice-resize ``src`` to ``width_720`` x 46 (at 1080i scale)."""
    out_h = int(round(HEIGHT_720 * SCALE))
    out_w = int(round(width_720 * SCALE))
    w0, h0 = src.size
    left, top, right, bottom = _bbox(src)
    s = out_h / float(h0)  # one vertical scale for the whole canvas
    # Cap = half the plate's own height (a pill end), plus any transparent margin.
    cap_src = int(round((bottom - top) / 2.0))
    left_src = min(w0 // 2 - 1, left + cap_src)
    right_src = min(w0 // 2 - 1, (w0 - right) + cap_src)
    left_dst = max(1, int(round(left_src * s)))
    right_dst = max(1, int(round(right_src * s)))
    mid_dst = max(1, out_w - left_dst - right_dst)

    def part(box, size):
        return src.crop(box).resize(size, Image.LANCZOS)

    canvas = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 0))
    canvas.paste(part((0, 0, left_src, h0), (left_dst, out_h)), (0, 0))
    canvas.paste(
        part((left_src, 0, w0 - right_src, h0), (mid_dst, out_h)), (left_dst, 0)
    )
    canvas.paste(
        part((w0 - right_src, 0, w0, h0), (right_dst, out_h)), (left_dst + mid_dst, 0)
    )
    return canvas


def main():
    os.makedirs(OUT, exist_ok=True)
    count = 0
    for path in sorted(glob.glob(os.path.join(MEDIA, "minimal_*.png"))):
        stem = os.path.splitext(os.path.basename(path))[0]
        src = Image.open(path).convert("RGBA")
        for width in WIDTHS_720:
            render_variant(src, width).save(
                os.path.join(OUT, "%s_w%d.png" % (stem, width)), optimize=True
            )
            count += 1
    print("Wrote %d plate variants to %s" % (count, OUT))


if __name__ == "__main__":
    main()
