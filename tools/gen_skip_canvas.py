# -*- coding: utf-8 -*-
"""Write what the drawn skip dialog needs: ``SkipCanvas.xml`` and the ``cv_*.png`` pictures.

    python tools/gen_skip_canvas.py            (write what is missing or changed)
    python tools/gen_skip_canvas.py --check    (exit 1 when something is missing or differs)

The dialog is drawn by ``skip_canvas.py``: it places everything itself, so the skin file is only a
set of picture slots (a nine-slice border cannot be given from Python) and the two buttons. The
pictures are painted from ``skip_canvas_looks.py``, which holds the mockups' own values: one set
per look, per corner choice (the look's own, hard, rounded) and per skin folder.
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

import gen_skin_1080i as gen  # noqa: E402
import gen_skip_layouts as old  # noqa: E402  (rich(): gradients, bevels, frames)
import skip_canvas as cv  # noqa: E402
import skip_canvas_looks as looks  # noqa: E402

SKINS = os.path.join(ROOT, "resources", "skins", "default")
MEDIA = os.path.join(SKINS, "media")
FOLDERS = (("1080", 1.0), ("720", 2.0 / 3.0))


def _stops(grad):
    angle, stops = grad
    return angle, [(pos, looks.rgb(colour)) for colour, pos in stops]


def _shape(size, radius, fill, edge, stroke, grad=None, bevel=False, frame=None, bar=0, scale=1.0):
    kwargs = dict(fill=fill or looks.NONE)
    if grad:
        kwargs["grad"] = _stops(grad)
    if edge:
        kwargs.update(edge=edge, stroke=max(1.0, stroke * looks.SCALE * scale))
    if bevel:
        kwargs.update(hi=77, lo=(102, 3 * scale))
    if frame:
        kwargs["frame"] = (frame[0] * looks.SCALE * scale, frame[1], 1)
    picture = old.rich(size, size, radius, **kwargs)
    if bar:
        strip = Image.new("RGBA", (max(1, int(round(bar * looks.SCALE * scale))), size), (255, 255, 255, 255))
        picture.alpha_composite(strip, (0, 0))
    return picture


def look_pictures(code, key, look) -> dict:
    out = {}
    for folder, scale in FOLDERS:
        def radius(value, limit):
            return min(limit, min(value, 60) * looks.SCALE * scale)

        b_plate, b_box, b_chip = cv.BORDERS[folder]["plate"], cv.BORDERS[folder]["box"], cv.BORDERS[folder]["chip"]
        name = "cv_%s%s_%%s_%s.png" % (code, key, folder)
        out[name % "plate"] = _shape(2 * b_plate + 8, radius(look["r"], b_plate), look.get("plate"), look["plate_edge"],
                                     look["plate_stroke"], look.get("plate_grad"), look.get("plate_bevel"),
                                     look.get("plate_frame"), scale=scale)
        out[name % "box"] = _shape(2 * b_box + 8, radius(look["ri"], b_box), look["nest"], look["nest_edge"], 1, scale=scale)
        out[name % "btn"] = _shape(2 * b_box + 8, radius(look["ri"], b_box), look.get("btn"), look["btn_edge"],
                                   look["btn_stroke"], look.get("btn_grad"), bool(look.get("btn_grad")), scale=scale)
        out[name % "foc"] = _shape(2 * b_box + 8, radius(look["ri"], b_box), look.get("foc"), look["foc_edge"],
                                   look["btn_stroke"], look.get("foc_grad"), bool(look.get("foc_grad")),
                                   bar=look["foc_bar"], scale=scale)
        # outside a plate the buttons take the look's button radius (a pill in the round looks)
        out[name % "pill"] = _shape(2 * b_box + 8, radius(look["rb"], b_box), look.get("btn"), look["btn_edge"],
                                    look["btn_stroke"], look.get("btn_grad"), bool(look.get("btn_grad")), scale=scale)
        out[name % "pillfoc"] = _shape(2 * b_box + 8, radius(look["rb"], b_box), look.get("foc"), look["foc_edge"],
                                       look["btn_stroke"], look.get("foc_grad"), bool(look.get("foc_grad")),
                                       bar=look["foc_bar"], scale=scale)
        # the plate as a pill, for the small forms of the round looks (one picture per height)
        for slot, part in (("plate_c", "platec"), ("plate_m", "platem")):
            b_pill = cv.BORDERS[folder][slot]
            out[name % part] = _shape(2 * b_pill + 8, min(b_pill, cv.PILL_HEIGHTS[slot] / 2.0 * scale), look.get("plate"),
                                      look["plate_edge"], look["plate_stroke"], look.get("plate_grad"),
                                      look.get("plate_bevel"), scale=scale)
        # tiles (Split): the focus colour and the card's own fill at the card's corner, in the button slots
        out[name % "tile"] = _shape(2 * b_box + 8, radius(look["r"], b_box), look.get("foc"), look["foc_edge"],
                                    look["btn_stroke"], look.get("foc_grad"), bool(look.get("foc_grad")), scale=scale)
        out[name % "ptile"] = _shape(2 * b_box + 8, radius(look["r"], b_box), look.get("plate"), look["plate_edge"],
                                     look["plate_stroke"], look.get("plate_grad"), look.get("plate_bevel"), scale=scale)
        # a white outline at the inner corner (Timeline: the block that is playing), tinted when drawn
        out[name % "outl"] = _shape(2 * b_box + 8, radius(look["ri"], b_box), looks.NONE, (255, 255, 255, 255), 1.5,
                                    scale=scale)
        # Focus style Outline: the button in focus as a line around it (on a card, and as a pill), tinted when drawn
        out[name % "focl"] = _shape(2 * b_box + 8, radius(look["ri"], b_box), looks.NONE, (255, 255, 255, 255), 3, scale=scale)
        out[name % "pillfocl"] = _shape(2 * b_box + 8, radius(look["rb"], b_box), looks.NONE, (255, 255, 255, 255), 3,
                                        scale=scale)
        # a heavier frame that stands a little outside a picture (Up Next, Queue: the chosen card), tinted when drawn
        out[name % "frame"] = _shape(2 * b_box + 8, radius(look["ri"] + 6 if look["ri"] else 0, b_box), looks.NONE,
                                     (255, 255, 255, 255), 3, scale=scale)
        out[name % "chip"] = _shape(2 * b_chip + 8, radius(look["rb"], b_chip), look["chip"], None, 1, scale=scale)
    return out


def shadow(scale, colour=(0, 0, 0), alpha=128, blur=28.0, radius=28.0, small=False) -> Image.Image:
    """A soft shade to lie under a plate: the plate's shape, blurred (nine-slice). ``small`` is the one
    for a low card, a pill or a tile: a picture cannot be drawn lower than twice its border."""
    border = cv.BORDERS["1080" if scale == 1.0 else "720"]["shadow_s" if small else "shadow"]
    size = 2 * border + 8
    reach = (cv.SMALL_REACH if small else cv.SHADOW_REACH) * looks.SCALE * scale
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((reach, reach, size - 1 - reach, size - 1 - reach),
                                           radius=radius * looks.SCALE * scale, fill=alpha)
    mask = mask.filter(ImageFilter.GaussianBlur(blur * looks.SCALE * scale / 2.0))
    out = Image.new("RGBA", (size, size), tuple(colour) + (0,))
    out.putalpha(mask)
    return out


def glow(scale, colour) -> Image.Image:
    """Neon: light around the plate's edge, outside and a little inside."""
    border = cv.BORDERS["1080" if scale == 1.0 else "720"]["shadow"]
    size = 2 * border + 8
    reach = cv.SHADOW_REACH * looks.SCALE * scale
    ring = Image.new("L", (size, size), 0)
    ImageDraw.Draw(ring).rounded_rectangle((reach, reach, size - 1 - reach, size - 1 - reach),
                                           radius=8 * looks.SCALE * scale, outline=255, width=max(2, int(round(5 * scale))))
    ring = ring.filter(ImageFilter.GaussianBlur(13 * looks.SCALE * scale / 2.0))
    out = Image.new("RGBA", (size, size), colour[:3] + (0,))
    out.putalpha(ring.point(lambda v: min(255, int(v * 2.4 * colour[3] / 255.0))))
    return out


def icons() -> dict:
    """Skip, Close and the jump arrow of the nested line, white, from the mockups' own outlines (24 units)."""
    out = {}
    s = 8  # 192 pixels for 24 units
    def canvas():
        return Image.new("L", (24 * s, 24 * s), 0)

    def line(draw, points, width=2.4):
        pts = [(x * s, y * s) for x, y in points]
        draw.line(pts, fill=255, width=int(round(width * s)), joint="curve")
        r = width * s / 2.0
        for x, y in (pts[0], pts[-1]):
            draw.ellipse((x - r, y - r, x + r, y + r), fill=255)

    skip = canvas()
    d = ImageDraw.Draw(skip)
    d.polygon([(5 * s, 5.5 * s), (5 * s, 18.5 * s), (14.5 * s, 12 * s)], fill=255)
    d.rounded_rectangle((16.5 * s, 5.5 * s, 19.5 * s, 18.5 * s), radius=1 * s, fill=255)
    close = canvas()
    d = ImageDraw.Draw(close)
    line(d, [(6, 6), (18, 18)])
    line(d, [(18, 6), (6, 18)])
    jump = canvas()
    d = ImageDraw.Draw(jump)
    arc = [(5 + 4 - 4 * math.cos(math.radians(a)), 11 + 4 * math.sin(math.radians(a))) for a in range(0, 91, 10)]
    line(d, [(5, 5), (5, 11)] + arc + [(19, 15)])
    line(d, [(15, 11), (19, 15), (15, 19)])
    play = canvas()
    ImageDraw.Draw(play).polygon([(7.5 * s, 4.8 * s), (7.5 * s, 19.2 * s), (19 * s, 12 * s)], fill=255)
    # Timeline: the dashed arc from the playhead to where Skip lands (stretched to that width)
    arc = Image.new("L", (400, 120), 0)
    arc_draw = ImageDraw.Draw(arc)
    points = []
    for step in range(0, 201):
        t = step / 200.0
        bx = (1 - t) ** 3 * 4 + 3 * (1 - t) ** 2 * t * 88 + 3 * (1 - t) * t * t * 312 + t ** 3 * 396
        by = (1 - t) ** 3 * 120 + 3 * (1 - t) ** 2 * t * 0 + 3 * (1 - t) * t * t * 0 + t ** 3 * 112
        points.append((bx, by))
    for index in range(0, len(points) - 1):
        if (index // 7) % 2 == 0:
            arc_draw.line([points[index], points[index + 1]], fill=255, width=10)
    dot = Image.new("L", (64, 64), 0)
    ImageDraw.Draw(dot).ellipse((0, 0, 63, 63), fill=255)
    # the soft patch behind a text that lies on the video
    from PIL import ImageFilter
    soft = Image.new("L", (256, 96), 0)
    ImageDraw.Draw(soft).rounded_rectangle((30, 22, 226, 74), 22, fill=255)
    soft = soft.filter(ImageFilter.GaussianBlur(11))
    patch_picture = Image.new("RGBA", soft.size, (255, 255, 255, 0))
    patch_picture.putalpha(soft)
    out["cv_txglow.png"] = patch_picture
    # fills cut to their shape: the foot of a tile (round bottom corners), the start of a pill (round left end)
    for folder, radius, cap in (("1080", 28, 38), ("720", 19, 25)):
        big = 4
        mask = Image.new("L", ((2 * radius + 8) * big, (radius + 8) * big), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, -radius * big, mask.size[0] - 1, mask.size[1] - 1), radius * big, fill=255)
        tile = Image.new("RGBA", mask.size, (255, 255, 255, 0))
        tile.putalpha(mask)
        out["cv_fill_v_%s.png" % folder] = tile.resize((2 * radius + 8, radius + 8), Image.LANCZOS)
        mask = Image.new("L", ((cap + 8) * big, 2 * cap * big), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, mask.size[0] + cap * big, mask.size[1] - 1), cap * big, fill=255)
        pill = Image.new("RGBA", mask.size, (255, 255, 255, 0))
        pill.putalpha(mask)
        out["cv_fill_h_%s.png" % folder] = pill.resize((cap + 8, 2 * cap), Image.LANCZOS)
        # the same for a button 60 high: a pill (round end) and a button with the inner corner
        high = 60 if folder == "1080" else 40
        for part, rad in (("p", high // 2), ("b", 16 if folder == "1080" else 11)):
            mask = Image.new("L", ((rad + 8) * big, high * big), 0)
            ImageDraw.Draw(mask).rounded_rectangle((0, 0, mask.size[0] + rad * big, mask.size[1] - 1), rad * big, fill=255)
            cut = Image.new("RGBA", mask.size, (255, 255, 255, 0))
            cut.putalpha(mask)
            out["cv_fill_%s_%s.png" % (part, folder)] = cut.resize((rad + 8, high), Image.LANCZOS)
    arc_picture = Image.new("RGBA", arc.size, (255, 255, 255, 0))
    arc_picture.putalpha(arc)
    out["cv_arc.png"] = arc_picture.resize((200, 60), Image.LANCZOS)
    for name, mask in (("cv_ic_skip.png", skip), ("cv_ic_close.png", close), ("cv_ic_jump.png", jump),
                       ("cv_ic_play.png", play), ("cv_dot.png", dot)):
        picture = Image.new("RGBA", mask.size, (255, 255, 255, 0))
        picture.putalpha(mask.resize(mask.size, Image.LANCZOS))
        out[name] = picture.resize((96, 96), Image.LANCZOS) if name != "cv_dot.png" else picture
    return out


def pictures() -> dict:
    out = icons()
    out["cv_clear.png"] = Image.new("RGBA", (8, 8), (255, 255, 255, 0))
    # masks for a picture of the library: a 16:9 picture with the inner corner of a card (16 of 320 wide),
    # and a small tile with round ends (107 x 60)
    # (and a poster, 2:3, with a corner a tenth of its width)
    for name, size, radius in (("cv_mask_r.png", (640, 360), 32), ("cv_mask_s.png", (428, 240), 120),
                               ("cv_mask_p.png", (240, 360), 24)):
        big = 2
        mask = Image.new("L", (size[0] * big, size[1] * big), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, mask.size[0] - 1, mask.size[1] - 1), radius * big, fill=255)
        tile = Image.new("RGBA", mask.size, (255, 255, 255, 0))
        tile.putalpha(mask)
        out[name] = tile.resize(size, Image.LANCZOS)
    # a fanart behind a card's words: clear at the left where they stand, showing towards the right, cut to the
    # card's corners (and the same with hard corners)
    for name, radius in (("cv_mask_c.png", 28), ("cv_mask_ch.png", 0)):
        wide, high = 780, 200
        shape = Image.new("L", (wide * 2, high * 2), 0)
        ImageDraw.Draw(shape).rounded_rectangle((0, 0, wide * 2 - 1, high * 2 - 1), radius * 2, fill=255)
        shape = shape.resize((wide, high), Image.LANCZOS)
        ramp = Image.new("L", (wide, high))
        px = ramp.load()
        for y in range(high):
            for x in range(wide):
                u = x / float(wide - 1)
                px[x, y] = int(round(255 * (0.10 + 0.62 * max(0.0, (u - 0.25) / 0.75) ** 1.2)))
        tile = Image.new("RGBA", (wide, high), (255, 255, 255, 0))
        from PIL import ImageChops as chops

        tile.putalpha(chops.multiply(shape, ramp))
        out[name] = tile
    # a fill across a card: round at the left, where the card's corners are, straight at the right
    for folder, scale in FOLDERS:
        border = int(cv.BORDERS[folder]["fill_c"].split(",")[0])
        big = 4
        mask = Image.new("L", ((border + 8) * big, (2 * border + 8) * big), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, mask.size[0] + 60 * big, mask.size[1] - 1), int(28 * scale * big), fill=255)
        cut = Image.new("RGBA", mask.size, (255, 255, 255, 0))
        cut.putalpha(mask)
        out["cv_fill_c_%s.png" % folder] = cut.resize((border + 8, 2 * border + 8), Image.LANCZOS)
    # Takeover: the shade over the next episode's picture. Dark at the left, where the texts are, and along the foot.
    take = Image.new("RGBA", (480, 270), (8, 9, 12, 0))
    px = take.load()
    for y in range(270):
        for x in range(480):
            u, v = x / 479.0, 1.0 - y / 269.0
            across = 0.92 - 0.32 * u / 0.42 if u <= 0.42 else (0.6 - 0.52 * (u - 0.42) / 0.33 if u <= 0.75 else 0.08)
            up = 0.7 * max(0.0, 1.0 - v / 0.45)
            px[x, y] = (8, 9, 12, int(round(255 * (1.0 - (1.0 - across) * (1.0 - up)))))
    out["cv_ov_take.png"] = take
    out["cv_black.png"] = Image.new("RGBA", (8, 8), (0, 0, 0, 255))
    for folder, scale in FOLDERS:
        out["cv_shadow_%s.png" % folder] = shadow(scale)
        out["cv_shadow_h_%s.png" % folder] = shadow(scale, radius=0.0)
        out["cv_shadow_s_%s.png" % folder] = shadow(scale, alpha=118, blur=18.0, radius=30.0, small=True)
        out["cv_shadow_s_h_%s.png" % folder] = shadow(scale, alpha=118, blur=18.0, radius=0.0, small=True)
        out["cv_glow_neon_%s.png" % folder] = glow(scale, looks.LOOKS["neon"]["glow"])
    # the stretched shades (white, tinted by the look when drawn): a band, a side, a solid, six corner glows
    def ramp(width, height, fn):
        picture = Image.new("RGBA", (width, height), (255, 255, 255, 0))
        px = picture.load()
        for y in range(height):
            for x in range(width):
                px[x, y] = (255, 255, 255, int(round(255 * max(0.0, min(1.0, fn(x / float(width - 1), y / float(height - 1)))))))
        return picture

    # the band: full at the screen edge, six tenths at 55 percent, clear at the far side
    band = ramp(8, 160, lambda u, v: (0.6 + 0.4 * (v - 0.45) / 0.55) if v >= 0.45 else 0.6 * (v / 0.45) ** 1.3)
    out["cv_ov_band.png"] = band
    out["cv_ov_band_top.png"] = band.transpose(Image.FLIP_TOP_BOTTOM)
    side = ramp(160, 8, lambda u, v: u ** 1.15)
    out["cv_ov_side_r.png"] = side
    out["cv_ov_side_l.png"] = side.transpose(Image.FLIP_LEFT_RIGHT)
    out["cv_ov_solid.png"] = Image.new("RGBA", (8, 8), (255, 255, 255, 255))
    corner = ramp(160, 160, lambda u, v: 1.0 - (((1 - u) ** 2 + (1 - v) ** 2) ** 0.5) / 0.7)
    centre = ramp(240, 160, lambda u, v: 1.0 - (((2 * abs(u - 0.5)) ** 2 + (1 - v) ** 2) ** 0.5) / 0.7)
    out["cv_ov_glow_br.png"] = corner
    out["cv_ov_glow_bl.png"] = corner.transpose(Image.FLIP_LEFT_RIGHT)
    out["cv_ov_glow_tr.png"] = corner.transpose(Image.FLIP_TOP_BOTTOM)
    out["cv_ov_glow_tl.png"] = corner.transpose(Image.FLIP_LEFT_RIGHT).transpose(Image.FLIP_TOP_BOTTOM)
    out["cv_ov_glow_bc.png"] = centre
    out["cv_ov_glow_tc.png"] = centre.transpose(Image.FLIP_TOP_BOTTOM)
    for folder, scale in FOLDERS:
        b_box = cv.BORDERS[folder]["box"]
        out["cv_ghost_%s.png" % folder] = old.rich(2 * b_box + 8, 2 * b_box + 8, b_box, fill=(0, 0, 0, 135))
    # the rounded shades behind a design that has no card: white, tinted by the look when drawn
    for folder, scale in FOLDERS:
        border = cv.BORDERS[folder]["overlay"]
        size = 2 * border + 8
        solid = old.rich(size, size, 44 * scale, fill=(255, 255, 255, 255))
        out["cv_ov_rd_%s.png" % folder] = solid
        fading = solid.copy()
        alpha = fading.getchannel("A")
        ramp = Image.new("L", (size, size))
        px = ramp.load()
        for y in range(size):
            for x in range(size):
                t = min(1.0, (x * 0.64 + y * 0.77) / (size * 1.41 * 0.7))  # along 140 degrees, full at 70 percent
                px[x, y] = int(round(255 * (0.5 + 0.5 * t)))
        from PIL import ImageChops
        fading.putalpha(ImageChops.multiply(alpha, ramp))
        out["cv_ov_rdg_%s.png" % folder] = fading
    for code in looks.CODES:
        for corners in looks.CORNERS:
            key = looks.corner_key(code, corners)
            if corners != "Skin" and not key:
                continue
            out.update(look_pictures(code, key, looks.look(code, corners)))
    return out


# ------------------------------------------------------------------------------ skin file
def slots_xml(folder, offset=0, indent="      ") -> str:
    """The picture slots and the two buttons; ``offset`` shifts the ids for a preview copy."""
    borders = cv.BORDERS[folder]
    out = ""

    def picture(slot, border, visible=""):
        cid, prop = cv.SLOT_IDS[slot] + offset, cv.slot_property(slot, offset)
        cond = "!String.IsEmpty(Window.Property(%s))" % prop
        text = '%s<control type="image" id="%d">\n' % (indent, cid)
        text += "%s  <left>0</left>\n%s  <top>0</top>\n%s  <width>1</width>\n%s  <height>1</height>\n" % ((indent,) * 4)
        text += '%s  <texture%s>$INFO[Window.Property(%s)]</texture>\n' % (indent, ' border="%s"' % border if border else "", prop)
        if slot.startswith("overlay") or slot in ("outline", "fill_c"):
            text += "%s  <colordiffuse>$INFO[Window.Property(%s_c)]</colordiffuse>\n" % (indent, prop)
        text += "%s  <visible>%s</visible>\n%s</control>\n" % (indent, cond + visible, indent)
        return text

    def photo(slot, mask="", aspect="scale", level=indent):
        """A picture of the library (an episode picture, a fanart, a logo): Kodi multiplies it by ``mask``,
        so its corners become clear."""
        cid, prop = cv.SLOT_IDS[slot] + offset, cv.slot_property(slot, offset)
        text = '%s<control type="image" id="%d">\n' % (level, cid)
        text += "%s  <left>0</left>\n%s  <top>0</top>\n%s  <width>1</width>\n%s  <height>1</height>\n" % ((level,) * 4)
        # (not loaded in the background: the picture is in Kodi's cache by then, and it has to be there when the
        # dialog is shown, or the card comes first and its picture a few frames later)
        text += '%s  <texture%s>$INFO[Window.Property(%s)]</texture>\n' % (
            level, ' diffuse="%s"' % mask if mask else "", prop)
        text += "%s  <aspectratio%s>%s</aspectratio>\n" % (level, ' align="left" aligny="bottom"' if aspect == "keep" else "", aspect)
        text += "%s  <visible>!String.IsEmpty(Window.Property(%s))</visible>\n%s</control>\n" % (level, prop, level)
        return text

    skip, close = cv.ID_SKIP + offset, cv.ID_CLOSE + offset
    # Takeover: the next episode's picture behind everything, under a shade of its own
    out += photo("back")
    out += picture("back_shade", 0)
    out += picture("overlay9", borders["overlay"])
    out += picture("overlay", 0)
    # everything but the shade behind the dialog sits in one group, which Size on screen zooms
    width, height = (1280, 720) if folder == "720" else (1920, 1080)
    out += '%s<control type="group" id="%d">\n' % (indent, cv.ID_ZOOM + offset)
    out += "%s  <left>0</left>\n%s  <top>0</top>\n%s  <width>%d</width>\n%s  <height>%d</height>\n" % (
        indent, indent, indent, width, indent, height)
    outer, indent = indent, indent + "  "
    out += picture("shadow", borders["shadow"])
    out += picture("shadow_2", borders["shadow"])
    out += picture("shadow_3", borders["shadow"])
    out += picture("shadow_s", borders["shadow_s"])
    out += picture("shadow_s2", borders["shadow_s"])
    out += picture("shadow_s3", borders["shadow_s"])
    out += picture("plate", borders["plate"])
    out += picture("plate2", borders["plate"])
    out += picture("plate_c", borders["plate_c"])
    out += picture("plate_m", borders["plate_m"])
    out += picture("plate_h", borders["plate_h"])
    # on the card, under its words: a fill that grows across it, or the show's fanart
    out += picture("fill_c", borders["fill_c"])
    out += photo("pic_card", "cv_mask_c.png", level=indent)
    out += photo("pic_card_h", "cv_mask_ch.png", level=indent)
    out += picture("box", borders["box"])
    out += picture("chip", borders["chip"])
    out += picture("box2", borders["box"])
    out += picture("box3", borders["box"])
    out += picture("outline", borders["box"])
    out += photo("pic", "cv_mask_r.png", level=indent)
    out += photo("pic_s", "cv_mask_s.png", level=indent)
    out += photo("pic_h", level=indent)
    out += photo("pic2", "cv_mask_r.png", level=indent)
    out += photo("pic3", "cv_mask_r.png", level=indent)
    out += photo("pic2_h", level=indent)
    out += photo("pic3_h", level=indent)
    out += photo("pic_po", "cv_mask_p.png", level=indent)
    out += photo("pic_po_h", level=indent)
    out += photo("logo", aspect="keep", level=indent)
    if offset:
        # a preview copy shows Skip with the focus and Close without it
        out += picture("skip_on", borders["box"])
        out += picture("close_off", borders["box"])
        out += picture("more_off", borders["box"])
        out += picture("fill_v", borders["fill_v"])
        out += picture("fill_h", borders["fill_h"])
        out += picture("fill_b", borders["fill_b"])
        out += picture("fill_p", borders["fill_p"])
        return out + "%s</control>\n" % outer
    out += picture("skip_off", borders["box"], " + !Control.HasFocus(%d)" % skip)
    out += picture("skip_on", borders["box"], " + Control.HasFocus(%d)" % skip)
    out += picture("close_off", borders["box"], " + !Control.HasFocus(%d)" % close)
    out += picture("close_on", borders["box"], " + Control.HasFocus(%d)" % close)
    more = cv.ID_MORE + offset
    out += picture("more_off", borders["box"], " + !Control.HasFocus(%d)" % more)
    out += picture("more_on", borders["box"], " + Control.HasFocus(%d)" % more)
    out += picture("fill_v", borders["fill_v"])
    out += picture("fill_h", borders["fill_h"])
    out += picture("fill_b", borders["fill_b"])
    out += picture("fill_p", borders["fill_p"])
    for cid, other in ((skip, close), (close, skip)):
        out += '%s<control type="button" id="%d">\n' % (indent, cid)
        out += "%s  <left>0</left>\n%s  <top>0</top>\n%s  <width>1</width>\n%s  <height>1</height>\n" % ((indent,) * 4)
        out += "%s  <label></label>\n%s  <texturefocus>-</texturefocus>\n%s  <texturenofocus>-</texturenofocus>\n" % ((indent,) * 3)
        out += "%s  <onleft>%d</onleft>\n%s  <onright>%d</onright>\n%s  <onup>%d</onup>\n%s  <ondown>%d</ondown>\n" % (
            indent, other, indent, other, indent, other, indent, other)
        out += "%s</control>\n" % indent
    # a third button and the places that only take the focus: unseen (so the focus cannot land there) until
    # a design places them. Where Left, Right, Up and Down go from each is set by the dialog.
    for name, cid in [("more", more)] + [(name, cid + offset) for name, cid in sorted(cv.HOT_IDS.items())]:
        out += '%s<control type="button" id="%d">\n' % (indent, cid)
        out += "%s  <left>0</left>\n%s  <top>0</top>\n%s  <width>1</width>\n%s  <height>1</height>\n" % ((indent,) * 4)
        out += "%s  <label></label>\n%s  <texturefocus>-</texturefocus>\n%s  <texturenofocus>-</texturenofocus>\n" % ((indent,) * 3)
        out += "%s  <visible>!String.IsEmpty(Window.Property(cv_hot_%s))</visible>\n" % (indent, name)
        out += "%s</control>\n" % indent
    return out + "%s</control>\n" % outer


def skin_xml(folder) -> str:
    width, height = (1920, 1080) if folder == "1080" else (1280, 720)
    probe = cv.PROBE_W if folder == "720" else cv.PROBE_W * 3 // 2
    return ("""<?xml version='1.0' encoding='utf-8'?>
<!-- Written by tools/gen_skip_canvas.py: edit that, not this file. -->
<window>
  <coordinates>
    <system>1</system>
    <posx>0</posx>
    <posy>0</posy>
    <width>%d</width>
    <height>%d</height>
  </coordinates>
  <zorder>1</zorder>
  <defaultcontrol>%d</defaultcontrol>
  <!-- Nothing of the dialog is seen while Skippy is putting it together: the texts it adds are on the window
       itself, and would show at their font's own size until each has been given its place and size. The flag is
       on the Home window (a window's own animation does not see its own properties) and only says "busy", so a
       drawing that fails leaves the dialog seen. -->
  <animation effect="fade" start="100" end="0" time="0" condition="String.IsEqual(Window(Home).Property(skippy_canvas_busy),true)">Conditional</animation>
  <controls>
    <control type="image" id="%d">
      <left>0</left>
      <top>0</top>
      <width>%d</width>
      <height>1</height>
      <texture>cv_clear.png</texture>
    </control>
    <control type="group" id="%d">
      <left>0</left>
      <top>0</top>
      <width>%d</width>
      <height>%d</height>
      <!-- always there, so a button in it can take the focus before the dialog is shown: what hides the
           dialog until then is the flag above, and its parts come with the animations Skippy gives them -->
      <!-- a still behind the dialog: only the test harness sets it (a control made in Python would cover the slots) -->
      <control type="image">
        <left>0</left>
        <top>0</top>
        <width>%d</width>
        <height>%d</height>
        <texture>$INFO[Window.Property(cv_test_backdrop)]</texture>
        <aspectratio>scale</aspectratio>
        <visible>!String.IsEmpty(Window.Property(cv_test_backdrop))</visible>
      </control>
""" % (width, height, cv.ID_SKIP, cv.ID_PROBE, probe, cv.ID_ROOT, width, height, width, height)
            + slots_xml(folder) + "    </control>\n  </controls>\n</window>\n")


def skin_files() -> dict:
    # the 1080i file is the 720p one through the converter, like every other pair (it scales the borders too)
    text = skin_xml("720")
    return {os.path.join(SKINS, "720p", cv.XML): text, os.path.join(SKINS, "1080i", cv.XML): gen.convert(text)}


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
    print("%d skin files, %d pictures, %d written" % (len(texts), len(images), len(todo)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
