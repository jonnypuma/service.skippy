"""Edit default skin XML for Full / Minimal skip dialog (720p resources)."""

import os
import xml.etree.ElementTree as ET

from settings_utils import addon_get_setting_text, get_addon, log

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


def _skip_dialog_layout_suffix(addon, setting_id):
    """Stored value matches Full mode: e.g. 'Bottom Right' from values list."""
    raw = (
        (addon_get_setting_text(addon, setting_id, _DEFAULT_SKIP_DIALOG_CORNER) or "").strip()
        or _DEFAULT_SKIP_DIALOG_CORNER
    )
    return raw.replace(" ", "")


def _get_skins_720p_dir():
    addon = get_addon()
    if not addon:
        return None
    return os.path.join(
        addon.getAddonInfo("path"), "resources", "skins", "default", "720p"
    )


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


def _update_full_skip_dialog_textures(focus_texture_path, mid_texture_path=None):
    """Set texturefocus on Full mode skip/close buttons; optional progress midtexture."""
    try:
        xml_dir = _get_skins_720p_dir()
        if not xml_dir:
            return
        if not focus_texture_path and not (mid_texture_path or "").strip():
            return
        mid_texture_path = (mid_texture_path or "").strip() or None
        updated = []
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
            updated.append(xml_file)
        if updated:
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
    try:
        xml_dir = _get_skins_720p_dir()
        if not xml_dir or not texture_filename:
            return
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
            log(f"📝 Updated Minimal dialog {xml_file}: plate + button focus → {texture_filename}")
    except Exception as e:
        log(f"⚠️ Failed to update Minimal skip dialog XML: {e}")
