# -*- coding: utf-8 -*-
"""The card behind the Full skip dialog and the next episode popup: its shape and its tint.

``Flat`` is the card of every earlier version: a plain rectangle, black, as see-through as the
card opacity says. The other styles are pictures with rounded corners (or a hairline edge) in the
looks of the skin Aeon Fuse; they keep their own colours and the opacity only fades them.

Nothing here needs Kodi to be imported, so the settings generator and the tests can read it.
"""

from __future__ import annotations

SETTING_KEY = "skip_card_style"
STYLE_FLAT = "Flat"

FLAT_TEXTURE = "white.png"
# Corner size of the card pictures, in texture pixels (Kodi's nine-slice border). The shortest Full
# dialog is 49 units high at 720p, so two borders always fit.
BORDER = 20

# (stored value, name in the settings and the Customize screen, picture)
STYLES = (
    (STYLE_FLAT, "Flat", FLAT_TEXTURE),
    ("Rounded", "Rounded", "skip_card_round.png"),
    ("FusedDark", "Fused Glass Dark", "skip_card_fgd.png"),
    ("FusedFrost", "Fused Glass Frost", "skip_card_fgf.png"),
    ("FusedClear", "Fused Glass Clear", "skip_card_fgc.png"),
    ("FusedStyle", "Fused Glass style", "skip_card_fgs.png"),
    ("AeonGlass", "Aeon Glass", "skip_card_agl.png"),
)
# Cards with round corners: the last row (the bar) keeps this far from the bottom edge, in 720p
# units, so its ends stay inside the curve. The others keep the 5 units of the flat card.
ROUND_STYLES = frozenset(("Rounded", "FusedDark", "FusedFrost", "FusedClear", "AeonGlass"))
ROUND_BOTTOM_MARGIN_720 = 10
_TEXTURES = {stored: picture for stored, _name, picture in STYLES}
_NAMES = {stored: name for stored, name, _picture in STYLES}


def normalize(value) -> str:
    """A stored style, or ``Flat`` when the text is not one of them."""
    text = "".join(str(value or "").split()).lower()
    for stored, _name, _picture in STYLES:
        if stored.lower() == text:
            return stored
    return STYLE_FLAT


def is_flat(style) -> bool:
    return normalize(style) == STYLE_FLAT


def bottom_margin_720(style, flat_margin) -> int:
    """Room under the last row of the Full dialog for a card of this style."""
    return ROUND_BOTTOM_MARGIN_720 if normalize(style) in ROUND_STYLES else flat_margin


def texture(style) -> str:
    """The media file drawn for a style."""
    return _TEXTURES[normalize(style)]


def name(style) -> str:
    return _NAMES[normalize(style)]


def options() -> list:
    """``[(name, stored value)]`` in the order of the settings list."""
    return [(label, stored) for stored, label, _picture in STYLES]


def picture_files() -> list:
    """The card pictures this add-on ships (the flat card uses Kodi-wide ``white.png``)."""
    return [picture for stored, _name, picture in STYLES if stored != STYLE_FLAT]


def _alpha(opacity) -> int:
    try:
        pct = max(0, min(100, int(opacity)))
    except (TypeError, ValueError):
        pct = 95
    return int(round(pct * 255 / 100.0))


def diffuse(style, opacity) -> str:
    """AARRGGBB for the card image: black on the flat white picture, plain fading on the others."""
    return "%02X%s" % (_alpha(opacity), "000000" if is_flat(style) else "FFFFFF")
