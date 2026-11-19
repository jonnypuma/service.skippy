# -*- coding: utf-8 -*-
"""The Studio of the Up Next popup: three panels, as the round-3 mockup (board CN3) draws them.

Settings in six tabs at the left (Look, Layout, Picture, Buttons, Motion, Autoplay), the live
preview at the top right, and under it what the row in focus does (the presets while the Preset row
has the focus). The window file is the skip dialog Studio's (``SkipStudio.xml``): the same row
slots, switches, toggles, sliders and colour dots, filled from ``next_studio``.

The preview is the popup itself, drawn small by the engine of the drawn dialogs and played: it
comes, counts down, beats in its last seconds when Pulse is on, leaves, and comes again.
"""

from __future__ import annotations

import os
import threading

import xbmc
import xbmcgui
import xbmcvfs

import next_canvas as nc
import next_episode_appearance as app
import next_layouts as nl
import next_studio as ns
import skip_canvas as cv
import skip_layouts as sl
import skip_studio as st
import skippy_modal_style
from addon_skin_resolution import init_window_xml_dialog, reconcile_window_xml_skin_resolution, scale_skin_coord
from settings_utils import addon_get_bool, addon_get_setting_text, get_addon, get_localized, log

KICKER = "SKIPPY · CUSTOMIZE"
CANCEL_ACTIONS = (10, 92, 216)
MOVE_LEFT, MOVE_RIGHT, MOVE_UP, MOVE_DOWN = 1, 2, 3, 4
PLAY_SECONDS, PLAY_REST_MS, PLAY_STEP_MS = 9, 900, 250
PLACE_STRING_FIRST = 49138  # the nine places, in the order of skip_canvas.PLACES
ACCENT_ARGB = {"Auto": "", "Gold": "FFE8B04B", "Blue": "FF7FB4FF", "Red": "FFFF5C6C", "Green": "FF5CD68A",
               "Teal": "FF3CC8C0", "Purple": "FFB48CFF", "White": "FFFFFFFF"}
CLASSIC_GROUPS = (3080, 5090)  # the skip dialog's card and chip in the borrowed stage: never shown here
PLOT = ("The organizers bet on which contestant will reach the next checkpoint first. Shujiro shares his past with "
        "Futaba, then reunites with his estranged sister.")
TILE_PARTS = ("plate", "tint", "pill", "bar", "bartint", "thumb")


def scroll_for(index, scroll, count, page) -> int:
    if count <= page:
        return 0
    if index < scroll:
        scroll = index
    elif index >= scroll + page:
        scroll = index - page + 1
    return max(0, min(count - page, scroll))


class NextStudio(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        skippy_modal_style.apply(self, style="fg_dark")  # the Studio is always Fused Glass Dark
        self._skin_resolution = init_window_xml_dialog(super(NextStudio, self), args)
        self.addon = kwargs.get("addon") or get_addon()
        self._original = kwargs.get("original") or self.load()
        self._draft = dict(kwargs.get("draft") or self._original)
        self._saved = False
        self._tab, self._scroll = 0, 0
        self._all, self._rows = [], []
        self._props = {}
        self._title = None
        self._about_for = None
        self._canvas = None
        self._show = None  # (options, texts) the preview is showing
        self._guard = threading.RLock()
        self._playing = False

    def load(self) -> dict:
        addon = self.addon
        return ns.load(lambda key, default: addon_get_setting_text(addon, key, default),
                       lambda key, default: addon_get_bool(addon, key, default))

    # ----------------------------------------------------------------- helpers
    def _sc(self, value):
        return int(scale_skin_coord(value, self._skin_resolution))

    def _ctrl(self, cid):
        try:
            return self.getControl(cid)
        except Exception:
            return None

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

    def _loc(self, pair) -> str:
        return get_localized(self.addon, pair[0], pair[1])

    def _focus(self, cid):
        try:
            self.setFocusId(cid)
        except Exception:
            pass

    def _focus_id(self) -> int:
        try:
            return int(self.getFocusId())
        except Exception:
            return 0

    def _set_button(self, cid, text):
        ctrl = self._ctrl(cid)
        if ctrl:
            try:
                ctrl.setLabel(text)
            except Exception:
                pass

    # ------------------------------------------------------------------ set-up
    def onInit(self):
        from addon_skin_resolution import FULL_SKIP_PROBE_ID

        asked = getattr(self, "_skin_resolution", None)
        locked = reconcile_window_xml_skin_resolution(self, asked, control_ids=(FULL_SKIP_PROBE_ID,))
        if locked != asked:
            self._skin_resolution = locked
        suffix = "720" if str(self._skin_resolution).startswith("720") else "1080"
        addon = self.addon
        self._props, self._title, self._about_for, self._canvas = {}, None, None, None
        self._prop("st_well", "st_well_%s.png" % suffix)
        self._prop("st_chip", "st_chip_%s.png" % suffix)
        self._prop("st_kicker", KICKER)
        self._prop("st_hint", get_localized(
            addon, 49133,
            "[B]Up / Down[/B]  choose a row      [B]Left / Right[/B]  pick      [B]OK[/B]  next choice      [B]Back[/B]  close without saving"))
        self._prop("st_tag", get_localized(addon, 49027, "LIVE PREVIEW"))
        for index, pair in enumerate(ns.TAB_LABELS):
            name = self._loc(pair)
            self._prop("st_tab%d" % index, name)
            self._set_button(st.tab_id(index), name)
        self._set_button(st.ID_SAVE, get_localized(addon, 44103, "Save"))
        self._set_button(st.ID_SAVE_PRESET, get_localized(addon, 49025, "Save as preset"))
        self._set_button(st.ID_RESET, get_localized(addon, 49026, "Reset"))
        for cid in CLASSIC_GROUPS:
            ctrl = self._ctrl(cid)
            if ctrl:
                try:
                    ctrl.setVisible(False)
                except Exception:
                    pass
        self._load_fanart()
        self._draw()
        # the preview is not drawn standing still here: the thread started below plays it at once, and two
        # drawings one after the other showed as a blink (card, card without its texts, gone, card again)
        self._opening = True
        self._refresh_preview()
        self._opening = False
        self._focus(st.row_id(0))
        self._update_about()
        self._playing = True
        threading.Thread(target=self._play_preview, name="skippy-next-studio-preview", daemon=True).start()

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

    # ------------------------------------------------------------ the preview
    def _stage(self):
        left, top = st.screen_origin()
        return self._sc(left), self._sc(top), st.SCREEN_ZOOM

    def _mock_episode(self) -> dict:
        from next_episode_dialog import mock_episode

        episode = dict(mock_episode(self.addon))
        episode.update({"season": 1, "episode": 3, "runtime": 2940, "plot": PLOT, "showtitle": "Skippy"})
        return episode

    def _refresh_preview(self):
        """Draw the popup of the draft on the small screen (a drawn design), or say why there is none."""
        import next_canvas_dialog as ncd
        import skip_canvas_draw as cvdraw

        addon, draft = self.addon, self._draft
        layout = nl.normalize_layout(draft.get(app.KEY_LAYOUT))
        self._prop("st_tag0", "·   %s" % app.preset_name(*(app.preset_of(draft) or (layout, None))))
        design = nc.design_for(layout) if nl.is_drawn(layout) and not app.is_native_style(draft) else None
        if design is None:
            self._show = None
            if self._canvas is not None:
                with self._guard:
                    self._canvas.clear()
            self.setProperty("cv_mock_ready", "")
            return
        try:
            episode = self._mock_episode()
            # the preview shows what Keep clear of subtitles does, with or without subtitles on screen
            options = ncd.options_for(addon, dict(draft, _preview=True), design)
            texts = ncd.texts_for(addon, episode, "0:20", 20, 55.0, queue=[episode] * 3 if design == "NQueue" else None)
            if not ns.yes(draft.get(nc.PREFIX + "logo")):
                texts.logo = ""
            if self._canvas is None:
                folder = "720" if str(self._skin_resolution).startswith("720") else "1080"
                media = os.path.join(addon.getAddonInfo("path") or "", "resources", "skins", "default", "media")
                self._canvas = cvdraw.Canvas(self, folder, media, offset=cv.MOCK_OFFSET, stage=self._stage(), prefix="cv_mock")
            self._show = (options, texts)
            if getattr(self, "_opening", False):
                return
            with self._guard:
                self._canvas.draw(options, texts, animate=False, build=nc.draw)
            self.setProperty("cv_mock_ready", "true")
        except Exception as exc:
            log("Up Next Studio: the preview could not be drawn: %s" % exc)

    def _play_preview(self):
        import next_canvas_dialog as ncd

        monitor = xbmc.Monitor()

        def rest(ms) -> bool:
            return monitor.waitForAbort(ms / 1000.0) or not self._playing

        while self._playing:
            canvas, show = self._canvas, self._show
            if canvas is None or show is None:
                if rest(500):
                    return
                continue
            options, texts = show
            try:
                for name in ("ready", "out", "pulse"):
                    self.setProperty("cv_mock_" + name, "")
                with self._guard:
                    if self._show is not show:
                        continue
                    canvas.draw(options, texts, animate=True, build=nc.draw)
                self.setProperty("cv_mock_ready", "true")
                steps = int(PLAY_SECONDS * 1000 / PLAY_STEP_MS)
                for step in range(steps + 1):
                    if rest(PLAY_STEP_MS):
                        return
                    if self._show is not show:
                        break  # drawn again for a new choice: it stands still until the next round
                    left = PLAY_SECONDS * (1.0 - step / float(steps))
                    with self._guard:
                        canvas.set_percent(100.0 * (1.0 - step / float(steps)))
                        ncd.tick(canvas, ncd.clock(left), str(max(0, int(round(left)))))
                    self.setProperty("cv_mock_pulse", "true" if options.pulse and left <= cv.PULSE_SECONDS else "")
                else:
                    self.setProperty("cv_mock_pulse", "")
                    self.setProperty("cv_mock_out", "true")
                    if rest(canvas.leave_ms + PLAY_REST_MS):
                        return
                    continue
                if rest(1200):
                    return
            except Exception:
                if rest(1000):
                    return

    # ---------------------------------------------------------------- drawing
    def _draw_title(self, text):
        if self._title and self._title[1] == text:
            return
        import skip_canvas_draw as cvdraw

        if self._title:
            try:
                self.removeControl(self._title[0])
            except Exception:
                pass
            self._title = None
        left, top = self._sc(st.PANEL[0] + st.PAD), self._sc(st.TITLE_TOP)
        width, height = self._sc(st.PANEL[2] - 2 * st.PAD), self._sc(st.TITLE_H)
        control = cvdraw.big_label(self, left, top, width, height, text, self._sc(st.TITLE_SIZE))
        self._title = (control, text) if control is not None else None

    def _value_text(self, item) -> str:
        """The written value of a row that is stepped through."""
        addon, draft = self.addon, self._draft
        key = item.key
        if item.kind == "preset":
            found = app.preset_of(draft)
            return app.preset_name(*found) if found else dict(nl.LAYOUT_NAMES)[nl.normalize_layout(draft.get(app.KEY_LAYOUT))]
        if key == app.KEY_LAYOUT:
            return dict(nl.LAYOUT_NAMES)[nl.normalize_layout(draft.get(key))]
        if key == app.KEY_LAYOUT_LOOK:
            return dict(sl.LOOK_NAMES)[sl.normalize_look(draft.get(key))]
        if item.kind == "slider":
            number = ns.number(draft, item)
            if key.endswith("speed"):
                return "%d ms" % number if number else get_localized(addon, 49224, "Auto")
            return "%d px" % number if key.endswith("distance") else ("%d s" % number if "lead" in key else str(number))
        if item.kind == "action":
            return "›"
        for stored, sid, english in item.choices:
            if str(draft.get(key)) == stored:
                return get_localized(addon, sid, english)
        return str(draft.get(key) or "")

    def _view(self, item) -> dict:
        addon, draft = self.addon, self._draft
        view = {"name": self._loc(item.name), "kind": "pick", "value": "", "seg": [], "on": -1, "toggle": "", "dots": [],
                "dot": -1, "share": None, "place": ""}
        if item.kind == "seg":
            view.update(kind="seg", seg=[get_localized(addon, sid, english) if sid else english for _v, sid, english in item.choices],
                        on=ns.choice_index(draft, item))
        elif item.kind == "toggle":
            view.update(kind="toggle", toggle="on" if ns.yes(draft.get(item.key)) else "off")
        elif item.kind == "swatch":
            current = draft.get(item.key) if draft.get(item.key) in ns.ACCENTS else "Auto"
            view.update(kind="swatch", dot=ns.ACCENTS.index(current),
                        dots=[("st_dot.png", ACCENT_ARGB[name]) if ACCENT_ARGB[name] else ("st_dot_auto.png", "FFFFFFFF")
                              for name in ns.ACCENTS])
        elif item.kind == "slider":
            number = ns.number(draft, item)
            view.update(kind="slider", share=(number - item.low) / float(max(1, item.high - item.low)),
                        value=self._value_text(item))
        elif item.kind == "pos":
            index = cv.PLACES.index(ns.place_of(draft))
            view.update(kind="pos", place=str(index), value=get_localized(addon, PLACE_STRING_FIRST + index, cv.PLACES[index]))
        elif item.kind == "action":
            view["value"] = "›"
        else:
            view["value"] = "‹  %s  ›" % self._value_text(item)
        return view

    def _draw_rows(self):
        draft = self._draft
        everything = ns.tab_rows(draft)
        self._all = everything[self._tab]
        self._scroll = scroll_for(self._scroll, self._scroll, len(self._all), st.ROWS)
        shown = self._all[self._scroll: self._scroll + st.ROWS]
        self._rows = [item for item, _why in shown]
        self._prop("st_more", "%d – %d / %d" % (self._scroll + 1, self._scroll + len(shown), len(self._all))
                   if len(self._all) > st.ROWS else "")
        self._prop("st_tab", str(self._tab))
        self._draw_title("%s %s" % (get_localized(self.addon, 49192, "Up next"), self._props.get("st_tab%d" % self._tab, "").lower()))
        empty = {"name": "", "kind": "", "value": "", "seg": [], "on": -1, "toggle": "", "dots": [], "dot": -1, "share": None,
                 "place": ""}
        for slot in range(st.ROWS):
            ctrl = self._ctrl(st.row_id(slot))
            item, why = shown[slot] if slot < len(shown) else (None, "")
            view = self._view(item) if item else dict(empty)
            dimmed = bool(item and why)
            if dimmed:
                view = dict(empty, name=view["name"])  # a row that does not apply: its name only
            prefix = "st_r%d_" % slot
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
                    ctrl.setVisible(item is not None)
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

    # ---------------------------------------------------------------- presets
    def _presets(self) -> list:
        """``(name, kind, value)`` of every preset: the drawn designs in every look, the looks saved under a
        name, and the popup of earlier versions last."""
        import next_episode_saved_looks as saved

        built = app.presets()
        out = [(app.preset_name(*item), "built", item) for item in built[:-1]]
        out += [(name, "saved", values) for name, values in saved.list_user_looks()]
        out.append((app.preset_name(*built[-1]), "built", built[-1]))
        return out

    def _current_preset(self, presets) -> int:
        import next_episode_saved_looks as saved

        name = saved.detect_saved_look(self._draft)
        for index, (label, kind, _value) in enumerate(presets):
            if kind == "saved" and label == name:
                return index
        found = app.preset_of(self._draft)
        for index, (_label, kind, value) in enumerate(presets):
            if kind == "built" and value == found:
                return index
        return -1

    def _step_preset(self, delta):
        import next_episode_saved_looks as saved

        presets = self._presets()
        current = self._current_preset(presets)
        index = (current + delta) % len(presets) if current >= 0 else (0 if delta > 0 else len(presets) - 1)
        _name, kind, value = presets[index]
        if kind == "saved":
            saved.apply_look(self._draft, value)
        else:
            layout, look = value
            self._draft[app.KEY_LAYOUT] = layout
            if look is not None:
                self._draft[app.KEY_LAYOUT_LOOK] = look

    def _draw_strip(self):
        """The presets around the one in use, as tiles in their look."""
        resolution = self._skin_resolution
        presets = self._presets()
        current = max(0, self._current_preset(presets))
        for index, item in enumerate(st.window_of(presets, current)):
            name, tile = "", {}
            if item:
                name, kind, value = item
                look = value[1] if kind == "built" else (value or {}).get(app.KEY_LAYOUT_LOOK)
                code = sl.normalize_look(look) if look else sl.DEFAULT_SKIP_LOOK
                tile = {"plate": sl.texture(code, "plate"), "tint": "FFFFFFFF", "pill": sl.texture(code, "focus", resolution),
                        "bar": "sl_white.png", "bartint": sl.look(code).accent}
            self._prop("st_t%d_name" % index, name)
            for part in TILE_PARTS:
                self._prop("st_t%d_%s" % (index, part), tile.get(part, ""))

    def _open_looks_menu(self):
        """OK on the Preset row: the list that loads, saves and deletes the looks saved under a name."""
        from next_episode_looks_ui import present_looks_menu

        try:
            present_looks_menu(self.addon, self._draft)
        except Exception as exc:
            log("Up Next Studio: the looks menu failed: %s" % exc)

    def _save_preset(self):
        from next_episode_looks_ui import _save_current

        try:
            _save_current(self.addon, self._draft)
        except Exception as exc:
            log("Up Next Studio: saving the look failed: %s" % exc)

    def _open_legacy(self):
        """The options of the popup of earlier versions: its own Customize screen, on this draft."""
        from next_episode_customize_ui import show_next_episode_customize

        legacy_keys = list(app.DEFAULT_DRAFT)
        draft = {key: self._draft.get(key) for key in legacy_keys}
        original = {key: self._original.get(key) for key in legacy_keys}
        if show_next_episode_customize(draft, original):
            # that screen saves by itself: what it stored is now both the draft and what is stored
            stored = self.load()
            for key in legacy_keys:
                self._draft[key] = self._original[key] = stored[key]

    # ------------------------------------------------------------------ about
    def about_text(self, item) -> str:
        addon = self.addon
        name = self._loc(item.name)
        why = dict((row.key, reason) for row, reason in self._all).get(item.key, "")
        if why:
            body = get_localized(addon, *ns.WHY[why])
        elif item.about:
            body = get_localized(addon, *item.about)
        elif item.kind == "preset":
            body = get_localized(addon, 49217, "A preset is a design in a look. Left and Right step through all of them, your "
                                               "saved ones included; OK opens the list that loads, saves and deletes them.")
        else:
            from skip_studio_ui import help_ids

            # a drawn option has the help of the skip dialog's option of the same name
            key = item.key
            if key.startswith(nc.PREFIX):
                key = {"overlay": sl.KEY_OVERLAY, "appear": sl.KEY_APPEAR, "leave": sl.KEY_LEAVE, "pulse": sl.KEY_PULSE,
                       "form": app.KEY_FORM, "zoom": app.KEY_ZOOM}.get(key[len(nc.PREFIX):], "skip_canvas_" + key[len(nc.PREFIX):])
            sid = help_ids().get(key)
            body = get_localized(addon, sid, "") if sid else ""
            if body.strip().lower() == name.strip().lower():
                body = ""
        return ("[B]%s[/B]   %s" % (name, body)).strip()

    def _update_about(self):
        slot = self._row_slot(self._focus_id())
        item = self._rows[slot] if slot is not None else None
        key = item.key if item else None
        if key == self._about_for and key is not None:
            return
        self._about_for = key
        presets = bool(item and item.kind == "preset")
        self._prop("st_mode", "presets" if presets else "about")
        self._prop("st_strip", get_localized(self.addon, 49028, "PRESETS") if presets
                   else get_localized(self.addon, 49128, "ABOUT THIS SETTING"))
        self._prop("st_about", "" if presets or item is None else self.about_text(item))

    # ------------------------------------------------------------- navigation
    def _row_slot(self, cid):
        try:
            index = int(cid) - st.ID_ROW_FIRST
        except (TypeError, ValueError):
            return None
        return index if 0 <= index < len(self._rows) else None

    def _show_row(self, index):
        scroll = scroll_for(index, self._scroll, len(self._all), st.ROWS)
        if scroll != self._scroll:
            self._scroll = scroll
            self._draw()
        self._focus(st.row_id(index - self._scroll))

    def _move(self, delta):
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
        else:
            if delta > 0 and count:
                self._show_row(0)
            else:
                self._focus(st.ID_SAVE)
        self._update_about()

    def _side(self, delta):
        cid = self._focus_id()
        foot = (st.ID_SAVE, st.ID_SAVE_PRESET, st.ID_RESET)
        if cid in foot:
            self._focus(foot[(foot.index(cid) + delta) % len(foot)])
            return
        if st.ID_TAB_FIRST <= cid < st.ID_TAB_FIRST + len(ns.TABS):
            self._open_tab((self._tab + delta) % len(ns.TABS))
            return
        slot = self._row_slot(cid)
        if slot is not None:
            self._change(self._rows[slot], delta)

    def _change(self, item, delta):
        """Step a row's choice; the focus stays on the row, wherever it now is."""
        if dict((row.key, reason) for row, reason in self._all).get(item.key):
            return  # dimmed: it does not apply
        if item.kind == "action":
            return
        if item.kind == "preset":
            self._step_preset(delta)
        else:
            ns.step(self._draft, item, delta)
        self._after_change(item.key)

    def _after_change(self, key):
        self._draw()
        self._refresh_preview()
        keys = [row.key for row, _why in self._all]
        if key in keys:
            self._show_row(keys.index(key))
        self._update_about()

    def _open_tab(self, index):
        self._tab, self._scroll = index, 0
        self._draw()
        self._focus(st.tab_id(self._tab))
        self._update_about()

    # ----------------------------------------------------------- save / close
    def _stop(self):
        self._playing = False

    def _save_and_close(self):
        self._stop()
        addon = self.addon
        try:
            for key, value in ns.changed(self._draft, self._original).items():
                addon.setSetting(key, value)
            self._saved = True
        except Exception as exc:
            log("Up Next Studio: saving failed: %s" % exc)
        self.close()

    def _cancel_and_close(self):
        self._stop()
        self.close()

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
            self._save_preset()
            self._draw()
            self._focus(st.ID_SAVE_PRESET)
        elif cid == st.ID_RESET:
            self._draft = ns.default_draft()
            self._draw()
            self._refresh_preview()
            self._focus(st.ID_RESET)
        elif st.ID_TAB_FIRST <= cid < st.ID_TAB_FIRST + len(ns.TABS):
            self._open_tab(cid - st.ID_TAB_FIRST)
        else:
            slot = self._row_slot(cid)
            if slot is None:
                return
            item = self._rows[slot]
            if dict((row.key, reason) for row, reason in self._all).get(item.key):
                return
            if item.kind == "preset":
                self._open_looks_menu()
                self._after_change(item.key)
            elif item.key == ns.KEY_LEGACY:
                self._open_legacy()
                self._after_change(item.key)
            else:
                self._change(item, 1)

    def onAction(self, action):
        aid = action.getId()
        if aid in CANCEL_ACTIONS:
            self._cancel_and_close()
        elif aid == MOVE_DOWN:
            self._move(1)
        elif aid == MOVE_UP:
            self._move(-1)
        elif aid in (MOVE_LEFT, MOVE_RIGHT):
            self._side(1 if aid == MOVE_RIGHT else -1)


def show_next_studio(draft=None, original=None) -> bool:
    """Open the Studio of the Up Next popup. True when it was saved."""
    addon = get_addon()
    if not addon:
        return False
    kwargs = {"addon": addon}
    if draft is not None:
        kwargs["draft"] = draft
    if original is not None:
        kwargs["original"] = original
    dialog = NextStudio(st.XML, addon.getAddonInfo("path"), "default", **kwargs)
    dialog.doModal()
    saved = bool(dialog._saved)
    del dialog
    return saved
