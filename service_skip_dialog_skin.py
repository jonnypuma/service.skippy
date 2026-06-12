"""Edit default skin XML for Full / Minimal skip dialog (720p and 1080i resources)."""

import os
import xml.etree.ElementTree as ET

from settings_utils import addon_get_bool, addon_get_setting_text, get_addon, log

_SKIP_DIALOG_FULL_FILES = (
    "SkipDialog_BottomRight.xml",
    "SkipDialog_BottomLeft.xml",
    "SkipDialog_TopLeft.xml",
    "SkipDialog_TopRight.xml",
    "SkipDialog.xml",
)
_FULL_MODE_PROGRESS_ID = "3014"
_FULL_MODE_SMOOTH_FILL_ID = "3031"
_SKIP_DIALOG_MINIMAL_FILES = (
    "Minimal_Skip_Dialog_BottomRight.xml",
    "Minimal_Skip_Dialog_BottomLeft.xml",
    "Minimal_Skip_Dialog_TopLeft.xml",
    "Minimal_Skip_Dialog_TopRight.xml",
)
_FULL_MODE_BUTTON_IDS = frozenset({"3012", "3013", "3015", "3016"})
_MINIMAL_PLATE_IMAGE_ID = "3021"
_DEFAULT_SKIP_DIALOG_CORNER = "Bottom Right"

_last_full_skip_textures = (None, None)
_last_minimal_plate_texture = None


def _skip_dialog_layout_suffix(addon, setting_id):
    """Stored value matches Full mode: e.g. 'Bottom Right' from values list."""
    raw = (
        (addon_get_setting_text(addon, setting_id, _DEFAULT_SKIP_DIALOG_CORNER) or "").strip()
        or _DEFAULT_SKIP_DIALOG_CORNER
    )
    return raw.replace(" ", "")


def _get_skins_res_dirs():
    addon = get_addon()
    if not addon:
        return []
    base = os.path.join(addon.getAddonInfo("path"), "resources", "skins", "default")
    dirs = []
    for res in ("720p", "1080i"):
        path = os.path.join(base, res)
        if os.path.isdir(path):
            dirs.append(path)
    return dirs


def _set_button_texturefocus(control, texture_path):
    for child in control:
        if child.tag == "texturefocus":
            child.text = texture_path
            return
    el = ET.SubElement(control, "texturefocus")
    el.text = texture_path


def _set_progress_midtexture(control, texture_path):
    for child in control:
        if child.tag == "midtexture":
            child.text = texture_path
            return
    el = ET.SubElement(control, "midtexture")
    el.text = texture_path


def _set_image_texture(control, texture_path):
    for child in control:
        if child.tag == "texture":
            child.text = texture_path
            return
    el = ET.SubElement(control, "texture")
    el.text = texture_path


def _write_skin_xml(tree, xml_path):
    try:
        ET.indent(tree, space="  ")
    except AttributeError:
        pass
    kwargs = {"encoding": "utf-8", "xml_declaration": True}
    try:
        tree.write(xml_path, short_empty_elements=False, **kwargs)
    except TypeError:
        tree.write(xml_path, **kwargs)


def warm_skip_dialog_skin_textures(addon=None):
    """Apply current skip-dialog texture settings once (cached — safe at service start)."""
    ad = addon or get_addon()
    if not ad:
        return
    mode = (addon_get_setting_text(ad, "skip_dialog_mode", "Full") or "Full").strip()
    if mode == "Minimal":
        plate = (addon_get_setting_text(ad, "minimal_button_style", "") or "").strip()
        if not plate.endswith(".png"):
            plate = "minimal_rounded_gray_640.png"
        _update_minimal_skip_dialog_textures(plate)
        return
    focus_texture_file = addon_get_setting_text(ad, "button_focus_style", "") or ""
    mid_texture_file = addon_get_setting_text(ad, "progress_bar_style", "") or ""
    if not focus_texture_file:
        focus_texture_file = "button_focus.png"
    if addon_get_bool(ad, "hide_close_button", False) and not addon_get_bool(
        ad, "show_skip_button_focus_texture", True
    ):
        focus_texture_file = "-"
    if not mid_texture_file:
        mid_texture_file = "progress_mid.png"
    _update_full_skip_dialog_textures(focus_texture_file, mid_texture_file)


def _update_full_skip_dialog_textures(focus_texture_path, mid_texture_path=None):
    """Set texturefocus on Full mode skip/close buttons; optional progress midtexture."""
    global _last_full_skip_textures
    try:
        mid_texture_path = (mid_texture_path or "").strip() or None
        cache_key = (focus_texture_path or "", mid_texture_path)
        if cache_key == _last_full_skip_textures:
            return
        xml_dirs = _get_skins_res_dirs()
        if not xml_dirs:
            return
        if not focus_texture_path and not mid_texture_path:
            return
        updated = []
        for xml_dir in xml_dirs:
            for xml_file in _SKIP_DIALOG_FULL_FILES:
                xml_path = os.path.join(xml_dir, xml_file)
                if not os.path.isfile(xml_path):
                    continue
                tree = ET.parse(xml_path)
                root = tree.getroot()
                for control in root.iter("control"):
                    ctype = control.get("type")
                    cid = control.get("id")
                    if ctype == "button" and cid in _FULL_MODE_BUTTON_IDS and focus_texture_path:
                        _set_button_texturefocus(control, focus_texture_path)
                    if (
                        mid_texture_path
                        and ctype == "progress"
                        and cid == _FULL_MODE_PROGRESS_ID
                    ):
                        _set_progress_midtexture(control, mid_texture_path)
                    if (
                        mid_texture_path
                        and ctype == "image"
                        and cid == _FULL_MODE_SMOOTH_FILL_ID
                    ):
                        _set_image_texture(control, mid_texture_path)
                _write_skin_xml(tree, xml_path)
                updated.append(os.path.join(os.path.basename(xml_dir), xml_file))
        if updated:
            _last_full_skip_textures = cache_key
            log(
                "📝 Full skip dialog skin XML (%s): button focus=%s, progress mid=%s"
                % (
                    ", ".join(updated),
                    focus_texture_path or "-",
                    mid_texture_path or "-",
                )
            )
    except Exception as e:
        log(f"⚠️ Failed to update Full skip dialog XML: {e}")


def _update_minimal_skip_dialog_textures(texture_filename):
    """Minimal chip: plate image 3021 + single skip button 3012 texturefocus."""
    global _last_minimal_plate_texture
    try:
        if texture_filename == _last_minimal_plate_texture:
            return
        xml_dirs = _get_skins_res_dirs()
        if not xml_dirs or not texture_filename:
            return
        for xml_dir in xml_dirs:
            for xml_file in _SKIP_DIALOG_MINIMAL_FILES:
                xml_path = os.path.join(xml_dir, xml_file)
                if not os.path.isfile(xml_path):
                    continue
                tree = ET.parse(xml_path)
                root = tree.getroot()
                for control in root.iter("control"):
                    ctype = control.get("type")
                    cid = control.get("id")
                    if ctype == "image" and cid == _MINIMAL_PLATE_IMAGE_ID:
                        _set_image_texture(control, texture_filename)
                    if ctype == "button" and cid == "3012":
                        _set_button_texturefocus(control, texture_filename)
                _write_skin_xml(tree, xml_path)
                log(
                    f"📝 Updated Minimal dialog {os.path.basename(xml_dir)}/{xml_file}: "
                    f"plate + button focus → {texture_filename}"
                )
        _last_minimal_plate_texture = texture_filename
    except Exception as e:
        log(f"⚠️ Failed to update Minimal skip dialog XML: {e}")
