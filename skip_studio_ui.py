# -*- coding: utf-8 -*-
"""The Studio: Customize Skip Dialog as three panels (settings in six tabs, live preview, about).

It is the classic Customize screen underneath: the draft, what each choice does, the preview and
Save are ``skip_dialog_customize_ui.SkipDialogCustomize``. This class lays the same choices out as
the round-3 mockup does: it catches the name and value the classic screen would write on a row
(``_set_row``), and draws them on its own row slots, grouped in tabs, each row with the control
that suits it (a switch group, a toggle, colour dots, a slider, the nine places, or a value to
step through). Under the preview it says what the row in focus does.
"""

from __future__ import annotations

import os
import re
import threading

import xbmcvfs

import skip_canvas as cv
import skip_dialog_customize_ui as base
import skip_dialog_presets as sp
import skip_layouts
import skip_studio as st
from skip_preset_wall import MANAGE, PARTS, preset_tile, show_preset_wall
from settings_utils import get_localized
from skip_dialog_appearance import (
    FULL_SKIP_PANEL_GROUP_ID,
    SKIP_DIALOG_SCREEN_MARGIN_720,
    card_top_on_screen,
)

MINIMAL_GROUP_ID = 5090
KICKER = "SKIPPY · CUSTOMIZE"

# The rows of each tab, as the row ids of the classic screen. A row shows only while it applies
# (the mode, the layout, what is switched on); a tab holds at most ``st.ROWS`` of them.
TAB_ROWS = (
    # Look
    (base.ID_PRESET, base.ID_LAYOUT, base.ID_MODE, base.ID_PREVIEW_TYPE, base.ID_LOOK, base.ID_CORNERS, base.ID_CV_BACKGROUND, base.ID_OVERLAY, base.ID_CV_GRADIENT,
     base.ID_CV_GRADIENT_TYPE, base.ID_CV_PROGRESS, base.ID_CV_BAR_EDGES, base.ID_CV_ACCENT, base.ID_BAR_COLOR, base.ID_CARD, base.ID_OPACITY,
     base.ID_PLATE),
    # Layout
    (base.ID_POSITION, base.ID_MIN_POSITION, base.ID_CV_DISTANCE, base.ID_CV_ZOOM, base.ID_CV_KICKER,
     base.ID_CV_NESTED, base.ID_OVERLAP),
    # Text
    (base.ID_SKIP_FORMAT, base.ID_CV_TIME, base.ID_DURATION_FORMAT, base.ID_DURATION_CONTENT, base.ID_HIDE_ENDING, base.ID_MIN_FORMAT,
     base.ID_ALL_CAPS, base.ID_FONT, base.ID_CV_TEXT_SIZE, base.ID_CV_OUTLINE, base.ID_CV_SHADOW),
    # Buttons
    (base.ID_FOCUS_STYLE, base.ID_CV_CLOSE, base.ID_HIDE_CLOSE, base.ID_CV_ICONS, base.ID_HIDE_ICONS, base.ID_FOCUS_FRAME,
     base.ID_COMBINED, base.ID_CV_FOCUS),
    # Motion
    (base.ID_APPEAR, base.ID_LEAVE, base.ID_PULSE),
    # Behaviour
    (base.ID_PROGRESS, base.ID_COUNTDOWN, base.ID_PROGRESS_STYLE, base.ID_HEIGHT),
)
# Rows that are a yes / no: drawn as a toggle.
TOGGLE_ROWS = frozenset((
    base.ID_ALL_CAPS, base.ID_HIDE_ENDING, base.ID_OVERLAP, base.ID_HIDE_CLOSE, base.ID_HIDE_ICONS,
    base.ID_FOCUS_FRAME, base.ID_COMBINED, base.ID_PROGRESS, base.ID_COUNTDOWN, base.ID_PULSE,
    base.ID_CV_CLOSE, base.ID_CV_ICONS, base.ID_CV_KICKER, base.ID_CV_NESTED, base.ID_CV_GRADIENT, base.ID_CV_TIME,
))
# Rows whose few choices stand side by side: row id -> (draft key, ((stored, string id, English), ...), default)
SEG_ROWS = {
    base.ID_CORNERS: ("skip_canvas_corners", (("Skin", 49149, "Skin"), ("Hard", 49075, "Hard"), ("Rounded", 49076, "Rounded")),
                      "Skin"),
    base.ID_CV_ZOOM: ("skip_canvas_zoom", base.ZOOM_NAMES, "100"),
    base.ID_CV_FOCUS: ("skip_canvas_focus", base.FOCUS_NAMES, "Skip"),
    base.ID_CV_OUTLINE: ("skip_canvas_outline", base.OUTLINE_NAMES, "Medium"),
    base.ID_CV_BACKGROUND: ("skip_canvas_background", base.BACKGROUND_NAMES, "None"),
    base.ID_CV_BAR_EDGES: ("skip_canvas_bar_edges", base.BAR_EDGE_NAMES, "Straight"),
}
# Why a row is dimmed: it belongs to the drawn designs, to the classic card, is not built yet, or
# does not go with the choices made (the size, a switch).
WHY = {
    "drawn": (49158, "For the drawn designs: choose a Design other than Card to use it."),
    "card": (49159, "For the classic Card only; the design in use does not have it."),
    "soon": (49160, "Not built for the drawn designs yet."),
    "other": (49163, "Not used with the choices made on this screen."),
}
DRAWN_ROWS = frozenset(base.CANVAS_ROW_IDS + (base.ID_LOOK, base.ID_BAR_COLOR, base.ID_OVERLAY, base.ID_APPEAR, base.ID_LEAVE,
                                              base.ID_PULSE))
# Progress: the four choices of the mockup. Line is the design's own way; Off hides it.
PROGRESS_STATES = (("Line", 49113, "Line"), ("Circle", 49114, "Circle"), ("Fill", 49115, "Fill"), ("Off", 49088, "Off"))
# Rows with a slider: row id -> (draft key, least, most)
SLIDER_ROWS = {
    base.ID_OPACITY: ("skip_card_opacity", 0, 100),
    base.ID_HEIGHT: ("progress_bar_height", 5, 32),
    base.ID_CV_DISTANCE: ("skip_canvas_distance", 0, base.DISTANCE_MAX),
}
# The preview plays: the dialog comes, counts down this many seconds (as fast as the clock), leaves, and
# after a short rest comes again.
PLAY_SECONDS, PLAY_REST_MS, PLAY_STEP_MS = 9, 900, 250
PLACE_STRING_FIRST = 49138  # the nine places, in the order of skip_canvas.PLACES
# The names the mockup gives a few rows (the classic screen has longer ones)
ROW_NAMES = {
    base.ID_LAYOUT: (49150, "Design"), base.ID_POSITION: (49151, "Position"), base.ID_MODE: (49152, "Size"),
    base.ID_MIN_POSITION: (49153, "Minimal position"), base.ID_CV_PROGRESS: (49154, "Progress"),
    base.ID_PREVIEW_TYPE: (49164, "Preview segment type"), base.ID_COUNTDOWN: (49168, "Progress countdown"),
}
# What "About this setting" says where the setting has no help of its own
ROW_ABOUT = {
    base.ID_POSITION: (49155, "The corner or edge the dialog sits in; the nine dots are the nine places of a drawn design. "
                              "The classic card knows the four corners."),
    base.ID_MIN_POSITION: (49156, "The corner the Minimal form sits in: it has a position of its own."),
    base.ID_PREVIEW_TYPE: (49167, "The segment type the live preview shows: step through all your types to see each in "
                                  "its own colour and wording. It is for the preview only and is not saved."),
}
# The setting behind a row: its help text is what "About this setting" says.
ROW_KEYS = {
    base.ID_MODE: "skip_dialog_mode", base.ID_LAYOUT: skip_layouts.KEY_LAYOUT, base.ID_LOOK: skip_layouts.KEY_LOOK,
    base.ID_BAR_COLOR: skip_layouts.KEY_BAR_COLOR, base.ID_OVERLAY: skip_layouts.KEY_OVERLAY,
    base.ID_APPEAR: skip_layouts.KEY_APPEAR, base.ID_LEAVE: skip_layouts.KEY_LEAVE, base.ID_PULSE: skip_layouts.KEY_PULSE,
    base.ID_CORNERS: "skip_canvas_corners", base.ID_CV_CLOSE: "skip_canvas_close", base.ID_CV_ICONS: "skip_canvas_icons",
    base.ID_CV_KICKER: "skip_canvas_kicker", base.ID_CV_NESTED: "skip_canvas_nested",
    base.ID_CV_SHADOW: "skip_canvas_text_shadow", base.ID_CV_TEXT_SIZE: "skip_canvas_text_size",
    base.ID_CV_ZOOM: "skip_canvas_zoom", base.ID_CV_ACCENT: "skip_canvas_accent", base.ID_CV_PROGRESS: "skip_canvas_progress",
    base.ID_CV_GRADIENT: "skip_canvas_overlay_gradient", base.ID_CV_GRADIENT_TYPE: "skip_canvas_gradient",
    base.ID_CV_OUTLINE: "skip_canvas_outline", base.ID_CV_DISTANCE: "skip_canvas_distance",
    base.ID_CV_FOCUS: "skip_canvas_focus", base.ID_CV_TIME: "skip_canvas_time",
    base.ID_CV_BACKGROUND: "skip_canvas_background", base.ID_CV_BAR_EDGES: "skip_canvas_bar_edges", base.ID_CARD: "skip_card_style", base.ID_OPACITY: "skip_card_opacity",
    base.ID_HIDE_ENDING: "hide_ending_text", base.ID_FONT: "skip_dialog_font_color",
    base.ID_OVERLAP: "skip_overlapping_segments", base.ID_ALL_CAPS: "skip_dialog_all_caps",
    base.ID_PROGRESS: "show_progress_bar", base.ID_COUNTDOWN: "progress_bar_countdown",
    base.ID_HEIGHT: "progress_bar_height", base.ID_PROGRESS_STYLE: "progress_bar_style",
    base.ID_POSITION: "skip_dialog_position", base.ID_FOCUS_STYLE: "button_focus_style",
    base.ID_SKIP_FORMAT: "skip_button_format", base.ID_HIDE_CLOSE: "hide_close_button",
    base.ID_FOCUS_FRAME: "show_skip_button_focus_texture", base.ID_HIDE_ICONS: "hide_skip_icon",
    base.ID_COMBINED: "compact_full_combined", base.ID_DURATION_FORMAT: "skip_duration_format",
    base.ID_DURATION_CONTENT: "skip_duration_content", base.ID_PLATE: "minimal_button_style",
    base.ID_MIN_FORMAT: "minimal_skip_button_format", base.ID_MIN_POSITION: "minimal_skip_dialog_position",
}
_HELP_IDS = {}


def help_ids(path=None) -> dict:
    """``{setting id: help string id}`` from ``resources/settings.xml`` (read once)."""
    if _HELP_IDS and path is None:
        return _HELP_IDS
    found = {}
    path = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "settings.xml")
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        for match in re.finditer(r"<setting\b[^>]*>", text):
            tag = match.group(0)
            sid, helped = re.search(r'\bid="([^"]+)"', tag), re.search(r'\bhelp="(\d+)"', tag)
            if sid and helped:
                found[sid.group(1)] = int(helped.group(1))
    except OSError:
        pass
    _HELP_IDS.update(found)
    return found


def tab_rows(draft) -> list:
    """For every tab, the classic row ids it shows for this draft."""
    shown = set(base.customize_nav_ids(draft)) | set(base.customize_picker_ids(draft))
    layout = base.draft_layout(draft)
    if layout is not None:
        # rows of the Studio only
        shown.update((base.ID_BAR_COLOR, base.ID_OVERLAY, base.ID_APPEAR, base.ID_LEAVE, base.ID_PULSE))
    if layout is not None and getattr(layout, "canvas", False):
        # a drawn design: its own rows, and the bar switch
        shown.update(base.CANVAS_ROW_IDS + (base.ID_PROGRESS,))
        shown.discard(base.ID_PROGRESS)  # Off is one of the four choices of Progress there
        if not draft.get("skip_canvas_overlay_gradient"):
            shown.discard(base.ID_CV_GRADIENT_TYPE)
        # the time on Skip has its own switch there; its format and content go with it, whatever the button says
        if draft.get("skip_canvas_time", True):
            shown.update((base.ID_DURATION_FORMAT, base.ID_DURATION_CONTENT))
        else:
            shown.difference_update((base.ID_DURATION_FORMAT, base.ID_DURATION_CONTENT))
    return [[cid for cid in ids if cid in shown] for ids in TAB_ROWS]


def tab_rows_all(draft) -> list:
    """For every tab, all its rows as ``(row id, why)``: ``why`` is empty for a row that applies, else
    the reason it is dimmed (a key of ``WHY``). Nothing is left out, so a tab looks the same whatever
    the design: only what can be changed differs."""
    used = tab_rows(draft)
    layout = base.draft_layout(draft)
    drawn = layout is not None and bool(getattr(layout, "canvas", False))
    out = []
    for ids, live in zip(TAB_ROWS, used):
        rows = []
        for cid in ids:
            if cid in live:
                why = ""
            elif cid in DRAWN_ROWS:
                why = "drawn" if layout is None else "other"
            elif cid == base.ID_PROGRESS and drawn:
                continue  # Off is one of the four choices of Progress there
            else:
                why = "card" if layout is not None else "other"
            rows.append((cid, why))
        out.append(rows)
    return out


def scroll_for(index, scroll, count, page) -> int:
    """The first row on screen so that row ``index`` of ``count`` is among the ``page`` shown."""
    if count <= page:
        return 0
    if index < scroll:
        scroll = index
    elif index >= scroll + page:
        scroll = index - page + 1
    return max(0, min(count - page, scroll))


def first_tab_with_rows(rows, wanted) -> int:
    """``wanted`` when that tab has rows, else the nearest tab that has."""
    if rows[wanted]:
        return wanted
    for index, ids in enumerate(rows):
        if ids:
            return index
    return 0


def next_tab(rows, current, delta) -> int:
    """The next tab with rows in a direction (wrapping); ``current`` when there is no other."""
    count = len(rows)
    for step in range(1, count + 1):
        index = (current + delta * step) % count
        if rows[index]:
            return index
    return current


def mode_choices(addon) -> list:
    """``[(stored, shown)]`` of the three sizes, for the switch row. A choice has room for one word,
    so "Compact Full" is shown by its first."""
    return [(m, (base._pair_label(base.MODE_LABELS, m) or m).split()[0]) for m in base.MODES]


def progress_state(draft) -> str:
    """Which of the four Progress choices a draft shows."""
    if not draft.get("show_progress_bar", True):
        return "Off"
    stored = skip_layouts.normalize_choice(draft.get("skip_canvas_progress"), cv.PROGRESS, "Auto")
    return stored if stored in ("Circle", "Fill") else "Line"


def set_progress_state(draft, state) -> None:
    draft["show_progress_bar"] = state != "Off"
    if state != "Off":
        draft["skip_canvas_progress"] = "Auto" if state == "Line" else state


def place_of(draft, minimal=False) -> str:
    """The place (one of nine) a draft puts the dialog at."""
    if minimal:
        return cv.place_name(draft.get("minimal_skip_dialog_position"))
    return cv.place_name(draft.get("skip_canvas_place") or draft.get("skip_dialog_position"))


def nearest_corner(place) -> str:
    """The corner the classic card would use for a place: a drawn design knows nine, the card four."""
    place = cv.place_name(place)
    return ("Top" if place.startswith("Top") else "Bottom") + ("Left" if "Left" in place else "Right")


def look_tile(code, resolution) -> dict:
    """A tile for a look of the new layouts."""
    found = skip_layouts.look(code)
    return {
        "plate": skip_layouts.texture(code, "plate"),
        "tint": "FFFFFFFF",
        "pill": skip_layouts.texture(code, "focus", resolution),
        "bar": "sl_white.png",
        "bartint": found.accent,
    }


class SkipStudio(base.SkipDialogCustomize):
    def __init__(self, *args, **kwargs):
        super(SkipStudio, self).__init__(*args, **kwargs)
        self._tab = 0
        self._cells = {}  # classic row id -> (name, value)
        self._rows = []  # classic row ids on screen, in slot order
        self._all = []  # every row of the open tab: (row id, why it is dimmed or "")
        self._scroll = 0
        self._tab_rows = [[] for _ in st.TABS]
        self._props = {}  # what is written on the window: a property is only set when it changes
        self._title = None  # (control, text) of the large title
        self._about_for = None

    # ----------------------------------------------------------------- set-up
    def onInit(self):
        from addon_skin_resolution import FULL_SKIP_PROBE_ID, reconcile_window_xml_skin_resolution

        import time

        marks = [("start", time.time())]
        asked = getattr(self, "_skin_resolution", None)
        locked = reconcile_window_xml_skin_resolution(self, asked, control_ids=(FULL_SKIP_PROBE_ID,))
        marks.append(("resolution", time.time()))
        if locked != asked:
            self._skin_resolution = locked
        addon = self.addon
        suffix = "720" if str(self._skin_resolution).startswith("720") else "1080"
        self._props, self._title, self._about_for = {}, None, None
        self._prop("st_well", "st_well_%s.png" % suffix)
        self._prop("st_chip", "st_chip_%s.png" % suffix)
        self._prop("st_kicker", KICKER)
        self._prop("st_hint", get_localized(
            addon, 49133,
            "[B]Up / Down[/B]  choose a row      [B]Left / Right[/B]  pick      [B]OK[/B]  next choice      [B]Back[/B]  close without saving"))
        self._prop("st_tag", get_localized(addon, 49027, "LIVE PREVIEW"))
        for index, (sid, text) in enumerate(zip(st.TAB_LABEL_IDS, st.TAB_LABELS)):
            name = get_localized(addon, sid, text)
            self._prop("st_tab%d" % index, name)
            self._set_button(st.tab_id(index), name)
        self._set_button(st.ID_SAVE, get_localized(addon, 44103, "Save"))
        self._set_button(st.ID_SAVE_PRESET, get_localized(addon, 49025, "Save as preset"))
        self._set_button(st.ID_RESET, get_localized(addon, 49026, "Reset"))
        marks.append(("labels", time.time()))
        self._load_fanart()
        marks.append(("fanart", time.time()))
        # a drawn design is not drawn standing still here: the thread started below plays it at once, and two
        # drawings one after the other showed as a blink
        self._opening = True
        self.refresh_mockup()
        self._opening = False
        marks.append(("rows and preview", time.time()))
        self._focus(st.row_id(0))
        self._update_about()
        marks.append(("focus", time.time()))
        try:
            import xbmc

            xbmc.log("[service.skippy] Skip Studio opened: %s" % ", ".join(
                "%s %d ms" % (what, (when - marks[index][1]) * 1000) for index, (what, when) in enumerate(marks[1:])), xbmc.LOGINFO)
        except Exception:
            pass
        self._playing = True
        threading.Thread(target=self._play_preview, name="skippy-studio-preview", daemon=True).start()

    # ------------------------------------------------------- the preview plays
    def _play_preview(self):
        """Show the drawn design the way it will be seen: it appears, its countdown and its bar run, it
        beats in its last seconds if Pulse is on, it leaves, and then it comes again."""
        import xbmc

        import skip_canvas_dialog as cvd

        monitor = xbmc.Monitor()

        def rest(ms) -> bool:
            return monitor.waitForAbort(ms / 1000.0) or not getattr(self, "_playing", False)

        while getattr(self, "_playing", False):
            canvas, show = getattr(self, "_mock_canvas", None), getattr(self, "_mock_show", None)
            if canvas is None or show is None or not self._is_canvas():
                if rest(500):
                    return
                continue
            options, texts, heading, kicker = show
            try:
                # hidden, drawn afresh with its motion, then shown: Appears plays
                for name in ("ready", "out", "pulse"):
                    self.setProperty("cv_mock_" + name, "")
                with self._mock_lock():
                    if getattr(self, "_mock_show", None) is not show:
                        continue  # a choice changed meanwhile: play the new one
                    canvas.draw(options, texts, animate=True)
                self.setProperty("cv_mock_ready", "true")
                steps = int(PLAY_SECONDS * 1000 / PLAY_STEP_MS)
                for step in range(steps + 1):
                    if rest(PLAY_STEP_MS):
                        return
                    if getattr(self, "_mock_show", None) is not show:
                        break  # the preview was drawn again for a new choice; it stands still until the next round
                    left = PLAY_SECONDS * (1.0 - step / float(steps))
                    with self._mock_lock():
                        canvas.set_percent(100.0 * step / steps)
                        cvd.tick(canvas, heading, kicker, "%d:%02d" % divmod(int(round(left)), 60), left)
                    self.setProperty("cv_mock_pulse", "true" if options.pulse and left <= cv.PULSE_SECONDS else "")
                else:
                    self.setProperty("cv_mock_pulse", "")
                    self.setProperty("cv_mock_out", "true")  # Leaves plays
                    if rest(canvas.leave_ms + PLAY_REST_MS):
                        return
                    continue
                if rest(1200):
                    return
            except Exception:
                if rest(1000):
                    return

    def _stop_preview(self):
        self._playing = False

    def _save_and_close(self):
        self._stop_preview()
        super(SkipStudio, self)._save_and_close()

    def _cancel_and_close(self):
        self._stop_preview()
        super(SkipStudio, self)._cancel_and_close()

    def _prop(self, name, value):
        value = "" if value is None else str(value)
        # a property that was never written is empty already: writing "" to it would only cost a call
        if self._props.get(name, "") != value:
            self._props[name] = value
            if self._batch is not None:
                self._batch[name] = value  # written with the rest of the drawing, side by side
            else:
                self.setProperty(name, value)

    _batch = None

    def _draw(self):
        """Draw the rows. Every call into Kodi waits for a frame on a slow box, and a screen of rows is a few
        hundred window properties: written one after the other, the Studio filled from top to bottom over
        several seconds. They are collected and written side by side."""
        import skip_canvas_draw as cvdraw

        import time

        started = time.time()
        self._batch = {}
        try:
            self._draw_rows()
        finally:
            batch, self._batch = self._batch, None
            built = time.time()
            cvdraw._side_by_side([(self.setProperty, pair) for pair in batch.items()])
            if len(batch) > 20:
                try:
                    import xbmc

                    xbmc.log("[service.skippy] Studio rows drawn: %d properties, built in %d ms, written in %d ms"
                             % (len(batch), (built - started) * 1000, (time.time() - built) * 1000), xbmc.LOGINFO)
                except Exception:
                    pass

    def _set_button(self, cid, text):
        ctrl = self._ctrl(cid)
        if ctrl:
            try:
                ctrl.setLabel(text)
            except Exception:
                pass

    def _load_fanart(self):
        ctrl = self._ctrl(st.ID_FANART)
        if not ctrl or not self.addon:
            return
        path = os.path.join(self.addon.getAddonInfo("path") or "", "fanart.png")
        if xbmcvfs.exists(path):
            try:
                ctrl.setImage(path)
            except Exception:
                pass

    def _focus(self, cid):
        try:
            self.setFocusId(cid)
        except Exception:
            pass

    def _is_canvas(self) -> bool:
        layout = base.draft_layout(self._draft)
        return layout is not None and bool(getattr(layout, "canvas", False))

    # -------------------------------------------- what the classic screen calls
    def _set_row(self, cid, name, value):
        self._cells[cid] = (str(name), str(value))

    def _layout_left_pane(self):
        return  # the rows are drawn once their names and values are known (_refresh_row_labels)

    def _refresh_row_labels(self):
        super(SkipStudio, self)._refresh_row_labels()
        self._draw()

    def refresh_mockup(self):
        # the preview of a drawn design always has a segment inside another, so that the Nested line
        # switch shows what it does; the classic card follows the overlap setting, as before
        self._preview_nested = True if self._is_canvas() else None
        super(SkipStudio, self).refresh_mockup()
        self._place_on_screen()
        kind = base.display_segment_label(getattr(self, "_preview_type", base.MOCK_SEGMENT_LABEL))
        self._prop("st_tag0", "·   %s" % kind)

    def _open_preset_menu(self):
        """OK on the Preset row: the preset wall. Its last tile opens the list that saves, deletes,
        exports and imports presets."""
        chosen = show_preset_wall(self.addon, self._draft)
        if chosen == MANAGE:
            base.present_preset_menu(self.addon, self._draft)
        elif chosen:
            for name, values, _builtin in sp.list_presets():
                if name == chosen:
                    sp.apply_preset(self._draft, values)
                    break
        self.refresh_mockup()

    # ------------------------------------------------------------ the preview
    def _mock_stage(self):
        """The small screen of the Studio's live preview: its corner and its zoom."""
        left, top = st.screen_origin()
        return self._sc(left), self._sc(top), st.SCREEN_ZOOM

    def _place_on_screen(self):
        """The classic screen puts the card and the chip in its own small stage; here they sit on
        the whole (small) screen, where the real dialog would be."""
        settings = base.DictSettingsReader(self._draft)
        sc = self._sc
        margin = SKIP_DIALOG_SCREEN_MARGIN_720
        for group_id, key, fallback_w, fallback_h, home_top in (
            (FULL_SKIP_PANEL_GROUP_ID, "skip_dialog_position", 430, 100, 620),
            (MINIMAL_GROUP_ID, "minimal_skip_dialog_position", 120, 46, 674),
        ):
            group = self._ctrl(group_id)
            if not group:
                continue
            corner = settings.get_text(key, "BottomRight")
            try:
                width = int(group.getWidth()) or sc(fallback_w)
                height = int(group.getHeight()) or sc(fallback_h)
            except Exception:
                width, height = sc(fallback_w), sc(fallback_h)
            if group_id == FULL_SKIP_PANEL_GROUP_ID:
                width = int(getattr(self, "_skip_panel_w", width))
            left = sc(margin) if "Left" in corner else sc(st.CANVAS_W - margin) - width
            top = 0 if "Top" in corner else card_top_on_screen(sc(home_top), height, sc(st.CANVAS_H), sc(margin))
            try:
                group.setPosition(int(left), int(top))
            except Exception:
                pass

    # ---------------------------------------------------------------- drawing
    def _draw_title(self, text):
        """The large title, at the mockup's size: a label of the skin's nearest font, zoomed the rest."""
        if self._title and self._title[1] == text:
            return
        import xbmcgui

        import skip_canvas_draw as cvdraw

        if self._title:
            try:
                self.removeControl(self._title[0])
            except Exception:
                pass
            self._title = None
        try:
            left, top = self._sc(st.PANEL[0] + st.PAD), self._sc(st.TITLE_TOP)
            width, height = self._sc(st.PANEL[2] - 2 * st.PAD), self._sc(st.TITLE_H)
            font, percent, wrap = cvdraw.pick_font(cvdraw.read_fonts(), self._sc(st.TITLE_SIZE), True)
            zoom = percent / 100.0
            shown = "[B]%s[/B]" % text if wrap else text
            control = xbmcgui.ControlLabel(left, int(round(top + height / 2.0 - height / zoom / 2.0)), int(width / zoom),
                                           int(height / zoom), shown, font=font, textColor="FFFFFFFF", alignment=0x4)
            self.addControl(control)
            if abs(zoom - 1.0) > 1e-3:
                control.setAnimations([("conditional", "effect=zoom start=%.3f end=%.3f center=%d,%d time=0 condition=true"
                                        % (percent, percent, left, int(top + height / 2.0)))])
            self._title = (control, text)
        except Exception:
            self._title = None

    def _row_view(self, cid) -> dict:
        """How a row is drawn: its kind and what its control shows."""
        addon, draft = self.addon, self._draft
        name, value = self._cells.get(cid, ("", ""))
        if cid in ROW_NAMES:
            name = get_localized(addon, *ROW_NAMES[cid])
        view = {"name": name, "kind": "pick", "value": value, "seg": [], "on": -1, "toggle": "", "dots": [], "dot": -1,
                "share": None, "place": ""}
        if cid == base.ID_MODE:
            pairs = mode_choices(addon)
            stored = sp.mode_name(draft.get("skip_dialog_mode"))
            view.update(kind="seg", seg=[shown for _stored, shown in pairs],
                        on=[s for s, _n in pairs].index(stored) if stored in [s for s, _n in pairs] else -1)
        elif cid in SEG_ROWS:
            key, names, default = SEG_ROWS[cid]
            values = [row[0] for row in names]
            stored = skip_layouts.normalize_choice(draft.get(key), values, default)
            view.update(kind="seg", seg=[get_localized(addon, sid, english) for _v, sid, english in names],
                        on=values.index(stored))
        elif cid == base.ID_CV_PROGRESS:
            states = [row[0] for row in PROGRESS_STATES]
            view.update(kind="seg", seg=[get_localized(addon, sid, english) for _v, sid, english in PROGRESS_STATES],
                        on=states.index(progress_state(draft)))
        elif cid in TOGGLE_ROWS:
            view.update(kind="toggle", toggle="on" if value == base._yes_no(addon, True) else "off")
        elif cid == base.ID_CV_ACCENT:
            import skip_canvas_dialog as cvd

            names = [row[0] for row in cvd.ACCENTS]
            stored = skip_layouts.normalize_choice(draft.get("skip_canvas_accent"), names, "Auto")
            view.update(kind="swatch", dot=names.index(stored),
                        dots=[("st_dot.png", argb) if argb else ("st_dot_auto.png", "FFFFFFFF") for _n, argb in cvd.ACCENTS])
        elif cid in SLIDER_ROWS:
            key, least, most = SLIDER_ROWS[cid]
            try:
                number = float(draft.get(key))
            except (TypeError, ValueError):
                number = float(least)
            view.update(kind="slider", share=(number - least) / float(most - least))
            if cid == base.ID_OPACITY and "%" not in value:
                view["value"] = "%s %%" % value
        elif cid in (base.ID_POSITION, base.ID_MIN_POSITION):
            minimal = cid == base.ID_MIN_POSITION
            place = place_of(draft, minimal) if (minimal or self._is_canvas()) else nearest_corner(place_of(draft))
            index = cv.PLACES.index(place)
            view.update(kind="pos", place=str(index), value=get_localized(addon, PLACE_STRING_FIRST + index, place))
        else:
            view["value"] = "‹  %s  ›" % value
        return view

    def _draw_rows(self):
        addon, draft = self.addon, self._draft
        everything = tab_rows_all(draft)
        self._tab_rows = [[cid for cid, _why in rows] for rows in everything]
        self._tab = first_tab_with_rows(self._tab_rows, self._tab)
        self._all = everything[self._tab]
        self._scroll = scroll_for(self._scroll, self._scroll, len(self._all), st.ROWS)
        self._rows = [cid for cid, _why in self._all[self._scroll: self._scroll + st.ROWS]]
        why = dict(self._all)
        self._prop("st_more", "%d – %d / %d" % (self._scroll + 1, self._scroll + len(self._rows), len(self._all))
                   if len(self._all) > st.ROWS else "")
        self._prop("st_tab", str(self._tab))
        self._draw_title("%s %s" % (get_localized(addon, 49147, "Skip dialog"), self._props.get("st_tab%d" % self._tab, "").lower()))
        for index in range(len(st.TABS)):
            tab = self._ctrl(st.tab_id(index))
            if tab:
                try:
                    tab.setEnabled(bool(self._tab_rows[index]))
                except Exception:
                    pass
        for slot in range(st.ROWS):
            ctrl = self._ctrl(st.row_id(slot))
            cid = self._rows[slot] if slot < len(self._rows) else None
            view = self._row_view(cid) if cid else {"name": "", "kind": "", "value": "", "seg": [], "on": -1, "toggle": "",
                                                    "dots": [], "dot": -1, "share": None, "place": ""}
            prefix = "st_r%d_" % slot
            dimmed = bool(cid and why.get(cid))
            if dimmed:
                # a row that does not apply: its name only
                view = dict(view, kind="", value="", seg=[], on=-1, toggle="", dots=[], dot=-1, share=None, place="")
            self._prop(prefix + "dim", "true" if dimmed else "")
            self._prop(prefix + "name", view["name"])
            self._prop(prefix + "kind", view["kind"] if view["kind"] in ("pick", "slider", "pos") else "")
            self._prop(prefix + "val", view["value"] if view["kind"] in ("pick", "slider", "pos") else "")
            choices = view["seg"]
            offset = st.SEG_OPTIONS - len(choices)
            for option in range(st.SEG_OPTIONS):
                self._prop(prefix + "s%d" % option, choices[option - offset] if choices and option >= offset else "")
            self._prop(prefix + "n", str(len(choices)) if choices else "")
            self._prop(prefix + "on", str(view["on"] + offset) if choices and view["on"] >= 0 else "")
            self._prop(prefix + "tog", view["toggle"])
            dots = view["dots"]
            shift = st.SWATCHES - len(dots)
            for index in range(st.SWATCHES):
                texture, colour = dots[index - shift] if dots and index >= shift else ("", "")
                self._prop(prefix + "t%d" % index, texture)
                self._prop(prefix + "c%d" % index, colour)
            self._prop(prefix + "con", str(view["dot"] + shift) if dots and view["dot"] >= 0 else "")
            self._prop(prefix + "pos", view["place"])
            if view["share"] is not None:
                self._place_slider(slot, view["share"])
            if ctrl:
                try:
                    ctrl.setVisible(cid is not None)
                except Exception:
                    pass
        self._draw_strip()
        self._about_for = None
        self._update_about()

    def _place_slider(self, slot, share):
        track = st.slider_box(slot)
        fill, knob = self._ctrl(st.ID_SLIDER_FILL + slot), self._ctrl(st.ID_SLIDER_KNOB + slot)
        share = max(0.0, min(1.0, float(share)))
        try:
            if fill:
                fill.setWidth(max(1, self._sc(int(round(track[2] * share)))))
            if knob:
                knob.setPosition(self._sc(st.knob_left(slot, share)), self._sc(track[1] + track[3] // 2 - st.KNOB // 2))
        except Exception:
            pass

    def _draw_strip(self):
        """The presets around the one in use: card presets from their parts, layout presets as miniatures."""
        addon, draft = self.addon, self._draft
        presets = sp.list_presets()
        found = sp.detect_preset(draft)
        names = [n for n, _v, _b in presets]
        items = [(sp.display_name(n) if b else n, preset_tile(v)) for n, v, b in presets]
        if found in names:
            current = names.index(found)
        else:
            # a look of your own: it stands in the middle, the first presets beside it
            items = [(get_localized(addon, 46016, "Custom"), preset_tile(sp.snapshot(draft)))] + items
            current = 0
        for index, item in enumerate(st.window_of(items, current)):
            name, tile = item if item else ("", {})
            self._prop("st_t%d_name" % index, name)
            for part in PARTS:
                self._prop("st_t%d_%s" % (index, part), (tile or {}).get(part, ""))

    def about_text(self, cid) -> str:
        """What "About this setting" says for a row of the classic screen."""
        addon = self.addon
        name = self._cells.get(cid, ("", ""))[0]
        if cid in ROW_NAMES:
            name = get_localized(addon, *ROW_NAMES[cid])
        why = dict(self._all).get(cid, "")
        if why:
            body = get_localized(addon, *WHY[why])
        elif cid in ROW_ABOUT:
            body = get_localized(addon, *ROW_ABOUT[cid])
        elif cid == base.ID_PRESET:
            body = get_localized(addon, 49148, "A preset sets the design, its look and its colours in one step. Left and Right step "
                                               "through the presets; OK opens the wall with all of them, yours included.")
        else:
            sid = help_ids().get(ROW_KEYS.get(cid, ""))
            body = get_localized(addon, sid, "") if sid else ""
            if body.strip().lower() == self._cells.get(cid, ("", ""))[0].strip().lower():
                body = ""  # a help text that only repeats the name says nothing
        return ("[B]%s[/B]   %s" % (name, body)).strip() if name else body

    def _update_about(self):
        """The panel under the preview follows the focus: the presets on the Preset row, else the help of the row."""
        slot = self._row_slot(self._focus_id())
        cid = self._rows[slot] if slot is not None else None
        if cid == self._about_for and self._about_for is not None:
            return
        self._about_for = cid
        presets = cid == base.ID_PRESET
        self._prop("st_mode", "presets" if presets else "about")
        self._prop("st_strip", get_localized(self.addon, 49028, "PRESETS") if presets
                   else get_localized(self.addon, 49128, "ABOUT THIS SETTING"))
        self._prop("st_about", "" if presets or cid is None else self.about_text(cid))

    # ------------------------------------------------------------- navigation
    def _row_slot(self, cid):
        try:
            index = int(cid) - st.ID_ROW_FIRST
        except (TypeError, ValueError):
            return None
        return index if 0 <= index < len(self._rows) else None

    def _show_row(self, index):
        """Bring row ``index`` of the open tab on screen (scrolling when it is not) and give it the focus."""
        scroll = scroll_for(index, self._scroll, len(self._all), st.ROWS)
        if scroll != self._scroll:
            self._scroll = scroll
            self._draw()
        self._focus(st.row_id(index - self._scroll))

    def _move(self, delta):
        """Up / Down: the open tab, its rows (a long tab scrolls), then the three buttons."""
        cid = self._focus_id()
        count = len(self._all)
        slot = self._row_slot(cid)
        if slot is not None:
            index = self._scroll + slot + delta
            if index < 0:
                self._focus(st.tab_id(self._tab))
            elif index >= count:
                self._focus(st.ID_SAVE)
            else:
                self._show_row(index)
        elif cid in (st.ID_SAVE, st.ID_SAVE_PRESET, st.ID_RESET):
            if delta < 0 and count:
                self._show_row(count - 1)
            else:
                self._focus(st.tab_id(self._tab))
        else:  # a tab
            if delta > 0 and count:
                self._show_row(0)
            else:
                self._focus(st.ID_SAVE)
        self._update_about()

    def _side(self, delta):
        """Left / Right: another tab, another choice of the row, or another of the three buttons."""
        cid = self._focus_id()
        foot = (st.ID_SAVE, st.ID_SAVE_PRESET, st.ID_RESET)
        if cid in foot:
            self._focus(foot[(foot.index(cid) + delta) % len(foot)])
            return
        if st.ID_TAB_FIRST <= cid < st.ID_TAB_FIRST + len(st.TABS):
            self._open_tab(next_tab(self._tab_rows, self._tab, delta))
            return
        slot = self._row_slot(cid)
        if slot is not None:
            self._change(self._rows[slot], delta)

    def _change(self, row, delta):
        """Step a row's choice. A choice can add or remove rows (a layout hides the card's rows), so the
        focus goes back to the row that was changed, wherever it now is."""
        draft = self._draft
        if dict(self._all).get(row):
            return  # dimmed: it does not apply to the design in use
        if row == base.ID_CV_PROGRESS:
            states = [state for state, _sid, _name in PROGRESS_STATES]
            set_progress_state(draft, states[(states.index(progress_state(draft)) + delta) % len(states)])
            self.refresh_mockup()
        elif row == base.ID_POSITION and self._is_canvas():
            place = cv.PLACES[(cv.PLACES.index(place_of(draft)) + delta) % len(cv.PLACES)]
            draft["skip_canvas_place"] = place
            draft["skip_dialog_position"] = nearest_corner(place)
            self.refresh_mockup()
        else:
            self._nudge(row, delta)
            if row == base.ID_POSITION:
                draft["skip_canvas_place"] = ""  # the card knows the four corners only
        everything = [cid for cid, _why in self._all]
        if row in everything:
            self._show_row(everything.index(row))
        elif self._rows:
            self._show_row(0)
        self._update_about()

    def _open_tab(self, index):
        self._tab = index
        self._scroll = 0
        self._draw()
        self._focus(st.tab_id(self._tab))
        self._update_about()

    def onFocus(self, controlId):
        self._update_about()

    def onClick(self, controlId):
        try:
            cid = int(controlId)
        except (TypeError, ValueError):
            return
        if cid == st.ID_SAVE:
            self._save_and_close()
        elif cid == st.ID_SAVE_PRESET:
            base.prompt_save_preset(self.addon, self._draft)
            self.refresh_mockup()
        elif cid == st.ID_RESET:
            self._draft = dict(self._original)
            self.refresh_mockup()
        elif st.ID_TAB_FIRST <= cid < st.ID_TAB_FIRST + len(st.TABS):
            if self._tab_rows[cid - st.ID_TAB_FIRST]:
                self._open_tab(cid - st.ID_TAB_FIRST)
        else:
            slot = self._row_slot(cid)
            if slot is None:
                return
            if self._rows[slot] == base.ID_PRESET:
                self._open_preset_menu()
                self._show_row(0)
            else:
                self._change(self._rows[slot], 1)

    def onAction(self, action):
        aid = action.getId()
        if aid in base._CANCEL_ACTIONS:
            self._cancel_and_close()
        elif aid == base._MOVE_DOWN:
            self._move(1)
        elif aid == base._MOVE_UP:
            self._move(-1)
        elif aid in (base._MOVE_LEFT, base._MOVE_RIGHT):
            self._side(1 if aid == base._MOVE_RIGHT else -1)


def show_skip_studio(draft=None, original=None) -> bool:
    """Open the Studio. ``draft`` previews unsaved values (a preset); ``original`` is what is stored."""
    addon = base.with_pending(base.get_addon())
    if not addon:
        return False
    kwargs = {"addon": addon}
    if draft is not None:
        kwargs["draft"] = draft
        kwargs["original"] = original or base.load_skip_dialog_draft(addon)
    dialog = SkipStudio(st.XML, addon.getAddonInfo("path"), "default", **kwargs)
    dialog.doModal()
    saved = bool(getattr(dialog, "_saved", False))
    del dialog
    return saved
