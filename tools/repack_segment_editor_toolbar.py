# -*- coding: utf-8 -*-
"""Repack segment editor toolbar + list-row buttons (720p layout, scaled for 1080i)."""
import os
import re

ROOT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "skins", "default")

# All layout numbers are 720p bases unless noted; use sc(res, v) for 1080i.
PANEL_W_720 = 1170
PANEL_H_720 = 585
OVERLAY_TOP_720 = 445
OVERLAY_H_720 = 140
BTN_H_720 = 30
GAP_720 = 2
ROW_TOP_720 = (450, 490, 530)
LIST_ROW_TOP_720 = 110
LIST_ROW_START_720 = 425
SCALE = {"720p": 1.0, "1080i": 1.5}

ROW1 = (
    ("5031", 48, "-10m"),
    ("5032", 44, "-5m"),
    ("5033", 44, "-1m"),
    ("5011", 48, "-30s"),
    ("5010", 48, "-10s"),
    ("5009", 44, "-5s"),
    ("5019", 44, "-1s"),
    ("5018", 54, "Pause"),
    ("5020", 44, "+1s"),
    ("5012", 44, "+5s"),
    ("5013", 48, "+10s"),
    ("5014", 48, "+30s"),
    ("5034", 44, "+1m"),
    ("5035", 44, "+5m"),
    ("5036", 48, "+10m"),
)

ROW2 = (
    ("5015", 94, "Set as Start"),
    ("5029", 160, "Set to Start of File"),
    ("5016", 86, "Set as End"),
    ("5030", 150, "Set to End of File"),
    ("5017", 54, "Create"),
    ("5023", 188, "Start at End of Segment"),
    ("5024", 188, "End at Start of Segment"),
)

ROW3 = (
    ("5025", 68, "Jump To"),
    ("5005", 218, "Add Current + User Set Time"),
    ("5002", 188, "Manual Start + End Times"),
    ("5004", 78, "Delete All"),
    ("5040", 48, "Undo"),
    ("5026", 62, "Upload"),
    ("5006", 46, "Save"),
    ("5007", 44, "Exit"),
)

LIST_ROW = (
    ("5037", 105, "Start@Curr"),
    ("5038", 91, "End@Curr"),
    ("5027", 95, "Snap Start"),
    ("5028", 97, "Snap End"),
    ("5041", 75, "Merge"),
    ("5042", 53, "Split"),
    ("5043", 85, "Fix Ovl"),
    ("5021", 53, "Edit"),
    ("5022", 55, "Del"),
)


def sc(res, v):
    if res == "720p":
        return int(v)
    return int(round(v * SCALE[res]))


def pack_row_centered_fill(res, top, specs):
    """Min label widths, equal slack per button, remainder as side margins."""
    gap = sc(res, GAP_720)
    h = sc(res, BTN_H_720)
    panel_w = sc(res, PANEL_W_720)
    min_widths = [sc(res, w720) for _, w720, _ in specs]
    n = len(specs)
    gaps_total = gap * (n - 1)
    base = sum(min_widths) + gaps_total
    slack = panel_w - base
    if slack < 0:
        raise ValueError(f"row overflows panel by {-slack}px at {res}")

    bonus = slack // n
    side_margin = (slack % n) // 2

    out = {}
    x = side_margin
    for (cid, _, label), min_w in zip(specs, min_widths):
        w = min_w + bonus
        out[cid] = {"left": x, "top": top, "width": w, "height": h, "label": label}
        x += w + gap
    return out


def pack_list_row(res):
    gap = sc(res, GAP_720)
    h = sc(res, BTN_H_720)
    out = {}
    x = sc(res, LIST_ROW_START_720)
    top = sc(res, LIST_ROW_TOP_720)
    for cid, w720, label in LIST_ROW:
        w = sc(res, w720)
        out[cid] = {"left": x, "top": top, "width": w, "height": h, "label": label}
        x += w + gap
    return out


def list_row_lefts_720p():
    """720p left coords for segment_editor_dialog.py (before scale_skin_coord)."""
    x = LIST_ROW_START_720
    out = {}
    for cid, w, _ in LIST_ROW:
        out[cid] = x
        x += w + GAP_720
    return out


def toolbar_tuples_720p():
    """(id, x, y, w, label) for segment_editor_window_ui.py."""
    out = []
    for specs, top in zip((ROW1, ROW2, ROW3), ROW_TOP_720):
        layout = pack_row_centered_fill("720p", top, specs)
        for cid, _, label in specs:
            g = layout[cid]
            out.append((cid, g["left"], g["top"], g["width"], label))
    return out


def patch_button_block(block, geom):
    block = re.sub(r"<left>\d+</left>", f"<left>{geom['left']}</left>", block, count=1)
    block = re.sub(r"<top>\d+</top>", f"<top>{geom['top']}</top>", block, count=1)
    block = re.sub(
        r"<width(?:\s+min=\"\d+\"\s+max=\"\d+\")?>auto</width>|<width>\d+</width>",
        f"<width>{geom['width']}</width>",
        block,
        count=1,
    )
    block = re.sub(
        r"<height>\d+</height>",
        f"<height>{geom['height']}</height>",
        block,
        count=1,
    )
    block = re.sub(
        r"<label>[^<]*</label>",
        f"<label>{geom['label']}</label>",
        block,
        count=1,
    )
    block = re.sub(r"\s*<aspect>[^<]*</aspect>\s*\n", "\n", block)
    if "<textoffsetx>" not in block:
        block = block.replace(
            "<align>center</align>",
            "<align>center</align>\n        <textoffsetx>0</textoffsetx>",
            1,
        )
    return block


def patch_panel_frame(text, res):
    """Main panel height + bottom toolbar darkening stripe."""
    panel_h = sc(res, PANEL_H_720)
    overlay_top = sc(res, OVERLAY_TOP_720)
    overlay_h = sc(res, OVERLAY_H_720)

    text = re.sub(
        r"(<control type=\"group\">\s*<left>\d+</left>\s*<top>\d+</top>\s*<width>\d+</width>\s*)"
        r"<height>\d+</height>",
        lambda m: f"{m.group(1)}<height>{panel_h}</height>",
        text,
        count=1,
    )
    text = re.sub(
        r"(<!-- Panel background[^\n]*\n\s*<control type=\"image\">\s*"
        r"<left>0</left>\s*<top>0</top>\s*<width>\d+</width>\s*)"
        r"<height>\d+</height>",
        lambda m: f"{m.group(1)}<height>{panel_h}</height>",
        text,
        count=1,
    )
    if "<!-- Panel background" not in text:
        text = re.sub(
            r"(<control type=\"group\">.*?<control type=\"image\">\s*"
            r"<left>0</left>\s*<top>0</top>\s*<width>\d+</width>\s*)"
            r"<height>\d+</height>",
            lambda m: f"{m.group(1)}<height>{panel_h}</height>",
            text,
            count=1,
            flags=re.DOTALL,
        )

    text = re.sub(
        r"(<!-- Darkening overlay for bottom button rows[^\n]*\n\s*"
        r"<control type=\"image\">\s*<left>0</left>\s*<top>)\d+(</top>\s*"
        r"<width>\d+</width>\s*<height>)\d+(</height>)",
        lambda m: f"{m.group(1)}{overlay_top}{m.group(2)}{overlay_h}{m.group(3)}",
        text,
        count=1,
    )
    if "<!-- Darkening overlay" not in text:
        text = re.sub(
            r"(<control type=\"image\">\s*<left>0</left>\s*<top>)\d+(</top>\s*"
            r"<width>\d+</width>\s*<height>)\d+(</height>\s*"
            r"<texture>white\.png</texture>\s*<colordiffuse>E0000000</colordiffuse>)",
            lambda m: f"{m.group(1)}{overlay_top}{m.group(2)}{overlay_h}{m.group(3)}",
            text,
            count=1,
        )
    return text


def patch_file(res, path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    text = patch_panel_frame(text, res)

    layout = {}
    for specs, top720 in zip((ROW1, ROW2, ROW3), ROW_TOP_720):
        layout.update(pack_row_centered_fill(res, sc(res, top720), specs))
    layout.update(pack_list_row(res))

    for cid, geom in layout.items():
        pat = rf'(<control type="button" id="{cid}">.*?</control>)'
        m = re.search(pat, text, flags=re.DOTALL)
        if not m:
            raise RuntimeError(f"button {cid} not found in {path}")
        text = text[: m.start(1)] + patch_button_block(m.group(1), geom) + text[m.end(1) :]

    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def main():
    for res in ("720p", "1080i"):
        path = os.path.join(ROOT, res, "SegmentEditorDialog.xml")
        patch_file(res, path)
        print("repacked", path)
    print("list-row 720p lefts:", list_row_lefts_720p())
    print("toolbar 720p:", toolbar_tuples_720p())
    print("1080i btn height check:", sc("1080i", BTN_H_720))


if __name__ == "__main__":
    main()
