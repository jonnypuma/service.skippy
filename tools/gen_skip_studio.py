# -*- coding: utf-8 -*-
"""Write the Studio (the Customize screen of the skip dialog): ``SkipStudio.xml`` and its pictures.

    python tools/gen_skip_layouts.py           (first: it writes the preview copies this file borrows)
    python tools/gen_skip_studio.py            (write what is missing or changed)
    python tools/gen_skip_studio.py --check    (exit 1 when a file is missing or differs)

The screen is always in the Fused Glass Dark look, panels with a shadow. Its live preview is the
whole screen drawn small; the dialogs in it are the preview copies of ``SkipDialogCustomize.xml``
(the classic card, the Minimal chip and every layout of ``skip_layouts.py``), so
``skip_dialog_customize_ui.py`` fills them the same way in both screens.

Geometry and ids come from ``skip_studio.py``. The 1080i file is ``gen_skin_1080i.convert()`` of
the 720p one, like every generated file.
"""
from __future__ import annotations

import io
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFilter

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
for _path in (ROOT, TOOLS):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import gen_fuse_preset_textures as fuse  # noqa: E402
import gen_preset_thumbs as thumbs  # noqa: E402
import gen_skin_1080i as gen  # noqa: E402
import skip_layouts as sl  # noqa: E402
import skip_studio as st  # noqa: E402

SKINS = os.path.join(ROOT, "resources", "skins", "default")
MEDIA = os.path.join(SKINS, "media")
CUSTOMIZE = "SkipDialogCustomize.xml"
P = "$INFO[Window.Property(%s)]"

TEXT, TEXT2, TEXT3, INK = "FFFFFFFF", "FFB9BEC8", "FF8A909C", "FF101216"


# ------------------------------------------------------------------------------- pictures
def shadow() -> Image.Image:
    """A soft shadow for a panel (nine-slice border ``SHADOW_BORDER``)."""
    size = 200
    alpha = Image.new("L", (size, size), 0)
    inset = st.SHADOW_GROW
    ImageDraw.Draw(alpha).rounded_rectangle((inset, inset, size - 1 - inset, size - 1 - inset), radius=28, fill=178)
    alpha = alpha.filter(ImageFilter.GaussianBlur(14))
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.putalpha(alpha)
    return out


def toggle(on, dark=False) -> Image.Image:
    """A switch, drawn three times the 720p size. ``dark`` is the one that is off on a white row."""
    width, height = st.TOGGLE_W * 3, st.TOGGLE_H * 3
    track = (232, 176, 75, 255) if on else ((16, 18, 22, 70) if dark else (255, 255, 255, 56))
    picture = fuse.shape(width, height, height / 2.0, track)
    knob = fuse.shape(height - 12, height - 12, (height - 12) / 2.0, (255, 255, 255, 255) if on else (200, 204, 212, 255))
    picture.alpha_composite(knob, (width - height + 6 if on else 6, 6))
    return picture


def dot(fill, ring=None, size=48) -> Image.Image:
    """A colour dot (white, tinted when drawn), or a ring for the dot that is chosen."""
    big = size * 4
    picture = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(picture)
    if ring:
        draw.ellipse((2, 2, big - 3, big - 3), outline=ring, width=big // 9)
    else:
        draw.ellipse((0, 0, big - 1, big - 1), fill=fill)
    return picture.resize((size, size), Image.LANCZOS)


def half_dot(size=48) -> Image.Image:
    """The dot of "follows the bar colour setting": half gold, half blue."""
    big = size * 4
    picture = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(picture)
    draw.pieslice((0, 0, big - 1, big - 1), 90, 270, fill=(232, 176, 75, 255))
    draw.pieslice((0, 0, big - 1, big - 1), 270, 90, fill=(127, 180, 255, 255))
    return picture.resize((size, size), Image.LANCZOS)


def check(size=40) -> Image.Image:
    big = size * 4
    picture = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    ImageDraw.Draw(picture).line([(big * 0.14, big * 0.54), (big * 0.40, big * 0.78), (big * 0.86, big * 0.24)],
                                 fill=(255, 255, 255, 255), width=big // 8, joint="curve")
    return picture.resize((size, size), Image.LANCZOS)


def pictures() -> dict:
    seg_720, seg_1080 = st.SEG_H, st.SEG_H * 3 // 2
    return {
        "st_back.png": Image.new("RGBA", (16, 16), (8, 9, 12, 255)),
        # the picture behind a preset tile that is drawn from parts (the miniatures have it built in)
        "pt_back.png": thumbs.backdrop().convert("RGB").resize((thumbs.OUT_W, thumbs.OUT_H), Image.LANCZOS),
        "st_shadow.png": shadow(),
        "st_toggle_on.png": toggle(True),
        "st_toggle_off.png": toggle(False),
        "st_toggle_off_dark.png": toggle(False, dark=True),
        # the well behind the choices of a switch row, and the chosen one; cut per skin folder (pills)
        "st_well_720.png": fuse.shape(64, seg_720, seg_720 / 2.0, (255, 255, 255, 255)),
        "st_well_1080.png": fuse.shape(96, seg_1080, seg_1080 / 2.0, (255, 255, 255, 255)),
        "st_chip_720.png": fuse.shape(64, seg_720, seg_720 / 2.0, (255, 255, 255, 255)),
        "st_chip_1080.png": fuse.shape(96, seg_1080, seg_1080 / 2.0, (255, 255, 255, 255)),
        # the frame round the current preset tile, and the hairline round the preview
        "st_ring.png": fuse.shape(96, 96, 14, (255, 255, 255, 0), (255, 255, 255, 255), stroke=2),
        "st_frame.png": fuse.shape(96, 96, 0, (255, 255, 255, 0), (255, 255, 255, 40), stroke=1),
        # colour dots, the ring round the chosen one, the knob of a slider, the tick on Save
        "st_dot.png": dot((255, 255, 255, 255)),
        "st_dot_auto.png": half_dot(),
        "st_dot_ring.png": dot(None, ring=(255, 255, 255, 255), size=66),
        "st_check.png": check(),
    }


# ------------------------------------------------------------------------------ skin file
def tags(pairs, indent="      "):
    return "".join("%s<%s>%s</%s>\n" % (indent, name, value, name) for name, value in pairs)


def box(rect):
    left, top, width, height = rect
    return [("left", left), ("top", top), ("width", width), ("height", height)]


def image(rect, texture, cid=None, border=None, diffuse=None, visible=None, aspect=None):
    out = '    <control type="image"%s>\n' % (' id="%d"' % cid if cid else "") + tags(box(rect))
    out += "      <texture%s>%s</texture>\n" % (' border="%s"' % border if border else "", texture)
    for name, value in (("colordiffuse", diffuse), ("aspectratio", aspect), ("visible", visible)):
        if value:
            out += tags([(name, value)])
    return out + "    </control>\n"


def label(rect, text, font="font10", color=TEXT, align="left", visible=None, cid=None, wrap=False):
    out = '    <control type="label"%s>\n' % (' id="%d"' % cid if cid else "") + tags(box(rect))
    out += tags([("label", text), ("font", font), ("textcolor", color), ("align", align), ("aligny", "center")])
    if wrap:
        out += tags([("wrapmultiline", "true")])
    if visible:
        out += tags([("visible", visible)])
    return out + "    </control>\n"


def button(cid, rect, text, align="left", offset=14):
    """A row or a button of the screen. Python owns the navigation, so every direction stays put."""
    out = '    <control type="button" id="%d">\n' % cid + tags(box(rect))
    out += tags([("label", text), ("font", "font12")])
    out += '      <texturefocus border="14">ms_fgd_focus.png</texturefocus>\n'
    out += '      <texturenofocus border="14">ms_fgd_row.png</texturenofocus>\n'
    out += tags([("textcolor", TEXT), ("focusedcolor", INK), ("disabledcolor", TEXT3), ("shadowcolor", "00000000"),
                 ("align", align), ("aligny", "center"), ("textoffsetx", offset),
                 ("onup", cid), ("ondown", cid), ("onleft", cid), ("onright", cid)])
    return out + "    </control>\n"


def panel(rect):
    left, top, width, height = rect
    grow = st.SHADOW_GROW
    return (image((left - grow, top - grow + st.SHADOW_DROP, width + 2 * grow, height + 2 * grow), "st_shadow.png",
                  border=st.SHADOW_BORDER)
            + image(rect, "ms_fgd_panel.png", border=28))


def row_button(cid, rect):
    """A row: no plate of its own, a white pill while it has the focus."""
    out = '    <control type="button" id="%d">\n' % cid + tags(box(rect))
    out += tags([("label", ""), ("font", "font12")])
    out += '      <texturefocus border="14">ms_fgd_focus.png</texturefocus>\n'
    out += "      <texturenofocus>-</texturenofocus>\n"
    out += tags([("onup", cid), ("ondown", cid), ("onleft", cid), ("onright", cid)])
    return out + "    </control>\n"


def tab_button(cid, rect):
    out = '    <control type="button" id="%d">\n' % cid + tags(box(rect))
    out += tags([("label", ""), ("font", "font12")])
    out += '      <texturefocus border="14">ms_fgd_focus.png</texturefocus>\n'
    out += "      <texturenofocus>-</texturenofocus>\n"
    out += tags([("textcolor", TEXT2), ("focusedcolor", INK), ("disabledcolor", "FF4A4F5A"), ("shadowcolor", "00000000"),
                 ("align", "center"), ("aligny", "center"), ("textoffsetx", 0),
                 ("onup", cid), ("ondown", cid), ("onleft", cid), ("onright", cid)])
    return out + "    </control>\n"


def left_panel() -> str:
    left, top, width, _height = st.PANEL
    out = panel(st.PANEL)
    out += label((left + st.PAD, st.KICKER_TOP, width - 2 * st.PAD, 14), P % "st_kicker", color=TEXT3)
    # the title is drawn by the screen itself, at the mockup's size (a skin need not have a font that large)
    for index in range(len(st.TABS)):
        rect = st.tab_box(index)
        # the open tab keeps a grey pill while the focus is somewhere else
        chosen = "String.IsEqual(Window.Property(st_tab),%d) + !Control.HasFocus(%d)" % (index, st.tab_id(index))
        out += image(rect, "ms_fgd_focus.png", border=13, visible=chosen, diffuse="24FFFFFF")
        out += tab_button(st.tab_id(index), rect)
        out += label(rect, P % ("st_tab%d" % index), font="font12", color=TEXT, align="center", visible=chosen)
    for row in range(st.ROWS):
        rect = st.row_box(row)
        rid = st.row_id(row)
        out += row_button(rid, rect)
        shown = "Control.IsVisible(%d)" % rid
        focus, blur = "Control.HasFocus(%d)" % rid, "!Control.HasFocus(%d)" % rid
        name = (rect[0] + st.ROW_PAD, rect[1], 230, rect[3])
        dim = "String.IsEqual(Window.Property(st_r%d_dim),true)" % row
        out += label(name, P % ("st_r%d_name" % row), font="font12", color=TEXT, visible="%s + %s + !%s" % (shown, blur, dim))
        # a row that does not apply to the design in use: still there, dimmed
        out += label(name, P % ("st_r%d_name" % row), font="font12", color="FF5E6470", visible="%s + %s + %s" % (shown, blur, dim))
        out += label(name, P % ("st_r%d_name" % row), font="font12", color=INK, visible="%s + %s" % (shown, focus))
        # the written value: at the control's end, or before a slider or the nine dots
        for kind in ("pick", "slider", "pos"):
            right = st.value_right(row, kind)
            box_ = (right - 250, rect[1], 250, rect[3])
            is_kind = "%s + String.IsEqual(Window.Property(st_r%d_kind),%s)" % (shown, row, kind)
            out += label(box_, P % ("st_r%d_val" % row), font="font12", color=TEXT, align="right", visible="%s + %s" % (is_kind, blur))
            out += label(box_, P % ("st_r%d_val" % row), font="font12", color=INK, align="right", visible="%s + %s" % (is_kind, focus))
        # a switch row: its choices side by side in a well, the chosen one a pill
        for count in range(2, st.SEG_OPTIONS + 1):
            start = st.seg_box(row, 0, count)
            last = st.seg_box(row, count - 1, count)
            has = "%s + String.IsEqual(Window.Property(st_r%d_n),%d)" % (shown, row, count)
            well = (start[0] - 3, start[1] - 2, last[0] + last[2] - start[0] + 6, st.SEG_H + 4)
            out += image(well, P % "st_well", border=st.SEG_H // 2, diffuse="14FFFFFF", visible="%s + %s" % (has, blur))
            out += image(well, P % "st_well", border=st.SEG_H // 2, diffuse="1E101216", visible="%s + %s" % (has, focus))
            # the choices of a row with this many: wider where fewer stand side by side. The screen
            # writes them into the last ``count`` of the option properties.
            for place in range(count):
                option = st.SEG_OPTIONS - count + place
                box_ = st.seg_box(row, place, count)
                on = "String.IsEqual(Window.Property(st_r%d_on),%d)" % (row, option)
                text = P % ("st_r%d_s%d" % (row, option))
                # without the focus: the chosen one white with dark letters; with it: dark with white letters
                out += image(box_, P % "st_chip", border=st.SEG_H // 2, visible="%s + %s + %s" % (has, on, blur))
                out += image(box_, P % "st_chip", border=st.SEG_H // 2, diffuse=INK, visible="%s + %s + %s" % (has, on, focus))
                out += label(box_, text, color=INK, align="center", visible="%s + %s + %s" % (has, on, blur))
                out += label(box_, text, color=TEXT, align="center", visible="%s + %s + %s" % (has, on, focus))
                out += label(box_, text, color=TEXT2, align="center", visible="%s + !%s + %s" % (has, on, blur))
                out += label(box_, text, color="FF4A4F5A", align="center", visible="%s + !%s + %s" % (has, on, focus))
        is_on = "%s + String.IsEqual(Window.Property(st_r%d_tog),on)" % (shown, row)
        is_off = "%s + String.IsEqual(Window.Property(st_r%d_tog),off)" % (shown, row)
        out += image(st.toggle_box(row), "st_toggle_on.png", visible=is_on)
        out += image(st.toggle_box(row), "st_toggle_off.png", visible="%s + %s" % (is_off, blur))
        # on the white row in focus the light track of a switch that is off would not show
        out += image(st.toggle_box(row), "st_toggle_off_dark.png", visible="%s + %s" % (is_off, focus))
        # a colour row: dots, a ring round the chosen one
        for index in range(st.SWATCHES):
            x, y, w, h = st.swatch_box(row, index)
            has = "%s + !String.IsEmpty(Window.Property(st_r%d_t%d))" % (shown, row, index)
            out += image((x, y, w, h), P % ("st_r%d_t%d" % (row, index)), diffuse=P % ("st_r%d_c%d" % (row, index)), visible=has)
            on = "String.IsEqual(Window.Property(st_r%d_con),%d)" % (row, index)
            out += image((x - 3, y - 3, w + 6, h + 6), "st_dot_ring.png", visible="%s + %s + %s" % (has, on, blur))
            out += image((x - 3, y - 3, w + 6, h + 6), "st_dot_ring.png", diffuse=INK, visible="%s + %s + %s" % (has, on, focus))
        # a slider row: its track, the part that is filled and the knob (Python sets their size and place)
        is_slider = "%s + String.IsEqual(Window.Property(st_r%d_kind),slider)" % (shown, row)
        track = st.slider_box(row)
        out += image(track, "sl_white.png", diffuse="33FFFFFF", visible="%s + %s" % (is_slider, blur))
        out += image(track, "sl_white.png", diffuse="33101216", visible="%s + %s" % (is_slider, focus))
        out += image((track[0], track[1], 1, track[3]), "sl_white.png", cid=st.ID_SLIDER_FILL + row, diffuse="FFE8B04B",
                     visible=is_slider)
        knob_top = track[1] + track[3] // 2 - st.KNOB // 2
        out += image((track[0], knob_top, st.KNOB, st.KNOB), "st_dot.png", cid=st.ID_SLIDER_KNOB + row, visible=is_slider)
        # a position row: nine dots, the chosen place lit
        for place in range(9):
            has = "%s + !String.IsEmpty(Window.Property(st_r%d_pos))" % (shown, row)
            on = "String.IsEqual(Window.Property(st_r%d_pos),%d)" % (row, place)
            out += image(st.pos_box(row, place), "st_dot.png", diffuse="FF7C828E", visible="%s + !%s" % (has, on))
            out += image(st.pos_box(row, place), "st_dot.png", diffuse="FFE8B04B", visible="%s + %s" % (has, on))
    # which rows of a long tab are on screen ("1 - 10 of 14")
    last = st.row_box(st.ROWS - 1)
    out += label((last[0], last[1] + last[3] + 2, last[2] - st.ROW_PAD, 16), P % "st_more", color=TEXT3, align="right")
    boxes = st.foot_boxes()
    out += button(st.ID_SAVE, boxes[0], "Save", align="left", offset=40)
    tick = (boxes[0][0] + 17, boxes[0][1] + (boxes[0][3] - 13) // 2, 13, 13)
    out += image(tick, "st_check.png", visible="!Control.HasFocus(%d)" % st.ID_SAVE)
    out += image(tick, "st_check.png", diffuse=INK, visible="Control.HasFocus(%d)" % st.ID_SAVE)
    out += button(st.ID_SAVE_PRESET, boxes[1], "Save as preset", align="center", offset=0)
    out += button(st.ID_RESET, boxes[2], "Reset", align="center", offset=0)
    return out


def borrowed() -> str:
    """The preview copies of the classic Customize file: the card, the Minimal chip and the layouts."""
    with open(os.path.join(SKINS, "720p", CUSTOMIZE), encoding="utf-8", newline="") as handle:
        text = handle.read().replace("\r\n", "\n")

    def group(cid):
        start = text.index('<control type="group" id="%d">' % cid)
        depth, at = 0, start
        for match in re.finditer(r"<control\b|</control>", text[start:]):
            depth += 1 if match.group(0) != "</control>" else -1
            if depth == 0:
                at = start + match.end()
                break
        return text[start:at]

    screen = group(sl.ID_MOCK_SCREEN)
    inner = screen[screen.index("</animation>") + len("</animation>"):screen.rindex("</control>")]
    card = group(3080)
    minimal = group(5090)
    assert "skl_mock" in inner and 'id="3081"' in card, "run tools/gen_skip_layouts.py first"
    # in the Studio the card gives way to a layout by property (the classic screen hides it from Python as well)
    return "      %s\n      %s\n%s" % (card, minimal, inner.strip("\n") + "\n")


def stage() -> str:
    left, top, width, height = st.STAGE
    sx, sy = st.screen_origin()
    out = panel(st.STAGE)
    out += '    <control type="group" id="%d">\n' % st.ID_SCREEN
    out += tags([("left", sx), ("top", sy), ("width", st.CANVAS_W), ("height", st.CANVAS_H)])
    out += ('      <animation effect="zoom" start="%d" end="%d" center="%d,%d" time="0" condition="true">Conditional'
            "</animation>\n" % (st.SCREEN_ZOOM, st.SCREEN_ZOOM, sx, sy))
    out += ('      <control type="image" id="%d">\n        <left>0</left><top>0</top>\n        <width>%d</width><height>%d</height>\n'
            "        <texture>st_back.png</texture>\n        <aspectratio>scale</aspectratio>\n      </control>\n"
            % (st.ID_FANART, st.CANVAS_W, st.CANVAS_H))
    out += ('      <control type="image">\n        <left>0</left><top>0</top>\n        <width>%d</width><height>%d</height>\n'
            "        <texture>sl_white.png</texture>\n        <colordiffuse>59000000</colordiffuse>\n      </control>\n"
            % (st.CANVAS_W, st.CANVAS_H))
    out += borrowed()
    out += "    </control>\n"
    out += image((sx, sy, int(st.CANVAS_W * st.SCREEN_ZOOM / 100.0), int(st.CANVAS_H * st.SCREEN_ZOOM / 100.0)), "st_frame.png", border=4)
    # the dark band the words stand on, then Live preview
    out += image((sx, sy, int(st.CANVAS_W * st.SCREEN_ZOOM / 100.0), 46), "cv_ov_band_top.png", diffuse="B0000000")
    out += label(st.tag_box(0), P % "st_tag", color=TEXT2)
    # beside it, the segment type the preview shows: plain words, nothing to pick here
    out += label(st.tag_box(1), P % "st_tag0", color=TEXT)
    return out


def strip() -> str:
    """Under the preview: what the row in focus does, or the presets while the Preset row has the focus."""
    left, top, width, height = st.STRIP
    out = panel(st.STRIP)
    out += label((left + st.PAD, top + 16, width - 2 * st.PAD, 16), P % "st_strip", color=TEXT3)
    about = "!String.IsEqual(Window.Property(st_mode),presets)"
    out += '    <control type="textbox" id="%d">\n' % st.ID_ABOUT + tags(box((left + st.PAD, top + 42, width - 2 * st.PAD, height - 58)))
    out += tags([("label", P % "st_about"), ("font", "font12"), ("textcolor", TEXT2), ("visible", about)])
    out += "    </control>\n"
    tiles = "String.IsEqual(Window.Property(st_mode),presets) + "
    for index in range(st.TILES):
        x, y, w, h = st.tile_box(index)
        has = tiles + "!String.IsEmpty(Window.Property(st_t%d_name))" % index
        out += image((x, y, w, h), "ms_fgd_inset.png", border=14, visible=has)
        out += image((x + 3, y + 3, w - 6, h - 6), P % ("st_t%d_thumb" % index), aspect="scale",
                     visible=tiles + "!String.IsEmpty(Window.Property(st_t%d_thumb))" % index)
        out += image((x + 14, y + 12, w - 28, h - 24), P % ("st_t%d_plate" % index), border=sl.PLATE_BORDER,
                     diffuse=P % ("st_t%d_tint" % index), visible=tiles + "!String.IsEmpty(Window.Property(st_t%d_plate))" % index)
        out += image((x + 24, y + 22, w - 48, 16), P % ("st_t%d_pill" % index), aspect="stretch",
                     visible=tiles + "!String.IsEmpty(Window.Property(st_t%d_pill))" % index)
        out += image((x + 24, y + 50, w - 78, 4), P % ("st_t%d_bar" % index), aspect="stretch",
                     diffuse=P % ("st_t%d_bartint" % index), visible=tiles + "!String.IsEmpty(Window.Property(st_t%d_bar))" % index)
        if index == st.TILES // 2:
            out += image((x - 3, y - 3, w + 6, h + 6), "st_ring.png", border=16, visible=has)
        out += label((x - 4, y + h + 6, w + 8, 18), P % ("st_t%d_name" % index),
                     color=TEXT if index == st.TILES // 2 else TEXT2, align="center", visible=has)
    return out


HEAD = """<?xml version='1.0' encoding='utf-8'?>
<!-- Written by tools/gen_skip_studio.py: edit that, not this file. -->
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
  <animation type="WindowOpen">
    <effect type="fade" start="0" end="100" time="200" />
  </animation>
  <animation type="WindowClose">
    <effect type="fade" start="100" end="0" time="200" />
  </animation>
  <controls>
"""


def skin_720() -> str:
    out = HEAD % st.row_id(0)
    out += image((0, 0, 1280, 720), "st_back.png")
    out += left_panel() + stage() + strip()
    out += label((st.PANEL[0], 688, 1180, 20), P % "st_hint", color=TEXT2)
    return out + "  </controls>\n</window>\n"


def wall_720() -> str:
    """The preset wall: twelve tiles a page, each a miniature (or a card drawn from its parts)."""
    out = HEAD % st.wall_id(0)
    out += image((0, 0, 1280, 720), "st_back.png")
    out += label((st.WALL_LEFT, 26, 700, 30), P % "pw_title", font="font16")
    out += label((st.WALL_LEFT + 700, 26, 1280 - 2 * st.WALL_LEFT - 700, 30), P % "pw_page", color=TEXT2, align="right")
    for index in range(st.WALL_TILES):
        x, y, w, h = st.wall_box(index)
        has = "!String.IsEmpty(Window.Property(pw_t%d_name))" % index
        thumb = "!String.IsEmpty(Window.Property(pw_t%d_thumb))" % index
        out += image((x, y, w, h), "pt_back.png", aspect="scale", visible="%s + !%s" % (has, thumb))
        out += image((x, y, w, h), P % ("pw_t%d_thumb" % index), aspect="scale", visible=thumb)
        # a card preset, drawn from its own pictures at the bottom right of the tile
        out += image((x + 96, y + 84, 176, 64), P % ("pw_t%d_plate" % index), border=sl.PLATE_BORDER,
                     diffuse=P % ("pw_t%d_tint" % index), visible="!String.IsEmpty(Window.Property(pw_t%d_plate))" % index)
        out += image((x + 106, y + 94, 156, 20), P % ("pw_t%d_pill" % index), aspect="stretch",
                     visible="!String.IsEmpty(Window.Property(pw_t%d_pill))" % index)
        out += image((x + 106, y + 130, 100, 5), P % ("pw_t%d_bar" % index), aspect="stretch",
                     visible="!String.IsEmpty(Window.Property(pw_t%d_bar))" % index)
        # the tile itself: only a frame while it has the focus
        out += '    <control type="button" id="%d">\n' % st.wall_id(index) + tags(box((x - 4, y - 4, w + 8, h + 8)))
        out += '      <texturefocus border="16">st_ring.png</texturefocus>\n      <texturenofocus>-</texturenofocus>\n'
        out += tags([("label", ""), ("onup", st.wall_id(index)), ("ondown", st.wall_id(index)),
                     ("onleft", st.wall_id(index)), ("onright", st.wall_id(index)), ("visible", has)])
        out += "    </control>\n"
        out += label((x, y + h + 6, w, 20), P % ("pw_t%d_name" % index), font="font12", color=TEXT2, align="center",
                     visible="!Control.HasFocus(%d)" % st.wall_id(index))
        out += label((x, y + h + 6, w, 20), P % ("pw_t%d_name" % index), font="font12", align="center",
                     visible="Control.HasFocus(%d)" % st.wall_id(index))
        # the preset in use: a gold line under its name (the fonts of a skin need not have a tick)
        out += image((x + w // 2 - 22, y + h + 30, 44, 3), "sl_white.png", diffuse="FFE8B84A",
                     visible="!String.IsEmpty(Window.Property(pw_t%d_on))" % index)
    out += label((40, 690, 1200, 20), P % "pw_hint", color=TEXT3, align="center")
    return out + "  </controls>\n</window>\n"


def skin_files() -> dict:
    out = {}
    for name, text in ((st.XML, skin_720()), (st.WALL_XML, wall_720())):
        out[os.path.join(SKINS, "720p", name)] = text
        out[os.path.join(SKINS, "1080i", name)] = gen.convert(text)
    return out


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
