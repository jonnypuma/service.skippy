# -*- coding: utf-8 -*-
"""Skip dialog presets: ready-made looks plus user-saved snapshots.

A preset is a dict of *look* settings for Custom mode (mode, textures, font colour,
card, label format, ...). Behaviour and placement (corner, overlap handling,
countdown, duration content) are never part of a preset, so applying one keeps
those as the user set them.

Built-in presets are read-only. User presets live in
``addon_data/service.skippy/skip_dialog_presets.json``.
"""
from __future__ import annotations

import skip_dialog_card
import skip_layouts
from skippy_profile_store import profile_path, read_json, write_json

USER_PRESETS_FILE = "skip_dialog_presets.json"
USER_PRESETS_SCHEMA = "skippy_skip_dialog_presets_v1"
MAX_NAME_LEN = 40
MAX_USER_PRESETS = 50

KEY_TYPES = {
    "skip_dialog_mode": str,
    "skip_dialog_font_color": str,
    "skip_dialog_all_caps": bool,
    "hide_ending_text": bool,
    "show_progress_bar": bool,
    "progress_bar_style": str,
    "progress_bar_height": int,
    "button_focus_style": str,
    "skip_button_format": str,
    "hide_close_button": bool,
    "show_skip_button_focus_texture": bool,
    "hide_skip_icon": bool,
    "compact_full_combined": bool,
    "skip_card_enabled": bool,
    "skip_card_opacity": int,
    "skip_card_style": str,
    "minimal_button_style": str,
    "minimal_skip_button_format": str,
}
INT_RANGES = {"progress_bar_height": (5, 32), "skip_card_opacity": (0, 100)}

_COMMON = ("skip_dialog_mode", "skip_dialog_font_color", "skip_dialog_all_caps")
_MINIMAL_KEYS = _COMMON + ("minimal_button_style", "minimal_skip_button_format")
_FULL_KEYS = _COMMON + (
    "hide_ending_text",
    "show_progress_bar",
    "progress_bar_style",
    "progress_bar_height",
    "button_focus_style",
    "skip_button_format",
    "hide_close_button",
    "show_skip_button_focus_texture",
    "hide_skip_icon",
    "compact_full_combined",
    "skip_card_enabled",
    "skip_card_opacity",
    "skip_card_style",
)

BASE_LOOK = {
    "skip_dialog_mode": "Full",
    "skip_dialog_font_color": "FFFFFFFF",
    "skip_dialog_all_caps": False,
    "hide_ending_text": False,
    "show_progress_bar": True,
    "progress_bar_style": "progress_mid.png",
    "progress_bar_height": 16,
    "button_focus_style": "button_focus.png",
    "skip_button_format": "Skip + Type + Duration",
    "hide_close_button": True,
    "show_skip_button_focus_texture": True,
    "hide_skip_icon": True,
    "compact_full_combined": False,
    "skip_card_enabled": True,
    "skip_card_opacity": 95,
    "skip_card_style": skip_dialog_card.STYLE_FLAT,
    "minimal_button_style": "minimal_rounded_gray_640.png",
    "minimal_skip_button_format": "Skip + Type",
}

_DARK_GREY = "FF3D3D3D"

_BLACK = "FF000000"
_WHITE_FOCUS = "button_focus_flat_white.png"
_WHITE_BAR = "progress_mid_fuse_white.png"

# The looks of the skin Aeon Fuse (Fused Glass Dark / Frost / Clear, Fused Glass style, Aeon,
# Aeon Glass). They are listed first; the presets of the versions before 8.2.0 follow them and
# carry "(legacy)" wherever a name is shown. The font colour is the colour of the text on the
# button, so a look with a white focus picture has black text.
_FUSE_OVERRIDES = (
    (
        "Fused Glass Dark",
        {
            "skip_card_style": "FusedDark",
            "skip_card_opacity": 100,
            "skip_dialog_font_color": _BLACK,
            "button_focus_style": _WHITE_FOCUS,
            "progress_bar_style": "progress_mid_fuse_gold.png",
            "progress_bar_height": 6,
        },
    ),
    (
        "Fused Glass Frost",
        {
            "skip_card_style": "FusedFrost",
            "skip_card_opacity": 100,
            "skip_dialog_font_color": _BLACK,
            "button_focus_style": _WHITE_FOCUS,
            "progress_bar_style": _WHITE_BAR,
            "progress_bar_height": 6,
        },
    ),
    (
        "Fused Glass Clear",
        {
            "skip_card_style": "FusedClear",
            "skip_card_opacity": 100,
            "skip_dialog_font_color": _BLACK,
            "button_focus_style": _WHITE_FOCUS,
            "progress_bar_style": _WHITE_BAR,
            "progress_bar_height": 6,
        },
    ),
    (
        "Fused Glass style",
        {
            "skip_card_style": "FusedStyle",
            "skip_card_opacity": 100,
            "skip_dialog_all_caps": True,
            "button_focus_style": "button_focus_fuse_bar.png",
            "progress_bar_style": _WHITE_BAR,
            "progress_bar_height": 5,
        },
    ),
    (
        "Aeon",
        {
            "skip_card_opacity": 93,
            "skip_dialog_all_caps": True,
            "skip_dialog_font_color": _BLACK,
            "button_focus_style": "button_focus_fuse_square.png",
            "progress_bar_style": _WHITE_BAR,
            "progress_bar_height": 5,
        },
    ),
    (
        "Aeon Glass",
        {
            "skip_card_style": "AeonGlass",
            "skip_card_opacity": 100,
            "button_focus_style": "button_focus_fuse_glass.png",
            "progress_bar_style": _WHITE_BAR,
            "progress_bar_height": 6,
        },
    ),
    (
        "Aeon Glass Fill",
        {
            "skip_card_style": "AeonGlass",
            "skip_card_opacity": 100,
            "compact_full_combined": True,
            "button_focus_style": "button_focus_fuse_glass.png",
            "progress_bar_style": _WHITE_BAR,
            "progress_bar_height": 6,
        },
    ),
    (
        "Fused Glass Bare",
        {
            "skip_card_enabled": False,
            "skip_dialog_font_color": _BLACK,
            "button_focus_style": _WHITE_FOCUS,
            "progress_bar_style": "progress_mid_fuse_gold.png",
            "progress_bar_height": 6,
        },
    ),
    (
        "Aeon Bare",
        {
            "skip_card_enabled": False,
            "skip_dialog_all_caps": True,
            "skip_dialog_font_color": _BLACK,
            "button_focus_style": "button_focus_fuse_square.png",
            "progress_bar_style": _WHITE_BAR,
            "progress_bar_height": 5,
        },
    ),
    (
        "Fused Glass Compact",
        {
            "skip_dialog_mode": "CompactFull",
            "skip_dialog_font_color": _BLACK,
            "button_focus_style": _WHITE_FOCUS,
            "progress_bar_style": "progress_mid_fuse_gold.png",
            "skip_button_format": "Skip + Type",
        },
    ),
    (
        "Fused Glass style Compact",
        {
            "skip_dialog_mode": "CompactFull",
            "skip_dialog_all_caps": True,
            "button_focus_style": "button_focus_fuse_bar.png",
            "progress_bar_style": _WHITE_BAR,
            "skip_button_format": "Skip + Type",
        },
    ),
    (
        "Aeon Compact",
        {
            "skip_dialog_mode": "CompactFull",
            "skip_dialog_all_caps": True,
            "skip_dialog_font_color": _BLACK,
            "button_focus_style": "button_focus_fuse_square.png",
            "progress_bar_style": _WHITE_BAR,
            "skip_button_format": "Skip + Type",
        },
    ),
    (
        "Aeon Glass Compact",
        {
            "skip_dialog_mode": "CompactFull",
            "button_focus_style": "button_focus_fuse_glass.png",
            "progress_bar_style": _WHITE_BAR,
            "skip_button_format": "Skip + Type",
        },
    ),
    (
        "Fused Glass Dark Minimal",
        {
            "skip_dialog_mode": "Minimal",
            "minimal_button_style": "minimal_fuse_dark_640.png",
        },
    ),
    (
        "Fused Glass Frost Minimal",
        {
            "skip_dialog_mode": "Minimal",
            "minimal_button_style": "minimal_fuse_frost_640.png",
        },
    ),
    (
        "Fused Glass Clear Minimal",
        {
            "skip_dialog_mode": "Minimal",
            "minimal_button_style": "minimal_fuse_clear_640.png",
        },
    ),
    (
        "Fused Glass style Minimal",
        {
            "skip_dialog_mode": "Minimal",
            "skip_dialog_all_caps": True,
            "minimal_button_style": "minimal_fuse_grid_640.png",
        },
    ),
    (
        "Aeon Minimal",
        {
            "skip_dialog_mode": "Minimal",
            "skip_dialog_all_caps": True,
            "skip_dialog_font_color": _BLACK,
            "minimal_button_style": "minimal_fuse_square_640.png",
        },
    ),
    (
        "Aeon Glass Minimal",
        {
            "skip_dialog_mode": "Minimal",
            "minimal_button_style": "minimal_fuse_glass_640.png",
        },
    ),
)

# The presets of the versions before 8.2.0.
# name -> overrides on BASE_LOOK (ordered: classic gloss first, then flat/matte/glass)
_LEGACY_OVERRIDES = (
    ("Classic", {}),
    (
        "Modern",
        {
            "skip_card_opacity": 70,
            "button_focus_style": "button_focus_flat_blue.png",
            "progress_bar_style": "progress_mid_flat_blue.png",
            "progress_bar_height": 6,
            "hide_skip_icon": True,
        },
    ),
    (
        "Stylish",
        {
            "skip_dialog_all_caps": True,
            "skip_card_opacity": 88,
            "button_focus_style": "button_focus_3d_graphite.png",
            "progress_bar_style": "progress_mid_3d_graphite.png",
            "progress_bar_height": 10,
        },
    ),
    (
        "Colorful",
        {
            "skip_card_opacity": 85,
            "button_focus_style": "button_focus_3d_violet.png",
            "progress_bar_style": "progress_mid_pink_lightblue.png",
            "progress_bar_height": 12,
        },
    ),
    (
        "Vibrant",
        {
            "skip_card_opacity": 80,
            "button_focus_style": "button_focus_flat_violet.png",
            "progress_bar_style": "progress_mid_grad_aurora.png",
            "progress_bar_height": 8,
            "hide_skip_icon": True,
        },
    ),
    (
        "Glass",
        {
            "skip_card_enabled": False,
            "hide_ending_text": True,
            "button_focus_style": "button_focus_glass_dark.png",
            "progress_bar_style": "progress_mid_grad_aurora.png",
            "progress_bar_height": 6,
            "hide_skip_icon": True,
        },
    ),
    (
        "Outline",
        {
            "skip_card_enabled": False,
            "hide_ending_text": True,
            "button_focus_style": "button_focus_outline_white.png",
            "progress_bar_style": "progress_mid_flat_white.png",
            "progress_bar_height": 5,
            "hide_skip_icon": True,
        },
    ),
    (
        "Subtle",
        {
            "skip_dialog_mode": "CompactFull",
            "button_focus_style": "button_focus_glass_white.png",
            "progress_bar_style": "progress_mid_flat_white.png",
            "skip_button_format": "Skip + Type",
            "hide_close_button": True,
        },
    ),
    (
        "Sleek",
        {
            "skip_dialog_mode": "CompactFull",
            "skip_dialog_all_caps": True,
            "button_focus_style": "button_focus_flat_teal.png",
            "skip_button_format": "Skip + Type",
            "hide_close_button": True,
            "compact_full_combined": True,
        },
    ),
    (
        "Clean",
        {
            "skip_dialog_mode": "CompactFull",
            "button_focus_style": "button_focus_underline_white.png",
            "progress_bar_style": "progress_mid_flat_white.png",
            "skip_button_format": "Skip + Type",
            "hide_close_button": True,
        },
    ),
    (
        "Mono",
        {
            "skip_dialog_all_caps": True,
            "skip_card_opacity": 85,
            "button_focus_style": "button_focus_flat_slate.png",
            "progress_bar_style": "progress_mid_flat_white.png",
            "progress_bar_height": 5,
            "hide_skip_icon": True,
        },
    ),
    (
        "Slate",
        {
            "skip_card_opacity": 75,
            "button_focus_style": "button_focus_flat_slate.png",
            "progress_bar_style": "progress_mid_flat_slate.png",
            "progress_bar_height": 6,
            "hide_skip_icon": True,
        },
    ),
    (
        "Gold",
        {
            "skip_dialog_all_caps": True,
            "skip_card_opacity": 60,
            "button_focus_style": "button_focus_gold.png",
            "progress_bar_style": "progress_mid_grad_gold.png",
            "progress_bar_height": 6,
            "skip_button_format": "Skip + Type",
            "hide_skip_icon": True,
        },
    ),
    (
        "Neon",
        {
            "skip_dialog_all_caps": True,
            "skip_card_enabled": False,
            "hide_ending_text": True,
            "button_focus_style": "button_focus_neon_cyan.png",
            "progress_bar_style": "progress_mid_glow_cyan.png",
            "progress_bar_height": 8,
            "hide_skip_icon": True,
        },
    ),
    (
        "Neon Pink",
        {
            "skip_dialog_all_caps": True,
            "skip_card_enabled": False,
            "hide_ending_text": True,
            "button_focus_style": "button_focus_neon_magenta.png",
            "progress_bar_style": "progress_mid_glow_magenta.png",
            "progress_bar_height": 8,
            "hide_skip_icon": True,
        },
    ),
    (
        "Frosted",
        {
            "skip_card_enabled": False,
            "hide_ending_text": True,
            "button_focus_style": "button_focus_frosted_white.png",
            "progress_bar_style": "progress_mid_flat_white.png",
            "progress_bar_height": 5,
            "hide_skip_icon": True,
        },
    ),
    (
        "Steel",
        {
            "skip_dialog_all_caps": True,
            "skip_card_opacity": 85,
            "button_focus_style": "button_focus_steel.png",
            "progress_bar_style": "progress_mid_flat_slate.png",
            "progress_bar_height": 6,
            "hide_skip_icon": True,
        },
    ),
    (
        "Retro",
        {
            "skip_dialog_font_color": "FF43A047",
            "skip_dialog_all_caps": True,
            "skip_card_opacity": 90,
            "button_focus_style": "button_focus_bracket_green.png",
            "progress_bar_style": "progress_mid_segmented_green.png",
            "progress_bar_height": 10,
            "skip_button_format": "Skip + Type",
            "hide_skip_icon": True,
        },
    ),
    (
        "Segments",
        {
            "skip_card_opacity": 80,
            "button_focus_style": "button_focus_flat_teal.png",
            "progress_bar_style": "progress_mid_segmented_teal.png",
            "progress_bar_height": 10,
            "hide_skip_icon": True,
        },
    ),
    (
        "Stripes",
        {
            "skip_card_opacity": 80,
            "button_focus_style": "button_focus_flat_orange.png",
            "progress_bar_style": "progress_mid_striped_orange.png",
            "progress_bar_height": 10,
            "hide_skip_icon": True,
        },
    ),
    (
        "Sunset",
        {
            "skip_card_opacity": 75,
            "button_focus_style": "button_focus_flat_orange.png",
            "progress_bar_style": "progress_mid_grad_sunset.png",
            "progress_bar_height": 8,
            "hide_skip_icon": True,
        },
    ),
    (
        "Big & Bold",
        {
            "skip_dialog_all_caps": True,
            "skip_card_opacity": 100,
            "button_focus_style": "button_focus_flat_blue.png",
            "progress_bar_style": "progress_mid_flat_blue.png",
            "progress_bar_height": 24,
        },
    ),
    (
        "Ghost",
        {
            "skip_card_enabled": False,
            "hide_ending_text": True,
            "button_focus_style": "button_focus_glass_white.png",
            "progress_bar_style": "progress_mid_flat_white.png",
            "progress_bar_height": 5,
            "skip_button_format": "Skip",
            "hide_close_button": True,
            "hide_skip_icon": True,
        },
    ),
    (
        "Accessible",
        {
            "skip_dialog_all_caps": True,
            "skip_card_opacity": 100,
            "button_focus_style": "button_focus_flat_blue.png",
            "progress_bar_style": "progress_mid_flat_white.png",
            "progress_bar_height": 14,
            "skip_dialog_font_color": "FFFFFFFF",
        },
    ),
    (
        "Arcade",
        {
            "skip_dialog_font_color": "FFFF4DD2",
            "skip_dialog_all_caps": True,
            "skip_card_opacity": 90,
            "button_focus_style": "button_focus_neon_magenta.png",
            "progress_bar_style": "progress_mid_segmented_white.png",
            "progress_bar_height": 10,
            "skip_button_format": "Skip + Type",
            "hide_skip_icon": True,
        },
    ),
    (
        "Terminal",
        {
            "skip_dialog_font_color": "FF39FF14",
            "skip_dialog_all_caps": True,
            "hide_ending_text": True,
            "skip_card_opacity": 100,
            "button_focus_style": "button_focus_bracket_green.png",
            "progress_bar_style": "progress_mid_flat_green.png",
            "progress_bar_height": 6,
            "skip_button_format": "Skip",
            "hide_skip_icon": True,
        },
    ),
    (
        "Blueprint",
        {
            "skip_dialog_font_color": "FF7FDBFF",
            "skip_dialog_all_caps": True,
            "skip_card_enabled": False,
            "button_focus_style": "button_focus_outline_cyan.png",
            "progress_bar_style": "progress_mid_flat_blue.png",
            "progress_bar_height": 5,
            "skip_button_format": "Skip + Type",
            "hide_skip_icon": True,
        },
    ),
    (
        "Lava",
        {
            "skip_dialog_font_color": "FFFFD54F",
            "button_focus_style": "button_focus_3d_orange.png",
            "progress_bar_style": "progress_mid_grad_sunset.png",
            "progress_bar_height": 14,
        },
    ),
    (
        "Deep Sea",
        {
            "skip_dialog_font_color": "FFE0F7FA",
            "skip_card_opacity": 80,
            "button_focus_style": "button_focus_aqua_vignette.png",
            "progress_bar_style": "progress_mid_grad_ocean.png",
            "progress_bar_height": 8,
            "skip_button_format": "Skip + Type",
            "hide_skip_icon": True,
        },
    ),
    (
        "Candy",
        {
            "skip_dialog_mode": "CompactFull",
            "skip_dialog_font_color": "FF6D4C6F",
            "button_focus_style": "button_focus_pastel_peach.png",
            "skip_button_format": "Skip + Type",
            "hide_close_button": True,
            "hide_skip_icon": True,
            "compact_full_combined": True,
        },
    ),
    (
        "Noir",
        {
            "skip_dialog_mode": "CompactFull",
            "skip_dialog_all_caps": True,
            "skip_card_opacity": 100,
            "button_focus_style": "button_focus_outline_white.png",
            "progress_bar_style": "progress_mid_flat_white.png",
            "progress_bar_height": 5,
            "skip_button_format": "Skip + Type",
            "hide_close_button": True,
            "hide_skip_icon": True,
        },
    ),
    (
        "Aurora",
        {
            "skip_dialog_font_color": "FFB9F6CA",
            "skip_card_opacity": 70,
            "button_focus_style": "button_focus_glass_dark.png",
            "progress_bar_style": "progress_mid_grad_aurora.png",
            "progress_bar_height": 8,
            "skip_button_format": "Skip + Type",
            "hide_skip_icon": True,
        },
    ),
    (
        "Pill",
        {
            "skip_dialog_mode": "CompactFull",
            "button_focus_style": "button_focus_glass_blue.png",
            "skip_button_format": "Skip + Type",
            "hide_close_button": True,
            "hide_skip_icon": True,
            "compact_full_combined": True,
        },
    ),
    (
        "Underline",
        {
            "skip_dialog_mode": "CompactFull",
            "button_focus_style": "button_focus_underline_cyan.png",
            "progress_bar_style": "progress_mid_flat_teal.png",
            "skip_button_format": "Skip + Type",
            "hide_close_button": True,
            "hide_skip_icon": True,
        },
    ),
    (
        "Minimalist",
        {
            "skip_dialog_mode": "Minimal",
            "skip_dialog_font_color": _DARK_GREY,
            "minimal_button_style": "minimal_flat_white_640.png",
            "minimal_skip_button_format": "Skip",
        },
    ),
    (
        "Minimal Dark",
        {
            "skip_dialog_mode": "Minimal",
            "minimal_button_style": "minimal_flat_charcoal_640.png",
        },
    ),
    (
        "Minimal Glass",
        {
            "skip_dialog_mode": "Minimal",
            "minimal_button_style": "minimal_glass_dark_640.png",
        },
    ),
    (
        "Minimal Color",
        {
            "skip_dialog_mode": "Minimal",
            "minimal_button_style": "minimal_grad_midnight_640.png",
        },
    ),
    (
        "Minimal Steel",
        {
            "skip_dialog_mode": "Minimal",
            "minimal_button_style": "minimal_steel_640.png",
        },
    ),
    (
        "Minimal Gold",
        {
            "skip_dialog_mode": "Minimal",
            "minimal_button_style": "minimal_gold_640.png",
        },
    ),
    (
        "Minimal Neon",
        {
            "skip_dialog_mode": "Minimal",
            "minimal_button_style": "minimal_neon_cyan_640.png",
        },
    ),
    (
        "Minimal Frosted",
        {
            "skip_dialog_mode": "Minimal",
            "minimal_button_style": "minimal_frosted_640.png",
        },
    ),
    (
        "Minimal Paper",
        {
            "skip_dialog_mode": "Minimal",
            "skip_dialog_font_color": _DARK_GREY,
            "minimal_button_style": "minimal_rounded_light-grey_640.png",
        },
    ),
    (
        "Minimal Pastel",
        {
            "skip_dialog_mode": "Minimal",
            "skip_dialog_font_color": _DARK_GREY,
            "minimal_button_style": "minimal_pastel_mint_640.png",
        },
    ),
    (
        "Minimal Sunset",
        {
            "skip_dialog_mode": "Minimal",
            "minimal_button_style": "minimal_grad_sunset_640.png",
        },
    ),
    (
        "Minimal Midnight",
        {
            "skip_dialog_mode": "Minimal",
            "skip_dialog_font_color": "FFB3E5FC",
            "minimal_button_style": "minimal_grad_midnight_640.png",
        },
    ),
    (
        "Minimal Cyberpunk",
        {
            "skip_dialog_mode": "Minimal",
            "skip_dialog_all_caps": True,
            "minimal_button_style": "minimal_rounded_deep-pink_640.png",
        },
    ),
    (
        "Minimal Coffee",
        {
            "skip_dialog_mode": "Minimal",
            "skip_dialog_font_color": "FF3E2723",
            "minimal_button_style": "minimal_rounded_mustard-yellow_640.png",
        },
    ),
)

_BUILTIN_OVERRIDES = _FUSE_OVERRIDES + _LEGACY_OVERRIDES
LEGACY_SUFFIX = " (legacy)"
_LEGACY_NAMES = frozenset(name for name, _over in _LEGACY_OVERRIDES)


def is_legacy(name) -> bool:
    """True for a built-in preset of the versions before 8.2.0."""
    return name in _LEGACY_NAMES


_CARD_NAMES = frozenset(name for name, _over in _BUILTIN_OVERRIDES)


def display_name(name) -> str:
    """The name a picker shows. Every built-in preset of the classic card carries "(legacy)": the
    card has the earlier options only, and without the suffix "Fused Glass Dark" (a card) reads like
    "Stack card · Fused Glass Dark" (a drawn design). The stored name never changes; only what is
    shown gets the suffix, so a saved look and the next episode popup keep pointing at it."""
    return (name + LEGACY_SUFFIX) if name in _CARD_NAMES else name


def reserved_names() -> set:
    """Lower-case names a saved preset cannot take: every built-in, with and without its suffix."""
    out = set()
    for name, _over in _BUILTIN_OVERRIDES:
        out.add(name.lower())
        out.add(display_name(name).lower())
    for name, _values in layout_presets():
        out.add(name.lower())
    return out


# ------------------------------------------------------------- layout presets
# A preset of a new layout (skip_layouts.py) is three choices: the layout, its look and what colours
# the progress. It leaves the card's own settings alone, so going back to a card preset finds them.
LAYOUT_KEYS = (skip_layouts.KEY_LAYOUT, skip_layouts.KEY_LOOK, skip_layouts.KEY_BAR_COLOR)
LAYOUT_PRESET_SEP = " · "


def layout_preset_name(layout, look) -> str:
    return "%s%s%s" % (dict(skip_layouts.LAYOUT_NAMES)[layout], LAYOUT_PRESET_SEP, dict(skip_layouts.LOOK_NAMES)[look])


def layout_presets() -> list:
    """``[(name, values)]``: every new layout in every look. Look by look, so that stepping through the
    presets shows another design at every step instead of one design in eighteen looks."""
    out = []
    for look in skip_layouts.LOOKS:
        for layout in skip_layouts.NEW_LAYOUTS:
            out.append((layout_preset_name(layout, look), {
                skip_layouts.KEY_LAYOUT: layout,
                skip_layouts.KEY_LOOK: look,
                # a look of its own keeps its own bar; the looks of the skin colour it by segment kind
                skip_layouts.KEY_BAR_COLOR: skip_layouts.BAR_LOOK if look in skip_layouts.OWN_LOOKS else skip_layouts.BAR_TYPE,
            }))
    return out


def layout_values(raw) -> dict:
    """The three layout choices in ``raw``, normalized; ``{}`` when it is the classic card."""
    raw = raw if isinstance(raw, dict) else {}
    layout = skip_layouts.normalize_layout(raw.get(skip_layouts.KEY_LAYOUT))
    if skip_layouts.is_card(layout):
        return {}
    return {
        skip_layouts.KEY_LAYOUT: layout,
        skip_layouts.KEY_LOOK: skip_layouts.normalize_look(raw.get(skip_layouts.KEY_LOOK)),
        skip_layouts.KEY_BAR_COLOR: skip_layouts.normalize_bar_color(raw.get(skip_layouts.KEY_BAR_COLOR)),
    }


# What a saved preset of a new layout stores besides the three choices above: the rest of the dialog.
_EXTRA_NORMALIZERS = (
    (skip_layouts.KEY_OVERLAY, skip_layouts.normalize_overlay),
    (skip_layouts.KEY_APPEAR, skip_layouts.normalize_appear),
    (skip_layouts.KEY_LEAVE, skip_layouts.normalize_leave),
    (skip_layouts.KEY_PULSE, lambda value: coerce_bool(value)),
)
LAYOUT_EXTRA_KEYS = tuple(key for key, _fn in _EXTRA_NORMALIZERS)
# The options of a drawn design (skip_canvas) and what they are as drawn. A built-in preset of a
# design IS the design as drawn, so it sets them back; a saved preset stores what was chosen.
DESIGN_DEFAULTS = {
    "skip_canvas_corners": "Skin", "skip_canvas_close": True, "skip_canvas_icons": True, "skip_canvas_kicker": True,
    "skip_canvas_nested": True, "skip_canvas_time": True, "skip_canvas_text_shadow": "Mild", "skip_canvas_outline": "Medium",
    "skip_canvas_text_size": "100", "skip_canvas_zoom": "100", "skip_canvas_accent": "Auto", "skip_canvas_progress": "Auto",
    "skip_canvas_overlay_gradient": False, "skip_canvas_gradient": "Auto", "skip_canvas_focus": "Skip",
    "skip_canvas_distance": 64, "skip_canvas_place": "",
    "skip_canvas_background": "None", "skip_canvas_bar_edges": "Straight",
}


def design_value(key, value):
    """A design option in the type of its default (a draft may hold it as text)."""
    default = DESIGN_DEFAULTS[key]
    if value is None:
        return default
    if isinstance(default, bool):
        return coerce_bool(value)
    if isinstance(default, int):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default
    return str(value).strip()


def design_values(raw, fill=False) -> dict:
    """The design options ``raw`` has, in their types; with ``fill`` the missing ones as drawn."""
    raw = raw if isinstance(raw, dict) else {}
    return {key: design_value(key, raw.get(key)) for key in DESIGN_DEFAULTS if fill or key in raw}


def coerce_bool(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes")
    return bool(value)


def layout_extras(raw) -> dict:
    """Background overlay, Appears, Leaves and the pulse, for the keys ``raw`` has (normalized)."""
    raw = raw if isinstance(raw, dict) else {}
    return {key: normalize(raw[key]) for key, normalize in _EXTRA_NORMALIZERS if key in raw}


_EXTRA_DEFAULTS = {
    skip_layouts.KEY_OVERLAY: skip_layouts.OVERLAY_AUTO,
    skip_layouts.KEY_APPEAR: skip_layouts.APPEARS[0],
    skip_layouts.KEY_LEAVE: skip_layouts.LEAVES[0],
    skip_layouts.KEY_PULSE: False,
}


def is_layout_preset(values) -> bool:
    return bool(layout_values(values))


def mode_name(raw) -> str:
    mode = (str(raw or "Full")).strip()
    if mode in ("CompactFull", "Compact Full"):
        return "CompactFull"
    return "Minimal" if mode == "Minimal" else "Full"


def relevant_keys(mode) -> tuple:
    return _MINIMAL_KEYS if mode_name(mode) == "Minimal" else _FULL_KEYS


def coerce_value(key, value):
    """Coerce to the key's type; returns None when unusable."""
    typ = KEY_TYPES.get(key)
    if typ is None:
        return None
    if typ is bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            low = value.strip().lower()
            if low in ("true", "1", "yes"):
                return True
            if low in ("false", "0", "no"):
                return False
        return None
    if typ is int:
        try:
            num = int(str(value).strip())
        except (TypeError, ValueError):
            return None
        lo, hi = INT_RANGES.get(key, (num, num))
        return max(lo, min(hi, num))
    text = str(value if value is not None else "").strip()
    return text or None


def _full_values(overrides: dict) -> dict:
    look = dict(BASE_LOOK)
    look.update(overrides)
    keys = relevant_keys(look["skip_dialog_mode"])
    return {k: look[k] for k in keys}


def builtin_presets() -> list:
    """Ordered ``[(name, values)]`` for the built-in presets."""
    return [(name, _full_values(over)) for name, over in _BUILTIN_OVERRIDES]


def builtin_names() -> set:
    return {name for name, _ in _BUILTIN_OVERRIDES}


def sanitize_values(raw) -> dict:
    """Keep only known keys with usable values; fill missing relevant keys from BASE."""
    if not isinstance(raw, dict):
        return {}
    clean = {}
    for key in KEY_TYPES:
        if key in raw:
            val = coerce_value(key, raw[key])
            if val is not None:
                clean[key] = val
    if "skip_dialog_mode" not in clean:
        return {}
    clean["skip_dialog_mode"] = mode_name(clean["skip_dialog_mode"])
    if "skip_card_style" in clean:
        clean["skip_card_style"] = skip_dialog_card.normalize(clean["skip_card_style"])
    for key in relevant_keys(clean["skip_dialog_mode"]):
        clean.setdefault(key, BASE_LOOK[key])
    out = {k: clean[k] for k in relevant_keys(clean["skip_dialog_mode"])}
    # a saved preset of a new layout carries its layout choices, its overlay and its motion as well
    chosen = layout_values(raw)
    if chosen:
        out.update(chosen)
        out.update(layout_extras(raw))
        out.update(design_values(raw))
    return out


def clean_name(name) -> str:
    text = " ".join(str(name or "").split())
    return text[:MAX_NAME_LEN].strip()


# ----------------------------------------------------------------- user store
def _store_path():
    return profile_path(USER_PRESETS_FILE)


def load_user_presets() -> dict:
    data = read_json(_store_path(), {}, recover=True)
    raw = data.get("presets") if isinstance(data, dict) else None
    out = {}
    if isinstance(raw, dict):
        for name, entry in raw.items():
            nm = clean_name(name)
            values = sanitize_values(entry.get("values") if isinstance(entry, dict) else None)
            if nm and values and nm.lower() not in reserved_names():
                out[nm] = values
    return out


def _write_user_presets(presets: dict) -> bool:
    payload = {
        "schema": USER_PRESETS_SCHEMA,
        "presets": {name: {"values": vals} for name, vals in sorted(presets.items())},
    }
    return write_json(_store_path(), payload, keep_backup=True)


def list_presets() -> list:
    """``[(name, values, is_builtin)]``: the drawn designs in every look, the saved ones (A-Z), then
    the presets of the classic card (the Fuse looks, then the older ones), all of which a picker
    marks as legacy. This is the order of every picker and of stepping through the Preset row."""
    builtin = [(n, v, True) for n, v in builtin_presets()]
    user = load_user_presets()
    saved = [(n, user[n], False) for n in sorted(user, key=str.lower)]
    return (
        [(n, v, True) for n, v in layout_presets()]
        + saved
        + [p for p in builtin if not is_legacy(p[0])]
        + [p for p in builtin if is_legacy(p[0])]
    )


def user_preset_exists(name) -> bool:
    return clean_name(name) in load_user_presets()


def snapshot(draft: dict) -> dict:
    """Preset values for the draft's current mode."""
    mode = mode_name(draft.get("skip_dialog_mode"))
    raw = {k: draft.get(k, BASE_LOOK[k]) for k in relevant_keys(mode)}
    raw["skip_dialog_mode"] = mode
    chosen = layout_values(draft)
    if chosen:
        raw.update(chosen)
        # the whole dialog: also what lies behind it and how it moves (defaults where the draft is silent)
        raw.update({
            skip_layouts.KEY_OVERLAY: draft.get(skip_layouts.KEY_OVERLAY, skip_layouts.OVERLAY_AUTO),
            skip_layouts.KEY_APPEAR: draft.get(skip_layouts.KEY_APPEAR, skip_layouts.APPEARS[0]),
            skip_layouts.KEY_LEAVE: draft.get(skip_layouts.KEY_LEAVE, skip_layouts.LEAVES[0]),
            skip_layouts.KEY_PULSE: draft.get(skip_layouts.KEY_PULSE, False),
        })
        if skip_layouts.is_canvas(chosen[skip_layouts.KEY_LAYOUT]):
            raw.update(design_values(draft, fill=True))  # and every option of the drawn design
    return sanitize_values(raw)


def save_user_preset(name, draft: dict) -> tuple:
    """Returns ``(ok, error_code)``; codes: ``name``, ``builtin``, ``limit``, ``write``."""
    nm = clean_name(name)
    if not nm:
        return False, "name"
    if nm.lower() in reserved_names():
        return False, "builtin"
    presets = load_user_presets()
    presets = {k: v for k, v in presets.items() if k.lower() != nm.lower()}
    if len(presets) >= MAX_USER_PRESETS:
        return False, "limit"
    presets[nm] = snapshot(draft)
    return (True, "") if _write_user_presets(presets) else (False, "write")


def delete_user_preset(name) -> bool:
    presets = load_user_presets()
    if name not in presets:
        return False
    del presets[name]
    return _write_user_presets(presets)


# ----------------------------------------------------------- apply / detect
def apply_preset(draft: dict, values: dict) -> None:
    """Write preset values into the draft (keys outside the preset stay as they are).

    A built-in layout preset sets the layout, its look and the bar colour and leaves the size, the
    overlay and the motion as they are. A saved one is a whole dialog: it also brings back its
    size, overlay and motion. The options of a drawn design go with either: a saved preset brings
    back what it stored, a built-in one is the design as drawn, so it sets them back. Any other
    preset is a look of the classic card, so it goes back to it.
    """
    chosen = layout_values(values)
    if chosen:
        draft.update(chosen)
        draft.update(layout_extras(values))
        if skip_layouts.is_canvas(chosen[skip_layouts.KEY_LAYOUT]):
            draft.update(design_values(values, fill=True))
        if "skip_dialog_mode" in values:
            draft["skip_dialog_mode"] = mode_name(values["skip_dialog_mode"])
        return
    for key, val in sanitize_values(values).items():
        draft[key] = val
    draft[skip_layouts.KEY_LAYOUT] = skip_layouts.LAYOUT_CARD


def detect_preset(draft: dict):
    """Name of the first preset whose values all match the draft, else None."""
    mode = mode_name(draft.get("skip_dialog_mode"))
    chosen = layout_values(draft)
    if chosen:
        # A preset matches when everything it stores is what the draft has. A saved one stores more
        # than a built-in one, so of several matches the one that says most wins.
        extras = layout_extras({key: draft.get(key) for key in LAYOUT_EXTRA_KEYS if key in draft})
        best, best_size = None, -1
        for name, values, _builtin in list_presets():
            if layout_values(values) != chosen:
                continue
            stored = layout_extras(values)
            if any(extras.get(key, _EXTRA_DEFAULTS[key]) != value for key, value in stored.items()):
                continue
            if "skip_dialog_mode" in values and mode_name(values["skip_dialog_mode"]) != mode:
                continue
            # a drawn design: its options count too (a built-in preset is the design as drawn)
            if skip_layouts.is_canvas(chosen[skip_layouts.KEY_LAYOUT]) and \
                    design_values(values, fill=True) != design_values(draft, fill=True):
                continue
            size = len(stored) + (1 if "skip_dialog_mode" in values else 0) + len(design_values(values))
            if size > best_size:
                best, best_size = name, size
        return best
    keys = relevant_keys(mode)
    current = {}
    for key in keys:
        val = coerce_value(key, draft.get(key, BASE_LOOK[key]))
        current[key] = BASE_LOOK[key] if val is None else val
    for name, values, _builtin in list_presets():
        if is_layout_preset(values):
            continue
        if mode_name(values.get("skip_dialog_mode")) != mode:
            continue
        if all(current.get(k) == values.get(k) for k in keys):
            return name
    return None


def cycle_preset(draft: dict, delta: int):
    """Next/previous preset after the draft's current one. Returns ``(name, values)``."""
    presets = list_presets()
    if not presets:
        return None
    names = [p[0] for p in presets]
    cur = detect_preset(draft)
    if cur in names:
        idx = (names.index(cur) + delta) % len(names)
    else:
        # A look of your own. The first step goes back to the preset it came from: the design in use in
        # its look, as drawn. (It used to go to the first preset of the list, a classic card.)
        chosen = layout_values(draft)
        home = layout_preset_name(chosen[skip_layouts.KEY_LAYOUT], chosen[skip_layouts.KEY_LOOK]) if chosen else None
        if home in names:
            idx = names.index(home)
        else:
            idx = 0 if delta > 0 else len(names) - 1
    return presets[idx][0], presets[idx][1]


# ------------------------------------------------------------------- backup
def export_user_presets() -> dict:
    return {"schema": USER_PRESETS_SCHEMA, "presets": {
        n: {"values": v} for n, v in load_user_presets().items()}}


def merge_user_presets_from_backup(blob) -> int:
    """Add presets from a backup; existing names are kept. Returns how many were added."""
    if not isinstance(blob, dict):
        return 0
    incoming = blob.get("presets")
    if not isinstance(incoming, dict):
        return 0
    presets = load_user_presets()
    added = 0
    for name, entry in incoming.items():
        nm = clean_name(name)
        values = sanitize_values(entry.get("values") if isinstance(entry, dict) else None)
        if not nm or not values or nm in builtin_names() or nm in presets:
            continue
        if len(presets) >= MAX_USER_PRESETS:
            break
        presets[nm] = values
        added += 1
    if added and not _write_user_presets(presets):
        return 0
    return added
