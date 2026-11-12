# -*- coding: utf-8 -*-
"""Offering to upload local segment types that the online databases do not have yet."""

import types
import unittest
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import service_local_to_online_sync as sync  # noqa: E402
from segment_item import SegmentItem  # noqa: E402


class _Addon:
    def __init__(self, **settings):
        self.settings = {
            "online_upload_enabled": "true",
            "sync_local_to_online": "Ask",
            "online_upload_default_target": "Both",
            "online_upload_theintrodb_api_key": "tidb-key",
            "online_upload_introdb_api_key": "",
        }
        self.settings.update(settings)

    def getSetting(self, key):
        return self.settings.get(key, "")

    def getSettingString(self, key):
        return self.settings.get(key, "")

    def getLocalizedString(self, _string_id):
        return ""


def _local():
    return [
        SegmentItem(300, 330, "recap"),
        SegmentItem(12, 62, "intro"),
        SegmentItem(5, 40, "recap"),
        SegmentItem(1300, 1380, "credits"),
    ]


class PolicyTests(unittest.TestCase):
    def test_the_setting_and_its_spellings(self):
        for raw, expected in (("Ask", "Ask"), ("Off", "Off"), ("ask", "Ask"), (" OFF ", "Off"), ("junk", "Off"), ("", "Off")):
            self.assertEqual(sync.sync_local_to_online_policy(_Addon(sync_local_to_online=raw)), expected, raw)

    def test_it_needs_uploads_turned_on(self):
        self.assertTrue(sync.sync_local_to_online_enabled(_Addon()))
        self.assertFalse(sync.sync_local_to_online_enabled(_Addon(online_upload_enabled="false")))
        self.assertFalse(sync.sync_local_to_online_enabled(_Addon(sync_local_to_online="Off")))
        self.assertFalse(sync.sync_local_to_online_enabled(None))

    def test_an_unknown_target_falls_back_to_both(self):
        self.assertEqual(sync._upload_target_from_settings(_Addon(online_upload_default_target="TheIntroDB")), "TheIntroDB")
        self.assertEqual(sync._upload_target_from_settings(_Addon(online_upload_default_target="nope")), "Both")


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.pending = set()
        stack = [
            patch.object(sync, "get_enriched_item_for_path", lambda _p: {"type": "episode"}),
            patch.object(sync, "build_upload_context", lambda item: {"type": "tv", "tmdb_id": 1}),
            patch.object(sync, "_media_key", lambda ctx: "tv:1"),
            patch.object(
                sync,
                "segment_has_pending_upload",
                lambda seg, *_a: seg.segment_type_label in self.pending or not self.pending,
            ),
        ]
        for p in stack:
            p.start()
            self.addCleanup(p.stop)

    def test_only_types_missing_online_are_offered_one_each_earliest_first(self):
        remote = [SegmentItem(10, 60, "intro", source="theintrodb")]
        found = sync.compute_local_to_online_upload_candidates("/v.mkv", _local(), remote, _Addon())
        self.assertEqual(
            [(s.segment_type_label, s.start_seconds) for s in found], [("credits", 1300.0), ("recap", 5.0)]
        )

    def test_types_already_uploaded_are_left_out(self):
        self.pending = {"credits"}
        found = sync.compute_local_to_online_upload_candidates("/v.mkv", _local(), [], _Addon())
        self.assertEqual([s.segment_type_label for s in found], ["credits"])

    def test_nothing_without_local_segments_or_a_library_entry(self):
        self.assertEqual(sync.compute_local_to_online_upload_candidates("/v.mkv", [], [], _Addon()), [])
        with patch.object(sync, "build_upload_context", lambda item: None):
            self.assertEqual(sync.compute_local_to_online_upload_candidates("/v.mkv", _local(), [], _Addon()), [])


class PromptTests(unittest.TestCase):
    def setUp(self):
        self.addon = _Addon()
        self.monitor = types.SimpleNamespace(skip_dialog_modal_active=False, local_to_online_sync_suppressed_path=None)
        self.answer = True
        self.uploads = []
        self.asked = []
        stack = [
            patch.object(sync, "get_addon", lambda: self.addon),
            patch.object(sync, "_playback_allows_sync_prompt", lambda _m: True),
            patch.object(
                sync,
                "compute_local_to_online_upload_candidates",
                lambda *_a: [SegmentItem(1300, 1380, "credits")],
            ),
            patch.object(sync, "_sync_yesno", self._yesno),
            patch.object(sync, "upload_segments_subset", lambda *a, **k: self.uploads.append((a, k))),
        ]
        for p in stack:
            p.start()
            self.addCleanup(p.stop)

    def _yesno(self, heading, body):
        self.asked.append((heading, body))
        return self.answer

    def prompt(self):
        sync.maybe_prompt_sync_local_to_online("/v.mkv", "episode", _local(), [], self.monitor)

    def test_yes_uploads_to_the_default_target_and_asks_once(self):
        self.prompt()
        self.assertEqual(len(self.uploads), 1)
        args, kwargs = self.uploads[0]
        self.assertEqual(args[0], "/v.mkv")
        self.assertEqual(args[2], "Both")
        self.assertEqual(kwargs, {"show_empty_message": False, "show_result": True})
        heading, body = self.asked[0]
        self.assertEqual(heading, "Sync local segments to online?")
        self.assertIn("credits", body)
        self.assertIn("No online segment data was found for this title.", body)
        self.prompt()
        self.assertEqual(len(self.asked), 1)

    def test_no_uploads_nothing_but_still_settles_the_file(self):
        self.answer = False
        self.prompt()
        self.assertEqual(self.uploads, [])
        self.assertEqual(self.monitor.local_to_online_sync_suppressed_path, "/v.mkv")

    def test_no_key_for_the_chosen_target_means_no_question(self):
        self.addon.settings["online_upload_default_target"] = "IntroDBApp"
        self.prompt()
        self.assertEqual(self.asked, [])

    def test_turned_off_or_busy_means_no_question(self):
        self.addon.settings["sync_local_to_online"] = "Off"
        self.prompt()
        self.addon.settings["sync_local_to_online"] = "Ask"
        with patch.object(sync, "_playback_allows_sync_prompt", lambda _m: False):
            self.prompt()
        self.assertEqual(self.asked, [])

    def test_the_body_says_what_is_online_already(self):
        body = sync._format_sync_prompt_body([SegmentItem(5, 40, "recap")], [SegmentItem(10, 60, "intro")])
        self.assertIn("Some segment types from your local sidecar are not online yet.", body)
        self.assertIn("recap", body)
        self.assertTrue(body.endswith("Upload these using your default upload target?"))


class GuardTests(unittest.TestCase):
    def test_no_prompt_while_a_skip_dialog_or_the_editor_is_open(self):
        player = MagicMock()
        player.isPlayingVideo.return_value = True
        window = MagicMock()
        window.getProperty.return_value = ""
        with patch.object(sync.xbmc, "Player", return_value=player), patch.object(
            sync.xbmcgui, "Window", return_value=window, create=True
        ):
            self.assertTrue(sync._playback_allows_sync_prompt(types.SimpleNamespace(skip_dialog_modal_active=False)))
            self.assertFalse(sync._playback_allows_sync_prompt(types.SimpleNamespace(skip_dialog_modal_active=True)))
            window.getProperty.return_value = "true"
            self.assertFalse(sync._playback_allows_sync_prompt(None))
            player.isPlayingVideo.return_value = False
            window.getProperty.return_value = ""
            self.assertFalse(sync._playback_allows_sync_prompt(None))


if __name__ == "__main__":
    unittest.main()
