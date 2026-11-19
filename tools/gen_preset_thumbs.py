# -*- coding: utf-8 -*-
"""Draw a miniature of every skip dialog layout in every look: the tiles of the preset wall.

    python tools/gen_skip_layouts.py            (first: the miniatures are drawn from its skin files)
    python tools/gen_preset_thumbs.py           (write what is missing or changed)
    python tools/gen_preset_thumbs.py --check   (exit 1 when a file is missing or differs)

A miniature is the 720p skin file of a layout (``SkipLayout_<name>.xml``) drawn on a whole
1280 x 720 screen in the colours of a look and scaled down to 320 x 180: plates, buttons, bars and
rings as they are, every line of text as a bar of its length class (no font is needed, so the
pictures are the same on every machine). The dialog sits bottom right (or where its anchor puts
it), a third of the segment has run, and Skip has the focus.

Output: ``resources/skins/default/media/pt_<Layout>_<look>.png`` (``skip_layouts.thumb``).
"""
from __future__ import annotations

import io
import os
import re
import sys
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
for _path in (ROOT, TOOLS):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import gen_skip_layouts as layouts_gen  # noqa: E402
import skip_layouts as sl  # noqa: E402

SKINS = os.path.join(ROOT, "resources", "skins", "default")
MEDIA = os.path.join(SKINS, "media")
W, H = sl.CANVAS_W, sl.CANVAS_H
OUT_W, OUT_H = 320, 180
PROGRESS = 35.0  # percent of the segment that has run in the picture
TYPE_COLOUR = "FFE8B04B"  # an intro
TEXT_H = {"font10": 8, "font11": 9, "font12": 10, "font13": 12, "font16": 14, "font30": 22}
PROP = re.compile(r"Window\.Property\(([a-z0-9_]+)\)")


def rgba(argb):
    text = str(argb or "FFFFFFFF")
    return tuple(int(text[i:i + 2], 16) for i in (2, 4, 6, 0))


def backdrop() -> Image.Image:
    """Something like a film frame: a soft diagonal sweep, lighter at the top left."""
    small = Image.new("RGB", (32, 18))
    pixels = small.load()
    for y in range(18):
        for x in range(32):
            t = (x / 31.0 + y / 17.0) / 2.0
            pixels[x, y] = (int(96 - 62 * t), int(112 - 70 * t), int(132 - 74 * t))
    return small.resize((W, H), Image.BICUBIC).convert("RGBA")


def paint(canvas, box, fill, radius=0.0, edge=None):
    left, top, right, bottom = [int(round(v)) for v in box]
    if right <= left or bottom <= top:
        return
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    radius = max(0.0, min(radius, (right - left) / 2.0, (bottom - top) / 2.0))
    draw.rounded_rectangle((left, top, right - 1, bottom - 1), radius=radius, fill=fill, outline=edge, width=2 if edge else 0)
    canvas.alpha_composite(layer)


def arc(canvas, box, colour, share, width):
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    box = [int(round(v)) for v in box]
    if share >= 1.0:
        draw.ellipse(box, outline=colour, width=width)
    else:
        draw.arc(box, -90, -90 + 360.0 * share, fill=colour, width=width)
    canvas.alpha_composite(layer)


def drawn(control) -> bool:
    """False for the half of a focus pair that is not shown: Skip has the focus, Close has not."""
    cond = control.findtext("visible") or ""
    for cid, focused in ((sl.ID_SKIP, True), (sl.ID_CLOSE, False)):
        if "Control.HasFocus(%d)" % cid in cond:
            wants_focus = "!Control.HasFocus(%d)" % cid not in cond
            return wants_focus == focused
    if "skl_top" in cond:
        return cond.startswith("!")  # the bottom band
    return True


_PICTURES = {}


def nine(name, width, height, border) -> Image.Image:
    """A picture of the skin stretched the way Kodi does it: the corners keep their size."""
    if not _PICTURES:
        _PICTURES.update(layouts_gen.pictures())
    source = _PICTURES[name].convert("RGBA")
    sw, sh = source.size
    b = max(0, min(int(border), sw // 2 - 1, sh // 2 - 1, width // 2, height // 2))
    out = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    xs = ((0, b, 0, b), (b, sw - b, b, width - b), (sw - b, sw, width - b, width))
    ys = ((0, b, 0, b), (b, sh - b, b, height - b), (sh - b, sh, height - b, height))
    for sx0, sx1, dx0, dx1 in xs:
        for sy0, sy1, dy0, dy1 in ys:
            if sx1 > sx0 and sy1 > sy0 and dx1 > dx0 and dy1 > dy0:
                out.paste(source.crop((sx0, sy0, sx1, sy1)).resize((dx1 - dx0, dy1 - dy0), Image.BILINEAR), (dx0, dy0))
    return out


def stamp(canvas, box, name, border):
    left, top, right, bottom = [int(round(v)) for v in box]
    if right > left and bottom > top:
        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        layer.paste(nine(name, right - left, bottom - top, border), (left, top))
        canvas.alpha_composite(layer)


def render(layout, code) -> Image.Image:
    bare = sl.is_bare(layout.name)
    look = sl.look(code, bare)
    props = sl.properties(code, "720p", bare)
    bar = sl.BAR_LOOK if code in sl.OWN_LOOKS else sl.BAR_TYPE
    props["skl_accent"] = sl.accent(code, bar, TYPE_COLOUR[2:], bare)
    canvas = backdrop()
    ox, oy = sl.origin(layout, "BottomRight")
    with open(os.path.join(SKINS, "720p", layout.xml), encoding="utf-8") as handle:
        root = ET.fromstring(handle.read().split("?>", 1)[1])
    group = next(c for c in root.iter("control") if c.get("id") == str(sl.ID_ROOT))
    fill_box = sl.fill_size(layout, PROGRESS)

    def colour_of(text, default="FFFFFFFF"):
        found = PROP.search(text or "")
        if found:
            return rgba(props.get(found.group(1), default))
        return rgba(text) if re.fullmatch(r"[0-9A-Fa-f]{8}", text or "") else rgba(default)

    for control in group.findall("control"):
        if not drawn(control):
            continue
        left, top, width, height = [int(control.findtext(tag) or 0) for tag in ("left", "top", "width", "height")]
        cid = int(control.get("id") or 0)
        kind = control.get("type")
        if kind == "image":
            texture = control.findtext("texture") or ""
            diffuse = control.findtext("colordiffuse") or ""
            if cid == sl.ID_BAR_FILL:
                left, top, width, height = fill_box
            elif cid == sl.ID_PLAYHEAD:
                left = fill_box[0] + fill_box[2] - 1
            elif cid == sl.ID_NESTED:
                left, width = layout.track[0] + int(layout.track[2] * 0.6), sl.JUMP_MARK_W
            box = (ox + left, oy + top, ox + left + width, oy + top + height)
            part = PROP.search(texture)
            if part and part.group(1) in ("skl_plate", "skl_slab", "skl_tile", "skl_button", "skl_focus"):
                border = (control.find("texture").get("border") or "0").split(",")[0]
                stamp(canvas, box, props[part.group(1)], border)
            elif "skl_poster" in texture:
                paint(canvas, box, (150, 122, 96, 255), 0)
                paint(canvas, (box[0], box[1] + (box[3] - box[1]) * 0.55, box[2], box[3]), (60, 52, 70, 255), 0)
            elif "skl_ring" in texture:
                arc(canvas, box, colour_of(diffuse), PROGRESS / 100.0, max(4, width // 9))
            elif texture.startswith("sl_ring_"):
                arc(canvas, box, colour_of(diffuse), 1.0, max(4, width // 9))
            elif texture == "sl_shade.png":
                paint(canvas, (box[0] + 16, box[1] + 16, box[2] - 16, box[3] - 16), (6, 8, 12, 165), 30)
            elif texture.startswith("sl_band"):
                steps = 24
                for step in range(steps):
                    share = ((step + 1) / float(steps)) ** 1.6
                    y0 = box[1] + (box[3] - box[1]) * step / float(steps)
                    paint(canvas, (box[0], y0, box[2], y0 + (box[3] - box[1]) / float(steps) + 1), (4, 5, 8, int(224 * share)))
            elif texture == "sl_white.png":
                paint(canvas, box, colour_of(diffuse))
        elif kind in ("label", "button"):
            if kind == "button":
                colour = rgba(look.focus_text if cid == sl.ID_SKIP else look.button_text)
                align, share, text_h = "center", 0.42, 10
            else:
                colour = colour_of(control.findtext("textcolor"))
                align = control.findtext("align") or "left"
                share = 0.34 if width > 600 else 0.62
                text_h = TEXT_H.get(control.findtext("font") or "font10", 9)
            if not (control.findtext("label") or "").strip():
                continue
            bar_w = max(12, min(int(width * share), 360))
            x = ox + left + (0 if align == "left" else (width - bar_w) if align == "right" else (width - bar_w) // 2)
            y = oy + top + (height - text_h) // 2
            paint(canvas, (x, y, x + bar_w, y + text_h), colour, text_h / 2.0)
    # Close in on the dialog: a 16:9 window around it with some of the picture left, so a small
    # corner dialog fills the tile as well as a band across the screen does.
    crop_w = min(W, max(layout.width + 96, int((layout.height + 96) * 16 / 9.0), 520))
    crop_h = int(round(crop_w * 9 / 16.0))
    left = max(0, min(W - crop_w, ox + layout.width // 2 - crop_w // 2))
    top = max(0, min(H - crop_h, oy + layout.height // 2 - crop_h // 2))
    return canvas.convert("RGB").crop((left, top, left + crop_w, top + crop_h)).resize((OUT_W, OUT_H), Image.LANCZOS)


_CANVAS_PICTURES = {}


def render_canvas(name, code) -> Image.Image:
    """The miniature of a drawn design: its drawing list (skip_canvas) painted with the real pictures."""
    import gen_skip_canvas as canvas_gen
    import skip_canvas as cv
    import skip_canvas_looks as cvlooks

    if not _CANVAS_PICTURES:
        _CANVAS_PICTURES.update(canvas_gen.pictures())
    look = cvlooks.look(code)
    drawing = cv.draw(cv.Options(design=name, look=code), cv.Texts())
    big = backdrop().resize((1920, 1080), Image.LANCZOS)

    def nine_of(picture_name, width, height, border):
        source = _CANVAS_PICTURES[picture_name].convert("RGBA")
        sw, sh = source.size
        b = max(0, min(int(border), sw // 2 - 1, sh // 2 - 1, width // 2, height // 2))
        out = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        for sx0, sx1, dx0, dx1 in ((0, b, 0, b), (b, sw - b, b, width - b), (sw - b, sw, width - b, width)):
            for sy0, sy1, dy0, dy1 in ((0, b, 0, b), (b, sh - b, b, height - b), (sh - b, sh, height - b, height)):
                if sx1 > sx0 and sy1 > sy0 and dx1 > dx0 and dy1 > dy0:
                    out.paste(source.crop((sx0, sy0, sx1, sy1)).resize((dx1 - dx0, dy1 - dy0), Image.BILINEAR), (dx0, dy0))
        return out

    def put(picture_name, rect, border):
        x, y, w, h = [int(round(v)) for v in rect]
        if w > 0 and h > 0 and picture_name in _CANVAS_PICTURES:
            layer = Image.new("RGBA", big.size, (0, 0, 0, 0))
            layer.paste(nine_of(picture_name, w, h, border), (x, y))
            big.alpha_composite(layer)

    borders = cv.BORDERS["1080"]
    for op in drawing.ops:
        kind, rect = op["t"], op["rect"]
        if kind == "slot":
            slot = op["slot"]
            if op.get("tex") == "shadow":
                small = slot.startswith("shadow_s")
                put("cv_shadow%s%s_1080.png" % ("_s" if small else "", "_h" if look["r"] == 0 else ""), rect,
                    borders["shadow_s" if small else "shadow"])
            elif op.get("tex") == "glow":
                put("cv_glow_%s_1080.png" % code, rect, borders["shadow"])
            elif op.get("tex"):
                put(op["tex"], rect, 0)
            else:
                part = {"plate": "plate", "plate2": "plate", "plate_c": "platec", "plate_m": "platem", "plate_h": "plate", "box": "box",
                        "chip": "chip", "box2": "box", "box3": "box", "outline": "outl"}.get(slot)
                if part:
                    border = borders["box"] if slot in ("box2", "box3", "outline") else borders.get(slot, borders["plate"])
                    put(cv.picture(code, drawing.corners, part, "1080"), rect, border)
        elif kind == "button":
            focused = op["which"] == "skip"
            part = ("pillfoc" if focused else "pill") if op.get("pill") else ("foc" if focused else "btn")
            if op.get("off") in ("tile", "ptile"):
                part = "tile" if focused else "ptile"
            if not op.get("bare") and not (op.get("ghost") and not focused):
                put(cv.picture(code, drawing.corners, part, "1080"), rect, borders["box"])
        elif kind == "fillslot":
            colour = cv.ink(look, op.get("ink"), op.get("ink") == "skip")
            colour = colour[:3] + (int(colour[3] * op.get("share", 1.0)),)
            paint(big, (rect[0], rect[1], rect[0] + rect[2], rect[1] + rect[3]), colour, 0)
        elif kind == "rect":
            colour = op.get("color") or cv.ink(look, op.get("ink"), op.get("ink") == "skip")
            paint(big, (rect[0], rect[1], rect[0] + rect[2], rect[1] + rect[3]), colour, min(rect[2], rect[3]) / 2.0)
        elif kind == "img":
            if op.get("tex") == "cv_arc.png":
                continue
            colour = op.get("color") or cv.ink(look, op.get("ink") or op.get("ink_acc") or op.get("bg"),
                                               (op.get("ink") or op.get("ink_acc")) == "skip")
            paint(big, (rect[0] + 3, rect[1] + 3, rect[0] + rect[2] - 3, rect[1] + rect[3] - 3), colour, rect[2] / 2.0)
        elif kind == "text":
            colour = op.get("color") or cv.ink(look, op.get("ink"), op.get("ink") == "skip")
            width = min(rect[2], cv.estimate(re.sub(r"\[/?B\]", "", op["text"]), op["size"], op.get("bold")))
            bar_h = max(4.0, op["size"] * 0.42)
            x = rect[0] if op.get("align", "l") == "l" else rect[0] + rect[2] - width if op["align"] == "r" else rect[0] + (rect[2] - width) / 2.0
            y = rect[1] + (rect[3] - bar_h) / 2.0
            paint(big, (x, y, x + width, y + bar_h), colour, bar_h / 2.0)
    crop_w = int(max(drawing.width + 150, (drawing.height + 150) * 16 / 9.0, 780))
    crop_h = int(round(crop_w * 9 / 16.0))
    left = int(max(0, min(1920 - crop_w, drawing.left + drawing.width / 2.0 - crop_w / 2.0)))
    top = int(max(0, min(1080 - crop_h, drawing.top + drawing.height / 2.0 - crop_h / 2.0)))
    return big.convert("RGB").crop((left, top, left + crop_w, top + crop_h)).resize((OUT_W, OUT_H), Image.LANCZOS)


def pictures() -> dict:
    out = {}
    for name in sl.NEW_LAYOUTS:
        for code in sl.LOOKS:
            if sl.is_canvas(name):
                out[sl.thumb(name, code)] = render_canvas(name, code)
            else:
                out[sl.thumb(name, code)] = render(sl.get(name, sl.SIZE_FULL), code)
    return out


def _png(picture) -> bytes:
    buffer = io.BytesIO()
    picture.save(buffer, "PNG", optimize=True)
    return buffer.getvalue()


def stale() -> list:
    out = []
    for name, picture in pictures().items():
        path = os.path.join(MEDIA, name)
        try:
            with Image.open(path) as found:
                same = found.size == picture.size and found.convert("RGB").tobytes() == picture.tobytes()
        except OSError:
            same = False
        if not same:
            out.append(name)
    return out


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    todo = stale()
    if "--check" in argv:
        for name in todo:
            print("stale or missing:", name)
        return 1 if todo else 0
    images = pictures()
    for name in todo:
        with open(os.path.join(MEDIA, name), "wb") as handle:
            handle.write(_png(images[name]))
    print("%d miniatures, %d written" % (len(images), len(todo)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
