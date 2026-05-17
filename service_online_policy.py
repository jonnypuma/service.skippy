# -*- coding: utf-8 -*-
"""Online sidecar save policies and segment source priority normalization (settings ↔ canonical ids)."""
from settings_utils import log, log_service_detail, normalize_label

# save_online_chapters_existing_policy (labelenum optionvalues)
_SAVE_CHAPTERS_SKIP_IF_EXISTS = "SkipIfExists"
_SAVE_CHAPTERS_OVERWRITE_SILENT = "OverwriteSilent"
_SAVE_CHAPTERS_OVERWRITE_ASK = "OverwriteAsk"
_SAVE_CHAPTERS_MERGE = "Merge"
_SAVE_CHAPTERS_UPDATE_SILENT = "UpdateSilent"
_SAVE_CHAPTERS_UPDATE_ASK = "UpdateAsk"
_SAVE_CHAPTERS_UPDATE_ALL_SILENT = "UpdateAllSilent"
_SAVE_CHAPTERS_UPDATE_ALL_ASK = "UpdateAllAsk"

_SAVE_ONLINE_FORMAT_BOTH = "Both"
_SAVE_ONLINE_FORMAT_EDL = "EDL"
_SAVE_ONLINE_FORMAT_XML = "XML"

_POLICY_STORAGE_VALUES = frozenset(
    {
        _SAVE_CHAPTERS_SKIP_IF_EXISTS,
        _SAVE_CHAPTERS_OVERWRITE_SILENT,
        _SAVE_CHAPTERS_OVERWRITE_ASK,
        _SAVE_CHAPTERS_MERGE,
        _SAVE_CHAPTERS_UPDATE_SILENT,
        _SAVE_CHAPTERS_UPDATE_ASK,
        _SAVE_CHAPTERS_UPDATE_ALL_SILENT,
        _SAVE_CHAPTERS_UPDATE_ALL_ASK,
    }
)

_UPDATE_POLICIES_WITH_NEIGHBOR_SNAP = frozenset(
    {
        _SAVE_CHAPTERS_UPDATE_SILENT,
        _SAVE_CHAPTERS_UPDATE_ASK,
        _SAVE_CHAPTERS_UPDATE_ALL_SILENT,
        _SAVE_CHAPTERS_UPDATE_ALL_ASK,
    }
)

_POLICY_LABEL_NORMALIZED = {
    normalize_label("Skip if exists"): _SAVE_CHAPTERS_SKIP_IF_EXISTS,
    normalize_label("Overwrite (no prompt)"): _SAVE_CHAPTERS_OVERWRITE_SILENT,
    normalize_label("Overwrite (ask first)"): _SAVE_CHAPTERS_OVERWRITE_ASK,
    normalize_label("Merge with existing"): _SAVE_CHAPTERS_MERGE,
    normalize_label("Update (no prompt)"): _SAVE_CHAPTERS_UPDATE_SILENT,
    normalize_label("Update (ask first)"): _SAVE_CHAPTERS_UPDATE_ASK,
    normalize_label("Update All (no prompt)"): _SAVE_CHAPTERS_UPDATE_ALL_SILENT,
    normalize_label("Update All (ask first)"): _SAVE_CHAPTERS_UPDATE_ALL_ASK,
}


def policy_allows_neighbor_snap(policy):
    """Neighbor snap toggles apply only to Update / Update All policies (not Merge/Overwrite)."""
    return policy in _UPDATE_POLICIES_WITH_NEIGHBOR_SNAP


def _normalize_online_sidecar_policy(raw):
    """Map labelenum storage value or display label to canonical policy ids."""
    s = (raw or "").strip()
    if s in _POLICY_STORAGE_VALUES:
        return s
    mapped = _POLICY_LABEL_NORMALIZED.get(normalize_label(s))
    if mapped:
        log_service_detail(
            "save_online_chapters_existing_policy value %r normalized to %s"
            % (s, mapped),
            tag="policy",
        )
        return mapped
    log(
        "Unknown save_online_chapters_existing_policy %r — using SkipIfExists"
        % (s,)
    )
    return _SAVE_CHAPTERS_SKIP_IF_EXISTS


def _normalize_save_online_format(raw):
    s = (raw or "").strip()
    if s in (
        _SAVE_ONLINE_FORMAT_BOTH,
        _SAVE_ONLINE_FORMAT_EDL,
        _SAVE_ONLINE_FORMAT_XML,
    ):
        return s
    key = normalize_label(s).replace(" ", "")
    aliases = {
        "both": _SAVE_ONLINE_FORMAT_BOTH,
        "edlonly": _SAVE_ONLINE_FORMAT_EDL,
        "edl": _SAVE_ONLINE_FORMAT_EDL,
        "xml": _SAVE_ONLINE_FORMAT_XML,
        "chaptersxmlonly": _SAVE_ONLINE_FORMAT_XML,
        "chapterxmlonly": _SAVE_ONLINE_FORMAT_XML,
    }
    hit = aliases.get(key)
    if hit:
        return hit
    return _SAVE_ONLINE_FORMAT_BOTH


_SEGMENT_PRIORITY_STORAGE = frozenset({"LocalFirst", "OnlineFirst"})
_SEGMENT_PRIORITY_BY_LABEL = {
    normalize_label("Local first"): "LocalFirst",
    normalize_label("Online first"): "OnlineFirst",
}


def _normalize_segment_source_priority(raw):
    """Map labelenum storage value or human-readable label to LocalFirst / OnlineFirst."""
    s = (raw or "").strip()
    if s in _SEGMENT_PRIORITY_STORAGE:
        return s
    mapped = _SEGMENT_PRIORITY_BY_LABEL.get(normalize_label(s))
    if mapped:
        log_service_detail(
            "segment_source_priority value %r normalized to %s" % (s, mapped),
            tag="policy",
        )
        return mapped
    log("Unknown segment_source_priority %r — using LocalFirst" % (s,))
    return "LocalFirst"
