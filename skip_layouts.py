# -*- coding: utf-8 -*-
"""The layouts of the skip dialog besides the classic card, and the looks they are drawn in.

``Card`` is the dialog of every earlier version (``SkipDialog_<corner>.xml``, the presets, the
Customize screen). Every other layout is a skin file of its own, ``SkipLayout_<name><size>.xml``,
written by ``tools/gen_skip_layouts.py``. Those files hold no texts, colours or pictures of their
own: all of it comes from window properties (``skl_*``) that ``skip_layout_dialog.py`` sets, so
one file serves the six looks.

Sizes follow the skip dialog mode: Full uses the full file, Compact Full the compact one. Minimal
mode keeps the classic chip.

Everything here is in 720p units and needs no Kodi, so the generator and the tests can read it.
"""

from __future__ import annotations

from dataclasses import dataclass

KEY_LAYOUT = "skip_dialog_layout"
KEY_LOOK = "skip_layout_look"
KEY_BAR_COLOR = "skip_layout_bar_color"
KEY_OVERLAY = "skip_layout_overlay"  # a shade behind the dialog
KEY_APPEAR = "skip_layout_appear"  # how the dialog comes
KEY_LEAVE = "skip_layout_leave"  # and goes
KEY_PULSE = "skip_layout_pulse"  # it beats in the last five seconds

# (stored value, string id, English name)
OVERLAY_NONE = "None"
OVERLAY_AUTO = "Auto"  # the shade a design has of its own (the Dial's rounded one); a card has none
OVERLAY_NAMES = (
    (OVERLAY_AUTO, 49085, "The design's own"),
    (OVERLAY_NONE, 49052, "None"),
    ("Square", 49053, "Square"),  # a hard rectangle out of the screen corner
    ("SquareFade", 49054, "Square, fading"),  # the same, fading out towards the picture
    ("Round", 49055, "Rounded"),  # a rounded shade that hugs the dialog
    ("RoundFade", 49056, "Rounded, fading"),  # light at the top left, full at the bottom right
    ("Band", 49057, "Band"),  # across the whole screen, fading away from its edge
    ("Glow", 49058, "Corner glow"),  # a round shade from the corner, no edge anywhere
)
OVERLAYS = tuple(row[0] for row in OVERLAY_NAMES)
APPEAR_NAMES = (("Fade", 49061, "Fade"), ("Rise", 49062, "Rise"), ("Pop", 49063, "Pop"), ("Slide", 49064, "Slide in"))
APPEARS = tuple(row[0] for row in APPEAR_NAMES)
LEAVE_NAMES = (("Fade", 49061, "Fade"), ("Drop", 49067, "Drop"), ("Shrink", 49068, "Shrink"))
LEAVES = tuple(row[0] for row in LEAVE_NAMES)
PULSE_SECONDS = 5
# window properties every layout file reads besides those of a look
HEAD_PROPERTIES = ("skl_overlay", "skl_overlay9", "skl_in", "skl_out", "skl_pulse")
OVERLAY_MARGIN = 20  # how far a shade reaches past the dialog
OVERLAY_BORDER = 24  # nine-slice border of the rounded shades

# What colours the progress (bar, ring, tile fill, timeline) of a new layout.
BAR_TYPE = "Type"  # the colour of the segment type, as in the segment editor (the default)
BAR_LOOK = "Look"  # the accent of the look
BAR_COLOR_NAMES = ((BAR_TYPE, "Segment type"), (BAR_LOOK, "Look"))

LAYOUT_CARD = "Card"
# (stored value, name shown)
LAYOUT_NAMES = (
    (LAYOUT_CARD, "Card"),
    ("Stack", "Stack card"),  # drawn by Skippy itself (skip_canvas)
    ("Slab", "Corner slab"),
    ("Dial", "Dial"),
    ("Band", "Cinema band"),
    ("Float", "Float"),
    ("Split", "Split"),
    ("Timeline", "Timeline"),
    ("Rail", "Side rail"),
    ("Poster", "Poster card"),
)
LAYOUTS = tuple(stored for stored, _name in LAYOUT_NAMES)
NEW_LAYOUTS = LAYOUTS[1:]

DEFAULT_LOOK = "fgf"
# What a new installation shows: the Stack card in Fused Glass Dark
DEFAULT_LAYOUT = "Stack"
DEFAULT_SKIP_LOOK = "fgd"
# (stored value, name shown): the looks of the skin Aeon Fuse
LOOK_NAMES = (
    ("fgd", "Fused Glass Dark"),
    ("fgf", "Fused Glass Frost"),
    ("fgc", "Fused Glass Clear"),
    ("fgs", "Fused Glass style"),
    ("aeo", "Aeon"),
    ("agl", "Aeon Glass"),
    # twelve looks of their own, not tied to a skin
    ("neon", "Neon"),
    ("paper", "Paper"),
    ("sunset", "Sunset"),
    ("ocean", "Ocean"),
    ("brutal", "Brutal"),
    ("term", "Terminal"),
    ("line", "Wireframe"),
    ("luxe", "Luxe"),
    ("pastel", "Pastel"),
    ("gloss", "Gloss"),
    ("mono", "Mono"),
    ("vhs", "VHS"),
)
LOOKS = tuple(stored for stored, _name in LOOK_NAMES)
FUSE_LOOKS = LOOKS[:6]
OWN_LOOKS = LOOKS[6:]
# layouts whose texts and buttons sit straight on the video (a soft shade at most), not on a plate
BARE_LAYOUTS = ("Dial", "Band", "Float")
OPEN = "_o"  # a look with a light plate has a twin for those layouts: light text, its own buttons

SIZE_FULL = "full"
SIZE_COMPACT = "compact"
SIZE_MINIMAL = "minimal"  # the Skip button and the time left, nothing else
SIZES = (SIZE_FULL, SIZE_COMPACT, SIZE_MINIMAL)

CANVAS_W, CANVAS_H = 1280, 720
MARGIN = 32  # from the screen edge to a layout that floats in a corner
PLATE_BORDER = 20  # nine-slice border of the plate pictures
BUTTON_H = 28  # every text button; the pill pictures are cut for this height
BUTTON_BORDER_720, BUTTON_BORDER_1080 = 14, 21  # nine-slice border of the button pictures per skin folder
RING_FRAMES = 50  # sl_ring_00.png (empty) .. sl_ring_50.png (full)

# Control ids shared by every layout file.
ID_ROOT = 3200
ID_PROBE = 3290  # an unseen image as wide as the classic card, so the skin folder can be told apart
ID_SKIP = 3210
ID_CLOSE = 3220
ID_BAR_FILL = 3231  # the line (width grows) or the tile fill (height grows)
ID_RING = 3240
ID_NESTED = 3251  # Timeline: the block of the nested segment
ID_PLAYHEAD = 3252
PROBE_W = 430

# The preview in Customize Skip Dialog: the whole screen drawn small inside the preview stage, a
# copy of every layout in it, and two pickers under the stage.
STAGE_LEFT, STAGE_TOP = 528, 16  # the stage group of SkipDialogCustomize.xml on the screen
STAGE_W, STAGE_H = 720, 540
MOCK_ZOOM = 56  # percent: 1280 x 720 becomes about 717 x 403
MOCK_LEFT, MOCK_TOP = 0, 68  # of the small screen inside the stage
ID_MOCK_SCREEN = 20990
ID_OVERLAY = 3295  # the rounded shades (nine-slice)
ID_OVERLAY_PLAIN = 3296  # the others (stretched)
ID_MOCK_OVERLAY = 20991
ID_MOCK_OVERLAY_PLAIN = 20992
ID_PICK_LAYOUT = 4145
ID_PICK_LOOK = 4146
CHIP_W, CHIP_TOP = 356, 566


def mock_offset(index) -> int:
    """What is added to every control id of the ``index``-th layout for its preview copy."""
    return 17800 + 100 * int(index)

TILE_INSET = 8  # Split: the fill keeps this far from the edge of its tile

PROGRESS_LINE = "line"
PROGRESS_RING = "ring"
PROGRESS_TILE = "tile"
PROGRESS_TIMELINE = "timeline"

ANCHOR_CORNER = "corner"  # floats MARGIN away from the chosen corner
ANCHOR_FLUSH = "flush"  # sits in the chosen corner itself
ANCHOR_BAND = "band"  # across the screen, at the bottom or the top
ANCHOR_EDGE = "edge"  # on the left or right edge, half way up
ANCHOR_CENTER = "center"  # centred, at the bottom or the top


@dataclass(frozen=True)
class Layout:
    """One skin file. ``track`` is where the progress is drawn: left, top, width, height."""

    name: str
    size: str
    width: int
    height: int
    anchor: str
    progress: str
    track: tuple
    has_close: bool = True
    has_next_line: bool = True  # room for the "next segment at" line
    canvas: bool = False  # drawn by skip_canvas: it has no skin file of its own

    @property
    def xml(self) -> str:
        if self.canvas:
            return CANVAS_XML
        return "SkipLayout_%s%s.xml" % (self.name, {SIZE_FULL: "", SIZE_COMPACT: "Compact"}.get(self.size, "Minimal"))


_ALL = (
    Layout("Slab", SIZE_FULL, 520, 122, ANCHOR_FLUSH, PROGRESS_LINE, (0, 0, 520, 4)),
    Layout("Slab", SIZE_COMPACT, 520, 44, ANCHOR_FLUSH, PROGRESS_LINE, (0, 0, 520, 4), has_next_line=False),
    Layout("Dial", SIZE_FULL, 470, 166, ANCHOR_CORNER, PROGRESS_RING, (16, 14, 92, 92)),
    Layout("Dial", SIZE_COMPACT, 312, 64, ANCHOR_CORNER, PROGRESS_RING, (10, 8, 48, 48), has_next_line=False),
    Layout("Band", SIZE_FULL, 1280, 150, ANCHOR_BAND, PROGRESS_LINE, (48, 126, 1184, 3)),
    Layout("Band", SIZE_COMPACT, 1280, 96, ANCHOR_BAND, PROGRESS_LINE, (48, 76, 1184, 3)),
    Layout("Float", SIZE_FULL, 470, 150, ANCHOR_CORNER, PROGRESS_RING, (280, 113, 22, 22)),
    Layout("Float", SIZE_COMPACT, 330, 40, ANCHOR_CORNER, PROGRESS_RING, (140, 9, 22, 22), has_close=False,
           has_next_line=False),
    Layout("Split", SIZE_FULL, 520, 104, ANCHOR_CORNER, PROGRESS_TILE, (324, 8, 124, 88)),
    Layout("Split", SIZE_COMPACT, 420, 44, ANCHOR_CORNER, PROGRESS_TILE, (204, 8, 156, 28), has_next_line=False),
    Layout("Timeline", SIZE_FULL, 640, 150, ANCHOR_CENTER, PROGRESS_TIMELINE, (20, 62, 600, 22)),
    Layout("Timeline", SIZE_COMPACT, 520, 52, ANCHOR_CENTER, PROGRESS_TIMELINE, (160, 30, 300, 8),
           has_next_line=False),
    Layout("Rail", SIZE_FULL, 184, 268, ANCHOR_EDGE, PROGRESS_RING, (50, 18, 84, 84)),
    Layout("Rail", SIZE_COMPACT, 184, 116, ANCHOR_EDGE, PROGRESS_RING, (16, 14, 48, 48), has_close=False,
           has_next_line=False),
    # the poster of the show or film at the left (kept last: the preview ids follow this order)
    Layout("Poster", SIZE_FULL, 520, 150, ANCHOR_CORNER, PROGRESS_LINE, (116, 100, 388, 4)),
    Layout("Poster", SIZE_COMPACT, 380, 72, ANCHOR_CORNER, PROGRESS_LINE, (62, 62, 306, 3), has_next_line=False),
)
# The Minimal forms come last, so the files and preview copies of the others keep their order.
_ALL = _ALL + (
    Layout("Slab", SIZE_MINIMAL, 230, 44, ANCHOR_FLUSH, PROGRESS_LINE, (0, 0, 230, 4), has_close=False, has_next_line=False),
    Layout("Dial", SIZE_MINIMAL, 216, 60, ANCHOR_CORNER, PROGRESS_RING, (8, 6, 48, 48), has_close=False, has_next_line=False),
    Layout("Band", SIZE_MINIMAL, 1280, 64, ANCHOR_BAND, PROGRESS_LINE, (48, 58, 1184, 3), has_close=False, has_next_line=False),
    Layout("Float", SIZE_MINIMAL, 200, 40, ANCHOR_CORNER, PROGRESS_RING, (10, 9, 22, 22), has_close=False, has_next_line=False),
    Layout("Split", SIZE_MINIMAL, 170, 44, ANCHOR_CORNER, PROGRESS_TILE, (8, 8, 154, 28), has_close=False, has_next_line=False),
    Layout("Timeline", SIZE_MINIMAL, 340, 44, ANCHOR_CENTER, PROGRESS_TIMELINE, (164, 18, 164, 8), has_close=False,
           has_next_line=False),
    Layout("Rail", SIZE_MINIMAL, 84, 92, ANCHOR_EDGE, PROGRESS_RING, (22, 8, 40, 40), has_close=False, has_next_line=False),
    Layout("Poster", SIZE_MINIMAL, 250, 54, ANCHOR_CORNER, PROGRESS_LINE, (50, 46, 192, 3), has_close=False, has_next_line=False),
)
# The drawn designs: Skippy places every part itself, so the sizes here are only what a design
# measures with everything shown. They are not in ``all_layouts()``, which lists the skin files.
CANVAS_XML = "SkipCanvas.xml"
CANVAS_LAYOUTS = ("Stack", "Slab", "Dial", "Band", "Float", "Split", "Timeline", "Rail")
_CANVAS = (
    Layout("Band", SIZE_FULL, 1195, 92, ANCHOR_BAND, PROGRESS_LINE, (0, 0, 0, 0), canvas=True),
    Layout("Band", SIZE_COMPACT, 1195, 55, ANCHOR_BAND, PROGRESS_LINE, (0, 0, 0, 0), has_next_line=False, canvas=True),
    Layout("Band", SIZE_MINIMAL, 1195, 40, ANCHOR_BAND, PROGRESS_LINE, (0, 0, 0, 0), has_close=False, has_next_line=False, canvas=True),
    Layout("Float", SIZE_FULL, 507, 141, ANCHOR_CORNER, PROGRESS_RING, (0, 0, 0, 0), canvas=True),
    Layout("Float", SIZE_COMPACT, 188, 40, ANCHOR_CORNER, PROGRESS_RING, (0, 0, 0, 0), has_next_line=False, canvas=True),
    Layout("Float", SIZE_MINIMAL, 169, 35, ANCHOR_CORNER, PROGRESS_RING, (0, 0, 0, 0), has_close=False, has_next_line=False, canvas=True),
    Layout("Split", SIZE_FULL, 513, 129, ANCHOR_CORNER, PROGRESS_TILE, (0, 0, 0, 0), canvas=True),
    Layout("Split", SIZE_COMPACT, 286, 51, ANCHOR_CORNER, PROGRESS_TILE, (0, 0, 0, 0), has_next_line=False, canvas=True),
    Layout("Split", SIZE_MINIMAL, 146, 51, ANCHOR_CORNER, PROGRESS_TILE, (0, 0, 0, 0), has_close=False, has_next_line=False, canvas=True),
    Layout("Timeline", SIZE_FULL, 627, 193, ANCHOR_CENTER, PROGRESS_LINE, (0, 0, 0, 0), canvas=True),
    Layout("Timeline", SIZE_COMPACT, 378, 56, ANCHOR_CENTER, PROGRESS_LINE, (0, 0, 0, 0), has_next_line=False, canvas=True),
    Layout("Timeline", SIZE_MINIMAL, 152, 56, ANCHOR_CENTER, PROGRESS_LINE, (0, 0, 0, 0), has_close=False, has_next_line=False, canvas=True),
    Layout("Rail", SIZE_FULL, 253, 363, ANCHOR_EDGE, PROGRESS_RING, (0, 0, 0, 0), canvas=True),
    Layout("Rail", SIZE_COMPACT, 200, 131, ANCHOR_EDGE, PROGRESS_RING, (0, 0, 0, 0), has_next_line=False, canvas=True),
    Layout("Rail", SIZE_MINIMAL, 91, 91, ANCHOR_EDGE, PROGRESS_RING, (0, 0, 0, 0), has_close=False, has_next_line=False, canvas=True),
    Layout("Dial", SIZE_FULL, 453, 148, ANCHOR_CORNER, PROGRESS_RING, (0, 0, 0, 0), canvas=True),
    Layout("Dial", SIZE_COMPACT, 248, 48, ANCHOR_CORNER, PROGRESS_RING, (0, 0, 0, 0), has_next_line=False, canvas=True),
    Layout("Dial", SIZE_MINIMAL, 163, 64, ANCHOR_CORNER, PROGRESS_RING, (0, 0, 0, 0), has_close=False, has_next_line=False,
           canvas=True),
    Layout("Slab", SIZE_FULL, 520, 173, ANCHOR_FLUSH, PROGRESS_LINE, (0, 0, 0, 0), canvas=True),
    Layout("Slab", SIZE_COMPACT, 295, 64, ANCHOR_FLUSH, PROGRESS_LINE, (0, 0, 0, 0), has_next_line=False, canvas=True),
    Layout("Slab", SIZE_MINIMAL, 147, 51, ANCHOR_FLUSH, PROGRESS_LINE, (0, 0, 0, 0), has_close=False, has_next_line=False,
           canvas=True),
    Layout("Stack", SIZE_FULL, 427, 183, ANCHOR_CORNER, PROGRESS_LINE, (0, 0, 0, 0), canvas=True),
    Layout("Stack", SIZE_COMPACT, 351, 56, ANCHOR_CORNER, PROGRESS_LINE, (0, 0, 0, 0), has_next_line=False, canvas=True),
    Layout("Stack", SIZE_MINIMAL, 139, 48, ANCHOR_CORNER, PROGRESS_LINE, (0, 0, 0, 0), has_close=False,
           has_next_line=False, canvas=True),
)
# a design that is drawn takes the place of its earlier skin files (which stay for the preview copies)
_BY_KEY = {(item.name, item.size): item for item in _ALL + _CANVAS}


def canvas_layouts() -> tuple:
    return _CANVAS


def is_canvas(layout) -> bool:
    return normalize_layout(layout) in CANVAS_LAYOUTS


def all_layouts() -> tuple:
    return _ALL


def normalize_layout(value) -> str:
    """A stored layout, or ``Card`` when the text is not one of them."""
    text = "".join(str(value or "").split()).lower()
    for stored, name in LAYOUT_NAMES:
        if text in (stored.lower(), "".join(name.split()).lower()):
            return stored
    return LAYOUT_CARD


def normalize_look(value) -> str:
    text = "".join(str(value or "").split()).lower()
    for stored, name in LOOK_NAMES:
        if text in (stored, "".join(name.split()).lower()):
            return stored
    return DEFAULT_LOOK


def normalize_bar_color(value) -> str:
    text = "".join(str(value or "").split()).lower()
    return BAR_LOOK if text == BAR_LOOK.lower() else BAR_TYPE


def bar_color_options() -> list:
    return [(name, stored) for stored, name in BAR_COLOR_NAMES]


def accent(code, bar_color, type_rgb, bare=False) -> str:
    """AARRGGBB of the progress: the segment type's colour (``type_rgb``, RRGGBB) or the look's accent."""
    rgb = str(type_rgb or "").strip()
    if normalize_bar_color(bar_color) == BAR_TYPE and len(rgb) == 6:
        return "FF" + rgb.upper()
    return look(code, bare).accent


def normalize_choice(value, choices, default) -> str:
    text = "".join(str(value or "").split()).lower()
    for choice in choices:
        if choice.lower() == text:
            return choice
    return default


def normalize_overlay(value) -> str:
    return normalize_choice(value, OVERLAYS, OVERLAY_AUTO)


def normalize_appear(value) -> str:
    return normalize_choice(value, APPEARS, APPEARS[0])


def normalize_leave(value) -> str:
    return normalize_choice(value, LEAVES, LEAVES[0])


def overlay_box(layout, position, kind):
    """The shade behind a layout: ``{"texture", "nine", "box": (left, top, width, height)}`` on the 720p
    canvas, or None. A layout across the screen has its own band and takes none. A shade follows
    the corner the dialog sits in: it runs out to the nearest edges of the screen."""
    kind = normalize_overlay(kind)
    if kind in (OVERLAY_NONE, OVERLAY_AUTO) or layout.anchor == ANCHOR_BAND:
        return None
    ox, oy = origin(layout, position)
    w, h, m = layout.width, layout.height, OVERLAY_MARGIN
    cx, cy = ox + w / 2.0, oy + h / 2.0
    left, right = cx < CANVAS_W / 2.0 - 2, cx > CANVAS_W / 2.0 + 2
    top, bottom = cy < CANVAS_H / 2.0 - 2, cy > CANVAS_H / 2.0 + 2

    def flush(extra=0):
        x0 = 0 if left else max(0, ox - m - (extra if right else 0))
        x1 = CANVAS_W if right else min(CANVAS_W, ox + w + m + (extra if left else 0))
        y0 = 0 if top else max(0, oy - m)
        y1 = CANVAS_H if bottom else min(CANVAS_H, oy + h + m)
        return x0, y0, x1 - x0, y1 - y0

    def found(texture, box, nine=False):
        return {"texture": texture, "nine": nine, "box": tuple(int(round(v)) for v in box)}

    if kind in ("Round", "RoundFade"):
        name = "ov_round.png" if kind == "Round" else "ov_round_fade.png"
        return found(name, (ox - m, oy - m, w + 2 * m, h + 2 * m), nine=True)
    if kind == "Square":
        return found("ov_square.png", flush())
    side = (left or right) and not (top or bottom)  # half way up an edge (Side rail)
    if (kind == "SquareFade" or side) and (left or right):
        x0, y0, width, height = flush(240)
        if side:
            y0, height = 0, CANVAS_H
        return found("ov_fade_l.png" if left else "ov_fade_r.png", (x0, y0, width, height))
    if kind in ("Band", "SquareFade"):
        if top:
            return found("sl_band_top.png", (0, 0, CANVAS_W, oy + h + 50))
        return found("sl_band.png", (0, oy - 50, CANVAS_W, CANVAS_H - (oy - 50)))
    # Corner glow
    name = ("t" if top else "b") + ("l" if left else "r" if right else "c")
    width = w + 2 * m + (420 if (left or right) else 600)
    height = h + 2 * m + 260
    x0 = 0 if left else (CANVAS_W - width) if right else (CANVAS_W - width) / 2.0
    y0 = 0 if top else CANVAS_H - height
    return found("ov_glow_%s.png" % name, (x0, y0, width, height))


def appear_value(layout, position, choice) -> str:
    """What the skin file reads for the way in: Slide becomes the side it comes from."""
    choice = normalize_appear(choice)
    if choice != "Slide":
        return choice
    ox, _oy = origin(layout, position)
    return "SlideLeft" if ox + layout.width / 2.0 < CANVAS_W / 2.0 - 2 else "SlideRight"


def pulses(countdown, enabled) -> bool:
    """True while ``mm:ss`` is within the last seconds and the pulse is switched on."""
    if not enabled:
        return False
    try:
        parts = [int(p) for p in str(countdown or "").strip().split(":")]
    except ValueError:
        return False
    seconds = 0
    for part in parts:
        seconds = seconds * 60 + part
    return bool(parts) and 0 < seconds <= PULSE_SECONDS


def is_bare(layout) -> bool:
    """True for a layout that draws straight on the video."""
    return normalize_layout(layout) in BARE_LAYOUTS


def layout_options() -> list:
    """``[(name, stored value)]`` in the order of the settings list."""
    return [(name, stored) for stored, name in LAYOUT_NAMES]


def look_options() -> list:
    return [(name, stored) for stored, name in LOOK_NAMES]


def is_card(layout) -> bool:
    return normalize_layout(layout) == LAYOUT_CARD


def size_for_mode(mode) -> str:
    """Full mode draws the full file, Compact Full the compact one, Minimal the smallest."""
    text = "".join(str(mode or "").split()).lower()
    return SIZE_COMPACT if text == "compactfull" else SIZE_MINIMAL if text == "minimal" else SIZE_FULL


def get(layout, size) -> Layout:
    """The file for a layout and size (``Card`` has none and raises ``KeyError``)."""
    return _BY_KEY[(normalize_layout(layout), size if size in SIZES else SIZE_FULL)]


# ------------------------------------------------------------------------------------ looks
@dataclass(frozen=True)
class Look:
    code: str
    text: str  # AARRGGBB of the main text
    text2: str  # the quieter lines
    button_text: str  # on a button without the focus
    focus_text: str  # on the button with the focus
    accent: str  # the progress
    track: str  # behind the progress
    shadow: str  # under text that sits straight on the video
    caps: bool
    tile_fill: str = "2E000000"  # what fills up a focused tile (Split): dark on a white tile, light on glass


_LOOKS = {
    "fgd": Look("fgd", "FFFFFFFF", "B8FFFFFF", "FFFFFFFF", "FF101216", "FFE8B04B", "33FFFFFF", "B0000000", False),
    "fgf": Look("fgf", "FFFFFFFF", "C8FFFFFF", "FFFFFFFF", "FF101216", "FFFFFFFF", "3DFFFFFF", "A0000000", False),
    "fgc": Look("fgc", "FFFFFFFF", "C8FFFFFF", "FFFFFFFF", "FF101216", "FFFFFFFF", "3DFFFFFF", "C0000000", False),
    "fgs": Look("fgs", "FFFFFFFF", "A3FFFFFF", "9EFFFFFF", "FFFFFFFF", "FFFFFFFF", "38FFFFFF", "B0000000", True, "3DFFFFFF"),
    "aeo": Look("aeo", "FFFFFFFF", "B3FFFFFF", "FFFFFFFF", "FF0B0B0B", "FFFFFFFF", "33FFFFFF", "B0000000", True),
    "agl": Look("agl", "FFFFFFFF", "C2FFFFFF", "FFFFFFFF", "FFFFFFFF", "FFFFFFFF", "42FFFFFF", "B0000000", False, "3DFFFFFF"),
    # code, text, text2, button text, focus text, accent, track, shadow, caps, tile fill
    "neon": Look("neon", "FFEAFFFF", "FF8CECF7", "FFFF8AEE", "FF04141A", "FFFF46E1", "3DFF46E1", "B0000000", True, "29000000"),
    "paper": Look("paper", "FF1C1A16", "B31C1A16", "FF1C1A16", "FFF4EFE6", "FFC8452E", "241C1A16", "01000000", False, "29FFFFFF"),
    "sunset": Look("sunset", "FFFFFFFF", "DBFFFFFF", "FFFFFFFF", "FF8A1C4D", "FFFFFFFF", "4DFFFFFF", "80000000", False, "33E8457A"),
    "ocean": Look("ocean", "FFFFFFFF", "DBFFFFFF", "FFFFFFFF", "FF123A8F", "FF9DFFF2", "47FFFFFF", "80000000", False, "332563EB"),
    "brutal": Look("brutal", "FF000000", "C7000000", "FF000000", "FFFFDE21", "FF000000", "33000000", "01000000", True, "40FFDE21"),
    "term": Look("term", "FFC8FFDD", "FF37FF8B", "FF37FF8B", "FF001A0A", "FF37FF8B", "3837FF8B", "B0000000", True, "33001A0A"),
    "line": Look("line", "FFFFFFFF", "D9FFFFFF", "FFFFFFFF", "FF000000", "FFFFFFFF", "4DFFFFFF", "D9000000", False, "29000000"),
    "luxe": Look("luxe", "FFF5EAD2", "FFC9A45C", "FFE9D5A7", "FF14110B", "FFC9A45C", "38C9A45C", "B0000000", False, "2914110B"),
    "pastel": Look("pastel", "FF2A2550", "B82A2550", "FF2A2550", "FFFFFFFF", "FFF27AA8", "212A2550", "01000000", False, "33FFFFFF"),
    "gloss": Look("gloss", "FFFFFFFF", "C7FFFFFF", "FFFFFFFF", "FFFFFFFF", "FF6DBCFF", "73000000", "99000000", False, "33FFFFFF"),
    "mono": Look("mono", "FFFFFFFF", "CCFFFFFF", "FFFFFFFF", "FF000000", "FFFFFFFF", "40FFFFFF", "B0000000", True, "29000000"),
    "vhs": Look("vhs", "FFFFFFFF", "FF3BFF6F", "FFFFFFFF", "FF0A0A3A", "FF3BFF6F", "4DFFFFFF", "C0000000", True, "290A0A3A"),
    # the twins for the layouts that sit on the video: the ink of the plate becomes its paper
    "paper_o": Look("paper_o", "FFF4EFE6", "C8F4EFE6", "FFF4EFE6", "FF1C1A16", "FFE8644C", "4DFFFFFF", "B0000000", False),
    "brutal_o": Look("brutal_o", "FFFFDE21", "FFFFFFFF", "FF000000", "FFFFDE21", "FFFFDE21", "4DFFFFFF", "C0000000", True),
    "pastel_o": Look("pastel_o", "FFECE8FF", "C8ECE8FF", "FFECE8FF", "FFFFFFFF", "FFF27AA8", "4DFFFFFF", "B0000000", False),
}


def variant(code, bare=False) -> str:
    """The code whose colours and buttons a layout uses: the look, or its twin on the video."""
    code = normalize_look(code)
    return code + OPEN if bare and code + OPEN in _LOOKS else code


def look(code, bare=False) -> Look:
    return _LOOKS[variant(code, bare)]


def texture(code, part, resolution="1080i") -> str:
    """The picture of a look: ``plate``, ``slab`` (the plate with hard corners) and ``tile`` (a focused
    tile) serve both skin folders; ``button`` and ``focus`` are cut per folder."""
    text = str(code or "")
    code = text if text in _LOOKS else normalize_look(code)
    if part in ("plate", "slab", "tile"):
        return "sl_%s_%s.png" % (normalize_look(code[:-len(OPEN)] if code.endswith(OPEN) else code), part)
    return "sl_%s_%s_%s.png" % (code, part, "720" if str(resolution).startswith("720") else "1080")


def thumb(layout, code) -> str:
    """The miniature of a layout in a look (tools/gen_preset_thumbs.py), for the preset wall."""
    return "pt_%s_%s.png" % (normalize_layout(layout), normalize_look(code))


def ring_frame(percent) -> str:
    """The ring picture for a percentage (0-100)."""
    try:
        value = max(0.0, min(100.0, float(percent)))
    except (TypeError, ValueError):
        value = 0.0
    return "sl_ring_%02d.png" % int(round(value * RING_FRAMES / 100.0))


def properties(code, resolution="1080i", bare=False) -> dict:
    """Skin properties of a look (the texts and the progress come from the dialog). ``bare`` is for a
    layout that sits on the video: a look with a light plate then gives its twin."""
    found = look(code, bare)
    on_picture = look(code, True)  # texts that lie on a picture inside a plate
    code = found.code
    return {
        "skl_pic_text": on_picture.text,
        "skl_pic_text2": on_picture.text2,
        "skl_plate": texture(code, "plate"),
        "skl_slab": texture(code, "slab"),
        "skl_tile": texture(code, "tile"),
        "skl_tile_fill": found.tile_fill,
        "skl_nested": "FF7FB4FF",
        "skl_button": texture(code, "button", resolution),
        "skl_focus": texture(code, "focus", resolution),
        "skl_text": found.text,
        "skl_text2": found.text2,
        "skl_button_text": found.button_text,
        "skl_focus_text": found.focus_text,
        "skl_accent": found.accent,
        "skl_track": found.track,
        "skl_shadow": found.shadow,
        "skl_focus_track": "33" + found.focus_text[2:],
    }


# ------------------------------------------------------------------------------- placement
def origin(layout: Layout, position) -> tuple:
    """Left and top of the layout on the 720p canvas for a stored corner (``BottomRight`` ...)."""
    text = str(position or "BottomRight")
    right = "Left" not in text
    bottom = "Top" not in text
    if layout.anchor == ANCHOR_BAND:
        return 0, (CANVAS_H - layout.height) if bottom else 0
    if layout.anchor == ANCHOR_EDGE:
        return (CANVAS_W - layout.width) if right else 0, (CANVAS_H - layout.height) // 2
    if layout.anchor == ANCHOR_CENTER:
        top = (CANVAS_H - MARGIN - layout.height) if bottom else MARGIN
        return (CANVAS_W - layout.width) // 2, top
    margin = 0 if layout.anchor == ANCHOR_FLUSH else MARGIN
    left = (CANVAS_W - margin - layout.width) if right else margin
    top = (CANVAS_H - margin - layout.height) if bottom else margin
    return left, top


def is_top(position) -> bool:
    return "Top" in str(position or "")


def fill_size(layout: Layout, percent) -> tuple:
    """``(left, top, width, height)`` of the fill for a percentage: a line grows to the right, a tile
    fills up from its bottom."""
    left, top, width, height = layout.track
    share = max(0.0, min(100.0, float(percent))) / 100.0
    if layout.progress == PROGRESS_TILE and layout.size == SIZE_FULL:
        filled = int(round(height * share))
        return left, top + height - filled, width, filled
    return left, top, int(round(width * share)), height


JUMP_MARK_W = 6  # Timeline: the mark where Skip lands when a segment lies inside this one


def timeline_parts(layout: Layout, start, end, position, jump=None) -> dict:
    """Where the playhead and the jump mark sit on the Timeline track, which spans the segment.

    ``jump`` is the time Skip lands on when it is inside the segment (the start of a nested
    segment), else None. Lefts are relative to the layout; ``jump_width`` 0 means "do not draw".
    """
    left, _top, width, _height = layout.track
    span = float(end) - float(start)
    out = {"playhead": left, "jump_left": left, "jump_width": 0}
    if span <= 0:
        return out

    def at(seconds):
        share = max(0.0, min(1.0, (float(seconds) - float(start)) / span))
        return left + int(round(share * width))

    out["playhead"] = at(position)
    try:
        inside = jump is not None and float(start) < float(jump) < float(end)
    except (TypeError, ValueError):
        inside = False
    if inside:
        out["jump_left"] = min(at(jump), left + width - JUMP_MARK_W)
        out["jump_width"] = JUMP_MARK_W
    return out


def clock(seconds) -> str:
    """``mm:ss`` (or ``h:mm:ss``) for a time in the video."""
    try:
        total = max(0, int(float(seconds)))
    except (TypeError, ValueError):
        total = 0
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return "%d:%02d:%02d" % (hours, minutes, secs) if hours else "%02d:%02d" % (minutes, secs)


def seconds_left(countdown) -> str:
    """The short form of ``mm:ss`` for a small ring: ``59`` under a minute, else ``1:05``."""
    text = str(countdown or "").strip()
    if not text or ":" not in text:
        return text
    parts = text.split(":")
    try:
        numbers = [int(p) for p in parts]
    except ValueError:
        return text
    if len(numbers) == 2 and numbers[0] == 0:
        return str(numbers[1])
    return "%d:%02d" % (numbers[-2] + 60 * (numbers[0] if len(numbers) == 3 else 0), numbers[-1])
