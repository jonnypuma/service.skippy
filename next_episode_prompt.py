# -*- coding: utf-8 -*-
"""Pick the popup style (custom dialog or native toast) and show the next episode prompt."""

from __future__ import annotations

import traceback

from next_episode_appearance import KEY_STYLE, STYLE_CUSTOM, is_native_style, load_popup_draft
from next_episode_state import END_CLOSE
from next_episode_toast import show_next_episode_toast
from settings_utils import addon_get_setting_text, log_error


def popup_is_native(addon) -> bool:
    return is_native_style(addon_get_setting_text(addon, KEY_STYLE, STYLE_CUSTOM))


def show_next_episode_prompt(
    addon,
    player,
    next_episode,
    window_start,
    total,
    *,
    still_watching=False,
    timed=False,
    end_action=END_CLOSE,
):
    """
    Show the prompt the user picked and wait for the answer.

    ``window_start`` and ``total`` bound the countdown: it runs from one to the other, which
    is the end of the file unless the prompt is ``timed`` to stay up for a fixed time.
    ``end_action`` is what the caller does when the countdown runs out unanswered.

    Returns True (play now / continue), False (dismissed / stop), ``TIMED_OUT`` (a timed
    countdown, or one whose end action is Play, ran out) or None (it closed by itself).
    ``still_watching`` turns it into the "Still watching?" question. A custom dialog that
    cannot be built falls back to the native toast, so the prompt still shows.
    """
    if not popup_is_native(addon):
        try:
            from next_episode_dialog import show_next_episode_dialog

            return show_next_episode_dialog(
                addon,
                player,
                next_episode,
                window_start,
                total,
                draft=load_popup_draft(addon),
                still_watching=still_watching,
                timed=timed,
                end_action=end_action,
            )
        except Exception as exc:
            log_error(
                "Next episode popup failed, using the toast instead (%s: %s)\n%s"
                % (type(exc).__name__, exc, traceback.format_exc())
            )
    return show_next_episode_toast(
        addon,
        player,
        next_episode,
        window_start,
        total,
        still_watching=still_watching,
        timed=timed,
        end_action=end_action,
    )
