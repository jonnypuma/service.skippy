# -*- coding: utf-8 -*-
"""The drawn skip dialog: Skippy places every part itself.

The designs of the mockups are functions here that turn a look, the texts and the options into a
list of things to draw, in the mockups' own measures. Because nothing is fixed in a skin file, an
option can change the build: no Close button and Skip takes its room, no icons, hard or rounded
corners, a line or no bar, nine places on the screen, any accent colour.

This part needs no Kodi. ``skip_canvas_draw.py`` puts the list on a window (the real dialog and
the Studio's live preview use the same drawing).

Measures: a design works in the stylesheet pixels of the mockups, which are pixels of a
1920 x 1080 screen (the Stack card is 640 wide).
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

import skip_canvas_looks as looks

XML = "SkipCanvas.xml"
SCREEN_W, SCREEN_H = 1920.0, 1080.0

# --- ids of the skin file ---------------------------------------------------------------------
ID_ROOT = 3300
ID_PROBE = 3390
ID_ZOOM = 3391  # the group that holds the card and the buttons: Size on screen zooms it
ID_VIDEO = 3392  # a video window (Takeover + video): drawn while Window.Property(cv_video) is true
# Where it is, in pixels of a 1080 screen (16:9). The window file has it at this place: Kodi gives a
# video window to Python as no control, so it cannot be moved from here.
VIDEO_RECT = (1256.0, 56.0, 608.0, 342.0)
VIDEO_STAGE_XML = "SkipVideoStage.xml"  # the plain window under the popup (see next_episode_dialog)
PROBE_W = 520  # at 720p; the 1080i file has 780
ID_SKIP = 3210  # the two buttons keep the ids of the other skip dialog files
ID_CLOSE = 3220
ID_MORE = 3230  # a third button (Up Next: Play a later one); unseen until a design places it
BUTTON_IDS = {"skip": ID_SKIP, "close": ID_CLOSE, "more": ID_MORE}
# places that take the focus but draw nothing themselves (Up Next: the cards of the Queue)
HOT_IDS = {"q1": 3251, "q2": 3252, "q3": 3253}
SLOT_IDS = {
    "overlay9": 3301, "overlay": 3302, "shadow": 3303, "plate": 3304, "plate2": 3305, "box": 3306, "chip": 3307,
    "skip_off": 3308, "skip_on": 3309, "close_off": 3310, "close_on": 3311,
    "box2": 3314, "box3": 3315, "outline": 3316, "fill_v": 3317, "fill_h": 3318, "plate_h": 3319,
    "shadow_2": 3320, "shadow_3": 3321, "shadow_s": 3322, "shadow_s2": 3323, "shadow_s3": 3324,
    "fill_b": 3325, "fill_p": 3326,
    # pictures (the Up Next designs): behind everything with its shade, in a card with rounded corners, as a
    # small rounded tile, with hard corners, and a logo that keeps its shape
    "back": 3370, "back_shade": 3371, "pic": 3372, "pic_s": 3373, "pic_h": 3374, "logo": 3375,
    "pic2": 3376, "pic3": 3377, "more_off": 3378, "more_on": 3379, "pic2_h": 3380, "pic3_h": 3381,
    "pic_po": 3382, "pic_po_h": 3383,  # a poster (2:3), rounded and with hard corners
    # a fill that grows across a whole card, and a fanart that lies behind a card's words
    "fill_c": 3384, "pic_card": 3385, "pic_card_h": 3386,
    # a plate that is a pill: one slot per height, because the border of a slot is fixed
    "plate_c": 3312, "plate_m": 3313,
}
PILL_HEIGHTS = {"plate_c": 84, "plate_m": 72}
MOCK_OFFSET = 20000  # added to the ids of the slots for the copy in the Customize screens
# nine-slice borders of the slots, per skin folder: they hold the largest corner a look has
BORDERS = {
    "1080": dict(plate=45, box=30, chip=14, shadow=93, overlay=45, plate_c=42, plate_m=36, plate_h=8, shadow_s=56, fill_b="16,0,0,0", fill_p="30,0,0,0", fill_v="28,0,28,28",
                 fill_h="38,0,0,0", fill_c="45,45,0,45"),
    "720": dict(plate=30, box=20, chip=9, shadow=62, overlay=30, plate_c=28, plate_m=24, plate_h=5, shadow_s=37, fill_b="11,0,0,0", fill_p="20,0,0,0", fill_v="19,0,19,19",
                fill_h="25,0,0,0", fill_c="30,30,0,30"),
}
SHADOW_REACH = 44  # how far the shade under a plate reaches past it (stylesheet pixels)
SHADOW_DROP = 20
SMALL_REACH = 26  # the shade under a low card, a pill or a tile: a picture of its own, with a small border
SMALL_DROP = 10


def slot_property(slot, offset=0) -> str:
    """The window property that names the picture of a slot (a preview copy has its own)."""
    return "cv_%s%s" % (slot, "_p" if offset else "")


# --- options -----------------------------------------------------------------------------------
PLACES = ("TopLeft", "Top", "TopRight", "Left", "Center", "Right", "BottomLeft", "Bottom", "BottomRight")
PROGRESS = ("Line", "Off")
SIZES = ("Full", "Compact", "Minimal")
DESIGNS = (("Stack", "Stack card"), ("Slab", "Corner slab"), ("Dial", "Dial"), ("Band", "Cinema band"), ("Float", "Float"),
           ("Split", "Split"), ("Timeline", "Timeline"), ("Rail", "Side rail"))
# What a design fixes whatever the options say: hard corners, a place flush in the screen corner,
# no shade under it.
RULES = {
    "Slab": {"corners": "Hard", "flush": True, "shadow": False},
    # bare: nothing is boxed in, the texts lie on the video (over the design's own shade)
    # (the Dial is a rounded design in every look: pill buttons also in Aeon)
    "Dial": {"bare": True, "overlay": "RoundFade", "corners": "Rounded"},
    # across the whole picture, 64 in from each side and 44 from the edge it sits at
    "Band": {"bare": True, "overlay": "Band", "band": True},
    "Float": {"bare": True, "overlay": "None", "corners": "Rounded"},
    "Split": {"overlay": "Glow"},
    "Timeline": {"centre": True},  # in the middle of the bottom (or top) edge
    "Rail": {"corners": "Hard", "flush": True, "edge": True, "overlay": "Side", "shadow": False},
}


@dataclass
class Options:
    design: str = "Stack"
    size: str = "Full"
    look: str = "fgf"
    corners: str = "Skin"  # Skin, Hard, Rounded
    close: bool = True  # the Close button; without it Skip takes its room
    icons: bool = True  # the icons on Skip and Close
    kicker: bool = True  # the type and range line
    nested: bool = True  # the line that says where Skip lands
    progress: str = "Line"
    accent: tuple = None  # (r, g, b, a) in place of the look's accent
    place: str = "BottomRight"
    distance: float = 64.0  # from the screen edge, stylesheet pixels
    zoom: int = 100  # size on screen, percent
    shadow: bool = True
    text_shadow: str = "Mild"  # under a text that lies on the video: one of TEXT_SHADOWS
    text_outline: str = "Medium"  # a dark line around the letters of a text on the video: one of OUTLINES
    text_size: int = 100  # percent: one of TEXT_SIZES
    overlay_gradient: bool = False  # a Square or Rounded overlay fades out towards the picture
    appear: str = "Fade"  # one of APPEARS: how the dialog comes
    leave: str = "Fade"  # one of LEAVES: how it goes
    pulse: bool = False  # it beats in its last five seconds
    gradient: str = "Auto"  # one of GRADIENTS: which way it fades
    # the shade behind the dialog: "Auto" is the design's own (none for a card), or one for all designs.
    # There is only ever one: a choice here takes the place of the design's own.
    overlay: str = "Auto"
    # the Up Next designs (next_canvas.py)
    picture: str = "On"  # "On" (the episode picture), "Poster", "Both" (side by side), "Fanart" (behind the card), "Off"
    fallback: str = "Fanart"  # when the episode has no picture: "Fanart", "Poster" or "Nothing"
    fill_on: str = "Button"  # Progress Fill: where it shows ("Button", "Card", "Picture")
    caps: str = "Look"  # "Look" (as the look writes), "On", "Off"
    time: bool = True  # the time left on the Play button
    credits: bool = False  # a Watch credits button
    speed: int = 0  # milliseconds a dialog takes to come (0: what Appears has of its own)
    rise: float = 0.0  # a dialog at the bottom stands this much higher (Keep clear of subtitles)
    focus_style: str = "Look"  # the button in focus: "Look" (the look's own), "Accent" (in the accent colour), "Outline"
    plot: bool = True
    video: bool = False  # Takeover + video: what is playing, small, at the top right
    background: str = "None"  # the whole screen behind the dialog: "None" (the video), "Fanart", "Colour"
    art_edges: str = "Look"  # the corners of the pictures: "Look" (as the look has them), "Straight", "Rounded"
    bar_edges: str = "Straight"  # the ends of the progress line: "Straight" or "Rounded"


@dataclass
class Texts:
    kicker: str = "Intro"
    range: str = "0:46 – 2:14"
    ending: str = "Intro ending in"
    countdown: str = "0:42"
    nested: str = "Skip to next segment at"
    nested_time: str = "2:11"
    nested_short: str = "Next at"
    nested_long: str = "Next segment at"
    nested_line: str = ""  # the whole nested line as one text (the real dialog has it ready made)
    chip: str = "Recap"
    skip: str = "Skip intro"
    duration: str = "1:28"
    close: str = "Close"
    left: str = "left"  # under the time in a ring
    skip_word: str = "Skip"  # on a tile
    rest: str = "Episode"  # Timeline: what follows the segment Skip lands in
    t0: str = "0:46"  # Timeline: start of the segment, the playhead, the end of the line
    now: str = "1:32"
    t1: str = "3:02"
    next_word: str = "Next"
    ends_in: str = "ends in"
    seconds: str = "42"  # the short time in a small ring
    fanart: str = ""  # Background Fanart: the picture of what is playing
    percent: float = 52.0


@dataclass
class Drawing:
    width: float
    height: float
    left: float = 0.0
    top: float = 0.0
    ops: list = field(default_factory=list)
    corners: str = "Skin"  # the corner choice the pictures are taken for
    lift: float = 0.0  # a flush design that stands this far above (or below) the screen edge
    shade: float = 0.0  # how far the design's own shade reaches past it (or how high its band is)
    drop: float = 0.0  # a band design whose foot stands this far above the screen edge instead of 44
    # Size on screen: the parts are laid out at full size and the whole is zoomed around ``anchor``
    # (the point of the dialog nearest its place). ``left``, ``top``, ``width`` and ``height`` are what is seen.
    zoom: float = 100.0
    anchor: tuple = (0.0, 0.0)
    overlaid: bool = False  # a shade lies behind the dialog: its texts need no heavy shadow of their own

    def find(self, key):
        for op in self.ops:
            if op.get("key") == key:
                return op
        return None


TEXT_SHADOWS = ("Off", "Mild", "Medium", "Strong", "Heavy")
TEXT_SIZES = (85, 100, 115, 130)
OUTLINES = ("Off", "Light", "Medium", "Strong")
ZOOMS = (70, 85, 100)  # Size on screen: Small, Medium, Large (percent)
GRADIENTS = ("Auto", "Vertical", "Horizontal", "Radial")
APPEARS = ("Fade", "Rise", "Pop", "Slide")
LEAVES = ("Fade", "Drop", "Shrink")
APPEAR_MS = {"Fade": 200, "Rise": 260, "Pop": 240, "Slide": 260}
LEAVE_MS = {"Fade": 160, "Drop": 200, "Shrink": 180}
PULSE_SECONDS = 5
PROGRESS = ("Auto", "Line", "Circle", "Fill", "Off")  # Auto: the design's own
# designs whose own progress is a line: there Circle and Fill move it into the Skip button
LINE_DESIGNS = ("Stack", "Slab", "Band", "NCard", "NSlab", "NBand", "NQueue", "NTake")
_PERCENT = 0.0  # the progress of the drawing that is being built
_TEXT = 1.0  # the text size factor of the drawing that is being built
_BAR_ROUND = False  # Progress bar edges Rounded, for the drawing that is being built
BACKGROUNDS = ("None", "Fanart", "Colour")
ART_EDGES = ("Look", "Straight", "Rounded")
BAR_EDGES = ("Straight", "Rounded")
BACKGROUND_DIM = 0.55  # how dark the shade over a fanart background is


def text_size(value) -> int:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return 100
    return min(TEXT_SIZES, key=lambda size: abs(size - number))


def estimate(text, size, bold=False) -> float:
    """About how wide a text is at a size (stylesheet pixels): good enough to size a button."""
    text = str(text or "")
    wide = sum(1 for ch in text if ch.isupper() or ch.isdigit())  # capitals and figures are wider than small letters
    units = (len(text) - wide) * (0.50 if bold else 0.45) + wide * (0.68 if bold else 0.62)
    return units * size * _TEXT


def place_name(value) -> str:
    """A stored position: one of the nine places (the four corners of earlier versions are among them)."""
    text = "".join(str(value or "").split()).lower()
    for name in PLACES:
        if name.lower() == text:
            return name
    return "BottomRight"


def origin(width, height, place, distance, flush=False, lift=0.0) -> tuple:
    """Left and top (screen pixels) of a dialog of this size (screen pixels) at one of the nine places.
    ``flush`` puts it against the screen edges, ``lift`` this far from the top or bottom edge."""
    place = place_name(place)
    gap = 0.0 if flush else distance * looks.SCALE
    if flush and lift:
        left = 0.0 if "Left" in place else (SCREEN_W - width) if "Right" in place else (SCREEN_W - width) / 2.0
        top = lift if place.startswith("Top") else SCREEN_H - lift - height
        return left, top
    if "Left" in place:
        left = gap
    elif "Right" in place:
        left = SCREEN_W - gap - width
    else:
        left = (SCREEN_W - width) / 2.0
    if place.startswith("Top"):
        top = gap
    elif place.startswith("Bottom"):
        top = SCREEN_H - gap - height
    else:
        top = (SCREEN_H - height) / 2.0
    return left, top


# --- the designs -------------------------------------------------------------------------------
def _caps(text, look) -> str:
    return str(text or "").upper() if look["caps"] else str(text or "")


def _button(ops, which, x, y, w, h, look, label, icon, texts_key, options, time="", on_plate=True, ghost=False):
    """A button: its two plates, the button itself, then the icon, the label and the time on it.
    ``on_plate`` False gives the look's own button corners (a pill in the round looks); a ``ghost``
    has no plate until it has the focus."""
    ops.append({"t": "button", "which": which, "rect": (x, y, w, h), "pill": not on_plate, "ghost": ghost})
    cx = x + 24
    inside = options.progress if which == "skip" and options.design in LINE_DESIGNS else ""
    if inside == "Fill" and getattr(options, "fill_on", "Button") != "Button":
        inside = ""  # the fill shows on the card or on the picture instead
    if inside == "Fill":
        # the bar as a fill of the Skip button itself
        pill = not on_plate and look["rb"] > 100
        ops.append({"t": "fillslot", "slot": "fill_p" if pill else "fill_b", "rect": (x, y, w * _PERCENT / 100.0, h),
                    "ink": "skip", "share": 0.13, "key": "fill", "track": (x, y, w, h), "min": 30.0 if pill else 16.0,
                    "stop": 8.0})
    if inside == "Circle":
        # the bar as a small ring in front of the label, in the icon's place
        ops.append({"t": "img", "tex": "sl_ring_50.png", "rect": (cx - 2, y + (h - 30) / 2.0, 30, 30), "ink": which, "share": 0.18})
        ops.append({"t": "img", "tex": ring_frame(_PERCENT), "rect": (cx - 2, y + (h - 30) / 2.0, 30, 30), "ink_acc": which,
                    "key": "ring"})
        cx += 28 + 12
    elif options.icons and icon:
        ops.append({"t": "img", "tex": icon, "rect": (cx, y + (h - 24) / 2.0, 24, 24), "ink": which, "key": which + "_icon"})
        cx += 24 + 12
    width = w - (cx - x) - 6  # a label may run close to the button's end: the estimate of its width is rough
    if time:
        time_w = estimate(time, 24) + 16
        ops.append({"t": "text", "rect": (x + w - 24 - time_w, y, time_w, h), "text": time, "size": 24, "align": "r",
                    "ink": which, "share": 0.62, "key": which + "_time"})
        width -= time_w + 18
    if label:
        ops.append({"t": "text", "rect": (cx, y, max(10, width), h), "text": label, "size": 24, "bold": True,
                    "ink": which, "key": texts_key})


def stack_full(look, texts, options) -> Drawing:
    """A · Stack card, Full: type and range, the time left, the nested line in its own box, the bar,
    Skip and Close."""
    ops = []
    width, tp, pad, gap, row = 640.0, look["tp"], look["pad"], look["gap"], 14.0
    acc = options.accent or look["acc"]
    y = tp
    if options.kicker:
        x = tp
        ops.append({"t": "img", "tex": "cv_dot.png", "rect": (x, y + 5, 10, 10), "color": acc})
        x += 19
        ops.append({"t": "text", "rect": (x, y, 300, 20), "text": texts.kicker.upper(), "size": 16, "bold": True,
                    "color": look["ink2"], "key": "kicker"})
        ops.append({"t": "text", "rect": (width - tp - 260, y, 260, 20), "text": texts.range, "size": 16, "align": "r",
                    "color": look["ink3"], "key": "range"})
        y += 20 + row
    ops.append({"t": "text", "rect": (tp, y, width - 2 * tp, 36), "size": 32, "color": look["ink"], "key": "heading",
                "bold": True,
                "text": "%s %s" % (_caps(texts.ending, look), texts.countdown)})
    y += 36 + row
    if options.nested and (texts.nested_time or texts.nested_line):
        box_h = 54.0
        ops.append({"t": "slot", "slot": "box", "rect": (tp, y, width - 2 * tp, box_h)})
        ops.append({"t": "img", "tex": "cv_ic_jump.png", "rect": (tp + 16, y + 17, 20, 20), "color": acc})
        chip_w = 0.0
        if texts.chip:
            chip = texts.chip.upper()
            chip_w = estimate(chip, 14, True) + 24
            cx = width - tp - 16 - chip_w
            ops.append({"t": "slot", "slot": "chip", "rect": (cx, y + 14, chip_w, 26)})
            ops.append({"t": "text", "rect": (cx, y + 14, chip_w, 26), "text": chip, "size": 14, "bold": True, "align": "c",
                        "color": look.get("chip_ink") or look["ink"], "key": "chip"})
        ops.append({"t": "text", "rect": (tp + 46, y, width - 2 * tp - 46 - 16 - chip_w - 8, box_h), "size": 20,
                    "color": look["ink2"], "key": "nested",
                    "text": _caps(texts.nested_line, look) if texts.nested_line
                    else "%s [B]%s[/B]" % (_caps(texts.nested, look), texts.nested_time)})
        y += box_h + row
    if options.progress == "Line":
        track = (tp, y, width - 2 * tp, 6.0)
        ops.append({"t": "rect", "rect": track, "color": look["track"]})
        ops.append({"t": "rect", "rect": (track[0], track[1], track[2] * texts.percent / 100.0, track[3]), "color": acc,
                    "key": "fill", "track": track})
        y += 6
    y += max(pad, tp - 11)
    # the buttons: Skip takes what Close leaves, and all of it without Close
    bh = 60.0
    close_w = 0.0
    if options.close:
        close_w = 48 + estimate(_caps(texts.close, look), 24, True) + (36 if options.icons else 0)
    skip_w = width - 2 * pad - (close_w + gap if options.close else 0)
    _button(ops, "skip", pad, y, skip_w, bh, look, _caps(texts.skip, look), "cv_ic_skip.png", "skip_label", options,
            time=texts.duration)
    if options.close:
        _button(ops, "close", width - pad - close_w, y, close_w, bh, look, _caps(texts.close, look), "cv_ic_close.png",
                "close_label", options)
    y += bh + pad
    ops.insert(0, {"t": "slot", "slot": "plate", "rect": (0, 0, width, y)})
    return Drawing(width, y, ops=ops)


def stack_compact(look, texts, options) -> Drawing:
    """A · Stack card, Compact: Skip, the time left over a short bar, and a small Close."""
    ops = []
    pad, bh = look["pad"], 60.0
    acc = options.accent or look["acc"]
    x = pad
    label = _caps(texts.skip, look)
    skip_w = 48 + estimate(label, 24, True) + (36 if options.icons else 0)
    _button(ops, "skip", x, pad, skip_w, bh, look, label, "cv_ic_skip.png", "skip_label", options, on_plate=False)
    x += skip_w + 16
    count_w = estimate(texts.countdown, 26, True) + 10
    ops.append({"t": "text", "rect": (x + 4, pad + 2, count_w, 30), "text": texts.countdown, "size": 26, "bold": True,
                "color": look["ink"], "key": "countdown"})
    if options.nested and texts.nested_time:
        ops.append({"t": "text", "rect": (x + 4 + count_w, pad + 8, 206 - count_w, 22), "size": 17, "color": look["ink2"],
                    "text": _caps("%s %s" % (texts.nested_short, texts.nested_time), look), "key": "nested"})
    if options.progress == "Line":
        track = (x + 4, pad + 44, 206.0, 6.0)
        ops.append({"t": "rect", "rect": track, "color": look["track"]})
        ops.append({"t": "rect", "rect": (track[0], track[1], track[2] * texts.percent / 100.0, track[3]), "color": acc,
                    "key": "fill", "track": track})
    x += 210 + 16
    if options.close:
        _button(ops, "close", x, pad, 60, bh, look, "", "cv_ic_close.png", "close_label", options, on_plate=False,
                ghost=True)
        # a square button: the cross sits in its middle
        for op in ops:
            if op.get("key") == "close_icon":
                op["rect"] = (x + 18, pad + 18, 24, 24)
        x += 60
    width, height = x + pad + (4 if options.close else 0), bh + 2 * pad
    ops.insert(0, {"t": "slot", "slot": "plate_c" if look["rb"] > 100 else "plate", "rect": (0, 0, width, height)})
    return Drawing(width, height, ops=ops)


def stack_minimal(look, texts, options) -> Drawing:
    """A · Stack card, Minimal: the Skip button alone, the bar as a line along its foot."""
    ops = []
    pad, bh = min(look["pad"], 6), 60.0
    label = _caps(texts.skip, look)
    skip_w = 48 + estimate(label, 24, True) + (36 if options.icons else 0)
    _button(ops, "skip", pad, pad, skip_w, bh, look, label, "cv_ic_skip.png", "skip_label", options, on_plate=False)
    if options.progress == "Line":
        inset = 24.0 if look["rb"] > 100 else max(4.0, look["ri"] * 0.6)
        track = (pad + inset, pad + bh - 5, skip_w - 2 * inset, 5.0)
        ops.append({"t": "rect", "rect": (track[0], track[1], track[2] * texts.percent / 100.0, track[3]),
                    "color": look["foc_acc"], "key": "fill", "track": track})
    width, height = skip_w + 2 * pad, bh + 2 * pad
    ops.insert(0, {"t": "slot", "slot": "plate_m" if look["rb"] > 100 else "plate", "rect": (0, 0, width, height)})
    return Drawing(width, height, ops=ops)


def _kicker(ops, look, texts, x, y, width, acc, dot=True):
    """The type at the left (with the accent dot in front of it), the range at the right."""
    if dot:
        ops.append({"t": "img", "tex": "cv_dot.png", "rect": (x, y + 5, 10, 10), "color": acc})
    ops.append({"t": "text", "rect": (x + (19 if dot else 0), y, 300, 20), "text": texts.kicker.upper(), "size": 16,
                "bold": True, "color": look["ink2"], "key": "kicker"})
    ops.append({"t": "text", "rect": (x + width - 260, y, 260, 20), "text": texts.range, "size": 16, "align": "r",
                "color": look["ink3"], "key": "range"})


def _nested_text(look, texts) -> str:
    if texts.nested_line:
        return _caps(texts.nested_line, look)
    return "%s [B]%s[/B]" % (_caps(texts.nested, look), texts.nested_time)


def _line(ops, track, look, acc, percent):
    x, y, w, h = track
    if _BAR_ROUND and w > 2 * h:
        # Progress bar edges Rounded: half discs at both ends of the track and of the fill, the end of the fill
        # moving with it (a whole disc would lie twice over the line where they meet: a darker ring)
        r = h / 2.0
        inner = (x + r, y, w - 2 * r, h)
        ops.append({"t": "img", "tex": "cv_cap_l.png", "rect": (x, y, r, h), "color": look["track"]})
        ops.append({"t": "rect", "rect": inner, "color": look["track"]})
        ops.append({"t": "img", "tex": "cv_cap_r.png", "rect": (x + w - r, y, r, h), "color": look["track"]})
        ops.append({"t": "img", "tex": "cv_cap_l.png", "rect": (x, y, r, h), "color": acc})
        reach = inner[2] * percent / 100.0
        ops.append({"t": "rect", "rect": (inner[0], y, reach, h), "color": acc, "key": "fill", "track": inner})
        ops.append({"t": "img", "tex": "cv_cap_r.png", "rect": (inner[0] + reach, y, r, h), "color": acc, "key": "fillcap",
                    "follow": {"x0": inner[0] + r / 2.0, "span": inner[2], "mode": "centre"}})
        return
    ops.append({"t": "rect", "rect": track, "color": look["track"]})
    ops.append({"t": "rect", "rect": (track[0], track[1], track[2] * percent / 100.0, track[3]), "color": acc,
                "key": "fill", "track": track})


def background_ops(options, look, texts, found_ops=()) -> list:
    """Background: what lies on the whole screen behind the dialog. Fanart is the picture of what is playing
    (Up Next: of the next episode) under a dark shade; Colour is the look's own dark, opaque. A design that
    has a picture of its own behind everything (Takeover) keeps it."""
    kind = getattr(options, "background", "None")
    if kind not in ("Fanart", "Colour") or any(op.get("t") == "pic" and op.get("shape") == "back" for op in found_ops):
        return []
    full = (0.0, 0.0, SCREEN_W, SCREEN_H)
    src = getattr(texts, "fanart", "") or ""
    if kind == "Fanart" and src:
        return [{"t": "pic", "shape": "back", "rect": full, "abs": True, "src": src, "own_shade": True},
                {"t": "slot", "slot": "back_shade", "tex": "sl_white.png", "rect": full, "abs": True,
                 "color": (0, 0, 0, int(round(255 * BACKGROUND_DIM)))}]
    plate = tuple(look.get("plate") or (14, 17, 22, 255))[:3]
    dark = tuple(int(round(channel * 0.55)) for channel in plate)
    return [{"t": "slot", "slot": "back_shade", "tex": "sl_white.png", "rect": full, "abs": True, "color": dark + (255,)}]


def slab_full(look, texts, options) -> Drawing:
    """B · Corner slab, Full: a square slab out of the screen corner, the bar along its top edge, the
    nested line under a rule, the buttons edge to edge."""
    ops = []
    width, px, bh = 780.0, 32.0, 68.0
    acc = options.accent or look["acc"]
    y = 0.0
    if options.progress == "Line":
        _line(ops, (0.0, 0.0, width, 6.0), look, acc, texts.percent)
    y = 6.0 + 28.0
    if options.kicker:
        _kicker(ops, look, texts, px, y, width - 2 * px, acc, dot=False)
        y += 20 + 14
    ops.append({"t": "text", "rect": (px, y, width - 2 * px, 45), "size": 40, "color": look["ink"], "key": "heading",
                "bold": True, "text": "%s %s" % (_caps(texts.ending, look), texts.countdown)})
    y += 45 + 14
    if options.nested and (texts.nested_time or texts.nested_line):
        ops.append({"t": "rect", "rect": (px, y, width - 2 * px, 1), "color": look["track"]})
        y += 1 + 14
        ops.append({"t": "img", "tex": "cv_ic_jump.png", "rect": (px, y + 2, 20, 20), "color": acc})
        chip_w = 0.0
        if texts.chip:
            chip = texts.chip.upper()
            chip_w = estimate(chip, 14, True) + 24
            ops.append({"t": "slot", "slot": "chip", "rect": (width - px - chip_w, y, chip_w, 24)})
            ops.append({"t": "text", "rect": (width - px - chip_w, y, chip_w, 24), "text": chip, "size": 14, "bold": True,
                        "align": "c", "color": look.get("chip_ink") or look["ink"], "key": "chip"})
        ops.append({"t": "text", "rect": (px + 30, y, width - 2 * px - 30 - chip_w - 8, 24), "size": 20,
                    "color": look["ink2"], "key": "nested", "text": _nested_text(look, texts)})
        y += 24
    y += 26
    close_w = 0.0
    if options.close:
        close_w = 48 + estimate(_caps(texts.close, look), 24, True) + (36 if options.icons else 0)
    _button(ops, "skip", 0, y, width - close_w, bh, look, _caps(texts.skip, look), "cv_ic_skip.png", "skip_label", options,
            time=texts.duration)
    if options.close:
        _button(ops, "close", width - close_w, y, close_w, bh, look, _caps(texts.close, look), "cv_ic_close.png",
                "close_label", options)
    y += bh
    ops.insert(0, {"t": "slot", "slot": "plate", "rect": (0, 0, width, y)})
    return Drawing(width, y, ops=ops)


def slab_compact(look, texts, options) -> Drawing:
    """B · Corner slab, Compact: the ending line over the time left, Skip and a square Close, 96 high."""
    ops = []
    height = 96.0
    acc = options.accent or look["acc"]
    ending = _caps(texts.ending, look)
    text_w = max(estimate(ending, 17), estimate(texts.countdown, 26, True)) + 56
    ops.append({"t": "text", "rect": (28, 22, text_w - 40, 22), "text": ending, "size": 17, "color": look["ink2"]})
    ops.append({"t": "text", "rect": (28, 46, text_w - 40, 30), "text": texts.countdown, "size": 26, "bold": True,
                "color": look["ink"], "key": "countdown"})
    label = _caps(texts.skip, look)
    skip_w = 48 + estimate(label, 24, True) + (36 if options.icons else 0)
    x = text_w
    _button(ops, "skip", x, 0, skip_w, height, look, label, "cv_ic_skip.png", "skip_label", options)
    x += skip_w
    if options.close:
        _button(ops, "close", x, 0, 60, height, look, "", "cv_ic_close.png", "close_label", options)
        for op in ops:
            if op.get("key") == "close_icon":
                op["rect"] = (x + 18, (height - 24) / 2.0, 24, 24)
        x += 60
    if options.progress == "Line":
        _line(ops, (0.0, 0.0, x, 6.0), look, acc, texts.percent)
    ops.insert(0, {"t": "slot", "slot": "plate", "rect": (0, 0, x, height)})
    return Drawing(x, height, ops=ops)


def slab_minimal(look, texts, options) -> Drawing:
    """B · Corner slab, Minimal: the Skip button alone on the screen edge, the bar along its top."""
    ops = []
    height = 76.0
    acc = options.accent or look["acc"]
    label = _caps(texts.skip, look)
    width = 60 + estimate(label, 24, True) + (36 if options.icons else 0)
    _button(ops, "skip", 0, 0, width, height, look, label, "cv_ic_skip.png", "skip_label", options)
    for op in ops:  # the padding of this button is 30, not 24
        if op.get("ink") == "skip":
            x, y, w, h = op["rect"]
            op["rect"] = (x + 6, y, w, h)
    if options.progress == "Line":
        _line(ops, (0.0, 0.0, width, 6.0), look, acc, texts.percent)
    ops.insert(0, {"t": "slot", "slot": "plate", "rect": (0, 0, width, height)})
    return Drawing(width, height, ops=ops, lift=120.0)


def _ring(ops, look, x, y, size, percent, acc, track=None):
    """A ring that fills clockwise from the top: its track, then the part that is done."""
    ops.append({"t": "img", "tex": "sl_ring_50.png", "rect": (x, y, size, size), "color": track or look["track"]})
    ops.append({"t": "img", "tex": ring_frame(percent), "rect": (x, y, size, size), "color": acc, "key": "ring"})


def ring_frame(percent) -> str:
    """The ring picture for a percentage: one of 51 frames."""
    try:
        value = max(0.0, min(100.0, float(percent)))
    except (TypeError, ValueError):
        value = 0.0
    return "sl_ring_%02d.png" % int(round(value / 2.0))


def dial_full(look, texts, options) -> Drawing:
    """C · Dial, Full: the time left as a ring, the texts beside it, the buttons under both. Nothing
    is boxed in: it sits on a soft rounded shade."""
    ops = []
    width, ring, gap = 680.0, 140.0, 26.0
    acc = options.accent or look["acc"]
    if options.progress != "Off":
        _ring(ops, look, 0, 0, ring, texts.percent, acc)
    ops.append({"t": "text", "rect": (0, 38, ring, 44), "text": texts.countdown, "size": 38, "bold": True, "align": "c",
                "color": look["ink"], "key": "countdown"})
    ops.append({"t": "text", "rect": (0, 86, ring, 18), "text": texts.left.upper(), "size": 14, "bold": True, "align": "c",
                "color": looks.with_alpha(look["ink"], 0.65)})
    x = ring + gap
    rows = []
    if options.kicker:
        rows.append(("kicker", 20))
    rows.append(("heading", 36))
    if options.nested and (texts.nested_time or texts.nested_line):
        rows.append(("nested", 24))
    total = sum(h for _name, h in rows) + 10 * (len(rows) - 1)
    y = (ring - total) / 2.0
    for name, height in rows:
        if name == "kicker":
            ops.append({"t": "text", "rect": (x, y, width - x, height), "size": 16, "bold": True, "color": look["ink2"],
                        "text": "%s · %s" % (texts.kicker.upper(), texts.range), "key": "kicker", "shadow": True})
        elif name == "heading":
            ops.append({"t": "text", "rect": (x, y, width - x, height), "size": 32, "bold": True, "color": look["ink"],
                        "text": _caps(texts.ending, look), "shadow": True})
        else:
            ops.append({"t": "img", "tex": "cv_ic_jump.png", "rect": (x, y + 2, 20, 20), "color": acc})
            ops.append({"t": "text", "rect": (x + 30, y, width - x - 30, height), "size": 20, "color": look["ink2"],
                        "text": _nested_text(look, texts), "key": "nested", "shadow": True})
        y += height + 10
    y = ring + 22
    bh = 60.0
    close_w = 0.0
    if options.close:
        close_w = 48 + estimate(_caps(texts.close, look), 24, True) + (36 if options.icons else 0)
    skip_w = width - (close_w + look["gap"] if options.close else 0)
    _button(ops, "skip", 0, y, skip_w, bh, look, _caps(texts.skip, look), "cv_ic_skip.png", "skip_label", options,
            time=texts.duration, on_plate=False)
    if options.close:
        _button(ops, "close", width - close_w, y, close_w, bh, look, _caps(texts.close, look), "cv_ic_close.png",
                "close_label", options, on_plate=False)
    return Drawing(width, y + bh, ops=ops, shade=30.0)


def dial_compact(look, texts, options) -> Drawing:
    """C · Dial, Compact: a small ring with the seconds, Skip and a small Close."""
    ops = []
    ring, bh = 72.0, 60.0
    acc = options.accent or look["acc"]
    if options.progress != "Off":
        _ring(ops, look, 0, 0, ring, texts.percent, acc)
    seconds = texts.seconds or texts.countdown
    ops.append({"t": "text", "rect": (0, 0, ring, ring), "text": seconds, "size": 22 if len(seconds) < 3 else 18, "bold": True,
                "align": "c", "color": look["ink"], "key": "seconds"})
    x = ring + 16
    label = _caps(texts.skip, look)
    skip_w = 48 + estimate(label, 24, True) + (36 if options.icons else 0)
    _button(ops, "skip", x, (ring - bh) / 2.0, skip_w, bh, look, label, "cv_ic_skip.png", "skip_label", options, on_plate=False)
    x += skip_w
    if options.close:
        x += 16
        _button(ops, "close", x, (ring - bh) / 2.0, 60, bh, look, "", "cv_ic_close.png", "close_label", options,
                on_plate=False, ghost=True)
        for op in ops:
            if op.get("key") == "close_icon":
                op["rect"] = (x + 18, (ring - 24) / 2.0, 24, 24)
        x += 60
    return Drawing(x, ring, ops=ops, shade=22.0)


def dial_minimal(look, texts, options) -> Drawing:
    """C · Dial, Minimal: the label and a round Skip button with the ring around it."""
    ops = []
    size = 96.0
    acc = options.accent or look["acc"]
    label = _caps(texts.skip, look)
    label_w = estimate(label, 24, True) + 8
    ops.append({"t": "text", "rect": (0, 0, label_w, size), "text": label, "size": 24, "bold": True, "color": look["ink"],
                "shadow": True})
    x = label_w + 16
    if options.progress != "Off":
        _ring(ops, look, x, 0, size, texts.percent, acc)
    # the round button: the focus colour as a disc, the Skip icon on it
    ops.append({"t": "button", "which": "skip", "rect": (x + 11, 11, size - 22, size - 22), "pill": True, "ghost": True,
                "bare": True})
    ops.append({"t": "img", "tex": "cv_dot.png", "rect": (x + 11, 11, size - 22, size - 22), "color": look["foc"],
                "key": "skip_disc"})
    ops.append({"t": "img", "tex": "cv_ic_skip.png", "rect": (x + 31, 31, 34, 34), "ink": "skip", "key": "skip_icon"})
    return Drawing(x + size, size, ops=ops, shade=18.0)


def _auto_button_width(look, texts, options, label, time=""):
    return 48 + estimate(label, 24, True) + (36 if options.icons else 0) + ((estimate(time, 24) + 60) if time else 0)


def band_full(look, texts, options) -> Drawing:
    """D · Cinema band, Full: across the whole picture. Type, the time left and the nested line at
    the left, Skip and Close at the right, one long bar under both."""
    ops = []
    width = SCREEN_W - 128.0
    acc = options.accent or look["acc"]
    rows = []
    if options.kicker:
        rows.append(("kicker", 20))
    rows.append(("heading", 45))
    if options.nested and (texts.nested_time or texts.nested_line):
        rows.append(("nested", 26))
    left_h = sum(h for _n, h in rows) + 10 * (len(rows) - 1)
    bh = 60.0
    body = max(left_h, bh)
    y = body - left_h
    for name, height in rows:
        if name == "kicker":
            ops.append({"t": "img", "tex": "cv_dot.png", "rect": (0, y + 5, 10, 10), "color": acc})
            kicker = texts.kicker.upper()
            ops.append({"t": "text", "rect": (19, y, 400, height), "size": 16, "bold": True, "color": look["ink2"],
                        "text": kicker, "key": "kicker", "shadow": True})
            ops.append({"t": "text", "rect": (19 + estimate(kicker, 16, True) + 12, y, 300, height), "size": 16,
                        "color": looks.with_alpha(look["ink2"], 0.7), "text": texts.range, "key": "range", "shadow": True})
        elif name == "heading":
            ops.append({"t": "text", "rect": (0, y, 1000, height), "size": 40, "bold": True, "color": look["ink"],
                        "text": "%s %s" % (_caps(texts.ending, look), texts.countdown), "key": "heading", "shadow": True})
        else:
            ops.append({"t": "img", "tex": "cv_ic_jump.png", "rect": (0, y + 3, 20, 20), "color": acc})
            nested = _nested_text(look, texts)
            ops.append({"t": "text", "rect": (30, y, 700, height), "size": 20, "color": look["ink2"], "text": nested,
                        "key": "nested", "shadow": True})
            if texts.chip:
                chip = texts.chip.upper()
                chip_w = estimate(chip, 14, True) + 24
                cx = 30 + estimate(nested.replace("[B]", "").replace("[/B]", ""), 20) + 14
                ops.append({"t": "slot", "slot": "chip", "rect": (cx, y, chip_w, 26)})
                ops.append({"t": "text", "rect": (cx, y, chip_w, 26), "text": chip, "size": 14, "bold": True, "align": "c",
                            "color": look.get("chip_ink") or look["ink"], "key": "chip"})
        y += height + 10
    by = body - bh
    close_w = _auto_button_width(look, texts, options, _caps(texts.close, look)) if options.close else 0.0
    skip_label = _caps(texts.skip, look)
    skip_w = _auto_button_width(look, texts, options, skip_label, texts.duration)
    skip_x = width - skip_w - (close_w + look["gap"] if options.close else 0)
    _button(ops, "skip", skip_x, by, skip_w, bh, look, skip_label, "cv_ic_skip.png", "skip_label", options,
            time=texts.duration, on_plate=False)
    if options.close:
        _button(ops, "close", width - close_w, by, close_w, bh, look, _caps(texts.close, look), "cv_ic_close.png",
                "close_label", options, on_plate=False)
    height = body
    if options.progress != "Off":
        _line(ops, (0.0, body + 22, width, 5.0), look, acc, texts.percent)
        height = body + 22 + 5
    return Drawing(width, height, ops=ops, shade=380.0)


def band_compact(look, texts, options) -> Drawing:
    """D · Cinema band, Compact: one line of text at the left, Skip and a small Close at the right."""
    ops = []
    width, bh = SCREEN_W - 128.0, 60.0
    acc = options.accent or look["acc"]
    heading = "%s %s" % (_caps(texts.ending, look), texts.countdown)
    ops.append({"t": "text", "rect": (0, 10, 900, 40), "size": 32, "bold": True, "color": look["ink"], "text": heading,
                "key": "heading", "shadow": True})
    if options.nested and texts.nested_time:
        ops.append({"t": "text", "rect": (estimate(heading, 32, True) * 0.9 + 18, 16, 600, 30), "size": 20, "color": look["ink2"],
                    "text": _caps("%s %s" % (texts.nested_long, texts.nested_time), look), "key": "nested", "shadow": True})
    label = _caps(texts.skip, look)
    skip_w = _auto_button_width(look, texts, options, label)
    x = width - skip_w - (60 + look["gap"] if options.close else 0)
    _button(ops, "skip", x, 0, skip_w, bh, look, label, "cv_ic_skip.png", "skip_label", options, on_plate=False)
    if options.close:
        _button(ops, "close", width - 60, 0, 60, bh, look, "", "cv_ic_close.png", "close_label", options, on_plate=False)
        for op in ops:
            if op.get("key") == "close_icon":
                op["rect"] = (width - 60 + 18, 18, 24, 24)
    height = bh
    if options.progress != "Off":
        _line(ops, (0.0, bh + 18, width, 5.0), look, acc, texts.percent)
        height = bh + 18 + 5
    return Drawing(width, height, ops=ops, shade=240.0)


def band_minimal(look, texts, options) -> Drawing:
    """D · Cinema band, Minimal: Skip alone at the right, the bar along the very edge of the screen."""
    ops = []
    acc = options.accent or look["acc"]
    label = _caps(texts.skip, look)
    skip_w = _auto_button_width(look, texts, options, label)
    width = SCREEN_W - 128.0
    _button(ops, "skip", width - skip_w, 0, skip_w, 60.0, look, label, "cv_ic_skip.png", "skip_label", options, on_plate=False)
    if options.progress != "Off":
        # the bar runs along the screen edge, the whole width: 34 under the button and 64 past each end
        track = (-64.0, 60.0 + 34 - 6, SCREEN_W, 6.0)
        ops.append({"t": "rect", "rect": track, "color": looks.white(.2)})
        ops.append({"t": "rect", "rect": (track[0], track[1], track[2] * texts.percent / 100.0, 6.0), "color": acc,
                    "key": "fill", "track": track})
    return Drawing(width, 60.0, ops=ops, shade=170.0, drop=34.0)


def _ring_button(ops, which, x, y, w, h, look, label, options, percent):
    """Float: a pill with a small ring in front of its label (the bar of this design)."""
    ops.append({"t": "button", "which": which, "rect": (x, y, w, h), "pill": True})
    cx = x + 20
    if options.progress != "Off":
        ops.append({"t": "img", "tex": "sl_ring_50.png", "rect": (cx, y + (h - 36) / 2.0, 36, 36), "ink": which, "share": 0.18})
        ops.append({"t": "img", "tex": ring_frame(percent), "rect": (cx, y + (h - 36) / 2.0, 36, 36), "ink_acc": which,
                    "key": "ring"})
        cx += 36 + 12
    else:
        cx = x + 24
    ops.append({"t": "text", "rect": (cx, y, w - (cx - x) - 6, h), "text": label, "size": 24, "bold": True, "ink": which,
                "key": "skip_label"})


def _ring_button_width(label, options):
    return (20 + 36 + 12 if options.progress != "Off" else 24) + estimate(label, 24, True) + 26


def float_full(look, texts, options) -> Drawing:
    """E · Float, Full: no box and no shade. Light type right-aligned on the video, a dark Close and
    Skip with its ring."""
    ops = []
    # as wide as its headline needs (capitals are wide), 760 at least
    width = max(760.0, estimate("%s %s" % (_caps(texts.ending, look), texts.countdown), 54, True) * 1.06)
    acc = options.accent or look["acc"]
    y = 0.0
    if options.kicker:
        ops.append({"t": "text", "rect": (0, y, width, 20), "size": 16, "bold": True, "align": "r", "color": look["ink2"],
                    "text": "%s · %s" % (texts.kicker.upper(), texts.range), "key": "kicker", "shadow": True})
        y += 20 + 12
    # The line is right-aligned, so the time gets a place of its own, as wide as its widest figures:
    # the words before it stand still while the seconds change.
    slot = estimate("0" * len(texts.countdown or "0:00"), 54, True) * 1.04
    ops.append({"t": "text", "rect": (0, y, width - slot - 14, 62), "size": 54, "align": "r", "color": look["ink"],
                "key": "lead", "text": _caps(texts.ending, look), "shadow": True})
    ops.append({"t": "text", "rect": (width - slot, y, slot + 20, 62), "size": 54, "bold": True, "color": look["ink"],
                "key": "countdown", "text": texts.countdown, "shadow": True})
    y += 62 + 12
    if options.nested and (texts.nested_time or texts.nested_line):
        nested = _nested_text(look, texts)
        text_w = estimate(nested.replace("[B]", "").replace("[/B]", ""), 20) + 6
        ops.append({"t": "img", "tex": "cv_ic_jump.png", "rect": (width - text_w - 30, y + 2, 20, 20), "color": acc})
        ops.append({"t": "text", "rect": (0, y, width, 24), "size": 20, "align": "r", "color": look["ink2"], "text": nested,
                    "key": "nested", "shadow": True})
        y += 24 + 12
    y += 10
    label = _caps(texts.skip, look)
    skip_w = _ring_button_width(label, options)
    _ring_button(ops, "skip", width - skip_w, y, skip_w, 60.0, look, label, options, texts.percent)
    if options.close:
        close_label = _caps(texts.close, look)
        close_w = 48 + estimate(close_label, 24, True)
        cx = width - skip_w - look["gap"] - close_w
        ops.append({"t": "button", "which": "close", "rect": (cx, y, close_w, 60.0), "pill": True, "off": "ghost"})
        ops.append({"t": "text", "rect": (cx, y, close_w, 60.0), "text": close_label, "size": 24, "bold": True, "align": "c",
                    "ink": "close", "key": "close_label"})
    return Drawing(width, y + 60.0, ops=ops)


def float_compact(look, texts, options) -> Drawing:
    """E · Float, Compact: the time left, large, and Skip with its ring."""
    ops = []
    label = _caps(texts.skip, look)
    skip_w = _ring_button_width(label, options)
    count_w = estimate(texts.countdown, 40, True) + 12
    ops.append({"t": "text", "rect": (0, 0, count_w, 60), "text": texts.countdown, "size": 40, "bold": True, "align": "r",
                "color": look["ink"], "key": "countdown", "shadow": True})
    _ring_button(ops, "skip", count_w + 22, 0, skip_w, 60.0, look, label, options, texts.percent)
    return Drawing(count_w + 22 + skip_w, 60.0, ops=ops)


def float_minimal(look, texts, options) -> Drawing:
    """E · Float, Minimal: the words alone, in capitals, underlined by the bar."""
    ops = []
    acc = options.accent or look["acc"]
    label = str(texts.skip or "").upper()
    text_w = estimate(label, 28, True) * 1.14 + 4  # set wide: the mockup spaces these letters
    x = 0.0
    ops.append({"t": "button", "which": "skip", "rect": (0, 0, text_w + (38 if options.icons else 0), 52), "bare": True})
    if options.icons:
        ops.append({"t": "img", "tex": "cv_ic_skip.png", "rect": (0, 5, 26, 26), "color": look["ink"]})
        x = 38.0
    ops.append({"t": "text", "rect": (x, 0, text_w, 36), "text": label, "size": 28, "bold": True, "color": look["ink"],
                "shadow": True})
    width = x + text_w
    if options.progress != "Off":
        track = (0.0, 48.0, width, 4.0)
        ops.append({"t": "rect", "rect": track, "color": looks.white(.3)})
        ops.append({"t": "rect", "rect": (0.0, 48.0, width * texts.percent / 100.0, 4.0), "color": acc, "key": "fill",
                    "track": track})
    return Drawing(width, 52.0, ops=ops)


def _centred_button(ops, which, x, y, w, h, look, label, icon, key, options, on_plate=True):
    """A button whose icon and label stand in its middle."""
    ops.append({"t": "button", "which": which, "rect": (x, y, w, h), "pill": not on_plate})
    text_w = estimate(label, 24, True) + 6
    total = text_w + (36 if options.icons and icon else 0)
    cx = x + (w - total) / 2.0
    if options.icons and icon:
        ops.append({"t": "img", "tex": icon, "rect": (cx, y + (h - 24) / 2.0, 24, 24), "ink": which, "key": which + "_icon"})
        cx += 36
    ops.append({"t": "text", "rect": (cx, y, text_w + 20, h), "text": label, "size": 24, "bold": True, "ink": which, "key": key})


def split_full(look, texts, options) -> Drawing:
    """F · Split, Full: the texts in a card of their own, a big Skip tile that fills up beside it,
    and a narrow Close tile."""
    ops = []
    tp, gap = look["tp"], look["gap"]
    acc = options.accent or look["acc"]
    info_w, act_w, cls_w = 500.0, 190.0, 64.0
    y = tp
    with_nested = options.nested and (texts.nested_time or texts.nested_line)
    nested = _nested_text(look, texts)
    content = estimate("%s %s" % (_caps(texts.ending, look), texts.countdown), 32, True)
    if with_nested:
        content = max(content, 62 + estimate(nested.replace("[B]", "").replace("[/B]", ""), 20) * 0.96)
    if options.kicker:
        content = max(content, 19 + estimate(texts.kicker.upper(), 16, True) + 40 + estimate(texts.range, 16))
    info_w = max(info_w, min(900.0, estimate("%s %s" % (_caps(texts.ending, look), texts.countdown), 32, True) * 1.06 + 2 * tp))
    content = min(content, info_w - 2 * tp)
    if options.kicker:
        _kicker(ops, look, texts, tp, y, content, acc)
        y += 20 + 14
    ops.append({"t": "text", "rect": (tp, y, info_w - 2 * tp, 36), "size": 32, "bold": True, "color": look["ink"],
                "text": "%s %s" % (_caps(texts.ending, look), texts.countdown), "key": "heading"})
    y += 36
    if with_nested:
        y += 14
        ops.append({"t": "slot", "slot": "box", "rect": (tp, y, content, 54)})
        ops.append({"t": "img", "tex": "cv_ic_jump.png", "rect": (tp + 16, y + 17, 20, 20), "color": acc})
        ops.append({"t": "text", "rect": (tp + 46, y, content - 54, 54), "size": 20, "color": look["ink2"],
                    "text": nested, "key": "nested"})
        y += 54
    height = max(150.0, y + tp)
    shift = (height - (y + tp)) / 2.0
    if shift:
        for op in ops:
            x0, y0, w0, h0 = op["rect"]
            op["rect"] = (x0, y0 + shift, w0, h0)
    ops.insert(0, {"t": "slot", "slot": "plate", "rect": (0, 0, info_w, height)})
    # the Skip tile: the focus colour as a tile, filling up from its foot
    ax = info_w + gap
    ops.append({"t": "button", "which": "skip", "rect": (ax, 0, act_w, height), "off": "ptile", "on": "tile",
                "panel": look["gap"] > 0})
    if options.progress != "Off":
        filled = height * texts.percent / 100.0
        ops.append({"t": "fillslot", "slot": "fill_v", "rect": (ax, height - filled, act_w, filled), "ink": "skip",
                    "share": 0.13, "key": "fill", "track": (ax, 0, act_w, height), "vertical": True, "min": 30.0})
    column = (44 if options.icons else 0) + 8 + 30 + ((6 + 22) if texts.duration else 0)
    cy = (height - column) / 2.0
    if options.icons:
        ops.append({"t": "img", "tex": "cv_ic_skip.png", "rect": (ax + (act_w - 44) / 2.0, cy, 44, 44), "ink": "skip",
                    "key": "skip_icon"})
        cy += 44 + 8
    ops.append({"t": "text", "rect": (ax, cy, act_w, 30), "text": _caps(texts.skip_word, look), "size": 26, "bold": True,
                "align": "c", "ink": "skip", "key": "skip_label"})
    if texts.duration:
        ops.append({"t": "text", "rect": (ax, cy + 36, act_w, 22), "text": texts.duration, "size": 18, "align": "c",
                    "ink": "skip", "share": 0.7, "key": "skip_time"})
    width = ax + act_w
    if options.close:
        cx = width + gap
        ops.append({"t": "button", "which": "close", "rect": (cx, 0, cls_w, height), "off": "ptile", "on": "tile",
                    "panel": look["gap"] > 0})
        ops.append({"t": "img", "tex": "cv_ic_close.png", "rect": (cx + (cls_w - 24) / 2.0, (height - 24) / 2.0, 24, 24),
                    "ink": "close", "key": "close_icon"})
        width = cx + cls_w
    return Drawing(width, height, ops=ops)


def split_compact(look, texts, options) -> Drawing:
    """F · Split, Compact: the type and the time left in a pill, Skip as a pill, Close as a disc."""
    ops = []
    gap, h = look["gap"], 76.0
    kicker = _caps(texts.kicker, look)
    info_w = 52 + estimate(kicker, 22) + 14 + estimate(texts.countdown, 28, True)
    ops.append({"t": "slot", "slot": "plate_m" if look["rb"] > 100 else "plate", "rect": (0, 0, info_w, h)})
    ops.append({"t": "text", "rect": (26, 0, estimate(kicker, 22) + 8, h), "text": kicker, "size": 22, "color": look["ink"]})
    ops.append({"t": "text", "rect": (26 + estimate(kicker, 22) + 14, 0, estimate(texts.countdown, 28, True) + 12, h),
                "text": texts.countdown, "size": 28, "bold": True, "color": look["ink"], "key": "countdown"})
    label = _caps(texts.skip, look)
    act_w = 56 + estimate(label, 24, True) + (38 if options.icons else 0)
    ax = info_w + gap
    ops.append({"t": "button", "which": "skip", "rect": (ax, 0, act_w, h), "pill": True, "panel": True})
    if options.progress != "Off":
        ops.append({"t": "fillslot", "slot": "fill_h", "rect": (ax, 0, act_w * texts.percent / 100.0, h), "ink": "skip",
                    "share": 0.13, "key": "fill", "track": (ax, 0, act_w, h), "min": 38.0, "stop": 12.0})
    cx = ax + 28
    if options.icons:
        ops.append({"t": "img", "tex": "cv_ic_skip.png", "rect": (cx, (h - 26) / 2.0, 26, 26), "ink": "skip", "key": "skip_icon"})
        cx += 38
    ops.append({"t": "text", "rect": (cx, 0, act_w - (cx - ax) - 8, h), "text": label, "size": 24, "bold": True, "ink": "skip",
                "key": "skip_label"})
    width = ax + act_w
    if options.close:
        dx = width + gap
        ops.append({"t": "button", "which": "close", "rect": (dx, 0, h, h), "bare": True, "panel": True})
        ops.append({"t": "img", "tex": "cv_dot.png", "rect": (dx, 0, h, h), "bg": "close"})
        ops.append({"t": "img", "tex": "cv_ic_close.png", "rect": (dx + (h - 24) / 2.0, (h - 24) / 2.0, 24, 24), "ink": "close",
                    "key": "close_icon"})
        width = dx + h
    return Drawing(width, h, ops=ops)


def split_minimal(look, texts, options) -> Drawing:
    """F · Split, Minimal: the Skip pill alone."""
    ops = []
    h = 76.0
    label = _caps(texts.skip, look)
    act_w = 56 + estimate(label, 24, True) + (38 if options.icons else 0)
    ops.append({"t": "button", "which": "skip", "rect": (0, 0, act_w, h), "pill": True, "panel": True})
    if options.progress != "Off":
        ops.append({"t": "fillslot", "slot": "fill_h", "rect": (0, 0, act_w * texts.percent / 100.0, h), "ink": "skip",
                    "share": 0.13, "key": "fill", "track": (0, 0, act_w, h), "min": 38.0, "stop": 12.0})
    cx = 28.0
    if options.icons:
        ops.append({"t": "img", "tex": "cv_ic_skip.png", "rect": (cx, (h - 26) / 2.0, 26, 26), "ink": "skip", "key": "skip_icon"})
        cx += 38
    ops.append({"t": "text", "rect": (cx, 0, act_w - cx - 8, h), "text": label, "size": 24, "bold": True, "ink": "skip",
                "key": "skip_label"})
    return Drawing(act_w, h, ops=ops)


# Timeline: where the three blocks stand on its track, in percent (left, width): the segment that
# is playing, the one Skip lands in, and what follows.
TIMELINE_BLOCKS = ((6.0, 52.0), (56.0, 26.0), (83.0, 17.0))


def timeline_full(look, texts, options) -> Drawing:
    """G · Timeline, Full: the segments as blocks on a line, the playhead, and a dashed arc from it
    to where Skip lands."""
    ops = []
    width, tp, pad, gap = 940.0, look["tp"], look["pad"], look["gap"]
    acc = options.accent or look["acc"]
    y = tp
    ops.append({"t": "text", "rect": (tp, y, 560, 36), "size": 32, "bold": True, "color": look["ink"], "key": "heading",
                "text": "%s %s" % (_caps(texts.ending, look), texts.countdown)})
    if options.nested and (texts.nested_time or texts.nested_line):
        nested = _nested_text(look, texts)
        text_w = estimate(nested.replace("[B]", "").replace("[/B]", ""), 20) * 0.95
        ops.append({"t": "img", "tex": "cv_ic_jump.png", "rect": (width - tp - text_w - 32, y + 8, 20, 20), "color": acc})
        ops.append({"t": "text", "rect": (width - tp - 420, y, 420, 36), "size": 20, "align": "r", "color": look["ink2"],
                    "text": nested, "key": "nested"})
    y += 36 + 14 + 30
    tx, tw, th = tp, width - 2 * tp, 56.0
    labels = (texts.kicker, texts.chip, texts.rest)
    for index, ((left, share), label) in enumerate(zip(TIMELINE_BLOCKS, labels)):
        bx, bw = tx + tw * left / 100.0, tw * share / 100.0
        ops.append({"t": "slot", "slot": ("box", "box2", "box3")[index], "rect": (bx, y, bw, th)})
        if index == 0:
            ops.append({"t": "rect", "rect": (bx + 2, y + 2, (bw - 4) * texts.percent / 100.0, th - 4),
                        "color": looks.with_alpha(acc, 0.32), "key": "fill", "track": (bx + 2, y + 2, bw - 4, th - 4)})
            ops.append({"t": "slot", "slot": "outline", "rect": (bx, y, bw, th), "color": acc})
        if label:
            ops.append({"t": "text", "rect": (bx + 14, y, bw - 20, th), "text": str(label).upper(), "size": 16, "bold": True,
                        "color": look["ink"] if index == 0 else look["ink2"]})
    cur_x, cur_w = tx + tw * TIMELINE_BLOCKS[0][0] / 100.0, tw * TIMELINE_BLOCKS[0][1] / 100.0
    land_x = tx + tw * TIMELINE_BLOCKS[1][0] / 100.0
    head = cur_x + cur_w * texts.percent / 100.0
    follow = {"x0": cur_x, "span": cur_w, "end": land_x}
    ops.append({"t": "img", "tex": "cv_arc.png", "rect": (head, y - 34, max(4.0, land_x - head), 30), "color": acc, "key": "arc",
                "follow": dict(follow, mode="arc")})
    ops.append({"t": "rect", "rect": (head - 2, y - 8, 4, th + 16), "color": look["ink"], "key": "playhead",
                "follow": dict(follow, mode="centre")})
    y += th + 14
    ops.append({"t": "text", "rect": (cur_x - 60, y, 120, 22), "text": texts.t0, "size": 16, "align": "c", "color": look["ink3"]})
    ops.append({"t": "text", "rect": (head - 60, y, 120, 22), "text": texts.now, "size": 16, "bold": True, "align": "c",
                "color": look["ink"], "key": "now", "follow": dict(follow, mode="label")})
    ops.append({"t": "text", "rect": (land_x - 60, y, 120, 22), "text": texts.nested_time, "size": 16, "bold": True, "align": "c",
                "color": acc})
    end_x = tx + tw * TIMELINE_BLOCKS[2][0] / 100.0
    ops.append({"t": "text", "rect": (end_x - 60, y, 120, 22), "text": texts.t1, "size": 16, "align": "c", "color": look["ink3"]})
    y += 22 + max(pad, tp - 11)
    bh = 60.0
    close_w = 0.0
    if options.close:
        close_w = 48 + estimate(_caps(texts.close, look), 24, True) + (36 if options.icons else 0)
    skip_w = width - 2 * pad - (close_w + gap if options.close else 0)
    _button(ops, "skip", pad, y, skip_w, bh, look, _caps(texts.skip, look), "cv_ic_skip.png", "skip_label", options,
            time=texts.duration)
    if options.close:
        _button(ops, "close", width - pad - close_w, y, close_w, bh, look, _caps(texts.close, look), "cv_ic_close.png",
                "close_label", options)
    y += bh + pad
    ops.insert(0, {"t": "slot", "slot": "plate", "rect": (0, 0, width, y)})
    return Drawing(width, y, ops=ops)


def _strip(ops, x, y, w, h, percent, on, off, mark):
    """The Timeline in small: three bars in the shares of the blocks, the first one lit, a mark on it."""
    shares = (52.0, 26.0, 22.0)
    total = sum(shares)
    bx = x
    for index, share in enumerate(shares):
        bw = (w - 6) * share / total
        ops.append({"t": "rect", "rect": (bx, y, bw, h), "color": on if index == 0 else off})
        bx += bw + 3
    first = (w - 6) * shares[0] / total
    ops.append({"t": "rect", "rect": (x + first * percent / 100.0 - 2, y - 5, 4, h + 10), "color": mark, "key": "playhead",
                "follow": {"x0": x, "span": first, "mode": "centre"}})


def timeline_compact(look, texts, options) -> Drawing:
    """G · Timeline, Compact: Skip, the type with the time left and where Skip lands over a small
    timeline, and a small Close."""
    ops = []
    pad, bh = look["pad"], 60.0
    acc = options.accent or look["acc"]
    label = _caps(texts.skip, look)
    skip_w = 48 + estimate(label, 24, True) + (36 if options.icons else 0)
    _button(ops, "skip", pad, pad, skip_w, bh, look, label, "cv_ic_skip.png", "skip_label", options, on_plate=False)
    x = pad + skip_w + 18 + 10
    mini = 300.0
    ops.append({"t": "text", "rect": (x, pad + 6, 190, 22), "size": 17, "color": look["ink2"], "key": "countdown_line",
                "text": "%s [B]%s[/B]" % (_caps(texts.kicker, look), texts.countdown)})
    if options.nested and texts.nested_time:
        ops.append({"t": "text", "rect": (x + mini - 160, pad + 6, 160, 22), "size": 17, "align": "r", "color": look["ink2"],
                    "text": "%s [B]%s[/B]" % (_caps(texts.next_word, look), texts.nested_time)})
    if options.progress != "Off":
        _strip(ops, x, pad + 38, mini, 12.0, texts.percent, acc, look["track"], look["ink"])
    x += mini + 18
    if options.close:
        _button(ops, "close", x, pad, 60, bh, look, "", "cv_ic_close.png", "close_label", options, on_plate=False, ghost=True)
        for op in ops:
            if op.get("key") == "close_icon":
                op["rect"] = (x + 18, pad + 18, 24, 24)
        x += 60
    width, height = x + pad, bh + 2 * pad
    ops.insert(0, {"t": "slot", "slot": "plate_c" if look["rb"] > 100 else "plate", "rect": (0, 0, width, height)})
    return Drawing(width, height, ops=ops)


def timeline_minimal(look, texts, options) -> Drawing:
    """G · Timeline, Minimal: the Skip button with the small timeline inside it."""
    ops = []
    pad, bh = min(look["pad"], 6), 72.0
    label = _caps(texts.skip, look)
    text_w = estimate(label, 24, True) + 8
    inner = text_w + (36 if options.icons else 0)
    skip_w = inner + 48
    ops.append({"t": "button", "which": "skip", "rect": (pad, pad, skip_w, bh), "pill": True})
    x, top = pad + 24, pad + (14 if options.progress != "Off" else 22)
    if options.icons:
        ops.append({"t": "img", "tex": "cv_ic_skip.png", "rect": (x, top + 2, 24, 24), "ink": "skip", "key": "skip_icon"})
        x += 36
    ops.append({"t": "text", "rect": (x, top, text_w + 12, 28), "text": label, "size": 24, "bold": True, "ink": "skip",
                "key": "skip_label"})
    if options.progress != "Off":
        _strip(ops, pad + 24, pad + 50, inner, 6.0, texts.percent, look["foc_acc"], looks.with_alpha(look["foc_ink"], 0.16),
               look["foc_ink"])
    width, height = skip_w + 2 * pad, bh + 2 * pad
    ops.insert(0, {"t": "slot", "slot": "plate_c" if look["rb"] > 100 else "plate", "rect": (0, 0, width, height)})
    return Drawing(width, height, ops=ops)


def rail_full(look, texts, options) -> Drawing:
    """H · Side rail, Full: a tab on the screen edge. The ring on top, the texts under it, the
    buttons stacked."""
    ops = []
    width, pad, gap = 380.0, look["pad"], look["gap"]
    acc = options.accent or look["acc"]
    y = 30.0
    ring = 150.0
    rx = (width - ring) / 2.0
    if options.progress != "Off":
        _ring(ops, look, rx, y, ring, texts.percent, acc)
    ops.append({"t": "text", "rect": (rx, y + 42, ring, 46), "text": texts.countdown, "size": 40, "bold": True, "align": "c",
                "color": look["ink"], "key": "countdown"})
    ops.append({"t": "text", "rect": (rx, y + 92, ring, 18), "text": texts.left.upper(), "size": 15, "bold": True, "align": "c",
                "color": looks.with_alpha(look["ink"], 0.65)})
    y += ring + 16
    if options.kicker:
        ops.append({"t": "text", "rect": (10, y, width - 20, 20), "size": 16, "bold": True, "align": "c", "color": look["ink2"],
                    "text": "%s · %s" % (texts.kicker.upper(), texts.range), "key": "kicker"})
        y += 20 + 16
    ending = _caps(texts.ending, look)
    fits = (width - 40) / max(1.0, estimate(ending, 32, True))
    ops.append({"t": "text", "rect": (10, y, width - 20, 36), "size": max(20.0, 32 * min(1.0, fits)), "bold": True, "align": "c",
                "color": look["ink"], "text": ending})
    y += 36 + 16
    if options.nested and (texts.nested_time or texts.nested_line):
        nested = _nested_text(look, texts)
        plain = nested.replace("[B]", "").replace("[/B]", "")
        second = ""
        if estimate(plain, 20) > width - 76 and " " in plain:
            # too long for the rail: the time goes on a line of its own, as in the mockup
            head, _space, tail = plain.rpartition(" ")
            nested, second = head, "[B]%s[/B]" % tail
        more = 26 if second else 0
        box_h = 14 + 24 + more + ((8 + 28) if texts.chip else 0) + 10
        ops.append({"t": "slot", "slot": "box", "rect": (26, y, width - 52, box_h)})
        ops.append({"t": "text", "rect": (30, y + 14, width - 60, 24), "size": 20, "align": "c", "color": look["ink2"],
                    "text": nested, "key": "nested"})
        if second:
            ops.append({"t": "text", "rect": (30, y + 40, width - 60, 24), "size": 20, "align": "c", "color": look["ink"],
                        "text": second})
            y += more
        if texts.chip:
            chip = texts.chip.upper()
            chip_w = estimate(chip, 14, True) + 24
            cx = (width - chip_w) / 2.0
            ops.append({"t": "slot", "slot": "chip", "rect": (cx, y + 46, chip_w, 28)})
            ops.append({"t": "text", "rect": (cx, y + 46, chip_w, 28), "text": chip, "size": 14, "bold": True, "align": "c",
                        "color": look.get("chip_ink") or look["ink"], "key": "chip"})
        y += box_h - more
    y += 24 + pad
    _centred_button(ops, "skip", pad, y, width - 2 * pad, 60.0, look, _caps(texts.skip, look), "cv_ic_skip.png", "skip_label",
                    options)
    y += 60
    if options.close:
        y += gap
        _centred_button(ops, "close", pad, y, width - 2 * pad, 60.0, look, _caps(texts.close, look), "cv_ic_close.png",
                        "close_label", options)
        y += 60
    y += pad
    ops.insert(0, {"t": "slot", "slot": "plate", "rect": (0, 0, width, y)})
    return Drawing(width, y, ops=ops)


def rail_compact(look, texts, options) -> Drawing:
    """H · Side rail, Compact: a small ring with the seconds, the type over when it ends, Skip."""
    ops = []
    width, pad = 300.0, look["pad"]
    acc = options.accent or look["acc"]
    if options.progress != "Off":
        _ring(ops, look, 20, 20, 72, texts.percent, acc)
    seconds = texts.seconds or texts.countdown
    ops.append({"t": "text", "rect": (20, 20, 72, 72), "text": seconds, "size": 22 if len(seconds) < 3 else 18, "bold": True,
                "align": "c", "color": look["ink"], "key": "seconds"})
    ops.append({"t": "text", "rect": (104, 30, width - 114, 20), "text": texts.kicker.upper(), "size": 16, "bold": True,
                "color": look["ink2"]})
    ops.append({"t": "text", "rect": (104, 54, width - 114, 28), "size": 22, "bold": True, "color": look["ink"],
                "text": _caps("%s %s" % (texts.ends_in, texts.countdown), look), "key": "ends_line"})
    y = 112.0 + pad
    _centred_button(ops, "skip", pad, y, width - 2 * pad, 60.0, look, _caps(texts.skip, look), "cv_ic_skip.png", "skip_label",
                    options)
    y += 60 + pad
    ops.insert(0, {"t": "slot", "slot": "plate", "rect": (0, 0, width, y)})
    return Drawing(width, y, ops=ops, lift=120.0)


def rail_minimal(look, texts, options) -> Drawing:
    """H · Side rail, Minimal: a square Skip button on the screen edge, a thin bar rising at its side."""
    ops = []
    pad, size = look["pad"], 112.0
    ops.append({"t": "button", "which": "skip", "rect": (pad, pad, size, size)})
    if options.icons:
        ops.append({"t": "img", "tex": "cv_ic_skip.png", "rect": (pad + 38, pad + 24, 36, 36), "ink": "skip", "key": "skip_icon"})
    ops.append({"t": "text", "rect": (pad, pad + (68 if options.icons else 44), size, 24), "text": _caps(texts.skip_word, look),
                "size": 18, "bold": True, "align": "c", "ink": "skip", "key": "skip_label"})
    if options.progress != "Off":
        track = (pad, pad, 7.0, size)
        filled = size * texts.percent / 100.0
        ops.append({"t": "rect", "rect": (pad, pad + size - filled, 7.0, filled), "color": look["foc_acc"], "key": "fill",
                    "track": track, "vertical": True})
    total = size + 2 * pad
    ops.insert(0, {"t": "slot", "slot": "plate", "rect": (0, 0, total, total)})
    return Drawing(total, total, ops=ops, lift=120.0)


def overlay_ops(kind, look, found, left, top, place, scale, fade=False, direction="Auto") -> list:
    """The one shade behind a dialog, as drawing ops in screen pixels. ``found`` is the design as
    built (its size and how far its own shade reaches); ``left`` and ``top`` are where it stands."""
    if kind in ("None", "", None):
        return []
    w, h = found.width * scale, found.height * scale
    tint = tuple(look["ov"])
    alpha = look["ova"]
    right_side = left + w / 2.0 > SCREEN_W / 2.0 + 2
    left_side = left + w / 2.0 < SCREEN_W / 2.0 - 2
    top_side = top + h / 2.0 < SCREEN_H / 2.0 - 2
    bottom_side = top + h / 2.0 > SCREEN_H / 2.0 + 2

    def op(tex, rect, a, slot="overlay"):
        return {"t": "slot", "slot": slot, "tex": tex, "rect": rect, "abs": True,
                "color": tint + (int(round(255 * max(0.0, min(1.0, a)))),)}

    if fade and kind in ("Square", "Round"):
        kind += "Fade"
    if kind == "SquareFade" and direction == "Radial":
        kind = "Glow"
    if kind in ("Round", "RoundFade"):
        reach = (found.shade if 0 < found.shade <= 60 else 30.0) * scale
        return [op("rdg" if kind == "RoundFade" else "rd", (left - reach, top - reach, w + 2 * reach, h + 2 * reach),
                   alpha + (0.14 if kind == "RoundFade" else 0.0), slot="overlay9")]
    if kind == "Band":
        height = (found.shade if found.shade > 60 else h + 160) * scale
        if top_side:
            return [op("band_top", (0, 0, SCREEN_W, height), alpha + 0.18)]
        return [op("band", (0, SCREEN_H - height, SCREEN_W, height), alpha + 0.18)]
    if kind == "Side" or (kind in ("SquareFade", "Band", "Glow") and not (top_side or bottom_side) and (left_side or right_side)):
        width = 860.0 * scale
        return [op("side_l" if left_side else "side_r", (0 if left_side else SCREEN_W - width, 0, width, SCREEN_H), alpha + 0.16)]
    m = 40.0 * scale
    x0 = 0.0 if left_side else max(0.0, left - m)
    x1 = SCREEN_W if right_side else min(SCREEN_W, left + w + m)
    y0 = 0.0 if top_side else max(0.0, top - m)
    y1 = SCREEN_H if bottom_side else min(SCREEN_H, top + h + m)
    if kind == "Square":
        return [op("solid", (x0, y0, x1 - x0, y1 - y0), alpha)]
    if kind == "SquareFade":
        extra = 420.0 * scale
        if direction == "Vertical" or (direction == "Auto" and not (left_side or right_side)):
            return [op("band_top" if top_side else "band", (x0, 0 if top_side else y0 - 80 * scale, x1 - x0, y1 - y0 + 80 * scale),
                       alpha + 0.18)]
        if direction == "Horizontal" and not left_side:
            return [op("side_r", (x0 - extra, y0, x1 - x0 + extra, y1 - y0), alpha + 0.14)]
        if left_side:
            return [op("side_l", (x0, y0, x1 - x0 + extra, y1 - y0), alpha + 0.14)]
        if right_side:
            return [op("side_r", (x0 - extra, y0, x1 - x0 + extra, y1 - y0), alpha + 0.14)]
        return [op("band_top" if top_side else "band", (0, y0 - 80 * scale if not top_side else 0, SCREEN_W, y1 - y0 + 80 * scale),
                   alpha + 0.18)]
    # Glow: a round shade out of the corner the dialog sits in
    gw, gh = w + 700 * scale, h + 420 * scale
    name = ("t" if top_side else "b") + ("l" if left_side else "r" if right_side else "c")
    gx = 0.0 if left_side else SCREEN_W - gw if right_side else (SCREEN_W - gw) / 2.0
    return [op("glow_" + name, (gx, 0.0 if top_side else SCREEN_H - gh, gw, gh), alpha + 0.2)]


_BUILDERS = {
    ("Band", "Full"): band_full, ("Band", "Compact"): band_compact, ("Band", "Minimal"): band_minimal,
    ("Float", "Full"): float_full, ("Float", "Compact"): float_compact, ("Float", "Minimal"): float_minimal,
    ("Split", "Full"): split_full, ("Split", "Compact"): split_compact, ("Split", "Minimal"): split_minimal,
    ("Timeline", "Full"): timeline_full, ("Timeline", "Compact"): timeline_compact,
    ("Timeline", "Minimal"): timeline_minimal,
    ("Rail", "Full"): rail_full, ("Rail", "Compact"): rail_compact, ("Rail", "Minimal"): rail_minimal,
    ("Dial", "Full"): dial_full, ("Dial", "Compact"): dial_compact, ("Dial", "Minimal"): dial_minimal,
    ("Stack", "Full"): stack_full, ("Stack", "Compact"): stack_compact, ("Stack", "Minimal"): stack_minimal,
    ("Slab", "Full"): slab_full, ("Slab", "Compact"): slab_compact, ("Slab", "Minimal"): slab_minimal,
}


def motion(options, centre, from_right, shown, leaving, beating, reach=1.0, fade_only=False) -> list:
    """The animations of one part of a dialog, as ``(event, attributes)`` pairs for Kodi.

    ``shown``, ``leaving`` and ``beating`` are conditions (window properties): a part is hidden until
    ``shown`` holds, then comes the way Appears says; it goes the way Leaves says once ``leaving``
    holds; it beats while ``beating`` holds. ``centre`` is the middle of the dialog and ``reach``
    scales the distances (both in the units of the part: the screen, or the Studio's small screen).
    ``fade_only`` is for what lies behind the dialog (its shade), which only fades.
    """
    appear = options.appear if options.appear in APPEARS else "Fade"
    leave = options.leave if options.leave in LEAVES else "Fade"
    come, go = APPEAR_MS[appear], LEAVE_MS[leave]
    if getattr(options, "speed", 0):
        come = max(60, int(options.speed))  # Speed: how long it takes to come; it leaves a little quicker
        go = max(60, int(come * 0.75))
    cx, cy = centre
    out = [("conditional", "effect=fade start=100 end=0 time=0 condition=!%s" % shown),
           ("conditional", "effect=fade start=0 end=100 time=%d condition=%s" % (come, shown)),
           ("conditional", "effect=fade start=100 end=0 time=%d condition=%s" % (go, leaving))]
    if fade_only:
        return out
    if appear == "Rise":
        out.append(("conditional", "effect=slide start=0,%d end=0,0 time=%d tween=cubic easing=out condition=%s"
                    % (round(26 * reach), come, shown)))
    elif appear == "Pop":
        out.append(("conditional", "effect=zoom start=90 end=100 center=%.1f,%.1f time=%d tween=back easing=out condition=%s"
                    % (cx, cy, come, shown)))
    elif appear == "Slide":
        out.append(("conditional", "effect=slide start=%d,0 end=0,0 time=%d tween=cubic easing=out condition=%s"
                    % (round((70 if from_right else -70) * reach), come, shown)))
    if leave == "Drop":
        out.append(("conditional", "effect=slide start=0,0 end=0,%d time=%d tween=cubic easing=in condition=%s"
                    % (round(22 * reach), go, leaving)))
    elif leave == "Shrink":
        out.append(("conditional", "effect=zoom start=100 end=92 center=%.1f,%.1f time=%d condition=%s" % (cx, cy, go, leaving)))
    if options.pulse:
        out.append(("conditional", "effect=zoom start=100 end=103 center=%.1f,%.1f time=500 pulse=true condition=%s"
                    % (cx, cy, beating)))
    return out


def names_type(options, texts) -> bool:
    """Whether the drawing says the segment type somewhere besides the Skip button. Then the button
    says Skip alone: the type is written once."""
    kicker = (texts.kicker or "").strip().lower()
    if not kicker or not texts.skip_word or options.size == "Minimal":
        return False
    if kicker in (texts.ending or "").lower():
        return True
    if options.size == "Full":
        return bool(options.kicker)
    return options.design in ("Split", "Timeline", "Rail")


def adjusted(look, options) -> dict:
    """A look with what the options change of it: All capitals, and the ink of an outlined focus. The
    designs and the code that draws them both take the look from here."""
    if getattr(options, "caps", "Look") in ("On", "Off"):
        look = dict(look, caps=options.caps == "On")  # whatever the look writes
    if getattr(options, "focus_style", "Look") == "Outline":
        # the button in focus is a line around it: what is written on it keeps the colour of the others
        look = dict(look, foc_ink=look["btn_ink"], foc_acc=look["acc"])
    return look


def draw(options: Options, texts: Texts) -> Drawing:
    """The finished drawing in screen pixels (1920 x 1080), placed where the options say."""
    rule = RULES.get(options.design, {})
    corners = rule.get("corners") or options.corners
    look = looks.look(options.look, corners)
    look = adjusted(look, options)
    if rule.get("bare"):
        look = bare_look(look)
    builder = _BUILDERS.get((options.design, options.size)) or stack_full
    global _TEXT, _PERCENT, _BAR_ROUND
    _BAR_ROUND = getattr(options, "bar_edges", "Straight") == "Rounded"
    factor = text_size(options.text_size) / 100.0
    _TEXT = factor  # widths that follow a text follow its size
    _PERCENT = float(texts.percent or 0.0)
    if options.progress == "Auto":
        options = dataclasses.replace(options, progress="Line")
    elif options.progress in ("Circle", "Fill") and options.design not in LINE_DESIGNS:
        options = dataclasses.replace(options, progress="Line")  # a ring, tile or timeline keeps its own
    if names_type(options, texts):
        texts = dataclasses.replace(texts, skip=texts.skip_word)  # the type is said once
    try:
        found = builder(look, texts, options)
    finally:
        _TEXT = 1.0
    scale = looks.SCALE
    seen = max(0.3, options.zoom / 100.0)
    if rule.get("bare"):
        # the small pictures that lie on the video beside its texts get the same dark line around them
        for op in found.ops:
            if op["t"] == "img" and "color" in op and op.get("tex") in ("cv_ic_jump.png", "cv_ic_skip.png", "cv_dot.png"):
                op["shadow"] = True
    for op in found.ops:
        # a picture cannot be drawn lower than twice its border: a low card takes the slot with the smaller one
        if op.get("slot") == "plate" and op["rect"][3] < 2 * BORDERS["1080"]["plate"]:
            if look["r"] == 0:
                op["slot"] = "plate_h"  # a square card: a small border does
            else:
                op["slot"] = "plate_c" if op["rect"][3] >= 2 * BORDERS["1080"]["plate_c"] else "plate_m"
    plate = next((op for op in found.ops if str(op.get("slot", "")).startswith("plate")), None)
    if plate is None:
        plate = next((op for op in found.ops if op["t"] == "button" and op.get("panel")), None)
        if plate is not None:
            plate = dict(plate, panel=False)
    extra = []
    if plate and options.shadow and rule.get("shadow", True):
        x, y, w, h = plate["rect"]
        if look.get("hard_shadow"):
            offset, _colour = look["hard_shadow"]
            extra.append({"t": "slot", "slot": "shadow", "tex": "cv_black.png", "rect": (x + offset, y + offset, w, h)})
        elif look.get("glow"):
            reach = SHADOW_REACH
            extra.append({"t": "slot", "slot": "shadow", "tex": "glow",
                          "rect": (x - reach, y - reach, w + 2 * reach, h + 2 * reach)})
        elif look["shadow"]:
            # every panel casts its shade: the card, and a tile or pill that stands beside it
            panels = [plate["rect"]]
            for op in found.ops:
                if op["t"] == "button" and op.get("panel") and op["rect"] not in panels:
                    panels.append(op["rect"])
            big = ["shadow", "shadow_2", "shadow_3"]
            small = ["shadow_s", "shadow_s2", "shadow_s3"]
            for x, y, w, h in panels:
                if min(w, h) + 2 * SHADOW_REACH >= 2 * BORDERS["1080"]["shadow"] and big:
                    reach, drop, slot = SHADOW_REACH, SHADOW_DROP, big.pop(0)
                elif min(w, h) + 2 * SMALL_REACH >= 2 * BORDERS["1080"]["shadow_s"] and small:
                    reach, drop, slot = SMALL_REACH, SMALL_DROP, small.pop(0)
                else:
                    continue
                extra.append({"t": "slot", "slot": slot, "tex": "shadow",
                              "rect": (x - reach, y - reach + drop, w + 2 * reach, h + 2 * reach)})
    out = Drawing(found.width * scale, found.height * scale, corners=corners)
    if rule.get("band"):
        foot = (found.drop or 44.0) * scale
        out.left = (SCREEN_W - out.width) / 2.0
        out.top = foot if place_name(options.place).startswith("Top") else SCREEN_H - foot - out.height
    else:
        place = place_name(options.place)
        if rule.get("centre"):
            place = "Top" if place.startswith("Top") else "Bottom"
        elif rule.get("edge") and not found.lift:
            place = "Left" if "Left" in place else "Right"
        out.left, out.top = origin(out.width, out.height, place, options.distance,
                                   flush=bool(rule.get("flush")), lift=found.lift * scale)
    rise = float(getattr(options, "rise", 0.0) or 0.0) * scale
    if rise and place_name(options.place).startswith("Bottom") and out.height < SCREEN_H * 0.8:
        out.top = max(0.0, out.top - rise)  # clear of the subtitles (a dialog that fills the screen stays)
    # the point the whole is zoomed around: the edge or corner of the dialog that faces its place
    spot = ("Top" if place_name(options.place).startswith("Top") else "Bottom") if rule.get("band") else place
    ax = out.left if "Left" in spot else out.left + out.width if "Right" in spot else out.left + out.width / 2.0
    ay = out.top if spot.startswith("Top") else out.top + out.height if spot.startswith("Bottom") else out.top + out.height / 2.0
    full_left, full_top = out.left, out.top
    out.zoom, out.anchor = seen * 100.0, (ax, ay)
    out.left, out.top = ax + seen * (full_left - ax), ay + seen * (full_top - ay)
    out.width, out.height = out.width * seen, out.height * seen
    # the one shade behind the dialog: the choice, else the design's own. It lies on the screen, not in the
    # zoomed group, so it is laid out for the dialog as it is seen.
    kind = rule.get("overlay", "None") if options.overlay == "Auto" else options.overlay
    shade = overlay_ops(kind, look, found, out.left, out.top, options.place, scale * seen,
                        fade=bool(options.overlay_gradient) and options.overlay != "Auto", direction=options.gradient)
    out.overlaid = bool(shade)
    behind = background_ops(options, look, texts, found.ops)
    if behind:
        out.ops.extend(behind)
        out.overlaid = True  # the texts lie on the shade or the colour, not on the video
    out.ops.extend(shade)
    for op in extra + found.ops:
        op = dict(op)
        if op.get("abs"):
            out.ops.append(op)
            continue
        x, y, w, h = op["rect"]
        op["rect"] = (full_left + x * scale, full_top + y * scale, w * scale, h * scale)
        if "track" in op:
            x, y, w, h = op["track"]
            op["track"] = (full_left + x * scale, full_top + y * scale, w * scale, h * scale)
        if "follow" in op:
            follow = dict(op["follow"])
            follow["x0"] = full_left + follow["x0"] * scale
            follow["span"] = follow["span"] * scale
            if "end" in follow:
                follow["end"] = full_left + follow["end"] * scale
            op["follow"] = follow
        if "size" in op:
            op["size"] = op["size"] * scale * factor
        if "min" in op:
            op["min"], op["stop"] = op["min"] * scale, op.get("stop", 0.0) * scale
        out.ops.append(op)
    return out


def bare_look(look) -> dict:
    """A look for a design that lies on the video: a look with dark ink on a light card writes light there."""
    r, g, b, _a = look["ink"]
    out = dict(look)
    if 0.299 * r + 0.587 * g + 0.114 * b < 128:
        out.update(ink=looks.white(1), ink2=looks.white(.8), ink3=looks.white(.6), track=looks.white(.3))
    return out


def ink(look, which, focused) -> tuple:
    """The colour of what is written on a button."""
    return look["foc_ink"] if focused else look["btn_ink"]


def picture(code, corners, part, folder) -> str:
    """The picture of a look's part: ``plate``, ``box``, ``chip``, ``btn``, ``foc``, ``pill``, ``pillfoc``."""
    return "cv_%s%s_%s_%s.png" % (code if code in looks.LOOKS else "fgf", looks.corner_key(code, corners), part, folder)
