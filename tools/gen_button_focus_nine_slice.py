# -*- coding: utf-8 -*-
"""Rebuild skip-button focus textures.

9-slice templates: Kodi ``border`` keeps left/right endcaps unstretched and
tiles the flattened middle. Authored at Full-mode 720p button height (25px)
with 12px caps (Close is 80px; 12+12 leaves a stretchable middle).
Already-templated 64x25 files in media/ are skipped unless a source copy
exists in tools/nine_slice_src/.

Height-only (Aqua Vignette): the darkening is a full-width gradient, so
9-slice would make dark caps on a bright body. Those files are scaled to
25px tall and stretched as a whole.
"""
from __future__ import annotations

import os
import sys

from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MEDIA = os.path.join(ROOT, "resources", "skins", "default", "media")
SRC = os.path.join(ROOT, "tools", "nine_slice_src")

CAP = 12
MID = 40
OUT_H = 25
OUT_W = CAP + MID + CAP  # 64
ALPHA_MIN = 8

NINE_SLICE_FILES = (
    "button_focus_aqua_bevel.png",
    "button_focus_aqua_rounded.png",
    "button_focus_blue_rounded_3d.png",
    "button_focus_gold_rectangular_3d.png",
    "button_focus_3d_green.png",
    "button_focus_3d_pink.png",
    "button_focus_3d_light_pink.png",
)
# Full-width gradients: 9-slice would copy the darkest ends and flatten the
# bright center. Only normalize height to the 25px Skip/Close button.
HEIGHT_ONLY_FILES = ("button_focus_aqua_vignette.png",)


def _opaque_bbox(im, min_alpha=ALPHA_MIN):
    w, h = im.size
    px = im.load()
    minx, miny, maxx, maxy = w, h, -1, -1
    for y in range(h):
        for x in range(w):
            if px[x, y][3] > min_alpha:
                if x < minx:
                    minx = x
                if y < miny:
                    miny = y
                if x > maxx:
                    maxx = x
                if y > maxy:
                    maxy = y
    if maxx < 0:
        return None
    return (minx, miny, maxx + 1, maxy + 1)


def _zero_fully_transparent(im):
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a == 0 and (r or g or b):
                px[x, y] = (0, 0, 0, 0)
    return im


def _premul_resize(im, size):
    """Resize RGBA with premultiplied alpha to limit halo at rounded ends."""
    src = im.convert("RGBA")
    premul = []
    for r, g, b, a in src.getdata():
        if a == 0:
            premul.append((0, 0, 0, 0))
        else:
            premul.append(((r * a) // 255, (g * a) // 255, (b * a) // 255, a))
    tmp = Image.new("RGBA", src.size)
    tmp.putdata(premul)
    resized = tmp.resize(size, Image.Resampling.LANCZOS)
    out_data = []
    for r, g, b, a in resized.getdata():
        if a == 0:
            out_data.append((0, 0, 0, 0))
        else:
            out_data.append(
                (
                    min(255, (r * 255) // a),
                    min(255, (g * 255) // a),
                    min(255, (b * 255) // a),
                    a,
                )
            )
    out = Image.new("RGBA", size)
    out.putdata(out_data)
    return out


def _src_path(name):
    src = os.path.join(SRC, name)
    if os.path.isfile(src):
        return src
    return os.path.join(MEDIA, name)


def make_height_normalized(im):
    """Keep the horizontal gradient; scale only to Skip/Close height."""
    src = _zero_fully_transparent(im.convert("RGBA"))
    sw, sh = src.size
    if sh <= 0:
        raise ValueError("empty texture")
    if sh == OUT_H:
        return src
    return _premul_resize(src, (sw, OUT_H))


def make_template(im):
    src = _zero_fully_transparent(im.convert("RGBA"))
    bbox = _opaque_bbox(src)
    if bbox:
        src = src.crop(bbox)
    sw, sh = src.size
    if sh <= 0:
        raise ValueError("empty texture")
    scaled_w = max(CAP * 2 + 1, int(round(sw * (OUT_H / float(sh)))))
    scaled = _premul_resize(src, (scaled_w, OUT_H))
    left = scaled.crop((0, 0, CAP, OUT_H))
    right = scaled.crop((scaled_w - CAP, 0, scaled_w, OUT_H))
    mid_x = min(max(CAP, scaled_w // 2), scaled_w - CAP - 1)
    mid_col = scaled.crop((mid_x, 0, mid_x + 1, OUT_H))
    middle = mid_col.resize((MID, OUT_H), Image.Resampling.NEAREST)
    out = Image.new("RGBA", (OUT_W, OUT_H), (0, 0, 0, 0))
    out.paste(left, (0, 0))
    out.paste(middle, (CAP, 0))
    out.paste(right, (CAP + MID, 0))
    return out


def main():
    for name in HEIGHT_ONLY_FILES:
        src_path = _src_path(name)
        if not os.path.isfile(src_path):
            print("missing %s" % src_path, file=sys.stderr)
            return 1
        out = make_height_normalized(Image.open(src_path))
        dest = os.path.join(MEDIA, name)
        out.save(dest, "PNG")
        print("wrote height-only %s %sx%s" % (name, out.size[0], out.size[1]))
    for name in NINE_SLICE_FILES:
        src_path = _src_path(name)
        dest = os.path.join(MEDIA, name)
        if not os.path.isfile(src_path):
            print("missing %s" % src_path, file=sys.stderr)
            return 1
        src = Image.open(src_path)
        if src.size == (OUT_W, OUT_H) and src_path == dest:
            print("skip already templated %s" % name)
            continue
        out = make_template(src)
        out.save(dest, "PNG")
        print("wrote %s %sx%s" % (name, out.size[0], out.size[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
