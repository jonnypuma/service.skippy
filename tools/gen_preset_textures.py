# -*- coding: utf-8 -*-
"""Author the flat / matte / glass textures used by the Skip dialog presets.

Run from the add-on root::

    python tools/gen_preset_textures.py

Writes into ``resources/skins/default/media``:

* ``button_focus_flat_*``, ``_glass_*``, ``_outline_*``, ``_underline_*`` -
  128x50 (2x of the 64x25 Skip button art) so edges stay crisp at 1080i.
  Pills are 9-slice: Kodi ``border="12,12,12,12"`` (see
  ``BUTTON_FOCUS_NINE_SLICE_BORDERS`` in ``skip_dialog_appearance.py``).
  Underlines have no border (uniform along the width, stretched whole).
* ``progress_mid_flat_*`` / ``progress_mid_grad_*`` - 512x32 flat bars.
* ``button_focus_frosted_/steel/neon_/gold/pastel_/bracket_*`` - second batch
  (frosted glass, brushed steel, neon glow, gold leaf, pastel, corner brackets),
  same 64x25 / 12-px 9-slice rules as above.
* ``progress_mid_segmented_/glow_/striped_/grad_gold`` - second batch of bars.
* ``minimal_pastel_/steel/frosted/gold/neon_*`` - second batch of Minimal plates.
* ``minimal_flat_*`` / ``_glass_*`` / ``_outline_*`` / ``_grad_*`` - 640x246
  pill plates for Minimal mode. The plate is drawn twice (image + focus
  overlay) so translucent plates are authored at about half the target alpha.

Everything is drawn 4x supersampled and downscaled for smooth edges.
"""
from __future__ import annotations

import math
import os
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MEDIA = os.path.join(ROOT, "resources", "skins", "default", "media")
SS = 4

BTN_W, BTN_H, BTN_CAP = 64, 25, 12
BAR_W, BAR_H = 512, 32
PLATE_W, PLATE_H = 640, 246

PALETTE = {
    "blue": (59, 130, 246),
    "teal": (20, 184, 166),
    "green": (34, 197, 94),
    "rose": (244, 63, 94),
    "orange": (249, 115, 22),
    "violet": (139, 92, 246),
    "slate": (71, 85, 105),
    "white": (248, 250, 252),
}
CYAN = (34, 211, 238)
GRADIENTS = {
    "ocean": ((59, 130, 246), (20, 184, 166)),
    "aurora": ((20, 184, 166), (139, 92, 246)),
    "sunset": ((249, 115, 22), (244, 63, 94)),
}

BUTTON_BORDERED = []  # filenames that need a 9-slice border entry
BUTTON_FILES = []
PROGRESS_FILES = []
PLATE_FILES = []


def _canvas(w, h):
    return Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))


def _down(im, w, h):
    return im.resize((w, h), Image.LANCZOS)


def _pill_mask(w, h, inset=0.0):
    """Capsule mask at SSx size; ``inset`` in final pixels."""
    m = Image.new("L", (w * SS, h * SS), 0)
    d = ImageDraw.Draw(m)
    i = inset * SS
    d.rounded_rectangle(
        [i, i, w * SS - 1 - i, h * SS - 1 - i], radius=(h * SS - 2 * i) / 2.0, fill=255
    )
    return m


def _vgrad(w, h, top, bottom):
    """RGBA vertical gradient at SSx size; colours are RGBA tuples."""
    g = Image.new("RGBA", (w * SS, h * SS))
    px = g.load()
    for y in range(h * SS):
        t = y / max(1, h * SS - 1)
        c = tuple(int(round(top[i] + (bottom[i] - top[i]) * t)) for i in range(4))
        for x in range(w * SS):
            px[x, y] = c
    return g


def _hgrad(w, h, left, right, diagonal=0.0):
    g = Image.new("RGBA", (w * SS, h * SS))
    px = g.load()
    W, H = w * SS, h * SS
    for x in range(W):
        for y in range(H):
            t = (x + diagonal * y) / max(1.0, W - 1 + diagonal * (H - 1))
            c = tuple(int(round(left[i] + (right[i] - left[i]) * t)) for i in range(3))
            px[x, y] = (c[0], c[1], c[2], 255)
    return g


def _solid(w, h, rgba):
    return Image.new("RGBA", (w * SS, h * SS), rgba)


def _compose(fill, mask):
    out = Image.new("RGBA", fill.size, (0, 0, 0, 0))
    out.paste(fill, (0, 0), mask)
    return out


def _ring(w, h, rgba, stroke):
    outer = _pill_mask(w, h, 0.0)
    inner = _pill_mask(w, h, stroke)
    ring = Image.new("L", outer.size, 0)
    ring.paste(outer, (0, 0))
    ring.paste(0, (0, 0), inner)
    return _compose(_solid(w, h, rgba), ring)


def _over(base, top):
    base.alpha_composite(top)
    return base


def _glass(w, h, tint, a_top, a_bot, border_rgba, stroke):
    fill = _vgrad(
        w, h, tint + (int(255 * a_top),), tint + (int(255 * a_bot),)
    )
    body = _compose(fill, _pill_mask(w, h))
    return _over(body, _ring(w, h, border_rgba, stroke))


# ------------------------------------------------------- second batch helpers
def _lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(len(a)))


def _stops_vgrad(w, h, stops, grain=0.0, seed=1, streak=0.0):
    """Vertical multi-stop RGBA gradient at SS size with optional brushed grain.

    ``stops`` is ``[(t, (r, g, b, a)), ...]``; ``grain`` adds a per-row brightness
    jitter (same across x, so it survives 9-slice stretching); ``streak`` adds slow
    horizontal variation per row for wide plates.
    """
    rng = random.Random(seed)
    W, H = w * SS, h * SS
    img = Image.new("RGBA", (W, H))
    px = img.load()
    for y in range(H):
        t = y / max(1, H - 1)
        for i in range(len(stops) - 1):
            if stops[i][0] <= t <= stops[i + 1][0]:
                k = (t - stops[i][0]) / max(1e-6, stops[i + 1][0] - stops[i][0])
                base = _lerp(stops[i][1], stops[i + 1][1], k)
                break
        else:
            base = stops[-1][1]
        j = rng.uniform(-grain, grain)
        phase = rng.uniform(0, 6.28)
        for x in range(W):
            d = j + (streak * math.sin(x / (W / 9.0) + phase) if streak else 0.0)
            px[x, y] = (
                max(0, min(255, int(base[0] + d))),
                max(0, min(255, int(base[1] + d))),
                max(0, min(255, int(base[2] + d))),
                base[3],
            )
    return img


def _glow_ring(w, h, rgb, stroke, inset, blur, glow_alpha=0.85, ring_rgb=None):
    """Capsule ring with a soft outer glow, fully inside the canvas."""
    ring = _ring_mask(w, h, inset, stroke)
    ring_img = _compose(_solid(w, h, (ring_rgb or rgb) + (255,)), ring)
    glow_mask = ring.filter(ImageFilter.GaussianBlur(blur * SS))
    glow_mask = glow_mask.point(lambda v: min(255, int(v * 5.0 * glow_alpha)))
    glow = _compose(_solid(w, h, rgb + (255,)), glow_mask)
    return _over(glow, ring_img)


def _ring_mask(w, h, inset, stroke):
    outer = _pill_mask(w, h, inset)
    inner = _pill_mask(w, h, inset + stroke)
    m = Image.new("L", outer.size, 0)
    m.paste(outer, (0, 0))
    m.paste(0, (0, 0), inner)
    return m


def _rim(w, h, rgba, stroke, inset=0.0):
    return _compose(_solid(w, h, rgba), _ring_mask(w, h, inset, stroke))


def _shape_with_rim(w, h, fill_img, rim_rgba, stroke):
    body = _compose(fill_img, _pill_mask(w, h))
    return _over(body, _rim(w, h, rim_rgba, stroke))


# ----------------------------------------------------------------- buttons
def _save_button(name, im, bordered=True):
    path = os.path.join(MEDIA, name)
    _down(im, BTN_W, BTN_H).save(path, "PNG")
    BUTTON_FILES.append(name)
    if bordered:
        BUTTON_BORDERED.append(name)
    print("wrote", name)


def make_buttons():
    for key, rgb in PALETTE.items():
        im = _compose(_solid(BTN_W, BTN_H, rgb + (255,)), _pill_mask(BTN_W, BTN_H))
        _save_button("button_focus_flat_%s.png" % key, im)
    _save_button(
        "button_focus_glass_white.png",
        _glass(BTN_W, BTN_H, (255, 255, 255), 0.34, 0.16, (255, 255, 255, 150), 2.0),
    )
    _save_button(
        "button_focus_glass_blue.png",
        _glass(BTN_W, BTN_H, (59, 130, 246), 0.55, 0.32, (147, 197, 253, 190), 2.0),
    )
    _save_button(
        "button_focus_glass_dark.png",
        _glass(BTN_W, BTN_H, (8, 10, 16), 0.62, 0.46, (255, 255, 255, 70), 2.0),
    )
    _save_button(
        "button_focus_outline_white.png",
        _ring(BTN_W, BTN_H, (255, 255, 255, 245), 2.2),
    )
    _save_button(
        "button_focus_outline_cyan.png",
        _ring(BTN_W, BTN_H, CYAN + (255,), 2.2),
    )
    for key, rgb in (("white", (255, 255, 255)), ("cyan", CYAN)):
        im = _vgrad(BTN_W, BTN_H, rgb + (0,), rgb + (46,))
        bar = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(bar).rectangle(
            [0, (BTN_H - 5) * SS, BTN_W * SS, BTN_H * SS], fill=rgb + (255,)
        )
        im.alpha_composite(bar)
        _save_button("button_focus_underline_%s.png" % key, im, bordered=False)


def make_buttons2():
    w, h = BTN_W, BTN_H
    # Frosted: milky translucent white with a bright rim and a faint top highlight.
    fill = _vgrad(w, h, (255, 255, 255, 120), (255, 255, 255, 62))
    im = _shape_with_rim(w, h, fill, (255, 255, 255, 215), 1.6)
    hi = _compose(_vgrad(w, h, (255, 255, 255, 70), (255, 255, 255, 0)), _pill_mask(w, h, 2.4))
    _save_button("button_focus_frosted_white.png", _over(im, hi))
    # Brushed steel: grey gradient with horizontal grain and a darker rim.
    steel = _stops_vgrad(
        w, h, [(0, (172, 180, 192, 255)), (0.45, (118, 126, 138, 255)), (1, (82, 90, 102, 255))],
        grain=9, seed=7,
    )
    _save_button("button_focus_steel.png", _shape_with_rim(w, h, steel, (40, 46, 56, 230), 1.4))
    # Neon glow rings.
    for key, rgb in (("cyan", CYAN), ("magenta", (232, 121, 249))):
        _save_button(
            "button_focus_neon_%s.png" % key,
            _glow_ring(w, h, rgb, stroke=1.2, inset=0.6, blur=1.1, ring_rgb=_lerp(rgb, (255, 255, 255), 0.55)),
        )
    # Gold leaf.
    gold = _stops_vgrad(
        w, h, [(0, (236, 190, 84, 255)), (0.5, (205, 150, 40, 255)), (1, (150, 100, 16, 255))],
        grain=4, seed=11,
    )
    _save_button("button_focus_gold.png", _shape_with_rim(w, h, gold, (255, 232, 164, 235), 1.4))
    # Pastel pills (use with dark text).
    for key, rgb in (("mint", (167, 243, 208)), ("peach", (254, 215, 170)), ("lavender", (221, 214, 254))):
        dark = _lerp(rgb, (0, 0, 0), 0.35)
        top = _lerp(rgb, (255, 255, 255), 0.35) + (255,)
        fill = _vgrad(w, h, top, rgb + (255,))
        _save_button(
            "button_focus_pastel_%s.png" % key, _shape_with_rim(w, h, fill, dark + (150,), 1.2)
        )
    # Corner brackets: only the four corners (<= the 12-px 9-slice border) are drawn,
    # so the edges stay open at any button width; a faint fill keeps it tappable.
    for key, rgb in (("white", (255, 255, 255)), ("cyan", CYAN), ("green", (74, 222, 128))):
        im = _canvas(w, h)
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, w * SS - 1, h * SS - 1], fill=rgb + (30,))
        t, arm, o = 2.4 * SS, 10 * SS, 1.0 * SS
        W, H = w * SS, h * SS
        for cx, cy, sx, sy in ((o, o, 1, 1), (W - o, o, -1, 1), (o, H - o, 1, -1), (W - o, H - o, -1, -1)):
            d.rectangle(sorted_box(cx, cy, cx + sx * arm, cy + sy * t), fill=rgb + (255,))
            d.rectangle(sorted_box(cx, cy, cx + sx * t, cy + sy * arm), fill=rgb + (255,))
        _save_button("button_focus_bracket_%s.png" % key, im)


def sorted_box(x0, y0, x1, y1):
    return [min(x0, x1), min(y0, y1), max(x0, x1) - 1, max(y0, y1) - 1]


# ---------------------------------------------------------------- progress
def make_progress():
    for key, rgb in PALETTE.items():
        name = "progress_mid_flat_%s.png" % key
        Image.new("RGBA", (BAR_W, BAR_H), rgb + (255,)).save(os.path.join(MEDIA, name), "PNG")
        PROGRESS_FILES.append(name)
        print("wrote", name)
    for key, (a, b) in GRADIENTS.items():
        name = "progress_mid_grad_%s.png" % key
        g = _hgrad(BAR_W, BAR_H, a, b)
        _down(g, BAR_W, BAR_H).save(os.path.join(MEDIA, name), "PNG")
        PROGRESS_FILES.append(name)
        print("wrote", name)


def _save_bar(name, im):
    im.save(os.path.join(MEDIA, name), "PNG")
    PROGRESS_FILES.append(name)
    print("wrote", name)


def make_progress2():
    # Segmented blocks: 32 cells of 16 px, 3 px gaps.
    for key, rgb in (("white", (248, 250, 252)), ("teal", PALETTE["teal"]), ("green", (74, 222, 128))):
        im = Image.new("RGBA", (BAR_W, BAR_H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        for i in range(BAR_W // 16):
            d.rectangle([i * 16, 0, i * 16 + 12, BAR_H - 1], fill=rgb + (255,))
        _save_bar("progress_mid_segmented_%s.png" % key, im)
    # Glow line: bright core with a soft halo above and below.
    for key, rgb in (("cyan", CYAN), ("magenta", (232, 121, 249))):
        im = Image.new("RGBA", (BAR_W, BAR_H), (0, 0, 0, 0))
        px = im.load()
        core = _lerp(rgb, (255, 255, 255), 0.6)
        for y in range(BAR_H):
            dist = abs((y + 0.5) - BAR_H / 2.0)
            if dist <= 5:
                c, a = core, 255
            else:
                c, a = rgb, int(235 * math.exp(-(((dist - 5) / 6.5) ** 2)))
            for x in range(BAR_W):
                px[x, y] = c + (a,)
        _save_bar("progress_mid_glow_%s.png" % key, im)
    # Diagonal stripes (matte, two tones).
    for key, (a, b) in (
        ("blue", ((59, 130, 246), (37, 99, 235))),
        ("orange", ((249, 115, 22), (234, 88, 12))),
    ):
        im = Image.new("RGBA", (BAR_W, BAR_H))
        px = im.load()
        for y in range(BAR_H):
            for x in range(BAR_W):
                px[x, y] = (a if ((x + y) // 12) % 2 == 0 else b) + (255,)
        _save_bar("progress_mid_striped_%s.png" % key, im)
    g = _hgrad(BAR_W, BAR_H, (250, 204, 21), (217, 119, 6))
    _save_bar("progress_mid_grad_gold.png", _down(g, BAR_W, BAR_H))


# ------------------------------------------------------------------ plates
def _save_plate(name, im):
    _down(im, PLATE_W, PLATE_H).save(os.path.join(MEDIA, name), "PNG")
    PLATE_FILES.append(name)
    print("wrote", name)


def make_plates():
    mask = _pill_mask(PLATE_W, PLATE_H)
    flats = {
        "black": (10, 11, 15, 235),
        "charcoal": (31, 41, 55, 242),
        "white": (248, 250, 252, 248),
        "blue": PALETTE["blue"] + (255,),
        "teal": PALETTE["teal"] + (255,),
        "rose": PALETTE["rose"] + (255,),
    }
    for key, rgba in flats.items():
        _save_plate(
            "minimal_flat_%s_640.png" % key, _compose(_solid(PLATE_W, PLATE_H, rgba), mask)
        )
    # Plates are drawn twice (image + focus overlay): author at ~half alpha.
    _save_plate(
        "minimal_glass_dark_640.png",
        _glass(PLATE_W, PLATE_H, (8, 10, 16), 0.36, 0.26, (255, 255, 255, 60), 5.0),
    )
    _save_plate(
        "minimal_glass_light_640.png",
        _glass(PLATE_W, PLATE_H, (255, 255, 255), 0.22, 0.10, (255, 255, 255, 110), 5.0),
    )
    _save_plate(
        "minimal_outline_white_640.png",
        _ring(PLATE_W, PLATE_H, (255, 255, 255, 235), 7.0),
    )
    for key, (a, b) in (
        ("midnight", ((30, 27, 75), (109, 40, 217))),
        ("sunset", ((249, 115, 22), (236, 72, 153))),
    ):
        g = _hgrad(PLATE_W, PLATE_H, a, b, diagonal=0.6)
        _save_plate("minimal_grad_%s_640.png" % key, _compose(g, mask))


def make_plates2():
    w, h = PLATE_W, PLATE_H
    mask = _pill_mask(w, h)
    for key, rgb in (("mint", (167, 243, 208)), ("peach", (254, 215, 170)), ("lavender", (221, 214, 254))):
        fill = _vgrad(w, h, _lerp(rgb, (255, 255, 255), 0.3) + (255,), rgb + (255,))
        _save_plate(
            "minimal_pastel_%s_640.png" % key,
            _shape_with_rim(w, h, fill, _lerp(rgb, (0, 0, 0), 0.3) + (140,), 4.0),
        )
    steel = _stops_vgrad(
        w, h, [(0, (150, 158, 170, 255)), (0.5, (104, 112, 124, 255)), (1, (70, 78, 90, 255))],
        grain=8, seed=3, streak=6,
    )
    _save_plate("minimal_steel_640.png", _shape_with_rim(w, h, steel, (36, 42, 52, 235), 4.0))
    gold = _stops_vgrad(
        w, h, [(0, (232, 186, 80, 255)), (0.5, (200, 146, 38, 255)), (1, (146, 98, 16, 255))],
        grain=3, seed=5, streak=3,
    )
    _save_plate("minimal_gold_640.png", _shape_with_rim(w, h, gold, (255, 232, 164, 235), 4.0))
    # Plates are drawn twice (image + focus overlay): author at ~half alpha.
    fill = _vgrad(w, h, (255, 255, 255, 62), (255, 255, 255, 30))
    frosted = _shape_with_rim(w, h, fill, (255, 255, 255, 110), 4.0)
    hi = _compose(_vgrad(w, h, (255, 255, 255, 36), (255, 255, 255, 0)), _pill_mask(w, h, 8.0))
    _save_plate("minimal_frosted_640.png", _over(frosted, hi))
    _save_plate(
        "minimal_neon_cyan_640.png",
        _glow_ring(w, h, CYAN, stroke=6.0, inset=10.0, blur=8.0, glow_alpha=0.7,
                   ring_rgb=_lerp(CYAN, (255, 255, 255), 0.55)),
    )


def main():
    os.makedirs(MEDIA, exist_ok=True)
    make_buttons()
    make_buttons2()
    make_progress()
    make_progress2()
    make_plates()
    make_plates2()
    print("\nBUTTON_FILES = %r" % (BUTTON_FILES,))
    print("BORDERED = %r" % (BUTTON_BORDERED,))
    print("PROGRESS_FILES = %r" % (PROGRESS_FILES,))
    print("PLATE_FILES = %r" % (PLATE_FILES,))


if __name__ == "__main__":
    main()
