# -*- coding: utf-8 -*-
"""Write the textures of the five window looks into resources/skins/default/media.

    python3 tools/gen_modal_style_textures.py

For each look (see skippy_modal_style.py) a flat ms_<code>_dim.png (the dim behind a window) and four 9-slice pictures: ms_<code>_panel.png (border 28),
ms_<code>_inset.png, ms_<code>_row.png and ms_<code>_focus.png (border 14). Drawn at four times the
size and scaled down, so the corners are smooth. Kodi cannot blur the video behind an add-on window,
so Frost is a lighter, milky panel rather than a blurred one.
"""
from __future__ import annotations

import os
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import segment_editor_layout as layout  # noqa: E402
import skippy_modal_style as style  # noqa: E402

MEDIA = os.path.join(ROOT, "resources", "skins", "default", "media")
SS = 4  # supersampling

# radius of the panel / of rows and buttons, then RGBA fills and 1 px edges (None = no edge)
LOOKS = {
    "fgd": dict(dim=(5, 6, 8, 184), r=28, ri=14, panel=(20, 23, 28, 245), panel_edge=(255, 255, 255, 24),
                inset=(0, 0, 0, 60), row=(255, 255, 255, 26), row_edge=None,
                focus=(255, 255, 255, 255), focus_edge=None),
    "fgf": dict(dim=(5, 6, 8, 150), r=28, ri=14, panel=(84, 92, 108, 236), panel_edge=(255, 255, 255, 104),
                inset=(0, 0, 0, 44), row=(255, 255, 255, 46), row_edge=None,
                focus=(255, 255, 255, 255), focus_edge=None),
    "fgc": dict(dim=(5, 6, 8, 115), r=28, ri=14, panel=(14, 16, 22, 150), panel_edge=(255, 255, 255, 84),
                inset=(0, 0, 0, 76), row=(255, 255, 255, 40), row_edge=None,
                focus=(255, 255, 255, 255), focus_edge=None),
    "aeo": dict(dim=(0, 0, 0, 204), r=0, ri=0, panel=(12, 12, 12, 238), panel_edge=None,
                inset=(255, 255, 255, 15), row=(255, 255, 255, 23), row_edge=None,
                focus=(255, 255, 255, 255), focus_edge=None),
    "agl": dict(dim=(0, 0, 0, 128), r=16, ri=8, panel=(34, 37, 46, 150), panel_edge=(255, 255, 255, 86),
                inset=(0, 0, 0, 60), row=(255, 255, 255, 18), row_edge=(255, 255, 255, 48),
                focus=(255, 255, 255, 72), focus_edge=(255, 255, 255, 200)),
}


def rounded(size: int, radius: int, fill, edge=None) -> Image.Image:
    """A square 9-slice picture: ``fill`` with an optional 1 px ``edge`` just inside its outline."""
    big = size * SS
    layer = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    box = (0, 0, big - 1, big - 1)
    if edge:
        draw.rounded_rectangle(box, radius=radius * SS, fill=edge)
        inner = (SS, SS, big - 1 - SS, big - 1 - SS)
        hole = Image.new("L", (big, big), 0)
        ImageDraw.Draw(hole).rounded_rectangle(inner, radius=max(0, radius - 1) * SS, fill=255)
        fill_layer = Image.new("RGBA", (big, big), fill)
        layer.paste(fill_layer, (0, 0), hole)
    else:
        draw.rounded_rectangle(box, radius=radius * SS, fill=fill)
    return layer.resize((size, size), Image.LANCZOS)


def frame(size: int, radius: int, width: int = 2) -> Image.Image:
    """A square 9-slice picture: a white line round nothing."""
    big = size * SS
    layer = Image.new("RGBA", (big, big), (255, 255, 255, 0))
    ImageDraw.Draw(layer).rounded_rectangle((SS // 2, SS // 2, big - 1 - SS // 2, big - 1 - SS // 2), radius=radius * SS,
                                            outline=(255, 255, 255, 255), width=width * SS)
    return layer.resize((size, size), Image.LANCZOS)


def build() -> dict:
    """File name -> image for every texture of every look."""
    out = {}
    for code, look in LOOKS.items():
        out["ms_%s_panel.png" % code] = rounded(96, look["r"], look["panel"], look["panel_edge"])
        out["ms_%s_inset.png" % code] = rounded(64, look["ri"], look["inset"])
        out["ms_%s_row.png" % code] = rounded(64, look["ri"], look["row"], look["row_edge"])
        out["ms_%s_focus.png" % code] = rounded(64, look["ri"], look["focus"], look["focus_edge"])
        out["ms_%s_dim.png" % code] = Image.new("RGBA", (16, 16), look["dim"])
    # one chip per segment type (list rows, and the blocks on the editor's timeline; 9-slice border 4)
    for key, rgb in layout.CHIP_COLORS.items():
        colour = tuple(int(rgb[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
        out["seg_%s.png" % key] = rounded(16, 4, colour)
    # a white frame: round the highlighted segment on the editor's timeline (9-slice border 10)
    out["seg_frame.png"] = frame(40, 9)
    # the blocks of the editor's timeline: the type's colour with round corners (9-slice border 10)
    for key, rgb in layout.CHIP_COLORS.items():
        colour = tuple(int(rgb[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
        out["segb_%s.png" % key] = rounded(40, 9, colour)
    # flat white with round corners, tinted where it is drawn: a flag, a tag, a handle (9-slice border 6)
    out["seg_tag.png"] = rounded(24, 5, (255, 255, 255, 255))
    out["seg_flat.png"] = Image.new("RGBA", (8, 8), (255, 255, 255, 255))
    # the marker on top of the playhead
    head = Image.new("RGBA", (14 * SS, 10 * SS), (255, 255, 255, 0))
    ImageDraw.Draw(head).polygon([(0, 0), (14 * SS - 1, 0), (7 * SS, 10 * SS - 1)], fill=(255, 255, 255, 255))
    out["seg_head.png"] = head.resize((14, 10), Image.LANCZOS)
    return out


def main() -> int:
    assert set(LOOKS) == set(style.STYLE_CODES.values()), "looks and skippy_modal_style.STYLE_CODES differ"
    assert all(look["r"] <= style.PANEL_BORDER and look["ri"] <= style.ROW_BORDER for look in LOOKS.values())
    for name, image in sorted(build().items()):
        image.save(os.path.join(MEDIA, name), optimize=True)
        print("wrote", name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
