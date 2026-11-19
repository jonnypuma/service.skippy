# -*- coding: utf-8 -*-
"""Layout presets (a layout in a look, by name) and the preset wall of the Studio."""
import os
import unittest
import xml.etree.ElementTree as ET

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import skip_dialog_presets as sp  # noqa: E402
import skip_layouts as sl  # noqa: E402
import skip_preset_wall as wall  # noqa: E402
import skip_studio as st  # noqa: E402
from tools import gen_preset_thumbs as thumbs  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SKINS = os.path.join(ROOT, "resources", "skins", "default")
MEDIA = os.path.join(SKINS, "media")


class LayoutPresetTests(unittest.TestCase):
    def test_every_new_layout_has_a_preset_in_every_look(self):
        presets = sp.layout_presets()
        layouts = [key for key, _label in sl.LAYOUT_NAMES if key != "Card"]
        self.assertEqual(len(presets), len(layouts) * len(sl.LOOKS))
        names = [name for name, _values in presets]
        self.assertEqual(len(set(names)), len(names))
        for name, values in presets:
            self.assertTrue(sp.is_layout_preset(values), name)
            self.assertIn(values[sl.KEY_LAYOUT], layouts)

    def test_the_list_keeps_legacy_presets_last(self):
        listed = sp.list_presets()
        names = [name for name, _values, _builtin in listed]
        self.assertEqual(len(set(names)), len(names))
        first_layout = min(i for i, (_n, v, _b) in enumerate(listed) if sp.is_layout_preset(v))
        first_legacy = min(i for i, (n, _v, b) in enumerate(listed) if b and sp.is_legacy(n))
        self.assertLess(first_layout, first_legacy)
        self.assertTrue(all(sp.is_legacy(n) for n, _v, b in listed[first_legacy:] if b))

    def test_applying_a_layout_preset_is_found_again(self):
        for name, values in sp.layout_presets():
            draft = {}
            sp.apply_preset(draft, sp.list_presets()[0][1])
            sp.apply_preset(draft, values)
            self.assertEqual(sp.detect_preset(draft), name)
            self.assertEqual(draft[sl.KEY_LAYOUT], values[sl.KEY_LAYOUT])

    def test_a_card_preset_goes_back_to_the_card(self):
        draft = {}
        sp.apply_preset(draft, sp.layout_presets()[0][1])
        name, values, _builtin = next(p for p in sp.list_presets() if not sp.is_layout_preset(p[1]))
        self.assertFalse(sp.is_layout_preset(values))
        sp.apply_preset(draft, values)
        self.assertEqual(draft[sl.KEY_LAYOUT], "Card")
        self.assertEqual(sp.detect_preset(draft), name)

    def test_layout_preset_names_are_reserved(self):
        reserved = sp.reserved_names()
        for name, _values in sp.layout_presets():
            self.assertIn(name.lower(), reserved)


class ThumbTests(unittest.TestCase):
    def test_every_layout_preset_has_its_miniature(self):
        for _name, values in sp.layout_presets():
            picture = sl.thumb(values[sl.KEY_LAYOUT], values[sl.KEY_LOOK])
            self.assertTrue(os.path.isfile(os.path.join(MEDIA, picture)), picture)

    def test_the_miniatures_are_up_to_date(self):
        self.assertEqual(thumbs.stale(), [])


class WallTests(unittest.TestCase):
    def test_tiles_follow_the_list(self):
        listed = sp.list_presets()
        tiles = wall.tiles(listed)
        self.assertEqual([t[0] for t in tiles], [n for n, _v, _b in listed])
        for _name, shown, values, tile in tiles:
            self.assertTrue(shown)
            if sp.is_layout_preset(values):
                self.assertEqual(list(tile), ["thumb"])
            else:
                self.assertNotIn("thumb", tile)

    def test_legacy_tiles_say_so(self):
        for name, shown, _values, _tile in wall.tiles():
            if sp.is_legacy(name):
                self.assertTrue(shown.endswith("(legacy)"), shown)

    def test_pages(self):
        self.assertEqual(st.wall_pages(0), 1)
        self.assertEqual(st.wall_pages(12), 1)
        self.assertEqual(st.wall_pages(13), 2)
        self.assertEqual(wall.page_of(11), 0)
        self.assertEqual(wall.page_of(12), 1)

    def test_moves_stop_at_the_ends_and_cross_pages(self):
        count = 30
        self.assertEqual(st.wall_move(0, count, "left"), 0)
        self.assertEqual(st.wall_move(0, count, "up"), 0)
        self.assertEqual(st.wall_move(11, count, "right"), 12)  # onto the next page
        self.assertEqual(st.wall_move(12, count, "left"), 11)
        self.assertEqual(st.wall_move(8, count, "down"), 12)
        self.assertEqual(st.wall_move(29, count, "right"), 29)
        self.assertEqual(st.wall_move(27, count, "down"), 29)  # a short last row: its last item
        self.assertEqual(st.wall_move(29, count, "down"), 29)

    def test_tiles_do_not_overlap_and_fit_the_screen(self):
        boxes = [st.wall_box(i) for i in range(st.WALL_TILES)]
        for x, y, w, h in boxes:
            self.assertGreaterEqual(x, 0)
            self.assertLessEqual(x + w, 1280)
            self.assertLessEqual(y + h + 26, 690)  # the name under the tile stays above the hint
        self.assertGreaterEqual(st.WALL_STEP_X, st.WALL_TILE_W)
        self.assertGreaterEqual(st.WALL_STEP_Y, st.WALL_TILE_H + 26)

    def test_the_wall_file(self):
        for res, scale in (("720p", 1.0), ("1080i", 1.5)):
            path = os.path.join(SKINS, res, st.WALL_XML)
            root = ET.parse(path).getroot()
            ids = [int(c.get("id")) for c in root.iter("control") if c.get("type") == "button"]
            self.assertEqual(ids, [st.wall_id(i) for i in range(st.WALL_TILES)], res)
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
            for index in range(st.WALL_TILES):
                for part in ("name", "on") + wall.PARTS[:5]:
                    self.assertIn("pw_t%d_%s)" % (index, part), text)
            first = next(c for c in root.iter("control") if c.get("id") == str(st.wall_id(0)))
            self.assertEqual(int(first.find("width").text), int(round((st.WALL_TILE_W + 8) * scale)))
            for texture in root.iter("texture"):
                name = (texture.text or "").strip()
                if name and not name.startswith("$") and name != "-":
                    self.assertTrue(os.path.isfile(os.path.join(MEDIA, name)), name)


if __name__ == "__main__":
    unittest.main()
