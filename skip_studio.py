# -*- coding: utf-8 -*-
"""The Studio: the Customize screen of the skip dialog (geometry and ids; no Kodi needed).

Three panels in the Fused Glass Dark look, each with a shadow: the settings at the left (six tabs,
a page of rows, Save / Save as preset / Reset), the live preview at the top right (the whole screen
drawn small, with the dialog where it will sit) and, under it, what the row in focus does (the
presets while the Preset row has the focus). The measures are those of the round-3 mockup.

``tools/gen_skip_studio.py`` writes ``SkipStudio.xml`` from this; ``skip_studio_ui.py`` runs it.
Everything is in 720p units.
"""

from __future__ import annotations

XML = "SkipStudio.xml"

# --- ids ---------------------------------------------------------------------------------------
ID_TAB_FIRST = 4301
ID_ROW_FIRST = 4311
ID_SAVE = 4331
ID_SAVE_PRESET = 4332
ID_RESET = 4333
ID_SCREEN = 4400  # the small screen of the live preview
ID_FANART = 4071  # the picture behind the preview (same id as in the classic Customize screen)

TABS = ("look", "layout", "text", "buttons", "motion", "behaviour")
TAB_LABEL_IDS = (49020, 49021, 49022, 49023, 49126, 49127)
TAB_LABELS = ("Look", "Layout", "Text", "Buttons", "Motion", "Behaviour")
ROWS = 10  # row slots on a page: a tab with more rows scrolls
SEG_OPTIONS = 4  # most choices a switch row can show side by side
SWATCHES = 8  # colour dots a colour row can show
TILES = 5  # preset tiles in the strip; the middle one is the current preset
PREVIEWS = 1  # the tag over the live preview: the segment type it shows

# ids of the parts Python moves or fills (per row slot)
ID_SLIDER_FILL = 4341  # + slot
ID_SLIDER_KNOB = 4361  # + slot
ID_ABOUT = 4390  # the text of "About this setting"

# --- geometry (the round-3 mockup, 1080 px / 1.5) ------------------------------------------------
PANEL = (43, 37, 445, 629)  # left, top, width, height
STAGE = (504, 37, 733, 413)
STRIP = (504, 466, 733, 200)  # "About this setting", or the presets while the Preset row has the focus
SHADOW_GROW, SHADOW_DROP, SHADOW_BORDER = 34, 10, 60  # the shadow picture reaches past a panel

PAD = 19  # the text column: kicker, title and row names start here
ROW_LEFT, ROW_W, ROW_H, ROW_STEP = PANEL[0] + 8, PANEL[2] - 16, 41, 44
ROW_PAD = 16  # a row's name and its control stand this far inside the row
KICKER_TOP, TITLE_TOP, TITLE_H, TITLE_SIZE = PANEL[1] + 20, PANEL[1] + 36, 34, 28
TAB_TOP, TAB_H, TAB_GAP = 119, 29, 2
ROWS_TOP = 158
FOOT_H = 39
FOOT_TOP = PANEL[1] + PANEL[3] - 10 - FOOT_H
SEG_W, SEG_H, SEG_GAP = 62, 27, 1
SEG_WIDTHS = {2: 84, 3: 80, 4: 62}  # a choice is wider where fewer stand side by side (Compact, Rounded, Medium)
TOGGLE_W, TOGGLE_H = 36, 20
SWATCH, SWATCH_GAP = 15, 7
SLIDER_W, SLIDER_H, KNOB = 132, 4, 13
POS_DOT, POS_GAP = 5, 3  # the nine dots of a position row

SCREEN_ZOOM = 57  # percent: 1280 x 720 becomes about 730 x 410 inside the stage
CANVAS_W, CANVAS_H = 1280, 720
TILE_W, TILE_H, TILE_GAP = 133, 82, 10
TILE_TOP = STRIP[1] + 36
TAG_TOP, TAG_H = STAGE[1] + 9, 22


# --- the preset wall (SkipPresetWall.xml): every preset as a tile, a page at a time -------------
WALL_XML = "SkipPresetWall.xml"
ID_WALL_FIRST = 4501
WALL_COLS, WALL_ROWS = 4, 3
WALL_TILES = WALL_COLS * WALL_ROWS
WALL_TILE_W, WALL_TILE_H = 284, 160  # 16:9, the shape of the miniatures
WALL_LEFT, WALL_TOP, WALL_STEP_X, WALL_STEP_Y = 46, 76, 302, 206


def wall_id(index) -> int:
    return ID_WALL_FIRST + int(index)


def wall_box(index) -> tuple:
    row, col = divmod(int(index), WALL_COLS)
    return WALL_LEFT + col * WALL_STEP_X, WALL_TOP + row * WALL_STEP_Y, WALL_TILE_W, WALL_TILE_H


def wall_pages(count) -> int:
    return max(1, (int(count) + WALL_TILES - 1) // WALL_TILES)


def wall_move(index, count, direction) -> int:
    """The item the focus moves to from ``index`` among ``count`` items: ``left`` / ``right`` step one
    item (and so turn the page at an edge), ``up`` / ``down`` step a row. It stops at both ends."""
    step = {"left": -1, "right": 1, "up": -WALL_COLS, "down": WALL_COLS}[direction]
    target = int(index) + step
    if target < 0 or target >= int(count):
        if direction == "down" and index // WALL_COLS < (count - 1) // WALL_COLS:
            return count - 1  # the last row is shorter: go to its last item
        return int(index)
    return target


def tab_id(index) -> int:
    return ID_TAB_FIRST + int(index)


def row_id(index) -> int:
    return ID_ROW_FIRST + int(index)


TAB_SHARES = (54, 64, 52, 72, 68, 92)  # a tab is as wide as its word needs


def tab_box(index) -> tuple:
    left = ROW_LEFT + ROW_PAD - 10
    room = ROW_LEFT + ROW_W - ROW_PAD + 10 - left - (len(TABS) - 1) * TAB_GAP
    widths = [room * share // sum(TAB_SHARES) for share in TAB_SHARES]
    return left + sum(widths[:index]) + index * TAB_GAP, TAB_TOP, widths[index], TAB_H


def row_box(index) -> tuple:
    return ROW_LEFT, ROWS_TOP + index * ROW_STEP, ROW_W, ROW_H


def control_right(row) -> int:
    """Where a row's control ends: the right end of the row, inside its padding."""
    left, _top, width, _height = row_box(row)
    return left + width - ROW_PAD


def seg_box(row, option, count=SEG_OPTIONS) -> tuple:
    """A choice of a switch row with ``count`` choices; they are packed against the right end of the row."""
    _left, top, _width, height = row_box(row)
    wide = SEG_WIDTHS.get(count, SEG_W)
    x = control_right(row) - (count - option) * wide - (count - 1 - option) * SEG_GAP
    return x, top + (height - SEG_H) // 2, wide, SEG_H


def toggle_box(row) -> tuple:
    _left, top, _width, height = row_box(row)
    return control_right(row) - TOGGLE_W, top + (height - TOGGLE_H) // 2, TOGGLE_W, TOGGLE_H


def swatch_box(row, index, count=SWATCHES) -> tuple:
    """A colour dot of a colour row with ``count`` dots, packed against the right end."""
    _left, top, _width, height = row_box(row)
    x = control_right(row) - (count - index) * SWATCH - (count - 1 - index) * SWATCH_GAP
    return x, top + (height - SWATCH) // 2, SWATCH, SWATCH


def slider_box(row) -> tuple:
    """The track of a slider row."""
    _left, top, _width, height = row_box(row)
    return control_right(row) - SLIDER_W, top + (height - SLIDER_H) // 2, SLIDER_W, SLIDER_H


def knob_left(row, share) -> int:
    """Left of the slider knob for a share between 0 and 1."""
    x, _y, width, _h = slider_box(row)
    share = max(0.0, min(1.0, float(share)))
    return int(round(x + share * width - KNOB / 2.0))


def pos_box(row, place) -> tuple:
    """One of the nine dots of a position row (0 = top left ... 8 = bottom right)."""
    _left, top, _width, height = row_box(row)
    size = 3 * POS_DOT + 2 * POS_GAP
    x0, y0 = control_right(row) - size, top + (height - size) // 2
    return x0 + (place % 3) * (POS_DOT + POS_GAP), y0 + (place // 3) * (POS_DOT + POS_GAP), POS_DOT, POS_DOT


def value_right(row, kind="pick") -> int:
    """Where the written value of a row ends: before its slider or its dots, else at the control's end."""
    if kind == "slider":
        return slider_box(row)[0] - 12
    if kind == "pos":
        return pos_box(row, 0)[0] - 10
    return control_right(row)


def foot_boxes() -> tuple:
    """Save, Save as preset, Reset."""
    left, right = ROW_LEFT, ROW_LEFT + ROW_W
    reset, preset = 76, 139
    return (
        (left, FOOT_TOP, right - left - reset - preset - 12, FOOT_H),
        (right - reset - 6 - preset, FOOT_TOP, preset, FOOT_H),
        (right - reset, FOOT_TOP, reset, FOOT_H),
    )


def tag_box(index) -> tuple:
    """A tag over the live preview: 0 is the words Live preview, 1 the segment type it shows."""
    widths = (104, 320)
    left = STAGE[0] + 18 + sum(widths[:index]) + 6 * index
    return left, TAG_TOP, widths[index], TAG_H


def tile_box(index) -> tuple:
    total = TILES * TILE_W + (TILES - 1) * TILE_GAP
    left = STRIP[0] + (STRIP[2] - total) // 2
    return left + index * (TILE_W + TILE_GAP), TILE_TOP, TILE_W, TILE_H


def screen_origin() -> tuple:
    """Left and top of the small screen, centred in the stage."""
    width = CANVAS_W * SCREEN_ZOOM / 100.0
    height = CANVAS_H * SCREEN_ZOOM / 100.0
    return STAGE[0] + int(round((STAGE[2] - width) / 2.0)), STAGE[1] + int(round((STAGE[3] - height) / 2.0))


def window_of(items, current, count=TILES) -> list:
    """``count`` items around ``current`` (wrapping), the current one in the middle; shorter lists
    are padded with None so the current one stays in the middle."""
    items = list(items)
    if not items:
        return [None] * count
    half = count // 2
    if len(items) < count:
        out = [None] * count
        for offset in range(-half, half + 1):
            index = current + offset
            if 0 <= index < len(items):
                out[half + offset] = items[index]
        return out
    return [items[(current + offset) % len(items)] for offset in range(-half, half + 1)]
