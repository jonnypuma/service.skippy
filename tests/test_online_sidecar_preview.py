# -*- coding: utf-8 -*-
"""The text shown before an online save overwrites or updates a sidecar.

The person decides from this text whether their own file is replaced, so it must name what
changes, what stays and what is lost.
"""

import unittest
from unittest.mock import patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import service_online_sidecar_preview as preview  # noqa: E402
from segment_item import SegmentItem  # noqa: E402

EXISTING_XML = (
    "<Chapters><EditionEntry>"
    "<ChapterAtom><ChapterTimeStart>00:00:10.000</ChapterTimeStart><ChapterTimeEnd>00:01:00.000</ChapterTimeEnd>"
    "<ChapterDisplay><ChapterString>Intro</ChapterString></ChapterDisplay></ChapterAtom>"
    "<ChapterAtom><ChapterTimeStart>00:05:00.000</ChapterTimeStart><ChapterTimeEnd>00:05:30.000</ChapterTimeEnd>"
    "<ChapterDisplay><ChapterString>Commercial</ChapterString></ChapterDisplay></ChapterAtom>"
    "</EditionEntry></Chapters>"
)


def _online():
    return [
        SegmentItem(12.0, 62.0, "intro", source="theintrodb"),
        SegmentItem(1300.0, 1380.0, "credits", source="introdb"),
    ]


class PreviewLinesTests(unittest.TestCase):
    def test_the_final_file_is_listed_in_time_order(self):
        lines = preview._lines_for_sidecar_preview_items(
            [SegmentItem(100, 200, "credits"), SegmentItem(0, 50, "intro")]
        )
        self.assertEqual(len(lines), 2)
        self.assertIn("intro", lines[0])
        self.assertIn("credits", lines[1])

    def test_an_empty_result_says_so_and_a_long_one_is_cut(self):
        self.assertEqual(preview._lines_for_sidecar_preview_items([]), ["  (empty)"])
        many = [SegmentItem(i * 10, i * 10 + 5, "intro") for i in range(40)]
        lines = preview._lines_for_sidecar_preview_items(many, max_rows=36)
        self.assertEqual(len(lines), 37)
        self.assertEqual(lines[-1], "  … +4 more")

    def test_update_changes_show_old_and_new_times_and_the_source(self):
        rows = [
            {
                "local_label": "Intro",
                "old_start": 10.0,
                "old_end": 60.0,
                "new_start": 12.0,
                "new_end": 62.0,
                "online_label": "intro",
                "online_source": "theintrodb",
            }
        ]
        lines = preview._lines_for_update_changes(rows)
        self.assertEqual(lines[0], "Planned time updates (local label kept):")
        self.assertIn("Intro", lines[1])
        self.assertIn("TheIntroDB.org", lines[1])
        self.assertIn("→", lines[1])
        self.assertIn("already match", preview._lines_for_update_changes([])[0])

    def test_overwrite_compare_pairs_types_and_counts_what_is_lost(self):
        local = [SegmentItem(10, 60, "intro"), SegmentItem(300, 330, "commercial")]
        lines = preview._lines_overwrite_compare(local, _online())
        text = "\n".join(lines)
        self.assertIn("local", text)
        self.assertIn("no same-type local entry", text)  # credits is new
        self.assertIn("Local-only rows (will be removed on overwrite): 1", text)
        self.assertEqual(preview._lines_overwrite_compare(local, []), [])

    def test_long_text_is_cut_for_the_dialog(self):
        self.assertEqual(preview._clamp_dialog_text("short"), "short")
        cut = preview._clamp_dialog_text("x" * 5000, max_chars=100)
        self.assertLessEqual(len(cut), 100)
        self.assertTrue(cut.endswith("(message truncated)"))


class LanguageTests(unittest.TestCase):
    def test_the_texts_follow_the_users_language(self):
        import service_online_sidecar_merge as merge

        german = {
            35035: "Geplante Zeitänderungen (lokale Bezeichnung bleibt):",
            35042: "Nur lokale Zeilen (werden beim Überschreiben entfernt): %d",
            35047: "[Online-Abfrage]",
        }

        class _Addon:
            def getLocalizedString(self, string_id):
                return german.get(string_id, "")

        with patch.object(merge, "get_addon", lambda: _Addon()):
            rows = [{"local_label": "Intro", "old_start": 1, "old_end": 2, "new_start": 3, "new_end": 4,
                     "online_label": "intro", "online_source": "theintrodb"}]
            self.assertEqual(preview._lines_for_update_changes(rows)[0], german[35035])
            lines = preview._lines_overwrite_compare([SegmentItem(10, 60, "intro"), SegmentItem(300, 330, "recap")], _online())
            self.assertEqual(lines[-1], "Nur lokale Zeilen (werden beim Überschreiben entfernt): 1")
            self.assertEqual(merge._summarize_online_by_source(_online())[0], "[Online-Abfrage]")
            # A string the language lacks falls back to English.
            self.assertIn("(online intro from TheIntroDB.org)", preview._lines_for_update_changes(rows)[1])


class AskDetailTests(unittest.TestCase):
    def setUp(self):
        stack = [
            patch.object(preview, "safe_file_read", lambda _path: EXISTING_XML),
            patch.object(preview, "parse_edl", lambda _v, update_monitor=False: [SegmentItem(10, 60, "intro")]),
            patch.object(preview, "get_addon", lambda: None),
            patch.object(preview, "log"),
        ]
        for p in stack:
            p.start()
            self.addCleanup(p.stop)

    def detail(self, policy, **scope):
        args = dict(scope_xml=False, scope_edl=False, xml_path=None, edl_path=None)
        args.update(scope)
        return preview._build_sidecar_ask_detail("/v/show.mkv", _online(), policy, **args)

    def test_update_lists_the_sources_the_changes_and_the_result(self):
        text = self.detail(preview._SAVE_CHAPTERS_UPDATE_ASK, scope_xml=True, xml_path="/v/show_chapters.xml")
        self.assertIn("[Online lookup]", text)
        self.assertIn("TheIntroDB.org", text)
        self.assertIn("IntroDB.app", text)
        self.assertIn("[Chapters XML]", text)
        self.assertIn("Planned time updates", text)
        self.assertIn("If you accept, this sidecar will contain:", text)
        self.assertNotIn("[EDL]", text)

    def test_update_all_for_the_edl_says_the_credits_are_added(self):
        text = self.detail(preview._SAVE_CHAPTERS_UPDATE_ALL_ASK, scope_edl=True, edl_path="/v/show.edl")
        result = text.split("[EDL] If you accept, this sidecar will contain:")[1]
        self.assertIn("credits", result)
        self.assertIn("intro", result)

    def test_overwrite_counts_both_sides(self):
        text = self.detail(
            preview._SAVE_CHAPTERS_OVERWRITE_ASK,
            scope_xml=True,
            xml_path="/v/show_chapters.xml",
            scope_edl=True,
            edl_path="/v/show.edl",
        )
        self.assertIn("[Chapters XML] Currently 2 chapter(s); online returns 2 window(s).", text)
        self.assertIn("[EDL] Currently 1 row(s); online returns 2 window(s).", text)
        self.assertIn("Local-only rows (will be removed on overwrite): 1", text)

    def test_a_failure_gives_an_empty_detail_not_an_error(self):
        with patch.object(preview, "_summarize_online_by_source", side_effect=RuntimeError("boom")):
            self.assertEqual(self.detail(preview._SAVE_CHAPTERS_UPDATE_ASK), "")


if __name__ == "__main__":
    unittest.main()
