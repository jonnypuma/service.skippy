# -*- coding: utf-8 -*-
"""The look of Skippy's own windows (everything except the skip dialog and the next episode popup).

One setting, ``modal_style``, chooses between five looks taken from the Aeon Fuse skin: Fused Glass
Dark, Frost (the default) and Clear, Aeon and Aeon Glass. A look is two things:

* textures (panel, inset box, row, focus, and the dim behind the window) named ``ms_<code>_<part>.png`` in the skin ``media``
  folder, written by ``tools/gen_modal_style_textures.py``. A button's textures cannot come from a
  window property in Kodi, so each styled window has one XML file per look: ``Name.xml`` is the
  Frost one (edit that), ``Name_<code>.xml`` are copies with the other texture prefix written by
  ``tools/gen_modal_style_variants.py``;
* colours (text, text on the focused row, shadows, the dim behind the window), which an XML file
  takes from window properties (``$INFO[Window.Property(ms_text)]``) set by :func:`apply`.

Windows drawn in Python (``skippy_editor_modal_skin.py``, the button discovery prompts) ask
:func:`texture` and :func:`color` for the same values.
"""
from __future__ import annotations

SETTING_KEY = "modal_style"
DEFAULT_STYLE = "fg_frost"

# stored setting value -> code used in file names; the order is the order in the settings list
STYLE_CODES = {
    "fg_dark": "fgd",
    "fg_frost": "fgf",
    "fg_clear": "fgc",
    "aeon": "aeo",
    "aeon_glass": "agl",
}
STYLE_NAMES = {
    "fg_dark": "Fused Glass - Dark",
    "fg_frost": "Fused Glass - Frost",
    "fg_clear": "Fused Glass - Clear",
    "aeon": "Aeon",
    "aeon_glass": "Aeon Glass",
}
DEFAULT_CODE = STYLE_CODES[DEFAULT_STYLE]
TEXTURE_PARTS = ("panel", "inset", "row", "focus", "dim")
# 9-slice borders the XML files use for those textures (texture pixels, the same at 720p and 1080i)
PANEL_BORDER = 28
ROW_BORDER = 14

# The windows that have one XML file per look.
STYLED_WINDOWS = (
    "SegmentEditorDialog.xml",
    "SegmentEditorDialogA.xml",
    "SegmentEditorDialogB.xml",
    "SegmentMarkerTypePicker.xml",
    "SegmentMarkerButtonDiscovery.xml",
    "SegmentTypesEditor.xml",
    "SourcePicker.xml",
    "SkippyPanel.xml",
    "SkipDialogCustomize.xml",
    "NextEpisodeCustomize.xml",
)

_INK = "FF0F1115"
_COLORS = {
    # text: labels on the panel; text2: secondary lines; text3: hints; text_focus: on the focused row
    "fg_dark": {
        "ms_text": "FFFFFFFF", "ms_text2": "FFB9BEC8", "ms_text3": "FF8A909C", "ms_text_focus": _INK,
        "ms_shadow": "00000000", "ms_dim": "B8050608", "ms_accent": "FFE8B04B",
    },
    "fg_frost": {
        "ms_text": "FFFFFFFF", "ms_text2": "FFDCE0E8", "ms_text3": "FFB4BAC6", "ms_text_focus": _INK,
        "ms_shadow": "66000000", "ms_dim": "8C050608", "ms_accent": "FFE8B04B",
    },
    "fg_clear": {
        "ms_text": "FFFFFFFF", "ms_text2": "FFD6DAE2", "ms_text3": "FFAEB4C0", "ms_text_focus": _INK,
        "ms_shadow": "99000000", "ms_dim": "73050608", "ms_accent": "FFE8B04B",
    },
    "aeon": {
        "ms_text": "FFFFFFFF", "ms_text2": "FFB3B3B3", "ms_text3": "FF808080", "ms_text_focus": "FF0B0B0B",
        "ms_shadow": "00000000", "ms_dim": "CC000000", "ms_accent": "FFFFFFFF",
    },
    "aeon_glass": {
        "ms_text": "FFFFFFFF", "ms_text2": "FFC8CCD4", "ms_text3": "FF9CA2AE", "ms_text_focus": "FFFFFFFF",
        "ms_shadow": "99000000", "ms_dim": "80000000", "ms_accent": "FFFFFFFF",
    },
}
COLOR_KEYS = tuple(_COLORS[DEFAULT_STYLE].keys())


def normalize(value) -> str:
    """A stored setting value as one of the five style keys (anything else is the default)."""
    key = str(value or "").strip().lower()
    return key if key in STYLE_CODES else DEFAULT_STYLE


def current_style(addon=None) -> str:
    """The style the user chose. Never raises: without an add-on or a readable setting it is the default."""
    try:
        if addon is None:
            import xbmcaddon  # late: unit tests load this module without Kodi

            addon = xbmcaddon.Addon()
        return normalize(addon.getSetting(SETTING_KEY))
    except Exception:
        return DEFAULT_STYLE


def code(style=None, addon=None) -> str:
    return STYLE_CODES[normalize(style) if style is not None else current_style(addon)]


def xml_name(base: str, style=None, addon=None) -> str:
    """The XML file of ``base`` for the chosen look: ``SkippyPanel.xml`` -> ``SkippyPanel_fgd.xml``.

    The default look and windows without styled copies keep their name.
    """
    if base not in STYLED_WINDOWS:
        return base
    style_code = code(style, addon)
    if style_code == DEFAULT_CODE:
        return base
    stem, ext = base[:-4], base[-4:]
    return "%s_%s%s" % (stem, style_code, ext)


def texture(part: str, style=None, addon=None) -> str:
    """File name of a texture of the chosen look (``panel``, ``inset``, ``row``, ``focus`` or ``dim``)."""
    if part not in TEXTURE_PARTS:
        raise ValueError("unknown texture part: %r" % (part,))
    return "ms_%s_%s.png" % (code(style, addon), part)


def colors(style=None, addon=None) -> dict:
    """Window property name -> AARRGGBB for the chosen look (a copy)."""
    key = normalize(style) if style is not None else current_style(addon)
    return dict(_COLORS[key])


def color(name: str, style=None, addon=None) -> str:
    return colors(style, addon)[name]


def properties(style=None, addon=None) -> dict:
    """Everything :func:`apply` sets on a window."""
    key = normalize(style) if style is not None else current_style(addon)
    props = dict(_COLORS[key])
    props["ms_style"] = key
    for part in TEXTURE_PARTS:
        props["ms_tex_%s" % part] = "ms_%s_%s.png" % (STYLE_CODES[key], part)
    return props


def apply(window, style=None, addon=None) -> str:
    """Set the look's window properties on ``window``; returns the style key. Never raises."""
    key = normalize(style) if style is not None else current_style(addon)
    for name, value in properties(key).items():
        try:
            window.setProperty(name, value)
        except Exception:
            pass
    return key
