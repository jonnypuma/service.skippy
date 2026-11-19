# -*- coding: utf-8 -*-
"""The drawn Up Next popup: the designs of the mockups (boards N2) on the engine of the drawn skip
dialog (``skip_canvas``).

A design is a function that turns a look, the texts and the options into a list of things to draw,
in the mockups' own measures (pixels of a 1920 x 1080 screen). The looks, the shades, the places on
the screen, Size on screen and the motion are those of ``skip_canvas``: the designs are entered in
its tables under names of their own, and ``draw`` here is ``skip_canvas.draw``.

Play now is the engine's Skip button and Cancel its Close button, so the focus, the colours of what
is written on them and the Studio's preview work as they do for the skip dialog.

This part needs no Kodi.
"""

from __future__ import annotations

from dataclasses import dataclass

import skip_canvas as cv
import skip_canvas_looks as looks
import skip_layouts as sl

# stored layout value -> (design name in the engine, name shown, letter of the mockup)
DESIGNS = (
    ("CardA", "NCard", "Card", "A"),
    ("Slab", "NSlab", "Poster slab", "B"),
    ("Ring", "NRing", "Play ring", "C"),
    ("Band", "NBand", "Lower third", "D"),
    ("Float", "NFloat", "Float", "E"),
    ("Takeover", "NTake", "Takeover", "F"),
    ("Queue", "NQueue", "Queue", "G"),
    ("Rail", "NRail", "Side rail", "H"),
    ("Poster", "NCard", "Poster card", "A"),  # the Card with the show's poster for its picture
)
DRAWN = {stored: design for stored, design, _name, _letter in DESIGNS}
SIZES = cv.SIZES
PREFIX = "next_canvas_"
# The options of a drawn Up Next design, as settings: the same choices as the drawn skip dialog has, under
# names of their own (name -> default). ``form`` is Full, Compact or Minimal.
OPTION_KEYS = {
    "form": "Full", "corners": "Skin", "close": "true", "icons": "true", "plot": "true", "picture": "Episode",
    "progress": "Auto", "accent": "Auto", "zoom": "100", "place": "", "distance": "64", "overlay": sl.OVERLAY_AUTO,
    "overlay_gradient": "false", "gradient": "Auto", "appear": sl.APPEARS[0], "leave": sl.LEAVES[0], "pulse": "false",
    "text_shadow": "Mild", "outline": "Medium", "text_size": "100",
    # the episode line over the title, the show's logo where a design has a place for it, and the look of the
    # skip dialog in place of the popup's own
    "kicker": "true", "logo": "true", "same_look": "false",
    # Progress as a fill: where it shows; all capitals; what stands in for a missing episode picture; the time on
    # Play; a Watch credits button; the bar moving smoothly or once a second; how fast the popup comes
    "fill_on": "Button", "caps": "Look", "fallback": "Fanart", "time": "true", "credits": "false", "bar": "Smooth",
    "speed": "0",
    # the look of the skin in place of the popup's own, room for the subtitles, and how the button in focus shows
    "follow_skin": "false", "subtitles": "false", "focus_style": "Look",
}

cv.RULES.update({
    "NSlab": {"corners": "Hard", "flush": True, "shadow": False},
    "NRing": {"bare": True, "overlay": "RoundFade", "corners": "Rounded"},
    "NBand": {"bare": True, "overlay": "Band", "band": True},
    "NFloat": {"bare": True, "overlay": "None", "corners": "Rounded"},
    "NTake": {},
    "NQueue": {"centre": True},  # in the middle of the bottom (or top) edge
    "NRail": {"corners": "Hard", "flush": True, "edge": True, "overlay": "Side", "shadow": False},
})
# what the whole-screen form of Takeover fixes (the other two forms are a corner panel and a picture)
TAKEOVER_FULL = {"bare": True, "flush": True, "shadow": False, "overlay": "None"}


@dataclass
class Texts:
    """What an Up Next design writes. ``percent`` is how full the bar is."""

    up_next: str = "Up next"
    episode: str = "S1 E3"
    mins: str = "49 min"
    title: str = "Fate"
    plot: str = ("The organizers bet on which contestant will reach the next checkpoint first. Shujiro shares his past "
                 "with Futaba, then reunites with his estranged sister.")
    countdown: str = "0:20"
    seconds: str = "20"
    play: str = "Play now"
    close: str = "Cancel"
    starts: str = "Next episode starts in"
    starts_short: str = "Starts in"
    up_in: str = "Up next in"
    next_word: str = "Next"
    ends: str = ""  # "ends 22:41"
    thumb: str = ""
    poster: str = ""
    fanart: str = ""
    logo: str = ""
    show: str = "Last Samurai Standing"
    play_one: str = "Play {ep}"  # the Queue's Play button names the chosen episode
    later: str = "Play a later one"
    credits: str = "Watch credits"
    # the Queue: the next episodes, the first is the one that starts by itself. Each ``(episode, title, minutes, picture)``.
    queue: tuple = (("S1 E3", "Fate", "49 min", ""), ("S1 E4", "The Mastermind", "48 min", ""), ("S1 E5", "Specters", "47 min", ""))
    percent: float = 55.0
    # the engine asks these of any texts: an Up Next design names no segment type
    kicker: str = ""
    skip_word: str = ""
    ending: str = ""


def _c(text, look) -> str:
    return cv._caps(text, look)


def _join(*parts) -> str:
    return " · ".join(str(part) for part in parts if part)


def _fmt(ops, rect, template, texts, size, look, key, **more):
    """A text with the time left in it: ``{cd}`` is the countdown, ``{secs}`` the seconds. The dialog
    writes it again every second from the template."""
    op = {"t": "text", "rect": rect, "text": template.format(cd=texts.countdown, secs=texts.seconds), "size": size,
          "key": key, "fmt": template}
    op.update(more)
    ops.append(op)
    return op


BOTH_GAP = 8.0  # between the poster and the episode picture when both are shown


def _picture(ops, texts, options, rect, shape="r", wide=True):
    """The picture of a design in a slot of the skin file, which cuts its corners. The Picture choice says
    which: the episode picture (else the fanart, else the poster), the poster in its place, or both: the
    poster and the episode picture side by side at one height. Nothing is ever laid over a picture."""
    mode = options.picture
    # what stands in when the episode has no picture of its own
    spare = {"Poster": texts.poster or texts.fanart, "Nothing": ""}.get(options.fallback, texts.fanart or texts.poster)
    episode = texts.thumb or spare
    if mode == "Fanart":
        episode = texts.fanart or episode  # only the Card lays it behind its words; elsewhere it is the picture
    source = (texts.poster or episode) if (mode == "Poster" or not wide) else episode
    x, y, w, h = rect
    if mode == "Both" and texts.poster and source != texts.poster and h >= 100:
        # the poster at the left in its own shape (2:3), the episode picture takes the rest of the place
        poster_w = round(h * 2.0 / 3.0)
        ops.append({"t": "pic", "shape": "ph" if shape == "h" else "p", "rect": (x, y, poster_w, h), "src": texts.poster})
        beside = (x + poster_w + BOTH_GAP, y, w - poster_w - BOTH_GAP, h)
        ops.append({"t": "pic", "shape": shape, "rect": beside, "src": source})
        return beside  # the place of the episode picture: a ring on it is centred there
    ops.append({"t": "pic", "shape": shape, "rect": rect, "src": source})
    return rect


def _play(ops, x, y, w, h, look, texts, options, label=None, time=True, on_plate=True):
    cv._button(ops, "skip", x, y, w, h, look, _c(label or texts.play, look), "cv_ic_play.png", "skip_label", options,
               time=texts.countdown if time and options.time else "", on_plate=on_plate)


def _line_on(options) -> bool:
    """Whether a design draws its line: not when Progress is a circle or a fill (those show on the Play
    button, the card or the picture) and not when it is off."""
    return options.progress not in ("Off", "Circle", "Fill")


def _credits_width(look, texts, options) -> float:
    return (48 + cv.estimate(_c(texts.credits, look), 24, True)) if options.credits else 0.0


def _credits(ops, x, y, h, look, texts, options, on_plate=True):
    """Watch credits: the popup goes, the next episode starts when the credits have run."""
    width = _credits_width(look, texts, options)
    ops.append({"t": "button", "which": "more", "rect": (x, y, width, h), "pill": not on_plate})
    ops.append({"t": "text", "rect": (x, y, width, h), "text": _c(texts.credits, look), "size": 24, "bold": True,
                "align": "c", "ink": "more", "key": "more_label"})
    return width


def _play_width(look, texts, options, label=None, time=False) -> float:
    width = 48 + cv.estimate(_c(label or texts.play, look), 24, True) + (36 if options.icons else 0)
    if time:
        width += cv.estimate(texts.countdown, 24) + 16 + 18
    return width + 6


def _cancel_width(look, texts, options) -> float:
    return 48 + cv.estimate(_c(texts.close, look), 24, True) + (36 if options.icons else 0)


def _cancel(ops, x, y, h, look, texts, options, on_plate=True, ghost=False):
    width = _cancel_width(look, texts, options)
    if ghost:
        ops.append({"t": "button", "which": "close", "rect": (x, y, width, h), "pill": True, "off": "ghost"})
        ops.append({"t": "text", "rect": (x, y, width, h), "text": _c(texts.close, look), "size": 24, "bold": True, "align": "c",
                    "ink": "close", "key": "close_label"})
    else:
        cv._button(ops, "close", x, y, width, h, look, _c(texts.close, look), "cv_ic_close.png", "close_label", options,
                   on_plate=on_plate)
    return width


def _square_close(ops, x, y, size, h, look, options, on_plate=True, ghost=True):
    cv._button(ops, "close", x, y, size, h, look, "", "cv_ic_close.png", "close_label", options, on_plate=on_plate, ghost=ghost)
    for op in ops:
        if op.get("key") == "close_icon":
            op["rect"] = (x + (size - 24) / 2.0, y + (h - 24) / 2.0, 24, 24)
    if not options.icons:  # a square button with nothing on it would be a blank: the cross always shows
        ops.append({"t": "img", "tex": "cv_ic_close.png", "rect": (x + (size - 24) / 2.0, y + (h - 24) / 2.0, 24, 24),
                    "ink": "close", "key": "close_icon"})


def _brow(ops, x, y, width, look, texts, options, time=True, on_plate=True, h=60.0, gap=None):
    """Play now takes what Cancel leaves of a row, and all of it without Cancel."""
    gap = look["gap"] if gap is None else gap
    close_w = _cancel_width(look, texts, options) if options.close else 0.0
    more_w = _credits_width(look, texts, options)
    play_w = width - (close_w + gap if options.close else 0) - (more_w + gap if more_w else 0)
    _play(ops, x, y, play_w, h, look, texts, options, time=time, on_plate=on_plate)
    if more_w:
        _credits(ops, x + play_w + gap, y, h, look, texts, options, on_plate=on_plate)
    if options.close:
        _cancel(ops, x + width - close_w, y, h, look, texts, options, on_plate=on_plate)


def _mid_ring(ops, x, y, w, h, size, texts, options, inner, font):
    """The countdown as a ring in the middle of a picture: a dark disc, the ring, the time in it."""
    cx, cy = x + (w - size) / 2.0, y + (h - size) / 2.0
    disc = round(size * 0.86)
    ops.append({"t": "img", "tex": "cv_dot.png", "rect": (x + (w - disc) / 2.0, y + (h - disc) / 2.0, disc, disc),
                "color": (0, 0, 0, 140)})
    if options.progress != "Off":
        cv._ring(ops, {"track": looks.white(.35)}, cx, cy, size, texts.percent, looks.white(1))
    if inner == "icon":
        ops.append({"t": "img", "tex": "cv_ic_play.png", "rect": (x + (w - 30) / 2.0, y + (h - 30) / 2.0, 30, 30),
                    "color": looks.white(1)})
    else:
        _fmt(ops, (cx, cy, size, size), inner, texts, font, None, "ring_time", bold=True, align="c", color=looks.white(1))


# --- A · Card -----------------------------------------------------------------------------------
def card_full(look, texts, options) -> cv.Drawing:
    """A · Card, Full: the picture, the episode, its title and plot in one card, the bar under them,
    Play now and Cancel."""
    ops = []
    width, pad, tp = 780.0, look["pad"], look["tp"]
    acc = options.accent or look["acc"]
    behind = options.picture == "Fanart" and bool(texts.fanart or texts.thumb)
    shown = options.picture != "Off" and not behind
    top_h = 180.0
    x = tp
    picture = None  # the place of the episode picture, for a fill that shows on it
    if shown and options.picture == "Poster" and texts.poster:
        # the poster instead: a narrow picture, and more room for the words
        ops.append({"t": "pic", "shape": "p", "rect": (pad, pad, 120.0, top_h), "src": texts.poster})
        x = pad + 120 + 6 + 16
    elif shown and options.picture == "Both" and texts.poster:
        # both, side by side at one height: the card grows by the poster, the words keep their room
        both_w = 120.0 + BOTH_GAP + 320.0
        width += 120.0 + BOTH_GAP
        picture = _picture(ops, texts, options, (pad, pad, both_w, top_h))
        x = pad + both_w + 6 + 16
    elif shown:
        picture = _picture(ops, texts, options, (pad, pad, 320.0, top_h))
        x = pad + 320 + 6 + 16
    rows = 20 + 9 + 36 + ((9 + 54) if options.plot and texts.plot else 0)
    if not shown:
        top_h = rows + 2 * (tp - 4) - 2 * pad + 2 * pad
    y = pad + (top_h - rows) / 2.0 if shown else tp - 4
    text_w = width - x - tp
    if options.kicker:
        ops.append({"t": "img", "tex": "cv_dot.png", "rect": (x, y + 5, 10, 10), "color": acc})
        ops.append({"t": "text", "rect": (x + 19, y, 240, 20), "text": texts.up_next.upper(), "size": 16, "bold": True,
                    "color": look["ink2"]})
        ops.append({"t": "text", "rect": (x + text_w - 300, y, 300, 20), "text": _join(texts.episode, texts.mins).upper(),
                    "size": 16, "align": "r", "color": look["ink3"]})
    y += 20 + 9
    ops.append({"t": "text", "rect": (x, y, text_w, 36), "text": _c(texts.title, look), "size": 32, "bold": True,
                "color": look["ink"], "key": "title"})
    y += 36 + 9
    if options.plot and texts.plot:
        ops.append({"t": "para", "rect": (x, y, text_w, 54), "lines": 2, "text": texts.plot, "size": 19, "color": look["ink2"]})
    y = (pad + top_h if shown else tp - 4 + rows + tp - 4) + pad
    if _line_on(options):
        cv._line(ops, (pad + pad / 3.0, y, width - 2 * (pad + pad / 3.0), 6.0), look, acc, texts.percent)
        y += 6
    y += pad
    _brow(ops, pad, y, width - 2 * pad, look, texts, options)
    y += 60 + pad
    under = []
    if behind:
        # the show's fanart behind the words: no picture of its own, the card as it is without one
        under.append({"t": "pic", "shape": "card", "rect": (0, 0, width, y), "src": texts.fanart or texts.thumb})
    if options.progress == "Fill" and options.fill_on == "Card":
        # the card itself fills from the left
        under.append({"t": "fillslot", "slot": "fill_c", "rect": (0, 0, width * texts.percent / 100.0, y),
                      "color": looks.with_alpha(look["ink"], 0.10), "key": "fill", "track": (0, 0, width, y), "min": 90.0})
    elif options.progress == "Fill" and options.fill_on == "Picture" and picture:
        # the picture comes out from under a veil as the time runs
        px, py, pw, ph = picture
        ops.append({"t": "rect", "rect": (px + pw * texts.percent / 100.0, py, pw * (1 - texts.percent / 100.0), ph),
                    "color": (0, 0, 0, 150), "key": "fill", "track": picture, "reveal": True})
    ops[0:0] = [{"t": "slot", "slot": "plate", "rect": (0, 0, width, y)}] + under
    return cv.Drawing(width, y, ops=ops)


def card_compact(look, texts, options) -> cv.Drawing:
    """A · Card, Compact: one row. The picture, the episode over the time left, Play now, a small Cancel."""
    ops = []
    pad, bh = look["pad"], 60.0
    x = pad
    if options.picture != "Off":
        _picture(ops, texts, options, (x, pad, 107.0, bh), shape="s")
        x += 107 + 16
    first = _c(_join(texts.episode, texts.title), look)
    text_w = max(190.0, cv.estimate(first, 22, True) + 8, cv.estimate("%s %s" % (texts.starts_short, texts.countdown), 17) + 8)
    ops.append({"t": "text", "rect": (x, pad + 5, text_w, 26), "text": first, "size": 22, "bold": True, "color": look["ink"],
                "key": "title"})
    _fmt(ops, (x, pad + 34, text_w, 22), _c(texts.starts_short, look) + " [B]{cd}[/B]", texts, 17, look, "starts_line",
         color=look["ink2"])
    x += text_w + 16
    play_w = _play_width(look, texts, options)
    _play(ops, x, pad, play_w, bh, look, texts, options, time=False, on_plate=False)
    x += play_w
    if options.close:
        x += 16
        _square_close(ops, x, pad, 60.0, bh, look, options, on_plate=False)
        x += 60
    width, height = x + pad + 6, bh + 2 * pad
    ops.insert(0, {"t": "slot", "slot": "plate_c" if look["rb"] > 100 else "plate", "rect": (0, 0, width, height)})
    return cv.Drawing(width, height, ops=ops)


def card_minimal(look, texts, options) -> cv.Drawing:
    """A · Card, Minimal: one button, "Next: <title>" and the time left, the bar along its foot."""
    ops = []
    pad, bh = min(look["pad"], 6), 60.0
    label = "%s: %s" % (texts.next_word, texts.title)
    width = _play_width(look, texts, options, label, time=True)
    _play(ops, pad, pad, width, bh, look, texts, options, label=label, on_plate=False)
    if _line_on(options):
        inset = 24.0 if look["rb"] > 100 else max(4.0, look["ri"] * 0.6)
        track = (pad + inset, pad + bh - 5, width - 2 * inset, 5.0)
        ops.append({"t": "rect", "rect": (track[0], track[1], track[2] * texts.percent / 100.0, track[3]),
                    "color": look["foc_acc"], "key": "fill", "track": track})
    total_w, total_h = width + 2 * pad, bh + 2 * pad
    ops.insert(0, {"t": "slot", "slot": "plate_m" if look["rb"] > 100 else "plate", "rect": (0, 0, total_w, total_h)})
    return cv.Drawing(total_w, total_h, ops=ops)


# --- B · Poster slab ----------------------------------------------------------------------------
def _on_picture(ops, texts, look, x, bottom, width, title_size=40):
    """The episode line and the title set on the foot of a picture, over a dark fade."""
    title_h = title_size + 5
    ops.append({"t": "text", "rect": (x, bottom - 18 - title_h - 6 - 20, width, 20), "size": 16, "bold": True,
                "text": _join(texts.up_next, texts.episode, texts.mins).upper(), "color": looks.white(1)})
    ops.append({"t": "text", "rect": (x, bottom - 18 - title_h, width, title_h), "size": title_size, "bold": True,
                "text": _c(texts.title, look), "color": looks.white(1), "key": "title"})


def slab_full(look, texts, options) -> cv.Drawing:
    """B · Poster slab, Full: a square slab out of the screen corner, the picture full width with the
    title set on it, the bar along the top edge, the buttons edge to edge."""
    ops = []
    width, pic_h = 680.0, 382.0
    acc = options.accent or look["acc"]
    y = 0.0
    if _line_on(options):
        cv._line(ops, (0.0, 0.0, width, 6.0), look, acc, texts.percent)
    y = 6.0
    if options.picture != "Off":
        _picture(ops, texts, options, (0, y, width, pic_h), shape="h")
        ops.append({"t": "img", "tex": "cv_ov_band.png", "rect": (0, y + pic_h * 0.4, width, pic_h * 0.6), "color": (0, 0, 0, 217)})
        _on_picture(ops, texts, look, 22.0, y + pic_h, width - 44)
        y += pic_h
    else:
        ops.append({"t": "text", "rect": (26, y + 22, width - 52, 20), "size": 16, "bold": True, "color": look["ink2"],
                    "text": _join(texts.up_next, texts.episode, texts.mins).upper()})
        ops.append({"t": "text", "rect": (26, y + 48, width - 52, 45), "size": 40, "bold": True, "color": look["ink"],
                    "text": _c(texts.title, look), "key": "title"})
        y += 100
    ops.append({"t": "text", "rect": (26, y, width - 180, 66), "size": 20, "color": look["ink2"], "text": _c(texts.starts, look)})
    ops.append({"t": "text", "rect": (width - 26 - 150, y, 150, 66), "size": 26, "bold": True, "align": "r",
                "color": look["ink"], "text": texts.countdown, "key": "countdown"})
    y += 66
    _brow(ops, 0, y, width, look, texts, options, time=False, h=68.0, gap=0.0)
    y += 68
    ops.insert(0, {"t": "slot", "slot": "plate", "rect": (0, 0, width, y)})
    return cv.Drawing(width, y, ops=ops)


def slab_compact(look, texts, options) -> cv.Drawing:
    """B · Poster slab, Compact: the picture, "Up next in" over the episode, Play now and a square Cancel."""
    ops = []
    height = 110.0
    acc = options.accent or look["acc"]
    x = 0.0
    if options.picture != "Off":
        _picture(ops, texts, options, (0, 0, 196.0, height), shape="h")
        x = 196.0
    second = _c(_join(texts.episode, texts.title), look)
    text_w = max(cv.estimate(second, 24, True), cv.estimate("%s 0:00" % texts.up_in.upper(), 16, True)) + 8
    _fmt(ops, (x + 26, 30, text_w, 20), texts.up_in.upper() + " {cd}", texts, 16, look, "up_in", bold=True, color=look["ink2"])
    ops.append({"t": "text", "rect": (x + 26, 55, text_w, 30), "text": second, "size": 24, "bold": True, "color": look["ink"],
                "key": "title"})
    x += 26 + text_w + 26
    play_w = _play_width(look, texts, options)
    _play(ops, x, 0, play_w, height, look, texts, options, time=False)
    x += play_w
    if options.close:
        _square_close(ops, x, 0, 60.0, height, look, options, ghost=False)
        x += 60
    if _line_on(options):
        cv._line(ops, (0.0, 0.0, x, 6.0), look, acc, texts.percent)
    ops.insert(0, {"t": "slot", "slot": "plate", "rect": (0, 0, x, height)})
    return cv.Drawing(x, height, ops=ops)


def slab_minimal(look, texts, options) -> cv.Drawing:
    """B · Poster slab, Minimal: the picture, the time left and a square Play button on the screen edge."""
    ops = []
    height = 90.0
    acc = options.accent or look["acc"]
    x = 0.0
    if options.picture != "Off":
        _picture(ops, texts, options, (0, 0, 160.0, height), shape="h")
        x = 160.0
    count_w = cv.estimate("0:00", 28, True) + 44
    ops.append({"t": "text", "rect": (x, 0, count_w, height), "text": texts.countdown, "size": 28, "bold": True, "align": "c",
                "color": look["ink"], "key": "countdown"})
    x += count_w
    ops.append({"t": "button", "which": "skip", "rect": (x, 0, 90.0, height)})
    ops.append({"t": "img", "tex": "cv_ic_play.png", "rect": (x + 33, 33, 24, 24), "ink": "skip", "key": "skip_icon"})
    x += 90
    if options.progress != "Off":
        cv._line(ops, (0.0, 0.0, x, 6.0), look, acc, texts.percent)
    ops.insert(0, {"t": "slot", "slot": "plate", "rect": (0, 0, x, height)})
    return cv.Drawing(x, height, ops=ops, lift=120.0)


# --- C · Play ring ------------------------------------------------------------------------------
def ring_full(look, texts, options) -> cv.Drawing:
    """C · Play ring, Full: the countdown is a ring on the picture itself. No card: a soft rounded
    shade lies behind."""
    ops = []
    width, pic_h = 580.0, 326.0
    y = 0.0
    if options.picture != "Off":
        px, py, pw, ph = _picture(ops, texts, options, (0, 0, width, pic_h))
        _mid_ring(ops, px, py, pw, ph, 150.0, texts, options, "{cd}", 36)
        y = pic_h + 18
    ops.append({"t": "text", "rect": (0, y, width, 20), "size": 16, "bold": True, "color": look["ink2"], "shadow": True,
                "text": _join(texts.up_next, texts.episode, texts.mins).upper()})
    y += 20 + 8
    ops.append({"t": "text", "rect": (0, y, width, 36), "size": 32, "bold": True, "color": look["ink"], "shadow": True,
                "text": _c(texts.title, look), "key": "title"})
    y += 36 + 18
    _brow(ops, 0, y, width, look, texts, options, time=options.picture == "Off", on_plate=False)
    return cv.Drawing(width, y + 60.0, ops=ops, shade=30.0)


def ring_compact(look, texts, options) -> cv.Drawing:
    """C · Play ring, Compact: a small picture with the ring, the episode beside it, Play now."""
    ops = []
    height = 112.0
    x = 0.0
    if options.picture != "Off":
        px, py, pw, ph = _picture(ops, texts, options, (0, 0, 200.0, height))
        _mid_ring(ops, px, py, pw, ph, 70.0, texts, options, "{secs}", 22)
        x = 220.0
    second = _c(_join(texts.episode, texts.title), look)
    text_w = max(cv.estimate(second, 24, True), cv.estimate("%s 0:00" % texts.up_in.upper(), 16, True)) + 8
    _fmt(ops, (x, 30, text_w, 20), texts.up_in.upper() + " {cd}", texts, 16, look, "up_in", bold=True, color=look["ink2"],
         shadow=True)
    ops.append({"t": "text", "rect": (x, 56, text_w, 30), "text": second, "size": 24, "bold": True, "color": look["ink"],
                "shadow": True, "key": "title"})
    x += text_w + 20
    play_w = _play_width(look, texts, options)
    _play(ops, x, (height - 60) / 2.0, play_w, 60.0, look, texts, options, time=False, on_plate=False)
    return cv.Drawing(x + play_w, height, ops=ops, shade=22.0)


def ring_minimal(look, texts, options) -> cv.Drawing:
    """C · Play ring, Minimal: "Next: <title>" and a round Play button with the ring around it."""
    ops = []
    size = 96.0
    acc = options.accent or look["acc"]
    label = _c("%s: %s" % (texts.next_word, texts.title), look)
    label_w = cv.estimate(label, 24, True) + 8
    ops.append({"t": "text", "rect": (0, 0, label_w, size), "text": label, "size": 24, "bold": True, "color": look["ink"],
                "shadow": True})
    x = label_w + 14
    if options.progress != "Off":
        cv._ring(ops, look, x, 0, size, texts.percent, acc)
    ops.append({"t": "button", "which": "skip", "rect": (x + 11, 11, size - 22, size - 22), "pill": True, "ghost": True,
                "bare": True})
    ops.append({"t": "img", "tex": "cv_dot.png", "rect": (x + 11, 11, size - 22, size - 22), "color": look["foc"],
                "key": "skip_disc"})
    ops.append({"t": "img", "tex": "cv_ic_play.png", "rect": (x + 31, 31, 34, 34), "ink": "skip", "key": "skip_icon"})
    return cv.Drawing(x + size, size, ops=ops, shade=18.0)


# --- D · Lower third ----------------------------------------------------------------------------
BAND_W = 1920.0 - 2 * 64.0


def band_full(look, texts, options) -> cv.Drawing:
    """D · Lower third, Full: across the whole picture. Picture and plot at the left, the buttons at
    the right, one long bar under all of it."""
    ops = []
    acc = options.accent or look["acc"]
    width, pic_h = BAND_W, 180.0
    x = 0.0
    if options.picture != "Off":
        _picture(ops, texts, options, (0, 0, 320.0, pic_h))
        x = 350.0
    rows = 20 + 9 + 45 + ((9 + 54) if options.plot and texts.plot else 0)
    y = pic_h - 4 - rows
    ops.append({"t": "img", "tex": "cv_dot.png", "rect": (x, y + 5, 10, 10), "color": acc})
    ops.append({"t": "text", "rect": (x + 19, y, 700, 20), "size": 16, "bold": True, "color": look["ink2"], "shadow": True,
                "text": _join(texts.up_next, texts.episode, texts.mins).upper()})
    y += 29
    ops.append({"t": "text", "rect": (x, y, 900, 45), "size": 40, "bold": True, "color": look["ink"], "shadow": True,
                "text": _c(texts.title, look), "key": "title"})
    y += 54
    if options.plot and texts.plot:
        ops.append({"t": "para", "rect": (x, y, 780, 54), "lines": 2, "text": texts.plot, "size": 19, "color": look["ink2"]})
    close_w = _cancel_width(look, texts, options) if options.close else 0.0
    play_w = _play_width(look, texts, options, time=True)
    bx = width - play_w - (close_w + look["gap"] if options.close else 0)
    _play(ops, bx, pic_h - 60, play_w, 60.0, look, texts, options, on_plate=False)
    if options.close:
        _cancel(ops, width - close_w, pic_h - 60, 60.0, look, texts, options, on_plate=False)
    height = pic_h
    if _line_on(options):
        cv._line(ops, (0.0, pic_h + 22, width, 5.0), look, acc, texts.percent)
        height += 27
    return cv.Drawing(width, height, ops=ops, shade=440.0)


def band_compact(look, texts, options) -> cv.Drawing:
    """D · Lower third, Compact: a small picture, the episode over the time left, Play now, a square Cancel."""
    ops = []
    acc = options.accent or look["acc"]
    width, pic_h = BAND_W, 90.0
    x = 0.0
    if options.picture != "Off":
        _picture(ops, texts, options, (0, 0, 160.0, pic_h))
        x = 190.0
    ops.append({"t": "text", "rect": (x, 12, 900, 36), "size": 32, "bold": True, "color": look["ink"], "shadow": True,
                "text": _c(_join(texts.episode, texts.title), look), "key": "title"})
    _fmt(ops, (x, 53, 900, 26), _c(texts.starts, look) + " {cd}", texts, 20, look, "starts_line", color=look["ink2"], shadow=True)
    play_w = _play_width(look, texts, options)
    bx = width - play_w - (60 + look["gap"] if options.close else 0)
    _play(ops, bx, 15, play_w, 60.0, look, texts, options, time=False, on_plate=False)
    if options.close:
        _square_close(ops, width - 60, 15, 60.0, 60.0, look, options, on_plate=False, ghost=False)
    height = pic_h
    if _line_on(options):
        cv._line(ops, (0.0, pic_h + 22, width, 5.0), look, acc, texts.percent)
        height += 27
    return cv.Drawing(width, height, ops=ops, shade=250.0)


def band_minimal(look, texts, options) -> cv.Drawing:
    """D · Lower third, Minimal: one button at the right, the bar across the picture under it."""
    ops = []
    acc = options.accent or look["acc"]
    width = BAND_W
    label = "%s: %s" % (texts.next_word, texts.title)
    play_w = _play_width(look, texts, options, label, time=True)
    _play(ops, width - play_w, 0, play_w, 60.0, look, texts, options, label=label, on_plate=False)
    height = 60.0
    if _line_on(options):
        cv._line(ops, (0.0, 60.0 + 16, width, 6.0), {"track": looks.white(.2)}, acc, texts.percent)
        height += 22
    return cv.Drawing(width, height, ops=ops, shade=170.0, drop=14.0)


# --- E · Float ----------------------------------------------------------------------------------
def float_full(look, texts, options) -> cv.Drawing:
    """E · Float, Full: no box and no shade. Light type and a small picture straight on the video."""
    ops = []
    shown = options.picture != "Off"
    lead, title = _c(texts.episode, look), _c(texts.title, look)
    head_w = cv.estimate(lead, 54) + cv.estimate(title, 54, True) + 30
    sub = _join(texts.mins, texts.ends)
    pic_w = 240.0 if shown else 0.0
    width = max(620.0, head_w + (24 + pic_w if shown else 0))
    y = 0.0
    _fmt(ops, (0, y, width, 20), texts.up_in.upper() + " {cd}", texts, 16, look, "up_in", bold=True, align="r",
         color=look["ink2"], shadow=True)
    y += 20 + 12
    right = width - (pic_w + 24 if shown else 0)
    if shown:
        _picture(ops, texts, options, (width - pic_w, y, pic_w, 135.0))
    block = 62 + (8 + 24 if sub else 0)
    ty = y + 135 - block if shown else y
    # the title is bold and stands at the right end; the episode, light, ends where it starts
    title_w = cv.estimate(title, 54, True) + 14
    ops.append({"t": "text", "rect": (0, ty, right - title_w - 18, 62), "size": 54, "align": "r", "color": look["ink"],
                "text": lead, "shadow": True})
    ops.append({"t": "text", "rect": (right - title_w, ty, title_w + 10, 62), "size": 54, "bold": True, "color": look["ink"],
                "text": title, "shadow": True, "key": "title"})
    if sub:
        ops.append({"t": "text", "rect": (0, ty + 70, right, 24), "size": 20, "align": "r", "color": look["ink2"],
                    "text": _c(sub, look), "shadow": True})
    y += (135 if shown else block) + 12 + 10
    label = _c(texts.play, look)
    play_w = cv._ring_button_width(label, options)
    cv._ring_button(ops, "skip", width - play_w, y, play_w, 60.0, look, label, options, texts.percent)
    if options.close:
        close_w = _cancel_width(look, texts, cv.dataclasses.replace(options, icons=False))
        _cancel(ops, width - play_w - look["gap"] - close_w, y, 60.0, look, texts, cv.dataclasses.replace(options, icons=False),
                ghost=True)
    return cv.Drawing(width, y + 60.0, ops=ops)


def float_compact(look, texts, options) -> cv.Drawing:
    """E · Float, Compact: "Up next in" over the title, right-aligned, and Play now with its ring."""
    ops = []
    title = _c(texts.title, look)
    text_w = max(cv.estimate(title, 32, True), cv.estimate("%s 0:00" % texts.up_in.upper(), 16, True)) + 12
    _fmt(ops, (0, 0, text_w, 20), texts.up_in.upper() + " {cd}", texts, 16, look, "up_in", bold=True, align="r",
         color=look["ink2"], shadow=True)
    ops.append({"t": "text", "rect": (0, 24, text_w, 36), "size": 32, "bold": True, "align": "r", "color": look["ink"],
                "text": title, "shadow": True, "key": "title"})
    label = _c(texts.play, look)
    play_w = cv._ring_button_width(label, options)
    cv._ring_button(ops, "skip", text_w + 22, 0, play_w, 60.0, look, label, options, texts.percent)
    return cv.Drawing(text_w + 22 + play_w, 60.0, ops=ops)


def float_minimal(look, texts, options) -> cv.Drawing:
    """E · Float, Minimal: the words alone, in capitals, underlined by the bar."""
    ops = []
    acc = options.accent or look["acc"]
    template = ("%s: %s" % (texts.next_word, texts.title)).upper() + " · {cd}"
    text_w = cv.estimate(template.format(cd="0:00"), 28, True) * 1.14 + 4
    x = 38.0 if options.icons else 0.0
    ops.append({"t": "button", "which": "skip", "rect": (0, 0, text_w + x, 52), "bare": True})
    if options.icons:
        ops.append({"t": "img", "tex": "cv_ic_play.png", "rect": (0, 5, 26, 26), "color": look["ink"], "shadow": True})
    _fmt(ops, (x, 0, text_w, 36), template, texts, 28, look, "lk", bold=True, color=look["ink"], shadow=True)
    width = x + text_w
    if options.progress != "Off":
        track = (0.0, 48.0, width, 4.0)
        ops.append({"t": "rect", "rect": track, "color": looks.white(.3)})
        ops.append({"t": "rect", "rect": (0.0, 48.0, width * texts.percent / 100.0, 4.0), "color": acc, "key": "fill",
                    "track": track})
    return cv.Drawing(width, 52.0, ops=ops)


# --- F · Takeover -------------------------------------------------------------------------------
def take_full(look, texts, options) -> cv.Drawing:
    """F · Takeover, Full: the next episode takes the screen. Its picture behind a shade, the show's
    logo, the title large, the plot, Play now with the time left and Cancel."""
    ops = []
    width, height = cv.SCREEN_W, cv.SCREEN_H
    ops.append({"t": "pic", "shape": "back", "rect": (0, 0, width, height), "src": texts.fanart or texts.thumb or texts.poster})
    x, body_w = 96.0, 820.0
    y = height - 96 - 60
    play_w = _play_width(look, texts, options, time=True) + 30
    _play(ops, x, y, play_w, 60.0, look, texts, options, on_plate=False)
    if _line_on(options):
        track = (x + 24, y + 55, play_w - 48, 5.0)
        ops.append({"t": "rect", "rect": (track[0], track[1], track[2] * texts.percent / 100.0, track[3]),
                    "color": look["foc_acc"], "key": "fill", "track": track})
    bx = x + play_w + look["gap"]
    if options.credits:
        bx += _credits(ops, bx, y, 60.0, look, texts, options, on_plate=False) + look["gap"]
    if options.close:
        _cancel(ops, bx, y, 60.0, look, texts, options, on_plate=False)
    # (No small window with what is playing: under a dialog Kodi keeps the video at full size, so such a
    # window only shows the piece of the picture that lies behind it. Tried in 8.31.0, taken out again.)
    y -= 12 + 16
    if options.plot and texts.plot:
        y -= 102
        ops.append({"t": "para", "rect": (x, y, 720, 102), "lines": 3, "text": texts.plot, "size": 24, "color": looks.white(.78)})
        y -= 16
    y -= 90
    ops.append({"t": "text", "rect": (x, y, 1500, 90), "size": 84, "bold": True, "color": looks.white(1), "shadow": True,
                "text": _c(texts.title, look), "key": "title"})
    y -= 16 + 20
    ops.append({"t": "text", "rect": (x, y, body_w, 20), "size": 16, "bold": True, "color": looks.white(.78), "shadow": True,
                "text": _join(texts.up_next, texts.episode, texts.mins).upper()})
    if texts.logo:
        ops.append({"t": "pic", "shape": "logo", "rect": (x, y - 30 - 150, 380.0, 150.0), "src": texts.logo})
    return cv.Drawing(width, height, ops=ops)


def take_compact(look, texts, options) -> cv.Drawing:
    """F · Takeover, Compact: a panel out of the screen corner. The picture with the logo on it, the
    episode and its title, Play now and Cancel."""
    ops = []
    width, pic_h, pad = 660.0, 300.0, look["pad"]
    y = 0.0
    if options.picture != "Off":
        _picture(ops, texts, options, (0, 0, width, pic_h), shape="h")
        ops.append({"t": "img", "tex": "cv_ov_band.png", "rect": (0, pic_h * 0.4, width, pic_h * 0.6), "color": (0, 0, 0, 217)})
        if texts.logo:
            ops.append({"t": "pic", "shape": "logo", "rect": (22, pic_h - 18 - 92, 230.0, 92.0), "src": texts.logo})
        y = pic_h
    y += 22
    _fmt(ops, (26, y, 320, 20), texts.up_in.upper() + " {cd}", texts, 16, look, "up_in", bold=True, color=look["ink2"])
    ops.append({"t": "text", "rect": (width - 26 - 300, y, 300, 20), "size": 16, "align": "r", "color": look["ink3"],
                "text": _join(texts.episode, texts.mins).upper()})
    y += 28
    ops.append({"t": "text", "rect": (26, y, width - 52, 36), "size": 32, "bold": True, "color": look["ink"],
                "text": _c(texts.title, look), "key": "title"})
    y += 36 + 18
    _brow(ops, pad, y, width - 2 * pad, look, texts, options, time=False)
    y += 60 + pad
    ops.insert(0, {"t": "slot", "slot": "plate", "rect": (0, 0, width, y)})
    return cv.Drawing(width, y, ops=ops)


def take_minimal(look, texts, options) -> cv.Drawing:
    """F · Takeover, Minimal: the picture in the corner with a Play ring on it, the title and the time under it."""
    ops = []
    width, pic_h = 300.0, 169.0
    px, py, pw, ph = _picture(ops, texts, options, (0, 0, width, pic_h))
    ops.append({"t": "button", "which": "skip", "rect": (0, 0, width, pic_h), "bare": True})
    _mid_ring(ops, px, py, pw, ph, 84.0, texts, options, "icon", 20)
    template = _c("%s: %s" % (texts.next_word, texts.title), look) + " · {cd}"
    _fmt(ops, (-300, pic_h + 10, width + 300, 28), template, texts, 22, look, "lk", bold=True, align="r", color=looks.white(1),
         shadow=True)
    return cv.Drawing(width, pic_h + 38, ops=ops)


# --- G · Queue ----------------------------------------------------------------------------------
QUEUE_SHAPES = ("r", "r2", "r3")


def _cards(ops, look, texts, x, y, w, h, gap, full):
    """The episodes of the Queue side by side: each a picture that takes the focus, its lines under it.
    A frame in the accent stands around the chosen one; a veil dims the others."""
    plate = look.get("plate") or (20, 23, 28, 245)
    for index, (code, title, mins, source) in enumerate(texts.queue[:3]):
        cx = x + index * (w + gap)
        ops.append({"t": "pic", "shape": QUEUE_SHAPES[index], "rect": (cx, y, w, h), "src": source or texts.thumb})
        first = _join(code, mins).upper() if full else str(code).upper()
        ops.append({"t": "text", "rect": (cx, y + h + 10, w, 18), "size": 15, "bold": True, "color": look["ink2"], "text": first})
        if full:
            ops.append({"t": "text", "rect": (cx, y + h + 32, w, 28), "size": 22, "bold": True, "color": look["ink"],
                        "text": _c(title, look)})
        ops.append({"t": "img", "tex": "sl_white.png", "rect": (cx, y, w, h + (60 if full else 28)),
                    "color": plate[:3] + (97,), "key": "veil%d" % index})
        ops.append({"t": "hot", "name": "q%d" % (index + 1), "rect": (cx, y, w, h + (60 if full else 28)), "ratio": h / w})
    return len(texts.queue[:3])


def queue_full(look, texts, options) -> cv.Drawing:
    """G · Queue, Full: the next three episodes side by side. Left and Right pick another one before it starts."""
    ops = []
    tp, pad, gap = look["tp"], look["pad"], 14.0
    acc = options.accent or look["acc"]
    count = max(1, len(texts.queue[:3]))
    width = 2 * tp + count * 320 + (count - 1) * gap
    y = tp
    ops.append({"t": "img", "tex": "cv_dot.png", "rect": (tp, y + 7, 10, 10), "color": acc})
    ops.append({"t": "text", "rect": (tp + 19, y, width / 2.0, 24), "size": 16, "bold": True, "color": look["ink2"],
                "text": _join(texts.up_next, texts.show).upper()})
    _fmt(ops, (width / 2.0, y, width / 2.0 - tp, 24), _c(texts.starts, look) + " [B]{cd}[/B]", texts, 20, look, "starts_line",
         align="r", color=look["ink2"])
    y += 24 + 6 + 10
    _cards(ops, look, texts, tp, y, 320.0, 180.0, gap, True)
    ops.append({"t": "slot", "slot": "outline", "tex": "frame", "rect": (tp - 6, y - 6, 332, 192), "color": acc})
    y += 180 + 60 + tp
    if _line_on(options):
        cv._line(ops, (tp, y, width - 2 * tp, 6.0), look, acc, texts.percent)
        y += 6 + tp
    close_w = _cancel_width(look, texts, options) if options.close else 0.0
    later = _c(texts.later, look)
    later_w = (48 + cv.estimate(later, 24, True)) if count > 1 else 0.0
    play_w = width - 2 * pad - (close_w + look["gap"] if close_w else 0) - (later_w + look["gap"] if later_w else 0)
    _play(ops, pad, y, play_w, 60.0, look, texts, options, label=texts.play_one.format(ep=texts.queue[0][0] if texts.queue else ""))
    x = pad + play_w + look["gap"]
    if later_w:
        ops.append({"t": "button", "which": "more", "rect": (x, y, later_w, 60.0)})
        ops.append({"t": "text", "rect": (x, y, later_w, 60.0), "text": later, "size": 24, "bold": True, "align": "c",
                    "ink": "more", "key": "more_label"})
        x += later_w + look["gap"]
    if options.close:
        _cancel(ops, x, y, 60.0, look, texts, options)
    y += 60 + pad
    ops.insert(0, {"t": "slot", "slot": "plate", "rect": (0, 0, width, y)})
    return cv.Drawing(width, y, ops=ops)


def queue_compact(look, texts, options) -> cv.Drawing:
    """G · Queue, Compact: three small cards, and beside them when the first starts and Play now."""
    ops = []
    tp = look["tp"]
    acc = options.accent or look["acc"]
    count = max(1, len(texts.queue[:3]))
    _cards(ops, look, texts, tp, tp, 176.0, 99.0, 12.0, False)
    ops.append({"t": "slot", "slot": "outline", "tex": "frame", "rect": (tp - 6, tp - 6, 188, 111), "color": acc})
    x = tp + count * 176 + (count - 1) * 12 + 12 + 8
    template = "%s · %s [B]{cd}[/B]" % (_c(texts.title, look), _c(texts.starts_short, look))
    play_w = _play_width(look, texts, options)
    side_w = max(play_w, cv.estimate(template.replace("[B]", "").replace("[/B]", "").format(cd="0:00"), 20) + 8)
    _fmt(ops, (x, tp + 14, side_w, 26), template, texts, 20, look, "starts_line", color=look["ink2"])
    _play(ops, x, tp + 14 + 26 + 10, play_w, 60.0, look, texts, options, time=False)
    width, height = x + side_w + tp, 2 * tp + 99 + 28
    ops.insert(0, {"t": "slot", "slot": "plate", "rect": (0, 0, width, height)})
    return cv.Drawing(width, height, ops=ops)


def queue_minimal(look, texts, options) -> cv.Drawing:
    """G · Queue, Minimal: one pill. The picture, the title over when it starts and how many follow, a round Play."""
    ops = []
    pad, bh = min(look["pad"], 6), 60.0
    x = pad
    if options.picture != "Off":
        _picture(ops, texts, options, (x, pad, 107.0, bh), shape="s")
        x += 107 + 14
    more = len(texts.queue[:3]) - 1
    template = _c(texts.starts_short, look) + " {cd}" + (" · +%d" % more if more > 0 else "")
    title = _c(texts.title, look)
    text_w = max(cv.estimate(title, 22, True), cv.estimate(template.format(cd="0:00"), 16)) + 10
    ops.append({"t": "text", "rect": (x, pad + 4, text_w, 28), "text": title, "size": 22, "bold": True, "color": look["ink"],
                "key": "title"})
    _fmt(ops, (x, pad + 33, text_w, 22), template, texts, 16, look, "starts_line", color=look["ink2"])
    x += text_w + 14
    ops.append({"t": "button", "which": "skip", "rect": (x, pad, 60.0, bh), "pill": True})
    ops.append({"t": "img", "tex": "cv_ic_play.png", "rect": (x + 18, pad + 18, 24, 24), "ink": "skip", "key": "skip_icon"})
    width, height = x + 60 + pad, bh + 2 * pad
    ops.insert(0, {"t": "slot", "slot": "plate_m" if look["rb"] > 100 else "plate", "rect": (0, 0, width, height)})
    return cv.Drawing(width, height, ops=ops)


# --- H · Side rail ------------------------------------------------------------------------------
def rail_full(look, texts, options) -> cv.Drawing:
    """H · Side rail, Full: a tab on the screen edge. The picture on top, the episode, its title and
    plot, the countdown as a ring, the buttons stacked."""
    ops = []
    width, pad = 420.0, look["pad"]
    acc = options.accent or look["acc"]
    y = 0.0
    if options.picture != "Off":
        _picture(ops, texts, options, (0, 0, width, 236.0), shape="h")
        y = 236.0
    y += 24
    ops.append({"t": "text", "rect": (28, y, width - 56, 20), "size": 16, "bold": True, "color": look["ink2"],
                "text": _join(texts.up_next, texts.episode, texts.mins).upper()})
    y += 32
    ops.append({"t": "text", "rect": (28, y, width - 56, 36), "size": 32, "bold": True, "color": look["ink"],
                "text": _c(texts.title, look), "key": "title"})
    y += 36
    if options.plot and texts.plot:
        y += 12
        ops.append({"t": "para", "rect": (28, y, width - 56, 80), "lines": 3, "text": texts.plot, "size": 19, "color": look["ink2"]})
        y += 80
    y += 18
    x = 28.0
    if options.progress != "Off":
        cv._ring(ops, look, x, y, 72.0, texts.percent, acc)
        _fmt(ops, (x, y, 72, 72), "{secs}", texts, 24, look, "ring_time", bold=True, align="c", color=look["ink"])
        x += 72 + 18
    _fmt(ops, (x, y, width - x - 20, 72), _c(texts.starts, look) + " [B]{cd}[/B]", texts, 19, look, "starts_line",
         color=look["ink2"])
    y += 72 + 24
    cv._centred_button(ops, "skip", pad, y, width - 2 * pad, 60.0, look, _c(texts.play, look), "cv_ic_play.png", "skip_label",
                       options)
    y += 60
    if options.close:
        y += look["gap"]
        cv._centred_button(ops, "close", pad, y, width - 2 * pad, 60.0, look, _c(texts.close, look), "cv_ic_close.png",
                           "close_label", options)
        y += 60
    y += pad
    ops.insert(0, {"t": "slot", "slot": "plate", "rect": (0, 0, width, y)})
    return cv.Drawing(width, y, ops=ops)


def rail_compact(look, texts, options) -> cv.Drawing:
    """H · Side rail, Compact: the picture, "Up next in", the episode, Play now."""
    ops = []
    width, pad = 340.0, look["pad"]
    y = 0.0
    if options.picture != "Off":
        _picture(ops, texts, options, (0, 0, width, 150.0), shape="h")
        y = 150.0
    y += 16
    _fmt(ops, (20, y, width - 40, 20), texts.up_in.upper() + " {cd}", texts, 16, look, "up_in", bold=True, color=look["ink2"])
    y += 26
    ops.append({"t": "text", "rect": (20, y, width - 40, 30), "size": 24, "bold": True, "color": look["ink"],
                "text": _c(_join(texts.episode, texts.title), look), "key": "title"})
    y += 30 + 16
    cv._centred_button(ops, "skip", pad, y, width - 2 * pad, 60.0, look, _c(texts.play, look), "cv_ic_play.png", "skip_label",
                       options)
    y += 60 + pad
    ops.insert(0, {"t": "slot", "slot": "plate", "rect": (0, 0, width, y)})
    return cv.Drawing(width, y, ops=ops, lift=120.0)


def rail_minimal(look, texts, options) -> cv.Drawing:
    """H · Side rail, Minimal: a square Play button on the screen edge, a thin bar rising at its side."""
    ops = []
    pad, size = look["pad"], 112.0
    ops.append({"t": "button", "which": "skip", "rect": (pad, pad, size, size)})
    ops.append({"t": "img", "tex": "cv_ic_play.png", "rect": (pad + 38, pad + 24, 36, 36), "ink": "skip", "key": "skip_icon"})
    ops.append({"t": "text", "rect": (pad, pad + 68, size, 24), "text": _c(texts.next_word, look), "size": 18, "bold": True,
                "align": "c", "ink": "skip", "key": "skip_label"})
    if options.progress != "Off":
        track = (pad, pad, 7.0, size)
        filled = size * texts.percent / 100.0
        ops.append({"t": "rect", "rect": (pad, pad + size - filled, 7.0, filled), "color": look["foc_acc"], "key": "fill",
                    "track": track, "vertical": True})
    total = size + 2 * pad
    ops.insert(0, {"t": "slot", "slot": "plate", "rect": (0, 0, total, total)})
    return cv.Drawing(total, total, ops=ops, lift=120.0)


BUILDERS = {
    "NCard": (card_full, card_compact, card_minimal),
    "NSlab": (slab_full, slab_compact, slab_minimal),
    "NRing": (ring_full, ring_compact, ring_minimal),
    "NBand": (band_full, band_compact, band_minimal),
    "NFloat": (float_full, float_compact, float_minimal),
    "NTake": (take_full, take_compact, take_minimal),
    "NQueue": (queue_full, queue_compact, queue_minimal),
    "NRail": (rail_full, rail_compact, rail_minimal),
}
for _design, _three in BUILDERS.items():
    for _size, _builder in zip(SIZES, _three):
        cv._BUILDERS[(_design, _size)] = _builder


def design_for(layout):
    """The engine's design for a stored popup layout, or None when that layout is not a drawn one."""
    text = "".join(str(layout or "").split()).lower()
    if text == "card":
        return None  # the stored value of the popup of earlier versions, though the drawn card is shown by that name
    for stored, design, name, _letter in DESIGNS:
        if text in (stored.lower(), "".join(name.split()).lower()):
            return design
    return None


def form(value) -> str:
    text = str(value or "").strip().lower()
    return next((size for size in SIZES if size.lower() == text), "Full")


def draw(options, texts) -> cv.Drawing:
    """The finished drawing, placed on the screen (``skip_canvas.draw`` with the rules of this design)."""
    if options.design == "NTake":
        # the whole-screen form is another thing than the corner panel and the corner picture
        rule = dict(TAKEOVER_FULL) if options.size == "Full" else (
            {"corners": "Hard", "flush": True, "shadow": False} if options.size == "Compact"
            else {"bare": True, "overlay": "None", "corners": "Rounded"})
        cv.RULES["NTake"] = rule
        if options.size == "Full":
            options = cv.dataclasses.replace(options, zoom=100, place="BottomLeft")
    return cv.draw(options, texts)
