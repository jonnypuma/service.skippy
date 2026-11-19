# -*- coding: utf-8 -*-
"""The popup layouts Takeover and Queue."""
import os
import unittest
import xml.etree.ElementTree as ET

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import next_episode_lookup as lookup  # noqa: E402
import next_layouts as nl  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SKINS = os.path.join(ROOT, "resources", "skins", "default")


def episode(number, **more):
    out = {"source": lookup.SOURCE_LIBRARY, "episodeid": 100 + number, "tvshowid": 4, "season": 1, "episode": number,
           "file": "e%d.mkv" % number, "title": "Episode %d" % number}
    out.update(more)
    return out


class LayoutTests(unittest.TestCase):
    def test_both_are_choices_after_the_others(self):
        self.assertIn("Takeover", nl.LAYOUTS)
        self.assertIn("Queue", nl.LAYOUTS)
        self.assertEqual(nl.normalize_layout("takeover"), "Takeover")
        self.assertEqual(nl.get("Queue").xml, "NextLayout_Queue.xml")

    def test_takeover_fills_the_screen_and_prefers_the_fanart(self):
        layout = nl.get("Takeover")
        self.assertEqual((layout.width, layout.height), (1280, 720))
        self.assertEqual(nl.origin(layout, "TopLeft"), (0, 0))
        self.assertEqual(nl.picture(layout, {"fanart": "f.jpg", "thumb": "t.jpg", "poster": "p.jpg"}), "f.jpg")
        self.assertEqual(nl.picture(layout, {"thumb": "t.jpg", "poster": "p.jpg"}), "t.jpg")
        self.assertEqual(nl.picture(layout, {"poster": "p.jpg"}), "p.jpg")
        self.assertEqual(nl.picture(layout, {}), "")

    def test_the_queue_cards_fit_and_chain_left_to_right(self):
        layout = nl.get("Queue")
        self.assertEqual(nl.QUEUE_IDS[0], nl.ID_PLAY)  # the first card is what Play is elsewhere
        last = nl.queue_left(nl.QUEUE_SIZE - 1) + nl.QUEUE_CARD_W
        self.assertLessEqual(last + nl.QUEUE_LEFT, layout.width)
        for res in ("720p", "1080i"):
            root = ET.parse(os.path.join(SKINS, res, layout.xml)).getroot()
            cards = {int(c.get("id")): c for c in root.iter("control") if c.get("type") == "button"}
            for index, cid in enumerate(nl.QUEUE_IDS):
                card = cards[cid]
                self.assertEqual(int(card.find("ondown").text), nl.ID_CLOSE)
                self.assertEqual(int(card.find("onright").text), nl.QUEUE_IDS[min(index + 1, nl.QUEUE_SIZE - 1)])
                self.assertEqual(int(card.find("onleft").text), nl.QUEUE_IDS[max(index - 1, 0)])
            self.assertEqual(int(root.find("defaultcontrol").text), nl.ID_PLAY)


class QueueLookupTests(unittest.TestCase):
    def setUp(self):
        self._real = lookup.find_library_successor

    def tearDown(self):
        lookup.find_library_successor = self._real

    def test_the_queue_follows_the_library(self):
        asked = []

        def fake(item, *, skip_watched=False, current=None):
            asked.append(dict(current))
            number = current["episode"] + 1
            return episode(number) if number <= 5 else None

        lookup.find_library_successor = fake
        queue = lookup.find_queue(episode(3), 3)
        self.assertEqual([e["episode"] for e in queue], [3, 4, 5])
        self.assertEqual(asked[0]["id"], 103)
        self.assertEqual(asked[0]["tvshowid"], 4)
        self.assertEqual([e["episode"] for e in lookup.find_queue(episode(5), 3)], [5])

    def test_what_is_not_a_library_episode_stands_alone(self):
        lookup.find_library_successor = lambda *a, **k: self.fail("no lookup expected")
        self.assertEqual(len(lookup.find_queue({"source": "playlist", "title": "x"}, 3)), 1)
        self.assertEqual(len(lookup.find_queue(episode(2, tvshowid=None), 3)), 1)
        self.assertEqual(lookup.find_queue(None, 3), [])

    def test_a_failing_lookup_ends_the_queue(self):
        def broken(*args, **kwargs):
            raise RuntimeError("library gone")

        lookup.find_library_successor = broken
        self.assertEqual(len(lookup.find_queue(episode(1), 3)), 1)


if __name__ == "__main__":
    unittest.main()
