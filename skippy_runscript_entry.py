# -*- coding: utf-8 -*-
"""Thin RunScript entry for service.skippy.

Kodi parses the whole script file before executing. If ``segment_marker.py`` is ever
broken (syntax), ``RunScript(..., open_segment_editor)`` still must work — that handler
runs here **without** importing ``segment_marker``.

Marker hotkey runs ``RunScript(service.skippy)`` with no args; that path imports
``segment_marker`` normally.
"""

import sys


def _addon():
    import xbmcaddon

    try:
        return xbmcaddon.Addon("service.skippy")
    except Exception:
        return None


def main():
    if len(sys.argv) > 1:
        command = (sys.argv[1] or "").strip().lower()

        # --- Editor / keymap / settings (no dependency on parsing segment_marker.py) ---
        if command == "open_segment_editor":
            from segment_editor_session import open_segment_editor

            open_segment_editor()
            return
        if command == "discover_editor_button":
            from segment_editor import discover_editor_remote_button

            addon = _addon()
            if addon:
                discover_editor_remote_button(addon)
            return
        if command == "install_editor_keymap":
            from keymap_utils import install_editor_keymap

            addon = _addon()
            install_editor_keymap(addon if addon else None, notify=True)
            return

        # --- Marker installer / discovery (heavy UI lives in segment_marker) ---
        if command == "discover_button":
            import segment_marker

            addon = segment_marker.get_addon()
            if addon:
                segment_marker.discover_remote_button(addon)
            return
        if command == "install_keymap":
            import segment_marker
            from keymap_utils import install_marker_keymap

            addon = segment_marker.get_addon()
            install_marker_keymap(addon if addon else None, notify=True)
            return

        # --- Statistics / per-title overrides ---
        if command == "show_statistics":
            from skippy_statistics_ui import show_statistics_modal

            show_statistics_modal()
            return
        if command == "reset_statistics":
            from skippy_statistics_ui import confirm_and_reset_statistics

            confirm_and_reset_statistics()
            return
        if command == "manage_show_overrides":
            from per_show_overrides_ui import show_manage_title_autoskip_modal

            show_manage_title_autoskip_modal()
            return
        if command == "clear_show_overrides":
            from per_show_overrides import clear_all_overrides
            from settings_utils import get_localized, notify_skippy

            addon = _addon()
            removed = clear_all_overrides()
            if removed:
                message = get_localized(
                    addon, 44009, "Cleared %d saved per-title choice(s).", removed
                )
            else:
                message = get_localized(
                    addon, 44010, "No saved per-title choices to clear."
                )
            notify_skippy(
                addon, message, title=get_localized(addon, 43000, "Skippy")
            )
            return

        # --- Backup / restore (delegated modules only) ---
        if command == "backup_settings":
            from settings_backup import run_backup_ui
            from settings_utils import skippy_notification_icon

            import segment_marker

            addon = segment_marker.get_addon()
            if addon:
                run_backup_ui(
                    addon,
                    skippy_notification_icon(addon) or "",
                    segment_marker.log,
                )
            return
        if command == "restore_settings":
            from settings_backup import run_restore_ui
            from settings_utils import skippy_notification_icon

            import segment_marker

            addon = segment_marker.get_addon()
            if addon:
                run_restore_ui(
                    addon,
                    skippy_notification_icon(addon) or "",
                    segment_marker.log,
                )
            return
        if command in ("backup_profile_data", "backup_upload_history"):
            from skippy_profile_backup import run_backup_ui
            from settings_utils import skippy_notification_icon

            import segment_marker

            addon = segment_marker.get_addon()
            if addon:
                run_backup_ui(
                    addon,
                    skippy_notification_icon(addon) or "",
                    segment_marker.log,
                )
            return
        if command in ("restore_profile_data", "restore_upload_history"):
            from skippy_profile_backup import run_restore_ui
            from settings_utils import skippy_notification_icon

            import segment_marker

            addon = segment_marker.get_addon()
            if addon:
                run_restore_ui(
                    addon,
                    skippy_notification_icon(addon) or "",
                    segment_marker.log,
                )
            return

    import segment_marker

    segment_marker.main()


if __name__ == "__main__":
    main()
