# -*- coding: utf-8 -*-
"""Statistics modal: skips, time saved, and online segment traffic."""

from __future__ import annotations

from settings_utils import (
    format_segment_label_for_ui,
    get_addon,
    get_localized,
    log,
    notify_skippy,
)
from skippy_stats import load_statistics, reset_statistics


def format_saved_time(addon, seconds) -> str:
    """Human total: ``2h 14m`` / ``14m 05s`` / ``45s``."""
    try:
        total = max(0, int(float(seconds)))
    except (TypeError, ValueError):
        total = 0
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return get_localized(addon, 44022, "%dh %02dm", hours, minutes)
    if minutes:
        return get_localized(addon, 44023, "%dm %02ds", minutes, secs)
    return get_localized(addon, 44024, "%ds", secs)


def build_statistics_text(addon, stats=None) -> str:
    """Body text for the statistics modal."""
    data = stats if stats is not None else load_statistics()
    skips = data.get("skips") or {}
    online = data.get("online") or {}
    by_type = skips.get("by_type") or {}

    lines = [
        get_localized(
            addon,
            44021,
            "Time saved: %s",
            format_saved_time(addon, skips.get("seconds_saved")),
        ),
        get_localized(addon, 44025, "Segments skipped: %d", int(skips.get("total") or 0)),
        "",
        get_localized(addon, 44026, "Skips by segment type:"),
    ]
    if by_type:
        for label, count in sorted(by_type.items(), key=lambda kv: (-kv[1], kv[0])):
            lines.append("  • %s: %d" % (format_segment_label_for_ui(label), count))
    else:
        lines.append("  • %s" % get_localized(addon, 44027, "No skips recorded yet"))

    lines.extend(
        [
            "",
            get_localized(
                addon,
                44028,
                "Online segments downloaded: %d",
                int(online.get("segments_downloaded") or 0),
            ),
            get_localized(
                addon,
                44029,
                "Online segments uploaded: %d",
                int(online.get("segments_uploaded") or 0),
            ),
            "",
            get_localized(addon, 44030, "Counting since %s", data.get("since_utc") or "?"),
        ]
    )
    return "\n".join(lines)


def show_statistics_modal() -> None:
    """Open the statistics modal (read-only; reset has its own settings button)."""
    from skippy_editor_modal_skin import show_editor_ok

    addon = get_addon()
    heading = get_localized(addon, 44020, "Statistics")
    body = build_statistics_text(addon)
    try:
        show_editor_ok(heading, body, get_localized(addon, 40001, "Close"))
    except Exception as exc:
        log("⚠ Statistics modal failed (%s) — falling back to stock dialog" % exc)
        import xbmcgui

        try:
            xbmcgui.Dialog().ok(heading, body)
        except Exception:
            pass


def confirm_and_reset_statistics() -> None:
    """Ask once, then zero every counter."""
    from skippy_editor_modal_skin import sidecar_overwrite_yesno_show

    addon = get_addon()
    heading = get_localized(addon, 44020, "Statistics")
    message = get_localized(addon, 44033, "Reset all Skippy statistics to zero?")
    reset_label = get_localized(addon, 44031, "Reset")
    cancel_label = get_localized(addon, 35019, "Cancel")
    try:
        confirmed = sidecar_overwrite_yesno_show(
            heading, message, reset_label, cancel_label
        )
    except Exception as exc:
        log("⚠ Statistics reset prompt failed (%s) — using stock yesno" % exc)
        import xbmcgui

        try:
            confirmed = xbmcgui.Dialog().yesno(
                heading, message, nolabel=cancel_label, yeslabel=reset_label
            )
        except Exception:
            return
    if not confirmed:
        return
    reset_statistics()
    log("🧹 Statistics reset by user")
    notify_skippy(
        addon,
        get_localized(addon, 44036, "Statistics reset"),
        title=get_localized(addon, 43000, "Skippy"),
    )
