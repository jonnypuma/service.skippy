# -*- coding: utf-8 -*-
"""Author glossy 3D Skip-button and progress-bar textures, then 9-slice the buttons."""
from __future__ import annotations

import math
import os
import sys

from PIL import Image

TOOLS = os.path.dirname(os.path.abspath(__file__))
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

import gen_button_focus_nine_slice as ns

SRC_W = 160
SRC_H = 50
PROGRESS_W = 370
PROGRESS_H = 16

# base, highlight, shadow — colours not already in the 3D set
STYLES = (
    ("cyan", (0, 168, 196), (210, 250, 255), (0, 62, 82)),
    ("silver", (168, 176, 186), (250, 252, 255), (68, 74, 84)),
    ("orange", (232, 118, 28), (255, 220, 150), (128, 44, 6)),
    ("violet", (132, 72, 204), (228, 200, 255), (58, 24, 108)),
    ("graphite", (72, 80, 90), (188, 198, 210), (22, 26, 32)),
    ("ice", (186, 216, 232), (255, 255, 255), (64, 108, 144)),
)


def _lerp(a, b, t):
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def _shade_y(t, base, highlight, shadow):
    """Vertical cylindrical gloss: specular near the top, darker belly."""
    spec = math.exp(-((t - 0.26) ** 2) / (2 * 0.075 ** 2))
    body = _lerp(highlight, base, min(1.0, t * 1.15))
    if t > 0.45:
        body = _lerp(body, shadow, (t - 0.45) / 0.55)
    gloss = _lerp(body, (255, 255, 255), spec * 0.55)
    if t <= 0.06:
        gloss = _lerp(gloss, (255, 255, 255), 0.35 * (1.0 - t / 0.06))
    if t >= 0.92:
        gloss = _lerp(gloss, shadow, (t - 0.92) / 0.08 * 0.45)
    return gloss


def _capsule_cover(x, y, w, h):
    r = (h - 1) / 2.0
    cy = r
    cx_l = r
    cx_r = w - 1 - r
    if x < cx_l:
        d = math.hypot(x - cx_l, y - cy)
    elif x > cx_r:
        d = math.hypot(x - cx_r, y - cy)
    else:
        d = abs(y - cy)
    return r + 0.65 - d, r


def draw_glossy_pill(w, h, base, highlight, shadow):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = im.load()
    denom = max(1, h - 1)
    for y in range(h):
        t = y / float(denom)
        col = _shade_y(t, base, highlight, shadow)
        for x in range(w):
            cover, radius = _capsule_cover(x, y, w, h)
            if cover <= 0:
                continue
            a = 255 if cover >= 1 else int(round(255 * cover))
            edge = 0.0
            # cover = radius+0.65 - d  => d = radius+0.65-cover
            d = radius + 0.65 - cover
            if d > radius - 2.4:
                edge = min(1.0, (d - (radius - 2.4)) / 2.4)
            rgb = _lerp(col, shadow, edge * 0.5)
            px[x, y] = (rgb[0], rgb[1], rgb[2], a)
    return im


def draw_glossy_bar(w, h, base, highlight, shadow):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = im.load()
    denom = max(1, h - 1)
    for y in range(h):
        t = y / float(denom)
        col = _shade_y(t, base, highlight, shadow)
        row = (col[0], col[1], col[2], 255)
        for x in range(w):
            px[x, y] = row
    return im


def main():
    os.makedirs(ns.SRC, exist_ok=True)
    for key, base, highlight, shadow in STYLES:
        btn_name = "button_focus_3d_%s.png" % key
        src = draw_glossy_pill(SRC_W, SRC_H, base, highlight, shadow)
        src_path = os.path.join(ns.SRC, btn_name)
        src.save(src_path, "PNG")
        templated = ns.make_template(src)
        dest = os.path.join(ns.MEDIA, btn_name)
        templated.save(dest, "PNG")
        print("wrote %s %sx%s (src %sx%s)" % (btn_name, templated.size[0], templated.size[1], SRC_W, SRC_H))

        bar_name = "progress_mid_3d_%s.png" % key
        bar = draw_glossy_bar(PROGRESS_W, PROGRESS_H, base, highlight, shadow)
        bar_path = os.path.join(ns.MEDIA, bar_name)
        bar.save(bar_path, "PNG")
        print("wrote %s %sx%s" % (bar_name, bar.size[0], bar.size[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
