# -*- coding: utf-8 -*-
"""Write the next episode popup layouts besides the classic card: ``NextLayout_<name>.xml``.

    python tools/gen_skip_layouts.py            (first: it writes the pictures of the looks)
    python tools/gen_next_layouts.py            (write what is missing or changed)
    python tools/gen_next_layouts.py --check    (exit 1 when a file is missing or differs)

One file per layout of ``next_layouts.py``, in ``720p`` and, through ``gen_skin_1080i.convert()``,
in ``1080i``. A file holds no text, colour or picture of a look: the looks are the six of the
skip dialog layouts (the ``skl_*`` window properties and ``sl_*.png`` pictures), the texts and the
pictures of the episode are ``nl_*`` properties that ``next_layout_dialog.py`` sets.
"""
from __future__ import annotations

import os
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
for _path in (ROOT, TOOLS):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import gen_skin_1080i as gen  # noqa: E402
import gen_skip_layouts as g  # noqa: E402
import next_layouts as nl  # noqa: E402
import skip_layouts as sl  # noqa: E402

SKINS = os.path.join(ROOT, "resources", "skins", "default")
P = g.P
image, label, button = g.image, g.label, g.button

HEADING = P % "nl_heading"
EPISODE = P % "nl_label"
COUNTDOWN = P % "next_ep_countdown"
PICTURE = P % "nl_picture"
HAS_PICTURE = "!String.IsEmpty(Window.Property(nl_picture))"


def line(layout):
    left, top, width, height = layout.track
    return (image(left, top, width, height, "sl_white.png", diffuse=P % "skl_track")
            + image(left, top, width, height, "sl_white.png", cid=nl.ID_BAR_FILL, diffuse=P % "skl_accent"))


def ring(layout, accent="skl_accent", track="skl_track"):
    left, top, width, height = layout.track
    return (image(left, top, width, height, "sl_ring_%02d.png" % sl.RING_FRAMES, diffuse=P % track)
            + image(left, top, width, height, P % "nl_ring", cid=nl.ID_RING, diffuse=P % accent))


def plate(layout, prop="skl_plate"):
    return image(0, 0, layout.width, layout.height, P % prop, border=sl.PLATE_BORDER)


def buttons(play, close):
    """Play now and Close: ``(left, top, width)`` each."""
    return (button(nl.ID_PLAY, play[0], play[1], play[2], P % "nl_play", nl.ID_CLOSE)
            + button(nl.ID_CLOSE, close[0], close[1], close[2], P % "nl_close", nl.ID_PLAY))


def poster(layout):
    return (plate(layout)
            + image(12, 12, 84, 126, PICTURE, aspect="scale", visible=HAS_PICTURE)
            + label(116, 12, 388, 16, HEADING, color="skl_text2")
            + label(116, 30, 388, 28, EPISODE, font="font13")
            + label(116, 62, 388, 18, COUNTDOWN, color="skl_text2")
            + line(layout)
            + buttons((116, 112, 250), (374, 112, 130)))


def slab(layout):
    return (plate(layout, "skl_slab")
            + image(0, 4, 420, 140, PICTURE, aspect="scale", visible=HAS_PICTURE)
            + image(0, 74, 420, 70, "sl_band.png", visible=HAS_PICTURE)
            # on the picture the texts are light in every look; without a picture they lie on the slab
            + label(16, 96, 388, 16, HEADING, color="skl_pic_text2", visible=HAS_PICTURE)
            + label(16, 112, 388, 28, EPISODE, font="font13", color="skl_pic_text", visible=HAS_PICTURE)
            + label(16, 96, 388, 16, HEADING, color="skl_text2", visible="!" + HAS_PICTURE)
            + label(16, 112, 388, 28, EPISODE, font="font13", visible="!" + HAS_PICTURE)
            + line(layout)
            + label(16, 150, 388, 18, COUNTDOWN, color="skl_text2")
            + buttons((12, 176, 260), (280, 176, 128)))


def play_ring(layout):
    left, top, width, height = layout.track
    return (image(-18, -18, layout.width + 36, layout.height + 36, "sl_shade.png", border=40)
            + image(16, 14, 180, 101, PICTURE, aspect="scale", visible=HAS_PICTURE)
            + image(16, 14, 180, 101, "sl_white.png", diffuse="73000000")
            + ring(layout, track="skl_ring_back")
            + label(left, top + 18, width, 20, "[B]%s[/B]" % (P % "nl_seconds"), font="font12", align="center")
            + label(212, 18, 252, 16, HEADING, color="skl_text2")
            + label(212, 38, 252, 46, EPISODE, font="font13", wrap=True)
            + label(212, 90, 252, 18, COUNTDOWN, color="skl_text2")
            + buttons((16, 124, 290), (314, 124, 150)))


def band(layout):
    top = "String.IsEqual(Window.Property(skl_top),true)"
    return (image(0, 0, layout.width, layout.height, "sl_band.png", visible="!" + top)
            + image(0, 0, layout.width, layout.height, "sl_band_top.png", visible=top)
            + image(48, 40, 142, 80, PICTURE, aspect="scale", visible=HAS_PICTURE)
            + label(206, 44, 560, 16, HEADING, color="skl_text2")
            + label(206, 62, 560, 30, EPISODE, font="font16")
            + label(206, 96, 560, 18, COUNTDOWN, color="skl_text2")
            + buttons((794, 84, 300), (1102, 84, 130))
            + line(layout))


def float_(layout):
    return (label(0, 4, 470, 16, HEADING, color="skl_text2", align="right")
            + label(0, 24, 470, 40, EPISODE, font="font30", align="right")
            + label(0, 70, 470, 20, COUNTDOWN, font="font11", color="skl_text2", align="right")
            + button(nl.ID_CLOSE, 150, 110, 112, P % "nl_close", nl.ID_PLAY)
            + button(nl.ID_PLAY, 270, 110, 200, P % "nl_play", nl.ID_CLOSE, offset=14)
            + ring(layout, "skl_focus_text", "skl_focus_track"))


def rail(layout):
    return (plate(layout, "skl_slab")
            + image(16, 16, 152, 86, PICTURE, aspect="scale", visible=HAS_PICTURE)
            + label(12, 108, 160, 16, HEADING, color="skl_text2", align="center")
            + label(12, 126, 160, 40, EPISODE, font="font12", align="center", wrap=True)
            + label(12, 170, 160, 32, COUNTDOWN, color="skl_text2", align="center", wrap=True)
            + line(layout)
            + button(nl.ID_PLAY, 16, 222, 152, P % "nl_play", nl.ID_CLOSE)
            + button(nl.ID_CLOSE, 16, 254, 152, P % "nl_close", nl.ID_PLAY))


def takeover(layout):
    """The next episode takes the screen: its fanart under a veil, the show's logo, the title large."""
    return (image(0, 0, 1280, 720, "sl_white.png", diffuse="FF0A0C10")
            + image(0, 0, 1280, 720, PICTURE, aspect="scale", visible=HAS_PICTURE)
            + image(0, 0, 1280, 720, "sl_white.png", diffuse="73000000")
            + image(0, 360, 1280, 360, "sl_band.png")
            + image(64, 356, 320, 120, P % "nl_logo", aspect="keep", visible="!String.IsEmpty(Window.Property(nl_logo))")
            + label(64, 492, 900, 20, HEADING, font="font12", color="skl_text2")
            # the title at nearly twice the size: a skin need not have a large font, so the label is zoomed
            + '      <control type="group">\n' + g.tags(g.box(64, 512, 1100, 64))
            + '        <animation effect="zoom" start="190" end="190" center="64,512" time="0" condition="true">Conditional</animation>\n'
            + label(0, 0, 578, 34, EPISODE, font="font13")
            + "      </control>\n"
            + label(64, 584, 900, 24, COUNTDOWN, font="font13", color="skl_text2")
            + line(layout)
            + buttons((64, 668, 300), (372, 668, 180)))


def queue(layout):
    """The next three episodes as cards: Left and Right pick one, OK plays it."""
    out = plate(layout) + label(16, 12, 632, 18, HEADING, color="skl_text2")
    close = nl.ID_CLOSE
    for index, cid in enumerate(nl.QUEUE_IDS):
        x, y, w, h = nl.queue_left(index), nl.QUEUE_TOP, nl.QUEUE_CARD_W, nl.QUEUE_CARD_H
        has = "!String.IsEmpty(Window.Property(nl_q%d_label))" % index
        focus, blur = "Control.HasFocus(%d)" % cid, "!Control.HasFocus(%d)" % cid
        out += image(x, y, w, h, "sl_white.png", diffuse=P % "skl_track", visible=has)
        out += image(x, y, w, h, P % ("nl_q%d_thumb" % index), aspect="scale", visible=has)
        out += image(x, y, w, h, "sl_white.png", diffuse="80000000", visible=has + " + " + blur)
        out += image(x, y + h + 2, w, 3, "sl_white.png", diffuse=P % "skl_accent", visible=has + " + " + focus)
        out += label(x, y + h + 8, w, 18, P % ("nl_q%d_label" % index), font="font12", visible=has + " + " + focus)
        out += label(x, y + h + 8, w, 18, P % ("nl_q%d_label" % index), font="font12", color="skl_text2", visible=has + " + " + blur)
        left = nl.QUEUE_IDS[index - 1] if index else cid
        right = nl.QUEUE_IDS[index + 1] if index + 1 < len(nl.QUEUE_IDS) else cid
        out += '      <control type="button" id="%d">\n' % cid + g.tags(g.box(x, y, w, h + 28))
        out += g.tags([("label", ""), ("texturefocus", "-"), ("texturenofocus", "-"), ("onleft", left), ("onright", right),
                       ("onup", cid), ("ondown", close), ("visible", has)])
        out += "      </control>\n"
    return (out + line(layout)
            + label(16, 204, 420, 28, COUNTDOWN, font="font12", color="skl_text2")
            + button(close, 448, 204, 200, P % "nl_close", nl.ID_PLAY))


BUILDERS = {"Poster": poster, "Slab": slab, "Ring": play_ring, "Band": band, "Float": float_, "Rail": rail,
            "Takeover": takeover, "Queue": queue}


def skin_720(layout) -> str:
    body = BUILDERS[layout.name](layout)
    # the buttons of g.button() show their focus picture for g's own Skip id; here it is Play's
    return (g.HEAD % (nl.ID_PLAY, nl.ID_PROBE, nl.PROBE_W, nl.ID_ROOT, layout.width, layout.height)).replace(
        "tools/gen_skip_layouts.py", "tools/gen_next_layouts.py").replace(
            # above its Customize screen (2), like the classic popup, so Preview draws on top of it
            "<zorder>1</zorder>", "<zorder>3</zorder>") + body + g.TAIL


def skin_files() -> dict:
    out = {}
    for layout in nl.all_layouts():
        text = skin_720(layout)
        out[os.path.join(SKINS, "720p", layout.xml)] = text
        out[os.path.join(SKINS, "1080i", layout.xml)] = gen.convert(text)
    return out


def masks() -> dict:
    """White pictures with round corners that cut the two pictures of Poster and episode (classic
    popup): Kodi multiplies a picture by its ``diffuse`` picture, so the corners become clear."""
    from PIL import Image, ImageDraw

    out = {}
    # the corners are 6 units at the 90 units of height the pair is drawn at
    for name, (width, height) in (("nx_mask_poster.png", (240, 360)), ("nx_mask_wide.png", (640, 360))):
        big = Image.new("L", (width * 2, height * 2), 0)
        ImageDraw.Draw(big).rounded_rectangle((0, 0, width * 2 - 1, height * 2 - 1), radius=2 * height * 6 // 90, fill=255)
        picture = Image.new("RGBA", (width, height), (255, 255, 255, 0))
        picture.putalpha(big.resize((width, height), Image.LANCZOS))
        out[os.path.join(SKINS, "media", name)] = picture
    return out


def stale_masks() -> list:
    from PIL import Image

    out = []
    for path, picture in masks().items():
        try:
            with Image.open(path) as found:
                if found.convert("RGBA").tobytes() != picture.tobytes() or found.size != picture.size:
                    out.append(path)
        except OSError:
            out.append(path)
    return out


def stale() -> list:
    out = stale_masks()
    for path, text in skin_files().items():
        try:
            with open(path, encoding="utf-8", newline="") as handle:
                if handle.read() != text:
                    out.append(path)
        except OSError:
            out.append(path)
    return out


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    todo = stale()
    if "--check" in argv:
        for path in todo:
            print("stale or missing:", os.path.relpath(path, ROOT))
        return 1 if todo else 0
    texts = skin_files()
    pictures = masks()
    for path in todo:
        if path in pictures:
            pictures[path].save(path, "PNG", optimize=True)
            print("wrote", os.path.relpath(path, ROOT))
            continue
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(texts[path])
        print("wrote", os.path.relpath(path, ROOT))
    print("%d skin files, %d written" % (len(texts), len(todo)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
