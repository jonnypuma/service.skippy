# -*- coding: utf-8 -*-
"""Write the two new segment editor layouts (720p; the source of truth).

    python3 tools/gen_segment_editor_layouts.py           # write SegmentEditorDialogA.xml and ...B.xml in 720p
    python3 tools/gen_segment_editor_layouts.py --check   # exit 1 when a file differs from what this writes
    python3 tools/gen_skin_1080i.py --overwrite           # is NOT needed: this tool writes the 1080i files too
    python3 tools/gen_modal_style_variants.py             # then the per-look copies

A is "List and drawer", B is "Drawer" (see segment_editor_layout.py). Both keep every control id of
SegmentEditorDialog.xml: the list 5000, the labels 5001 and 5008 and all 39 buttons, so
segment_editor_dialog.py drives all three files. New in both: a timeline (track 5099, segment blocks
5100-5119, playhead 5130, mark under the selected segment 5131, end time 5132) that Python fills.
The 1080i files are made with gen_skin_1080i.convert(), the same rule as every generated file.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_skin_1080i as gen  # noqa: E402
import segment_editor_layout as lay  # noqa: E402
import skippy_modal_style as style  # noqa: E402

SKINS = os.path.join(ROOT, "resources", "skins", "default")
P = "$INFO[Window.Property(%s)]"
ROWB = style.ROW_BORDER
# Flags of a segment: lighter than the classic file's pure red and blue, which are hard to read on the Frost panel.
NESTED, OVERLAPPING = "FFFF8F80", "FF7FC4FF"

LABELS = {
    5037: "Start = Now", 5038: "End = Now", 5027: "Snap Start", 5028: "Snap End", 5041: "Merge", 5042: "Split",
    5043: "Fix Overlap", 5021: "Edit", 5022: "Delete",
    5031: "-10m", 5032: "-5m", 5033: "-1m", 5011: "-30s", 5010: "-10s", 5009: "-5s", 5019: "-1s", 5018: "Pause",
    5020: "+1s", 5012: "+5s", 5013: "+10s", 5014: "+30s", 5034: "+1m", 5035: "+5m", 5036: "+10m",
    5015: "Set as Start", 5029: "Set to Start of File", 5016: "Set as End", 5030: "Set to End of File", 5017: "Create",
    5023: "Start at End of Segment", 5024: "End at Start of Segment",
    5025: "Jump To", 5005: "Add Current + User Set Time", 5002: "Manual Start + End Times", 5004: "Delete All",
    5040: "Undo", 5026: "Upload", 5006: "Save", 5007: "Exit",
}
ROW_ACTIONS = (5037, 5038, 5027, 5028, 5041, 5042, 5043, 5021, 5022)
SEEK = (5031, 5032, 5033, 5011, 5010, 5009, 5019, 5018, 5020, 5012, 5013, 5014, 5034, 5035, 5036)
MARK = (5015, 5029, 5016, 5030, 5017, 5023, 5024)
FILE = (5025, 5005, 5002, 5004, 5040, 5026, 5006, 5007)
assert len(set(ROW_ACTIONS + SEEK + MARK + FILE)) == 39 and set(ROW_ACTIONS + SEEK + MARK + FILE) == set(LABELS)


def tags(indent, pairs):
    return "".join("%s<%s>%s</%s>\n" % (indent, name, value, name) for name, value in pairs)


def button(cid, left, top, width, nav, height=30):
    out = '      <control type="button" id="%d">\n' % cid
    out += tags("        ", [("left", left), ("top", top), ("width", width), ("height", height), ("label", LABELS[cid]),
                             ("font", "font10"), ("textcolor", P % "ms_text"), ("focusedcolor", P % "ms_text_focus")])
    out += '        <texturenofocus border="%d">ms_fgf_row.png</texturenofocus>\n' % ROWB
    out += '        <texturefocus border="%d">ms_fgf_focus.png</texturefocus>\n' % ROWB
    out += tags("        ", [("shadowcolor", "00000000"), ("aligny", "center"), ("align", "center"), ("textoffsetx", 0)])
    out += tags("        ", [("on" + k, v) for k, v in nav.items() if v])
    return out + "      </control>\n"


def label(left, top, width, height, text, font, color, cid=None, align="left", extra=()):
    out = '      <control type="label"%s>\n' % (' id="%d"' % cid if cid else "")
    out += tags("        ", [("left", left), ("top", top), ("width", width), ("height", height), ("label", text), ("font", font),
                             ("textcolor", color), ("shadowcolor", P % "ms_shadow"), ("shadowoffsetx", 1), ("shadowoffsety", 1),
                             ("align", align), ("aligny", "center")] + list(extra))
    return out + "      </control>\n"


def image(left, top, width, height, texture, cid=None, border=None, extra=()):
    out = '      <control type="image"%s>\n' % (' id="%d"' % cid if cid else "")
    out += tags("        ", [("left", left), ("top", top), ("width", width), ("height", height)])
    out += "        <texture%s>%s</texture>\n" % (' border="%d"' % border if border is not None else "", texture)
    out += tags("        ", list(extra))
    return out + "      </control>\n"


def row(ids, left, top, widths, gap, up, down, left_exit=None, right_exit=None):
    """A row of buttons. ``up`` / ``down``: one id for all, or a tuple with one per button."""
    assert len(ids) == len(widths), (ids, widths)
    out, x = "", left
    for i, (cid, width) in enumerate(zip(ids, widths)):
        nav = {
            "left": ids[i - 1] if i else left_exit,
            "right": ids[i + 1] if i + 1 < len(ids) else right_exit,
            "up": up[i] if isinstance(up, tuple) else up,
            "down": down[i] if isinstance(down, tuple) else down,
        }
        out += button(cid, x, top, width, nav)
        x += width + gap
    return out, x - gap


def timeline(left, top, width, end_label_left, end_label_width, header_top):
    out = label(left + 2, header_top, 300, 16, "Timeline", "font10", P % "ms_text2")
    out += label(end_label_left, header_top, end_label_width, 16, "", "font10", P % "ms_text3", cid=lay.END_LABEL_ID, align="right")
    out += image(left, top, width, 30, "ms_fgf_inset.png", cid=lay.TRACK_ID, border=ROWB)
    for cid in lay.BLOCK_IDS:  # parked off screen until Python places them
        out += image(-9999, top, 10, 30, "seg_other.png", cid=cid, border=4)
    out += image(-9999, top + 32, 10, 3, "white.png", cid=lay.SELECTED_MARK_ID, extra=[("colordiffuse", P % "ms_text")])
    out += image(-9999, top - 5, 2, 40, "white.png", cid=lay.PLAYHEAD_ID, extra=[("colordiffuse", P % "ms_text")])
    return out


def list_line2(left, top, width, scroll):
    out = ""
    for kind, color in (("normal", P % "ms_text3"), ("nested", NESTED), ("overlapping", OVERLAPPING)):
        out += '            <control type="label">\n'
        out += tags("              ", [("left", left), ("top", top), ("width", width), ("height", 20), ("label", "$INFO[ListItem.Label2]"),
                                       ("font", "font10"), ("textcolor", color), ("align", "left")] +
                    ([("scroll", "true")] if scroll else []) +
                    [("visible", "String.IsEqual(ListItem.Property(segment_type),%s)" % kind)])
        out += "            </control>\n"
    return out


def side_list(left, top, width, height, nav):
    def layout(tag, focused):
        out = '        <%s width="%d" height="50">\n' % (tag, width)
        if focused:
            out += '          <control type="image">\n' + tags("            ", [("left", 0), ("top", 0), ("width", width), ("height", 48)])
            out += '            <texture border="%d">ms_fgf_row.png</texture>\n          </control>\n' % ROWB
        out += '          <control type="image">\n' + tags("            ", [("left", 10), ("top", 11), ("width", 12), ("height", 12)])
        out += "            <texture>$INFO[ListItem.Property(type_chip)]</texture>\n          </control>\n"
        out += '          <control type="label">\n' + tags("            ", [
            ("left", 30), ("top", 5), ("width", 150), ("height", 24),
            ("label", "$INFO[ListItem.Property(segment_num)]. $INFO[ListItem.Property(label)]"), ("font", "font12"),
            ("textcolor", P % "ms_text"), ("align", "left")] + ([("scroll", "true")] if focused else [])) + "          </control>\n"
        out += '          <control type="label">\n' + tags("            ", [
            ("left", 184), ("top", 6), ("width", 206), ("height", 22),
            ("label", "$INFO[ListItem.Property(start_hms)] - $INFO[ListItem.Property(end_hms)]"), ("font", "font10"),
            ("textcolor", P % "ms_text2"), ("align", "right")]) + "          </control>\n"
        out += list_line2(30, 27, 360, focused).replace("            <", "          <").replace("              <", "            <")
        return out + "        </%s>\n" % tag
    out = '      <control type="list" id="5000">\n'
    out += tags("        ", [("left", left), ("top", top), ("width", width), ("height", height)] + [("on" + k, v) for k, v in nav.items()])
    return out + layout("itemlayout", False) + layout("focusedlayout", True) + "      </control>\n"


def chip_list(left, top, width, nav):
    item = 148

    def chip_label(color, visible):
        return ('          <control type="label">\n' + tags("            ", [
            ("left", 28), ("top", 0), ("width", item - 38), ("height", 34), ("label", "$INFO[ListItem.Property(label)]"), ("font", "font12"),
            ("textcolor", color), ("align", "left"), ("aligny", "center")] + ([("visible", visible)] if visible else [])) + "          </control>\n")

    def layout(tag, focused):
        out = '        <%s width="%d" height="34">\n' % (tag, item)
        out += '          <control type="image">\n' + tags("            ", [("left", 0), ("top", 0), ("width", item - 4), ("height", 34)])
        out += '            <texture border="%d">ms_fgf_row.png</texture>\n          </control>\n' % ROWB
        if focused:
            out += '          <control type="image">\n' + tags("            ", [("left", 0), ("top", 0), ("width", item - 4), ("height", 34)])
            out += '            <texture border="%d">ms_fgf_focus.png</texture>\n' % ROWB
            out += "            <visible>Control.HasFocus(5000)</visible>\n          </control>\n"
            out += '          <control type="image">\n' + tags("            ", [("left", 6), ("top", 31), ("width", item - 16), ("height", 2)])
            out += "            <texture>white.png</texture>\n" + tags("            ", [("colordiffuse", P % "ms_text"), ("visible", "!Control.HasFocus(5000)")])
            out += "          </control>\n"
        out += '          <control type="image">\n' + tags("            ", [("left", 10), ("top", 11), ("width", 12), ("height", 12)])
        out += "            <texture>$INFO[ListItem.Property(type_chip)]</texture>\n          </control>\n"
        if focused:
            out += chip_label(P % "ms_text", "!Control.HasFocus(5000)") + chip_label(P % "ms_text_focus", "Control.HasFocus(5000)")
        else:
            out += chip_label(P % "ms_text", "")
        for kind, color in (("nested", NESTED), ("overlapping", OVERLAPPING)):
            out += '          <control type="image">\n' + tags("            ", [("left", item - 22), ("top", 13), ("width", 8), ("height", 8)])
            out += "            <texture>white.png</texture>\n" + tags("            ", [
                ("colordiffuse", color), ("visible", "String.IsEqual(ListItem.Property(segment_type),%s)" % kind)]) + "          </control>\n"
        return out + "        </%s>\n" % tag
    out = '      <control type="list" id="5000">\n'
    out += tags("        ", [("left", left), ("top", top), ("width", width), ("height", 34), ("orientation", "horizontal")] +
                [("on" + k, v) for k, v in nav.items()])
    return out + layout("itemlayout", False) + layout("focusedlayout", True) + "      </control>\n"


HEAD = """<?xml version="1.0" encoding="UTF-8"?>
<!-- Written by tools/gen_segment_editor_layouts.py: edit that, not this file. %s -->
<window>
  <coordinates>
    <system>1</system>
    <posx>0</posx>
    <posy>0</posy>
    <width>1280</width>
    <height>720</height>
  </coordinates>
  <zorder>1</zorder>
  <defaultcontrol>5018</defaultcontrol>
  <animation type="WindowOpen">
    <effect type="fade" start="0" end="100" time="200" />
  </animation>
  <animation type="WindowClose">
    <effect type="fade" start="100" end="0" time="150" />
  </animation>

  <controls>
    <control type="image">
      <left>0</left>
      <top>0</top>
      <width>1280</width>
      <height>720</height>
      <texture>white.png</texture>
      <colordiffuse>F0000000</colordiffuse>
      <visible>String.IsEqual(Window.Property(EnableFullscreenOverlay),true)</visible>
    </control>
"""


def group(left, top, width, height, body):
    out = '    <control type="group">\n' + tags("      ", [("left", left), ("top", top), ("width", width), ("height", height)])
    out += image(0, 0, width, height, "ms_fgf_panel.png", border=style.PANEL_BORDER)
    return out + body + "    </control>\n"


def header(left, top, text):
    return label(left + 2, top, 300, 14, text, "font10", P % "ms_text3")


# Layout A as the round-3 mockup (ED3-A), in 720p units (mockup pixels / 1.5).
A_LABELS = {
    5037: "Start = now", 5038: "End = now", 5027: "Snap start", 5028: "Snap end", 5041: "Merge", 5042: "Split",
    5043: "Fix overlap", 5021: "Edit", 5022: "Delete",
    5015: "Set as start", 5029: "Start of file", 5016: "Set as end", 5030: "End of file", 5017: "Create",
    5023: "Start at end of segment", 5024: "End at start of segment",
    5025: "Jump to", 5005: "Add current + typed time", 5002: "Type start + end", 5004: "Delete all",
    5040: "Undo", 5026: "Upload", 5006: "Save", 5007: "Exit",
}
# The panels stand 16 from the left and right edges of the screen (the mockup has 35 and 29): the 32 units
# that gives all go to the list, whose rows need them for a long type name and for the source.
A_PANEL = (16, 33, 424, 657)
A_DRAWER = (453, 413, 811, 277)
A_TRACK = (20, 64, 771, 37)  # inside the drawer
A_ROW_H, A_BUTTON_H = 43, 29


def a_button(cid, left, top, width, nav):
    return button(cid, left, top, width, nav, height=A_BUTTON_H).replace(
        "<label>%s</label>" % LABELS[cid], "<label>%s</label>" % A_LABELS.get(cid, LABELS[cid]))


def a_row(ids, left, top, widths, gap, up, down, left_exit=None, right_exit=None):
    assert len(ids) == len(widths), (ids, widths)
    out, x = "", left
    for i, (cid, width) in enumerate(zip(ids, widths)):
        nav = {
            "left": ids[i - 1] if i else left_exit,
            "right": ids[i + 1] if i + 1 < len(ids) else right_exit,
            "up": up[i] if isinstance(up, tuple) else up,
            "down": down[i] if isinstance(down, tuple) else down,
        }
        out += a_button(cid, x, top, width, nav)
        x += width + gap
    return out, x - gap


# The text sizes of a list row, as zooms of the skin's fonts (font12 is 23 pixels and font10 21 in Aeon
# Fuse; the mockup's rows have 21 for the name and the times, 17 for the length, 16 for the source and
# 14 for the flag). A row is inside a list, where the editor cannot set a size, so they are fixed here.
ROW_ZOOM = {"name": 91, "range": 91, "length": 81, "source": 76, "flag": 68}


def a_list(left, top, width, height, nav):
    """The segments, one line each: the type's colour, its name, from - to, its length, a flag when it
    lies inside or runs into another, and its source."""
    def cell(x, w, text, font, color, zoom, align="left", visible=None, scroll=False):
        # A label is zoomed around its own middle. Its box is made so much wider that the zoomed box is
        # ``w`` wide, and set back so that the text still starts (or ends) at the place asked for.
        z = zoom / 100.0
        box = int(round(w / z))
        if align == "left":
            bx = x - (box - w) / 2.0
        elif align == "right":
            bx = x + w - box + (box - w) / 2.0
        else:
            bx = x + w / 2.0 - box / 2.0
        out = '          <control type="label">\n' + tags("            ", [
            ("left", int(round(bx))), ("top", 0), ("width", box), ("height", A_ROW_H - 3), ("label", text), ("font", font),
            ("textcolor", color), ("align", align), ("aligny", "center")]
            + ([("scroll", "true")] if scroll else []) + ([("visible", visible)] if visible else []))
        out += ('            <animation effect="zoom" start="%d" end="%d" center="auto" time="0" condition="true">Conditional'
                "</animation>\n" % (zoom, zoom))
        return out + "          </control>\n"

    flagged = "!String.IsEqual(ListItem.Property(segment_type),normal)"
    plain = "String.IsEqual(ListItem.Property(segment_type),normal)"
    right = width - 19

    def layout(tag, focused):
        out = '        <%s width="%d" height="%d">\n' % (tag, width, A_ROW_H)
        if focused:
            out += '          <control type="image">\n' + tags("            ", [("left", 7), ("top", 0), ("width", width - 14), ("height", A_ROW_H - 3)])
            out += '            <texture border="%d">ms_fgf_row.png</texture>\n          </control>\n' % ROWB
        out += '          <control type="image">\n' + tags("            ", [("left", 20), ("top", 15), ("width", 10), ("height", 10)])
        out += "            <texture>$INFO[ListItem.Property(type_chip)]</texture>\n          </control>\n"
        # name (room for Commercial and Featurette), from - to (room for a film: 1:47:40 - 1:51:12), length
        out += cell(39, 104, "[B]$INFO[ListItem.Property(label)][/B]", "font12", P % "ms_text", ROW_ZOOM["name"], scroll=focused)
        out += cell(147, 112, "$INFO[ListItem.Property(range)]", "font12", P % "ms_text", ROW_ZOOM["range"])
        out += cell(261, 34, "$INFO[ListItem.Property(length)]", "font10", P % "ms_text3", ROW_ZOOM["length"])
        # a segment that lies inside another, or runs into one: a small rounded flag after its length
        for kind, color in (("nested", "FFFF6F61"), ("overlapping", "FF5AA9F0")):
            shown = "String.IsEqual(ListItem.Property(segment_type),%s)" % kind
            out += '          <control type="image">\n' + tags("            ", [("left", 297), ("top", 12), ("width", 48), ("height", 16)])
            out += '            <texture border="6">seg_tag.png</texture>\n' + tags("            ", [("colordiffuse", color), ("visible", shown)])
            out += "          </control>\n"
        out += cell(297, 48, "[B]$INFO[ListItem.Property(flag)][/B]", "font10", "FF101216", ROW_ZOOM["flag"], align="center",
                    visible=flagged).replace("<height>%d</height>" % (A_ROW_H - 3), "<height>%d</height>" % (A_ROW_H - 3))
        # the source at the right end: all the room after the length, or what the flag leaves of it
        out += cell(297, right - 297, "$INFO[ListItem.Property(source)]", "font10", P % "ms_text3", ROW_ZOOM["source"],
                    align="right", visible=plain)
        out += cell(349, right - 349, "$INFO[ListItem.Property(source)]", "font10", P % "ms_text3", ROW_ZOOM["source"],
                    align="right", visible=flagged, scroll=focused)
        return out + "        </%s>\n" % tag

    out = '      <control type="list" id="5000">\n'
    out += tags("        ", [("left", left), ("top", top), ("width", width), ("height", height)] + [("on" + k, v) for k, v in nav.items()])
    return out + layout("itemlayout", False) + layout("focusedlayout", True) + "      </control>\n"


def a_timeline():
    """The track with a word in every block, a frame round the highlighted segment, the playhead, the
    times under it, and over it a thin bar for the whole file with the stretch that is shown."""
    left, top, width, height = A_TRACK
    out = label(19, 14, 300, 16, P % "ed_timeline", "font10", P % "ms_text2", cid=lay.HEAD_TIMELINE_ID)
    out += label(width + left - 420, 14, 420, 16, "", "font10", P % "ms_text3", cid=lay.END_LABEL_ID, align="right")
    # the whole file, thin
    out += image(left, 39, width, 6, "seg_tag.png", cid=lay.OVERVIEW_ID, border=3, extra=[("colordiffuse", "30FFFFFF")])
    for cid in lay.OVERVIEW_BLOCK_IDS:
        out += image(-9999, 39, 4, 6, "seg_other.png", cid=cid, border=2)
    out += image(-9999, 35, 20, 14, "seg_frame.png", cid=lay.OVERVIEW_WINDOW_ID, border=6)
    # the stretch that is shown
    out += image(left, top, width, height, "ms_fgf_inset.png", cid=lay.TRACK_ID, border=ROWB)
    for cid in lay.BLOCK_IDS:  # parked off screen until Python places them
        out += image(-9999, top, 10, height, "segb_other.png", cid=cid, border=10)
    for cid in lay.HANDLE_IDS:  # the two handles inside the highlighted block
        out += image(-9999, top + 8, 3, height - 16, "seg_tag.png", cid=cid, border=1, extra=[("colordiffuse", "B4101216")])
    for cid in lay.BLOCK_LABEL_IDS:
        out += label(-9999, top, 60, height, "", "font10", "FF101216", cid=cid).replace(
            "<shadowcolor>%s</shadowcolor>" % (P % "ms_shadow"), "<shadowcolor>00000000</shadowcolor>")
    out += image(-9999, top - 2, 20, height + 4, "seg_frame.png", cid=lay.OUTLINE_ID, border=10)
    # the mark of the Drawer layout (a line under the block) has no part here: the frame does its work
    out += image(-9999, top + height + 2, 10, 3, "seg_flat.png", cid=lay.SELECTED_MARK_ID, extra=[("colordiffuse", "00FFFFFF")])
    out += image(-9999, top - 7, 2, height + 14, "seg_flat.png", cid=lay.PLAYHEAD_ID, extra=[("colordiffuse", P % "ms_text")])
    out += image(-9999, top - 12, 9, 6, "seg_head.png", cid=lay.PLAYHEAD_HEAD_ID, extra=[("colordiffuse", P % "ms_text")])
    # the times under the ends of the highlighted segment
    out += label(-9999, top + height + 5, 80, 14, "", "font10", P % "ms_text2", cid=lay.TIME_SEG_START_ID, align="center")
    out += label(-9999, top + height + 5, 80, 14, "", "font10", P % "ms_text2", cid=lay.TIME_SEG_END_ID, align="center")
    # the times: where the track starts and ends, and the playhead
    out += label(left, top + height + 5, 90, 14, "", "font10", P % "ms_text3", cid=lay.TIME_START_ID)
    out += label(left + width - 90, top + height + 5, 90, 14, "", "font10", P % "ms_text3", cid=lay.TIME_END_ID, align="right")
    out += label(-9999, top + height + 5, 80, 14, "", "font10", P % "ms_text", cid=lay.TIME_NOW_ID, align="center")
    return out


def layout_a():
    """List and drawer, as the round-3 mockup."""
    px, py, pw, ph = A_PANEL
    body = label(19, 18, pw - 38, 14, P % "ed_kicker", "font10", P % "ms_text3", cid=lay.KICKER_ID)
    # the large "4 segments" is drawn by the editor itself at the mockup's size: this only keeps its place
    body += image(19, 36, pw - 38, 34, "-", cid=lay.TITLE_BOX_ID)
    body += label(19, 74, pw - 38, 20, "$INFO[VideoPlayer.TVShowTitle,, · ]$INFO[VideoPlayer.Season,S,]"
                  "$INFO[VideoPlayer.Episode, E, · ]$INFO[VideoPlayer.Title]", "font12", P % "ms_text2", extra=[("scroll", "true")])
    body += label(19, 99, pw - 38, 18, "Current Time: --:--:--", "font10", P % "ms_text2", cid=5001)
    body += label(19, 117, pw - 38, 18, "", "font10", P % "ms_accent", cid=5008, extra=[("scroll", "true")])
    # From a segment in the list: Left goes to its nine actions under the list, Right to the timeline's
    # seek and jump controls in the drawer.
    body += a_list(1, 146, pw - 2, 8 * A_ROW_H, {"left": 5037, "right": 5018, "down": lay.LOOK_BUTTON_IDS[0], "up": 5037})
    # Look: the dark overlay behind the editor, the look of its panels, the video small or full screen
    body += label(15, 494, pw - 30, 14, P % "ed_look", "font10", P % "ms_text3", cid=lay.HEAD_LOOK_ID)
    x = 9
    looks = lay.LOOK_BUTTON_IDS
    for index, (cid, wide) in enumerate(zip(looks, (133, 134, 133))):
        nav = {"left": 5000 if index == 0 else looks[index - 1], "right": looks[index + 1] if index < 2 else 5018,
               "up": 5000, "down": ROW_ACTIONS[index]}
        out = '      <control type="button" id="%d">\n' % cid
        out += tags("        ", [("left", x), ("top", 509), ("width", wide), ("height", A_BUTTON_H), ("label", ""),
                                 ("font", "font10"), ("textcolor", P % "ms_text"), ("focusedcolor", P % "ms_text_focus")])
        out += '        <texturenofocus border="%d">ms_fgf_row.png</texturenofocus>\n' % ROWB
        out += '        <texturefocus border="%d">ms_fgf_focus.png</texturefocus>\n' % ROWB
        out += tags("        ", [("shadowcolor", "00000000"), ("aligny", "center"), ("align", "center"), ("textoffsetx", 0)])
        out += tags("        ", [("on" + k, v) for k, v in nav.items()])
        body += out + "      </control>\n"
        x += wide + 3
    body += label(15, 541, pw - 30, 14, P % "ed_selected", "font10", P % "ms_text3", cid=lay.HEAD_SELECTED_ID)
    grid = (ROW_ACTIONS[0:3], ROW_ACTIONS[3:6], ROW_ACTIONS[6:9])
    tops = (556, 588, 620)
    for r, ids in enumerate(grid):
        part, end = a_row(ids, 9, tops[r], (133, 134, 133), 3,
                          up=lay.LOOK_BUTTON_IDS if r == 0 else grid[r - 1],
                          down=5000 if r == 2 else grid[r + 1], right_exit=5018,
                          left_exit=5000)
        assert end == pw - 9, end
        body += part
    left_panel = group(px, py, pw, ph, body)
    # the drawer
    dx, dy, dw, dh = A_DRAWER
    d = a_timeline()
    d += label(11, 126, 300, 12, P % "ed_seek", "font10", P % "ms_text3", cid=lay.HEAD_SEEK_ID)
    part, end = a_row(SEEK, 10, 141, (49,) * 7 + (61,) + (49,) * 7, 3, up=5000, down=5015, left_exit=5000)
    assert end <= dw - 10, end
    d += part
    d += label(11, 174, 300, 12, P % "ed_mark", "font10", P % "ms_text3", cid=lay.HEAD_MARK_ID)
    part, end = a_row(MARK_A, 10, 189, (97, 95, 93, 89, 69, 164, 166), 3, up=5018, down=5025, left_exit=5000)
    assert end == dw - 10, end
    d += part
    d += label(11, 222, 300, 12, P % "ed_file", "font10", P % "ms_text3", cid=lay.HEAD_FILE_ID)
    part, end = a_row(FILE, 10, 237, (82, 160, 128, 110, 62, 78, 79, 71), 3, up=5015, down=5018, left_exit=5000)
    assert end == dw - 10, end
    d += part
    drawer = group(dx, dy, dw, dh, d)
    # over the picture: what is behind the editor, and under the panels what the keys do
    extra = '    <control type="group">\n' + tags("      ", [("left", 0), ("top", 0), ("width", 1280), ("height", 720)])
    # the video small above the timeline: Kodi draws it there only while a plain window lies under the editor
    # (video_stage); the editor shows it when it has opened over one
    vx, vy, vw, vh = lay.VIDEO_RECT
    extra += '      <control type="videowindow" id="%d">\n' % lay.VIDEO_ID
    extra += tags("        ", [("left", vx), ("top", vy), ("width", vw), ("height", vh),
                              ("visible", "String.IsEqual(Window.Property(ed_video),true)")])
    extra += "      </control>\n"
    extra += image(dx + 10, 45, 80, 20, "seg_tag.png", border=6)
    # the label is wider than its tag: it is zoomed down around its middle, and must not be cut before that
    extra += label(dx - 20, 45, 140, 20, P % "ed_live", "font10", "FF101216", cid=lay.TAG_LIVE_ID, align="center").replace(
        "<shadowcolor>%s</shadowcolor>" % (P % "ms_shadow"), "<shadowcolor>00000000</shadowcolor>")
    extra += image(dx + 96, 45, 150, 20, "seg_tag.png", border=6, extra=[("colordiffuse", "B4101216")])
    extra += label(dx + 96, 45, 150, 20, P % "ed_overlay", "font10", P % "ms_text", cid=lay.TAG_OVERLAY_ID, align="center")
    extra += label(px + 10, 694, 1180, 18, P % "ed_hint", "font10", P % "ms_text2")
    extra += "    </control>\n"
    return HEAD % "Layout A: list and drawer." + left_panel + drawer + extra + "  </controls>\n</window>\n"


MARK_A = (5015, 5029, 5016, 5030, 5017, 5023, 5024)


def layout_b():
    """Drawer."""
    d = label(18, 8, 200, 20, "Segment Editor", "font12", P % "ms_text2")
    d += label(230, 8, 540, 20, "", "font12", "FFFFAA00", cid=5008, align="right", extra=[("scroll", "true")])
    d += label(780, 8, 420, 20, "Current Time: --:--:--", "font14", P % "ms_text2", cid=5001, align="right")
    d += chip_list(16, 34, 1184, {"down": 5037, "up": 5025})
    d += header(16, 74, "Selected segment")
    part, end = row(ROW_ACTIONS, 16, 90, (128,) * 9, 4, up=5000, down=5018)
    assert end == 1200, end
    d += part
    d += timeline(16, 144, 1184, 900, 300, 126)
    d += header(16, 182, "Seek")
    part, end = row(SEEK, 16, 198, (74,) * 7 + (92,) + (74,) * 7, 4, up=5037, down=5015)
    assert end == 1200, end
    d += part
    d += header(16, 234, "Mark")
    part, end = row(MARK, 16, 250, (128, 190, 120, 184, 88, 222, 228), 4, up=5018, down=5025)
    assert end == 1200, end
    d += part
    d += header(16, 286, "Segments and file")
    part, end = row(FILE, 16, 302, (100, 268, 238, 128, 98, 112, 112, 100), 4, up=5015, down=5000)
    assert end == 1200, end
    d += part
    return HEAD % "Layout B: drawer." + group(32, 344, 1216, 344, d) + "  </controls>\n</window>\n"


def expected() -> dict:
    """Path -> text of the four files (720p as drawn, 1080i through gen_skin_1080i.convert)."""
    out = {}
    for name, text in ((lay.XML_FILES[lay.LAYOUT_SIDE], layout_a()), (lay.XML_FILES[lay.LAYOUT_DRAWER], layout_b())):
        out[os.path.join(SKINS, "720p", name)] = text
        out[os.path.join(SKINS, "1080i", name)] = gen.convert(text)
    return out


def stale() -> list:
    bad = []
    for path, text in expected().items():
        try:
            with open(path, encoding="utf-8", newline="") as handle:
                if handle.read().replace("\r\n", "\n") != text:
                    bad.append(path)
        except OSError:
            bad.append(path)
    return bad


def main(argv) -> int:
    if "--check" in argv:
        bad = stale()
        for path in bad:
            print("stale or missing:", os.path.relpath(path, ROOT))
        return 1 if bad else 0
    for path, text in expected().items():
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        print("wrote", os.path.relpath(path, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
