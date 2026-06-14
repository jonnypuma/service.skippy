# -*- coding: utf-8 -*-
"""Apply Phase 1 segment editor skin tweaks (720p + 1080i)."""
import os
import re

ROOT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "skins", "default")

LABEL_OLD_START = "Set Start to Start of File"
LABEL_NEW_START = "Set to Start of File"
LABEL_OLD_END = "Set End to End of File"
LABEL_NEW_END = "Set to End of File"

# (control id, min, max) for auto width — max = previous fixed width
AUTO_720 = {
    "5029": (95, 218),
    "5030": (95, 208),
    "5023": (95, 208),
    "5024": (95, 208),
    "5005": (100, 378),
    "5002": (100, 350),
}

AUTO_1080 = {
    "5029": (143, 327),
    "5030": (143, 312),
    "5023": (143, 312),
    "5024": (143, 312),
    "5005": (150, 567),
    "5002": (150, 525),
}

BTN_H = {"720p": (30, 38), "1080i": (45, 57)}


def _patch_focused_scroll(text):
    """Add scroll to focusedlayout labels only (once each)."""
    marker = "<focusedlayout width="
    start = text.find(marker)
    if start < 0:
        return text
    end = text.find("</focusedlayout>", start)
    if end < 0:
        return text
    block = text[start:end]
    if "<scroll>true</scroll>" in block:
        return text

    def add_scroll(m):
        chunk = m.group(0)
        if "<scroll>" in chunk:
            return chunk
        return chunk.replace("</align>", "</align>\n            <scroll>true</scroll>", 1)

    new_block = re.sub(
        r"<control type=\"label\">.*?</control>",
        add_scroll,
        block,
        flags=re.DOTALL,
    )
    return text[:start] + new_block + text[end:]


def _patch_button_block(block, btn_h_new, auto_map, cid):
    block = block.replace(LABEL_OLD_START, LABEL_NEW_START)
    block = block.replace(LABEL_OLD_END, LABEL_NEW_END)
    if cid in auto_map:
        mn, mx = auto_map[cid]
        block = re.sub(
            r"<width>\d+</width>",
            f'<width min="{mn}" max="{mx}">auto</width>',
            block,
            count=1,
        )
    block = re.sub(
        r"<height>\d+</height>",
        f"<height>{btn_h_new}</height>",
        block,
        count=1,
    )
    return block


def patch_file(res, path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    orig = text
    text = _patch_focused_scroll(text)

    old_h, new_h = BTN_H[res]
    auto_map = AUTO_720 if res == "720p" else AUTO_1080

    # Toolbar + list-row action buttons (ids 5002-5043 range except list 5000)
    for cid in sorted(set(list(auto_map.keys()) + [
        "5031", "5032", "5033", "5011", "5010", "5009", "5019", "5018", "5020",
        "5012", "5013", "5014", "5034", "5035", "5036", "5015", "5016", "5017",
        "5025", "5004", "5040", "5026", "5006", "5007",
        "5037", "5038", "5027", "5028", "5041", "5042", "5043", "5021", "5022",
    ]), key=int):
        pat = rf'(<control type="button" id="{cid}">.*?</control>)'
        m = re.search(pat, text, flags=re.DOTALL)
        if not m:
            continue
        new_block = _patch_button_block(m.group(1), new_h, auto_map, cid)
        text = text[: m.start(1)] + new_block + text[m.end(1) :]

    if text != orig:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        return True
    return False


def main():
    for res in ("720p", "1080i"):
        path = os.path.join(ROOT, res, "SegmentEditorDialog.xml")
        if patch_file(res, path):
            print("patched", path)


if __name__ == "__main__":
    main()
