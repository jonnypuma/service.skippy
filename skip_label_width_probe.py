# -*- coding: utf-8 -*-
"""Diagnostic: can a skin ``auto``-width label / button report its real text width?

Run in Kodi:  RunScript(service.skippy,label_width_probe)

It opens a small dialog holding three controls (all font16, the skip dialog's font):
an ``auto`` width label, an ``auto`` width button and a fixed 600px label. For each sample
text it reads ``getWidth()`` from each control and compares with Skippy's glyph estimate.
Result: a text viewer plus a ``label_width_probe.json`` file in the add-on profile.
If the auto controls grow with the text while the fixed one stays 600, ``getWidth()`` can
replace the estimate in ``skip_dialog_appearance``.
"""
from __future__ import annotations

import json

import xbmc
import xbmcgui

from addon_skin_resolution import init_window_xml_dialog, scale_skin_coord
from settings_utils import get_addon, log

AUTO_LABEL_ID = 9001
AUTO_BUTTON_ID = 9002
FIXED_LABEL_ID = 9003
FIXED_WIDTH_720 = 600
SAMPLES = (
    "Skip",
    "Skip Intro",
    "Skip Commercial",
    "SKIP COMMERCIAL",
    "Skip Intro · 1m30s",
    "Skip Commercial · 1m30s",
    "iiiiiiiiii",
    "WWWWWWWWWW",
)
SETTLE_MS = 250


def _width(control):
    try:
        return int(control.getWidth())
    except Exception:
        return -1


def measure(window, samples=SAMPLES, sleep=xbmc.sleep, settle_ms=SETTLE_MS):
    """Return one dict per sample with the widths the three controls report."""
    from skip_dialog_appearance import estimate_skip_label_width_720

    rows = []
    for text in samples:
        for cid in (AUTO_LABEL_ID, AUTO_BUTTON_ID, FIXED_LABEL_ID):
            ctrl = window.getControl(cid)
            ctrl.setLabel(text)
        sleep(settle_ms)  # let the GUI thread run a render pass before reading
        rows.append(
            {
                "text": text,
                "estimate_720": estimate_skip_label_width_720(text),
                "auto_label": _width(window.getControl(AUTO_LABEL_ID)),
                "auto_button": _width(window.getControl(AUTO_BUTTON_ID)),
                "fixed_label": _width(window.getControl(FIXED_LABEL_ID)),
            }
        )
    return rows


def verdict(rows, fixed_expected):
    """Plain-language conclusion for the measured rows."""
    def tracks(key):
        vals = [r[key] for r in rows if r[key] >= 0]
        return len(set(vals)) > 2 and max(vals) > min(vals) * 1.5

    parts = []
    for key, name in (("auto_label", "auto label"), ("auto_button", "auto button")):
        parts.append(
            "%s: getWidth() follows the text" % name if tracks(key)
            else "%s: getWidth() does NOT follow the text (fixed or unsupported)" % name
        )
    fixed = {r["fixed_label"] for r in rows}
    parts.append(
        "fixed label: always %s (expected %d)"
        % (", ".join(str(v) for v in sorted(fixed)), fixed_expected)
    )
    return parts


def format_report(rows, parts, scale):
    lines = ["Skin scale vs 720p: %.2fx" % scale, ""]
    lines.append("%-28s %8s %8s %8s %8s" % ("text", "estim.", "label", "button", "fixed"))
    for r in rows:
        lines.append(
            "%-28s %8d %8d %8d %8d"
            % (r["text"][:28], round(r["estimate_720"] * scale), r["auto_label"],
               r["auto_button"], r["fixed_label"])
        )
    return "\n".join(lines + [""] + parts)


class LabelWidthProbe(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        init_window_xml_dialog(super(LabelWidthProbe, self), args)
        self.report = ""
        self.rows = []

    def onInit(self):
        try:
            scale = scale_skin_coord(1000) / 1000.0
            self.rows = measure(self)
            parts = verdict(self.rows, scale_skin_coord(FIXED_WIDTH_720))
            self.report = format_report(self.rows, parts, scale)
        except Exception as exc:  # diagnostic must never crash the add-on
            self.report = "Probe failed: %s" % exc
        self.close()


def run_label_width_probe():
    addon = get_addon()
    if not addon:
        return
    dlg = LabelWidthProbe("LabelWidthProbe.xml", addon.getAddonInfo("path"), "default")
    dlg.doModal()
    report = dlg.report
    del dlg
    log("Label width probe:\n%s" % report)
    try:
        from skippy_profile_store import profile_path, write_json

        write_json(profile_path("label_width_probe.json"), {"report": report})
    except Exception:
        pass
    xbmcgui.Dialog().textviewer("Skippy label width probe", report)


__all__ = ["run_label_width_probe", "measure", "verdict", "format_report", "json"]
