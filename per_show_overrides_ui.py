# -*- coding: utf-8 -*-
"""Settings UI for browsing and deleting per-title auto-skip rules."""

from __future__ import annotations

from per_show_overrides import delete_override, list_title_entries
from settings_utils import (
    format_segment_label_for_ui,
    get_addon,
    get_localized,
    log,
    notify_skippy,
)


def format_title_entry_label(entry: dict) -> str:
    """One list row: ``Friends — Intro, Recap``."""
    title = (entry.get("title") or entry.get("key") or "?").strip() or "?"
    labels = [
        format_segment_label_for_ui(label)
        for label in (entry.get("auto_labels") or [])
    ]
    if not labels:
        return title
    return "%s — %s" % (title, ", ".join(labels))


def show_manage_title_autoskip_modal() -> None:
    """
    List titles with saved auto-skip rules; selecting one offers to delete that entry.

    Loops until the user cancels or the list is empty.
    """
    from skippy_editor_modal_skin import (
        show_editor_list_pick,
        show_editor_ok,
        sidecar_overwrite_yesno_show,
    )

    addon = get_addon()
    heading = get_localized(addon, 44060, "Title autoskip")
    empty_msg = get_localized(
        addon, 44063, "No titles with auto-skip saved yet."
    )
    subtitle = get_localized(
        addon, 44064, "Select a title to remove its auto-skip rules."
    )
    delete_label = get_localized(addon, 44070, "Delete")
    cancel_label = get_localized(addon, 35019, "Cancel")

    while True:
        entries = list_title_entries(auto_only=True)
        if not entries:
            try:
                show_editor_ok(heading, empty_msg)
            except Exception as exc:
                log("⚠ Title autoskip empty dialog failed (%s)" % exc)
            return

        options = [format_title_entry_label(entry) for entry in entries]
        try:
            index = show_editor_list_pick(
                heading,
                options,
                subtitle=subtitle,
                cancel_label=get_localized(addon, 40001, "Close"),
            )
        except Exception as exc:
            log("⚠ Title autoskip list failed (%s) — falling back to stock select" % exc)
            import xbmcgui

            try:
                index = xbmcgui.Dialog().select(heading, options)
            except Exception:
                return

        if index < 0 or index >= len(entries):
            return

        entry = entries[index]
        title = entry.get("title") or entry.get("key") or "?"
        confirm_msg = "%s\n\n%s" % (
            get_localized(addon, 44065, "Remove auto-skip for %s?", title),
            get_localized(
                addon,
                44066,
                "This deletes the saved auto-skip rules for this title so Skippy will ask again.",
            ),
        )
        try:
            confirmed = sidecar_overwrite_yesno_show(
                heading, confirm_msg, delete_label, cancel_label
            )
        except Exception as exc:
            log("⚠ Title autoskip delete confirm failed (%s) — using stock yesno" % exc)
            import xbmcgui

            try:
                confirmed = xbmcgui.Dialog().yesno(
                    heading,
                    confirm_msg,
                    nolabel=cancel_label,
                    yeslabel=delete_label,
                )
            except Exception:
                return

        if not confirmed:
            continue

        if delete_override(entry["key"]):
            notify_skippy(
                addon,
                get_localized(addon, 44067, "Removed auto-skip for %s", title),
                title=get_localized(addon, 43000, "Skippy"),
            )
        else:
            notify_skippy(
                addon,
                get_localized(addon, 44068, "Could not remove that title entry."),
                title=get_localized(addon, 43000, "Skippy"),
            )
