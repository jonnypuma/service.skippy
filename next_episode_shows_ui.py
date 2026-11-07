# -*- coding: utf-8 -*-
"""Windows for per-show autoplay: the question after Play now and the Manage list."""

from __future__ import annotations

from typing import Any

import xbmcgui

from next_episode_shows import (
    MODE_ASK,
    MODE_AUTO,
    MODE_NEVER,
    MODES,
    delete_show,
    list_entries,
    save_mode,
    show_key_for_identity,
)
from remote_http import jsonrpc
from settings_utils import get_addon, get_localized, log, notify_skippy

# Strings (47088-47104) are looked up with an English fallback so a missing one never blanks a window.


def mode_word(addon, mode) -> str:
    if mode == MODE_AUTO:
        return get_localized(addon, 47091, "Play automatically")
    if mode == MODE_NEVER:
        return get_localized(addon, 47145, "Never offer")
    return get_localized(addon, 47092, "Ask first")


def format_entry_label(addon, entry: dict) -> str:
    """One list row: ``Friends — Play automatically``."""
    title = (entry.get("title") or entry.get("key") or "?").strip() or "?"
    return "%s — %s" % (title, mode_word(addon, entry.get("mode")))


def _toast(addon, message) -> None:
    notify_skippy(addon, message, title=get_localized(addon, 43000, "Skippy"))


def _question_texts(addon, title):
    heading = get_localized(addon, 47096, "Always play the next episode?")
    if title:
        message = get_localized(
            addon,
            47097,
            "Start the next episode of %s automatically from now on?",
            title,
        )
    else:
        message = get_localized(
            addon,
            47098,
            "Start the next episode of this show automatically from now on?",
        )
    yes_label = get_localized(addon, 35018, "Yes")
    no_label = get_localized(addon, 47099, "Keep asking")
    return heading, message, yes_label, no_label


def ask_autoplay_for_show(ctx: Any, addon, key, title) -> None:
    """
    Ask once whether this show should start its next episode by itself.

    Shown a few seconds into the episode the user just started with Play now. Either
    answer is remembered: Yes plays automatically from now on, "Keep asking" keeps the
    prompt for this show, even when global autoplay is on.
    """
    from skippy_editor_modal_skin import sidecar_overwrite_yesno_show

    try:
        if not ctx.player.isPlayingVideo():
            return
    except RuntimeError:
        return

    heading, message, yes_label, no_label = _question_texts(addon, title)
    monitor = ctx.monitor
    monitor.skip_dialog_modal_active = True
    try:
        try:
            confirmed = sidecar_overwrite_yesno_show(heading, message, yes_label, no_label)
        except Exception as exc:
            log("⚠ Per-show autoplay question failed (%s) — using stock yesno" % exc)
            try:
                confirmed = xbmcgui.Dialog().yesno(
                    heading, message, nolabel=no_label, yeslabel=yes_label
                )
            except Exception:
                return
    finally:
        monitor.skip_dialog_modal_active = False

    if save_mode(key, MODE_AUTO if confirmed else MODE_ASK, title=title) and confirmed:
        try:
            xbmcgui.Dialog().notification(
                heading=get_localized(addon, 43000, "Skippy"),
                message=get_localized(addon, 47100, "Autoplay saved for this show"),
                icon=getattr(ctx, "icon_path", "") or "",
                time=2500,
                sound=False,
            )
        except Exception as exc:
            log("⚠ Per-show autoplay saved toast failed: %s" % exc)


def _library_shows() -> list[dict]:
    response = jsonrpc(
        "VideoLibrary.GetTVShows",
        {"properties": ["title"], "sort": {"method": "title", "ignorearticle": True}},
        log_errors=False,
    )
    shows = []
    for row in (response.get("result") or {}).get("tvshows") or []:
        try:
            show_id = int(row.get("tvshowid"))
        except (TypeError, ValueError):
            continue
        title = (row.get("title") or row.get("label") or "").strip()
        if show_id > 0 and title:
            shows.append({"tvshowid": show_id, "title": title})
    return shows


def _identify_show(show: dict):
    """``(key, title)`` for a library show; the key is None when it has no TMDB / IMDb id."""
    from remote_library import library_title_identity

    identity = library_title_identity(
        {"type": "episode", "tvshowid": show["tvshowid"], "showtitle": show["title"]}
    )
    title = ((identity or {}).get("title") or show["title"]).strip()
    return show_key_for_identity(identity), title


def _pick_mode(addon, heading, preselect=0) -> str | None:
    from skippy_editor_modal_skin import show_editor_list_pick

    options = [mode_word(addon, mode) for mode in MODES]
    index = show_editor_list_pick(
        heading,
        options,
        preselect=preselect,
        cancel_label=get_localized(addon, 35019, "Cancel"),
    )
    if isinstance(index, int) and 0 <= index < len(MODES):
        return MODES[index]
    return None


def _add_show(addon) -> None:
    shows = _library_shows()
    if not shows:
        _toast(addon, get_localized(addon, 47094, "No TV shows in your library yet."))
        return
    index = xbmcgui.Dialog().select(
        get_localized(addon, 47104, "Choose a show"), [show["title"] for show in shows]
    )
    if index < 0 or index >= len(shows):
        return
    key, title = _identify_show(shows[index])
    if not key:
        _toast(addon, get_localized(addon, 47095, "Could not tell which show that is."))
        return
    mode = _pick_mode(addon, title)
    if mode:
        save_mode(key, mode, title=title)


def _edit_show(addon, entry: dict) -> None:
    from skippy_editor_modal_skin import show_editor_list_pick

    forget_label = get_localized(addon, 47093, "Forget this show")
    options = [mode_word(addon, mode) for mode in MODES] + [forget_label]
    index = show_editor_list_pick(
        entry["title"],
        options,
        preselect=MODES.index(entry["mode"]) if entry["mode"] in MODES else 0,
        cancel_label=get_localized(addon, 35019, "Cancel"),
    )
    if isinstance(index, int) and 0 <= index < len(MODES):
        save_mode(entry["key"], MODES[index])
    elif index == len(MODES) and delete_show(entry["key"]):
        _toast(
            addon,
            get_localized(
                addon, 47101, "Forgot the autoplay choice for %s", entry["title"]
            ),
        )


def show_manage_next_episode_shows_modal() -> None:
    """
    List the shows with a saved autoplay choice; select one to change or forget it, or add
    a show from the library. Loops until the user closes it.
    """
    from skippy_editor_modal_skin import show_editor_list_pick

    addon = get_addon()
    heading = get_localized(addon, 47088, "Autoplay by show")
    subtitle = get_localized(addon, 47089, "Select a show to change or forget its choice.")
    add_label = get_localized(addon, 47090, "Add a show...")
    close_label = get_localized(addon, 40001, "Close")

    while True:
        entries = list_entries()
        options = [add_label] + [format_entry_label(addon, entry) for entry in entries]
        try:
            index = show_editor_list_pick(
                heading, options, subtitle=subtitle, cancel_label=close_label
            )
        except Exception as exc:
            log("⚠ Autoplay by show list failed (%s) — falling back to stock select" % exc)
            try:
                index = xbmcgui.Dialog().select(heading, options)
            except Exception:
                return
        if index < 0 or index >= len(options):
            return
        if index == 0:
            _add_show(addon)
        else:
            _edit_show(addon, entries[index - 1])
