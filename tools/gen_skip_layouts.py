# -*- coding: utf-8 -*-
"""Write the skip dialog layouts besides the classic card: their skin files and their pictures.

    python tools/gen_skip_layouts.py            (write what is missing or changed)
    python tools/gen_skip_layouts.py --check    (exit 1 when a file is missing or differs)

Skin files: ``SkipLayout_<name>.xml`` and ``SkipLayout_<name>Compact.xml`` for every layout of
``skip_layouts.py``, in ``720p`` (the source of truth) and ``1080i`` (through
``gen_skin_1080i.convert()``; only the nine-slice border of the button pictures differs, because
a pill needs a border of half the button's height in each folder). A file holds no text, colour
or picture of a look: all of it comes from the ``skl_*`` window properties that
``skip_layout_dialog.py`` sets.

Pictures, in ``resources/skins/default/media``: per look ``sl_<look>_plate`` / ``_slab`` (the
plate with hard corners) / ``_tile`` (a focused tile), ``_button_<720|1080>`` and
``_focus_<720|1080>``; and for all looks the ring ``sl_ring_00`` .. ``sl_ring_50``, the soft shade
``sl_shade`` and the screen-wide bands ``sl_band`` / ``sl_band_top``.
"""
from __future__ import annotations

import io
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFilter

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
for _path in (ROOT, TOOLS):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import gen_fuse_preset_textures as fuse  # noqa: E402
import gen_modal_style_textures as window_looks  # noqa: E402
import gen_skin_1080i as gen  # noqa: E402
import skip_layouts as sl  # noqa: E402

SKINS = os.path.join(ROOT, "resources", "skins", "default")
MEDIA = os.path.join(SKINS, "media")
P = "$INFO[Window.Property(%s)]"
BH = sl.BUTTON_H
WHITE = (255, 255, 255, 255)

# ------------------------------------------------------------------------------- pictures
# plate fill, plate edge, plate radius, button fill, button edge, focus fill, focus edge, button radius at 1080
_WL = window_looks.LOOKS
PAINT = {
    "fgd": (_WL["fgd"]["panel"], _WL["fgd"]["panel_edge"], 20, (255, 255, 255, 31), None, WHITE, None, 21),
    "fgf": (_WL["fgf"]["panel"], _WL["fgf"]["panel_edge"], 20, (255, 255, 255, 48), None, WHITE, None, 21),
    "fgc": (_WL["fgc"]["panel"], _WL["fgc"]["panel_edge"], 20, (255, 255, 255, 43), None, WHITE, None, 21),
    "fgs": ((7, 8, 10, 194), (255, 255, 255, 71), 0, (255, 255, 255, 0), (255, 255, 255, 71),
            (255, 255, 255, 28), (255, 255, 255, 71), 0),
    "aeo": ((12, 12, 12, 237), None, 0, (255, 255, 255, 23), None, WHITE, None, 0),
    "agl": (_WL["agl"]["panel"], _WL["agl"]["panel_edge"], 16, (255, 255, 255, 18), (255, 255, 255, 46),
            (255, 255, 255, 69), (255, 255, 255, 194), 8),
}
RING_SIZE, RING_STROKE = 192, 14


def ring(share) -> Image.Image:
    """A white ring filled clockwise from the top for ``share`` (0-1), with round ends."""
    scale = 4
    big = RING_SIZE * scale
    stroke = RING_STROKE * scale
    layer = Image.new("L", (big, big), 0)
    draw = ImageDraw.Draw(layer)
    box = (0, 0, big - 1, big - 1)  # Pillow draws the stroke inside the box
    if share >= 1.0:
        draw.ellipse(box, outline=255, width=stroke)
    elif share > 0.0:
        draw.arc(box, -90, -90 + 360.0 * share, fill=255, width=stroke)
        radius = (big - stroke) / 2.0
        for angle in (-90.0, -90.0 + 360.0 * share):
            x = big / 2.0 + radius * math.cos(math.radians(angle))
            y = big / 2.0 + radius * math.sin(math.radians(angle))
            draw.ellipse((x - stroke / 2.0, y - stroke / 2.0, x + stroke / 2.0, y + stroke / 2.0), fill=255)
    alpha = layer.resize((RING_SIZE, RING_SIZE), Image.LANCZOS)
    out = Image.new("RGBA", (RING_SIZE, RING_SIZE), (255, 255, 255, 0))
    out.putalpha(alpha)
    return out


def shade() -> Image.Image:
    """A soft dark rounded shade for the layouts that have no plate (nine-slice border 40)."""
    size, pad = 160, 22
    alpha = Image.new("L", (size, size), 0)
    ImageDraw.Draw(alpha).rounded_rectangle((pad, pad, size - 1 - pad, size - 1 - pad), radius=26, fill=150)
    alpha = alpha.filter(ImageFilter.GaussianBlur(11))
    out = Image.new("RGBA", (size, size), (6, 8, 12, 0))
    out.putalpha(alpha)
    return out


def band_picture(top=False) -> Image.Image:
    """A screen-wide band: clear at the far edge, dark at the screen edge."""
    width, height = 8, 150
    out = Image.new("RGBA", (width, height), (4, 5, 8, 0))
    pixels = out.load()
    for y in range(height):
        share = (y / float(height - 1)) ** 1.6
        for x in range(width):
            pixels[x, y] = (4, 5, 8, int(round(224 * share)))
    return out.transpose(Image.FLIP_TOP_BOTTOM) if top else out


# ---------------------------------------------------------------- the looks of their own
# A richer painter than ``fuse.shape``: gradients, a glow inside the edge, a bevel, a second frame.
SS = 4
CLEAR = (255, 255, 255, 0)


def gradient(width, height, angle, stops) -> Image.Image:
    """A linear gradient as CSS draws it: ``angle`` in degrees (180 runs top to bottom, 135 towards
    the bottom right), ``stops`` as ``[(position 0-1, (r, g, b, a))]``."""
    small_w, small_h = 48, 48
    out = Image.new("RGBA", (small_w, small_h))
    pixels = out.load()
    sin, cos = math.sin(math.radians(angle)), math.cos(math.radians(angle))
    reach = abs(width * sin) + abs(height * cos)
    for py in range(small_h):
        for px in range(small_w):
            x = (px + 0.5) / small_w * width - width / 2.0
            y = (py + 0.5) / small_h * height - height / 2.0
            t = max(0.0, min(1.0, (x * sin - y * cos) / reach + 0.5))
            for index in range(len(stops) - 1):
                (p0, c0), (p1, c1) = stops[index], stops[index + 1]
                if t <= p1 or index == len(stops) - 2:
                    share = 0.0 if p1 <= p0 else max(0.0, min(1.0, (t - p0) / (p1 - p0)))
                    pixels[px, py] = tuple(int(round(c0[i] + (c1[i] - c0[i]) * share)) for i in range(4))
                    break
    return out.resize((width, height), Image.BILINEAR)


def rich(width, height, radius, fill=CLEAR, edge=None, stroke=1.0, grad=None, glow=None, hi=0, lo=None, frame=None):
    """A rounded rectangle. ``grad``: (angle, stops) in place of ``fill``. ``glow``: (rgb, alpha, reach)
    inside the edge. ``hi``: alpha of a white line under the top edge. ``lo``: (alpha, height) of a dark
    line above the bottom edge. ``frame``: (inset, rgba, stroke), a second outline inside."""
    big_w, big_h = width * SS, height * SS

    def mask(inset, r):
        layer = Image.new("L", (big_w, big_h), 0)
        if big_w - 1 - inset > inset and big_h - 1 - inset > inset:
            ImageDraw.Draw(layer).rounded_rectangle(
                (inset, inset, big_w - 1 - inset, big_h - 1 - inset), radius=max(0.0, r) * SS, fill=255)
        return layer

    outline = mask(0, radius)
    inset = int(round(stroke * SS)) if edge else 0
    inner = mask(inset, radius - (stroke if edge else 0))
    body = gradient(big_w, big_h, grad[0], grad[1]) if grad else Image.new("RGBA", (big_w, big_h), fill)
    if glow:
        rgb, alpha, reach = glow
        soft = inner.filter(ImageFilter.GaussianBlur(reach * SS / 2.0))
        light = Image.new("RGBA", (big_w, big_h), tuple(rgb) + (0,))
        light.putalpha(soft.point(lambda v: int((255 - v) * alpha / 255.0)))
        body = Image.alpha_composite(body, light)
    if hi or lo:
        rim = Image.new("RGBA", (big_w, big_h), (0, 0, 0, 0))
        if hi:
            moved = Image.new("L", (big_w, big_h), 0)
            moved.paste(inner, (0, SS))
            top = Image.composite(Image.new("L", (big_w, big_h), hi), Image.new("L", (big_w, big_h), 0),
                                  Image.eval(moved, lambda v: 255 - v))
            white = Image.new("RGBA", (big_w, big_h), (255, 255, 255, 0))
            white.putalpha(top)
            rim = Image.alpha_composite(rim, white)
        if lo:
            moved = Image.new("L", (big_w, big_h), 0)
            moved.paste(inner, (0, -int(lo[1] * SS)))
            low = Image.composite(Image.new("L", (big_w, big_h), lo[0]), Image.new("L", (big_w, big_h), 0),
                                  Image.eval(moved, lambda v: 255 - v))
            dark = Image.new("RGBA", (big_w, big_h), (0, 0, 0, 0))
            dark.putalpha(low)
            rim = Image.alpha_composite(rim, dark)
        body = Image.alpha_composite(body, rim)
    if frame:
        gap, colour, width_ = frame
        ring_ = mask(int(gap * SS), radius - gap)
        hole = mask(int((gap + width_) * SS), radius - gap - width_)
        ring_ = Image.composite(Image.new("L", (big_w, big_h), 0), ring_, hole)
        line = Image.new("RGBA", (big_w, big_h), colour[:3] + (0,))
        line.putalpha(ring_.point(lambda v: int(v * colour[3] / 255.0)))
        body = Image.alpha_composite(body, line)
    layer = Image.new("RGBA", (big_w, big_h), (0, 0, 0, 0))
    if edge:
        layer.paste(Image.new("RGBA", (big_w, big_h), edge), (0, 0), outline)
    layer.paste(body, (0, 0), inner)
    return layer.resize((width, height), Image.LANCZOS)


def _rgb(text, alpha=255):
    return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16), alpha)


# per look: plate radius, button radius at 1080 (21 = a pill), then what paints the plate, a button
# and the button with the focus. Sizes are 1080 pixels; the 720 pictures take two thirds.
OWN = {
    "neon": (8, 4,
             dict(fill=(8, 5, 22, 189), edge=_rgb("39F0FF"), stroke=2, glow=((57, 240, 255), 70, 12)),
             dict(fill=(255, 70, 225, 20), edge=_rgb("FF46E1", 191), stroke=2),
             dict(fill=_rgb("39F0FF"), glow=((255, 255, 255), 70, 5))),
    "paper": (20, 12,
              dict(fill=_rgb("F4EFE6"), edge=(0, 0, 0, 26)),
              dict(fill=(28, 26, 22, 22)),
              dict(fill=_rgb("1C1A16"))),
    "sunset": (20, 21,
               dict(grad=(135, [(0.0, _rgb("FF9A3D")), (0.55, _rgb("E8457A")), (1.0, _rgb("8A3FFC"))]),
                    edge=(255, 255, 255, 71)),
               dict(fill=(255, 255, 255, 51)),
               dict(fill=WHITE)),
    "ocean": (20, 21,
              dict(grad=(140, [(0.0, _rgb("10C0B0")), (0.58, _rgb("2563EB")), (1.0, _rgb("3B1D8F"))]),
                   edge=(255, 255, 255, 66)),
              dict(fill=(255, 255, 255, 46)),
              dict(fill=WHITE)),
    "brutal": (0, 0,
               dict(fill=_rgb("FFDE21"), edge=_rgb("000000"), stroke=5),
               dict(fill=_rgb("FFDE21"), edge=_rgb("000000"), stroke=4),
               dict(fill=_rgb("000000"))),
    "term": (0, 0,
             dict(fill=(0, 12, 5, 235), edge=_rgb("37FF8B"), stroke=1.5),
             dict(fill=(55, 255, 139, 0), edge=_rgb("37FF8B", 128), stroke=1.5),
             dict(fill=_rgb("37FF8B"))),
    "line": (20, 21,
             dict(fill=(255, 255, 255, 0), edge=WHITE, stroke=2),
             dict(fill=(255, 255, 255, 0), edge=(255, 255, 255, 191), stroke=2),
             dict(fill=WHITE)),
    "luxe": (3, 0,
             dict(fill=(11, 10, 8, 242), edge=_rgb("C9A45C"), stroke=1.5, frame=(7, _rgb("C9A45C", 140), 1)),
             dict(fill=(201, 164, 92, 0), edge=_rgb("C9A45C", 140), stroke=1.5),
             dict(fill=_rgb("C9A45C"))),
    "pastel": (20, 21,
               dict(fill=_rgb("ECE8FF"), edge=(255, 255, 255, 178), stroke=1.5),
               dict(fill=(42, 37, 80, 24)),
               dict(fill=_rgb("7C6CF2"))),
    "gloss": (20, 14,
              dict(grad=(180, [(0.0, _rgb("414755")), (1.0, _rgb("181B21"))]), edge=(0, 0, 0, 153), hi=77, lo=(102, 3)),
              dict(grad=(180, [(0.0, _rgb("525967")), (1.0, _rgb("2B2F38"))]), edge=(0, 0, 0, 153), hi=72, lo=(110, 2)),
              dict(grad=(180, [(0.0, _rgb("6DBCFF")), (1.0, _rgb("1B6FE0"))]), edge=_rgb("0C3F86"), hi=140, lo=(120, 3))),
    "mono": (0, 0,
             dict(fill=_rgb("000000"), edge=WHITE, stroke=3),
             dict(fill=_rgb("000000"), edge=WHITE, stroke=3),
             dict(fill=WHITE)),
    "vhs": (0, 0,
            dict(fill=(0, 0, 40, 140)),
            dict(fill=(255, 255, 255, 0), edge=(255, 255, 255, 128), stroke=1.5),
            dict(fill=WHITE)),
    # the twins on the video: only buttons, the plate is the look's own
    "paper_o": (20, 12, None, dict(fill=(244, 239, 230, 46)), dict(fill=_rgb("F4EFE6"))),
    "brutal_o": (0, 0, None, dict(fill=_rgb("FFDE21"), edge=_rgb("000000"), stroke=4),
                 dict(fill=_rgb("000000"), edge=_rgb("FFDE21"), stroke=4)),
    "pastel_o": (20, 21, None, dict(fill=(236, 232, 255, 46)), dict(fill=_rgb("7C6CF2"))),
}


def _scaled(spec, share):
    """A paint for a smaller picture: strokes, glows, bevels and frames shrink with it."""
    out = dict(spec)
    if "stroke" in out:
        out["stroke"] = out["stroke"] * share
    if "glow" in out:
        out["glow"] = (out["glow"][0], out["glow"][1], out["glow"][2] * share)
    if "lo" in out:
        out["lo"] = (out["lo"][0], out["lo"][1] * share)
    if "frame" in out:
        out["frame"] = (out["frame"][0] * share, out["frame"][1], out["frame"][2])
    return out


def own_pictures() -> dict:
    out = {}
    for code, (plate_r, button_r, plate, button, focus) in OWN.items():
        if plate:
            out["sl_%s_plate.png" % code] = rich(96, 96, plate_r, **plate)
            out["sl_%s_slab.png" % code] = rich(96, 96, 0, **plate)
            tile = dict(focus)
            tile.pop("glow", None)
            out["sl_%s_tile.png" % code] = rich(96, 96, plate_r, **tile)
        for folder, width, height, share in (("720", 64, BH, 2.0 / 3.0), ("1080", 96, BH * 3 // 2, 1.0)):
            r = height / 2.0 if button_r >= 21 else button_r * share
            out["sl_%s_button_%s.png" % (code, folder)] = rich(width, height, r, **_scaled(button, share))
            out["sl_%s_focus_%s.png" % (code, folder)] = rich(width, height, r, **_scaled(focus, share))
    return out


SHADE = (6, 8, 12, 184)  # the tint of every background overlay


def overlay_pictures() -> dict:
    """The shades that can lie behind a layout (``skip_layouts.overlay_box`` picks one and its box)."""
    out = {"ov_square.png": Image.new("RGBA", (8, 8), SHADE)}
    round_ = rich(96, 96, sl.OVERLAY_BORDER, fill=SHADE)
    out["ov_round.png"] = round_
    fading = round_.copy()
    alpha = fading.getchannel("A").load()
    for y in range(96):
        for x in range(96):
            alpha[x, y] = int(alpha[x, y] * (0.3 + 0.7 * (x + y) / 190.0))
    fading.putalpha(Image.frombytes("L", (96, 96), bytes(alpha[x, y] for y in range(96) for x in range(96))))
    out["ov_round_fade.png"] = fading
    fade = Image.new("RGBA", (96, 8), SHADE[:3] + (0,))
    pixels = fade.load()
    for x in range(96):
        for y in range(8):
            pixels[x, y] = SHADE[:3] + (int(round(SHADE[3] * (x / 95.0) ** 1.3)),)
    out["ov_fade_r.png"] = fade
    out["ov_fade_l.png"] = fade.transpose(Image.FLIP_LEFT_RIGHT)

    def glow(width, focus_x):
        picture = Image.new("RGBA", (width, 128), SHADE[:3] + (0,))
        px = picture.load()
        for y in range(128):
            for x in range(width):
                dx = (x - focus_x) / float(max(focus_x, width - 1 - focus_x) or 1)
                dy = (127 - y) / 127.0
                reach = max(0.0, 1.0 - math.sqrt(dx * dx + dy * dy))
                px[x, y] = SHADE[:3] + (int(round(215 * reach ** 1.5)),)
        return picture

    corner, centre = glow(128, 127), glow(256, 127.5)
    out["ov_glow_br.png"] = corner
    out["ov_glow_bl.png"] = corner.transpose(Image.FLIP_LEFT_RIGHT)
    out["ov_glow_tr.png"] = corner.transpose(Image.FLIP_TOP_BOTTOM)
    out["ov_glow_tl.png"] = corner.transpose(Image.FLIP_LEFT_RIGHT).transpose(Image.FLIP_TOP_BOTTOM)
    out["ov_glow_bc.png"] = centre
    out["ov_glow_tc.png"] = centre.transpose(Image.FLIP_TOP_BOTTOM)
    return out


def pictures() -> dict:
    out = own_pictures()
    out.update(overlay_pictures())
    for code, (plate, edge, radius, button, button_edge, focus, focus_edge, button_r) in PAINT.items():
        bar = 5 if code == "fgs" else 0
        out["sl_%s_plate.png" % code] = fuse.shape(96, 96, radius, plate, edge)
        out["sl_%s_slab.png" % code] = fuse.shape(96, 96, 0, plate, edge)
        out["sl_%s_tile.png" % code] = fuse.shape(96, 96, radius, focus, focus_edge, bar=bar)
        for folder, width, height, r in (("720", 64, BH, button_r * 2.0 / 3.0), ("1080", 96, BH * 3 // 2, button_r)):
            out["sl_%s_button_%s.png" % (code, folder)] = fuse.shape(width, height, r, button, button_edge)
            out["sl_%s_focus_%s.png" % (code, folder)] = fuse.shape(
                width, height, r, focus, focus_edge, bar=(bar if folder == "1080" else bar * 2.0 / 3.0))
    for step in range(sl.RING_FRAMES + 1):
        out["sl_ring_%02d.png" % step] = ring(step / float(sl.RING_FRAMES))
    out["sl_shade.png"] = shade()
    out["sl_white.png"] = Image.new("RGBA", (8, 8), WHITE)  # Kodi's own white.png fades towards a corner
    out["sl_band.png"] = band_picture()
    out["sl_band_top.png"] = band_picture(top=True)
    return out


# ------------------------------------------------------------------------------ skin files
# A preview copy (the Customize screen) shifts every id and draws buttons as pictures with a label.
CTX = {"offset": 0, "mock": False}


def cid_of(control_id):
    return control_id + CTX["offset"] if control_id else control_id


def tags(pairs, indent="        "):
    return "".join("%s<%s>%s</%s>\n" % (indent, name, value, name) for name, value in pairs)


def box(left, top, width, height):
    return [("left", left), ("top", top), ("width", width), ("height", height)]


def image(left, top, width, height, texture, cid=None, border=None, diffuse=None, visible=None, aspect=None):
    out = '      <control type="image"%s>\n' % (' id="%d"' % cid_of(cid) if cid else "")
    out += tags(box(left, top, width, height))
    out += "        <texture%s>%s</texture>\n" % (' border="%s"' % border if border else "", texture)
    if diffuse:
        out += tags([("colordiffuse", diffuse)])
    if aspect:
        out += tags([("aspectratio", aspect)])
    if visible:
        out += tags([("visible", visible)])
    return out + "      </control>\n"


def label(left, top, width, height, text, font="font10", color="skl_text", align="left", visible=None, wrap=False):
    out = '      <control type="label">\n' + tags(box(left, top, width, height))
    out += tags([("label", text), ("font", font), ("textcolor", P % color), ("shadowcolor", P % "skl_shadow"),
                 ("align", align), ("aligny", "center")])
    if wrap:
        out += tags([("wrapmultiline", "true")])
    if visible:
        out += tags([("visible", visible)])
    return out + "      </control>\n"


def button(cid, left, top, width, text, other, font="font12", height=BH, plates=True, offset=0):
    """A text button: its two plates as pictures behind it (a button cannot take a picture from a
    window property), then the button itself without pictures."""
    out = ""
    if CTX["mock"]:
        # the preview shows Skip with the focus and Close without it
        focused = cid == sl.ID_SKIP
        if plates:
            out += image(left, top, width, height, P % ("skl_focus" if focused else "skl_button"),
                         border=sl.BUTTON_BORDER_720)
        out += '      <control type="label">\n' + tags(box(left, top, width, height))
        out += tags([("label", text), ("font", font),
                     ("textcolor", P % ("skl_focus_text" if focused else "skl_button_text")),
                     ("align", "center"), ("aligny", "center")])
        return out + "      </control>\n"
    if plates:
        out += image(left, top, width, height, P % "skl_button", border=sl.BUTTON_BORDER_720,
                     visible="!Control.HasFocus(%d)" % cid)
        out += image(left, top, width, height, P % "skl_focus", border=sl.BUTTON_BORDER_720,
                     visible="Control.HasFocus(%d)" % cid)
    out += '      <control type="button" id="%d">\n' % cid + tags(box(left, top, width, height))
    out += tags([("label", text), ("font", font), ("textcolor", P % "skl_button_text"),
                 ("focusedcolor", P % "skl_focus_text"), ("disabledcolor", P % "skl_button_text"),
                 ("shadowcolor", "00000000"), ("texturefocus", "-"), ("texturenofocus", "-"),
                 ("align", "center"), ("aligny", "center"), ("textoffsetx", offset),
                 ("onleft", other), ("onright", other), ("onup", other), ("ondown", other)])
    return out + "      </control>\n"


def progress_line(layout, diffuse="skl_accent"):
    left, top, width, height = layout.track
    return (image(left, top, width, height, "sl_white.png", diffuse=P % "skl_track")
            + image(left, top, 0, height, "sl_white.png", cid=sl.ID_BAR_FILL, diffuse=P % diffuse))


def progress_ring(layout, accent="skl_accent", track="skl_track"):
    left, top, width, height = layout.track
    return (image(left, top, width, height, "sl_ring_%02d.png" % sl.RING_FRAMES, diffuse=P % track)
            + image(left, top, width, height, P % "skl_ring", cid=sl.ID_RING, diffuse=P % accent))


HEADING = "%s [B]%s[/B]" % (P % "skl_heading", P % "countdown")
NEXT = P % "next_jump_label"
JUMP = "String.IsEqual(Window.Property(show_next_jump),true)"


def plate(layout, prop="skl_plate", left=0, width=None):
    return image(left, 0, width if width else layout.width, layout.height, P % prop, border=sl.PLATE_BORDER)


def slab(layout):
    close = sl.ID_CLOSE
    if layout.size == sl.SIZE_FULL:
        return (plate(layout, "skl_slab") + progress_line(layout)
                + label(20, 14, 300, 16, P % "skl_kicker", color="skl_text2")
                + label(320, 14, 180, 16, P % "skl_range", color="skl_text2", align="right")
                + label(20, 32, 480, 24, HEADING, font="font13")
                + label(20, 58, 480, 20, NEXT, font="font11", color="skl_text2", visible=JUMP)
                + button(sl.ID_SKIP, 12, 84, 340, P % "skl_skip", close)
                + button(close, 360, 84, 148, P % "skl_close", sl.ID_SKIP))
    return (plate(layout, "skl_slab") + progress_line(layout)
            + label(16, 12, 250, 24, HEADING, font="font12")
            + button(sl.ID_SKIP, 276, 10, 180, P % "skl_skip_short", close)
            + button(close, 464, 10, 44, "X", sl.ID_SKIP))


def dial(layout):
    close = sl.ID_CLOSE
    left, top, width, height = layout.track
    # the shade reaches past the layout on every side, where it fades out
    shade_picture = image(-18, -18, layout.width + 36, layout.height + 36, "sl_shade.png", border=40)
    if layout.size == sl.SIZE_FULL:
        return (shade_picture + progress_ring(layout)
                + label(left, top + 30, width, 32, "[B]%s[/B]" % (P % "countdown"), font="font13", align="center")
                + label(124, 20, 330, 16, "%s  %s" % (P % "skl_kicker", P % "skl_range"), color="skl_text2")
                + label(124, 40, 330, 24, P % "skl_heading", font="font13")
                + label(124, 68, 330, 20, NEXT, font="font11", color="skl_text2", visible=JUMP)
                + button(sl.ID_SKIP, 16, 122, 300, P % "skl_skip", close)
                + button(close, 324, 122, 130, P % "skl_close", sl.ID_SKIP))
    return (shade_picture + progress_ring(layout)
            + label(left, top + 14, width, 20, P % "skl_seconds", font="font10", align="center")
            + button(sl.ID_SKIP, 70, 18, 180, P % "skl_skip_short", close)
            + button(close, 258, 18, 44, "X", sl.ID_SKIP))


def band(layout):
    close = sl.ID_CLOSE
    top = "String.IsEqual(Window.Property(skl_top),true)"
    back = (image(0, 0, layout.width, layout.height, "sl_band.png", visible="!" + top)
            + image(0, 0, layout.width, layout.height, "sl_band_top.png", visible=top))
    if layout.size == sl.SIZE_FULL:
        return (back
                + label(48, 54, 700, 16, "%s  %s" % (P % "skl_kicker", P % "skl_range"), color="skl_text2")
                + label(48, 72, 700, 28, HEADING, font="font16")
                + label(48, 100, 700, 20, NEXT, font="font11", color="skl_text2", visible=JUMP)
                + button(sl.ID_SKIP, 794, 84, 300, P % "skl_skip", close)
                + button(close, 1102, 84, 130, P % "skl_close", sl.ID_SKIP)
                + progress_line(layout))
    return (back
            + label(48, 28, 700, 24, HEADING, font="font13")
            + label(48, 52, 700, 16, NEXT, color="skl_text2", visible=JUMP)
            + button(sl.ID_SKIP, 934, 38, 250, P % "skl_skip_short", close)
            + button(close, 1192, 38, 40, "X", sl.ID_SKIP)
            + progress_line(layout))


def float_(layout):
    close = sl.ID_CLOSE
    if layout.size == sl.SIZE_FULL:
        return (label(0, 4, 470, 16, "%s  %s" % (P % "skl_kicker", P % "skl_range"), color="skl_text2", align="right")
                + label(0, 24, 470, 40, HEADING, font="font30", align="right")
                + label(0, 70, 470, 20, NEXT, font="font11", color="skl_text2", align="right", visible=JUMP)
                + button(close, 150, 110, 112, P % "skl_close", sl.ID_SKIP)
                + button(sl.ID_SKIP, 270, 110, 200, P % "skl_skip_short", close, offset=14)
                + progress_ring(layout, "skl_focus_text", "skl_focus_track"))
    return (label(0, 4, 120, 32, "[B]%s[/B]" % (P % "countdown"), font="font16", align="right")
            + button(sl.ID_SKIP, 130, 6, 200, P % "skl_skip_short", sl.ID_SKIP, offset=14)
            + progress_ring(layout, "skl_focus_text", "skl_focus_track"))


def tile(cid, left, width, height, text, other, font):
    """A big tile: plate without the focus, the look's focus fill with it."""
    if CTX["mock"]:
        picture = "skl_tile" if cid == sl.ID_SKIP else "skl_plate"
        return (image(left, 0, width, height, P % picture, border=sl.PLATE_BORDER),
                button(cid, left, 0, width, text, other, font=font, height=height, plates=False))
    return (image(left, 0, width, height, P % "skl_plate", border=sl.PLATE_BORDER, visible="!Control.HasFocus(%d)" % cid)
            + image(left, 0, width, height, P % "skl_tile", border=sl.PLATE_BORDER, visible="Control.HasFocus(%d)" % cid),
            button(cid, left, 0, width, text, other, font=font, height=height, plates=False))


def split(layout):
    close = sl.ID_CLOSE
    left, top, width, height = layout.track  # the fill, a little inside the tile so it clears the corners
    tile_left, tile_width, height = left - sl.TILE_INSET, width + 2 * sl.TILE_INSET, layout.height
    skip_back, skip_button = tile(sl.ID_SKIP, tile_left, tile_width, height, P % "skl_skip_word", close,
                                  "font16" if layout.size == sl.SIZE_FULL else "font12")
    fill = image(left, top, 0, 0, "sl_white.png", cid=sl.ID_BAR_FILL, diffuse=P % "skl_tile_fill")
    if layout.size == sl.SIZE_FULL:
        close_back, close_button = tile(close, 464, 56, height, "X", sl.ID_SKIP, "font13")
        return (plate(layout, width=308)
                + label(16, 14, 276, 16, "%s  %s" % (P % "skl_kicker", P % "skl_range"), color="skl_text2")
                + label(16, 36, 276, 24, HEADING, font="font13")
                + label(16, 66, 276, 20, NEXT, color="skl_text2", visible=JUMP)
                + skip_back + fill + skip_button + close_back + close_button)
    close_back, close_button = tile(close, 376, 44, height, "X", sl.ID_SKIP, "font12")
    return (plate(layout, width=188)
            + label(12, 10, 164, 24, "%s [B]%s[/B]" % (P % "skl_kicker", P % "countdown"), font="font12")
            + skip_back + fill + skip_button + close_back + close_button)


def timeline(layout):
    close = sl.ID_CLOSE
    left, top, width, height = layout.track
    track = (image(left, top, width, height, "sl_white.png", diffuse=P % "skl_track")
             + image(left, top, 0, height, "sl_white.png", cid=sl.ID_BAR_FILL, diffuse=P % "skl_accent")
             + image(left, top, 0, height, "sl_white.png", cid=sl.ID_NESTED, diffuse=P % "skl_nested")
             + image(left, top - 4, 2, height + 8, "sl_white.png", cid=sl.ID_PLAYHEAD, diffuse=P % "skl_text"))
    if layout.size == sl.SIZE_FULL:
        return (plate(layout)
                + label(20, 14, 330, 24, HEADING, font="font13")
                + label(350, 16, 270, 20, NEXT, color="skl_text2", align="right", visible=JUMP)
                + label(20, 42, 300, 16, "%s  %s" % (P % "skl_kicker", P % "skl_range"), color="skl_text2")
                + track
                + label(left, top + height + 4, 120, 14, P % "skl_t0", color="skl_text2")
                + label(left + width - 120, top + height + 4, 120, 14, P % "skl_t1", color="skl_text2", align="right")
                + button(sl.ID_SKIP, 20, 110, 420, P % "skl_skip", close)
                + button(close, 448, 110, 172, P % "skl_close", sl.ID_SKIP))
    return (plate(layout)
            + button(sl.ID_SKIP, 12, 12, 140, P % "skl_skip_short", close)
            + label(left, 8, width, 16, "%s [B]%s[/B]" % (P % "skl_kicker", P % "countdown"))
            + track
            + button(close, 468, 12, 40, "X", sl.ID_SKIP))


def rail(layout):
    close = sl.ID_CLOSE
    left, top, width, height = layout.track
    if layout.size == sl.SIZE_FULL:
        return (plate(layout, "skl_slab") + progress_ring(layout)
                + label(left, top + 28, width, 28, "[B]%s[/B]" % (P % "countdown"), font="font13", align="center")
                + label(12, 108, 160, 16, P % "skl_kicker", color="skl_text2", align="center")
                + label(12, 126, 160, 20, P % "skl_heading", font="font12", align="center")
                + label(12, 148, 160, 44, NEXT, color="skl_text2", align="center", visible=JUMP, wrap=True)
                + button(sl.ID_SKIP, 16, 200, 152, P % "skl_skip_word", close)
                + button(close, 16, 232, 152, P % "skl_close", sl.ID_SKIP))
    return (plate(layout, "skl_slab") + progress_ring(layout)
            + label(left, top + 14, width, 20, P % "skl_seconds", align="center")
            + label(72, 16, 100, 18, P % "skl_kicker", font="font12")
            + label(72, 36, 100, 16, "[B]%s[/B]" % (P % "countdown"), color="skl_text2")
            + button(sl.ID_SKIP, 16, 76, 152, P % "skl_skip_word", sl.ID_SKIP))


def poster(layout):
    close = sl.ID_CLOSE
    art = P % "skl_poster"
    if layout.size == sl.SIZE_FULL:
        return (plate(layout)
                + image(12, 12, 84, 126, art, aspect="scale")
                + label(116, 14, 250, 16, P % "skl_kicker", color="skl_text2")
                + label(366, 14, 138, 16, P % "skl_range", color="skl_text2", align="right")
                + label(116, 34, 388, 26, HEADING, font="font13")
                + label(116, 64, 388, 20, NEXT, font="font11", color="skl_text2", visible=JUMP)
                + progress_line(layout)
                + button(sl.ID_SKIP, 116, 112, 250, P % "skl_skip", close)
                + button(close, 374, 112, 130, P % "skl_close", sl.ID_SKIP))
    return (plate(layout)
            + image(10, 9, 36, 54, art, aspect="scale")
            + label(62, 6, 306, 20, "%s [B]%s[/B]" % (P % "skl_kicker", P % "countdown"), font="font12")
            + button(sl.ID_SKIP, 62, 28, 258, P % "skl_skip_short", close)
            + button(close, 328, 28, 40, "X", sl.ID_SKIP)
            + progress_line(layout))


def minimal(layout):
    """The smallest form of a layout: Skip and how far the segment is, in the build of its family."""
    name = layout.name
    left, top, width, height = layout.track
    skip = sl.ID_SKIP
    if name == "Slab":
        return (plate(layout, "skl_slab") + progress_line(layout)
                + button(skip, 8, 10, 214, P % "skl_skip_short", skip))
    if name == "Dial":
        return (image(-18, -18, layout.width + 36, layout.height + 36, "sl_shade.png", border=40)
                + progress_ring(layout)
                + label(left, top + 14, width, 20, P % "skl_seconds", align="center")
                + button(skip, 64, 16, 144, P % "skl_skip_word", skip))
    if name == "Band":
        top_band = "String.IsEqual(Window.Property(skl_top),true)"
        return (image(0, 0, layout.width, layout.height, "sl_band.png", visible="!" + top_band)
                + image(0, 0, layout.width, layout.height, "sl_band_top.png", visible=top_band)
                + label(48, 16, 700, 28, HEADING, font="font13")
                + button(skip, 1032, 16, 200, P % "skl_skip_short", skip)
                + progress_line(layout))
    if name == "Float":
        return (button(skip, 0, 6, 200, P % "skl_skip_short", skip, offset=14)
                + progress_ring(layout, "skl_focus_text", "skl_focus_track"))
    if name == "Split":
        back, front = tile(skip, 0, layout.width, layout.height, P % "skl_skip_short", skip, "font12")
        return back + image(left, top, 0, 0, "sl_white.png", cid=sl.ID_BAR_FILL, diffuse=P % "skl_tile_fill") + front
    if name == "Timeline":
        return (plate(layout)
                + button(skip, 8, 8, 144, P % "skl_skip_word", skip)
                + image(left, top, width, height, "sl_white.png", diffuse=P % "skl_track")
                + image(left, top, 0, height, "sl_white.png", cid=sl.ID_BAR_FILL, diffuse=P % "skl_accent")
                + image(left, top, 0, height, "sl_white.png", cid=sl.ID_NESTED, diffuse=P % "skl_nested")
                + image(left, top - 4, 2, height + 8, "sl_white.png", cid=sl.ID_PLAYHEAD, diffuse=P % "skl_text"))
    if name == "Rail":
        return (plate(layout, "skl_slab") + progress_ring(layout)
                + label(left, top + 10, width, 20, P % "skl_seconds", align="center")
                + button(skip, 8, 56, 68, P % "skl_skip_word", skip))
    # Poster
    return (plate(layout)
            + image(10, 7, 28, 40, P % "skl_poster", aspect="scale")
            + button(skip, 50, 10, 192, P % "skl_skip_short", skip)
            + progress_line(layout))


def _with_minimal(builder):
    return lambda layout: minimal(layout) if layout.size == sl.SIZE_MINIMAL else builder(layout)


BUILDERS = {name: _with_minimal(builder) for name, builder in (
    ("Poster", poster), ("Slab", slab), ("Dial", dial), ("Band", band), ("Float", float_), ("Split", split),
    ("Timeline", timeline), ("Rail", rail))}

HEAD = """<?xml version='1.0' encoding='utf-8'?>
<!-- Written by tools/gen_skip_layouts.py: edit that, not this file. -->
<window>
  <coordinates>
    <system>1</system>
    <posx>0</posx>
    <posy>0</posy>
    <width>1280</width>
    <height>720</height>
  </coordinates>
  <zorder>1</zorder>
  <defaultcontrol>%d</defaultcontrol>
  <animation type="WindowClose">
    <effect type="fade" start="100" end="0" time="250"></effect>
  </animation>
  <controls>
    <control type="image" id="%d">
      <left>0</left>
      <top>0</top>
      <width>%d</width>
      <height>1</height>
      <texture>white.png</texture>
      <colordiffuse>00FFFFFF</colordiffuse>
    </control>
    <control type="image" id="3295">
      <left>0</left>
      <top>0</top>
      <width>1</width>
      <height>1</height>
      <texture border="24">$INFO[Window.Property(skl_overlay9)]</texture>
      <visible>String.IsEqual(Window.Property(skippy_dialog_ready),true) + !String.IsEmpty(Window.Property(skl_overlay9))</visible>
      <animation type="Visible">
        <effect type="fade" start="0" end="100" time="300"></effect>
      </animation>
    </control>
    <control type="image" id="3296">
      <left>0</left>
      <top>0</top>
      <width>1</width>
      <height>1</height>
      <texture>$INFO[Window.Property(skl_overlay)]</texture>
      <visible>String.IsEqual(Window.Property(skippy_dialog_ready),true) + !String.IsEmpty(Window.Property(skl_overlay))</visible>
      <animation type="Visible">
        <effect type="fade" start="0" end="100" time="300"></effect>
      </animation>
    </control>
    <control type="group" id="%d">
      <posx>0</posx>
      <posy>0</posy>
      <width>%d</width>
      <height>%d</height>
      <visible>String.IsEqual(Window.Property(skippy_dialog_ready),true)</visible>
      <animation type="Visible" condition="String.IsEqual(Window.Property(skl_in),Rise)">
        <effect type="slide" start="0,12" end="0,0" time="180" tween="cubic" easing="out"></effect>
        <effect type="fade" start="0" end="100" time="180"></effect>
      </animation>
      <animation type="Visible" condition="String.IsEqual(Window.Property(skl_in),Pop)">
        <effect type="zoom" start="86" end="100" center="auto" time="170" tween="back" easing="out"></effect>
        <effect type="fade" start="0" end="100" time="140"></effect>
      </animation>
      <animation type="Visible" condition="String.IsEqual(Window.Property(skl_in),SlideRight)">
        <effect type="slide" start="40,0" end="0,0" time="200" tween="cubic" easing="out"></effect>
        <effect type="fade" start="0" end="100" time="200"></effect>
      </animation>
      <animation type="Visible" condition="String.IsEqual(Window.Property(skl_in),SlideLeft)">
        <effect type="slide" start="-40,0" end="0,0" time="200" tween="cubic" easing="out"></effect>
        <effect type="fade" start="0" end="100" time="200"></effect>
      </animation>
      <animation type="Visible">
        <effect type="fade" start="0" end="100" time="300"></effect>
      </animation>
      <animation type="WindowClose" condition="String.IsEqual(Window.Property(skl_out),Drop)">
        <effect type="slide" start="0,0" end="0,10" time="150"></effect>
        <effect type="fade" start="100" end="0" time="150"></effect>
      </animation>
      <animation type="WindowClose" condition="String.IsEqual(Window.Property(skl_out),Shrink)">
        <effect type="zoom" start="100" end="88" center="auto" time="150"></effect>
        <effect type="fade" start="100" end="0" time="150"></effect>
      </animation>
      <animation effect="zoom" start="100" end="104" center="auto" time="500" pulse="true" condition="String.IsEqual(Window.Property(skl_pulse),true)">Conditional</animation>
"""
TAIL = "    </control>\n  </controls>\n</window>\n"


def skin_720(layout) -> str:
    body = BUILDERS[layout.name](layout)
    return (HEAD % (sl.ID_SKIP, sl.ID_PROBE, sl.PROBE_W, sl.ID_ROOT, layout.width, layout.height)) + body + TAIL


def skin_files() -> dict:
    """Path -> text for both skin folders."""
    out = {}
    for layout in sl.all_layouts():
        text = skin_720(layout)
        out[os.path.join(SKINS, "720p", layout.xml)] = text
        out[os.path.join(SKINS, "1080i", layout.xml)] = gen.convert(text)
    for folder in ("720p", "1080i"):
        path = os.path.join(SKINS, folder, CUSTOMIZE)
        with open(path, encoding="utf-8", newline="") as handle:
            out[path] = with_mocks(handle.read(), folder)
    return out


# ------------------------------------------------------------- the Customize screen's preview
CUSTOMIZE = "SkipDialogCustomize.xml"
BEGIN, END = "<!-- SKIP-LAYOUT-PREVIEW-BEGIN (tools/gen_skip_layouts.py) -->", "<!-- SKIP-LAYOUT-PREVIEW-END -->"
STAGE_CLOSE = "    </control>\n  </controls>\n</window>"


def chip(cid, left, text):
    """A picker under the preview, styled like the rows of the screen."""
    out = '      <control type="button" id="%d">\n' % cid
    out += tags([("left", left), ("top", sl.CHIP_TOP), ("width", sl.CHIP_W), ("height", 30), ("label", text),
                 ("font", "font12")])
    out += '        <texturefocus border="14">ms_fgf_focus.png</texturefocus>\n'
    out += '        <texturenofocus border="14">ms_fgf_row.png</texturenofocus>\n'
    out += tags([("textcolor", P % "ms_text"), ("focusedcolor", P % "ms_text_focus"), ("shadowcolor", "00000000"),
                 ("align", "left"), ("aligny", "center"), ("textoffsetx", 14),
                 ("onup", cid), ("ondown", cid), ("onleft", cid), ("onright", cid)])
    return out + "      </control>\n"


def mocks_720() -> str:
    """The two pickers and a small screen holding a copy of every layout (720p)."""
    out = "      %s\n" % BEGIN
    out += chip(sl.ID_PICK_LAYOUT, 0, "Skip dialog layout") + chip(sl.ID_PICK_LOOK, sl.CHIP_W + 8, "Layout look")
    # the whole 1280 x 720 screen, drawn small inside the preview stage
    out += '      <control type="group" id="%d">\n' % sl.ID_MOCK_SCREEN
    out += tags([("left", sl.MOCK_LEFT), ("top", sl.MOCK_TOP), ("width", sl.CANVAS_W), ("height", sl.CANVAS_H)])
    out += ('        <animation effect="zoom" start="%d" end="%d" center="%d,%d" time="0" condition="true">Conditional'
            "</animation>\n" % (sl.MOCK_ZOOM, sl.MOCK_ZOOM, sl.MOCK_LEFT, sl.MOCK_TOP))  # the centre counts from the stage group
    # a faint veil marks the screen the layout sits on (the stage is taller than a screen)
    out += image(0, 0, sl.CANVAS_W, sl.CANVAS_H, "sl_white.png", diffuse="16FFFFFF",
                 visible="!String.IsEmpty(Window.Property(skl_mock))")
    # the shade behind the layout (Background overlay), placed by the Customize screen
    has_mock = "!String.IsEmpty(Window.Property(skl_mock))"
    out += image(0, 0, 1, 1, P % "skl_overlay9", cid=sl.ID_MOCK_OVERLAY, border=sl.OVERLAY_BORDER,
                 visible=has_mock + " + !String.IsEmpty(Window.Property(skl_overlay9))")
    out += image(0, 0, 1, 1, P % "skl_overlay", cid=sl.ID_MOCK_OVERLAY_PLAIN,
                 visible=has_mock + " + !String.IsEmpty(Window.Property(skl_overlay))")
    # the slots of the drawn designs (skip_canvas): the Customize screen draws on them, small
    import gen_skip_canvas as canvas_gen
    import skip_canvas as canvas

    out += canvas_gen.slots_xml("720", canvas.MOCK_OFFSET, "      ")
    for index, layout in enumerate(sl.all_layouts()):
        CTX.update(offset=sl.mock_offset(index), mock=True)
        try:
            body = BUILDERS[layout.name](layout)
        finally:
            CTX.update(offset=0, mock=False)
        out += '      <control type="group" id="%d">\n' % (sl.ID_ROOT + sl.mock_offset(index))
        out += tags([("left", 0), ("top", 0), ("width", layout.width), ("height", layout.height),
                     ("visible", "String.IsEqual(Window.Property(skl_mock),%s)" % layout.xml[:-4])])
        out += body + "      </control>\n"
    return out + "      </control>\n      %s\n" % END


def with_mocks(text, folder) -> str:
    """The Customize file with the preview block put in (or replaced), keeping its line endings."""
    nl = "\r\n" if "\r\n" in text else "\n"
    block = mocks_720() if folder == "720p" else gen.convert(mocks_720())
    block = block.replace("\n", nl)
    if BEGIN in text:
        start = text.index(BEGIN) - 6
        stop = text.index(END) + len(END) + len(nl)
        return text[:start] + block + text[stop:]
    close = STAGE_CLOSE.replace("\n", nl)
    assert text.rstrip().endswith(close), "the stage group must close the file"
    at = text.rindex(close)
    return text[:at] + block + text[at:]


def _png(picture) -> bytes:
    buffer = io.BytesIO()
    picture.save(buffer, "PNG", optimize=True)
    return buffer.getvalue()


def stale() -> list:
    out = []
    for path, text in skin_files().items():
        try:
            with open(path, encoding="utf-8", newline="") as handle:
                if handle.read() != text:
                    out.append(path)
        except OSError:
            out.append(path)
    for name, picture in pictures().items():
        path = os.path.join(MEDIA, name)
        try:
            with Image.open(path) as found:
                same = found.size == picture.size and found.convert("RGBA").tobytes() == picture.convert("RGBA").tobytes()
        except OSError:
            same = False
        if not same:
            out.append(path)
    return out


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    todo = stale()
    if "--check" in argv:
        for path in todo:
            print("stale or missing:", os.path.relpath(path, ROOT))
        return 1 if todo else 0
    texts, images = skin_files(), {os.path.join(MEDIA, name): picture for name, picture in pictures().items()}
    for path in todo:
        if path in texts:
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(texts[path])
        else:
            with open(path, "wb") as handle:
                handle.write(_png(images[path]))
        print("wrote", os.path.relpath(path, ROOT))
    print("%d skin files, %d pictures, %d written" % (len(texts), len(images), len(todo)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
