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
    "hide_skip_icon": False,
    "compact_full_combined": False,
    "skip_card_enabled": True,
    "skip_card_opacity": 95,
    "minimal_button_style": "minimal_rounded_gray_640.png",
    "minimal_skip_button_format": "Skip + Type",
}

_DARK_GREY = "FF3D3D3D"

# name -> overrides on BASE_LOOK (ordered: classic gloss first, then flat/matte/glass)
_BUILTIN_OVERRIDES = (
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
    for key in relevant_keys(clean["skip_dialog_mode"]):
        clean.setdefault(key, BASE_LOOK[key])
    return {k: clean[k] for k in relevant_keys(clean["skip_dialog_mode"])}


def clean_name(name) -> str:
    text = " ".join(str(name or "").split())
    return text[:MAX_NAME_LEN].strip()


# ----------------------------------------------------------------- user store
def _store_path():
    return profile_path(USER_PRESETS_FILE)


def load_user_presets() -> dict:
    data = read_json(_store_path(), {})
    raw = data.get("presets") if isinstance(data, dict) else None
    out = {}
    if isinstance(raw, dict):
        for name, entry in raw.items():
            nm = clean_name(name)
            values = sanitize_values(entry.get("values") if isinstance(entry, dict) else None)
            if nm and values and nm not in builtin_names():
                out[nm] = values
    return out


def _write_user_presets(presets: dict) -> bool:
    payload = {
        "schema": USER_PRESETS_SCHEMA,
        "presets": {name: {"values": vals} for name, vals in sorted(presets.items())},
    }
    return write_json(_store_path(), payload)


def list_presets() -> list:
    """``[(name, values, is_builtin)]`` built-ins first, then saved presets (A-Z)."""
    out = [(n, v, True) for n, v in builtin_presets()]
    user = load_user_presets()
    out.extend((n, user[n], False) for n in sorted(user, key=str.lower))
    return out


def user_preset_exists(name) -> bool:
    return clean_name(name) in load_user_presets()


def snapshot(draft: dict) -> dict:
    """Preset values for the draft's current mode."""
    mode = mode_name(draft.get("skip_dialog_mode"))
    raw = {k: draft.get(k, BASE_LOOK[k]) for k in relevant_keys(mode)}
    raw["skip_dialog_mode"] = mode
    return sanitize_values(raw)


def save_user_preset(name, draft: dict) -> tuple:
    """Returns ``(ok, error_code)``; codes: ``name``, ``builtin``, ``limit``, ``write``."""
    nm = clean_name(name)
    if not nm:
        return False, "name"
    if nm in builtin_names() or nm.lower() in {b.lower() for b in builtin_names()}:
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
    """Write preset values into the draft (keys outside the preset stay as they are)."""
    for key, val in sanitize_values(values).items():
        draft[key] = val


def detect_preset(draft: dict):
    """Name of the first preset whose values all match the draft, else None."""
    mode = mode_name(draft.get("skip_dialog_mode"))
    keys = relevant_keys(mode)
    current = {}
    for key in keys:
        val = coerce_value(key, draft.get(key, BASE_LOOK[key]))
        current[key] = BASE_LOOK[key] if val is None else val
    for name, values, _builtin in list_presets():
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
