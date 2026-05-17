# -*- coding: utf-8 -*-
"""Generate resources/settings.xml in Kodi settings version=\"1\" format."""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET

ADDON_ID = "service.skippy"

# --- helpers for legacy labelenum orientation ---
# Type A: values="|" are DISPLAY, optionvalues="|" are STORED (getSetting returns these)


def enum_a(display_pipe: str, stored_pipe: str) -> list[tuple[str, str]]:
    d = display_pipe.split("|")
    s = stored_pipe.split("|")
    assert len(d) == len(s), (display_pipe, stored_pipe)
    return list(zip(d, s))


# Type B: values="|" are STORED, optionvalues="|" are DISPLAY (progress mid, button focus, minimal plate)


def enum_b(stored_pipe: str, display_pipe: str) -> list[tuple[str, str]]:
    stores = stored_pipe.split("|")
    labels = display_pipe.split("|")
    assert len(stores) == len(labels), (stored_pipe, display_pipe)
    return list(zip(labels, stores))


def sub(parent: ET.Element, tag: str, text: str | None = None, **attrib) -> ET.Element:
    e = ET.SubElement(parent, tag, attrib)
    if text is not None:
        e.text = text
    return e


def add_deps(root_setting: ET.Element, visible=None, enable=None):
    if not visible and not enable:
        return
    dr = sub(root_setting, "dependencies")
    if visible:
        for set_id, val in visible:
            dep = ET.SubElement(dr, "dependency", type="visible", setting=set_id)
            dep.text = val
    if enable:
        for set_id, val in enable:
            dep = ET.SubElement(dr, "dependency", type="enable", setting=set_id)
            dep.text = val


def string_setting(
    g, sid, level, label, help_s, default="", hidden=False, vis=None, en=None
):
    s = ET.SubElement(g, "setting", id=sid, type="string", label=str(label), help=help_s)
    sub(s, "level", str(level))
    sub(s, "default", default)
    co = sub(s, "constraints")
    sub(co, "allowempty", "true")
    ctrl = sub(s, "control", type="edit", format="string")
    sub(ctrl, "heading", str(label))
    if hidden:
        sub(ctrl, "hidden", "true")
    add_deps(s, vis, en)
    return s


def bool_setting(g, sid, level, label, help_s, default: bool, vis=None, en=None):
    s = ET.SubElement(g, "setting", id=sid, type="boolean", label=str(label), help=help_s)
    sub(s, "level", str(level))
    sub(s, "default", "true" if default else "false")
    sub(s, "control", type="toggle")
    add_deps(s, vis, en)
    return s


def int_setting(
    g,
    sid,
    level,
    label,
    help_s,
    default: int,
    *,
    minimum=None,
    maximum=None,
    step=None,
    slider=False,
    vis=None,
    en=None,
):
    s = ET.SubElement(g, "setting", id=sid, type="integer", label=str(label), help=help_s)
    sub(s, "level", str(level))
    sub(s, "default", str(default))
    co = sub(s, "constraints")
    if minimum is not None:
        sub(co, "minimum", str(minimum))
    if maximum is not None:
        sub(co, "maximum", str(maximum))
    if step is not None:
        sub(co, "step", str(step))
    if slider:
        ctrl = sub(s, "control", type="slider", format="integer")
        sub(ctrl, "popup", "false")
    else:
        ctrl = sub(s, "control", type="edit", format="integer")
        sub(ctrl, "heading", str(label))
    add_deps(s, vis, en)
    return s


def labelenum_setting(g, sid, level, label, help_s, default_val, pairs, vis=None, en=None):
    """pairs: list of (display_label, stored_value)."""
    s = ET.SubElement(g, "setting", id=sid, type="string", label=str(label), help=help_s)
    sub(s, "level", str(level))
    sub(s, "default", default_val)
    co = sub(s, "constraints")
    opts = sub(co, "options")
    for disp, val in pairs:
        o = ET.SubElement(opts, "option", {"label": disp})
        o.text = val
    sub(co, "allowempty", "true")
    sub(s, "control", type="spinner", format="string")
    add_deps(s, vis, en)
    return s


def action_setting(g, sid, level, label, help_s, data, vis=None):
    s = ET.SubElement(g, "setting", id=sid, type="action", label=str(label), help=help_s)
    sub(s, "level", str(level))
    ctrl = sub(s, "control", type="button", format="action")
    sub(ctrl, "data", data)
    add_deps(s, vis, None)
    return s


def main():
    root = ET.Element("settings", version="1")
    section = ET.SubElement(root, "section", id=ADDON_ID)

    # ---- 30000 segments ----
    cat = ET.SubElement(section, "category", id="segments", label="30000")

    g = ET.SubElement(cat, "group", id="g_seg_keywords", label="31010")
    string_setting(
        g,
        "custom_segment_keywords",
        0,
        "31000",
        "Comma-separated list of chapterstrings (case-insensitive) the skipper should monitor.",
        default="intro,recap,main,credits,outro,prologue,epilogue,ad,ads,sponsor,sponsors,commercial,commercials,preview,next time on,next on,sneak peek,last time on,last on,previously on,closing,ending,behind the scenes,behind-the-scenes,bts,featurette",
    )

    g = ET.SubElement(cat, "group", id="g_seg1", label="31001")
    string_setting(
        g,
        "segment_always_skip",
        0,
        "31002",
        "Subset of your segment keywords that should skip automatically.",
        default="commercial,commercials,sponsor,sponsors,ad,ads",
    )
    string_setting(
        g,
        "segment_ask_skip",
        0,
        "31003",
        "Subset that should prompt you before skipping.",
        default="intro,recap,segment,preview,next time on,next on,sneak peek,last time on,last on,previously on,behind the scenes,behind-the-scenes,bts,featurette",
    )
    string_setting(
        g,
        "segment_never_skip",
        0,
        "31004",
        "Subset to always play, never skip.",
        default="prologue,epilogue,main,credits,outro,closing,ending",
    )
    bool_setting(
        g,
        "ignore_internal_edl_actions",
        1,
        "31005",
        "Skippy will ignore any EDL segment whose action type is not explicitly mapped in edl_action_mapping. This includes Kodi's internal action types and any unknown or custom types without a defined label. If set to false it will fall back to label 'Segment'.",
        True,
    )
    string_setting(
        g,
        "edl_action_mapping",
        1,
        "31006",
        "Format: action_type:label. Example: 4:Segment,5:Intro,6:Ad,7:Credits",
        default="4:Segment,5:Intro,6:Ad,7:Commercial,8:Credits,9:Recap,10:Prologue,11:Epilogue,12:Main,13:Outro,14:Unknown,15:Preview,16:Sponsor,17:Cold_open,18:Behind the scenes,19:Featurette",
    )
    bool_setting(
        g,
        "skip_overlapping_segments",
        2,
        "31007",
        "Configurable overlap detection to help avoid redundant or conflicting skips",
        True,
    )
    bool_setting(
        g,
        "open_segment_editor_on_overlap",
        2,
        "31011",
        "31012",
        False,
        vis=[("skip_overlapping_segments", "false")],
    )
    bool_setting(g, "use_embedded_chapters_fallback", 1, "31008", "31009", True)

    g = ET.SubElement(cat, "group", id="g_online", label="32045")
    labelenum_setting(
        g,
        "save_online_segments_format",
        2,
        "32077",
        "32078",
        "Both",
        enum_a("Both|EDL only|Chapters XML only", "Both|EDL|XML"),
    )
    bool_setting(g, "save_online_segments_to_chapters_xml", 2, "32046", "32047", False)
    labelenum_setting(
        g,
        "save_online_chapters_existing_policy",
        2,
        "32069",
        "32070",
        "SkipIfExists",
        enum_a(
            "Skip if exists|Overwrite (no prompt)|Overwrite (ask first)|Merge with existing|Update (no prompt)|Update (ask first)|Update All (no prompt)|Update All (ask first)",
            "SkipIfExists|OverwriteSilent|OverwriteAsk|Merge|UpdateSilent|UpdateAsk|UpdateAllSilent|UpdateAllAsk",
        ),
    )
    bool_setting(
        g, "save_online_chapters_backup_before_overwrite", 2, "32071", "32072", True
    )
    bool_setting(
        g,
        "online_sidecar_snap_neighbor_start",
        3,
        "32093",
        "32094",
        False,
        vis=[("save_online_segments_to_chapters_xml", "true")],
    )
    bool_setting(
        g,
        "online_sidecar_snap_neighbor_end",
        3,
        "32095",
        "32096",
        False,
        vis=[("save_online_segments_to_chapters_xml", "true")],
    )
    bool_setting(
        g,
        "tv_prefetch_next_episode",
        3,
        "31013",
        "31014",
        True,
        en=[("tv_use_online_segment_lookup", "true")],
    )

    # ---- 30001 playback ----
    cat = ET.SubElement(section, "category", id="playback", label="30001")
    # 32019 = Global options
    g = ET.SubElement(cat, "group", id="g_pb", label="32019")
    int_setting(
        g,
        "rewind_threshold_seconds",
        3,
        "32008",
        "If playback jumps backward more than this threshold, skip prompts will reset. Helps avoid false triggers from buffering or auto-rewind addons.",
        8,
        minimum=2,
        maximum=30,
    )
    int_setting(
        g,
        "skip_jump_offset_seconds",
        2,
        "32091",
        "32092",
        0,
        minimum=-5,
        maximum=5,
        step=1,
        slider=True,
    )
    bool_setting(g, "enable_skip_movies", 0, "32010", "32087", True)
    bool_setting(
        g,
        "show_skip_dialog_movies",
        0,
        "32017",
        "32089",
        True,
        vis=[("enable_skip_movies", "true")],
    )
    bool_setting(g, "enable_skip_episodes", 0, "32011", "32088", True)
    bool_setting(
        g,
        "show_skip_dialog_episodes",
        0,
        "32018",
        "32090",
        True,
        vis=[("enable_skip_episodes", "true")],
    )
    bool_setting(g, "hide_ending_text", 1, "32016", "32016", False)
    labelenum_setting(
        g,
        "skip_dialog_mode",
        0,
        "32020",
        "32020",
        "Full",
        enum_a("Full|Minimal", "Full|Minimal"),
    )
    labelenum_setting(
        g,
        "skip_dialog_font_color",
        1,
        "32026",
        "32026",
        "FFFFFFFF",
        enum_a(
            "White|Light grey|Grey|Dark grey|Black|Blue|Red|Green|Aquamarine|Pink|Purple|Peach|Orange|Yellow",
            "FFFFFFFF|FF8E8E8E|FF6E6E6E|FF3D3D3D|FF000000|FF1976D2|FFE5392F|FF43A047|FF00ACC1|FFE91E63|FF8E24AA|FFFF8A65|FFEF6C00|FFF9A825",
        ),
    )

    g = ET.SubElement(cat, "group", id="g_prog", label="32021")
    bool_setting(g, "show_progress_bar", 1, "32007", "32007", True)
    bool_setting(
        g,
        "progress_bar_countdown",
        1,
        "32027",
        "32027",
        False,
        en=[("show_progress_bar", "true")],
    )
    labelenum_setting(
        g,
        "progress_bar_style",
        2,
        "32079",
        "32079",
        "progress_mid.png",
        enum_b(
            "progress_mid.png|progress_mid_blue_purple.png|progress_mid_darkyellow.png|progress_mid_green_blue.png|progress_mid_lightblue.png|progress_mid_lightgreen.png|progress_mid_lightyellow.png|progress_mid_pink.png|progress_mid_pink_lightblue.png|progress_mid_purple.png|progress_mid_yellow_red.png",
            "Green (Default)|Blue/purple gradient|Dark yellow|Green/blue gradient|Light blue|Light green|Light yellow|Pink|Pink/light blue gradient|Purple|Yellow/red gradient",
        ),
        en=[("show_progress_bar", "true")],
    )
    int_setting(
        g,
        "progress_bar_height",
        2,
        "32080",
        "32080",
        16,
        minimum=5,
        maximum=32,
        step=1,
        slider=True,
        en=[("show_progress_bar", "true")],
    )
    bool_setting(
        g,
        "smooth_progress_bar",
        2,
        "32083",
        "32084",
        False,
        en=[("show_progress_bar", "true")],
    )
    int_setting(
        g,
        "progress_bar_updates_per_second",
        2,
        "32085",
        "32086",
        4,
        minimum=2,
        maximum=120,
        step=1,
        slider=True,
        en=[
            ("show_progress_bar", "true"),
            ("smooth_progress_bar", "true"),
        ],
    )
    labelenum_setting(
        g,
        "skip_dialog_position",
        0,
        "32009",
        "32009",
        "BottomRight",
        enum_a(
            "Bottom Right|Top Right|Top Left|Bottom Left",
            "BottomRight|TopRight|TopLeft|BottomLeft",
        ),
    )
    labelenum_setting(
        g,
        "button_focus_style",
        1,
        "32000",
        "32000",
        "button_focus.png",
        enum_b(
            "button_focus.png|button_focus_aqua.png|button_focus_aqua_bevel.png|button_focus_aqua_dark.png|button_focus_aqua_vignette.png|button_focus_aqua_rounded.png|button_focus_blue.png|button_focus_blue_rectangular_3d.png|button_focus_blue_rounded_3d.png|button_focus_gold_rectangular_3d.png",
            "Default|Aqua|Aqua Bevel|Aqua Dark|Aqua Vignette|Aqua Rounded|Blue|Blue Rectangular 3D|Blue Rounded 3D|Gold Rectangular 3D",
        ),
    )
    labelenum_setting(
        g,
        "skip_button_format",
        1,
        "32013",
        "32013",
        "Skip + Type + Duration",
        enum_a(
            "Skip|Skip + Type|Skip + Type + Duration",
            "Skip|Skip + Type|Skip + Type + Duration",
        ),
    )
    bool_setting(g, "hide_close_button", 1, "32014", "32014", False)
    bool_setting(
        g,
        "show_skip_button_focus_texture",
        1,
        "32081",
        "32082",
        True,
        en=[("hide_close_button", "true")],
    )
    bool_setting(g, "hide_skip_icon", 1, "32015", "32015", False)

    g = ET.SubElement(cat, "group", id="g_min", label="32022")
    MINIMAL_FN = (
        "minimal_rounded_gray_640.png|minimal_rectangular_aquamarine-blue_640.png|"
        "minimal_rectangular_blue_640.png|minimal_rectangular_yellow_640.png|"
        "minimal_rounded_baby-purple_640.png|minimal_rounded_blue-red-gradient_640.png|"
        "minimal_rounded_bright-aqua_640.png|minimal_rounded_bright-blue-sky_640.png|"
        "minimal_rounded_bright-cyan_640.png|minimal_rounded_burnt-pink_640.png|"
        "minimal_rounded_cranberry_640.png|minimal_rounded_deep-pink_640.png|"
        "minimal_rounded_greyish-blue_640.png|minimal_rounded_languid-lavender_640.png|"
        "minimal_rounded_light-green-7284348_640.png|minimal_rounded_light-grey_640.png|"
        "minimal_rounded_light-yellow_640.png|minimal_rounded_minty-green_640.png|"
        "minimal_rounded_mustard-yellow_640.png|minimal_rounded_pale-gold_640.png|"
        "minimal_rounded_pale-sky-blue_640.png|minimal_rounded_pastel-green_640.png|"
        "minimal_rounded_pattens-blue_640.png|minimal_rounded_peach-orange_640.png|"
        "minimal_rounded_pink-daisy_640.png|minimal_rounded_pink-lemonade_640.png|"
        "minimal_rounded_pinkish-orange_640.png|minimal_rounded_sunset_640.png|"
        "minimal_rounded_white_640.png"
    )
    MINIMAL_LB = (
        "Rounded Gray|Rectangular Aquamarine Blue|Rectangular Blue|Rectangular Yellow|"
        "Rounded Baby Purple|Rounded Blue Red Gradient|Rounded Bright Aqua|"
        "Rounded Bright Blue Sky|Rounded Bright Cyan|Rounded Burnt Pink|Rounded Cranberry|"
        "Rounded Deep Pink|Rounded Greyish Blue|Rounded Languid Lavender|"
        "Rounded Light Green 7284348|Rounded Light Grey|Rounded Light Yellow|"
        "Rounded Minty Green|Rounded Mustard Yellow|Rounded Pale Gold|"
        "Rounded Pale Sky Blue|Rounded Pastel Green|Rounded Pattens Blue|"
        "Rounded Peach Orange|Rounded Pink Daisy|Rounded Pink Lemonade|"
        "Rounded Pinkish Orange|Rounded Sunset|Rounded White"
    )
    labelenum_setting(
        g,
        "minimal_button_style",
        1,
        "32023",
        "32023",
        "minimal_rounded_gray_640.png",
        enum_b(MINIMAL_FN, MINIMAL_LB),
    )
    labelenum_setting(
        g,
        "minimal_skip_button_format",
        1,
        "32025",
        "32025",
        "Skip + Type",
        enum_a(
            "Skip|Skip + Type|Skip + Type + Duration",
            "Skip|Skip + Type|Skip + Type + Duration",
        ),
    )
    labelenum_setting(
        g,
        "minimal_skip_dialog_position",
        0,
        "32024",
        "32024",
        "BottomRight",
        enum_a(
            "Bottom Right|Top Right|Top Left|Bottom Left",
            "BottomRight|TopRight|TopLeft|BottomLeft",
        ),
    )

    # ---- 30004 sources ----
    cat = ET.SubElement(section, "category", id="sources", label="30004")
    g = ET.SubElement(cat, "group", id="g_tv0", label="32036")
    bool_setting(g, "tv_tmdb_resolve_missing_ids", 3, "32031", "32035", True)
    string_setting(g, "tv_tmdb_api_key", 3, "32032", "32033", "", hidden=True)
    bool_setting(g, "tv_tmdb_use_helper_api_key", 3, "32034", "32037", True)
    int_setting(
        g,
        "remote_api_failure_cooldown_seconds",
        3,
        "32073",
        "32074",
        120,
        minimum=0,
        maximum=3600,
    )
    g = ET.SubElement(cat, "group", id="g_tv1", label="32059")
    bool_setting(g, "tv_use_local_chapter_edl", 0, "32028", "32061", True)
    bool_setting(g, "tv_use_online_segment_lookup", 0, "32029", "32062", False)
    labelenum_setting(
        g,
        "tv_online_merge_priority",
        0,
        "32065",
        "32066",
        "TheIntroDBFirst",
        enum_a(
            "TheIntroDB first|IntroDB.app first", "TheIntroDBFirst|IntroDBFirst"
        ),
    )
    labelenum_setting(
        g,
        "tv_segment_source_priority",
        0,
        "32030",
        "32063",
        "LocalFirst",
        enum_a("Local first|Online first", "LocalFirst|OnlineFirst"),
    )
    g = ET.SubElement(cat, "group", id="g_mov", label="32060")
    bool_setting(g, "movie_use_local_chapter_edl", 0, "32028", "32052", True)
    bool_setting(g, "movie_use_online_segment_lookup", 0, "32029", "32064", False)
    labelenum_setting(
        g,
        "movie_online_merge_priority",
        0,
        "32067",
        "32068",
        "TheIntroDBFirst",
        enum_a(
            "TheIntroDB first|IntroDB.app first", "TheIntroDBFirst|IntroDBFirst"
        ),
    )
    labelenum_setting(
        g,
        "movie_segment_source_priority",
        0,
        "32030",
        "32054",
        "LocalFirst",
        enum_a("Local first|Online first", "LocalFirst|OnlineFirst"),
    )

    # ---- 30002 toasts ----
    cat = ET.SubElement(section, "category", id="toasts", label="30002")
    g = ET.SubElement(cat, "group", id="g_toast", label="")
    bool_setting(
        g,
        "show_not_found_toast_for_tv_episodes",
        0,
        "33000",
        "Show a notification if no readable sidecar (.edl or chapters.xml) is found for the current episode.",
        True,
    )
    bool_setting(
        g,
        "show_not_found_toast_for_movies",
        0,
        "33001",
        "Show a notification if no readable sidecar (.edl or chapters.xml) is found for the current movie.",
        False,
    )
    bool_setting(
        g,
        "show_toast_for_overlapping_nested_segments",
        2,
        "33002",
        "Show a notification if the sidecar (.edl or chapters.xml) has overlapping segments.",
        False,
    )
    bool_setting(
        g,
        "show_toast_for_skipped_segment",
        0,
        "33003",
        "Show a toast notification if a segment is skipped.",
        True,
    )

    # ---- 30005 marker ----
    cat = ET.SubElement(section, "category", id="marker", label="30005")
    g = ET.SubElement(cat, "group", id="g_marker", label="")
    v_marker = [("segment_marker_enabled", "true")]
    bool_setting(g, "segment_marker_enabled", 0, "36000", "36001", False)
    bool_setting(
        g, "segment_marker_auto_save", 1, "36002", "36003", False, vis=v_marker
    )
    bool_setting(
        g,
        "segment_marker_show_indicator",
        1,
        "36004",
        "36005",
        True,
        vis=v_marker,
    )
    labelenum_setting(
        g,
        "segment_marker_save_format",
        2,
        "36017",
        "36018",
        "Both",
        enum_a("Both|EDL only|Chapters XML only", "Both|EDL|XML"),
        vis=v_marker,
    )
    labelenum_setting(
        g,
        "segment_marker_file_permissions",
        2,
        "36006",
        "36007",
        "Default",
        enum_a(
            "Leave unchanged (no chmod)|World-readable (644)|World-writable (666)",
            "Default|644|666",
        ),
        vis=v_marker,
    )
    labelenum_setting(
        g,
        "segment_marker_existing_policy",
        2,
        "36031",
        "36032",
        "MergeNonOverlapping",
        enum_a(
            "Merge non-overlapping|Keep both (old starts after new)|Overwrite overlapping|Append always|Replace file|Ask each time",
            "MergeNonOverlapping|KeepBothOldAfterNew|OverwriteOverlapping|AppendAlways|ReplaceFile|AskEachTime",
        ),
        vis=v_marker,
    )
    bool_setting(
        g,
        "segment_marker_backup_before_write",
        1,
        "36033",
        "36034",
        True,
        vis=v_marker,
    )
    string_setting(
        g,
        "segment_marker_keyboard_shortcut",
        2,
        "36019",
        "36020",
        "ctrl+e",
        vis=v_marker,
    )
    labelenum_setting(
        g,
        "segment_marker_keyboard_press_type",
        2,
        "36029",
        "36030",
        "normal",
        enum_a("Normal press|Long press", "normal|longpress"),
        vis=v_marker,
    )
    string_setting(
        g,
        "segment_marker_remote_button",
        2,
        "36021",
        "36022",
        "",
        vis=v_marker,
    )
    labelenum_setting(
        g,
        "segment_marker_remote_press_type",
        2,
        "36027",
        "36028",
        "normal",
        enum_a("Normal press|Long press", "normal|longpress"),
        vis=v_marker,
    )
    action_setting(
        g,
        "segment_marker_action_discover",
        2,
        "36023",
        "36024",
        "RunScript(service.skippy,discover_button)",
        vis=v_marker,
    )
    action_setting(
        g,
        "segment_marker_action_keymap",
        2,
        "36025",
        "36026",
        "RunScript(service.skippy,install_keymap)",
        vis=v_marker,
    )

    # ---- 30006 editor ----
    cat = ET.SubElement(section, "category", id="editor", label="30006")
    g = ET.SubElement(cat, "group", id="g_edit", label="")
    v_ed = [("segment_editor_enabled", "true")]
    bool_setting(g, "segment_editor_enabled", 1, "37000", "37001", False)
    labelenum_setting(
        g,
        "segment_editor_save_format",
        2,
        "36017",
        "37002",
        "Both",
        enum_a("Both|EDL only|Chapters XML only", "Both|EDL|XML"),
        vis=v_ed,
    )
    labelenum_setting(
        g,
        "segment_editor_file_permissions",
        2,
        "36006",
        "36007",
        "Default",
        enum_a(
            "Leave unchanged (no chmod)|World-readable (644)|World-writable (666)",
            "Default|644|666",
        ),
        vis=v_ed,
    )
    bool_setting(
        g,
        "segment_editor_backup_before_write",
        2,
        "36033",
        "36034",
        True,
        vis=v_ed,
    )
    bool_setting(
        g,
        "segment_editor_fullscreen_overlay",
        1,
        "37010",
        "37011",
        False,
        vis=v_ed,
    )
    string_setting(
        g,
        "segment_editor_keyboard_shortcut",
        2,
        "37004",
        "37005",
        "ctrl+shift+e",
        vis=v_ed,
    )
    labelenum_setting(
        g,
        "segment_editor_keyboard_press_type",
        2,
        "36029",
        "36030",
        "normal",
        enum_a("Normal press|Long press", "normal|longpress"),
        vis=v_ed,
    )
    string_setting(
        g,
        "segment_editor_remote_button",
        2,
        "37006",
        "37007",
        "",
        vis=v_ed,
    )
    labelenum_setting(
        g,
        "segment_editor_remote_press_type",
        2,
        "37008",
        "37009",
        "normal",
        enum_a("Normal press|Long press", "normal|longpress"),
        vis=v_ed,
    )
    action_setting(
        g,
        "segment_editor_action_discover",
        2,
        "37014",
        "37015",
        "RunScript(service.skippy,discover_editor_button)",
        vis=v_ed,
    )
    action_setting(
        g,
        "segment_editor_action_keymap",
        2,
        "37016",
        "37017",
        "RunScript(service.skippy,install_editor_keymap)",
        vis=v_ed,
    )

    # ---- 39000 online segment upload (Expert) ----
    cat = ET.SubElement(section, "category", id="online_upload", label="39000")
    g = ET.SubElement(cat, "group", id="g_online_upload", label="")
    bool_setting(
        g,
        "online_upload_enabled",
        3,
        "39025",
        "39026",
        False,
    )
    labelenum_setting(
        g,
        "online_upload_default_target",
        3,
        "39001",
        "39002",
        "Both",
        enum_a(
            "Both|TheIntroDB.org|IntroDB.app",
            "Both|TheIntroDB|IntroDBApp",
        ),
    )
    string_setting(
        g,
        "online_upload_theintrodb_api_key",
        3,
        "39003",
        "39004",
        default="",
        hidden=True,
    )
    string_setting(
        g,
        "online_upload_introdb_api_key",
        3,
        "39005",
        "39006",
        default="",
        hidden=True,
    )

    # ---- 30007 backup / restore ----
    cat = ET.SubElement(section, "category", id="backup", label="30007")
    g = ET.SubElement(cat, "group", id="g_backup", label="")
    action_setting(
        g,
        "settings_action_backup",
        2,
        "38000",
        "38001",
        "RunScript(service.skippy,backup_settings)",
    )
    action_setting(
        g,
        "settings_action_restore",
        2,
        "38002",
        "38003",
        "RunScript(service.skippy,restore_settings)",
    )

    # ---- 30003 debug ----
    cat = ET.SubElement(section, "category", id="debug", label="30003")
    g = ET.SubElement(cat, "group", id="g_dbg", label="")
    bool_setting(g, "enable_verbose_logging", 3, "34000", "34001", False)
    labelenum_setting(
        g,
        "skippy_log_detail_level",
        3,
        "34002",
        "34003",
        "Normal",
        enum_a("Errors only|Normal|All detail", "ErrorOnly|Normal|All"),
        en=[("enable_verbose_logging", "true")],
    )

    ET.indent(root, space="    ")
    out_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "resources",
        "settings.xml",
    )
    tree = ET.ElementTree(root)
    tree.write(out_path, encoding="utf-8", xml_declaration=True)
    with open(out_path, encoding="utf-8") as f:
        x = f.read()
    x = x.replace(
        '<?xml version=\'1.0\' encoding=\'utf-8\'?>',
        '<?xml version="1.0" encoding="utf-8" standalone="yes"?>',
    )
    x = x.replace(
        "<?xml version='1.0' encoding='utf-8'?>",
        '<?xml version="1.0" encoding="utf-8" standalone="yes"?>',
    )
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(x)
    print("Wrote", out_path)


if __name__ == "__main__":
    main()
