# -*- coding: utf-8 -*-
"""The Studio of the Up Next popup: its tabs and rows, what is dimmed and why, its draft and what Save writes."""
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

import next_canvas as nc  # noqa: E402
import next_episode_appearance as app  # noqa: E402
import next_studio as ns  # noqa: E402

P = nc.PREFIX


class RowTests(unittest.TestCase):
    def setUp(self):
        self.draft = ns.default_draft()

    def rows(self, tab):
        return dict((item.key, why) for item, why in ns.tab_rows(self.draft)[ns.TABS.index(tab)])

    def test_the_six_tabs_of_the_mockup(self):
        self.assertEqual(ns.TABS, ("look", "layout", "picture", "buttons", "motion", "autoplay"))
        self.assertEqual(len(ns.TAB_ROWS), len(ns.TAB_LABELS))
        keys = [item.key for rows in ns.TAB_ROWS for item in rows]
        self.assertEqual(len(keys), len(set(keys)))

    def test_every_row_that_is_a_setting_is_in_the_draft_and_in_settings_xml(self):
        with open(os.path.join(ROOT, "resources", "settings.xml"), encoding="utf-8") as handle:
            text = handle.read()
        for rows in ns.TAB_ROWS:
            for item in rows:
                if item.kind in ("soon", "action", "preset"):
                    continue
                self.assertIn(item.key, self.draft, item.key)
                self.assertIn('id="%s"' % item.key, text, item.key)

    def test_nothing_is_hidden_what_does_not_apply_is_dimmed_with_a_reason(self):
        counts = [len(rows) for rows in ns.tab_rows(self.draft)]
        self.draft[app.KEY_LAYOUT] = "Card"  # the popup of earlier versions
        self.assertEqual([len(rows) for rows in ns.tab_rows(self.draft)], counts)
        look = self.rows("look")
        self.assertEqual(look[P + "form"], "drawn")
        self.assertEqual(look[ns.KEY_LEGACY], "")  # its own options are a step away
        self.assertEqual(look[ns.KEY_PRESET], "")
        self.assertEqual(self.rows("autoplay")["next_episode_lead_seconds"], "")
        self.draft[app.KEY_LAYOUT] = "CardA"
        self.assertEqual(self.rows("look")[ns.KEY_LEGACY], "other")
        self.assertFalse([item.key for rows in ns.TAB_ROWS for item in rows if item.kind == "soon"])  # every row is built
        self.assertEqual(self.rows("look")[app.KEY_LAYOUT_LOOK], "")
        self.draft[P + "follow_skin"] = "true"
        self.assertEqual((self.rows("look")[app.KEY_LAYOUT_LOOK], self.rows("look")[P + "same_look"]), ("other", "other"))
        self.draft[P + "follow_skin"] = "false"
        self.assertEqual(self.rows("look")[P + "fill_on"], "other")  # only a fill has a place to show on
        ns.set_progress_state(self.draft, "Fill")
        self.assertEqual(self.rows("look")[P + "fill_on"], "")
        self.assertTrue(all(why in ("", "soon", "other", "drawn") for rows in ns.tab_rows(self.draft) for _item, why in rows))

    def test_the_native_toast_leaves_only_the_style_and_autoplay(self):
        self.draft[app.KEY_STYLE] = app.STYLE_NATIVE
        look = self.rows("look")
        self.assertEqual(look[app.KEY_STYLE], "")
        self.assertTrue(all(why for key, why in look.items() if key != app.KEY_STYLE))
        self.assertTrue(all(not why or key == "next_episode_still_watching_after" for key, why in self.rows("autoplay").items()))

    def test_rows_step_their_values(self):
        d = self.draft
        self.assertTrue(ns.step(d, ns.find(P + "form"), 1))
        self.assertEqual(d[P + "form"], "Compact")
        ns.step(d, ns.find(P + "zoom"), -1)
        self.assertEqual(d[P + "zoom"], "85")
        ns.step(d, ns.find(P + "plot"), 1)
        self.assertEqual(d[P + "plot"], "false")
        ns.step(d, ns.find(P + "distance"), 1)
        self.assertEqual(d[P + "distance"], "72")
        for _ in range(40):
            ns.step(d, ns.find(P + "distance"), 1)
        self.assertEqual(d[P + "distance"], "160")  # it stops at its end
        ns.step(d, ns.find(P + "place"), 1)
        self.assertEqual((d[P + "place"], d[app.KEY_POSITION]), ("TopLeft", "TopLeft"))
        ns.step(d, ns.find(P + "accent"), 1)
        self.assertEqual(d[P + "accent"], "Gold")
        # Progress: Line, Circle, Fill, Off (a switch and a kind underneath)
        seen = []
        for _ in range(4):
            ns.step(d, ns.find(app.KEY_PROGRESS), 1)
            seen.append((ns.progress_state(d), d[app.KEY_PROGRESS], d[P + "progress"]))
        self.assertEqual(seen, [("Circle", True, "Circle"), ("Fill", True, "Fill"), ("Off", False, "Fill"), ("Line", True, "Auto")])
        ns.step(d, ns.find(P + "speed"), 1)
        self.assertEqual(d[P + "speed"], "20")
        ns.step(d, ns.find(P + "caps"), 1)
        self.assertEqual(d[P + "caps"], "On")
        ns.step(d, ns.find("next_episode_popup_end_action"), 1)
        self.assertEqual(d["next_episode_popup_end_action"], "Play")
        ns.step(d, ns.find(ns.KEY_PRESET), 1)
        self.assertEqual(app.preset_name(*app.preset_of(d)), "Card · Fused Glass Frost")
        ns.step(d, ns.find(P + "focus_style"), 1)
        self.assertEqual(d[P + "focus_style"], "Accent")
        ns.step(d, ns.find(P + "subtitles"), 1)
        self.assertEqual(d[P + "subtitles"], "true")

    def test_save_writes_only_what_changed(self):
        original = ns.default_draft()
        self.assertEqual(ns.changed(self.draft, original), {})
        ns.step(self.draft, ns.find(P + "form"), 1)
        ns.step(self.draft, ns.find("next_episode_start_at_credits"), 1)
        self.assertEqual(ns.changed(self.draft, original), {P + "form": "Compact", "next_episode_start_at_credits": "false"})

    def test_the_draft_is_read_from_the_settings(self):
        stored = {P + "form": "Minimal", "next_episode_lead_seconds": "60", app.KEY_LAYOUT: "Queue"}
        draft = ns.load(lambda key, default: stored.get(key, default), lambda key, default: default)
        self.assertEqual((draft[P + "form"], draft["next_episode_lead_seconds"], draft[app.KEY_LAYOUT]), ("Minimal", "60", "Queue"))
        self.assertEqual(draft[P + "zoom"], "100")

    def test_the_new_strings_are_in_every_language(self):
        folder = os.path.join(ROOT, "resources", "language")
        for lang in os.listdir(folder):
            with open(os.path.join(folder, lang, "strings.po"), encoding="utf-8") as handle:
                text = handle.read()
            for sid in range(49199, 49227):
                self.assertIn('msgctxt "#%d"' % sid, text, (lang, sid))

    def test_the_settings_screen_opens_the_studio(self):
        with open(os.path.join(ROOT, "skippy_runscript_entry.py"), encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn("from next_studio_ui import show_next_studio", source)
        self.assertIn('"customize_next_episode_popup_classic"', source)


if __name__ == "__main__":
    unittest.main()
