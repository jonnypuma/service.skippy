# -*- coding: utf-8 -*-
"""Keeps "Show the prompt for" within "Seconds before the end".

The prompt appears that many seconds before the end of the episode, so it cannot stay up longer
than that. Kodi's settings cannot limit one number by another, so the service checks the pair
whenever a setting changes and lowers the prompt time when it is too long, with a toast that
says so.

With **Start at the credits** on the window is not known in advance (the credits can start long
before the usual time), so nothing is limited then. A prompt time that is longer than what is
left when the prompt appears is never a problem anyway: the prompt then stays up until the
episode ends (see ``next_episode_state.popup_span``).
"""

from __future__ import annotations

from next_episode_state import KEY_POPUP_DURATION, MAX_POPUP_DURATION_S

KEY_LEAD = "next_episode_lead_seconds"
KEY_CREDITS = "next_episode_start_at_credits"
KEY_ENABLED = "next_episode_enabled"
DEFAULT_LEAD_S = 45
MIN_LEAD_S = 10
MAX_LEAD_S = 300

TOAST_ID = 47144
TOAST_DEFAULT = "Show the prompt for was lowered to %s seconds: it cannot be longer than Seconds before the end."


def allowed_popup_duration(duration, lead_seconds, credits_on) -> int:
    """The prompt time to keep: 0 (until the episode ends) stays, and with the credits start on
    nothing is limited; otherwise it is at most the lead time."""
    try:
        length = int(duration)
        lead = int(lead_seconds)
    except (TypeError, ValueError):
        return 0
    if length <= 0:
        return 0
    length = min(length, MAX_POPUP_DURATION_S)
    if credits_on:
        return length
    return min(length, max(lead, 0))


def enforce_popup_duration_limit(addon=None):
    """Lower the stored prompt time when it is longer than the lead time. Returns the new value,
    or None when nothing had to change."""
    from settings_utils import (
        addon_get_bool,
        addon_get_int,
        get_addon,
        get_localized,
        invalidate_settings_cache,
        notify_skippy,
    )

    invalidate_settings_cache()
    addon = get_addon() if addon is None else addon
    if addon is None or not addon_get_bool(addon, KEY_ENABLED, False):
        return None
    duration = addon_get_int(addon, KEY_POPUP_DURATION, 0, minimum=0, maximum=MAX_POPUP_DURATION_S)
    if duration <= 0:
        return None
    lead = addon_get_int(addon, KEY_LEAD, DEFAULT_LEAD_S, minimum=MIN_LEAD_S, maximum=MAX_LEAD_S)
    allowed = allowed_popup_duration(duration, lead, addon_get_bool(addon, KEY_CREDITS, False))
    if allowed == duration:
        return None
    addon.setSetting(KEY_POPUP_DURATION, str(allowed))
    notify_skippy(
        addon, get_localized(addon, TOAST_ID, TOAST_DEFAULT, allowed), prefer_builtin=True
    )
    return allowed
