# -*- coding: utf-8 -*-
"""The Up Next integration: next episodes announced by video add-ons (upnext_data)."""

import base64
import json
import os
import types
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import import_fresh, install_kodi_stubs

install_kodi_stubs()

import next_episode_lookup as lookup
import next_episode_play as play
import next_episode_provider as prov
import service_loop_next_episode as step
import service_main_loop
from next_episode_state import (
    LOOKUP_FOUND,
    LOOKUP_IDLE,
    LOOKUP_NONE as lookup_none,
    LOOKUP_RUNNING as lookup_running,
    NextEpisodeState,
)
from tests.test_main_loop_dedup import _Monitor, _Player as _LoopPlayer, _bindings
from tests.test_next_episode import LIBRARY_NEXT, SETTINGS, _Player as _FilePlayer

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

URL = "plugin://plugin.video.foo/?play=12345&token=secret"
INFO = {"item_id": "12345"}


def payload(**extra):
    base = {
        "current_episode": {"episodeid": 1, "title": "One", "season": 1, "episode": 1},
        "next_episode": {
            "episodeid": 2,
            "title": "Two",
            "showtitle": "Show",
            "season": "1",
            "episode": "2",
            "art": {"thumb": "http://img/thumb.jpg", "tvshow.poster": "http://img/poster.jpg"},
        },
        "play_url": URL,
    }
    base.update(extra)
    return base


def encode(data, how="base64"):
    raw = json.dumps(data).encode("utf-8")
    text = base64.b64encode(raw).decode() if how == "base64" else raw.hex()
    return json.dumps([text])


class DecodeTests(unittest.TestCase):
    def test_a_base64_payload_in_a_one_item_list_is_decoded(self):
        self.assertEqual(prov.decode_notification(encode(payload())), payload())

    def test_a_hex_payload_is_decoded_too(self):
        self.assertEqual(prov.decode_notification(encode(payload(), "hex")), payload())

    def test_an_already_decoded_payload_is_accepted(self):
        self.assertEqual(prov.decode_notification(json.dumps([payload()])), payload())
        self.assertEqual(prov.decode_notification([payload()]), payload())

    def test_bytes_are_accepted(self):
        self.assertEqual(prov.decode_notification(encode(payload()).encode()), payload())

    def test_things_that_are_not_announcements_are_refused(self):
        for junk in (
            None,
            "",
            "not json",
            "[]",
            "{}",
            json.dumps([""]),
            json.dumps([5]),
            json.dumps(["!!!"]),
            json.dumps([base64.b64encode(b"not json").decode()]),
            json.dumps([base64.b64encode(b"[1, 2]").decode()]),
            json.dumps(["zz"]),
            5,
        ):
            self.assertIsNone(prov.decode_notification(junk), repr(junk))

    def test_a_huge_payload_is_refused(self):
        too_big = encode(dict(payload(), padding="x" * prov.MAX_ENCODED_CHARS))
        self.assertIsNone(prov.decode_notification(too_big))
        small_enough = encode(dict(payload(), padding="x" * 1000))
        self.assertEqual(prov.decode_notification(small_enough)["play_url"], URL)

    def test_the_sender_names_the_add_on(self):
        self.assertEqual(prov.provider_id("plugin.video.foo.SIGNAL"), "plugin.video.foo")
        self.assertEqual(prov.provider_id(" plugin.video.foo.SIGNAL "), "plugin.video.foo")
        for junk in ("plugin.video.foo", "", None, ".SIGNAL", "x.signal"):
            self.assertEqual(prov.provider_id(junk), "", repr(junk))


class ParseTests(unittest.TestCase):
    def test_the_next_episode_becomes_a_prompt_item(self):
        found = prov.parse_payload("plugin.video.foo", payload())
        self.assertEqual(found.provider, "plugin.video.foo")
        self.assertEqual(
            found.next_item,
            {
                "source": lookup.SOURCE_PROVIDER,
                "provider": "plugin.video.foo",
                "play_url": URL,
                "play_info": None,
                "title": "Two",
                "showtitle": "Show",
                "season": 1,
                "episode": 2,
                "file": "",
                "thumb": "http://img/thumb.jpg",
            },
        )
        self.assertEqual(lookup.episode_label(found.next_item), "S01E02 · Two")

    def test_play_info_alone_is_enough(self):
        data = payload(play_info=INFO)
        del data["play_url"]
        found = prov.parse_payload("plugin.video.foo", data)
        self.assertEqual(found.next_item["play_url"], "")
        self.assertEqual(found.next_item["play_info"], INFO)

    def test_without_a_way_to_start_it_there_is_nothing_to_offer(self):
        for extra in ({"play_url": ""}, {"play_url": "  "}, {"play_url": None}, {"play_url": 5}):
            data = payload(**extra)
            self.assertIsNone(prov.parse_payload("plugin.video.foo", data), extra)

    def test_without_a_next_episode_there_is_nothing_to_offer(self):
        for bad in (None, [], "x", 5):
            self.assertIsNone(prov.parse_payload("p", payload(next_episode=bad)))
        data = payload()
        del data["next_episode"]
        self.assertIsNone(prov.parse_payload("p", data))
        self.assertIsNone(prov.parse_payload("", payload()))
        self.assertIsNone(prov.parse_payload("p", None))
        self.assertIsNone(prov.parse_payload("p", [payload()]))

    def test_odd_episode_numbers_and_titles_are_tolerated(self):
        found = prov.parse_payload(
            "p", payload(next_episode={"title": 5, "season": "x", "episode": -1, "art": "no"})
        )
        item = found.next_item
        self.assertEqual((item["title"], item["season"], item["episode"], item["thumb"]), ("", None, None, ""))
        self.assertEqual(lookup.episode_label(item), "")

    def test_season_zero_is_a_special_not_a_missing_number(self):
        item = prov.parse_payload("p", payload(next_episode={"season": 0, "episode": 3})).next_item
        self.assertEqual((item["season"], item["episode"]), (0, 3))

    def test_timing_comes_from_either_field(self):
        found = prov.parse_payload("p", payload(notification_time=30, notification_offset="1400"))
        self.assertEqual((found.notification_time, found.notification_offset), (30.0, 1400.0))
        for bad in (0, -5, "x", None, True * 0):
            found = prov.parse_payload("p", payload(notification_time=bad, notification_offset=bad))
            self.assertEqual((found.notification_time, found.notification_offset), (None, None), bad)

    def test_the_prompt_start_prefers_the_offset(self):
        both = prov.ProviderData("p", {}, notification_time=30.0, notification_offset=1400.0)
        self.assertEqual(both.prompt_start(1500), 1400.0)
        only_time = prov.ProviderData("p", {}, notification_time=30.0)
        self.assertEqual(only_time.prompt_start(1500), 1470.0)
        self.assertIsNone(only_time.prompt_start(0))
        self.assertIsNone(only_time.prompt_start("x"))
        self.assertIsNone(prov.ProviderData("p", {}).prompt_start(1500))

    def test_stamping_keeps_everything_else(self):
        found = prov.parse_payload("p", payload(notification_time=30))
        stamped = found.stamped("file.mkv", 12.5)
        self.assertEqual((stamped.video, stamped.received_mono), ("file.mkv", 12.5))
        self.assertEqual((stamped.provider, stamped.next_item, stamped.notification_time), ("p", found.next_item, 30.0))
        self.assertEqual(found.video, "")

    def test_the_reply_is_what_up_next_would_send(self):
        text = prov.encode_reply(INFO)
        self.assertEqual(json.loads(base64.b64decode(text)), INFO)
        self.assertEqual(json.loads(base64.b64decode(prov.encode_reply(None))), {})
        self.assertEqual(prov.reply_message("plugin.video.foo"), "plugin.video.foo_play_action")


class PlayTests(unittest.TestCase):
    def item(self, **extra):
        item = prov.parse_payload("plugin.video.foo", payload(play_info=INFO)).next_item
        item.update(extra)
        return item

    def run_play(self, item, response=None):
        calls = []

        def rpc(method, params=None, log_errors=True):
            calls.append((method, params))
            return {"result": "OK"} if response is None else response

        with patch.object(play, "jsonrpc", rpc), patch.object(play, "log_error"):
            ok = play.play_next(item, resume=False)
        return ok, calls

    def test_a_play_url_is_opened_directly(self):
        ok, calls = self.run_play(self.item())
        self.assertTrue(ok)
        self.assertEqual(calls, [("Player.Open", {"item": {"file": URL}})])

    def test_play_info_is_sent_back_to_the_add_on_when_there_is_no_url(self):
        ok, calls = self.run_play(self.item(play_url=""))
        self.assertTrue(ok)
        method, params = calls[0]
        self.assertEqual(method, "JSONRPC.NotifyAll")
        self.assertEqual(params["sender"], "upnextprovider.SIGNAL")
        self.assertEqual(params["message"], "plugin.video.foo_play_action")
        self.assertEqual(json.loads(base64.b64decode(params["data"][0])), INFO)
        self.assertEqual(len(params["data"]), 1)

    def test_a_url_wins_over_play_info(self):
        _ok, calls = self.run_play(self.item())
        self.assertEqual([c[0] for c in calls], ["Player.Open"])

    def test_without_an_add_on_there_is_nobody_to_ask(self):
        ok, calls = self.run_play(self.item(play_url="", provider=""))
        self.assertFalse(ok)
        self.assertEqual(calls, [])

    def test_a_refusal_is_reported_as_a_failure(self):
        ok, _calls = self.run_play(self.item(), {"error": {"message": "no"}})
        self.assertFalse(ok)
        ok, _calls = self.run_play(self.item(), {})
        self.assertFalse(ok)

    def test_library_and_playlist_items_still_play_as_before(self):
        ok, calls = self.run_play({"source": lookup.SOURCE_LIBRARY, "episodeid": 9})
        self.assertTrue(ok)
        self.assertEqual(calls[0][0], "Player.Open")
        self.assertEqual(calls[0][1]["item"], {"episodeid": 9})
        self.assertFalse(self.run_play({"source": "other"})[0])


class _Settings:
    """A stand-in for the add-on settings the loop reads."""

    def __init__(self, **values):
        self.values = dict(SETTINGS, next_episode_use_provider_data=True, **values)

    def get_bool(self, _a, key, default=False):
        return self.values.get(key, default)

    def get_int(self, _a, key, default=0, minimum=None, maximum=None):
        return self.values.get(key, default)


class _PlayerWithFile(_FilePlayer):
    def __init__(self, path, total=1500.0, head=1460.0, playing=True):
        super().__init__(total)
        self.path = path
        self.head = head
        self.playing = playing

    def getPlayingFile(self):
        return self.path

    def getTime(self):
        return self.head

    def isPlaying(self):
        return self.playing


VIDEO = "plugin://plugin.video.foo/?play=12345"


class HandlerBase(unittest.TestCase):
    def setUp(self):
        self.monitor = types.SimpleNamespace(next_episode_state=None)
        self.player = _PlayerWithFile(VIDEO)
        self.ctx = types.SimpleNamespace(monitor=self.monitor, player=self.player)
        self.cfg = _Settings()
        self.answers = []
        self.prompts = []
        self.plays = []
        self.lookups = []
        self.paused = False
        self.now = 1000.0
        self.upnext = False
        stack = [
            patch.object(step, "get_addon", lambda: object()),
            patch.object(step, "addon_get_bool", lambda *a, **k: self.cfg.get_bool(*a, **k)),
            patch.object(step, "addon_get_int", lambda *a, **k: self.cfg.get_int(*a, **k)),
            patch.object(step, "countdown_settings", lambda _a: (0, "Close")),
            patch.object(step, "_upnext_enabled", lambda: self.upnext),
            patch.object(step, "_idle_seconds", lambda: None),
            patch.object(step, "show_next_episode_prompt", self._prompt),
            patch.object(step, "play_next", self._play),
            patch.object(step, "schedule_mark_watched", lambda *a: None),
            patch.object(step, "_start_lookup", lambda *a, **k: self.lookups.append((a, k))),
            patch.object(step.time, "monotonic", lambda: self.now),
            patch.object(step.xbmc, "getCondVisibility", lambda cond: self.paused and cond == "Player.Paused"),
            patch.object(step, "log"),
            patch.object(step, "log_error"),
        ]
        for p in stack:
            p.start()
            self.addCleanup(p.stop)

    def _prompt(self, addon, player, item, start, total, **kwargs):
        self.prompts.append((item, start, total))
        return self.answers.pop(0) if self.answers else None

    def _play(self, item, resume=True):
        self.plays.append(item)
        return True

    def announce(self, video=VIDEO, received=500.0, **extra):
        found = prov.parse_payload("plugin.video.foo", payload(**extra))
        self.monitor.next_episode_provider = found.stamped(video, received)
        return self.monitor.next_episode_provider


class NoteSignalTests(HandlerBase):
    def note(self, sender="plugin.video.foo.SIGNAL", data=None, method="Other.upnext_data"):
        step.note_upnext_data(self.monitor, sender, method, encode(payload()) if data is None else data)

    def test_the_announcement_is_kept_with_the_playing_file_and_the_time(self):
        self.now = 777.0
        with patch.object(step.xbmc, "Player", lambda: self.player):
            self.note()
        kept = self.monitor.next_episode_provider
        self.assertEqual((kept.video, kept.received_mono, kept.provider), (VIDEO, 777.0, "plugin.video.foo"))
        self.assertEqual(kept.next_item["play_url"], URL)

    def test_a_newer_announcement_replaces_the_old_one(self):
        with patch.object(step.xbmc, "Player", lambda: self.player):
            self.note()
            self.now = 900.0
            self.note(data=encode(payload(next_episode={"title": "Three", "season": 1, "episode": 3})))
        self.assertEqual(self.monitor.next_episode_provider.next_item["title"], "Three")

    def test_nothing_is_kept_while_the_feature_is_off(self):
        self.cfg.values["next_episode_enabled"] = False
        with patch.object(step.xbmc, "Player", lambda: self.player):
            self.note()
        self.assertFalse(hasattr(self.monitor, "next_episode_provider"))

    def test_nothing_is_kept_when_add_on_information_is_switched_off(self):
        self.cfg.values["next_episode_use_provider_data"] = False
        with patch.object(step.xbmc, "Player", lambda: self.player):
            self.note()
        self.assertFalse(hasattr(self.monitor, "next_episode_provider"))

    def test_signals_from_unknown_senders_or_with_bad_data_are_ignored(self):
        with patch.object(step.xbmc, "Player", lambda: self.player):
            self.note(sender="plugin.video.foo")
            self.note(data="garbage")
            self.note(data=encode({"next_episode": {"title": "x"}}))
        self.assertFalse(hasattr(self.monitor, "next_episode_provider"))

    def test_nothing_is_kept_when_nothing_is_playing(self):
        quiet = _PlayerWithFile("")
        with patch.object(step.xbmc, "Player", lambda: quiet):
            self.note()
        self.assertFalse(hasattr(self.monitor, "next_episode_provider"))

    def test_a_failing_player_does_not_raise(self):
        def broken():
            raise RuntimeError("no player")

        with patch.object(step.xbmc, "Player", broken):
            self.note()
        self.assertFalse(hasattr(self.monitor, "next_episode_provider"))

    def test_the_url_never_reaches_the_log(self):
        with patch.object(step.xbmc, "Player", lambda: self.player):
            self.note()
        logged = " ".join(str(c) for c in step.log.call_args_list)
        self.assertNotIn("secret", logged)
        self.assertNotIn(URL, logged)


class RemoteTickTests(HandlerBase):
    def tick(self):
        return step.handle_remote_next_episode(self.ctx)

    def test_without_an_announcement_nothing_happens(self):
        self.assertFalse(self.tick().switched)
        self.assertIsNone(self.monitor.next_episode_state)

    def test_an_announcement_for_another_video_is_ignored(self):
        self.announce(video="plugin://other")
        self.tick()
        self.assertIsNone(self.monitor.next_episode_state)

    def test_a_mock_monitor_is_not_mistaken_for_an_announcement(self):
        self.ctx.monitor = MagicMock()
        self.assertFalse(step.handle_remote_next_episode(self.ctx).switched)

    def test_only_a_real_announcement_counts(self):
        self.monitor.next_episode_provider = types.SimpleNamespace(video=VIDEO, received_mono=1.0)
        self.tick()
        self.assertIsNone(self.monitor.next_episode_state)

    def test_nothing_happens_while_paused_or_stopped(self):
        self.announce()
        self.paused = True
        self.tick()
        self.assertIsNone(self.monitor.next_episode_state)
        self.paused = False
        self.player.playing = False
        self.tick()
        self.assertIsNone(self.monitor.next_episode_state)

    def test_the_announced_episode_is_offered_in_the_usual_window(self):
        self.announce()
        self.answers = [None]
        self.tick()
        item, start, total = self.prompts[0]
        self.assertEqual(item["title"], "Two")
        self.assertEqual((start, total), (1455.0, 1500.0))
        state = self.monitor.next_episode_state
        self.assertTrue(state.remote)
        self.assertEqual(state.lookup, LOOKUP_FOUND)
        self.assertEqual(self.lookups, [], "no library lookup for an add-on video")

    def test_before_the_window_nothing_is_shown(self):
        self.announce()
        self.player.head = 600.0
        self.tick()
        self.assertEqual(self.prompts, [])

    def test_play_now_opens_the_announced_episode(self):
        self.announce()
        self.answers = [True]
        result = self.tick()
        self.assertTrue(result.switched)
        self.assertEqual(self.plays[0]["play_url"], URL)

    def test_autoplay_starts_it_without_a_prompt(self):
        self.announce()
        self.cfg.values["next_episode_autoplay"] = True
        self.cfg.values["next_episode_still_watching"] = False
        self.assertTrue(self.tick().switched)
        self.assertEqual(self.prompts, [])
        self.assertEqual(len(self.plays), 1)

    def test_close_keeps_it_away(self):
        self.announce()
        self.answers = [False]
        self.tick()
        self.now += 60
        self.tick()
        self.assertEqual(len(self.prompts), 1)

    def test_the_addons_own_prompt_time_is_used_when_starting_at_the_credits(self):
        self.announce(notification_offset=1400)
        self.cfg.values["next_episode_start_at_credits"] = True
        self.player.head = 1405.0
        self.answers = [None]
        self.tick()
        self.assertEqual(self.prompts[0][1:], (1400.0, 1500.0))

    def test_the_addons_prompt_time_is_ignored_unless_asked_for(self):
        self.announce(notification_offset=1400)
        self.player.head = 1405.0
        self.tick()
        self.assertEqual(self.prompts, [])

    def test_the_addons_time_before_the_end_works_too(self):
        self.announce(notification_time=100)
        self.cfg.values["next_episode_start_at_credits"] = True
        self.player.head = 1405.0
        self.answers = [None]
        self.tick()
        self.assertEqual(self.prompts[0][1:], (1400.0, 1500.0))

    def test_segments_of_an_earlier_video_do_not_move_the_start(self):
        self.announce()
        self.cfg.values["next_episode_start_at_credits"] = True
        self.monitor.current_segments = [
            types.SimpleNamespace(
                start_seconds=1300.0, end_seconds=1500.0, segment_type_label="credits", segment_type="credits"
            )
        ]
        self.answers = [None]
        self.tick()
        self.assertEqual(self.prompts[0][1:], (1455.0, 1500.0))

    def test_the_up_next_add_on_keeps_skippys_prompt_off(self):
        self.announce()
        self.upnext = True
        self.tick()
        self.assertEqual(self.prompts, [])

    def test_switching_the_add_on_information_off_stops_it(self):
        self.announce()
        self.cfg.values["next_episode_use_provider_data"] = False
        self.tick()
        self.assertEqual(self.prompts, [])
        self.assertEqual(self.lookups, [])
        self.assertIsNone(self.monitor.next_episode_state)

    def test_switching_the_whole_feature_off_stops_it(self):
        self.announce()
        self.cfg.values["next_episode_enabled"] = False
        self.tick()
        self.assertEqual(self.prompts, [])
        self.assertIsNone(self.monitor.next_episode_state)

    def test_an_error_is_logged_once_and_never_raised(self):
        self.announce()
        with patch.object(step, "handle_next_episode", side_effect=ValueError("boom")):
            self.tick()
            self.tick()
        self.assertEqual(step.log_error.call_count, 1)


class LocalFileTests(HandlerBase):
    """A file Skippy handles itself: the add-on's answer replaces the library's, the lookup still runs."""

    def setUp(self):
        super().setUp()
        self.video = "smb://nas/shows/Show/s01e01.mkv"
        self.player = _PlayerWithFile(self.video)
        self.ctx.player = self.player

    def tick(self, current_time=1460.0):
        return step.handle_next_episode(
            self.ctx,
            video=self.video,
            playback_type="episode",
            current_time=current_time,
            player_item={"type": "episode", "id": 7},
        )

    def test_the_announcement_replaces_the_library_answer(self):
        state = NextEpisodeState(
            video=self.video, lookup=LOOKUP_FOUND, next_item=LIBRARY_NEXT, current_episode_id=7, current_playcount=1
        )
        self.monitor.next_episode_state = state
        self.announce(video=self.video)
        self.answers = [True]
        self.assertTrue(self.tick().switched)
        self.assertEqual(self.plays[0]["source"], lookup.SOURCE_PROVIDER)
        self.assertFalse(state.remote)

    def test_an_announcement_stands_in_when_the_library_has_no_next_episode(self):
        for lookup_state in (lookup_none, lookup_running):
            self.monitor.next_episode_state = NextEpisodeState(
                video=self.video, lookup=lookup_state, next_item=None
            )
            self.announce(video=self.video)
            self.answers = [None]
            self.prompts.clear()
            self.tick()
            self.assertEqual(self.prompts[0][0]["source"], lookup.SOURCE_PROVIDER, lookup_state)
            self.assertEqual(self.monitor.next_episode_state.lookup, LOOKUP_FOUND)
            self.now += 60

    def test_a_library_file_still_gets_its_lookup(self):
        self.announce(video=self.video)
        self.assertFalse(self.tick().switched)
        self.assertEqual(len(self.lookups), 1)
        state = self.monitor.next_episode_state
        self.assertEqual(state.lookup, LOOKUP_IDLE, "the lookup is under way")
        self.assertEqual(state.next_item["source"], lookup.SOURCE_PROVIDER)

    def test_without_an_announcement_the_library_answer_stays(self):
        state = NextEpisodeState(video=self.video, lookup=LOOKUP_FOUND, next_item=LIBRARY_NEXT)
        self.monitor.next_episode_state = state
        self.answers = [True]
        self.tick()
        self.assertIs(self.plays[0], LIBRARY_NEXT)

    def test_a_late_library_lookup_does_not_overwrite_the_announcement(self):
        state = NextEpisodeState(video=self.video)
        self.monitor.next_episode_state = state
        found = self.announce(video=self.video)
        self.tick()
        with patch.object(step, "describe_current_episode", lambda item: {"id": 7, "playcount": 1}), patch.object(
            step, "find_next_episode", lambda *a, **k: LIBRARY_NEXT
        ):
            step.run_lookup(state, {"type": "episode"}, False)
        self.assertEqual(state.next_item, found.next_item)
        self.assertEqual(state.lookup, LOOKUP_FOUND)
        self.assertEqual((state.current_episode_id, state.current_playcount), (7, 1))

    def test_a_lookup_that_finds_nothing_still_leaves_the_announced_episode(self):
        state = NextEpisodeState(video=self.video)
        self.monitor.next_episode_state = state
        found = self.announce(video=self.video)
        self.tick()
        with patch.object(step, "describe_current_episode", lambda item: {}), patch.object(
            step, "find_next_episode", lambda *a, **k: None
        ):
            step.run_lookup(state, {"type": "episode"}, False)
        self.assertEqual(state.next_item, found.next_item)
        self.assertEqual(state.lookup, LOOKUP_FOUND)

    def test_a_lookup_without_an_announcement_behaves_as_before(self):
        state = NextEpisodeState(video=self.video)
        with patch.object(step, "describe_current_episode", lambda item: {"id": 7}), patch.object(
            step, "find_next_episode", lambda *a, **k: LIBRARY_NEXT
        ):
            step.run_lookup(state, {"type": "episode"}, False)
        self.assertIs(state.next_item, LIBRARY_NEXT)
        self.assertEqual(state.lookup, LOOKUP_FOUND)

    def test_a_newer_announcement_replaces_an_adopted_one(self):
        state = NextEpisodeState(video=self.video, lookup=LOOKUP_FOUND, next_item=LIBRARY_NEXT)
        self.monitor.next_episode_state = state
        first = self.announce(video=self.video, received=500.0)
        self.player.head = 100.0
        self.tick(100.0)
        self.assertEqual(state.next_item, first.next_item)
        second = self.announce(
            video=self.video, received=600.0, next_episode={"title": "Three", "season": 1, "episode": 3}
        )
        self.tick(100.0)
        self.assertEqual(state.next_item, second.next_item)
        # The same announcement again changes nothing.
        state.next_item = "kept"
        self.tick(100.0)
        self.assertEqual(state.next_item, "kept")

    def test_an_announcement_for_another_file_is_not_adopted(self):
        state = NextEpisodeState(video=self.video, lookup=LOOKUP_FOUND, next_item=LIBRARY_NEXT)
        self.monitor.next_episode_state = state
        self.announce(video="smb://nas/other.mkv")
        self.tick(100.0)
        self.assertIs(state.next_item, LIBRARY_NEXT)

    def test_it_is_ignored_when_the_setting_is_off(self):
        self.cfg.values["next_episode_use_provider_data"] = False
        state = NextEpisodeState(video=self.video, lookup=LOOKUP_FOUND, next_item=LIBRARY_NEXT)
        self.monitor.next_episode_state = state
        self.announce(video=self.video)
        self.tick(100.0)
        self.assertIs(state.next_item, LIBRARY_NEXT)

    def test_the_segments_credits_start_comes_before_the_addons_time(self):
        state = NextEpisodeState(video=self.video, lookup=LOOKUP_FOUND, next_item=LIBRARY_NEXT)
        self.monitor.next_episode_state = state
        self.announce(video=self.video, notification_offset=1400)
        self.cfg.values["next_episode_start_at_credits"] = True
        with patch.object(step, "credits_start_seconds", lambda segments, total: 1420.0):
            self.answers = [None]
            self.tick(1425.0)
        self.assertEqual(self.prompts[0][1], 1420.0)

    def test_the_addons_time_is_used_when_there_is_no_credits_segment(self):
        state = NextEpisodeState(video=self.video, lookup=LOOKUP_FOUND, next_item=LIBRARY_NEXT)
        self.monitor.next_episode_state = state
        self.announce(video=self.video, notification_offset=1400)
        self.cfg.values["next_episode_start_at_credits"] = True
        with patch.object(step, "credits_start_seconds", lambda segments, total: None):
            self.answers = [None]
            self.tick(1405.0)
        self.assertEqual(self.prompts[0][1], 1400.0)


class WiringTests(unittest.TestCase):
    def test_the_monitor_hands_the_signal_to_the_next_episode_step(self):
        install_kodi_stubs()
        with patch("service_main_loop.run_service_main_loop", lambda _ctx: None):
            service = import_fresh("service")
        monitor = service.PlayerMonitor.__new__(service.PlayerMonitor)
        with patch.object(step, "note_upnext_data") as seen, patch.object(service, "log_always") as opened:
            monitor.onNotification("plugin.video.foo.SIGNAL", "Other.upnext_data", '["x"]')
        seen.assert_called_once_with(monitor, "plugin.video.foo.SIGNAL", "Other.upnext_data", '["x"]')
        opened.assert_not_called()

    def test_other_notifications_are_not_taken_for_it(self):
        install_kodi_stubs()
        with patch("service_main_loop.run_service_main_loop", lambda _ctx: None):
            service = import_fresh("service")
        monitor = service.PlayerMonitor.__new__(service.PlayerMonitor)
        with patch.object(step, "note_upnext_data") as seen:
            monitor.onNotification("Player", "Player.OnPlay", "{}")
            monitor.onNotification("x", "Other.something_else", "{}")
        seen.assert_not_called()

    def test_the_main_loop_gives_ignored_playback_to_the_add_on_step(self):
        monitor = _Monitor([])
        monitor._aborts = [False, True]
        calls = []
        with patch.object(service_main_loop, "refresh_playback_context", lambda _c: None), patch.object(
            service_main_loop, "handle_remote_next_episode", lambda c: calls.append(c)
        ):
            ctx = _bindings(monitor, _LoopPlayer(10.0))
            service_main_loop.run_service_main_loop(ctx)
        self.assertEqual(calls, [ctx])


class SettingsTests(unittest.TestCase):
    def test_the_switch_is_an_advanced_option_that_is_on_by_default(self):
        tree = ET.parse(os.path.join(ROOT, "resources", "settings.xml"))
        found = {s.get("id"): s for s in tree.getroot().iter("setting")}
        setting = found["next_episode_use_provider_data"]
        self.assertEqual(setting.get("type"), "boolean")
        self.assertEqual(setting.findtext("level"), "2")
        self.assertEqual(setting.findtext("default"), "true")
        self.assertEqual((setting.get("label"), setting.get("help")), ("47126", "47127"))
        deps = [(d.get("setting"), d.text) for d in setting.iter("dependency") if d.get("type") == "visible"]
        self.assertEqual(deps, [("next_episode_enabled", "true")])
        self.assertEqual(step.KEY_USE_PROVIDER_DATA, "next_episode_use_provider_data")


class StringsTests(unittest.TestCase):
    def test_every_pack_has_both_strings(self):
        langs = os.path.join(ROOT, "resources", "language")
        packs = sorted(os.listdir(langs))
        self.assertGreaterEqual(len(packs), 11)
        english = None
        for pack in packs:
            with open(os.path.join(langs, pack, "strings.po"), encoding="utf-8") as handle:
                text = handle.read()
            for sid in (47126, 47127):
                marker = 'msgctxt "#%d"\nmsgid "' % sid
                self.assertIn(marker, text, (pack, sid))
                msgstr = text.split(marker, 1)[1].split('\nmsgstr "', 1)[1].split('"\n', 1)[0]
                self.assertTrue(msgstr.strip(), (pack, sid))
                if pack.endswith("en_gb"):
                    english = english or {}
                    english[sid] = msgstr
                else:
                    self.assertNotEqual(msgstr, (english or {}).get(sid), (pack, sid))
                self.assertNotIn("%", msgstr)


if __name__ == "__main__":
    unittest.main()
