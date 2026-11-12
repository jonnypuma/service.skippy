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


def _name_value_row(line, value):
    """``PanelRow`` with the name at the left and the value at the right when the translated
    line ends with its value (``Time saved: 2m 05s``); otherwise the whole line is the name."""
    from skippy_panel_ui import PanelRow

    value = str(value)
    if value and line.endswith(value):
        name = line[: -len(value)].rstrip().rstrip(":\uff1a").rstrip()
        if name:
            return PanelRow(name, value)
    return PanelRow(line)


# The per-title list stops here; the rest is summed in one "and N more" line.
MAX_TITLE_ROWS = 25


def titles_by_time_saved(by_title):
    """``[(name, seconds_saved, skips)]`` most time saved first; nameless rows dropped."""
    rows = []
    for key, row in (by_title or {}).items():
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip() or str(key).split(":", 1)[-1]
        if not name:
            continue
        try:
            seconds = float(row.get("seconds_saved") or 0.0)
            skips = int(row.get("skips") or 0)
        except (TypeError, ValueError):
            continue
        rows.append((name, seconds, skips))
    rows.sort(key=lambda r: (-r[1], -r[2], r[0].lower()))
    return rows


def _title_lines(addon, by_title):
    """``(name, value)`` pairs for the per-title section, capped at :data:`MAX_TITLE_ROWS`."""
    titles = titles_by_time_saved(by_title)
    out = [(name, format_saved_time(addon, seconds)) for name, seconds, _ in titles[:MAX_TITLE_ROWS]]
    rest = titles[MAX_TITLE_ROWS:]
    if rest:
        out.append(
            (
                get_localized(addon, 48001, "And %d more", len(rest)),
                format_saved_time(addon, sum(seconds for _, seconds, _ in rest)),
            )
        )
    return out


def build_statistics_rows(addon, stats=None):
    """``(rows, footnote)`` for the statistics panel: name at the left, value at the right."""
    from skippy_panel_ui import PanelRow

    data = stats if stats is not None else load_statistics()
    skips = data.get("skips") or {}
    online = data.get("online") or {}
    by_type = skips.get("by_type") or {}

    saved = format_saved_time(addon, skips.get("seconds_saved"))
    total = int(skips.get("total") or 0)
    downloaded = int(online.get("segments_downloaded") or 0)
    uploaded = int(online.get("segments_uploaded") or 0)
    heading = get_localized(addon, 44026, "Skips by segment type:")
    rows = [
        _name_value_row(get_localized(addon, 44021, "Time saved: %s", saved), saved),
        _name_value_row(get_localized(addon, 44025, "Segments skipped: %d", total), total),
        PanelRow(heading.rstrip().rstrip(":\uff1a").rstrip(), header=True),
    ]
    if by_type:
        for label, count in sorted(by_type.items(), key=lambda kv: (-kv[1], kv[0])):
            rows.append(PanelRow(format_segment_label_for_ui(label), str(int(count))))
    else:
        rows.append(PanelRow(get_localized(addon, 44027, "No skips recorded yet")))
    titles = _title_lines(addon, skips.get("by_title"))
    if titles:
        title_heading = get_localized(addon, 48000, "Time saved by show or film:")
        rows.append(PanelRow(title_heading.rstrip().rstrip(":\uff1a").rstrip(), header=True))
        for name, value in titles:
            rows.append(PanelRow(name, value))
    rows.append(PanelRow("", header=True))
    rows.append(
        _name_value_row(
            get_localized(addon, 44028, "Online segments downloaded: %d", downloaded),
            downloaded,
        )
    )
    rows.append(
        _name_value_row(
            get_localized(addon, 44029, "Online segments uploaded: %d", uploaded), uploaded
        )
    )
    footnote = get_localized(addon, 44030, "Counting since %s", data.get("since_utc") or "?")
    return rows, footnote


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
    titles = _title_lines(addon, skips.get("by_title"))
    if titles:
        lines.extend(["", get_localized(addon, 48000, "Time saved by show or film:")])
        lines.extend("  • %s: %s" % (name, value) for name, value in titles)

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
    from skippy_panel_ui import show_panel_rows

    addon = get_addon()
    heading = get_localized(addon, 44020, "Statistics")
    try:
        rows, footnote = build_statistics_rows(addon)
        show_panel_rows(
            heading, rows, get_localized(addon, 40001, "Close"), footnote=footnote
        )
    except Exception as exc:
        log("⚠ Statistics modal failed (%s) — falling back to stock dialog" % exc)
        import xbmcgui

        try:
            xbmcgui.Dialog().ok(heading, build_statistics_text(addon))
        except Exception:
            pass


def confirm_and_reset_statistics() -> None:
    """Ask once, then zero every counter."""
    from skippy_panel_ui import show_panel_yesno

    addon = get_addon()
    heading = get_localized(addon, 44020, "Statistics")
    message = get_localized(addon, 44033, "Reset all Skippy statistics to zero?")
    reset_label = get_localized(addon, 44031, "Reset")
    cancel_label = get_localized(addon, 35019, "Cancel")
    try:
        confirmed = show_panel_yesno(heading, message, reset_label, cancel_label)
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
