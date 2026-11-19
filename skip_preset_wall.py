# -*- coding: utf-8 -*-
"""The preset wall: every skip dialog preset as a tile, a page of twelve at a time.

A layout preset shows the miniature of its layout in its look (``tools/gen_preset_thumbs.py``); a
card preset is drawn from its own pictures (card, highlight, bar). OK takes the preset under the
focus, Back leaves without choosing. The last tile opens the list that saves, deletes, exports and
imports presets.

``tiles()`` and the two tile functions need no Kodi; the Studio's strip uses them too.
"""

from __future__ import annotations

import skip_dialog_card
import skip_dialog_presets as sp
import skip_layouts
import skip_studio as st

MANAGE = "__manage__"  # the answer of the last tile
PARTS = ("thumb", "plate", "tint", "pill", "bar", "bartint")


def card_tile(values) -> dict:
    """What a card preset draws: its card, its focus picture and its bar."""
    mode = sp.mode_name(values.get("skip_dialog_mode"))
    if mode == "Minimal":
        return {"plate": "", "tint": "FFFFFFFF", "pill": values.get("minimal_button_style", ""), "bar": "", "bartint": "FFFFFFFF"}
    style = skip_dialog_card.normalize(values.get("skip_card_style"))
    card_on = mode == "Full" and bool(values.get("skip_card_enabled", True))
    return {
        "plate": skip_dialog_card.texture(style) if card_on else "",
        "tint": skip_dialog_card.diffuse(style, values.get("skip_card_opacity", 95)),
        "pill": values.get("button_focus_style", ""),
        "bar": values.get("progress_bar_style", "") if values.get("show_progress_bar", True) else "",
        "bartint": "FFFFFFFF",
    }


def preset_tile(values) -> dict:
    """The tile of any preset: a miniature for one of a new layout, else the card's parts."""
    chosen = sp.layout_values(values)
    if chosen:
        return {"thumb": skip_layouts.thumb(chosen[skip_layouts.KEY_LAYOUT], chosen[skip_layouts.KEY_LOOK])}
    return card_tile(values)


def tiles(presets=None) -> list:
    """``[(stored name, shown name, values, tile)]`` in the order of the pickers."""
    out = []
    for name, values, builtin in (sp.list_presets() if presets is None else presets):
        out.append((name, sp.display_name(name) if builtin else name, values, preset_tile(values)))
    return out


def page_of(index) -> int:
    return int(index) // st.WALL_TILES


def show_preset_wall(addon, draft):
    """Open the wall. Returns the stored name of the chosen preset, ``MANAGE`` or None."""
    import xbmc
    import xbmcgui

    from addon_skin_resolution import init_window_xml_dialog
    from settings_utils import get_localized

    items = tiles()
    current = sp.detect_preset(draft)
    names = [item[0] for item in items]
    entries = [(name, shown, tile) for name, shown, _values, tile in items]
    entries.append((MANAGE, get_localized(addon, 49046, "Save, delete, export…"), {}))

    class Wall(xbmcgui.WindowXMLDialog):
        def __init__(self, *args):
            init_window_xml_dialog(super(Wall, self), args)
            self.result = None
            self.index = names.index(current) if current in names else 0

        def onInit(self):
            self.setProperty("pw_title", get_localized(addon, 49045, "Presets"))
            self.setProperty(
                "pw_hint",
                get_localized(addon, 49047, "Arrows: choose     OK: use this preset     Back: keep the current one"),
            )
            self._draw()

        def _draw(self):
            page = page_of(self.index)
            first = page * st.WALL_TILES
            for slot in range(st.WALL_TILES):
                entry = entries[first + slot] if first + slot < len(entries) else None
                name, shown, tile = entry if entry else ("", "", {})
                self.setProperty("pw_t%d_name" % slot, shown if entry else "")
                self.setProperty("pw_t%d_on" % slot, "1" if entry and name == current else "")
                for part in PARTS:
                    self.setProperty("pw_t%d_%s" % (slot, part), (tile or {}).get(part, ""))
            self.setProperty("pw_page", "%d / %d" % (page + 1, st.wall_pages(len(entries))))
            # a tile that was empty a moment ago is hidden until Kodi draws the next frame, and a
            # hidden control does not take the focus: ask again until it has it
            target = st.wall_id(self.index - first)
            for _attempt in range(8):
                try:
                    self.setFocusId(target)
                    if self.getFocusId() == target:
                        break
                except Exception:
                    pass
                xbmc.sleep(40)

        def _go(self, direction):
            target = st.wall_move(self.index, len(entries), direction)
            if target != self.index:
                self.index = target
                self._draw()

        def onAction(self, action):
            aid = action.getId()
            if aid in (10, 92, 216):
                self.close()
            elif aid in (1, 2, 3, 4):
                self._go({1: "left", 2: "right", 3: "up", 4: "down"}[aid])
            elif aid in (5, 6):  # page up / page down
                target = self.index + (st.WALL_TILES if aid == 6 else -st.WALL_TILES)
                self.index = max(0, min(len(entries) - 1, target))
                self._draw()

        def onClick(self, control_id):
            slot = int(control_id) - st.ID_WALL_FIRST
            index = page_of(self.index) * st.WALL_TILES + slot
            if 0 <= slot < st.WALL_TILES and index < len(entries):
                self.result = entries[index][0]
                self.close()

    wall = Wall(st.WALL_XML, addon.getAddonInfo("path"), "default")
    wall.doModal()
    result = wall.result
    del wall
    return result
