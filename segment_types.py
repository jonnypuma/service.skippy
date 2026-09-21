# -*- coding: utf-8 -*-
"""Typed segment catalog: skip mode, aliases, and EDL numbers.

Live data is ``addon_data/service.skippy/segment_types.json`` (schema
``skippy_segment_types_v1``). Built-in types are seeded in code; the JSON file
overlays skip mode, aliases, write EDL, order, and custom types.
"""

from __future__ import annotations

import os
import unicodedata

from skippy_profile_store import profile_path, read_json, write_json

SCHEMA = "skippy_segment_types_v1"
CATALOG_FILENAME = "segment_types.json"

SKIP_AUTO = "auto"
SKIP_ASK = "ask"
SKIP_NEVER = "never"
SKIP_MODES = (SKIP_AUTO, SKIP_ASK, SKIP_NEVER)
SKIP_MODE_LABELS = {
    SKIP_AUTO: "Always",
    SKIP_ASK: "Ask",
    SKIP_NEVER: "Never",
}
SKIP_CYCLE = (SKIP_AUTO, SKIP_ASK, SKIP_NEVER)

# Legacy EDL numbers that still parse but are never written.
LEGACY_READ_EDL = frozenset({6, 13, 16, 17, 14})

_MIN_WRITE_EDL = 4


def normalize_label(label):
    return unicodedata.normalize("NFKC", str(label or "")).strip().lower()


def _log(msg):
    try:
        from settings_utils import log

        log(msg)
    except Exception:
        pass


# Built-in seed. ``edl_read_aliases`` and ``online_bucket`` stay in code.
_BUILTIN_SPECS = (
    {
        "id": "intro",
        "label": "Intro",
        "skip_mode": SKIP_ASK,
        "edl_action": 5,
        "edl_read_aliases": (),
        "aliases": (
            "intro",
            "opening",
            "title",
            "titles",
            "beginning",
            "introduction",
            "opening theme",
        ),
        "online_bucket": "intro",
    },
    {
        "id": "recap",
        "label": "Recap",
        "skip_mode": SKIP_ASK,
        "edl_action": 9,
        "edl_read_aliases": (),
        "aliases": (
            "recap",
            "previously on",
            "last time on",
            "last on",
            "previously",
        ),
        "online_bucket": "recap",
    },
    {
        "id": "commercial",
        "label": "Commercial",
        "skip_mode": SKIP_AUTO,
        "edl_action": 7,
        "edl_read_aliases": (6, 16),
        "aliases": (
            "commercial",
            "commercials",
            "ad",
            "ads",
            "sponsor",
            "sponsors",
        ),
        "online_bucket": None,
    },
    {
        "id": "prologue",
        "label": "Prologue",
        "skip_mode": SKIP_NEVER,
        "edl_action": 10,
        "edl_read_aliases": (17,),
        "aliases": ("prologue", "cold open", "cold_open"),
        "online_bucket": None,
    },
    {
        "id": "preview",
        "label": "Preview",
        "skip_mode": SKIP_ASK,
        "edl_action": 15,
        "edl_read_aliases": (),
        "aliases": (
            "preview",
            "next time on",
            "next on",
            "sneak peek",
            "teaser",
        ),
        "online_bucket": "preview",
    },
    {
        "id": "credits",
        "label": "Credits",
        "skip_mode": SKIP_NEVER,
        "edl_action": 8,
        "edl_read_aliases": (13,),
        "aliases": ("credits", "outro", "closing", "ending"),
        "online_bucket": "credits",
    },
    {
        "id": "epilogue",
        "label": "Epilogue",
        "skip_mode": SKIP_NEVER,
        "edl_action": 11,
        "edl_read_aliases": (),
        "aliases": ("epilogue",),
        "online_bucket": None,
    },
    {
        "id": "behind_the_scenes",
        "label": "Behind the scenes",
        "skip_mode": SKIP_ASK,
        "edl_action": 18,
        "edl_read_aliases": (),
        "aliases": ("behind the scenes", "behind-the-scenes", "bts"),
        "online_bucket": None,
    },
    {
        "id": "featurette",
        "label": "Featurette",
        "skip_mode": SKIP_ASK,
        "edl_action": 19,
        "edl_read_aliases": (),
        "aliases": ("featurette",),
        "online_bucket": None,
    },
    {
        "id": "main",
        "label": "Main",
        "skip_mode": SKIP_NEVER,
        "edl_action": 12,
        "edl_read_aliases": (),
        "aliases": ("main",),
        "online_bucket": None,
    },
    {
        "id": "segment",
        "label": "Segment",
        "skip_mode": SKIP_NEVER,
        "edl_action": 4,
        "edl_read_aliases": (14,),
        "aliases": ("segment",),
        "online_bucket": None,
    },
)

BUILTIN_BY_ID = {spec["id"]: spec for spec in _BUILTIN_SPECS}

_cache = None
_cache_mtime = None
_cache_path = None
_forced_types = None


def catalog_path():
    return profile_path(CATALOG_FILENAME)


def invalidate_catalog_cache():
    global _cache, _cache_mtime, _cache_path
    _cache = None
    _cache_mtime = None
    _cache_path = None


def set_catalog_for_tests(types_or_none):
    """Pin an in-memory catalog (tests). Pass None to restore file loading."""
    global _forced_types
    invalidate_catalog_cache()
    if types_or_none is None:
        _forced_types = None
        return
    _forced_types = [clone_type(t) for t in types_or_none]


def clone_type(type_row):
    row = type_row or {}
    spec = BUILTIN_BY_ID.get(normalize_label(row.get("id") or ""))
    aliases = [
        str(a).strip()
        for a in (row.get("aliases") or [])
        if str(a).strip()
    ]
    skip = _coerce_skip_mode(row.get("skip_mode"), SKIP_NEVER)
    try:
        edl = int(row.get("edl_action"))
    except (TypeError, ValueError):
        edl = int(spec["edl_action"]) if spec else _MIN_WRITE_EDL
    builtin = bool(row.get("builtin")) if "builtin" in row else bool(spec)
    type_id = normalize_label(row.get("id") or row.get("label") or "")
    label = (row.get("label") or "").strip() or (spec["label"] if spec else type_id)
    online = row.get("online_bucket")
    if online is None and spec:
        online = spec.get("online_bucket")
    read_aliases = row.get("edl_read_aliases")
    if not read_aliases and spec:
        read_aliases = spec.get("edl_read_aliases") or ()
    return {
        "id": type_id,
        "label": label,
        "skip_mode": skip,
        "edl_action": edl,
        "aliases": aliases,
        "builtin": builtin,
        "online_bucket": online,
        "edl_read_aliases": [int(a) for a in (read_aliases or ())],
    }


def clone_types(types):
    return [clone_type(t) for t in (types or [])]


def seeded_builtin_types():
    return [clone_type(spec) for spec in _BUILTIN_SPECS]


def _coerce_skip_mode(value, default=SKIP_NEVER):
    raw = normalize_label(value)
    if raw in ("always", "auto"):
        return SKIP_AUTO
    if raw == "ask":
        return SKIP_ASK
    if raw == "never":
        return SKIP_NEVER
    return default


def _file_mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def _phrases_for_type(type_row):
    phrases = []
    for raw in (
        (type_row.get("id"),)
        + (type_row.get("label"),)
        + tuple(type_row.get("aliases") or ())
    ):
        norm = normalize_label(raw)
        if norm and norm not in phrases:
            phrases.append(norm)
    return phrases


def resolve_in_types(types, label):
    """Return the type dict from ``types`` that owns ``label``, or None."""
    needle = normalize_label(label)
    if not needle:
        return None
    for type_row in types or []:
        if needle in _phrases_for_type(type_row):
            return type_row
    return None


def owner_of_phrase(types, phrase, *, exclude_id=None):
    needle = normalize_label(phrase)
    if not needle:
        return None
    for type_row in types or []:
        if exclude_id and type_row.get("id") == exclude_id:
            continue
        if needle in _phrases_for_type(type_row):
            return type_row
    return None


def _split_csv(raw):
    return [part.strip() for part in str(raw or "").split(",") if part.strip()]


def _read_legacy_setting(addon, key, default=""):
    if addon is not None:
        try:
            value = addon.getSetting(key)
            if value is None:
                return default
            return str(value)
        except Exception:
            return default
    try:
        from settings_utils import addon_get_setting_text, get_addon

        live = get_addon()
        if not live:
            return default
        text = addon_get_setting_text(live, key, default)
        if text is None:
            return default
        return str(text)
    except Exception:
        return default


def _parse_edl_pairs(raw):
    action_to_label = {}
    label_to_action = {}
    for pair in [entry.strip() for entry in str(raw or "").split(",") if ":" in entry]:
        try:
            action, label = pair.split(":", 1)
            action_int = int(action.strip())
            norm = normalize_label(label)
            if not norm:
                continue
            action_to_label[action_int] = norm
            label_to_action[norm] = action_int
        except (TypeError, ValueError):
            continue
    return action_to_label, label_to_action


def used_edl_numbers(types):
    used = set()
    for type_row in types or []:
        try:
            used.add(int(type_row.get("edl_action")))
        except (TypeError, ValueError):
            pass
        for alias in type_row.get("edl_read_aliases") or ():
            try:
                used.add(int(alias))
            except (TypeError, ValueError):
                pass
    return used


def next_free_edl_action(types, start=_MIN_WRITE_EDL):
    used = used_edl_numbers(types)
    n = max(_MIN_WRITE_EDL, int(start or _MIN_WRITE_EDL))
    while n in used:
        n += 1
    return n


def unused_edl_actions(types, count=24):
    used = used_edl_numbers(types)
    out = []
    n = _MIN_WRITE_EDL
    while len(out) < count:
        if n not in used:
            out.append(n)
        n += 1
    return out


def cycle_skip_mode(mode):
    current = _coerce_skip_mode(mode, SKIP_NEVER)
    idx = SKIP_CYCLE.index(current)
    return SKIP_CYCLE[(idx + 1) % len(SKIP_CYCLE)]


def skip_mode_label(mode):
    return SKIP_MODE_LABELS.get(_coerce_skip_mode(mode, SKIP_NEVER), "Never")


def add_custom_type(types, name):
    """Append a custom type. Returns ``(type_row, error)``."""
    label = str(name or "").strip()
    type_id = normalize_label(label)
    if not type_id:
        return None, "Type name is required."
    owner = owner_of_phrase(types, type_id)
    if owner:
        return None, "That name is already used by %s." % owner.get("label")
    row = {
        "id": type_id,
        "label": label,
        "skip_mode": SKIP_NEVER,
        "edl_action": next_free_edl_action(types),
        "aliases": [label],
        "builtin": False,
        "online_bucket": None,
        "edl_read_aliases": [],
    }
    types.append(row)
    return row, None


def delete_custom_type(types, type_id):
    needle = normalize_label(type_id)
    for i, type_row in enumerate(list(types or [])):
        if type_row.get("id") != needle:
            continue
        if type_row.get("builtin"):
            return "Built-in types cannot be deleted."
        del types[i]
        return None
    return "Type not found."


def add_alias(types, type_id, phrase):
    needle = normalize_label(type_id)
    type_row = next((t for t in types if t.get("id") == needle), None)
    if type_row is None:
        return "Type not found."
    raw = str(phrase or "").strip()
    norm = normalize_label(raw)
    if not norm:
        return "Alias is empty."
    owner = owner_of_phrase(types, norm, exclude_id=needle)
    if owner:
        return "That alias is already used by %s." % owner.get("label")
    if norm in _phrases_for_type(type_row):
        return None
    type_row["aliases"].append(raw)
    return None


def remove_alias(types, type_id, phrase):
    needle = normalize_label(type_id)
    type_row = next((t for t in types if t.get("id") == needle), None)
    if type_row is None:
        return "Type not found."
    norm = normalize_label(phrase)
    kept = [a for a in type_row.get("aliases") or [] if normalize_label(a) != norm]
    type_row["aliases"] = kept
    return None


def set_edl_action(types, type_id, action):
    needle = normalize_label(type_id)
    type_row = next((t for t in types if t.get("id") == needle), None)
    if type_row is None:
        return "Type not found."
    try:
        action_int = int(action)
    except (TypeError, ValueError):
        return "EDL number must be an integer."
    if action_int < _MIN_WRITE_EDL:
        return "EDL number must be 4 or higher."
    used = used_edl_numbers(types)
    try:
        used.discard(int(type_row.get("edl_action")))
    except (TypeError, ValueError):
        pass
    if action_int in used:
        return "EDL number already used."
    type_row["edl_action"] = action_int
    return None


def set_skip_mode(types, type_id, mode):
    needle = normalize_label(type_id)
    type_row = next((t for t in types if t.get("id") == needle), None)
    if type_row is None:
        return "Type not found."
    type_row["skip_mode"] = _coerce_skip_mode(mode, SKIP_NEVER)
    return None


def validate_types(types):
    if not types:
        return "Catalog is empty."
    seen_ids = set()
    seen_phrases = {}
    seen_edl = {}
    for type_row in types:
        type_id = normalize_label(type_row.get("id") or "")
        if not type_id:
            return "A type is missing an id."
        if type_id in seen_ids:
            return "Duplicate type id: %s" % type_id
        seen_ids.add(type_id)
        try:
            edl = int(type_row.get("edl_action"))
        except (TypeError, ValueError):
            return "Type %s has a non-integer EDL number." % type_id
        if edl < _MIN_WRITE_EDL:
            return "Type %s uses a reserved EDL number." % type_id
        if edl in seen_edl:
            return "EDL number %s is used by more than one type." % edl
        seen_edl[edl] = type_id
        if _coerce_skip_mode(type_row.get("skip_mode"), None) is None:
            return "Type %s has an invalid skip mode." % type_id
        for phrase in _phrases_for_type(type_row):
            owner = seen_phrases.get(phrase)
            if owner and owner != type_id:
                return "Alias '%s' is used by %s and %s." % (phrase, owner, type_id)
            seen_phrases[phrase] = type_id
    return None


def _overlay_builtin(spec, loaded):
    row = clone_type(spec)
    if loaded:
        if loaded.get("skip_mode") is not None:
            row["skip_mode"] = _coerce_skip_mode(loaded.get("skip_mode"), row["skip_mode"])
        aliases = [
            str(a).strip()
            for a in (loaded.get("aliases") or [])
            if str(a).strip()
        ]
        if aliases:
            row["aliases"] = aliases
        try:
            edl = int(loaded.get("edl_action"))
            if edl >= _MIN_WRITE_EDL:
                row["edl_action"] = edl
        except (TypeError, ValueError):
            pass
    row["builtin"] = True
    row["label"] = spec["label"]
    row["online_bucket"] = spec.get("online_bucket")
    row["edl_read_aliases"] = list(spec.get("edl_read_aliases") or ())
    return row


def _sanitize_custom(loaded):
    label = (loaded.get("label") or loaded.get("id") or "").strip() or "segment"
    type_id = normalize_label(loaded.get("id") or label)
    aliases = [
        str(a).strip()
        for a in (loaded.get("aliases") or [])
        if str(a).strip()
    ]
    if not aliases:
        aliases = [label]
    try:
        edl = int(loaded.get("edl_action"))
    except (TypeError, ValueError):
        edl = _MIN_WRITE_EDL
    if edl < _MIN_WRITE_EDL:
        edl = _MIN_WRITE_EDL
    return {
        "id": type_id,
        "label": label,
        "skip_mode": _coerce_skip_mode(loaded.get("skip_mode"), SKIP_NEVER),
        "edl_action": edl,
        "aliases": aliases,
        "builtin": False,
        "online_bucket": None,
        "edl_read_aliases": [],
    }


def _merge_loaded_types(loaded_types):
    result = []
    seen = set()
    for raw in loaded_types or []:
        if not isinstance(raw, dict):
            continue
        type_id = normalize_label(raw.get("id") or raw.get("label") or "")
        if not type_id or type_id in seen:
            continue
        if type_id in BUILTIN_BY_ID:
            result.append(_overlay_builtin(BUILTIN_BY_ID[type_id], raw))
        else:
            result.append(_sanitize_custom(raw))
        seen.add(type_id)
    for spec in _BUILTIN_SPECS:
        if spec["id"] not in seen:
            result.append(clone_type(spec))
            seen.add(spec["id"])
    _repair_collisions(result)
    return result


def _repair_collisions(types):
    seen_phrases = {}
    for type_row in types:
        kept = []
        for alias in type_row.get("aliases") or []:
            norm = normalize_label(alias)
            owner = seen_phrases.get(norm)
            if owner and owner != type_row["id"]:
                continue
            kept.append(alias)
            if norm:
                seen_phrases[norm] = type_row["id"]
        for extra in (type_row.get("id"), type_row.get("label")):
            norm = normalize_label(extra)
            if norm:
                seen_phrases.setdefault(norm, type_row["id"])
        type_row["aliases"] = kept
    seen_edl = {}
    for type_row in types:
        try:
            edl = int(type_row.get("edl_action"))
        except (TypeError, ValueError):
            edl = next_free_edl_action(types)
            type_row["edl_action"] = edl
        if edl < _MIN_WRITE_EDL or edl in seen_edl:
            type_row["edl_action"] = next_free_edl_action(
                [t for t in types if t is not type_row]
            )
            edl = type_row["edl_action"]
        seen_edl[edl] = type_row["id"]


def _payload_types(data):
    if not isinstance(data, dict):
        return None
    if data.get("schema") != SCHEMA:
        return None
    types = data.get("types")
    if not isinstance(types, list) or not types:
        return None
    return types


def types_to_payload(types):
    return {
        "schema": SCHEMA,
        "types": [
            {
                "id": t["id"],
                "label": t["label"],
                "skip_mode": t["skip_mode"],
                "edl_action": int(t["edl_action"]),
                "aliases": list(t.get("aliases") or []),
                "builtin": bool(t.get("builtin")),
            }
            for t in types
        ],
    }


def migrate_from_legacy_settings(addon=None):
    """Seed builtins and overlay leftover 6.x comma-separated settings."""
    types = seeded_builtin_types()
    always = _split_csv(_read_legacy_setting(addon, "segment_always_skip"))
    ask = _split_csv(_read_legacy_setting(addon, "segment_ask_skip"))
    never = _split_csv(_read_legacy_setting(addon, "segment_never_skip"))
    keywords = _split_csv(_read_legacy_setting(addon, "custom_segment_keywords"))
    edl_raw = _read_legacy_setting(addon, "edl_action_mapping")
    _action_to_label, label_to_action = _parse_edl_pairs(edl_raw)

    skip_locked = set()
    pending_custom = {}
    for mode, words in (
        (SKIP_AUTO, always),
        (SKIP_ASK, ask),
        (SKIP_NEVER, never),
    ):
        for word in words:
            existing = resolve_in_types(types, word)
            if existing:
                if existing["id"] not in skip_locked:
                    existing["skip_mode"] = mode
                    skip_locked.add(existing["id"])
                continue
            key = normalize_label(word)
            if key and key not in pending_custom:
                pending_custom[key] = {"label": word.strip(), "skip_mode": mode}

    for word in keywords:
        if resolve_in_types(types, word):
            continue
        key = normalize_label(word)
        if key and key not in pending_custom:
            pending_custom[key] = {"label": word.strip(), "skip_mode": SKIP_NEVER}

    for _key, info in pending_custom.items():
        edl = label_to_action.get(normalize_label(info["label"]))
        if edl is None or edl < _MIN_WRITE_EDL or edl in used_edl_numbers(types):
            edl = next_free_edl_action(types)
        types.append(
            {
                "id": normalize_label(info["label"]),
                "label": info["label"],
                "skip_mode": info["skip_mode"],
                "edl_action": edl,
                "aliases": [info["label"]],
                "builtin": False,
                "online_bucket": None,
                "edl_read_aliases": [],
            }
        )

    used_write = {int(t["edl_action"]) for t in types}
    for action, label in _action_to_label.items():
        if action in LEGACY_READ_EDL or action < _MIN_WRITE_EDL:
            continue
        existing = resolve_in_types(types, label)
        if existing is None:
            continue
        current = int(existing["edl_action"])
        if action == current:
            continue
        if action in used_write:
            continue
        used_write.discard(current)
        existing["edl_action"] = action
        used_write.add(action)

    _repair_collisions(types)
    return types


def _set_cache(types, path=None, mtime=None):
    global _cache, _cache_mtime, _cache_path
    _cache = clone_types(types)
    _cache_path = path
    _cache_mtime = mtime
    return clone_types(_cache)


def ensure_catalog(addon=None):
    """Load or create the catalog. First 7.0 run migrates old settings."""
    global _cache, _cache_mtime, _cache_path
    if _forced_types is not None:
        return clone_types(_forced_types)

    path = catalog_path()
    mtime = _file_mtime(path) if path else None
    if (
        _cache is not None
        and path == _cache_path
        and mtime == _cache_mtime
    ):
        return clone_types(_cache)

    loaded = read_json(path, default=None) if path else None
    raw_types = _payload_types(loaded)
    if raw_types is not None:
        types = _merge_loaded_types(raw_types)
        missing_builtin = any(
            spec["id"] not in {t["id"] for t in raw_types} for spec in _BUILTIN_SPECS
        )
        if missing_builtin and path:
            save_catalog(types)
            mtime = _file_mtime(path)
        return _set_cache(types, path, mtime)

    types = migrate_from_legacy_settings(addon)
    if path:
        if save_catalog(types):
            _log("Segment types catalog created (%d type(s))" % len(types))
            mtime = _file_mtime(path)
        else:
            _log("Segment types catalog could not be written")
    return _set_cache(types, path, mtime)


def get_types():
    return ensure_catalog()


def save_catalog(types):
    """Write ``types`` to profile JSON. Returns True on success."""
    err = validate_types(types)
    if err:
        _log("Segment types catalog not saved: %s" % err)
        return False
    path = catalog_path()
    ok = write_json(path, types_to_payload(types))
    if ok:
        invalidate_catalog_cache()
        _set_cache(types, path, _file_mtime(path) if path else None)
    return ok


def export_catalog():
    """JSON-serializable payload for profile backup."""
    return types_to_payload(ensure_catalog())


def merge_catalog_from_backup(incoming):
    """
    Replace-or-merge by type id. Incoming order wins; local-only custom types
    are appended. Returns True when the live catalog was written.
    """
    if not isinstance(incoming, dict):
        return False
    incoming_types = incoming.get("types")
    if not isinstance(incoming_types, list) or not incoming_types:
        return False
    local = ensure_catalog()
    merged = _merge_loaded_types(incoming_types)
    incoming_ids = {
        normalize_label(t.get("id") or t.get("label") or "")
        for t in incoming_types
        if isinstance(t, dict)
    }
    for type_row in local:
        if type_row["id"] not in incoming_ids and not type_row.get("builtin"):
            merged.append(clone_type(type_row))
    _repair_collisions(merged)
    return save_catalog(merged)


def resolve_segment_type(label):
    """Type dict for ``label``, or None when unmatched."""
    return resolve_in_types(ensure_catalog(), label)


def canonical_type_id(label):
    type_row = resolve_segment_type(label)
    if type_row:
        return type_row["id"]
    return normalize_label(label) or None


def display_label_for(label):
    type_row = resolve_segment_type(label)
    if type_row:
        return type_row["label"]
    value = (label or "").strip()
    if not value:
        return value
    value = value.replace("_", " ")
    if any(ch.isupper() for ch in value):
        return value
    return " ".join(word[:1].upper() + word[1:] for word in value.split())


def get_user_skip_mode(label):
    type_row = resolve_segment_type(label)
    if not type_row:
        return SKIP_NEVER
    return _coerce_skip_mode(type_row.get("skip_mode"), SKIP_NEVER)


def get_edl_type_map():
    """EDL action int → canonical type id (write number plus read aliases)."""
    mapping = {}
    for type_row in ensure_catalog():
        mapping[int(type_row["edl_action"])] = type_row["id"]
        for alias in type_row.get("edl_read_aliases") or ():
            mapping[int(alias)] = type_row["id"]
    return mapping


def get_edl_label_to_action_map():
    """Normalized label / alias → write EDL number."""
    mapping = {}
    for type_row in ensure_catalog():
        action = int(type_row["edl_action"])
        for phrase in _phrases_for_type(type_row):
            mapping[phrase] = action
    return mapping


def edl_write_action(label, action_type=None):
    """Primary write EDL for a label (collapses legacy 6/13/16/17)."""
    mapping = get_edl_label_to_action_map()
    key = normalize_label(label)
    if key in mapping:
        return mapping[key]
    type_map = get_edl_type_map()
    try:
        raw = int(action_type)
    except (TypeError, ValueError):
        raw = None
    if raw is not None and raw in type_map:
        return mapping.get(type_map[raw], 4)
    if raw is not None and raw >= _MIN_WRITE_EDL:
        return raw
    return 4


def get_custom_segment_keyword_labels(_addon=None):
    """Display names in catalog order (marker / editor pickers)."""
    return [t["label"] for t in ensure_catalog()]


def watch_labels():
    """Normalized ids + aliases used to recognize named chapters."""
    labels = set()
    for type_row in ensure_catalog():
        labels.update(_phrases_for_type(type_row))
    return labels


def catalog_stamp():
    """Parse-cache signature: ids, skip modes, EDL numbers, aliases."""
    parts = []
    for type_row in ensure_catalog():
        aliases = ",".join(sorted(_phrases_for_type(type_row)))
        parts.append(
            "%s:%s:%s:%s"
            % (
                type_row["id"],
                type_row["skip_mode"],
                type_row["edl_action"],
                aliases,
            )
        )
    return tuple(parts)


def catalog_snapshot_text(limit=220):
    chunks = []
    for type_row in ensure_catalog():
        chunks.append(
            "%s=%s/edl%s"
            % (type_row["id"], type_row["skip_mode"], type_row["edl_action"])
        )
    text = ",".join(chunks)
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text
