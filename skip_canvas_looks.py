# -*- coding: utf-8 -*-
"""The looks of the drawn skip dialog, value for value from the mockup stylesheet (no Kodi needed).

Sizes are the stylesheet's own pixels, which are the pixels of a 1920 x 1080 screen (``SCALE`` is 1;
it is kept as the one place to change should a dialog ever be drawn larger). Colours are ``(r, g, b, a)`` with a from 0 to 255.
``tools/gen_skip_canvas.py`` paints the pictures from this table, ``skip_canvas.py`` reads the
colours and the measures.
"""

from __future__ import annotations

SCALE = 1.0


def _a(alpha) -> int:
    return int(round(alpha * 255))


def white(alpha) -> tuple:
    return (255, 255, 255, _a(alpha))


def rgb(text, alpha=1.0) -> tuple:
    return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16), _a(alpha))


NONE = (255, 255, 255, 0)

# The Fused Glass family shares these; a look only names what differs.
_FG = dict(
    r=28, ri=16, rb=999, pad=12, gap=8, tp=28,
    plate=(20, 23, 28, _a(.96)), plate_edge=white(.09), plate_stroke=1,
    btn=white(.10), btn_edge=None, btn_stroke=1, btn_ink=white(1),
    foc=white(1), foc_edge=None, foc_ink=rgb("0F1115"), foc_bar=0, foc_acc=rgb("A8700A"),
    acc=rgb("E8B04B"), track=white(.17),
    ink=white(1), ink2=white(.74), ink3=white(.52),
    nest=white(.07), nest_edge=None, chip=white(.14),
    caps=False, shadow=True, text_shadow=(0, 0, 0, 0),
    ov=(8, 9, 12), ova=0.74,  # the tint and strength of a shade behind the dialog
)


def _look(**over) -> dict:
    out = dict(_FG)
    out.update(over)
    return out


LOOKS = {
    "fgd": _look(),
    "fgf": _look(ova=0.26, plate=(84, 92, 108, 236), plate_edge=white(.34), btn=white(.19), nest=white(.12), text_shadow=(0, 0, 0, 102)),
    "fgc": _look(ova=0.44, plate=(14, 16, 22, _a(.40)), plate_edge=white(.30), btn=white(.17), nest=(0, 0, 0, _a(.26)),
                 text_shadow=(0, 0, 0, 178)),
    "fgs": _look(ov=(5, 6, 8), ova=0.78, r=0, ri=0, rb=0, pad=0, gap=0, tp=28, plate=(7, 8, 10, _a(.76)), plate_edge=white(.28),
                 btn=NONE, btn_edge=white(.28), btn_ink=white(.62), foc=white(.11), foc_edge=white(.28), foc_ink=white(1),
                 foc_bar=6, foc_acc=white(1), acc=white(1), track=white(.22), ink2=white(.64), ink3=white(.48),
                 nest=NONE, nest_edge=white(.28), chip=white(.12), caps=True, shadow=False),
    "aeo": _look(ov=(0, 0, 0), ova=0.84, r=0, ri=0, rb=0, pad=0, gap=0, tp=28, plate=(12, 12, 12, _a(.93)), plate_edge=None,
                 btn=white(.09), foc=white(1), foc_ink=rgb("0B0B0B"), foc_acc=rgb("0B0B0B"), acc=white(1), track=white(.20),
                 ink2=white(.70), ink3=white(.50), nest=white(.07), chip=white(.14), caps=True, shadow=False),
    "agl": _look(ov=(14, 16, 22), ova=0.5, r=16, ri=8, rb=8, pad=8, gap=8, tp=20, plate=(34, 37, 46, _a(.44)), plate_edge=white(.32),
                 btn=white(.07), btn_edge=white(.18), foc=white(.27), foc_edge=white(.76), foc_ink=white(1), foc_acc=white(1),
                 acc=white(1), track=white(.22), ink2=white(.76), ink3=white(.54), nest=(0, 0, 0, _a(.22)),
                 nest_edge=white(.16), chip=white(.16), text_shadow=(0, 0, 0, 153)),
    # the twelve looks of their own
    "neon": _look(ov=(8, 5, 22), r=8, ri=2, rb=4, pad=10, plate=(8, 5, 22, _a(.74)), plate_edge=rgb("39F0FF"), plate_stroke=2,
                  btn=NONE, btn_edge=rgb("FF46E1", .75), btn_stroke=2, btn_ink=rgb("FF8AEE"), foc=rgb("39F0FF"),
                  foc_edge=rgb("39F0FF"), foc_ink=rgb("04141A"), foc_acc=rgb("04141A"), acc=rgb("FF46E1"),
                  track=rgb("FF46E1", .24), ink=rgb("EAFFFF"), ink2=rgb("8CECF7"), ink3=rgb("8CECF7", .6),
                  nest=rgb("39F0FF", .08), nest_edge=rgb("39F0FF", .4), chip=rgb("FF46E1", .25), caps=True, shadow=False,
                  glow=rgb("39F0FF", .55)),
    "paper": _look(ov=(20, 18, 14), r=22, ri=12, rb=12, pad=10, plate=rgb("F4EFE6"), plate_edge=(0, 0, 0, _a(.06)),
                   btn=rgb("1C1A16", .08), btn_ink=rgb("1C1A16"), foc=rgb("1C1A16"), foc_ink=rgb("F4EFE6"),
                   foc_acc=rgb("F0A898"), acc=rgb("C8452E"), track=rgb("1C1A16", .14), ink=rgb("1C1A16"),
                   ink2=rgb("1C1A16", .7), ink3=rgb("1C1A16", .5), nest=rgb("1C1A16", .06), chip=rgb("C8452E", .14)),
    "sunset": _look(ov=(60, 16, 60), r=28, ri=16, rb=999, pad=12, plate_grad=(135, (("FF9A3D", 0.0), ("E8457A", 0.55), ("8A3FFC", 1.0))),
                    plate_edge=white(.28), btn=white(.20), foc=white(1), foc_ink=rgb("8A1C4D"), foc_acc=rgb("E8457A"),
                    acc=white(1), track=white(.30), ink2=white(.86), ink3=white(.66), nest=(0, 0, 0, _a(.15)),
                    chip=white(.24)),
    "ocean": _look(ov=(8, 24, 70), r=28, ri=16, rb=999, pad=12, plate_grad=(140, (("10C0B0", 0.0), ("2563EB", 0.58), ("3B1D8F", 1.0))),
                   plate_edge=white(.26), btn=white(.18), foc=white(1), foc_ink=rgb("123A8F"), foc_acc=rgb("2563EB"),
                   acc=rgb("9DFFF2"), track=white(.28), ink2=white(.86), ink3=white(.66), nest=(0, 0, 0, _a(.16)),
                   chip=white(.22)),
    "brutal": _look(ov=(0, 0, 0), r=0, ri=0, rb=0, pad=0, gap=0, tp=26, plate=rgb("FFDE21"), plate_edge=rgb("000000"), plate_stroke=5,
                    btn=rgb("FFDE21"), btn_edge=rgb("000000"), btn_stroke=5, btn_ink=rgb("000000"), foc=rgb("000000"),
                    foc_edge=rgb("000000"), foc_ink=rgb("FFDE21"), foc_acc=rgb("FFDE21"), acc=rgb("000000"),
                    track=(0, 0, 0, _a(.2)), ink=rgb("000000"), ink2=(0, 0, 0, _a(.78)), ink3=(0, 0, 0, _a(.6)),
                    nest=NONE, nest_edge=rgb("000000"), chip=rgb("000000"), chip_ink=rgb("FFDE21"), caps=True, shadow=False,
                    hard_shadow=(12, rgb("000000"))),
    "term": _look(ov=(0, 12, 5), r=0, ri=0, rb=0, pad=10, gap=10, plate=(0, 12, 5, _a(.92)), plate_edge=rgb("37FF8B"),
                  btn=NONE, btn_edge=rgb("37FF8B", .5), btn_ink=rgb("37FF8B"), foc=rgb("37FF8B"), foc_edge=rgb("37FF8B"),
                  foc_ink=rgb("001A0A"), foc_acc=rgb("001A0A"), acc=rgb("37FF8B"), track=rgb("37FF8B", .22),
                  ink=rgb("C8FFDD"), ink2=rgb("37FF8B"), ink3=rgb("37FF8B", .6), nest=rgb("37FF8B", .07),
                  nest_edge=rgb("37FF8B", .4), chip=rgb("37FF8B", .2), caps=True),
    "line": _look(ov=(0, 0, 0), r=20, ri=10, rb=999, pad=10, plate=NONE, plate_edge=white(1), plate_stroke=2, btn=NONE,
                  btn_edge=white(.75), btn_stroke=2, foc=white(1), foc_edge=white(1), foc_ink=rgb("000000"),
                  foc_acc=rgb("000000"), acc=white(1), track=white(.30), ink2=white(.85), ink3=white(.65), nest=NONE,
                  nest_edge=white(.55), chip=white(.20), shadow=False, text_shadow=(0, 0, 0, 217)),
    "luxe": _look(ov=(11, 10, 8), r=3, ri=0, rb=0, pad=18, gap=10, tp=14, plate=(11, 10, 8, _a(.95)), plate_edge=rgb("C9A45C"),
                  plate_frame=(7, rgb("C9A45C", .55)), btn=NONE, btn_edge=rgb("C9A45C", .55), btn_ink=rgb("E9D5A7"),
                  foc=rgb("C9A45C"), foc_edge=rgb("C9A45C"), foc_ink=rgb("14110B"), foc_acc=rgb("14110B"),
                  acc=rgb("C9A45C"), track=rgb("C9A45C", .22), ink=rgb("F5EAD2"), ink2=rgb("C9A45C"),
                  ink3=rgb("C9A45C", .7), nest=NONE, nest_edge=rgb("C9A45C", .4), chip=rgb("C9A45C", .2)),
    "pastel": _look(ov=(30, 24, 60), r=34, ri=22, rb=999, pad=12, plate=rgb("ECE8FF"), plate_edge=white(.7), btn=rgb("2A2550", .09),
                    btn_ink=rgb("2A2550"), foc=rgb("7C6CF2"), foc_ink=white(1), foc_acc=white(1), acc=rgb("F27AA8"),
                    track=rgb("2A2550", .13), ink=rgb("2A2550"), ink2=rgb("2A2550", .72), ink3=rgb("2A2550", .52),
                    nest=rgb("7C6CF2", .12), chip=rgb("F27AA8", .25)),
    "gloss": _look(ov=(10, 12, 16), r=20, ri=12, rb=14, pad=10, plate_grad=(180, (("414755", 0.0), ("181B21", 1.0))),
                   plate_edge=(0, 0, 0, _a(.6)), plate_bevel=True, btn_grad=(180, (("525967", 0.0), ("2B2F38", 1.0))),
                   btn_edge=(0, 0, 0, _a(.6)), foc_grad=(180, (("6DBCFF", 0.0), ("1B6FE0", 1.0))), foc_edge=rgb("0C3F86"),
                   foc_ink=white(1), foc_acc=white(1), acc=rgb("6DBCFF"), track=(0, 0, 0, _a(.45)), ink2=white(.78),
                   ink3=white(.56), nest=(0, 0, 0, _a(.3)), nest_edge=white(.08), chip=rgb("6DBCFF", .25),
                   text_shadow=(0, 0, 0, 153)),
    "mono": _look(ov=(0, 0, 0), ova=0.9, r=0, ri=0, rb=0, pad=0, gap=0, tp=26, plate=rgb("000000"), plate_edge=white(1), plate_stroke=3,
                  btn=rgb("000000"), btn_edge=white(1), btn_stroke=3, foc=white(1), foc_edge=white(1),
                  foc_ink=rgb("000000"), foc_acc=rgb("000000"), acc=white(1), track=white(.25), ink2=white(.8),
                  ink3=white(.6), nest=NONE, nest_edge=white(1), chip=white(1), chip_ink=rgb("000000"), caps=True,
                  shadow=False),
    "vhs": _look(ov=(0, 0, 40), r=0, ri=0, rb=0, pad=10, gap=12, plate=(0, 0, 40, _a(.55)), plate_edge=None, btn=NONE, foc=white(1),
                 foc_edge=white(1), foc_ink=rgb("0A0A3A"), foc_acc=rgb("0A0A3A"), acc=rgb("3BFF6F"), track=white(.30),
                 ink2=rgb("3BFF6F"), ink3=white(.7), nest=NONE, nest_edge=white(.5), chip=rgb("3BFF6F", .3), caps=True,
                 shadow=False, fringe=True),
}
CODES = tuple(LOOKS)

# Corners: what the Studio's Corners row forces. "Skin" keeps the look's own.
CORNERS = ("Skin", "Hard", "Rounded")
ROUND = dict(r=28, ri=16, rb=999, pad=12, gap=8)  # the mockups' rounded shape: padded, with a gap between the buttons
HARD = dict(r=0, ri=0, rb=0)


def look(code, corners="Skin") -> dict:
    """The look with the corner choice applied."""
    found = dict(LOOKS.get(code) or LOOKS["fgf"])
    if corners == "Hard":
        found.update(HARD)
    elif corners == "Rounded" and found["r"] < ROUND["r"]:
        found.update(ROUND)
    found["corner_key"] = corner_key(code, corners)
    return found


def corner_key(code, corners="Skin") -> str:
    """Which set of pictures draws this look with this corner choice: ``""`` its own, ``h`` or ``r``."""
    own = LOOKS.get(code) or LOOKS["fgf"]
    if corners == "Hard" and own["r"] > 0:
        return "h"
    if corners == "Rounded" and own["r"] < ROUND["r"]:
        return "r"
    return ""


def argb(colour) -> str:
    """``0xAARRGGBB`` as Kodi's Python controls take it."""
    r, g, b, a = colour
    return "0x%02X%02X%02X%02X" % (a, r, g, b)


def with_alpha(colour, share) -> tuple:
    return colour[:3] + (int(round(colour[3] * share)),)
