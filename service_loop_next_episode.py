# -*- coding: utf-8 -*-
"""Main-loop step for the next episode prompt / autoplay."""

from __future__ import annotations

import threading
import time
import traceback
from dataclasses import dataclass
from typing import Any

import xbmc

from next_episode_credits import credits_start_seconds
from next_episode_guard import (
    WatchChain,
    begin_episode,
    ended_on_its_own,
    evaluate,
    start_stop_watchdog,
)
from next_episode_lookup import (
    KIND_EPISODE,
    KIND_MOVIE,
    describe_current_episode,
    describe_current_movie,
    episode_label,
    find_next_episode,
    is_movie_playback,
)
from next_episode_play import play_next, schedule_mark_watched
from next_episode_provider import (
    ProviderData,
    decode_notification,
    parse_payload,
    provider_id,
)
from next_episode_state import (
    END_CLOSE,
    END_PLAY,
    LOOKUP_FOUND,
    LOOKUP_IDLE,
    LOOKUP_NONE,
    LOOKUP_RUNNING,
    MIN_REPROMPT_S,
    TIMED_OUT,
    NextEpisodeState,
    in_prompt_window,
    popup_span,
    rearm_if_before_window,
    reset_guard,
    window_start,
)
from next_episode_prompt import show_next_episode_prompt
from next_episode_view import countdown_settings
from next_episode_shows import (
    lookup_mode,
    never_offer,
    per_show_autoplay_enabled,
    resolve_autoplay,
    show_key_for_identity,
)
from settings_utils import (
    addon_get_bool,
    addon_get_int,
    get_addon,
    get_localized,
    log,
    log_error,
    notify_skippy,
)

UPNEXT_ADDON_ID = "service.upnext"
KEY_USE_PROVIDER_DATA = "next_episode_use_provider_data"
# Whether a movie that belongs to a Kodi collection offers the next movie of the collection.
KEY_MOVIES = "next_episode_movies"

# The "always play this show automatically?" question comes this far into the episode
# the user just started with Play now, and is dropped when no episode starts within
# REMEMBER_EXPIRES_S.
REMEMBER_DELAY_S = 8.0
REMEMBER_EXPIRES_S = 180.0


@dataclass(frozen=True)
class NextEpisodeTick:
    """What the main loop must do after the next episode step."""

    hide_skip_dialogs: bool = False
    switched: bool = False


IDLE_TICK = NextEpisodeTick()


def handle_next_episode(
    ctx: Any, *, video, playback_type, current_time, player_item, remote=False
) -> NextEpisodeTick:
    """Never raises: a failure here must not take the skip dialogs down with it."""
    try:
        return _handle(
            ctx,
            video=video,
            playback_type=playback_type,
            current_time=current_time,
            player_item=player_item,
            remote=remote,
        )
    except Exception as exc:
        signature = "%s: %s" % (type(exc).__name__, exc)
        if signature != getattr(ctx.monitor, "_next_episode_error", None):
            ctx.monitor._next_episode_error = signature
            log_error(
                "Next episode step failed (%s)\n%s" % (signature, traceback.format_exc())
            )
        return IDLE_TICK


def _handle(
    ctx, *, video, playback_type, current_time, player_item, remote=False
) -> NextEpisodeTick:
    monitor = ctx.monitor
    addon = get_addon()
    if not addon or not addon_get_bool(addon, "next_episode_enabled", False):
        return IDLE_TICK
    if not video:
        return IDLE_TICK
    if playback_type == "movie":
        if not addon_get_bool(addon, KEY_MOVIES, True):
            return IDLE_TICK
    elif playback_type != "episode":
        return IDLE_TICK
    if _upnext_enabled():
        _note_upnext(monitor, addon)
        return IDLE_TICK

    state = _state_for(monitor, video)
    state.remote = bool(remote)
    per_show = per_show_autoplay_enabled(addon)
    _maybe_ask_remember(ctx, monitor, addon, video, current_time, per_show)
    _adopt_provider_data(monitor, state, video, addon)
    if state.lookup == LOOKUP_IDLE:
        _start_lookup(
            state,
            player_item,
            skip_watched=addon_get_bool(addon, "next_episode_skip_watched", False),
            resolve_show=per_show,
        )
        return IDLE_TICK
    if state.lookup != LOOKUP_FOUND:
        return IDLE_TICK

    total = _total_time(ctx.player)
    _note_progress(state, current_time, total)
    lead = addon_get_int(addon, "next_episode_lead_seconds", 45, minimum=10, maximum=300)
    credits = _credits_start(monitor, addon, total, state)
    if rearm_if_before_window(state, current_time, total, lead, credits):
        log("Next episode: playhead is before the window again - prompt re-armed")
    if not in_prompt_window(current_time, total, lead, credits):
        return IDLE_TICK

    show_mode = lookup_mode(state.show_key) if per_show and state.show_key else None
    if never_offer(per_show, show_mode):
        # A show set to "Never offer": no prompt, no automatic start, and the skip dialogs
        # keep working as usual.
        return IDLE_TICK

    hide = addon_get_bool(addon, "next_episode_hide_skip_dialogs", True)
    held = NextEpisodeTick(hide_skip_dialogs=hide)
    if state.started or state.dismissed or state.failed:
        return held

    autoplay = resolve_autoplay(
        addon_get_bool(addon, "next_episode_autoplay", False), per_show, show_mode
    )
    # The question does not depend on automatic play: it counts the episodes that went on without
    # a button press, whoever started them (Skippy, Kodi's own play next video, a playlist).
    ask_still_watching = _still_watching_due(monitor, state, addon)
    if autoplay and not ask_still_watching:
        return NextEpisodeTick(
            hide_skip_dialogs=hide,
            switched=_start_next(monitor, state, addon, autoplayed=True),
        )

    now = time.monotonic()
    if now - state.last_prompt_mono < MIN_REPROMPT_S:
        return held
    state.last_prompt_mono = now
    start = window_start(total, lead, credits)
    if ask_still_watching:
        _arm_stop_watchdog(ctx, state, start, total)
    # The "still watching?" question always runs to the end of the file: a timeout must never
    # stand in for an answer to it.
    duration, action = (0, END_CLOSE) if ask_still_watching else countdown_settings(addon)
    begin, end, timed = popup_span(start, current_time, total, duration)
    answer = show_next_episode_prompt(
        addon,
        ctx.player,
        state.next_item,
        begin,
        end,
        still_watching=ask_still_watching,
        timed=timed,
        end_action=action,
    )
    if answer == TIMED_OUT:
        if action == END_PLAY:
            log("Next episode: countdown ran out - playing it")
            return NextEpisodeTick(
                hide_skip_dialogs=hide,
                switched=_start_next(monitor, state, addon, autoplayed=True),
            )
        state.dismissed = True
        log("Next episode: countdown ran out - prompt closed")
        return held
    if answer is True:
        state.answered = True
        if ask_still_watching:
            _stand_down_watchdog(state)
        switched = _start_next(monitor, state, addon)
        if switched and per_show and show_mode is None and not autoplay and not ask_still_watching:
            _queue_remember(monitor, state)
        return NextEpisodeTick(hide_skip_dialogs=hide, switched=switched)
    if answer is False:
        state.answered = True
        state.dismissed = True
        log("Next episode: prompt dismissed")
    return held


def _use_provider_data(addon) -> bool:
    return addon_get_bool(addon, KEY_USE_PROVIDER_DATA, True)


def _adopt_provider_data(monitor, state, video, addon) -> None:
    """Take the next episode a video add-on announced for this video, in place of a library lookup."""
    found = getattr(monitor, "next_episode_provider", None)
    if not isinstance(found, ProviderData) or found.video != video:
        return
    if not _use_provider_data(addon):
        return
    if isinstance(state.provider, ProviderData) and found.received_mono <= state.provider.received_mono:
        return
    state.provider = found
    state.next_item = found.next_item
    # Playback Skippy ignores has no library entry to look up; a library file still gets its lookup
    # (for the episode it marks as watched) and keeps the add-on's answer for what comes next.
    if state.remote or state.lookup != LOOKUP_IDLE:
        state.lookup = LOOKUP_FOUND
    log("Next episode: %s announced %s" % (found.provider, episode_label(found.next_item) or "an episode"))


def _playing_file(player):
    try:
        path = player.getPlayingFile()
    except Exception:
        return ""
    return path if isinstance(path, str) else ""


def note_upnext_data(monitor, sender, method, data) -> None:
    """Remember what a video add-on said about the next episode of what is playing now.

    Called from the monitor's notification handler for Up Next's ``upnext_data`` signal; never raises.
    """
    try:
        addon = get_addon()
        if not addon or not addon_get_bool(addon, "next_episode_enabled", False):
            return
        if not _use_provider_data(addon):
            return
        provider = provider_id(sender)
        if not provider:
            return
        found = parse_payload(provider, decode_notification(data))
        if found is None:
            log("Next episode: ignored an Up Next announcement from %s (no usable next episode)" % provider)
            return
        playing = _playing_file(xbmc.Player())
        if not playing:
            return
        monitor.next_episode_provider = found.stamped(playing, time.monotonic())
    except Exception as exc:
        log_error("Next episode: reading an Up Next announcement failed: %s" % exc)


def handle_remote_next_episode(ctx: Any) -> NextEpisodeTick:
    """The next episode step for playback the main loop otherwise ignores (add-on and stream URLs).

    Such playback has no sidecar segments and no library entry, so the only way to know what comes
    next is the video add-on telling us. Without that, nothing happens. Never raises.
    """
    try:
        monitor = ctx.monitor
        found = getattr(monitor, "next_episode_provider", None)
        if not isinstance(found, ProviderData):
            return IDLE_TICK
        addon = get_addon()
        if not addon or not addon_get_bool(addon, "next_episode_enabled", False):
            return IDLE_TICK
        if not _use_provider_data(addon):
            return IDLE_TICK
        player = ctx.player
        playing = _playing_file(player)
        if not playing or playing != found.video:
            return IDLE_TICK
        if not player.isPlaying() or xbmc.getCondVisibility("Player.Paused"):
            return IDLE_TICK
        return handle_next_episode(
            ctx,
            video=playing,
            playback_type="episode",
            current_time=player.getTime(),
            player_item={"type": "episode"},
            remote=True,
        )
    except Exception as exc:
        signature = "%s: %s" % (type(exc).__name__, exc)
        if signature != getattr(ctx.monitor, "_next_episode_remote_error", None):
            ctx.monitor._next_episode_remote_error = signature
            log_error("Next episode step for add-on playback failed (%s)" % signature)
        return IDLE_TICK


def _state_for(monitor, video) -> NextEpisodeState:
    state = getattr(monitor, "next_episode_state", None)
    if state is None or state.video != video:
        carried = False
        if state is not None:
            carried = ended_on_its_own(state, time.monotonic())
            reset_guard(state)
        state = NextEpisodeState(video=video)
        monitor.next_episode_state = state
        begin_episode(_chain_for(monitor), carried=carried)
    return state


def _note_progress(state, current_time, total) -> None:
    """Remember how far the episode got, so the next one can tell whether this one ended by itself."""
    try:
        state.last_time = float(current_time)
        state.total = float(total)
        state.last_seen_mono = time.monotonic()
    except (TypeError, ValueError):
        pass


def _chain_for(monitor) -> WatchChain:
    chain = getattr(monitor, "next_episode_chain", None)
    if chain is None:
        chain = WatchChain()
        monitor.next_episode_chain = chain
    return chain


def _credits_start(monitor, addon, total, state=None):
    """Where the Credits segment starts, when the setting asks for it and there is one.

    Without a Credits segment of Skippy's own, the time the video add-on asked for is used.
    Playback Skippy ignores has no segments: whatever the monitor holds belongs to an earlier video.
    """
    if not addon_get_bool(addon, "next_episode_start_at_credits", False):
        return None
    remote = bool(getattr(state, "remote", False))
    found = (
        None
        if remote
        else credits_start_seconds(getattr(monitor, "current_segments", None), total)
    )
    if found is None and isinstance(getattr(state, "provider", None), ProviderData):
        return state.provider.prompt_start(total)
    return found


def _idle_seconds():
    """Seconds since the last button press, or None when Kodi cannot say."""
    try:
        return float(xbmc.getGlobalIdleTime())
    except Exception:
        return None


def _still_watching_due(monitor, state, addon) -> bool:
    """Decide once per episode whether to ask "still watching?" instead of autoplaying."""
    if not addon_get_bool(addon, "next_episode_still_watching", True):
        return False
    if not state.guard_checked:
        state.guard_checked = True
        limit = addon_get_int(
            addon, "next_episode_still_watching_after", 3, minimum=1, maximum=10
        )
        chain = _chain_for(monitor)
        state.guard_ask = evaluate(
            chain, state.created_mono, time.monotonic(), _idle_seconds(), limit
        )
        log(
            "Next episode: %d episode(s) in a row without a button press, limit %d%s"
            % (chain.unattended, limit, " - asking if you are still watching" if state.guard_ask else "")
        )
    return state.guard_ask


def _arm_stop_watchdog(ctx, state, start, total) -> None:
    """Kodi (a playlist, its own play next video) would carry on by itself.

    So playback is stopped before the end if nobody answers the question.
    """
    cancel = state.guard_cancel
    if cancel is not None and not cancel.is_set():
        return
    state.guard_cancel = start_stop_watchdog(ctx.player, start, total)


def _stand_down_watchdog(state) -> None:
    cancel = state.guard_cancel
    if cancel is not None:
        cancel.set()


def _queue_remember(monitor, state) -> None:
    """Note that the episode just started with Play now may earn a per-show autoplay question."""
    if not state.show_key:
        return
    monitor.next_episode_remember = {
        "key": state.show_key,
        "title": state.show_title,
        "video": state.video,
        "mono": time.monotonic(),
    }


def _maybe_ask_remember(ctx, monitor, addon, video, current_time, per_show) -> None:
    """Ask the queued question once the next episode is playing; never raises into the loop."""
    pending = getattr(monitor, "next_episode_remember", None)
    if not pending or video == pending["video"]:
        return
    if not per_show or time.monotonic() - pending["mono"] > REMEMBER_EXPIRES_S:
        monitor.next_episode_remember = None
        return
    try:
        if float(current_time) < REMEMBER_DELAY_S:
            return
    except (TypeError, ValueError):
        return
    monitor.next_episode_remember = None
    if lookup_mode(pending["key"]) is not None:
        return
    from next_episode_shows_ui import ask_autoplay_for_show

    ask_autoplay_for_show(ctx, addon, pending["key"], pending["title"])


def _resolve_show(state, item, current) -> None:
    """Fill the per-show key and title; a show that cannot be identified stays on the global setting."""
    try:
        from remote_library import library_title_identity

        episode = dict(item or {})
        episode.setdefault("type", "episode")
        if current.get("tvshowid"):
            episode["tvshowid"] = current["tvshowid"]
        identity = library_title_identity(episode)
        state.show_key = show_key_for_identity(identity)
        state.show_title = ((identity or {}).get("title") or item.get("showtitle") or "").strip()
    except Exception as exc:
        log("Next episode: could not identify the show (%s)" % exc)


def _start_lookup(state, player_item, *, skip_watched, resolve_show=False) -> None:
    state.lookup = LOOKUP_RUNNING
    item = dict(player_item or {})
    threading.Thread(
        target=run_lookup, args=(state, item, skip_watched, resolve_show), daemon=True
    ).start()


def run_lookup(state, item, skip_watched, resolve_show=False) -> None:
    """Resolve the next episode and the facts needed later; runs off the service thread."""
    try:
        movie = is_movie_playback(item)
        current = describe_current_movie(item) if movie else describe_current_episode(item)
        if resolve_show and not movie:
            _resolve_show(state, item, current)
        nxt = find_next_episode(item, skip_watched=skip_watched, current=current)
        state.current_kind = KIND_MOVIE if movie else KIND_EPISODE
        state.current_episode_id = current.get("id")
        state.current_playcount = current.get("playcount")
        if state.provider is not None:
            # The video add-on already said what comes next; that wins over the library.
            state.lookup = LOOKUP_FOUND
            return
        state.next_item = nxt
        state.lookup = LOOKUP_FOUND if nxt else LOOKUP_NONE
        if nxt:
            log("Next episode: %s (%s)" % (episode_label(nxt), nxt.get("source")))
        else:
            log("Next episode: none found after this one")
    except Exception as exc:
        state.lookup = LOOKUP_NONE
        log_error("Next episode lookup failed: %s\n%s" % (exc, traceback.format_exc()))


def _start_next(monitor, state, addon, *, autoplayed=False) -> bool:
    ok = play_next(
        state.next_item, resume=addon_get_bool(addon, "next_episode_resume", True)
    )
    if not ok:
        state.failed = True
        return False
    state.started = True
    _chain_for(monitor).autoplay_pending = bool(autoplayed)
    log("Next episode: started %s" % episode_label(state.next_item))
    if addon_get_bool(addon, "next_episode_mark_watched", True):
        schedule_mark_watched(
            monitor, state.current_episode_id, state.current_playcount, state.current_kind
        )
    return True


def _total_time(player) -> float:
    try:
        return float(player.getTotalTime())
    except Exception:
        return 0.0


def _upnext_enabled() -> bool:
    try:
        return bool(
            xbmc.getCondVisibility("System.AddonIsEnabled(%s)" % UPNEXT_ADDON_ID)
        )
    except Exception:
        return False


def _note_upnext(monitor, addon) -> None:
    """Tell the user once per Kodi session why the prompt stays off."""
    if getattr(monitor, "next_episode_upnext_notified", False):
        return
    monitor.next_episode_upnext_notified = True
    log("Next episode: %s is enabled - Skippy's prompt stays off" % UPNEXT_ADDON_ID)
    notify_skippy(
        addon,
        get_localized(
            addon, 47022, "Up Next is turned on, so Skippy's next episode prompt stays off."
        ),
        title=get_localized(addon, 43000, "Skippy"),
    )
