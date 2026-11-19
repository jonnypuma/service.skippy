# -*- coding: utf-8 -*-
"""The picture choices of the next episode popup, the Poster layout and bars in the segment type's colour."""
import os
import unittest
import xml.etree.ElementTree as ET

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import next_episode_appearance as app  # noqa: E402
import next_episode_lookup as lookup  # noqa: E402
import next_episode_view as view  # noqa: E402
import skip_layout_dialog as dialog  # noqa: E402
import skip_layouts as sl  # noqa: E402
from segment_editor_layout import CHIP_COLORS, chip_key  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SKINS = os.path.join(ROOT, "resources", "skins", "default")
EPISODE = {"thumb": "wide.jpg", "poster": "poster.jpg", "fanart": "fanart.jpg"}


class _Segment:
    def __init__(self, label):
        self.segment_type_label = label


class _Settings:
    def __init__(self, **values):
        self.values = values

    def get_text(self, key, default=""):
        return self.values.get(key, default)


def draft(**values):
    out = dict(app.DEFAULT_DRAFT)
    out.update(values)
    return out


class PicturePlanTests(unittest.TestCase):
    def test_the_default_is_the_episode_picture_as_before(self):
        self.assertEqual(app.DEFAULT_DRAFT[app.KEY_PICTURE], app.PICTURE_EPISODE)
        plan = app.picture_plan(draft(), EPISODE)
        self.assertEqual(plan, {"picture": app.PICTURE_EPISODE, "thumb": "wide.jpg", "pair_poster": "",
                                "pair_thumb": "", "fanart": ""})

    def test_each_choice(self):
        poster = app.picture_plan(draft(**{app.KEY_PICTURE: app.PICTURE_POSTER}), EPISODE)
        self.assertEqual((poster["picture"], poster["thumb"], poster["pair_poster"]), (app.PICTURE_POSTER, "poster.jpg", ""))
        both = app.picture_plan(draft(**{app.KEY_PICTURE: app.PICTURE_BOTH}), EPISODE)
        self.assertEqual((both["picture"], both["thumb"], both["pair_poster"], both["pair_thumb"]),
                         (app.PICTURE_BOTH, "", "poster.jpg", "wide.jpg"))
        fp = app.picture_plan(draft(**{app.KEY_PICTURE: app.PICTURE_FANART_POSTER}), EPISODE)
        self.assertEqual((fp["picture"], fp["thumb"], fp["fanart"]), (app.PICTURE_FANART_POSTER, "poster.jpg", "fanart.jpg"))
        fe = app.picture_plan(draft(**{app.KEY_PICTURE: app.PICTURE_FANART_EPISODE}), EPISODE)
        self.assertEqual((fe["picture"], fe["thumb"], fe["fanart"]), (app.PICTURE_FANART_EPISODE, "wide.jpg", "fanart.jpg"))
        fanart = app.picture_plan(draft(**{app.KEY_PICTURE: app.PICTURE_FANART}), EPISODE)
        self.assertEqual((fanart["picture"], fanart["thumb"], fanart["fanart"]), (app.PICTURE_FANART, "", "fanart.jpg"))

    def test_off_shows_nothing(self):
        plan = app.picture_plan(draft(**{app.KEY_THUMBNAIL: False, app.KEY_PICTURE: app.PICTURE_POSTER}), EPISODE)
        self.assertEqual(plan["picture"], "")
        self.assertEqual((plan["thumb"], plan["pair_poster"], plan["pair_thumb"], plan["fanart"]), ("", "", "", ""))

    def test_missing_art_falls_back_to_the_episode_picture_then_to_nothing(self):
        only_wide = {"thumb": "wide.jpg"}
        for wanted in (app.PICTURE_POSTER, app.PICTURE_BOTH):
            plan = app.picture_plan(draft(**{app.KEY_PICTURE: wanted}), only_wide)
            self.assertEqual((plan["picture"], plan["thumb"]), (app.PICTURE_EPISODE, "wide.jpg"), wanted)
        # without fanart the wide picture serves as the backdrop
        plan = app.picture_plan(draft(**{app.KEY_PICTURE: app.PICTURE_FANART}), only_wide)
        self.assertEqual((plan["picture"], plan["fanart"]), (app.PICTURE_FANART, "wide.jpg"))
        self.assertEqual(app.picture_plan(draft(**{app.KEY_PICTURE: app.PICTURE_POSTER}), {})["picture"], "")
        self.assertEqual(app.picture_plan(draft(), None)["picture"], "")

    def test_the_row_cycles_off_and_the_four_pictures_and_keeps_the_kind(self):
        d = draft()
        seen = []
        for _ in range(len(app.PICTURE_ROW_CHOICES)):
            seen.append(app.picture_choice(d))
            app.cycle_picture(d, 1)
        self.assertEqual(seen, [app.PICTURE_EPISODE, app.PICTURE_POSTER, app.PICTURE_BOTH, app.PICTURE_FANART,
                                app.PICTURE_FANART_POSTER, app.PICTURE_FANART_EPISODE, app.PICTURE_OFF])
        self.assertEqual(app.picture_choice(d), app.PICTURE_EPISODE)
        app.cycle_picture(d, -1)
        self.assertEqual((d[app.KEY_THUMBNAIL], d[app.KEY_PICTURE]), (False, app.PICTURE_EPISODE))


class PictureLayoutTests(unittest.TestCase):
    def layout(self, picture, thumbnail=True):
        return app.popup_layout(thumbnail=thumbnail, countdown=True, progress=True, picture=picture)

    def test_the_episode_layout_is_what_it_was(self):
        now = self.layout(app.PICTURE_EPISODE)
        self.assertEqual((now.thumb_w, now.thumb_h), (app.THUMB_W, app.THUMB_H))
        self.assertEqual(now.picture, app.PICTURE_EPISODE)
        self.assertEqual(app.popup_layout(thumbnail=True, countdown=True, progress=True), now)

    def test_a_poster_is_upright_and_pushes_the_rows_down(self):
        poster = self.layout(app.PICTURE_POSTER)
        self.assertEqual((poster.thumb_w, poster.thumb_h), (app.POSTER_W, app.POSTER_H))
        self.assertGreater(poster.thumb_h, poster.thumb_w)
        self.assertGreater(poster.panel_h, self.layout(app.PICTURE_EPISODE).panel_h)
        self.assertGreaterEqual(poster.countdown_y, app.PAD + app.POSTER_H)
        self.assertLess(poster.text_x, self.layout(app.PICTURE_EPISODE).text_x)

    def test_fanart_has_no_picture_box_and_text_from_the_left(self):
        fanart = self.layout(app.PICTURE_FANART)
        self.assertFalse(fanart.thumbnail)
        self.assertEqual(fanart.text_x, app.PAD)
        self.assertEqual(fanart.picture, app.PICTURE_FANART)

    def test_no_picture(self):
        none = self.layout(app.PICTURE_POSTER, thumbnail=False)
        self.assertEqual((none.picture, none.thumbnail), ("", False))

    def test_placements(self):
        ids = view.popup_ids()
        both = {p[0]: p[1:] for p in view.popup_placements(self.layout(app.PICTURE_BOTH), ids)}
        # the poster first, the episode picture beside it, at one height and on one line
        poster_box, thumb_box = both[ids.pair_poster], both[ids.pair_thumb]
        self.assertNotIn(ids.thumb, both)
        self.assertEqual(poster_box[3], thumb_box[3])
        self.assertEqual(poster_box[1], thumb_box[1])
        self.assertEqual(thumb_box[0], poster_box[0] + poster_box[2] + app.PAIR_GAP)
        self.assertAlmostEqual(poster_box[2] / float(poster_box[3]), 2 / 3.0, places=2)
        self.assertAlmostEqual(thumb_box[2] / float(thumb_box[3]), 16 / 9.0, places=2)
        pair_layout = self.layout(app.PICTURE_BOTH)
        self.assertGreaterEqual(pair_layout.text_x, thumb_box[0] + thumb_box[2] + app.TEXT_GAP)
        self.assertGreaterEqual(pair_layout.text_w, 240)
        self.assertNotIn(ids.fanart, both)
        # fanart with a picture in front: the backdrop and the picture box both
        for wanted, size in ((app.PICTURE_FANART_POSTER, (app.POSTER_W, app.POSTER_H)),
                             (app.PICTURE_FANART_EPISODE, (app.THUMB_W, app.THUMB_H))):
            placed = {p[0]: p[1:] for p in view.popup_placements(self.layout(wanted), ids)}
            self.assertIn(ids.fanart, placed, wanted)
            self.assertEqual(placed[ids.thumb][2:], size, wanted)
            self.assertNotIn(ids.pair_poster, placed, wanted)
        fan_layout = self.layout(app.PICTURE_FANART)
        fan = {p[0]: p[1:] for p in view.popup_placements(fan_layout, ids)}
        self.assertEqual(fan[ids.fanart], fan[ids.veil])
        self.assertEqual(fan[ids.fanart][0], app.FANART_INSET)
        self.assertEqual(fan[ids.fanart][2], fan_layout.panel_w - 2 * app.FANART_INSET)
        self.assertNotIn(ids.thumb, fan)
        self.assertNotIn(ids.pair_poster, fan)
        poster = {p[0]: p[1:] for p in view.popup_placements(self.layout(app.PICTURE_POSTER), ids)}
        self.assertEqual(poster[ids.thumb][2:], (app.POSTER_W, app.POSTER_H))

    def test_the_skins_have_the_three_new_pictures_and_the_mock_too(self):
        for res in ("720p", "1080i"):
            for name, offset in (("NextEpisodeDialog.xml", 0), ("NextEpisodeCustomize.xml", view.MOCK_ID_OFFSET)):
                with open(os.path.join(SKINS, res, name), encoding="utf-8") as handle:
                    root = ET.fromstring(handle.read().split("?>", 1)[1])
                found = {c.get("id") for c in root.iter("control")}
                ids = view.popup_ids(offset)
                for cid in (ids.fanart, ids.veil, ids.pair_poster, ids.pair_thumb):
                    self.assertIn(str(cid), found, (res, name, cid))

    def test_the_lookup_keys(self):
        art = {"tvshow.poster": "show.jpg", "poster": "ep.jpg", "tvshow.fanart": "fan.jpg", "thumb": "wide.jpg"}
        self.assertEqual(lookup.pick_thumb(art, lookup._POSTER_KEYS), "show.jpg")
        self.assertEqual(lookup.pick_thumb(art, lookup._FANART_KEYS), "fan.jpg")
        self.assertEqual(lookup.pick_thumb({}, lookup._POSTER_KEYS), "")


class TypeColourTests(unittest.TestCase):
    def test_the_bar_takes_the_colour_of_the_segment_type_by_default(self):
        self.assertEqual(sl.normalize_bar_color(None), sl.BAR_TYPE)
        self.assertEqual(sl.normalize_bar_color("look"), sl.BAR_LOOK)
        self.assertEqual(sl.accent("fgd", sl.BAR_TYPE, "7FB4FF"), "FF7FB4FF")
        self.assertEqual(sl.accent("fgd", sl.BAR_LOOK, "7FB4FF"), sl.look("fgd").accent)
        self.assertEqual(sl.accent("fgf", sl.BAR_TYPE, ""), sl.look("fgf").accent)

    def test_the_dialog_reads_the_type_and_the_setting(self):
        intro, recap = _Segment("intro"), _Segment("Recap")
        self.assertEqual(dialog.layout_accent(None, "fgf", intro, settings=_Settings()), "FF" + CHIP_COLORS["intro"])
        self.assertEqual(dialog.layout_accent(None, "fgf", recap, settings=_Settings()), "FF" + CHIP_COLORS["recap"])
        look = _Settings(**{sl.KEY_BAR_COLOR: sl.BAR_LOOK})
        self.assertEqual(dialog.layout_accent(None, "fgd", intro, settings=look), sl.look("fgd").accent)
        self.assertEqual(dialog.layout_accent(None, "fgf", _Segment("something else"), settings=_Settings()),
                         "FF" + CHIP_COLORS[chip_key("something else")])  # a type of the user's own: a spare colour

    def test_the_setting_lists_both_choices(self):
        root = ET.parse(os.path.join(ROOT, "resources", "settings.xml")).getroot()
        setting = next(s for s in root.iter("setting") if s.get("id") == sl.KEY_BAR_COLOR)
        self.assertEqual([o.text for o in setting.iter("option")], [sl.BAR_TYPE, sl.BAR_LOOK])
        self.assertEqual(setting.find("default").text, sl.BAR_TYPE)
        picture = next(s for s in root.iter("setting") if s.get("id") == app.KEY_PICTURE)
        self.assertEqual([o.text for o in picture.iter("option")], list(app.PICTURES))


class PosterLayoutTests(unittest.TestCase):
    def test_poster_card_is_a_layout_with_both_sizes_kept_last(self):
        self.assertEqual(sl.normalize_layout("Poster card"), "Poster")
        sized = [item for item in sl.all_layouts() if item.size != sl.SIZE_MINIMAL]
        self.assertEqual([item.name for item in sized[-2:]], ["Poster", "Poster"])
        for size in (sl.SIZE_FULL, sl.SIZE_COMPACT):
            layout = sl.get("Poster", size)
            with open(os.path.join(SKINS, "720p", layout.xml), encoding="utf-8") as handle:
                text = handle.read()
            self.assertEqual(text.count("Window.Property(skl_poster)"), 1, layout.xml)
            self.assertIn("<aspectratio>scale</aspectratio>", text)


if __name__ == "__main__":
    unittest.main()
