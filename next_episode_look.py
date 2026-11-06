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

from dataclasses import dataclass
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
