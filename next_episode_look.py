# -*- coding: utf-8 -*-
"""The look of the next episode popup: its own default, the skip dialog's current look, or one
of the skip dialog's presets.

A look is the part of the popup that can change without touching its layout: the card behind
it, the text colours, upper case, the focus texture of the two buttons and the texture of the
progress bar. Which rows show (picture, time left, bar) and where the popup sits stay in the
popup settings and are never part of a look.

Nothing here needs Kodi to be imported, so the settings generator can read the choices.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional

KEY_LOOK = "next_episode_popup_look"

LOOK_DEFAULT = "Default"
LOOK_SKIP_DIALOG = "SkipDialog"

# The Full and Compact Full presets of the skip dialog, in its order. The Minimal ones only
# choose a corner chip, which the popup has no use for. A test keeps this list in step with
# skip_dialog_presets.
PRESET_NAMES = (
    "Classic", "Modern", "Stylish", "Colorful", "Vibrant", "Glass", "Outline", "Subtle",
    "Sleek", "Clean", "Mono", "Slate", "Gold", "Neon", "Neon Pink", "Frosted", "Steel",
    "Retro", "Segments", "Stripes", "Sunset", "Big & Bold", "Ghost", "Accessible", "Arcade",
    "Terminal", "Blueprint", "Lava", "Deep Sea", "Candy", "Noir", "Aurora", "Pill",
    "Underline",
)


def preset_token(name) -> str:
    """The stored value for a preset name: letters and digits only (``Big & Bold`` -> ``BigBold``)."""
    return "".join(ch for ch in str(name or "") if ch.isalnum())


PRESET_TOKENS = {preset_token(name): name for name in PRESET_NAMES}
LOOK_CHOICES = (LOOK_DEFAULT, LOOK_SKIP_DIALOG) + tuple(PRESET_TOKENS)
LOOK_LABELS = {LOOK_DEFAULT: "Default", LOOK_SKIP_DIALOG: "Same as skip dialog"}
LOOK_LABELS.update({token: name for token, name in PRESET_TOKENS.items()})

BORDER_ALL = "all"  # nine-slice with a 12 px border all round
BORDER_SIDES = "sides"  # 12 px on the left and right only (the 3D textures)
BORDER_NONE = "none"  # stretched as one piece

# --- the user's own choices on top of a look -------------------------------------------------
# Each is stored as a setting. ``FOLLOW_LOOK`` ("Same as look") leaves that part to the look; any
# other value replaces it. Picking another look in the Customize screen clears them again.
FOLLOW_LOOK = "Look"
FOLLOW_LOOK_LABEL = "Same as look"

KEY_TEXT_COLOR = "next_episode_popup_text_color"
KEY_HEADING_COLOR = "next_episode_popup_heading_color"
KEY_ALL_CAPS = "next_episode_popup_all_caps"
KEY_FOCUS_STYLE = "next_episode_popup_focus_style"
KEY_BAR_STYLE = "next_episode_popup_bar_style"
KEY_CARD_OPACITY = "next_episode_popup_card_opacity"
OVERRIDE_KEYS = (
    KEY_TEXT_COLOR,
    KEY_HEADING_COLOR,
    KEY_ALL_CAPS,
    KEY_FOCUS_STYLE,
    KEY_BAR_STYLE,
    KEY_CARD_OPACITY,
)

CAPS_ON = "On"
CAPS_OFF = "Off"

# The skip dialog"s font colours (skip_dialog_customize_ui.FONT_COLORS); a test keeps them in step.
COLOR_PAIRS = (
    ("White", "FFFFFFFF"),
    ("Light grey", "FF8E8E8E"),
    ("Grey", "FF6E6E6E"),
    ("Dark grey", "FF3D3D3D"),
    ("Black", "FF000000"),
    ("Blue", "FF1976D2"),
    ("Red", "FFE5392F"),
    ("Green", "FF43A047"),
    ("Aquamarine", "FF00ACC1"),
    ("Pink", "FFE91E63"),
    ("Purple", "FF8E24AA"),
    ("Peach", "FFFF8A65"),
    ("Orange", "FFEF6C00"),
    ("Yellow", "FFF9A825"),
)

# The skip dialog"s button highlight textures (BUTTON_FOCUS).
FOCUS_PAIRS = (
    ("Default", "button_focus.png"),
    ("Aqua", "button_focus_aqua.png"),
    ("Aqua Bevel", "button_focus_aqua_bevel.png"),
    ("Aqua Dark", "button_focus_aqua_dark.png"),
    ("Aqua Vignette", "button_focus_aqua_vignette.png"),
    ("Aqua Rounded", "button_focus_aqua_rounded.png"),
    ("Blue", "button_focus_blue.png"),
    ("Blue Rectangular 3D", "button_focus_blue_rectangular_3d.png"),
    ("Blue Rounded 3D", "button_focus_blue_rounded_3d.png"),
    ("Gold Rectangular 3D", "button_focus_gold_rectangular_3d.png"),
    ("Green 3D", "button_focus_3d_green.png"),
    ("Pink 3D", "button_focus_3d_pink.png"),
    ("Light Pink 3D", "button_focus_3d_light_pink.png"),
    ("Cyan 3D", "button_focus_3d_cyan.png"),
    ("Silver 3D", "button_focus_3d_silver.png"),
    ("Orange 3D", "button_focus_3d_orange.png"),
    ("Violet 3D", "button_focus_3d_violet.png"),
    ("Graphite 3D", "button_focus_3d_graphite.png"),
    ("Ice 3D", "button_focus_3d_ice.png"),
    ("Flat Blue", "button_focus_flat_blue.png"),
    ("Flat Teal", "button_focus_flat_teal.png"),
    ("Flat Green", "button_focus_flat_green.png"),
    ("Flat Rose", "button_focus_flat_rose.png"),
    ("Flat Orange", "button_focus_flat_orange.png"),
    ("Flat Violet", "button_focus_flat_violet.png"),
    ("Flat Slate", "button_focus_flat_slate.png"),
    ("Flat White", "button_focus_flat_white.png"),
    ("Glass White", "button_focus_glass_white.png"),
    ("Glass Blue", "button_focus_glass_blue.png"),
    ("Glass Dark", "button_focus_glass_dark.png"),
    ("Outline White", "button_focus_outline_white.png"),
    ("Outline Cyan", "button_focus_outline_cyan.png"),
    ("Underline White", "button_focus_underline_white.png"),
    ("Underline Cyan", "button_focus_underline_cyan.png"),
    ("Frosted White", "button_focus_frosted_white.png"),
    ("Brushed Steel", "button_focus_steel.png"),
    ("Neon Cyan", "button_focus_neon_cyan.png"),
    ("Neon Magenta", "button_focus_neon_magenta.png"),
    ("Gold Leaf", "button_focus_gold.png"),
    ("Pastel Mint", "button_focus_pastel_mint.png"),
    ("Pastel Peach", "button_focus_pastel_peach.png"),
    ("Pastel Lavender", "button_focus_pastel_lavender.png"),
    ("Bracket White", "button_focus_bracket_white.png"),
    ("Bracket Cyan", "button_focus_bracket_cyan.png"),
    ("Bracket Green", "button_focus_bracket_green.png"),
)

# The skip dialog"s progress bar styles (PROGRESS_STYLES).
BAR_PAIRS = (
    ("Green (Default)", "progress_mid.png"),
    ("Blue/purple gradient", "progress_mid_blue_purple.png"),
    ("Dark yellow", "progress_mid_darkyellow.png"),
    ("Green/blue gradient", "progress_mid_green_blue.png"),
    ("Light blue", "progress_mid_lightblue.png"),
    ("Light green", "progress_mid_lightgreen.png"),
    ("Light yellow", "progress_mid_lightyellow.png"),
    ("Pink", "progress_mid_pink.png"),
    ("Pink/light blue gradient", "progress_mid_pink_lightblue.png"),
    ("Purple", "progress_mid_purple.png"),
    ("Yellow/red gradient", "progress_mid_yellow_red.png"),
    ("Cyan 3D", "progress_mid_3d_cyan.png"),
    ("Silver 3D", "progress_mid_3d_silver.png"),
    ("Orange 3D", "progress_mid_3d_orange.png"),
    ("Violet 3D", "progress_mid_3d_violet.png"),
    ("Graphite 3D", "progress_mid_3d_graphite.png"),
    ("Ice 3D", "progress_mid_3d_ice.png"),
    ("Flat Blue", "progress_mid_flat_blue.png"),
    ("Flat Teal", "progress_mid_flat_teal.png"),
    ("Flat Green", "progress_mid_flat_green.png"),
    ("Flat Rose", "progress_mid_flat_rose.png"),
    ("Flat Orange", "progress_mid_flat_orange.png"),
    ("Flat Violet", "progress_mid_flat_violet.png"),
    ("Flat Slate", "progress_mid_flat_slate.png"),
    ("Flat White", "progress_mid_flat_white.png"),
    ("Gradient Ocean", "progress_mid_grad_ocean.png"),
    ("Gradient Aurora", "progress_mid_grad_aurora.png"),
    ("Gradient Sunset", "progress_mid_grad_sunset.png"),
    ("Segmented White", "progress_mid_segmented_white.png"),
    ("Segmented Teal", "progress_mid_segmented_teal.png"),
    ("Segmented Green", "progress_mid_segmented_green.png"),
    ("Glow Cyan", "progress_mid_glow_cyan.png"),
    ("Glow Magenta", "progress_mid_glow_magenta.png"),
    ("Striped Blue", "progress_mid_striped_blue.png"),
    ("Striped Orange", "progress_mid_striped_orange.png"),
    ("Gradient Gold", "progress_mid_grad_gold.png"),
)

CAPS_PAIRS = ((CAPS_ON, CAPS_ON), (CAPS_OFF, CAPS_OFF))
# Card opacity in steps of 5 %, like the skip dialog's own setting; 0 % is no card at all.
OPACITY_PAIRS = tuple(("%d%%" % pct, str(pct)) for pct in range(0, 101, 5))

OVERRIDE_PAIRS = {
    KEY_TEXT_COLOR: COLOR_PAIRS,
    KEY_HEADING_COLOR: COLOR_PAIRS,
    KEY_ALL_CAPS: CAPS_PAIRS,
    KEY_FOCUS_STYLE: FOCUS_PAIRS,
    KEY_BAR_STYLE: BAR_PAIRS,
    KEY_CARD_OPACITY: OPACITY_PAIRS,
}


def override_pairs(key):
    """``(label, stored value)`` choices for an override, "Same as look" first."""
    return ((FOLLOW_LOOK_LABEL, FOLLOW_LOOK),) + tuple(OVERRIDE_PAIRS[key])


def override_options(key):
    """Stored values for an override, ``FOLLOW_LOOK`` first."""
    return tuple(value for _label, value in override_pairs(key))


def override_label(key, stored) -> str:
    """The English name of a stored choice."""
    for label, value in override_pairs(key):
        if value == stored:
            return label
    return str(stored)


def normalize_override(key, value) -> str:
    """A stored override, or ``FOLLOW_LOOK`` when the text is not one of the choices."""
    text = str(value if value is not None else "").strip().lower()
    for stored in override_options(key):
        if stored.lower() == text:
            return stored
    return FOLLOW_LOOK



@dataclass(frozen=True)
class PopupLook:
    card_color: str  # AARRGGBB of the card behind the popup (alpha 00 means no card)
    heading_color: str  # AARRGGBB of the "Play next episode?" line
    text_color: Optional[str]  # AARRGGBB, or None to follow the skip dialog font colour setting
    all_caps: bool
    focus_texture: str  # media file drawn behind the focused button
    focus_border: str  # BORDER_ALL / BORDER_SIDES / BORDER_NONE
    bar_texture: str  # progress_mid_*.png


# What the popup has always looked like.
DEFAULT_LOOK = PopupLook(
    card_color="F0000000",
    heading_color="FFB0D4E8",
    text_color=None,
    all_caps=False,
    focus_texture="button_focus_flat_teal.png",
    focus_border=BORDER_ALL,
    bar_texture="progress_mid_segmented_teal.png",
)


def normalize_look(value) -> str:
    """A stored look, or the default when the text is not one of the choices."""
    text = "".join(str(value or "").split()).lower()
    for choice in LOOK_CHOICES:
        if choice.lower() == text:
            return choice
    return LOOK_DEFAULT


def card_color(enabled, opacity) -> str:
    """AARRGGBB black for the card; no card at all when it is switched off."""
    if not enabled:
        return "00000000"
    try:
        pct = max(0, min(100, int(opacity)))
    except (TypeError, ValueError):
        pct = 95
    return "%02X000000" % int(round(pct * 255 / 100.0))


def focus_border(filename) -> str:
    """How the focus texture is cut up, the same table the skip dialog uses."""
    from skip_dialog_appearance import button_focus_nine_slice_border

    border = button_focus_nine_slice_border(filename)
    if border == "12,12,12,12":
        return BORDER_ALL
    if border:
        return BORDER_SIDES
    return BORDER_NONE


def look_from_values(values) -> PopupLook:
    """Turn skip dialog look values (a preset, or the current settings) into a popup look."""
    from skip_dialog_appearance import resolve_font_color_argb

    values = values or {}
    text = resolve_font_color_argb(values.get("skip_dialog_font_color"), fallback="FFFFFFFF")
    focus = (values.get("button_focus_style") or "").strip() or "button_focus.png"
    return PopupLook(
        card_color=card_color(
            values.get("skip_card_enabled", True), values.get("skip_card_opacity", 95)
        ),
        heading_color=text,
        text_color=text,
        all_caps=bool(values.get("skip_dialog_all_caps", False)),
        focus_texture=focus,
        focus_border=focus_border(focus),
        bar_texture=(values.get("progress_bar_style") or "").strip() or "progress_mid.png",
    )


def skip_dialog_values(addon) -> dict:
    """The skip dialog's look settings as they are now."""
    from settings_utils import addon_get_bool, addon_get_int, addon_get_setting_text
    from skip_dialog_presets import BASE_LOOK

    return {
        "skip_dialog_font_color": addon_get_setting_text(
            addon, "skip_dialog_font_color", BASE_LOOK["skip_dialog_font_color"]
        ),
        "skip_dialog_all_caps": addon_get_bool(
            addon, "skip_dialog_all_caps", BASE_LOOK["skip_dialog_all_caps"]
        ),
        "progress_bar_style": addon_get_setting_text(
            addon, "progress_bar_style", BASE_LOOK["progress_bar_style"]
        ),
        "button_focus_style": addon_get_setting_text(
            addon, "button_focus_style", BASE_LOOK["button_focus_style"]
        ),
        "skip_card_enabled": addon_get_bool(
            addon, "skip_card_enabled", BASE_LOOK["skip_card_enabled"]
        ),
        "skip_card_opacity": addon_get_int(
            addon, "skip_card_opacity", BASE_LOOK["skip_card_opacity"], minimum=0, maximum=100
        ),
    }


def resolve_look(choice, addon) -> PopupLook:
    """The look for a stored choice. Never raises: anything unusable gives the default look."""
    token = normalize_look(choice)
    if token == LOOK_DEFAULT:
        return DEFAULT_LOOK
    try:
        if token == LOOK_SKIP_DIALOG:
            return look_from_values(skip_dialog_values(addon))
        from skip_dialog_presets import builtin_presets

        name = PRESET_TOKENS.get(token)
        for preset_name, values in builtin_presets():
            if preset_name == name:
                return look_from_values(values)
    except Exception:
        pass
    return DEFAULT_LOOK


def look_with_overrides(look, values) -> PopupLook:
    """``look`` with the user's own choices on top. Never raises: unusable values change nothing."""
    values = values or {}
    changes = {}
    text = normalize_override(KEY_TEXT_COLOR, values.get(KEY_TEXT_COLOR))
    if text != FOLLOW_LOOK:
        changes["text_color"] = text
    heading = normalize_override(KEY_HEADING_COLOR, values.get(KEY_HEADING_COLOR))
    if heading != FOLLOW_LOOK:
        changes["heading_color"] = heading
    caps = normalize_override(KEY_ALL_CAPS, values.get(KEY_ALL_CAPS))
    if caps != FOLLOW_LOOK:
        changes["all_caps"] = caps == CAPS_ON
    focus = normalize_override(KEY_FOCUS_STYLE, values.get(KEY_FOCUS_STYLE))
    if focus != FOLLOW_LOOK:
        changes["focus_texture"] = focus
        try:
            changes["focus_border"] = focus_border(focus)
        except Exception:
            changes["focus_border"] = BORDER_ALL
    bar = normalize_override(KEY_BAR_STYLE, values.get(KEY_BAR_STYLE))
    if bar != FOLLOW_LOOK:
        changes["bar_texture"] = bar
    opacity = normalize_override(KEY_CARD_OPACITY, values.get(KEY_CARD_OPACITY))
    if opacity != FOLLOW_LOOK:
        changes["card_color"] = card_color(True, int(opacity))
    return replace(look, **changes) if changes else look


def resolve_popup_look(values, addon) -> PopupLook:
    """The look the popup is drawn with: the chosen look plus the user's own choices."""
    values = values or {}
    return look_with_overrides(resolve_look(values.get(KEY_LOOK), addon), values)
