import unittest
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import service_source_conflict as sc  # noqa: E402
from remote_lookup import merge_remote_segments  # noqa: E402
from segment_item import SegmentItem  # noqa: E402


def seg(start, end, label="intro", source="edl"):
    return SegmentItem(start, end, label=label, source=source)


def merged_online(a=(10, 60), b=(10.8, 59.5)):
    return merge_remote_segments(
        [seg(*a, source="theintrodb")], [seg(*b, source="introdb")]
    )


class MergeCorroborationTests(unittest.TestCase):
    def test_agreeing_secondary_is_remembered_on_the_winner(self):
        out = merged_online()
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].corroboration[0][0], "introdb")

    def test_overlapping_but_disagreeing_secondary_is_not_corroboration(self):
        out = merged_online(b=(14, 70))
        self.assertEqual(len(out), 1)
        self.assertFalse(getattr(out[0], "corroboration", []))


class FindConflictsTests(unittest.TestCase):
    def test_local_far_from_two_agreeing_online_sources_is_a_conflict(self):
        found = sc.find_source_conflicts([seg(20, 70, source="xml")], merged_online())
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].bucket, "intro")
        self.assertEqual(found[0].online_sources, ["theintrodb", "introdb"])

    def test_local_within_tolerance_is_not_a_conflict(self):
        self.assertEqual(sc.find_source_conflicts([seg(10.9, 60.7, source="xml")], merged_online()), [])

    def test_single_online_source_is_not_enough(self):
        online = [seg(10, 60, source="theintrodb")]
        self.assertEqual(sc.find_source_conflicts([seg(40, 90, source="xml")], online), [])

    def test_different_segment_types_do_not_conflict(self):
        self.assertEqual(sc.find_source_conflicts([seg(40, 90, label="credits")], merged_online()), [])


class ChoiceTests(unittest.TestCase):
    def setUp(self):
        self.store = {}
        self.patches = [
            patch.object(sc, "read_json", side_effect=lambda _p, default=None: dict(self.store)),
            patch.object(sc, "write_json", side_effect=self._write),
            patch.object(sc, "profile_path", return_value="x"),
        ]
        for p in self.patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in self.patches])
        self.local = seg(20, 70, source="xml")
        self.remote = merged_online()

    def _write(self, _path, data):
        self.store.clear()
        self.store.update(data)
        return True

    def test_choice_round_trip(self):
        self.assertIsNone(sc.get_choice("/a.mkv", "intro"))
        self.assertTrue(sc.save_choice("/a.mkv", "intro", sc.CHOICE_ONLINE))
        self.assertEqual(sc.get_choice("/a.mkv", "intro"), sc.CHOICE_ONLINE)
        self.assertFalse(sc.save_choice("/a.mkv", "intro", "bogus"))

    def test_online_choice_replaces_local_segment_when_local_wins(self):
        sc.save_choice("/a.mkv", "intro", sc.CHOICE_ONLINE)
        out = sc.apply_source_choices("/a.mkv", [self.local], [self.local], self.remote)
        self.assertEqual(out, [self.remote[0]])

    def test_local_choice_replaces_online_segment_when_online_wins(self):
        sc.save_choice("/a.mkv", "intro", sc.CHOICE_LOCAL)
        out = sc.apply_source_choices("/a.mkv", list(self.remote), [self.local], self.remote)
        self.assertEqual(out, [self.local])

    def test_no_choice_keeps_the_priority_result(self):
        out = sc.apply_source_choices("/a.mkv", [self.local], [self.local], self.remote)
        self.assertEqual(out, [self.local])

    def test_stored_files_are_capped(self):
        for i in range(sc.MAX_STORED_FILES + 5):
            sc.save_choice("/f%d.mkv" % i, "intro", sc.CHOICE_LOCAL)
        self.assertEqual(len(self.store), sc.MAX_STORED_FILES)


class PromptGateTests(unittest.TestCase):
    def test_disabled_setting_never_prompts(self):
        with patch.object(sc, "get_addon", return_value=MagicMock()), \
             patch.object(sc, "addon_get_bool", return_value=False), \
             patch("skip_source_picker_ui.review_source_conflicts") as review:
            sc.maybe_prompt_source_conflict("/a.mkv", "episode", [seg(20, 70)], merged_online(), MagicMock())
        review.assert_not_called()


class PickerHelperTests(unittest.TestCase):
    def test_format_time_and_source_names(self):
        import skip_source_picker_ui as ui

        self.assertEqual(ui.format_time(65.4), "1:05")
        self.assertEqual(ui.format_time(3725), "1:02:05")
        self.assertEqual(ui.online_names(["theintrodb", "introdb"]), "TheIntroDB + IntroDB.app")


if __name__ == "__main__":
    unittest.main()
