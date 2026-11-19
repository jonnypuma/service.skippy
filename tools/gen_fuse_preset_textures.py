# -*- coding: utf-8 -*-
"""Write the textures of the Fuse presets into resources/skins/default/media.

    python tools/gen_fuse_preset_textures.py            (write what is missing or changed)
    python tools/gen_fuse_preset_textures.py --check    (exit 1 when a file is missing or differs)

The Fuse presets give the skip dialog and the next episode popup the looks of the skin Aeon Fuse
(Fused Glass Dark / Frost / Clear, Fused Glass style, Aeon, Aeon Glass):

* ``skip_card_*.png`` - the card behind the Full dialog and the popup, 96x96, nine-slice border
  ``skip_dialog_card.BORDER``. Same fills and edges as the window looks of
  ``gen_modal_style_textures.py``.
* ``button_focus_fuse_*.png`` - 64x25 focus pictures, nine-slice ``12,12,12,12``.
* ``progress_mid_fuse_*.png`` - 512x16 flat bars. They are as high as ``progress_background.png``:
  Kodi's progress control scales the fill by the height of the track picture, so a 32 px fill on
  the 16 px track is drawn twice as high as the bar and too low.
* ``minimal_fuse_*_640.png`` - 640x246 Minimal plates and their eight widths in ``media/plates``.
  A plate is drawn twice (picture and focus overlay), so a see-through plate is authored at the
  alpha that gives the wanted one after two layers.

Everything is drawn at four times the size and scaled down, so the corners are smooth.
"""
from __future__ import annotations

import io
import math
import os
import sys

from PIL import Image, ImageDraw

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
for _path in (ROOT, TOOLS):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import gen_minimal_plate_variants as plate_variants  # noqa: E402
import gen_modal_style_textures as window_looks  # noqa: E402
import skip_dialog_card  # noqa: E402

MEDIA = os.path.join(ROOT, "resources", "skins", "default", "media")
PLATES = os.path.join(MEDIA, "plates")
SS = 4

CARD_SIZE = 96
BTN_W, BTN_H = 64, 25
BAR_W, BAR_H = 512, 16
PLATE_W, PLATE_H = 640, 246

WHITE = (255, 255, 255, 255)
ACCENT_GOLD = (232, 176, 75, 255)  # ms_accent of the Fused Glass looks


def shape(width, height, radius, fill, edge=None, stroke=1.0, bar=0.0, bar_fill=WHITE):
    """A rounded rectangle with an optional edge just inside its outline and a bar at the left."""
    big_w, big_h = width * SS, height * SS
    outline = Image.new("L", (big_w, big_h), 0)
    ImageDraw.Draw(outline).rounded_rectangle((0, 0, big_w - 1, big_h - 1), radius=radius * SS, fill=255)
    layer = Image.new("RGBA", (big_w, big_h), (0, 0, 0, 0))
    if edge:
        layer.paste(Image.new("RGBA", (big_w, big_h), edge), (0, 0), outline)
        inset = int(round(stroke * SS))
        hole = Image.new("L", (big_w, big_h), 0)
        ImageDraw.Draw(hole).rounded_rectangle(
            (inset, inset, big_w - 1 - inset, big_h - 1 - inset), radius=max(0.0, radius - stroke) * SS, fill=255)
        layer.paste(Image.new("RGBA", (big_w, big_h), fill), (0, 0), hole)
    else:
        layer.paste(Image.new("RGBA", (big_w, big_h), fill), (0, 0), outline)
    if bar:
        strip = Image.new("L", (big_w, big_h), 0)
        ImageDraw.Draw(strip).rectangle((0, 0, int(round(bar * SS)) - 1, big_h - 1), fill=255)
        mask = Image.new("L", (big_w, big_h), 0)
        mask.paste(strip, (0, 0), outline)
        layer.paste(Image.new("RGBA", (big_w, big_h), bar_fill), (0, 0), mask)
    return layer.resize((width, height), Image.LANCZOS)


def twice(rgba):
    """The colour whose alpha, drawn twice, gives the alpha of ``rgba``."""
    alpha = 1.0 - math.sqrt(max(0.0, 1.0 - rgba[3] / 255.0))
    return rgba[:3] + (int(round(alpha * 255)),)


def cards() -> dict:
    looks = window_looks.LOOKS
    radius = skip_dialog_card.BORDER
    out = {"skip_card_round.png": shape(CARD_SIZE, CARD_SIZE, radius, (0, 0, 0, 255))}
    for code in ("fgd", "fgf", "fgc"):
        out["skip_card_%s.png" % code] = shape(
            CARD_SIZE, CARD_SIZE, radius, looks[code]["panel"], looks[code]["panel_edge"])
    out["skip_card_fgs.png"] = shape(CARD_SIZE, CARD_SIZE, 0, (7, 8, 10, 194), (255, 255, 255, 71))
    out["skip_card_agl.png"] = shape(
        CARD_SIZE, CARD_SIZE, min(radius, looks["agl"]["r"]), looks["agl"]["panel"], looks["agl"]["panel_edge"])
    return out


def buttons() -> dict:
    return {
        # Aeon: the hard white focus bar
        "button_focus_fuse_square.png": shape(BTN_W, BTN_H, 0, WHITE),
        # Aeon Glass: a pane of lighter glass with a bright edge
        "button_focus_fuse_glass.png": shape(BTN_W, BTN_H, 8, (255, 255, 255, 69), (255, 255, 255, 194)),
        # Fused Glass style: a faint fill, hairline edges and the white bar at the left
        "button_focus_fuse_bar.png": shape(BTN_W, BTN_H, 0, (255, 255, 255, 28), (255, 255, 255, 71), bar=5),
    }


def bars() -> dict:
    return {
        "progress_mid_fuse_gold.png": Image.new("RGBA", (BAR_W, BAR_H), ACCENT_GOLD),
        "progress_mid_fuse_white.png": Image.new("RGBA", (BAR_W, BAR_H), (248, 250, 252, 255)),
    }


def plates() -> dict:
    pill = PLATE_H / 2.0
    edge = 5.0  # about one screen pixel once the plate is drawn 46 units high
    return {
        "minimal_fuse_dark_640.png": shape(
            PLATE_W, PLATE_H, pill, twice((20, 23, 28, 245)), twice((255, 255, 255, 40)), stroke=edge),
        "minimal_fuse_frost_640.png": shape(
            PLATE_W, PLATE_H, pill, twice((84, 92, 108, 236)), twice((255, 255, 255, 104)), stroke=edge),
        "minimal_fuse_clear_640.png": shape(
            PLATE_W, PLATE_H, pill, twice((14, 16, 22, 150)), twice((255, 255, 255, 84)), stroke=edge),
        "minimal_fuse_square_640.png": shape(PLATE_W, PLATE_H, 0, WHITE),
        "minimal_fuse_grid_640.png": shape(
            PLATE_W, PLATE_H, 0, twice((7, 8, 10, 194)), twice((255, 255, 255, 71)), stroke=edge, bar=30),
        "minimal_fuse_glass_640.png": shape(
            PLATE_W, PLATE_H, 43, twice((34, 37, 46, 150)), twice((255, 255, 255, 110)), stroke=edge),
    }


def build() -> dict:
    """Path relative to the media folder -> image, for every texture of the Fuse presets."""
    out = {}
    out.update(cards())
    out.update(buttons())
    out.update(bars())
    for name, image in plates().items():
        out[name] = image
        stem = os.path.splitext(name)[0]
        for width in plate_variants.WIDTHS_720:
            out["plates/%s_w%d.png" % (stem, width)] = plate_variants.render_variant(image, width)
    return out


def _png(image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, "PNG", optimize=True)
    return buffer.getvalue()


def stale() -> list:
    """Files that are missing or differ from what this script draws."""
    out = []
    for name, image in build().items():
        path = os.path.join(MEDIA, *name.split("/"))
        try:
            with Image.open(path) as found:
                same = found.convert("RGBA").tobytes() == image.convert("RGBA").tobytes() and found.size == image.size
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
            print("stale:", name)
        return 1 if todo else 0
    os.makedirs(PLATES, exist_ok=True)
    images = build()
    for name in todo:
        path = os.path.join(MEDIA, *name.split("/"))
        with open(path, "wb") as handle:
            handle.write(_png(images[name]))
        print("wrote", name)
    print("%d textures, %d written" % (len(images), len(todo)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
