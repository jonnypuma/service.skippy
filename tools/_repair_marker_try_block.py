"""Fix segment_marker.py main() broken try indentation (second-press save block)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "segment_marker.py"
lines = ROOT.read_text(encoding="utf-8").splitlines(True)

if_main_i = next(i for i, ln in enumerate(lines) if ln.strip().startswith("if __name__"))
anchors = [i for i, ln in enumerate(lines) if ln.strip() == "xbmc.sleep(500)"]
if len(anchors) != 1:
    raise SystemExit(f"ambiguous xbmc.sleep(500) lines: {[a+1 for a in anchors]}")
sleep_i = anchors[0]

new_middle = r"""    xbmc.sleep(500)

    try:
        save_format = addon.getSetting("segment_marker_save_format") or "Both"
        existing_policy = (
            addon.getSetting("segment_marker_existing_policy") or _MARKER_POLICY_MERGE
        )
        existing_policy = normalize_marker_policy(existing_policy)
        log(f"Marker save policy setting resolved to: {existing_policy}")
        if existing_policy == _MARKER_POLICY_ASK:
            if marker_selected_sidecars_exist(video_path, save_format):
                overlaps = marker_range_overlaps_existing(
                    video_path, save_format, start_time, end_time
                )
                chosen_policy = ask_marker_existing_policy(addon, overlaps)
                if not chosen_policy:
                    show_toast(get_localized(addon, 36014))
                    log("Marker save policy selection cancelled")
                    return
                existing_policy = chosen_policy
            else:
                log(
                    "AskEachTime selected but no sidecar exists for save format; skipping save-method picker"
                )
                existing_policy = _MARKER_POLICY_MERGE

        label = pick_segment_type(addon)
        if not label:
            show_toast(get_localized(addon, 36014))
            log("Segment type selection cancelled")
            return

        auto_save = addon.getSetting("segment_marker_auto_save") == "true"
        if not auto_save:
            if not confirm_save(addon, start_time, end_time, label):
                show_toast(get_localized(addon, 36014))
                log("Save cancelled by user")
                return

        perm_setting = addon.getSetting("segment_marker_file_permissions") or "Default"
        backup_before_write = (
            addon.getSetting("segment_marker_backup_before_write") == "true"
        )

        edl_ok = False
        xml_ok = False

        if save_format in ("Both", "EDL"):
            edl_ok = save_to_edl(
                video_path,
                start_time,
                end_time,
                label,
                perm_setting,
                addon,
                policy=existing_policy,
                backup_before_write=backup_before_write,
            )

        if save_format in ("Both", "XML"):
            xml_ok = save_to_chapters_xml(
                video_path,
                start_time,
                end_time,
                label,
                perm_setting,
                addon,
                policy=existing_policy,
                backup_before_write=backup_before_write,
            )

        edl_saved = edl_ok is True
        xml_saved = xml_ok is True
        edl_skipped = edl_ok == "skipped"
        xml_skipped = xml_ok == "skipped"

        if save_format == "Both":
            if edl_saved and xml_saved:
                show_toast(f"{get_localized(addon, 36012)}: {label}")
                log(f"Segment saved: {label} [{start_time}-{end_time}]")
            elif (edl_skipped and xml_skipped) or (
                (edl_skipped or xml_skipped) and not (edl_saved or xml_saved)
            ):
                show_toast("Segment overlaps existing entry; not changed")
                log(
                    "Marker save skipped by merge policy because the range overlaps existing entries"
                )
            elif edl_saved or xml_saved:
                partial = "EDL" if edl_saved else "chapters.xml"
                show_toast(f"Partial save ({partial})")
                log(f"Partial save: EDL={edl_ok}, XML={xml_ok}")
            else:
                show_toast(get_localized(addon, 36013))
                log("Failed to save segment to both files")
        elif save_format == "EDL":
            if edl_saved:
                show_toast(f"{get_localized(addon, 36012)}: {label} (EDL)")
                log(f"Segment saved to EDL: {label} [{start_time}-{end_time}]")
            elif edl_skipped:
                show_toast("Segment overlaps existing EDL entry; not changed")
                log("Marker EDL save skipped by merge policy")
            else:
                show_toast(get_localized(addon, 36013))
                log("Failed to save segment to EDL")
        elif save_format == "XML":
            if xml_saved:
                show_toast(f"{get_localized(addon, 36012)}: {label} (XML)")
                log(f"Segment saved to chapters.xml: {label} [{start_time}-{end_time}]")
            elif xml_skipped:
                show_toast("Segment overlaps existing XML chapter; not changed")
                log("Marker XML save skipped by merge policy")
            else:
                show_toast(get_localized(addon, 36013))
                log("Failed to save segment to chapters.xml")

    finally:
        set_marker_second_press_flow_active(False)
        clear_marker_pending_state()


"""

ROOT.write_text("".join(lines[:sleep_i]) + new_middle + "".join(lines[if_main_i:]), encoding="utf-8", newline="\n")
print("repaired splice at line", sleep_i + 1)
