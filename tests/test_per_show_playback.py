# -*- coding: utf-8 -*-
"""The per-title auto-skip choice during playback: when it applies and when it is asked for."""

import types
import unittest
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()

import service_loop_per_show as per_show  # noqa: E402
from segment_item import SegmentItem  # noqa: E402


class _PerShowTest(unittest.TestCase):
    def setUp(self):
        self.saved = {}
        self.enabled = True
        self.identity = {"type": "episode", "tmdb_id": 1396, "title": "Breaking Bad"}
        self.lookups = []
        self.monitor = types.SimpleNamespace(per_show_override_identity=None, skip_dialog_modal_active=False)
        stack = [
            patch.object(per_show, "per_show_override_enabled", lambda _a: self.enabled),
            patch.object(per_show, "get_player_snapshot", lambda _m: None),
            patch.object(per_show, "snapshot_matches_path", lambda _s, _p: False),
            patch.object(per_show, "get_enriched_item_for_path", self._item),
            patch.object(per_show, "library_title_identity", lambda item: self.identity),
            patch.object(per_show, "lookup_override", lambda key, label: self.saved.get((key, label))),
            patch.object(per_show, "save_override", self._save),
            patch.object(per_show, "log"),
            patch.object(per_show, "_log_detail"),
        ]
        for p in stack:
            p.start()
            self.addCleanup(p.stop)

    def _item(self, path, snapshot=None):
        self.lookups.append(path)
        return {"file": path}

    def _save(self, key, label, mode, title=""):
        self.saved[(key, label)] = mode


class ApplyTests(_PerShowTest):
    def test_a_saved_choice_turns_ask_into_auto(self):
        key = per_show.override_key_for_identity(self.identity)
        self.saved[(key, "intro")] = per_show.MODE_AUTO
        self.assertEqual(per_show.apply_per_show_override(self.monitor, None, "/v.mkv", "intro", "ask"), "auto")
        self.assertEqual(per_show.apply_per_show_override(self.monitor, None, "/v.mkv", "recap", "ask"), "ask")

    def test_other_modes_and_a_declined_choice_stay_as_they_are(self):
        key = per_show.override_key_for_identity(self.identity)
        self.saved[(key, "intro")] = per_show.MODE_DECLINED
        self.assertEqual(per_show.apply_per_show_override(self.monitor, None, "/v.mkv", "intro", "ask"), "ask")
        self.saved[(key, "intro")] = per_show.MODE_AUTO
        self.assertEqual(per_show.apply_per_show_override(self.monitor, None, "/v.mkv", "intro", "never"), "never")
        self.enabled = False
        self.assertEqual(per_show.apply_per_show_override(self.monitor, None, "/v.mkv", "intro", "ask"), "ask")

    def test_the_title_is_looked_up_once_per_video(self):
        for _ in range(3):
            per_show.playback_override_identity(self.monitor, "/v.mkv")
        per_show.playback_override_identity(self.monitor, "/w.mkv")
        self.assertEqual(self.lookups, ["/v.mkv", "/w.mkv"])
        per_show.clear_playback_override_key(self.monitor)
        self.assertIsNone(self.monitor.per_show_override_identity)

    def test_a_title_without_ids_has_no_choice(self):
        self.identity = {"type": "episode", "tmdb_id": None, "imdb_id": None, "title": "Home video"}
        self.assertEqual(per_show.playback_override_identity(self.monitor, "/v.mkv"), (None, "Home video"))
        self.assertEqual(per_show.apply_per_show_override(self.monitor, None, "/v.mkv", "intro", "ask"), "ask")


class PromptTests(_PerShowTest):
    def setUp(self):
        super().setUp()
        self.answers = []
        self.questions = []
        self.player = MagicMock()
        self.player.isPlayingVideo.return_value = True
        self.ctx = types.SimpleNamespace(monitor=self.monitor, player=self.player, icon_path="")
        stack = [
            patch.object(per_show, "sidecar_overwrite_yesno_show", self._ask),
            patch.object(per_show, "get_localized", lambda _a, _i, default="", *args: default % args if args else default),
            patch.object(per_show.xbmcgui, "Dialog", MagicMock()),
        ]
        for p in stack:
            p.start()
            self.addCleanup(p.stop)

    def _ask(self, heading, message, yes, no):
        self.questions.append(message)
        self.assertTrue(self.monitor.skip_dialog_modal_active)  # nothing else may open meanwhile
        return self.answers.pop(0)

    def prompt(self, label="intro"):
        per_show.maybe_prompt_per_show_override(self.ctx, None, SegmentItem(10, 60, label), "/v.mkv")

    def test_yes_saves_auto_and_the_question_is_not_asked_again(self):
        self.answers = [True]
        self.prompt()
        self.prompt()
        key = per_show.override_key_for_identity(self.identity)
        self.assertEqual(self.saved, {(key, "intro"): per_show.MODE_AUTO})
        self.assertEqual(self.questions, ["Automatically skip Intro for Breaking Bad from now on?"])
        self.assertFalse(self.monitor.skip_dialog_modal_active)

    def test_not_now_is_remembered_too(self):
        self.answers = [False]
        self.prompt()
        self.prompt()
        key = per_show.override_key_for_identity(self.identity)
        self.assertEqual(self.saved, {(key, "intro"): per_show.MODE_DECLINED})
        self.assertEqual(len(self.questions), 1)

    def test_no_question_when_playback_stopped_or_the_feature_is_off(self):
        self.player.isPlayingVideo.return_value = False
        self.prompt()
        self.player.isPlayingVideo.return_value = True
        self.enabled = False
        self.prompt()
        self.assertEqual(self.questions, [])

    def test_a_broken_panel_falls_back_to_kodis_dialog(self):
        def broken(*_a):
            raise RuntimeError("no skin file")

        with patch.object(per_show, "sidecar_overwrite_yesno_show", broken):
            dialog = MagicMock()
            dialog.yesno.return_value = True
            with patch.object(per_show.xbmcgui, "Dialog", return_value=dialog):
                self.prompt()
        key = per_show.override_key_for_identity(self.identity)
        self.assertEqual(self.saved[(key, "intro")], per_show.MODE_AUTO)
        self.assertFalse(self.monitor.skip_dialog_modal_active)


if __name__ == "__main__":
    unittest.main()
