# -*- coding: utf-8 -*-
"""Source picker modal: review local vs online segment times and keep one source."""
from __future__ import annotations

import xbmc
import xbmcgui

from addon_skin_resolution import init_window_xml_dialog
from service_source_conflict import CHOICE_LOCAL, CHOICE_ONLINE, save_choice
from settings_utils import get_localized, log

ID_TITLE = 100
ID_LOCAL_NAME, ID_LOCAL_START, ID_LOCAL_END = 110, 111, 112
ID_ONLINE_NAME, ID_ONLINE_START, ID_ONLINE_END = 120, 121, 122
ID_USE_LOCAL, ID_USE_ONLINE, ID_CLOSE = 130, 131, 132
SEEK_TARGETS = {
    ID_LOCAL_START: ("local", "start"),
    ID_LOCAL_END: ("local", "end"),
    ID_ONLINE_START: ("online", "start"),
    ID_ONLINE_END: ("online", "end"),
}
_SOURCE_NAMES = {"theintrodb": "TheIntroDB", "introdb": "IntroDB.app"}


def format_time(seconds) -> str:
    total = max(0, int(round(float(seconds))))
    h, rest = divmod(total, 3600)
    m, s = divmod(rest, 60)
    return "%d:%02d:%02d" % (h, m, s) if h else "%d:%02d" % (m, s)


def online_names(sources) -> str:
    seen = []
    for src in sources:
        name = _SOURCE_NAMES.get(str(src).lower(), str(src) or "online")
        if name not in seen:
            seen.append(name)
    return " + ".join(seen)


class SourcePicker(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        init_window_xml_dialog(super(SourcePicker, self), args)
        self.conflict = kwargs.get("conflict")
        self.addon = kwargs.get("addon")
        self.choice = None
        self._paused_by_us = False

    def _s(self, sid, default, *args):
        return get_localized(self.addon, sid, default, *args)

    def onInit(self):
        c = self.conflict
        label = c.label.replace("_", " ").title() if c.label else c.bucket.title()
        self.getControl(ID_TITLE).setLabel(self._s(46047, "Sources disagree: %s", label))
        self.getControl(ID_LOCAL_NAME).setLabel(self._s(46048, "Local sidecar"))
        self.getControl(ID_ONLINE_NAME).setLabel(
            self._s(46049, "Online (%s)", online_names(c.online_sources))
        )
        for cid, (who, edge) in SEEK_TARGETS.items():
            seg = c.local if who == "local" else c.online
            secs = seg.start_seconds if edge == "start" else seg.end_seconds
            text = (
                self._s(46050, "Start %s", format_time(secs))
                if edge == "start"
                else self._s(46051, "End %s", format_time(secs))
            )
            self.getControl(cid).setLabel(text)
        self.getControl(ID_USE_LOCAL).setLabel(self._s(46052, "Use local"))
        self.getControl(ID_USE_ONLINE).setLabel(self._s(46053, "Use online"))
        self.getControl(ID_CLOSE).setLabel(self._s(46054, "Close"))
        try:
            player = xbmc.Player()
            if player.isPlayingVideo() and not xbmc.getCondVisibility("Player.Paused"):
                player.pause()
                self._paused_by_us = True
        except Exception:
            pass
        self.setFocusId(ID_LOCAL_START)

    def _seek(self, who, edge):
        seg = self.conflict.local if who == "local" else self.conflict.online
        secs = seg.start_seconds if edge == "start" else seg.end_seconds
        try:
            xbmc.Player().seekTime(float(secs))
        except Exception as exc:
            log("⚠ Source picker seek failed: %s" % exc)

    def onClick(self, controlId):
        if controlId in SEEK_TARGETS:
            self._seek(*SEEK_TARGETS[controlId])
        elif controlId == ID_USE_LOCAL:
            self.choice = CHOICE_LOCAL
            self.close()
        elif controlId == ID_USE_ONLINE:
            self.choice = CHOICE_ONLINE
            self.close()
        elif controlId == ID_CLOSE:
            self.close()

    def onAction(self, action):
        if action.getId() in (
            xbmcgui.ACTION_PREVIOUS_MENU,
            xbmcgui.ACTION_NAV_BACK,
            getattr(xbmcgui, "ACTION_BACKSPACE", 110),
        ):
            self.close()

    def resume_if_paused(self):
        if self._paused_by_us:
            try:
                if xbmc.getCondVisibility("Player.Paused"):
                    xbmc.Player().pause()
            except Exception:
                pass
            self._paused_by_us = False


def _invalidate_parse_cache(segment_monitor):
    if segment_monitor is None:
        return
    segment_monitor.segment_parse_cache = None
    try:
        from service_segment_processed_cache import clear_segment_processed_cache

        clear_segment_processed_cache(segment_monitor)
    except Exception:
        pass


def review_source_conflicts(addon, video_path, conflicts, segment_monitor):
    """Ask, then show one picker per disagreeing segment; persist and apply the picks."""
    from service_local_to_online_sync import _sync_yesno

    labels = ", ".join(sorted({c.bucket.title() for c in conflicts}))
    heading = get_localized(addon, 46045, "Segment sources disagree")
    body = get_localized(
        addon,
        46046,
        "%s: the local sidecar differs from the two online sources, which agree with each other.\n\nReview the sources now?",
        labels,
    )
    if not _sync_yesno(heading, body):
        return
    changed = False
    for conflict in conflicts:
        dlg = SourcePicker(
            "SourcePicker.xml", addon.getAddonInfo("path"), "default", conflict=conflict, addon=addon
        )
        dlg.doModal()
        choice = dlg.choice
        dlg.resume_if_paused()
        del dlg
        if choice and save_choice(video_path, conflict.bucket, choice):
            changed = True
    if changed:
        _invalidate_parse_cache(segment_monitor)
