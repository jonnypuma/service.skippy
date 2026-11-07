# -*- coding: utf-8 -*-
"""Native (stock Yes/No) skip dialog."""

import unittest
from unittest.mock import MagicMock, patch

from tests.kodi_stubs import install_kodi_stubs

install_kodi_stubs()


def _segment():
    from segment_item import SegmentItem

    return SegmentItem(10.0, 70.0, "intro", source="xml")


def _loc(_addon, _id, default="", *args):
    return default % args if args else default


def _settings(values):
    return lambda _addon, key, default="": values.get(key, default)


class NativeSkipDialogTests(unittest.TestCase):
    def test_type_detection(self):
        import skip_dialog_native as n

        with patch.object(n, "addon_get_setting_text", _settings({"skip_dialog_type": "Native"})):
            self.assertTrue(n.is_native_skip_dialog(object()))
        with patch.object(n, "addon_get_setting_text", _settings({})):
            self.assertFalse(n.is_native_skip_dialog(object()))
        self.assertFalse(n.is_native_skip_dialog(None))

    def _run(self, answer, values=None):
        import skip_dialog_native as n

        values = dict({"native_use_toast": False}, **(values or {}))
        player = MagicMock()
        player.getTime.return_value = 25.0
        player.isPlaying.return_value = True
        dlg = MagicMock()
        dlg.yesno.return_value = answer
        addon = MagicMock()
        addon.getAddonInfo.return_value = "Skippy"
        with patch.object(n, "addon_get_setting_text", _settings(values)), patch.object(
            n, "addon_get_bool", lambda _a, k, d=False: values.get(k, d)
        ), patch.object(n.xbmcgui, "Dialog", return_value=dlg, create=True), patch.object(
            n, "compute_skip_seek_destination_seconds", return_value=71.0
        ), patch.object(n, "get_localized", _loc), patch.dict(
            n.build_skip_button_label.__globals__, {"get_localized": _loc}
        ):
            result = n.show_native_skip_dialog(addon, _segment(), player)
        return result, dlg

    def test_skip_returns_seek_target(self):
        result, dlg = self._run(True)
        self.assertEqual(result, 71.0)
        args, kwargs = dlg.yesno.call_args
        self.assertEqual(kwargs["autoclose"], 45000)  # 70 - 25 seconds
        self.assertEqual(kwargs["yeslabel"], "Skip Intro (1m0s)")
        self.assertIn("00:45", args[1])

    def test_duration_suffix_toggle(self):
        _r, dlg = self._run(True, {"native_show_duration": False})
        self.assertEqual(dlg.yesno.call_args.kwargs["yeslabel"], "Skip Intro")
        _r, dlg = self._run(True, {"native_skip_format": "Skip"})
        self.assertEqual(dlg.yesno.call_args.kwargs["yeslabel"], "Skip (1m0s)")
        _r, dlg = self._run(True, {"native_skip_format": "Skip", "native_show_duration": False})
        self.assertEqual(dlg.yesno.call_args.kwargs["yeslabel"], "Skip")

    def test_dismiss_returns_false(self):
        result, _dlg = self._run(False)
        self.assertIs(result, False)

    def test_auto_close_off_omits_autoclose(self):
        _result, dlg = self._run(False, {"native_auto_close": False})
        self.assertNotIn("autoclose", dlg.yesno.call_args.kwargs)

    def test_falls_back_when_defaultbutton_unsupported(self):
        import skip_dialog_native as n

        player = MagicMock()
        player.getTime.return_value = 25.0
        dlg = MagicMock()
        dlg.yesno.side_effect = [TypeError("defaultbutton"), True]
        addon = MagicMock()
        addon.getAddonInfo.return_value = "Skippy"
        with patch.object(n, "addon_get_setting_text", _settings({})), patch.object(
            n, "addon_get_bool", lambda _a, k, d=False: False if k == "native_use_toast" else d
        ), patch.object(n.xbmcgui, "Dialog", return_value=dlg, create=True), patch.object(
            n, "compute_skip_seek_destination_seconds", return_value=71.0
        ), patch.object(n, "get_localized", _loc), patch.dict(
            n.build_skip_button_label.__globals__, {"get_localized": _loc}
        ):
            self.assertEqual(n.show_native_skip_dialog(addon, _segment(), player), 71.0)
        self.assertEqual(dlg.yesno.call_count, 2)


class ToastTests(unittest.TestCase):
    def _player(self, head, playing=True):
        p = MagicMock()
        p.getTime.return_value = head
        p.isPlaying.return_value = playing
        return p

    def _run_keepalive(self, visibility, head=25.0, playing=True):
        import threading
        import skip_dialog_native as n

        posts, closed = [], []
        stop = threading.Event()
        seq = iter(visibility)
        clock = iter(range(0, 1000))
        with patch.object(n, "_WATCH_INTERVAL_S", 0.0), patch.object(
            n, "_TOAST_FIRST_CHECK_S", 0.5
        ), patch.object(n, "_TOAST_REPOST_GAP_S", 0.5), patch.object(
            n.time, "time", lambda: float(next(clock))
        ), patch.object(
            n, "_toast_visible", lambda: next(seq, True)
        ):
            def close():
                closed.append(1)
                stop.set()

            # stop after the visibility script is exhausted
            orig = n._toast_visible
            def vis():
                v = next(seq, None)
                if v is None:
                    stop.set()
                    return True
                return v
            with patch.object(n, "_toast_visible", vis):
                n._toast_keepalive(
                    self._player(head, playing), _segment(), posts.append, close, stop
                )
        return posts, closed

    def test_reposts_when_toast_vanishes_after_being_seen(self):
        posts, _ = self._run_keepalive([True, False, True])
        self.assertEqual(len(posts), 1)
        self.assertGreaterEqual(posts[0], 1500)
        self.assertLessEqual(posts[0], 45000)

    def test_no_reposts_when_visibility_never_detected(self):
        posts, _ = self._run_keepalive([False, False, False, False])
        self.assertEqual(posts, [])

    def test_closes_key_catcher_when_segment_ends(self):
        _posts, closed = self._run_keepalive([True], head=70.0)
        self.assertEqual(closed, [1])

    def test_closes_key_catcher_when_playback_stops(self):
        _posts, closed = self._run_keepalive([True], playing=False)
        self.assertEqual(closed, [1])

    def test_ok_skips_back_dismisses(self):
        import skip_dialog_native as n

        dlg = n.SkipToastKeys.__new__(n.SkipToastKeys)
        dlg.result, dlg._done, dlg.close = None, False, MagicMock()
        act = MagicMock()
        act.getId.return_value = n._ACTION_SELECT
        dlg.onAction(act)
        dlg.onClick(3012)  # second event is ignored
        self.assertIs(dlg.result, True)
        dlg.close.assert_called_once()
        dlg2 = n.SkipToastKeys.__new__(n.SkipToastKeys)
        dlg2.result, dlg2._done, dlg2.close = None, False, MagicMock()
        act.getId.return_value = 92
        dlg2.onAction(act)
        self.assertIs(dlg2.result, False)


class _Label:
    """A fade label of the toast window that records being reset."""

    def __init__(self, resets, control_id):
        self._resets = resets
        self._id = control_id

    def reset(self):
        self._resets.append(self._id)


class ToastWindowRecoveryTests(unittest.TestCase):
    """Kodi shows no toast after one was closed while its text still scrolled, unless the labels are reset."""

    def _window(self, controls):
        asked = []

        class _Win:
            def __init__(self, window_id):
                asked.append(window_id)

            def getControl(self, control_id):
                if control_id not in controls:
                    raise RuntimeError("no such control")
                return controls[control_id]

        return _Win, asked

    def test_both_fade_labels_of_the_toast_window_are_reset(self):
        import skip_dialog_native as n

        resets = []
        win, asked = self._window({401: _Label(resets, 401), 402: _Label(resets, 402)})
        with patch.object(n.xbmcgui, "Window", win):
            self.assertTrue(n.unstick_toast())
        self.assertEqual(asked, [10107])
        self.assertEqual(resets, [401, 402])

    def test_a_window_that_cannot_be_reached_is_not_an_error(self):
        import skip_dialog_native as n

        def boom(_window_id):
            raise RuntimeError("no such window")

        with patch.object(n.xbmcgui, "Window", boom):
            self.assertFalse(n.unstick_toast())

    def test_a_skin_without_fade_labels_is_left_alone(self):
        import skip_dialog_native as n

        resets = []
        win, _asked = self._window({401: object(), 402: _Label(resets, 402)})
        with patch.object(n.xbmcgui, "Window", win):
            self.assertTrue(n.unstick_toast())
        self.assertEqual(resets, [402])
        win, _asked = self._window({})
        with patch.object(n.xbmcgui, "Window", win):
            self.assertFalse(n.unstick_toast())

    def test_dismissing_a_toast_closes_it_and_then_clears_the_window(self):
        import skip_dialog_native as n

        order = []
        with patch.object(
            n.xbmc, "executebuiltin", lambda cmd: order.append(cmd), create=True
        ), patch.object(n, "unstick_toast", lambda: order.append("unstick")):
            n._dismiss_toast()
        self.assertEqual(
            order,
            ["Dialog.Close(notification,true)", "Dialog.Close(10107,true)", "unstick"],
        )

    def test_a_toast_on_screen_is_not_touched_before_posting(self):
        import skip_dialog_native as n

        called = []
        with patch.object(n, "_toast_visible", lambda: True), patch.object(
            n, "unstick_toast", lambda: called.append(1) or True
        ):
            self.assertFalse(n.ready_toast_window())
        self.assertEqual(called, [])

    def test_the_window_is_cleared_before_posting_when_no_toast_shows(self):
        import skip_dialog_native as n

        called = []
        with patch.object(n, "_toast_visible", lambda: False), patch.object(
            n, "unstick_toast", lambda: called.append(1) or True
        ):
            self.assertTrue(n.ready_toast_window())
        self.assertEqual(called, [1])

    def test_the_skip_toast_clears_the_window_before_it_is_posted(self):
        import skip_dialog_native as n

        order = []
        dialog = MagicMock()
        dialog.notification = lambda *a: order.append("post")

        class _Keys:
            def __init__(self, *args):
                self.result = None

            def doModal(self):
                pass

            def close(self):
                pass

        addon = MagicMock()
        addon.getAddonInfo.return_value = "icon.png"
        values = {"skip_dialog_type": "Native", "native_use_toast": True}
        with patch.object(n, "addon_get_setting_text", _settings(values)), patch.object(
            n, "addon_get_bool", lambda _a, k, d=False: values.get(k, d)
        ), patch.object(n, "get_localized", _loc), patch.dict(
            n.build_skip_button_label.__globals__, {"get_localized": _loc}
        ), patch.object(n, "SkipToastKeys", _Keys), patch.object(
            n, "_toast_keepalive", lambda *a, **k: None
        ), patch.object(n, "_dismiss_toast"), patch.object(
            n, "ready_toast_window", lambda: order.append("ready")
        ), patch.object(n.xbmcgui, "Dialog", lambda: dialog):
            n.show_toast_skip_dialog(addon, _segment(), self._player(25.0))
        self.assertEqual(order, ["ready", "post"])

    def _player(self, head):
        p = MagicMock()
        p.getTime.return_value = head
        p.isPlaying.return_value = True
        return p


if __name__ == "__main__":
    unittest.main()
