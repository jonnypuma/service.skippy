# -*- coding: utf-8 -*-
"""Lazy-loaded Skip Dialog Customize modal (draft settings + frozen mockup)."""
from __future__ import annotations

import skip_dialog_card
import skip_layouts
import skippy_modal_style
import os

import xbmcgui
import xbmcvfs

from addon_skin_resolution import (
    FULL_SKIP_PROBE_ID,
    init_window_xml_dialog,
    reconcile_window_xml_skin_resolution,
    scale_skin_coord,
)
from settings_utils import (
    addon_get_bool,
    addon_get_int,
    addon_get_setting_text,
    get_addon,
    get_localized,
)
from settings_pending import with_pending
import skip_dialog_presets as sp
from skip_dialog_presets_ui import (
    present_preset_menu,
    preset_row_parts,
    prompt_save_preset,
)
from skip_dialog_appearance import (
    DIALOG_READY_PROP,
    ENDING_TEXT_ARGB,
    FULL_MOCK_W_720,
    FULL_SKIP_BUTTON_IDS,
    FULL_SKIP_PANEL_GROUP_ID,
    MINIMAL_MOCK_H_720,
    MINIMAL_PANEL_GROUP_ID,
    MINIMAL_PLATE_IMAGE_ID,
    MINIMAL_SKIP_BUTTON_ID,
    MOCK_INTRO_END,
    MOCK_PLAYHEAD,
    MOCK_SEGMENT_LABEL,
    display_segment_label,
    MOCK_STAGE_H_720,
    MOCK_STAGE_W_720,
    DictSettingsReader,
    apply_full_skip_layout,
    apply_minimal_skip_layout,
    apply_jump_label,
    apply_jump_properties,
    apply_mock_textures,
    apply_skip_dialog_caps,
    build_customize_mock_segment,
    build_skip_button_label,
    countdown_mmss,
    ending_text_for_segment,
    font_color_argb_from_settings,
    is_compact_combined,
    is_compact_full_mode,
    is_minimal_skip_mode,
    mock_corner_pos,
    set_skip_button_label,
    set_skip_info_label,
    skip_duration_for_playhead,
    skip_format_includes_duration,
)

ID_TITLE = 4090
ID_PANEL_BG = 4081
ID_MODE = 4100
ID_PRESET = 4140
ID_PREVIEW_TYPE = 4143
# The two pickers under the preview: the layout of the dialog and the look of a new layout.
ID_LAYOUT = skip_layouts.ID_PICK_LAYOUT
ID_LOOK = skip_layouts.ID_PICK_LOOK
# Only the Studio has a row for it (the classic screen has no room left): the colour of the progress.
ID_BAR_COLOR = 4147
# rows of the Studio only (the list screen has no room for them)
ID_OVERLAY = 4148
ID_APPEAR = 4149
ID_LEAVE = 4150
ID_PULSE = 4151
# rows of a drawn design (skip_canvas)
ID_CORNERS = 4152
ID_CV_CLOSE = 4153
ID_CV_ICONS = 4154
ID_CV_KICKER = 4155
ID_CV_NESTED = 4156
ID_CV_SHADOW = 4157
ID_CV_TEXT_SIZE = 4158
ID_CV_ZOOM = 4159
ID_CV_ACCENT = 4160
ID_CV_PROGRESS = 4161
ID_CV_GRADIENT = 4162
ID_CV_GRADIENT_TYPE = 4163
ID_CV_OUTLINE = 4164
ID_CV_DISTANCE = 4165
ID_CV_FOCUS = 4166
ID_CV_TIME = 4167
ID_CV_BACKGROUND = 4168  # Background: None, Fanart, Colour (the Studio's row; the classic screen has none)
ID_CV_BAR_EDGES = 4169  # Progress bar edges: Straight, Rounded
CANVAS_ROW_IDS = (ID_CORNERS, ID_CV_CLOSE, ID_CV_ICONS, ID_CV_KICKER, ID_CV_NESTED, ID_CV_SHADOW, ID_CV_TEXT_SIZE,
                  ID_CV_ZOOM, ID_CV_ACCENT, ID_CV_PROGRESS, ID_CV_GRADIENT, ID_CV_GRADIENT_TYPE, ID_CV_OUTLINE,
                  ID_CV_DISTANCE, ID_CV_FOCUS, ID_CV_TIME, ID_CV_BACKGROUND, ID_CV_BAR_EDGES)
BACKGROUND_NAMES = (("None", 49052, "None"), ("Fanart", 49039, "Fanart"), ("Colour", 49228, "Colour"))
BAR_EDGE_NAMES = (("Straight", 49231, "Straight"), ("Rounded", 49076, "Rounded"))
FOCUS_NAMES = (("Skip", 40000, "Skip"), ("Close", 40001, "Close"))
OUTLINE_NAMES = (("Off", 49088, "Off"), ("Light", 49161, "Light"), ("Medium", 49090, "Medium"), ("Strong", 49091, "Strong"))
DISTANCE_MAX, DISTANCE_STEP = 160, 8  # Distance from the edge, in pixels of a 1080 screen
ZOOM_NAMES = (("70", 49095, "Small"), ("85", 49090, "Medium"), ("100", 49097, "Large"))
ACCENT_NAMES = (("Auto", 49103, "The bar colour setting"), ("Gold", 49104, "Gold"), ("Blue", 49105, "Blue"),
                ("Red", 49106, "Red"), ("Green", 49107, "Green"), ("Teal", 49108, "Teal"), ("Purple", 49109, "Purple"),
                ("White", 49110, "White"))
PROGRESS_NAMES = (("Auto", 49085, "The design's own"), ("Line", 49113, "Line"), ("Circle", 49114, "Circle"),
                  ("Fill", 49115, "Fill"))
GRADIENT_NAMES = (("Auto", 49120, "Away from the dialog"), ("Vertical", 49121, "Top to bottom"),
                  ("Horizontal", 49122, "Side to side"), ("Radial", 49123, "Round"))
# rows that pick one of a list: row id -> (draft key, names, default, label string id, label)
CANVAS_CHOICES = {
    ID_CV_ZOOM: ("skip_canvas_zoom", ZOOM_NAMES, "100", 49099, "Size on screen"),
    ID_CV_ACCENT: ("skip_canvas_accent", ACCENT_NAMES, "Auto", 49101, "Accent colour"),
    ID_CV_PROGRESS: ("skip_canvas_progress", PROGRESS_NAMES, "Auto", 49111, "Progress style"),
    ID_CV_GRADIENT_TYPE: ("skip_canvas_gradient", GRADIENT_NAMES, "Auto", 49118, "Gradient direction"),
    ID_CV_FOCUS: ("skip_canvas_focus", FOCUS_NAMES, "Skip", 49130, "Button the focus starts on"),
    ID_CV_OUTLINE: ("skip_canvas_outline", OUTLINE_NAMES, "Medium", 49124, "Text outline"),
    ID_CV_BACKGROUND: ("skip_canvas_background", BACKGROUND_NAMES, "None", 49227, "Background"),
    ID_CV_BAR_EDGES: ("skip_canvas_bar_edges", BAR_EDGE_NAMES, "Straight", 49230, "Progress bar edges"),
}
TEXT_SHADOW_NAMES = (("Off", 49088, "Off"), ("Mild", 49089, "Mild"), ("Medium", 49090, "Medium"),
                     ("Strong", 49091, "Strong"), ("Heavy", 49092, "Heavy"))
TEXT_SIZE_NAMES = (("85", 49095, "Small"), ("100", 49096, "Standard"), ("115", 49097, "Large"), ("130", 49098, "Larger"))
ID_CARD = 4141
ID_OPACITY = 4142
ID_HIDE_ENDING = 4101
ID_FONT = 4102
ID_OVERLAP = 4103
ID_ALL_CAPS = 4104
ID_FULL_HEADER = 4110
ID_PROGRESS = 4111
ID_COUNTDOWN = 4112
ID_HEIGHT = 4113
ID_PROGRESS_STYLE = 4114
ID_POSITION = 4115
ID_FOCUS_STYLE = 4116
ID_SKIP_FORMAT = 4117
ID_HIDE_CLOSE = 4118
ID_FOCUS_FRAME = 4119
ID_HIDE_ICONS = 4120
ID_COMBINED = 4121
ID_DURATION_FORMAT = 4122
ID_DURATION_CONTENT = 4123
ID_MIN_HEADER = 4130
ID_PLATE = 4131
ID_MIN_FORMAT = 4132
ID_MIN_POSITION = 4133
ID_SAVE = 4190
ID_CANCEL = 4191
ID_FANART = 4071
ID_CLOSE_MOCK = 3013

_CANCEL_ACTIONS = (10, 92, 216)
_MOVE_LEFT = getattr(xbmcgui, "ACTION_MOVE_LEFT", 1)
_MOVE_RIGHT = getattr(xbmcgui, "ACTION_MOVE_RIGHT", 2)
_MOVE_UP = getattr(xbmcgui, "ACTION_MOVE_UP", 3)
_MOVE_DOWN = getattr(xbmcgui, "ACTION_MOVE_DOWN", 4)

MODES = ("Full", "CompactFull", "Minimal")
MODE_LABELS = (
    ("Full", "Full"),
    ("Compact Full", "CompactFull"),
    ("Minimal", "Minimal"),
)
SKIP_FORMATS = ("Skip", "Skip + Type", "Skip + Type + Duration")
DURATION_FORMATS = (
    ("1m30s", "1m30s"),
    ("01:30", "mm:ss"),
)
DURATION_CONTENTS = (
    ("Total segment time", "total"),
    ("Elapsed (count up)", "elapsed_up"),
    ("Remaining (count down)", "elapsed_down"),
    ("Elapsed / Total", "elapsed_total"),
)
POSITIONS = (
    ("Bottom Right", "BottomRight"),
    ("Top Right", "TopRight"),
    ("Top Left", "TopLeft"),
    ("Bottom Left", "BottomLeft"),
)
FONT_COLORS = (
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
BUTTON_FOCUS = (
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
    ("Fuse Square", "button_focus_fuse_square.png"),
    ("Fuse Glass", "button_focus_fuse_glass.png"),
    ("Fuse Bar", "button_focus_fuse_bar.png"),
)
MINIMAL_PLATES = (
    ("Rounded Gray", "minimal_rounded_gray_640.png"),
    ("Rectangular Aquamarine Blue", "minimal_rectangular_aquamarine-blue_640.png"),
    ("Rectangular Blue", "minimal_rectangular_blue_640.png"),
    ("Rectangular Yellow", "minimal_rectangular_yellow_640.png"),
    ("Blue 3D", "minimal_3d_blue.png"),
    ("Glossy Blue 3D", "minimal_3d_glossy_blue.png"),
    ("Red Glossy 3D", "minimal_3d_red_glossy.png"),
    ("Black Beveled", "minimal_black_beveled.png"),
    ("Rounded Baby Purple", "minimal_rounded_baby-purple_640.png"),
    ("Rounded Blue Red Gradient", "minimal_rounded_blue-red-gradient_640.png"),
    ("Rounded Bright Aqua", "minimal_rounded_bright-aqua_640.png"),
    ("Rounded Bright Blue Sky", "minimal_rounded_bright-blue-sky_640.png"),
    ("Rounded Bright Cyan", "minimal_rounded_bright-cyan_640.png"),
    ("Rounded Burnt Pink", "minimal_rounded_burnt-pink_640.png"),
    ("Rounded Cranberry", "minimal_rounded_cranberry_640.png"),
    ("Rounded Deep Pink", "minimal_rounded_deep-pink_640.png"),
    ("Rounded Greyish Blue", "minimal_rounded_greyish-blue_640.png"),
    ("Rounded Languid Lavender", "minimal_rounded_languid-lavender_640.png"),
    ("Rounded Light Green 7284348", "minimal_rounded_light-green-7284348_640.png"),
    ("Rounded Light Grey", "minimal_rounded_light-grey_640.png"),
    ("Rounded Light Yellow", "minimal_rounded_light-yellow_640.png"),
    ("Rounded Minty Green", "minimal_rounded_minty-green_640.png"),
    ("Rounded Mustard Yellow", "minimal_rounded_mustard-yellow_640.png"),
    ("Rounded Pale Gold", "minimal_rounded_pale-gold_640.png"),
    ("Rounded Pale Sky Blue", "minimal_rounded_pale-sky-blue_640.png"),
    ("Rounded Pastel Green", "minimal_rounded_pastel-green_640.png"),
    ("Rounded Pattens Blue", "minimal_rounded_pattens-blue_640.png"),
    ("Rounded Peach Orange", "minimal_rounded_peach-orange_640.png"),
    ("Rounded Pink Daisy", "minimal_rounded_pink-daisy_640.png"),
    ("Rounded Pink Lemonade", "minimal_rounded_pink-lemonade_640.png"),
    ("Rounded Pinkish Orange", "minimal_rounded_pinkish-orange_640.png"),
    ("Rounded Sunset", "minimal_rounded_sunset_640.png"),
    ("Rounded White", "minimal_rounded_white_640.png"),
    ("Flat Black", "minimal_flat_black_640.png"),
    ("Flat Charcoal", "minimal_flat_charcoal_640.png"),
    ("Flat White", "minimal_flat_white_640.png"),
    ("Flat Blue", "minimal_flat_blue_640.png"),
    ("Flat Teal", "minimal_flat_teal_640.png"),
    ("Flat Rose", "minimal_flat_rose_640.png"),
    ("Glass Dark", "minimal_glass_dark_640.png"),
    ("Glass Light", "minimal_glass_light_640.png"),
    ("Outline White", "minimal_outline_white_640.png"),
    ("Gradient Midnight", "minimal_grad_midnight_640.png"),
    ("Gradient Sunset", "minimal_grad_sunset_640.png"),
    ("Pastel Mint", "minimal_pastel_mint_640.png"),
    ("Pastel Peach", "minimal_pastel_peach_640.png"),
    ("Pastel Lavender", "minimal_pastel_lavender_640.png"),
    ("Brushed Steel", "minimal_steel_640.png"),
    ("Frosted", "minimal_frosted_640.png"),
    ("Gold Leaf", "minimal_gold_640.png"),
    ("Neon Cyan", "minimal_neon_cyan_640.png"),
    ("Fuse Dark", "minimal_fuse_dark_640.png"),
    ("Fuse Frost", "minimal_fuse_frost_640.png"),
    ("Fuse Clear", "minimal_fuse_clear_640.png"),
    ("Fuse Square", "minimal_fuse_square_640.png"),
    ("Fuse Grid", "minimal_fuse_grid_640.png"),
    ("Fuse Glass", "minimal_fuse_glass_640.png"),
)
PROGRESS_STYLES = (
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
    ("Fuse Gold", "progress_mid_fuse_gold.png"),
    ("Fuse White", "progress_mid_fuse_white.png"),
)
# The Card row: no card, or one of the shapes of the card (skip_dialog_card.STYLES).
CARD_OFF = "Off"
CARD_CHOICES = (CARD_OFF,) + tuple(stored for _name, stored in skip_dialog_card.options())


def card_choice(draft) -> str:
    """What the Card row shows: ``Off``, or the stored card style."""
    if not draft.get("skip_card_enabled", True):
        return CARD_OFF
    return skip_dialog_card.normalize(draft.get("skip_card_style"))


def set_card_choice(draft, choice) -> None:
    """Store a choice of the Card row. Switching the card off keeps the style for next time."""
    if choice == CARD_OFF:
        draft["skip_card_enabled"] = False
        return
    draft["skip_card_enabled"] = True
    draft["skip_card_style"] = skip_dialog_card.normalize(choice)

DRAFT_BOOL_KEYS = (
    "hide_ending_text",
    "skip_overlapping_segments",
    "show_progress_bar",
    "progress_bar_countdown",
    "hide_close_button",
    "show_skip_button_focus_texture",
    "hide_skip_icon",
    "skip_dialog_all_caps",
    "smooth_progress_bar",
    "compact_full_combined",
    "skip_card_enabled",
    skip_layouts.KEY_PULSE,
    "skip_canvas_close",
    "skip_canvas_icons",
    "skip_canvas_kicker",
    "skip_canvas_nested",
    "skip_canvas_overlay_gradient",
    "skip_canvas_time",
)
DRAFT_TEXT_KEYS = (
    "skip_dialog_mode",
    "skip_dialog_font_color",
    "skip_dialog_position",
    "button_focus_style",
    "skip_button_format",
    "skip_duration_format",
    "skip_duration_content",
    "minimal_button_style",
    "minimal_skip_button_format",
    "minimal_skip_dialog_position",
    "progress_bar_style",
    "skip_card_style",
    skip_layouts.KEY_LAYOUT,
    skip_layouts.KEY_LOOK,
    skip_layouts.KEY_BAR_COLOR,
    skip_layouts.KEY_OVERLAY,
    skip_layouts.KEY_APPEAR,
    skip_layouts.KEY_LEAVE,
    "skip_canvas_corners",
    "skip_canvas_text_shadow",
    "skip_canvas_text_size",
    "skip_canvas_zoom",
    "skip_canvas_accent",
    "skip_canvas_progress",
    "skip_canvas_gradient",
    "skip_canvas_focus",
    "skip_canvas_outline",
    "skip_canvas_place",
    "skip_canvas_background",
    "skip_canvas_bar_edges",
)
DRAFT_INT_KEYS = (
    ("skip_canvas_distance", 64, 0, 160),
    ("progress_bar_height", 16, 5, 32),
    ("skip_card_opacity", 95, 0, 100),
)

_TEXT_DEFAULTS = {
    "skip_dialog_mode": "CompactFull",
    "skip_dialog_font_color": "FFFFFFFF",
    "skip_dialog_position": "BottomRight",
    "button_focus_style": "button_focus_flat_teal.png",
    "skip_button_format": "Skip + Type",
    "skip_duration_format": "1m30s",
    "skip_duration_content": "total",
    "minimal_button_style": "minimal_rounded_gray_640.png",
    "minimal_skip_button_format": "Skip + Type",
    "minimal_skip_dialog_position": "BottomRight",
    "progress_bar_style": "progress_mid.png",
    "skip_card_style": skip_dialog_card.STYLE_FLAT,
    skip_layouts.KEY_LAYOUT: skip_layouts.DEFAULT_LAYOUT,
    skip_layouts.KEY_LOOK: skip_layouts.DEFAULT_SKIP_LOOK,
    skip_layouts.KEY_BAR_COLOR: skip_layouts.BAR_TYPE,
    skip_layouts.KEY_OVERLAY: skip_layouts.OVERLAY_AUTO,
    skip_layouts.KEY_APPEAR: skip_layouts.APPEARS[0],
    skip_layouts.KEY_LEAVE: skip_layouts.LEAVES[0],
    "skip_canvas_corners": "Skin",
    "skip_canvas_text_shadow": "Mild",
    "skip_canvas_text_size": "100",
    "skip_canvas_zoom": "100",
    "skip_canvas_accent": "Auto",
    "skip_canvas_progress": "Auto",
    "skip_canvas_gradient": "Auto",
    "skip_canvas_focus": "Skip",
    "skip_canvas_outline": "Medium",
    "skip_canvas_place": "",
    "skip_canvas_background": "None",
    "skip_canvas_bar_edges": "Straight",
}
_BOOL_DEFAULTS = {
    "hide_ending_text": False,
    "skip_overlapping_segments": True,
    "show_progress_bar": True,
    "progress_bar_countdown": False,
    "hide_close_button": True,
    "show_skip_button_focus_texture": True,
    "hide_skip_icon": False,
    "skip_dialog_all_caps": True,
    "smooth_progress_bar": True,
    "compact_full_combined": True,
    "skip_card_enabled": True,
    skip_layouts.KEY_PULSE: False,
    "skip_canvas_close": True,
    "skip_canvas_icons": True,
    "skip_canvas_kicker": True,
    "skip_canvas_nested": True,
    "skip_canvas_overlay_gradient": False,
    "skip_canvas_time": True,
}


def load_skip_dialog_draft(addon) -> dict:
    draft = {}
    for key in DRAFT_TEXT_KEYS:
        draft[key] = (
            addon_get_setting_text(addon, key, _TEXT_DEFAULTS[key]) or _TEXT_DEFAULTS[key]
        ).strip()
    for key in DRAFT_BOOL_KEYS:
        draft[key] = addon_get_bool(addon, key, _BOOL_DEFAULTS[key])
    for key, default, minimum, maximum in DRAFT_INT_KEYS:
        draft[key] = addon_get_int(addon, key, default, minimum=minimum, maximum=maximum)
    return draft


def draft_setting_payload(draft: dict) -> dict:
    """Convert a draft dict to Kodi setSetting strings."""
    out = {}
    for key in DRAFT_TEXT_KEYS:
        out[key] = str(draft.get(key, _TEXT_DEFAULTS[key]))
    for key in DRAFT_BOOL_KEYS:
        out[key] = "true" if draft.get(key, _BOOL_DEFAULTS[key]) else "false"
    for key, default, minimum, maximum in DRAFT_INT_KEYS:
        val = int(draft.get(key, default))
        val = max(minimum, min(maximum, val))
        out[key] = str(val)
    return out


def _cycle(options, current, delta):
    items = list(options)
    if not items:
        return current
    try:
        idx = items.index(current)
    except ValueError:
        idx = 0
    return items[(idx + delta) % len(items)]


def _pair_label(pairs, stored):
    for label, value in pairs:
        if value == stored:
            return label
    return stored


def canvas_distance(value) -> int:
    """Distance from the edge as stored (a text), in pixels of a 1080 screen."""
    try:
        return max(0, min(DISTANCE_MAX, int(float(value))))
    except (TypeError, ValueError):
        return 64


def preview_type_ids():
    """Segment type ids the preview can show, in catalog order (Commercial always first-class)."""
    ids = []
    try:
        from segment_types import get_types

        for entry in get_types():
            sid = str((entry.get("id") if isinstance(entry, dict) else "") or "").strip()
            if sid and sid not in ids:
                ids.append(sid)
    except Exception:
        pass
    if MOCK_SEGMENT_LABEL not in ids:
        ids.append(MOCK_SEGMENT_LABEL)
    return ids


def draft_layout(draft: dict):
    """The layout file the draft asks for, or None for the classic card."""
    mode = draft.get("skip_dialog_mode") or "Full"
    name = skip_layouts.normalize_layout(draft.get(skip_layouts.KEY_LAYOUT))
    if skip_layouts.is_card(name):
        return None
    return skip_layouts.get(name, skip_layouts.size_for_mode(mode))


def customize_picker_ids(draft: dict):
    """The pickers outside the row list, in focus order: preview type, layout, and the look of a
    new layout."""
    ids = [ID_PREVIEW_TYPE, ID_LAYOUT]
    if draft_layout(draft) is not None:
        ids.append(ID_LOOK)
    return ids


def customize_nav_ids(draft: dict):
    """Visible left-pane control order. XML onup/ondown are self-bound so this is the only mover."""
    if draft_layout(draft) is not None:
        # A new layout has its look; the card's own rows (and the presets) do not apply to it.
        ids = [ID_PRESET, ID_MODE, ID_OVERLAP, ID_COUNTDOWN, ID_POSITION, ID_SKIP_FORMAT]
        if skip_format_includes_duration(draft.get("skip_button_format") or "Skip + Type + Duration"):
            ids.extend([ID_DURATION_FORMAT, ID_DURATION_CONTENT])
        return ids + [ID_SAVE, ID_CANCEL]
    ids = [ID_PRESET, ID_MODE]
    mode = draft.get("skip_dialog_mode") or "Full"
    minimal = is_minimal_skip_mode(mode)
    compact = is_compact_full_mode(mode)
    combined = (not minimal) and bool(draft.get("compact_full_combined"))
    if not minimal and not compact:
        ids.append(ID_HIDE_ENDING)
    ids.extend([ID_FONT, ID_ALL_CAPS])
    if not minimal and not compact:
        ids.append(ID_CARD)
        if draft.get("skip_card_enabled", True):
            ids.append(ID_OPACITY)
    if not minimal:
        ids.append(ID_OVERLAP)
        ids.append(ID_COMBINED)
        if not combined:
            ids.extend(
                [
                    ID_PROGRESS,
                    ID_COUNTDOWN,
                    ID_PROGRESS_STYLE,
                ]
            )
            if not compact:
                ids.append(ID_HEIGHT)
        else:
            ids.append(ID_COUNTDOWN)
        ids.extend(
            [
                ID_POSITION,
                ID_FOCUS_STYLE,
                ID_SKIP_FORMAT,
            ]
        )
        if skip_format_includes_duration(draft.get("skip_button_format") or "Skip + Type + Duration"):
            ids.extend([ID_DURATION_FORMAT, ID_DURATION_CONTENT])
        if not combined:
            ids.append(ID_HIDE_CLOSE)
            if not compact:
                ids.append(ID_HIDE_ICONS)
            if draft.get("hide_close_button"):
                ids.append(ID_FOCUS_FRAME)
        elif not compact:
            ids.append(ID_HIDE_ICONS)
    else:
        ids.extend([ID_PLATE, ID_MIN_FORMAT, ID_MIN_POSITION])
        if skip_format_includes_duration(draft.get("minimal_skip_button_format") or "Skip + Type"):
            ids.extend([ID_DURATION_FORMAT, ID_DURATION_CONTENT])
    ids.extend([ID_SAVE, ID_CANCEL])
    return ids


def customize_section_header_before(nav_ids):
    """Insert Full/Minimal section headers before these packed row ids.

    Combined sits with global options (after Ignore overlapping). The Full
    header must not land between those two rows, or Combined jumps under
    Full-mode options when the progress rows hide.
    """
    starts = set()
    if ID_PLATE in nav_ids:
        starts.add(ID_PLATE)
    if ID_PROGRESS in nav_ids:
        starts.add(ID_PROGRESS)
    elif ID_COUNTDOWN in nav_ids:
        starts.add(ID_COUNTDOWN)
    elif ID_POSITION in nav_ids:
        starts.add(ID_POSITION)
    return starts


def customize_left_pane_layout(nav_ids, sc):
    """Pack the rows under the heading and the buttons right below them, as the next episode modal does.

    ``row_h`` is the step from one row to the next (it shrinks, down to a minimum, when there are
    more rows than the screen has room for); each row is drawn ``row_gap`` shorter than that, so the
    tinted rows do not touch. ``panel_h`` is the height of the panel behind it all and never goes
    beyond the room the screen has for it.
    """
    ids = [cid for cid in nav_ids if cid not in (ID_SAVE, ID_CANCEL)]
    starts = customize_section_header_before(ids)
    n_headers = sum(1 for cid in ids if cid in starts)
    left = sc(16)
    row_w = sc(468)
    start_y = sc(52)
    header_h = sc(24)
    save_h = sc(40)
    max_panel_h = sc(688)
    bottom_pad = sc(16)
    gap = sc(10)
    default_row = sc(34)
    min_row = sc(26)
    budget = max_panel_h - bottom_pad - save_h - gap - start_y - n_headers * header_h
    row_h = default_row
    if ids:
        if budget > 0:
            row_h = min(default_row, max(min_row, budget // len(ids)))
        else:
            row_h = min_row
    row_gap = sc(4) if row_h >= sc(30) else sc(2)
    content_bottom = start_y + n_headers * header_h + len(ids) * row_h
    save_y = content_bottom + gap
    save_w = (row_w - sc(10)) // 2
    return {
        "ids": ids,
        "starts": starts,
        "left": left,
        "start_y": start_y,
        "header_h": header_h,
        "row_h": row_h,
        "row_gap": row_gap,
        "button_h": row_h - row_gap,
        "save_y": save_y,
        "save_h": save_h,
        "save_w": save_w,
        "cancel_x": left + row_w - save_w,
        "gap": gap,
        "content_bottom": content_bottom,
        "panel_h": save_y + save_h + bottom_pad,
    }


def _yes_no(addon, flag):
    return get_localized(addon, 44105, "Yes") if flag else get_localized(addon, 44106, "No")


class SkipDialogCustomize(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        skippy_modal_style.apply(self)  # before the window shows
        self._skin_resolution = init_window_xml_dialog(super(SkipDialogCustomize, self), args)
        self.addon = kwargs.get("addon") or with_pending(get_addon())
        self._draft = kwargs.get("draft") or load_skip_dialog_draft(self.addon)
        self._original = dict(kwargs.get("original") or self._draft)
        self._saved = False
        self._closing = False
        self._preview_type = MOCK_SEGMENT_LABEL

    def _mock_lock(self):
        """One drawing of the preview at a time (the Studio also draws it from the thread that plays it)."""
        import threading

        lock = getattr(self, "_mock_guard", None)
        if lock is None:
            lock = self._mock_guard = threading.RLock()
        return lock

    def _mock_nested(self, settings) -> bool:
        """Whether the preview shows a segment inside another: the Studio can ask for it (its Nested
        preview); otherwise it follows the overlap setting."""
        asked = getattr(self, "_preview_nested", None)
        return settings.get_bool("skip_overlapping_segments", True) if asked is None else bool(asked)

    def _sc(self, value):
        return scale_skin_coord(value, getattr(self, "_skin_resolution", None))

    def _ctrl(self, cid):
        try:
            return self.getControl(cid)
        except Exception:
            return None

    def _set_row(self, cid, name, value):
        """A row shows its name at the left and its value at the right, as in the next episode modal."""
        ctrl = self._ctrl(cid)
        if ctrl:
            try:
                ctrl.setLabel(label=name, label2=str(value))
            except Exception:
                pass

    def _set_label(self, cid, text):
        ctrl = self._ctrl(cid)
        if ctrl:
            try:
                ctrl.setLabel(text)
            except Exception:
                pass

    def onInit(self):
        skippy_modal_style.apply(self)
        asked = getattr(self, "_skin_resolution", None)
        locked = reconcile_window_xml_skin_resolution(
            self, asked, control_ids=(FULL_SKIP_PROBE_ID,)
        )
        if locked != asked:
            self._skin_resolution = locked
        self._set_label(ID_TITLE, get_localized(self.addon, 44102, "Customize skip dialog"))
        self._set_label(ID_SAVE, get_localized(self.addon, 44103, "Save"))
        self._set_label(ID_CANCEL, get_localized(self.addon, 44104, "Cancel"))
        self._set_label(ID_FULL_HEADER, get_localized(self.addon, 32021, "Full mode"))
        self._set_label(ID_MIN_HEADER, get_localized(self.addon, 32022, "Minimal mode"))
        self._load_fanart()
        self.refresh_mockup()
        try:
            self.setFocusId(ID_PRESET if ID_PRESET in self._nav_ids() else ID_MODE)
        except Exception:
            pass

    def _load_fanart(self):
        ctrl = self._ctrl(ID_FANART)
        if not ctrl or not self.addon:
            return
        path = os.path.join(self.addon.getAddonInfo("path") or "", "fanart.png")
        if xbmcvfs.exists(path):
            try:
                ctrl.setImage(path)
            except Exception:
                pass

    def _nav_ids(self):
        return customize_nav_ids(self._draft)

    def _focus_id(self):
        try:
            return int(self.getFocusId())
        except Exception:
            return ID_MODE

    def _move_focus(self, delta):
        # The preview-type picker sits in the header, one step above the Preset row.
        ids = customize_picker_ids(self._draft) + list(self._nav_ids())
        current = self._focus_id()
        if current not in ids:
            current = ids[0]
        nxt = ids[(ids.index(current) + delta) % len(ids)]
        try:
            self.setFocusId(nxt)
        except Exception:
            pass

    def refresh_mockup(self):
        settings = DictSettingsReader(self._draft)
        addon = self.addon
        layout = draft_layout(self._draft)
        self.setProperty("skl_mock", layout.xml[:-4] if layout is not None else "")
        card_group = self._ctrl(FULL_SKIP_PANEL_GROUP_ID)
        if card_group:
            try:
                card_group.setVisible(layout is None)
            except Exception:
                pass
        pickers = customize_picker_ids(self._draft)
        for cid in (ID_LAYOUT, ID_LOOK):
            picker = self._ctrl(cid)
            if picker:
                try:
                    picker.setVisible(cid in pickers)
                except Exception:
                    pass
        if layout is not None:
            try:
                self._refresh_layout_mock(settings, layout)
            except Exception:
                pass
            # The Minimal form of a layout is a preview copy like the others: the chip of the classic
            # Minimal mode (shown while this property says Minimal) stays away.
            mode_text = settings.get_text("skip_dialog_mode", "Full").strip() or "Full"
            self.setProperty("skippy_customize_mode", "Full" if layout.size == skip_layouts.SIZE_MINIMAL else mode_text)
            self._set_label(
                ID_FULL_HEADER,
                get_localized(addon, 32100, "Compact Full")
                if layout.size == skip_layouts.SIZE_COMPACT
                else get_localized(addon, 32022, "Minimal mode")
                if layout.size == skip_layouts.SIZE_MINIMAL
                else get_localized(addon, 32021, "Full mode"),
            )
            self.setProperty(DIALOG_READY_PROP, "true")
            self._layout_left_pane()
            self._refresh_row_labels()
            return
        mode = settings.get_text("skip_dialog_mode", "Full").strip() or "Full"
        minimal = is_minimal_skip_mode(mode)
        compact = is_compact_full_mode(mode)
        combined = is_compact_combined(settings)
        self.setProperty("skippy_customize_mode", mode)
        self.setProperty("skippy_compact_full", "true" if compact else "false")
        hide_end = settings.get_bool("hide_ending_text", False)
        hide_close = True if combined else settings.get_bool("hide_close_button", False)
        hide_icon = settings.get_bool("hide_skip_icon", False)
        if compact:
            hide_end = True
            hide_icon = True
        self.setProperty(
            "skippy_customize_hide_close",
            "true" if hide_close else "false",
        )
        self.setProperty("hide_ending_text", "true" if hide_end else "false")
        self.setProperty("hide_close_button", "true" if hide_close else "false")
        self.setProperty("hide_skip_icon", "true" if hide_icon else "false")
        if compact:
            self._set_label(ID_FULL_HEADER, get_localized(addon, 32100, "Compact Full"))
        else:
            self._set_label(ID_FULL_HEADER, get_localized(addon, 32021, "Full mode"))

        segment = build_customize_mock_segment(
            self._mock_nested(settings),
            getattr(self, "_preview_type", MOCK_SEGMENT_LABEL),
        )
        color = font_color_argb_from_settings(settings)
        self.setProperty("skip_dialog_text_color", color)
        duration_str = skip_duration_for_playhead(MOCK_PLAYHEAD, segment, settings)
        if minimal:
            fmt = settings.get_text("minimal_skip_button_format", "Skip + Type")
        else:
            fmt = settings.get_text("skip_button_format", "Skip + Type + Duration")
        self.setProperty(
            "skippy_customize_duration",
            "true" if skip_format_includes_duration(fmt) else "false",
        )
        skip_label = apply_skip_dialog_caps(
            build_skip_button_label(segment, fmt, duration_str, addon),
            settings.get_bool("skip_dialog_all_caps", False),
        )
        for cid in FULL_SKIP_BUTTON_IDS:
            set_skip_button_label(self._ctrl(cid), skip_label, color)
        set_skip_button_label(self._ctrl(MINIMAL_SKIP_BUTTON_ID), skip_label, color)
        close_lbl = apply_skip_dialog_caps(
            get_localized(addon, 40001, "Close"),
            settings.get_bool("skip_dialog_all_caps", False),
        )
        set_skip_button_label(self._ctrl(ID_CLOSE_MOCK), close_lbl, color)

        all_caps = settings.get_bool("skip_dialog_all_caps", False)
        self.setProperty(
            "ending_text",
            apply_skip_dialog_caps(ending_text_for_segment(addon, segment), all_caps),
        )
        remaining = MOCK_INTRO_END - MOCK_PLAYHEAD
        self.setProperty("countdown", countdown_mmss(remaining))
        apply_jump_properties(self, addon, segment, all_caps=all_caps)
        if self.getProperty("show_next_jump") == "true":
            apply_jump_label(self, self.getProperty("next_jump_label") or "")
        end_ctrl = self._ctrl(2)
        if end_ctrl and not hide_end:
            line = "%s %s" % (
                self.getProperty("ending_text") or "",
                self.getProperty("countdown") or "",
            )
            set_skip_info_label(end_ctrl, line.strip(), ENDING_TEXT_ARGB, font="font10")

        panel_h = self._sc(100)
        if not minimal:
            panel_h = apply_full_skip_layout(
                self,
                settings,
                playhead=MOCK_PLAYHEAD,
                segment=segment,
                scale_fn=self._sc,
                place_focus_overlays=True,
                addon=addon,
            ) or panel_h

        stage_w = self._sc(MOCK_STAGE_W_720)
        stage_h = self._sc(MOCK_STAGE_H_720)
        if minimal:
            corner = settings.get_text("minimal_skip_dialog_position", "BottomRight")
            plate_w = apply_minimal_skip_layout(
                self,
                settings,
                segment,
                self._sc,
                addon=addon,
                group_id=MINIMAL_PANEL_GROUP_ID,
                plate_ids=(MINIMAL_PLATE_IMAGE_ID, 5040),
                button_id=MINIMAL_SKIP_BUTTON_ID,
                place_panel=False,
            )
            x, y = mock_corner_pos(
                corner,
                stage_w,
                stage_h,
                plate_w,
                self._sc(MINIMAL_MOCK_H_720),
            )
            grp = self._ctrl(MINIMAL_PANEL_GROUP_ID)
            if grp:
                grp.setPosition(x, y)
        else:
            corner = settings.get_text("skip_dialog_position", "BottomRight")
            x, y = mock_corner_pos(
                corner,
                stage_w,
                stage_h,
                int(getattr(self, "_skip_panel_w", self._sc(FULL_MOCK_W_720))),
                int(panel_h),
            )
            grp = self._ctrl(FULL_SKIP_PANEL_GROUP_ID)
            if grp:
                grp.setPosition(x, y)

        apply_mock_textures(self, settings, minimal)
        self.setProperty(DIALOG_READY_PROP, "true")
        self._layout_left_pane()
        self._refresh_row_labels()

    def _mock_stage(self):
        """Where the small screen of the preview sits on this window and how small it is drawn:
        ``(left, top, zoom percent)`` in the units of the skin folder in use."""
        return (self._sc(skip_layouts.STAGE_LEFT + skip_layouts.MOCK_LEFT),
                self._sc(skip_layouts.STAGE_TOP + skip_layouts.MOCK_TOP), skip_layouts.MOCK_ZOOM)

    def _refresh_canvas_mock(self, settings, layout):
        """The preview of a drawn design: the same drawing as the real dialog, small, on the stage."""
        import skip_canvas as cv
        import skip_canvas_dialog as cvd
        import skip_canvas_draw as cvdraw
        from skip_layout_dialog import layout_accent, texts as layout_texts
        from smooth_progress import segment_percent

        addon = self.addon
        code = skip_layouts.normalize_look(self._draft.get(skip_layouts.KEY_LOOK))
        position = settings.get_text("skip_dialog_position", "BottomRight")
        segment = build_customize_mock_segment(
            self._mock_nested(settings),
            getattr(self, "_preview_type", MOCK_SEGMENT_LABEL),
        )
        found = layout_texts(addon, segment, MOCK_PLAYHEAD, False, settings=settings)
        nested = apply_jump_properties(self, addon, segment, all_caps=False)
        countdown = settings.get_bool("progress_bar_countdown", False)
        percent = segment_percent(MOCK_PLAYHEAD, segment.start_seconds, segment.end_seconds, countdown)
        duration = ""
        if settings.get_bool("skip_canvas_time", True):
            duration = cvd.short_clock(skip_duration_for_playhead(MOCK_PLAYHEAD, segment, settings) or "")
        options = cvd.options_from(settings.get_text, settings.get_bool, layout, code, position,
                                   layout_accent(addon, code, segment, settings=settings))
        texts = cvd.texts_from(found, countdown_mmss(MOCK_INTRO_END - MOCK_PLAYHEAD), nested, duration, percent or 0.0)
        # Background Fanart in the preview: the Studio's own picture stands in for the show's
        texts.fanart = os.path.join(addon.getAddonInfo("path") or "", "fanart.png")
        if getattr(self, "_mock_canvas", None) is None:
            resolution = getattr(self, "_skin_resolution", None) or "1080i"
            folder = "720" if str(resolution).startswith("720") else "1080"
            media = os.path.join(addon.getAddonInfo("path") or "", "resources", "skins", "default", "media")
            self._mock_canvas = cvdraw.Canvas(self, folder, media, offset=cv.MOCK_OFFSET, stage=self._mock_stage(),
                                              prefix="cv_mock")
        # what the preview is showing, for a screen that plays it (the Studio): the drawing can be made again
        self._mock_show = (options, texts, found.get("skl_heading", ""), found.get("skl_kicker", ""))
        if getattr(self, "_opening", False):
            return  # the Studio, as it opens: its preview thread draws this at once (see SkipStudio.onInit)
        with self._mock_lock():
            self._mock_canvas.draw(options, texts, animate=False)

    def _refresh_layout_mock(self, settings, layout):
        """Fill and place the preview copy of a layout (the small screen under ``skl_mock``)."""
        from skip_layout_dialog import layout_accent, texts as layout_texts
        from smooth_progress import segment_percent

        if getattr(layout, "canvas", False):
            self._refresh_canvas_mock(settings, layout)
            return
        if getattr(self, "_mock_canvas", None) is not None:
            self._mock_canvas.clear()

        addon = self.addon
        code = skip_layouts.normalize_look(self._draft.get(skip_layouts.KEY_LOOK))
        look = skip_layouts.look(code)
        offset = skip_layouts.mock_offset(skip_layouts.all_layouts().index(layout))
        position = settings.get_text("skip_dialog_position", "BottomRight")
        segment = build_customize_mock_segment(
            self._mock_nested(settings),
            getattr(self, "_preview_type", MOCK_SEGMENT_LABEL),
        )
        bare = skip_layouts.is_bare(layout.name)
        resolution = getattr(self, "_skin_resolution", None) or "1080i"
        for name, value in skip_layouts.properties(code, resolution, bare).items():
            self.setProperty(name, value)
        self.setProperty("skl_accent", layout_accent(addon, code, segment, settings=settings, bare=bare))
        self.setProperty("skl_poster", os.path.join(addon.getAddonInfo("path") or "", "icon.png") if addon else "")
        self.setProperty("skl_top", "true" if skip_layouts.is_top(position) else "false")
        for name, value in layout_texts(addon, segment, MOCK_PLAYHEAD, look.caps, settings=settings).items():
            self.setProperty(name, value)
        remaining = countdown_mmss(MOCK_INTRO_END - MOCK_PLAYHEAD)
        self.setProperty("countdown", remaining)
        self.setProperty("skl_seconds", skip_layouts.seconds_left(remaining))
        apply_jump_properties(self, addon, segment, all_caps=look.caps)

        from skip_layout_dialog import apply_overlay

        apply_overlay(self, self._ctrl, self._sc, layout, position, self._draft.get(skip_layouts.KEY_OVERLAY),
                      ids=(skip_layouts.ID_MOCK_OVERLAY, skip_layouts.ID_MOCK_OVERLAY_PLAIN))
        left, top = skip_layouts.origin(layout, position)
        root = self._ctrl(skip_layouts.ID_ROOT + offset)
        if root:
            root.setPosition(self._sc(left), self._sc(top))
        countdown = settings.get_bool("progress_bar_countdown", False)
        timeline = layout.progress == skip_layouts.PROGRESS_TIMELINE
        percent = segment_percent(MOCK_PLAYHEAD, segment.start_seconds, segment.end_seconds, countdown and not timeline)
        if layout.progress == skip_layouts.PROGRESS_RING:
            self.setProperty("skl_ring", skip_layouts.ring_frame(percent))
            return
        box = [int(self._sc(v)) for v in skip_layouts.fill_size(layout, percent)]
        fill = self._ctrl(skip_layouts.ID_BAR_FILL + offset)
        if fill:
            fill.setPosition(box[0], box[1])
            fill.setWidth(box[2])
            fill.setHeight(box[3])
        if timeline:
            parts = skip_layouts.timeline_parts(
                layout, segment.start_seconds, segment.end_seconds, MOCK_PLAYHEAD,
                getattr(segment, "next_segment_start", None),
            )
            track_top = int(self._sc(layout.track[1]))
            head = self._ctrl(skip_layouts.ID_PLAYHEAD + offset)
            if head:
                head.setPosition(int(self._sc(parts["playhead"])) - 1, track_top - int(self._sc(4)))
            mark = self._ctrl(skip_layouts.ID_NESTED + offset)
            if mark:
                mark.setPosition(int(self._sc(parts["jump_left"])), track_top)
                mark.setWidth(int(self._sc(parts["jump_width"])))

    def _layout_left_pane(self):
        """Pack visible setting rows so Minimal does not leave holes for Full-only options."""
        metrics = customize_left_pane_layout(self._nav_ids(), self._sc)
        left = metrics["left"]
        y = metrics["start_y"]
        row_h = metrics["row_h"]
        header_h = metrics["header_h"]
        ids = metrics["ids"]
        section_start = metrics["starts"]
        backdrop = self._ctrl(ID_PANEL_BG)
        if backdrop:
            try:
                backdrop.setHeight(metrics["panel_h"])
            except Exception:
                pass
        for cid in ids:
            if cid in section_start:
                header_id = ID_MIN_HEADER if cid == ID_PLATE else ID_FULL_HEADER
                header = self._ctrl(header_id)
                if header:
                    try:
                        header.setPosition(left, y)
                    except Exception:
                        pass
                y += header_h
            ctrl = self._ctrl(cid)
            if ctrl:
                try:
                    ctrl.setPosition(left, y)
                except Exception:
                    pass
                try:
                    ctrl.setHeight(metrics["button_h"])
                except Exception:
                    pass
                try:
                    ctrl.setVisible(True)
                except Exception:
                    pass
            y += row_h
        save = self._ctrl(ID_SAVE)
        cancel = self._ctrl(ID_CANCEL)
        save_y = metrics["save_y"]
        save_h = metrics["save_h"]
        save_w = metrics["save_w"]
        if save:
            try:
                save.setPosition(left, save_y)
            except Exception:
                pass
            try:
                save.setWidth(save_w)
                save.setHeight(save_h)
            except Exception:
                pass
        if cancel:
            try:
                cancel.setPosition(metrics["cancel_x"], save_y)
            except Exception:
                pass
            try:
                cancel.setWidth(save_w)
                cancel.setHeight(save_h)
            except Exception:
                pass
        for cid in (
            ID_PRESET,
            ID_FONT,
            ID_ALL_CAPS,
            ID_HIDE_ENDING,
            ID_CARD,
            ID_OPACITY,
            ID_OVERLAP,
            ID_PROGRESS,
            ID_COUNTDOWN,
            ID_PROGRESS_STYLE,
            ID_HEIGHT,
            ID_POSITION,
            ID_FOCUS_STYLE,
            ID_SKIP_FORMAT,
            ID_COMBINED,
            ID_DURATION_FORMAT,
            ID_DURATION_CONTENT,
            ID_HIDE_CLOSE,
            ID_HIDE_ICONS,
            ID_FOCUS_FRAME,
            ID_PLATE,
            ID_MIN_FORMAT,
            ID_MIN_POSITION,
        ):
            if cid not in ids:
                hidden = self._ctrl(cid)
                if hidden:
                    try:
                        hidden.setVisible(False)
                    except Exception:
                        pass

    def _refresh_row_labels(self):
        addon = self.addon
        d = self._draft
        self._set_row(ID_PRESET, *preset_row_parts(addon, d))
        self._set_row(
            ID_LAYOUT,
            get_localized(addon, 49010, "Skip dialog layout"),
            dict(skip_layouts.LAYOUT_NAMES)[skip_layouts.normalize_layout(d.get(skip_layouts.KEY_LAYOUT))],
        )
        def named(rows, stored):
            for value, string_id, english in rows:
                if value == stored:
                    return get_localized(addon, string_id, english)
            return stored

        corner_names = {"Skin": (49074, "The look's own"), "Hard": (49075, "Hard"), "Rounded": (49076, "Rounded")}
        corner = skip_layouts.normalize_choice(d.get("skip_canvas_corners"), ("Skin", "Hard", "Rounded"), "Skin")
        self._set_row(ID_CORNERS, get_localized(addon, 49072, "Corners"), get_localized(addon, *corner_names[corner]))
        self._set_row(ID_CV_CLOSE, get_localized(addon, 49077, "Close button"), _yes_no(addon, d.get("skip_canvas_close", True)))
        self._set_row(ID_CV_ICONS, get_localized(addon, 49079, "Icons on the buttons"),
                      _yes_no(addon, d.get("skip_canvas_icons", True)))
        self._set_row(ID_CV_KICKER, get_localized(addon, 49081, "Type and range line"),
                      _yes_no(addon, d.get("skip_canvas_kicker", True)))
        self._set_row(ID_CV_NESTED, get_localized(addon, 49083, "Nested line"),
                      _yes_no(addon, d.get("skip_canvas_nested", True)))
        for row_id, (key, names, default, label_id, label) in CANVAS_CHOICES.items():
            stored = skip_layouts.normalize_choice(d.get(key), [row[0] for row in names], default)
            shown = next(english if not sid else get_localized(addon, sid, english)
                         for value, sid, english in names if value == stored)
            self._set_row(row_id, get_localized(addon, label_id, label), shown)
        self._set_row(ID_CV_TIME, get_localized(addon, 49165, "Time on the Skip button"),
                      _yes_no(addon, d.get("skip_canvas_time", True)))
        self._set_row(ID_CV_DISTANCE, get_localized(addon, 49129, "Distance from the edge"),
                      "%d px" % canvas_distance(d.get("skip_canvas_distance")))
        self._set_row(ID_CV_GRADIENT, get_localized(addon, 49116, "Overlay gradient"),
                      _yes_no(addon, d.get("skip_canvas_overlay_gradient", False)))
        self._set_row(ID_CV_SHADOW, get_localized(addon, 49086, "Text shadow"), named(
            TEXT_SHADOW_NAMES, skip_layouts.normalize_choice(d.get("skip_canvas_text_shadow"),
                                                             [row[0] for row in TEXT_SHADOW_NAMES], "Mild")))
        self._set_row(ID_CV_TEXT_SIZE, get_localized(addon, 49093, "Text size"), named(
            TEXT_SIZE_NAMES, skip_layouts.normalize_choice(d.get("skip_canvas_text_size"),
                                                           [row[0] for row in TEXT_SIZE_NAMES], "100")))
        self._set_row(ID_OVERLAY, get_localized(addon, 49050, "Background overlay"),
                      named(skip_layouts.OVERLAY_NAMES, skip_layouts.normalize_overlay(d.get(skip_layouts.KEY_OVERLAY))))
        self._set_row(ID_APPEAR, get_localized(addon, 49059, "Appears"),
                      named(skip_layouts.APPEAR_NAMES, skip_layouts.normalize_appear(d.get(skip_layouts.KEY_APPEAR))))
        self._set_row(ID_LEAVE, get_localized(addon, 49065, "Leaves"),
                      named(skip_layouts.LEAVE_NAMES, skip_layouts.normalize_leave(d.get(skip_layouts.KEY_LEAVE))))
        self._set_row(ID_PULSE, get_localized(addon, 49069, "Pulse in the last five seconds"),
                      _yes_no(addon, d.get(skip_layouts.KEY_PULSE)))
        self._set_row(
            ID_BAR_COLOR,
            get_localized(addon, 49031, "Bar colour"),
            get_localized(addon, 49032, "Segment type")
            if skip_layouts.normalize_bar_color(d.get(skip_layouts.KEY_BAR_COLOR)) == skip_layouts.BAR_TYPE
            else get_localized(addon, 49020, "Look"),
        )
        self._set_row(
            ID_LOOK,
            get_localized(addon, 49012, "Layout look"),
            dict(skip_layouts.LOOK_NAMES)[skip_layouts.normalize_look(d.get(skip_layouts.KEY_LOOK))],
        )
        self._set_row(
            ID_PREVIEW_TYPE,
            get_localized(addon, 46034, "Preview type"),
            display_segment_label(getattr(self, "_preview_type", MOCK_SEGMENT_LABEL)),
        )
        card = card_choice(d)
        self._set_row(
            ID_CARD,
            get_localized(addon, 49008, "Card style"),
            get_localized(addon, 35030, "Off") if card == CARD_OFF else skip_dialog_card.name(card),
        )
        self._set_row(
            ID_OPACITY,
            get_localized(addon, 46012, "Card opacity (%)"),
            d.get("skip_card_opacity", 95),
        )
        self._set_row(
            ID_MODE,
            get_localized(addon, 32020, "Skip dialog mode"),
            _pair_label(MODE_LABELS, d.get("skip_dialog_mode", "Full")),
        )
        self._set_row(
            ID_HIDE_ENDING,
            get_localized(addon, 32016, "Hide ending text"),
            _yes_no(addon, d.get("hide_ending_text")),
        )
        self._set_row(
            ID_FONT,
            get_localized(addon, 32026, "Skip dialog font color"),
            _pair_label(FONT_COLORS, d.get("skip_dialog_font_color")),
        )
        self._set_row(
            ID_ALL_CAPS,
            get_localized(addon, 32099, "Skip dialog text in ALL CAPS"),
            _yes_no(addon, d.get("skip_dialog_all_caps")),
        )
        self._set_row(
            ID_OVERLAP,
            get_localized(addon, 31007, "Ignore overlapping segments"),
            _yes_no(addon, d.get("skip_overlapping_segments")),
        )
        self._set_row(
            ID_PROGRESS,
            get_localized(addon, 32007, "Show Progress Bar in Skip Dialog"),
            _yes_no(addon, d.get("show_progress_bar")),
        )
        self._set_row(
            ID_COUNTDOWN,
            get_localized(addon, 32027, "Progress bar shows remaining (countdown)"),
            _yes_no(addon, d.get("progress_bar_countdown")),
        )
        self._set_row(
            ID_PROGRESS_STYLE,
            get_localized(addon, 32079, "Progress bar style"),
            _pair_label(PROGRESS_STYLES, d.get("progress_bar_style")),
        )
        self._set_row(
            ID_HEIGHT,
            get_localized(addon, 32080, "Progress bar height (pixels)"),
            d.get("progress_bar_height", 16),
        )
        self._set_row(
            ID_POSITION,
            get_localized(addon, 32009, "Skip Dialog Position"),
            _pair_label(POSITIONS, d.get("skip_dialog_position")),
        )
        self._set_row(
            ID_FOCUS_STYLE,
            get_localized(addon, 32000, "Button Focus Style"),
            _pair_label(BUTTON_FOCUS, d.get("button_focus_style")),
        )
        self._set_row(
            ID_SKIP_FORMAT,
            get_localized(addon, 32013, "Skip button format"),
            d.get("skip_button_format", "Skip + Type + Duration"),
        )
        self._set_row(
            ID_COMBINED,
            get_localized(addon, 32101, "Combined skip and progress"),
            _yes_no(addon, d.get("compact_full_combined")),
        )
        self._set_row(
            ID_DURATION_FORMAT,
            get_localized(addon, 32102, "Skip duration format"),
            _pair_label(DURATION_FORMATS, d.get("skip_duration_format", "1m30s")),
        )
        self._set_row(
            ID_DURATION_CONTENT,
            get_localized(addon, 32103, "Skip duration content"),
            _pair_label(DURATION_CONTENTS, d.get("skip_duration_content", "total")),
        )
        self._set_row(
            ID_HIDE_CLOSE,
            get_localized(addon, 32014, "Hide Close button"),
            _yes_no(addon, d.get("hide_close_button")),
        )
        self._set_row(
            ID_HIDE_ICONS,
            get_localized(addon, 32015, "Hide Skip and Close Icons"),
            _yes_no(addon, d.get("hide_skip_icon")),
        )
        self._set_row(
            ID_FOCUS_FRAME,
            get_localized(addon, 32081, "Show skip button focus frame"),
            _yes_no(addon, d.get("show_skip_button_focus_texture")),
        )
        self._set_row(
            ID_PLATE,
            get_localized(addon, 32023, "Minimal plate style"),
            _pair_label(MINIMAL_PLATES, d.get("minimal_button_style")),
        )
        self._set_row(
            ID_MIN_FORMAT,
            get_localized(addon, 32025, "Minimal skip label format"),
            d.get("minimal_skip_button_format", "Skip + Type"),
        )
        self._set_row(
            ID_MIN_POSITION,
            get_localized(addon, 32024, "Minimal skip dialog position"),
            _pair_label(POSITIONS, d.get("minimal_skip_dialog_position")),
        )

    def _nudge(self, control_id, delta):
        d = self._draft
        if control_id == ID_PREVIEW_TYPE:
            self._preview_type = _cycle(
                preview_type_ids(), getattr(self, "_preview_type", MOCK_SEGMENT_LABEL), delta
            )
        elif control_id == ID_LAYOUT:
            d[skip_layouts.KEY_LAYOUT] = _cycle(
                skip_layouts.LAYOUTS, skip_layouts.normalize_layout(d.get(skip_layouts.KEY_LAYOUT)), delta
            )
        elif control_id == ID_CORNERS:
            d["skip_canvas_corners"] = _cycle(
                ("Skin", "Hard", "Rounded"),
                skip_layouts.normalize_choice(d.get("skip_canvas_corners"), ("Skin", "Hard", "Rounded"), "Skin"), delta)
        elif control_id in CANVAS_CHOICES:
            key, names, default = CANVAS_CHOICES[control_id][:3]
            values = tuple(row[0] for row in names)
            d[key] = _cycle(values, skip_layouts.normalize_choice(d.get(key), values, default), delta)
        elif control_id == ID_CV_TIME:
            d["skip_canvas_time"] = not d.get("skip_canvas_time", True)
        elif control_id == ID_CV_DISTANCE:
            value = canvas_distance(d.get("skip_canvas_distance")) + DISTANCE_STEP * delta
            d["skip_canvas_distance"] = max(0, min(DISTANCE_MAX, value))
        elif control_id == ID_CV_GRADIENT:
            d["skip_canvas_overlay_gradient"] = not d.get("skip_canvas_overlay_gradient", False)
        elif control_id in (ID_CV_SHADOW, ID_CV_TEXT_SIZE):
            key, names, default = (("skip_canvas_text_shadow", TEXT_SHADOW_NAMES, "Mild") if control_id == ID_CV_SHADOW
                                   else ("skip_canvas_text_size", TEXT_SIZE_NAMES, "100"))
            values = tuple(row[0] for row in names)
            d[key] = _cycle(values, skip_layouts.normalize_choice(d.get(key), values, default), delta)
        elif control_id in (ID_CV_CLOSE, ID_CV_ICONS, ID_CV_KICKER, ID_CV_NESTED):
            key = {ID_CV_CLOSE: "skip_canvas_close", ID_CV_ICONS: "skip_canvas_icons",
                   ID_CV_KICKER: "skip_canvas_kicker", ID_CV_NESTED: "skip_canvas_nested"}[control_id]
            d[key] = not d.get(key, True)
        elif control_id == ID_OVERLAY:
            d[skip_layouts.KEY_OVERLAY] = _cycle(
                skip_layouts.OVERLAYS, skip_layouts.normalize_overlay(d.get(skip_layouts.KEY_OVERLAY)), delta)
        elif control_id == ID_APPEAR:
            d[skip_layouts.KEY_APPEAR] = _cycle(
                skip_layouts.APPEARS, skip_layouts.normalize_appear(d.get(skip_layouts.KEY_APPEAR)), delta)
        elif control_id == ID_LEAVE:
            d[skip_layouts.KEY_LEAVE] = _cycle(
                skip_layouts.LEAVES, skip_layouts.normalize_leave(d.get(skip_layouts.KEY_LEAVE)), delta)
        elif control_id == ID_PULSE:
            d[skip_layouts.KEY_PULSE] = not d.get(skip_layouts.KEY_PULSE)
        elif control_id == ID_BAR_COLOR:
            d[skip_layouts.KEY_BAR_COLOR] = _cycle(
                (skip_layouts.BAR_TYPE, skip_layouts.BAR_LOOK),
                skip_layouts.normalize_bar_color(d.get(skip_layouts.KEY_BAR_COLOR)),
                delta,
            )
        elif control_id == ID_LOOK:
            d[skip_layouts.KEY_LOOK] = _cycle(
                skip_layouts.LOOKS, skip_layouts.normalize_look(d.get(skip_layouts.KEY_LOOK)), delta
            )
        elif control_id == ID_PRESET:
            picked = sp.cycle_preset(d, delta)
            if not picked:
                return
            sp.apply_preset(d, picked[1])
        elif control_id == ID_CARD:
            set_card_choice(d, _cycle(CARD_CHOICES, card_choice(d), delta))
        elif control_id == ID_OPACITY:
            val = int(d.get("skip_card_opacity", 95)) + 5 * delta
            d["skip_card_opacity"] = 0 if val > 100 else 100 if val < 0 else val
        elif control_id == ID_MODE:
            d["skip_dialog_mode"] = _cycle(MODES, d.get("skip_dialog_mode", "Full"), delta)
            if d["skip_dialog_mode"] == "Full" and d.get("compact_full_combined"):
                # Combined skip + progress hides the separate bar rows, so arriving in Full
                # from a combined Compact look (Sleek, Pill) would show almost the same list.
                d["compact_full_combined"] = False
        elif control_id == ID_HIDE_ENDING:
            d["hide_ending_text"] = not d.get("hide_ending_text")
        elif control_id == ID_FONT:
            stored = [pair[1] for pair in FONT_COLORS]
            d["skip_dialog_font_color"] = _cycle(
                stored, d.get("skip_dialog_font_color", "FFFFFFFF"), delta
            )
        elif control_id == ID_ALL_CAPS:
            d["skip_dialog_all_caps"] = not d.get("skip_dialog_all_caps")
        elif control_id == ID_OVERLAP:
            d["skip_overlapping_segments"] = not d.get("skip_overlapping_segments", True)
        elif control_id == ID_PROGRESS:
            d["show_progress_bar"] = not d.get("show_progress_bar", True)
        elif control_id == ID_COUNTDOWN:
            d["progress_bar_countdown"] = not d.get("progress_bar_countdown")
        elif control_id == ID_PROGRESS_STYLE:
            stored = [pair[1] for pair in PROGRESS_STYLES]
            d["progress_bar_style"] = _cycle(
                stored, d.get("progress_bar_style", "progress_mid.png"), delta
            )
        elif control_id == ID_HEIGHT:
            val = int(d.get("progress_bar_height", 16)) + delta
            d["progress_bar_height"] = max(5, min(32, val))
        elif control_id == ID_POSITION:
            stored = [pair[1] for pair in POSITIONS]
            d["skip_dialog_position"] = _cycle(
                stored, d.get("skip_dialog_position", "BottomRight"), delta
            )
        elif control_id == ID_FOCUS_STYLE:
            stored = [pair[1] for pair in BUTTON_FOCUS]
            d["button_focus_style"] = _cycle(
                stored, d.get("button_focus_style", "button_focus.png"), delta
            )
        elif control_id == ID_SKIP_FORMAT:
            d["skip_button_format"] = _cycle(
                SKIP_FORMATS, d.get("skip_button_format", "Skip + Type + Duration"), delta
            )
        elif control_id == ID_COMBINED:
            d["compact_full_combined"] = not d.get("compact_full_combined")
        elif control_id == ID_DURATION_FORMAT:
            stored = [pair[1] for pair in DURATION_FORMATS]
            d["skip_duration_format"] = _cycle(
                stored, d.get("skip_duration_format", "1m30s"), delta
            )
        elif control_id == ID_DURATION_CONTENT:
            stored = [pair[1] for pair in DURATION_CONTENTS]
            d["skip_duration_content"] = _cycle(
                stored, d.get("skip_duration_content", "total"), delta
            )
        elif control_id == ID_HIDE_CLOSE:
            d["hide_close_button"] = not d.get("hide_close_button")
        elif control_id == ID_HIDE_ICONS:
            d["hide_skip_icon"] = not d.get("hide_skip_icon")
        elif control_id == ID_FOCUS_FRAME:
            d["show_skip_button_focus_texture"] = not d.get(
                "show_skip_button_focus_texture", True
            )
        elif control_id == ID_PLATE:
            stored = [pair[1] for pair in MINIMAL_PLATES]
            d["minimal_button_style"] = _cycle(
                stored, d.get("minimal_button_style", "minimal_rounded_gray_640.png"), delta
            )
        elif control_id == ID_MIN_FORMAT:
            d["minimal_skip_button_format"] = _cycle(
                SKIP_FORMATS, d.get("minimal_skip_button_format", "Skip + Type"), delta
            )
        elif control_id == ID_MIN_POSITION:
            stored = [pair[1] for pair in POSITIONS]
            d["minimal_skip_dialog_position"] = _cycle(
                stored, d.get("minimal_skip_dialog_position", "BottomRight"), delta
            )
        else:
            return
        self.refresh_mockup()

    def _open_preset_menu(self):
        present_preset_menu(self.addon, self._draft)
        self.refresh_mockup()
        try:
            self.setFocusId(ID_PRESET if ID_PRESET in self._nav_ids() else ID_MODE)
        except Exception:
            pass

    def _save_and_close(self):
        addon = self.addon
        payload = draft_setting_payload(self._draft)
        original = draft_setting_payload(self._original)
        if addon:
            for key, value in payload.items():
                if original.get(key) != value:
                    try:
                        addon.setSetting(key, value)
                    except Exception:
                        pass
        self._saved = True
        # A look that matches no preset is "Custom": offer to keep it as a preset.
        changed = payload != original if addon else False
        if addon and changed and not sp.detect_preset(self._draft):
            try:
                prompt_save_preset(addon, self._draft)
            except Exception:
                pass
        self._closing = True
        self.close()

    def _cancel_and_close(self):
        self._saved = False
        self._closing = True
        self.close()

    def onClick(self, controlId):
        try:
            cid = int(controlId)
        except (TypeError, ValueError):
            return
        if cid == ID_SAVE:
            self._save_and_close()
            return
        if cid == ID_CANCEL:
            self._cancel_and_close()
            return
        if cid == ID_PRESET:
            self._open_preset_menu()
            return
        if cid in (
            ID_PREVIEW_TYPE,
            ID_LAYOUT,
            ID_LOOK,
            ID_MODE,
            ID_CARD,
            ID_OPACITY,
            ID_HIDE_ENDING,
            ID_FONT,
            ID_ALL_CAPS,
            ID_OVERLAP,
            ID_PROGRESS,
            ID_COUNTDOWN,
            ID_PROGRESS_STYLE,
            ID_HEIGHT,
            ID_POSITION,
            ID_FOCUS_STYLE,
            ID_SKIP_FORMAT,
            ID_COMBINED,
            ID_DURATION_FORMAT,
            ID_DURATION_CONTENT,
            ID_HIDE_CLOSE,
            ID_HIDE_ICONS,
            ID_FOCUS_FRAME,
            ID_PLATE,
            ID_MIN_FORMAT,
            ID_MIN_POSITION,
        ):
            self._nudge(cid, 1)

    def onAction(self, action):
        aid = action.getId()
        if aid in _CANCEL_ACTIONS:
            self._cancel_and_close()
            return
        if aid == _MOVE_DOWN:
            self._move_focus(1)
            return
        if aid == _MOVE_UP:
            self._move_focus(-1)
            return
        if aid in (_MOVE_LEFT, _MOVE_RIGHT):
            cid = self._focus_id()
            if cid in (ID_SAVE, ID_CANCEL):
                self._move_focus(1 if aid == _MOVE_RIGHT else -1)
                return
            self._nudge(cid, 1 if aid == _MOVE_RIGHT else -1)


def show_skip_dialog_customize(draft=None, original=None):
    """Open Customize Skip Dialog: the Studio (skip_studio_ui.py), or this classic screen should
    the Studio fail to open. ``draft`` previews unsaved values (e.g. a preset); ``original`` is
    what is currently stored, so Save writes only real changes."""
    try:
        from skip_studio_ui import show_skip_studio
    except Exception:
        return show_skip_dialog_customize_classic(draft=draft, original=original)
    return show_skip_studio(draft=draft, original=original)


def show_skip_dialog_customize_classic(draft=None, original=None):
    """The Customize screen of the versions before the Studio (one list of rows)."""
    # Opened from the settings window, it must see what an earlier Save handed to that window.
    addon = with_pending(get_addon())
    if not addon:
        return False
    path = addon.getAddonInfo("path")
    kwargs = {"addon": addon}
    if draft is not None:
        kwargs["draft"] = draft
        kwargs["original"] = original or load_skip_dialog_draft(addon)
    dialog = SkipDialogCustomize(
        skippy_modal_style.xml_name("SkipDialogCustomize.xml", addon=addon), path, "default", **kwargs
    )
    dialog.doModal()
    saved = bool(getattr(dialog, "_saved", False))
    del dialog
    return saved
