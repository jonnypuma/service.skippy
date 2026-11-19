# -*- coding: utf-8 -*-
"""The next episode popup in a drawn design (``next_canvas``).

It is ``next_episode_dialog.NextEpisodeDialog`` for everything that matters to the caller: the
answer, the countdown, when it closes by itself. The drawing is that of the drawn skip dialog: the
skin file ``SkipCanvas.xml`` holds picture slots and two buttons, and ``skip_canvas_draw.Canvas``
places everything. Play now is the engine's Skip button, Cancel its Close button.
"""

from __future__ import annotations

import os
import threading
import types

import xbmc

import next_canvas as nc
import next_episode_dialog as base
import next_layouts as nl
import skip_canvas as cv
import skip_canvas_dialog as scd
import skip_canvas_draw as draw
import skip_layouts as sl
from addon_skin_resolution import reconcile_window_xml_skin_resolution
from next_episode_appearance import FOCUS_CLOSE, KEY_FOCUS, KEY_POSITION, KEY_PROGRESS, seconds_left
from next_episode_lookup import is_movie_item, parse_int
from settings_utils import addon_get_setting_text, get_localized, log, log_always

PREFIX, OPTION_KEYS = nc.PREFIX, nc.OPTION_KEYS
# what the skip dialog calls a setting -> the Up Next name for the same choice
_TWINS = {
    scd.KEY_CORNERS: "corners", scd.KEY_CLOSE: "close", scd.KEY_ICONS: "icons", scd.KEY_PROGRESS: "progress",
    scd.KEY_ACCENT: "accent", scd.KEY_ZOOM: "zoom", "skip_canvas_place": "place", "skip_canvas_distance": "distance",
    sl.KEY_OVERLAY: "overlay", scd.KEY_GRADIENT_ON: "overlay_gradient", scd.KEY_GRADIENT: "gradient",
    sl.KEY_APPEAR: "appear", sl.KEY_LEAVE: "leave", sl.KEY_PULSE: "pulse", scd.KEY_TEXT_SHADOW: "text_shadow",
    scd.KEY_TEXT_OUTLINE: "outline", scd.KEY_TEXT_SIZE: "text_size", scd.KEY_KICKER: "kicker",
}


def setting_keys() -> list:
    return [PREFIX + name for name in OPTION_KEYS]


def reader(addon, draft):
    """``get(name)``: an option of the drawn popup, from the draft when it has it, else from the settings."""
    def get(name):
        key = PREFIX + name
        if draft and draft.get(key) not in (None, ""):
            return str(draft[key])
        found = addon_get_setting_text(addon, key, "") if addon else ""
        return found if found not in (None, "") else OPTION_KEYS[name]
    return get


def _yes(text) -> bool:
    return str(text).strip().lower() in ("true", "1", "yes")


def options_for(addon, draft, design) -> cv.Options:
    """The options of a drawn Up Next design: the skip dialog's own reading of the same choices."""
    get = reader(addon, draft)
    draft = draft or {}

    def get_text(key, default):
        return get(_TWINS[key]) if key in _TWINS else default

    def get_bool(key, default):
        if key == "show_progress_bar":
            return bool(draft.get(KEY_PROGRESS, True))
        return _yes(get(_TWINS[key])) if key in _TWINS else default

    layout = types.SimpleNamespace(name=design, size=sl.SIZE_FULL)
    look = draft.get(nl.KEY_LAYOUT_LOOK)
    if _yes(get("follow_skin")):
        # Follow the skin style: the look that goes with what the skin is showing (a skin without one keeps the popup's)
        import skin_look

        look = skin_look.current() or look
    elif _yes(get("same_look")):
        # Same look as the skip dialog: whatever look that one has now
        look = (addon_get_setting_text(addon, sl.KEY_LOOK, "") if addon else "") or look
    options = scd.options_from(get_text, get_bool, layout, look, draft.get(KEY_POSITION))
    picture = picture_choice(get("picture"))
    if nl.normalize_layout(draft.get(nl.KEY_LAYOUT)) == "Poster" and picture != "Off":
        picture = "Poster"  # the Poster card is the Card with the show's poster
    try:
        speed = max(0, min(600, int(float(get("speed")))))
    except (TypeError, ValueError):
        speed = 0
    return cv.dataclasses.replace(
        options, size=nc.form(get("form")), plot=_yes(get("plot")), picture=picture,
        fallback=sl.normalize_choice(get("fallback"), ("Fanart", "Poster", "Nothing"), "Fanart"),
        fill_on=sl.normalize_choice(get("fill_on"), ("Button", "Card", "Picture"), "Button"),
        caps=sl.normalize_choice(get("caps"), ("Look", "On", "Off"), "Look"),
        time=_yes(get("time")), credits=_yes(get("credits")), speed=speed,
        focus_style=sl.normalize_choice(get("focus_style"), ("Look", "Accent", "Outline"), "Look"),
        background=sl.normalize_choice(get("background"), cv.BACKGROUNDS, "None"),
        art_edges=sl.normalize_choice(get("art_edges"), cv.ART_EDGES, "Look"),
        bar_edges=sl.normalize_choice(get("bar_edges"), cv.BAR_EDGES, "Straight"),
        # Takeover + video: what is playing small at the top right (the whole-screen form only)
        video=nl.normalize_layout(draft.get(nl.KEY_LAYOUT)) == nl.LAYOUT_TAKE_VIDEO and nc.form(get("form")) == "Full",
        rise=SUBTITLE_RISE if _yes(get("subtitles")) and (draft.get("_preview") or subtitles_showing()) else 0.0)


PICTURES = ("Episode", "Poster", "Both", "Fanart", "Off")
SUBTITLE_RISE = 150.0  # how much higher a popup at the bottom stands while subtitles are shown


def subtitles_showing() -> bool:
    try:
        return bool(xbmc.getCondVisibility("VideoPlayer.HasSubtitles + VideoPlayer.SubtitlesEnabled"))
    except Exception:
        return False


def picture_choice(stored) -> str:
    """The Picture choice as the designs know it. Earlier versions stored a yes or a no."""
    text = str(stored or "").strip()
    if text.lower() in ("true", "1", "yes", "episode", ""):
        return "On"
    if text.lower() in ("false", "0", "no", "off"):
        return "Off"
    return text if text in ("Poster", "Both", "Fanart") else "On"


def minutes(addon, episode) -> str:
    seconds = parse_int((episode or {}).get("runtime"))
    if not seconds or seconds <= 0:
        return ""
    return get_localized(addon, 49196, "%d min") % max(1, int(round(seconds / 60.0)))


def _template(text) -> str:
    """A translated line with ``%s`` for the time left, as a template of the designs (``{cd}``)."""
    return str(text).replace("{", "(").replace("}", ")").replace("%s", "{cd}")


def texts_for(addon, episode, countdown, seconds, percent, still_watching=False, queue=None) -> nc.Texts:
    """What a design writes for an episode (or a film)."""
    episode = episode or {}
    movie = is_movie_item(episode)
    season, number = parse_int(episode.get("season")), parse_int(episode.get("episode"))
    code = ""
    if not movie and season is not None and number is not None and season >= 0 and number >= 0:
        code = "S%d E%d" % (season, number)
    title = (episode.get("title") or "").strip() or code
    if still_watching:
        play, close = get_localized(addon, 47071, "Continue"), get_localized(addon, 47072, "Stop")
        up_next = get_localized(addon, 47070, "Still watching?")
    else:
        play, close = get_localized(addon, 47050, "Play now"), get_localized(addon, 35019, "Cancel")
        up_next = get_localized(addon, 49192, "Up next")
    starts = _template(get_localized(addon, 47124, "Next episode starts in %s"))
    return nc.Texts(
        up_next=up_next, episode=code, mins=minutes(addon, episode), title=title, plot=(episode.get("plot") or "").strip(),
        countdown=countdown, seconds=str(seconds), play=play, close=close,
        # a line with the time left in it keeps its place for the time; without one it ends the line
        starts=starts.replace("{cd}", "").strip(), starts_short=_template(get_localized(addon, 49193, "Starts in %s")).replace("{cd}", "").strip(),
        up_in=_template(get_localized(addon, 49194, "Up next in %s")).replace("{cd}", "").strip(),
        next_word=get_localized(addon, 49195, "Next"),
        thumb=episode.get("thumb") or "", poster=episode.get("poster") or "", fanart=episode.get("fanart") or "",
        logo=episode.get("logo") or "", percent=percent, show=(episode.get("showtitle") or "").strip(),
        play_one=_template(get_localized(addon, 49198, "Play %s")).replace("{cd}", "{ep}"),
        later=get_localized(addon, 49197, "Play a later one"),
        credits=get_localized(addon, 49218, "Watch credits"),
        queue=tuple(queue_row(addon, item) for item in (queue or [episode])),
    )


def queue_row(addon, episode) -> tuple:
    """A card of the Queue: ``(episode, title, minutes, picture)``."""
    season, number = parse_int(episode.get("season")), parse_int(episode.get("episode"))
    code = "S%d E%d" % (season, number) if season is not None and number is not None and season >= 0 and number >= 0 else ""
    return (code, (episode.get("title") or "").strip() or code, minutes(addon, episode),
            episode.get("thumb") or episode.get("fanart") or episode.get("poster") or "")


def tick(canvas, shown, secs) -> None:
    """Write the time left wherever a design shows it (the popup every second, the Studio's preview as it plays)."""
    canvas.set_text("countdown", shown)
    canvas.set_text("skip_time", shown)
    # every line that has the time left in it is written again from its template
    for key, (_control, op) in list(canvas.by_key.items()):
        if op and op.get("fmt") and not str(key).startswith("shade:"):
            canvas.set_text(key, op["fmt"].format(cd=shown, secs=secs))


# What was made ready ahead of time for an episode: {"key": its file or title, "queue": [...]}
_READY = {}


def _episode_key(episode) -> str:
    episode = episode or {}
    return str(episode.get("file") or "%s|%s|%s" % (episode.get("showtitle"), episode.get("season"), episode.get("episode")))


def cache_picture(path) -> bool:
    """Have Kodi put a picture into its picture cache now, so it is there when the popup shows it. A
    picture on a network share otherwise loads while the popup is already on screen."""
    if not path:
        return False
    try:
        from urllib.parse import quote

        import xbmcvfs

        url = path if str(path).startswith("image://") else "image://%s/" % quote(str(path), safe="")
        handle = xbmcvfs.File(url)
        try:
            handle.readBytes(16)  # opening it is what makes Kodi cache it
        finally:
            handle.close()
        return True
    except Exception:
        return False


def preload(addon, episode) -> dict:
    """Everything the drawn popup can have ready before it is due (the next episode is known from the
    start of playback): its code and the skin's fonts, its design built once, the episodes of a Queue, and
    its pictures in Kodi's picture cache. Returns what it did, for the log."""
    import time

    from next_episode_appearance import load_popup_draft

    started = time.time()
    episode = episode or {}
    draft = load_popup_draft(addon)
    if not nl.is_drawn(draft.get(nl.KEY_LAYOUT)):
        return {"drawn": False}
    design = nc.design_for(draft.get(nl.KEY_LAYOUT))
    draw.read_fonts()
    queue = []
    if design == "NQueue":
        try:
            from next_episode_lookup import find_queue

            queue = find_queue(episode, 3) or []
        except Exception:
            queue = []
    _READY.clear()
    _READY.update(key=_episode_key(episode), queue=queue)
    options = options_for(addon, draft, design)
    texts = texts_for(addon, episode, "0:45", 45, 100.0, queue=queue or None)
    nc.draw(options, texts)
    pictures = [episode.get(name) for name in ("thumb", "fanart", "poster", "logo")]
    pictures += [item.get("thumb") or item.get("fanart") for item in queue]
    cached = sum(1 for path in dict.fromkeys(p for p in pictures if p) if cache_picture(path))
    done = {"drawn": True, "design": design, "queue": len(queue), "pictures": cached, "ms": int((time.time() - started) * 1000)}
    log_always("Up Next made ready ahead: %s" % done)
    return done


def clock(seconds) -> str:
    seconds = max(0, int(round(float(seconds))))
    return "%d:%02d" % (seconds // 60, seconds % 60)


class NextCanvasDialog(base.NextEpisodeDialog):
    def __init__(self, *args, **kwargs):
        self._nc_design = kwargs.pop("design")
        # The flag is off when the window opens (Kodi does not undo an animation whose condition already held then:
        # the dialog stayed unseen for good). The window is empty until the drawing starts, which sets the flag.
        draw.reveal()
        super(NextCanvasDialog, self).__init__(*args, **kwargs)
        self._canvas = None
        self._nc_last = None
        self._nc_queue = []  # the Queue: the episodes of its cards
        self._nc_card = 0  # and the chosen one
        self._nc_names = {}  # control id -> the name the drawing knows it by

    def onInit(self):
        draw.conceal()  # as early as can be: Kodi takes a frame or two to act on it
        self._skin_resolution = reconcile_window_xml_skin_resolution(
            self, getattr(self, "_skin_resolution", None), control_ids=(cv.ID_PROBE,)
        )
        head = self._head()
        left = seconds_left(head, self.total)
        options = None
        try:
            options = options_for(self.addon, self.draft, self._nc_design)
            if self._nc_design == "NQueue":
                self._nc_queue = self._find_queue()
            texts = texts_for(self.addon, self.next_episode, clock(left), max(0, int(round(float(left)))),
                              self._bar_percent(head) or 0.0, self.still_watching, queue=self._nc_queue)
            if not _yes(reader(self.addon, self.draft)("logo")):
                texts.logo = ""
            folder = "720" if str(self._skin_resolution).startswith("720") else "1080"
            media = os.path.join(self.addon.getAddonInfo("path"), "resources", "skins", "default", "media")
            self._canvas = draw.Canvas(self, folder, media)
            self._canvas.draw(options, texts, build=nc.draw)
            self._wire_focus()
        except Exception as exc:
            log("Next episode popup (drawn): set-up failed: %s" % exc)
        self._update_countdown(head)
        try:
            # Still unseen: the focus goes where it starts and the buttons take its colours, so that the
            # dialog comes complete and in one piece. Then it is shown, and its parts come as Appears says.
            close_first = (self.draft.get(KEY_FOCUS) == FOCUS_CLOSE and not self.still_watching
                           and options is not None and options.close
                           and self._canvas is not None and self._canvas.drawing.find("close_label") is not None)
            self.setFocusId(cv.ID_CLOSE if close_first else cv.ID_SKIP)
            if self._canvas is not None:
                self._wire_focus()  # (a second time: set before the focus, the directions did not always take)
                self._canvas.set_focus("close" if close_first else "skip")
                log_always("Up Next drawn: %s %s (%s, %s) %s" % (options.design, options.size, options.look, options.place,
                                                         self._canvas.timing))
        except Exception:
            pass
        finally:
            # Uncovered first (every part is still at nothing: each waits for "ready"), then "ready": the parts
            # come from nothing, all together, the way Appears says.
            draw.settle()
            draw.reveal()
            self.setProperty("skippy_dialog_ready", "true")
        self._start_progress_driver()
        threading.Thread(target=self._watch, daemon=True).start()

    def _find_queue(self) -> list:
        """The next episode and the two after it (the preview shows three of its one)."""
        from next_episode_lookup import find_queue

        if _READY.get("key") == _episode_key(self.next_episode) and _READY.get("queue"):
            queue = list(_READY["queue"])  # looked up ahead of time
            queue[0] = self.next_episode  # (the popup rewrites this one in place when a later card is chosen)
        else:
            try:
                queue = find_queue(self.next_episode, 3)
            except Exception:
                queue = []
        queue = queue or [self.next_episode]
        if len(queue) == 1 and getattr(self, "preview", False):
            queue = queue * 3
        return queue

    def _wire_focus(self):
        """Where Left, Right, Up and Down go: along the cards, along the buttons, and between the two rows."""
        drawing = self._canvas.drawing
        cards = sorted((op for op in drawing.ops if op["t"] == "hot"), key=lambda op: op["rect"][0])
        buttons = sorted((op for op in drawing.ops if op["t"] == "button"), key=lambda op: op["rect"][0])
        card_ids = [cv.HOT_IDS[op["name"]] for op in cards]
        button_ids = [cv.BUTTON_IDS[op["which"]] for op in buttons]
        self._nc_names = {cv.HOT_IDS[op["name"]]: op["name"] for op in cards}
        self._nc_names.update({cv.BUTTON_IDS[op["which"]]: op["which"] for op in buttons})
        if not cards and len(buttons) <= 2:
            return  # two buttons: the skin file already sends each to the other
        controls = {cid: self.getControl(cid) for cid in card_ids + button_ids}

        def step(ids, index, delta):
            return controls[ids[max(0, min(len(ids) - 1, index + delta))]]

        for index, cid in enumerate(card_ids):
            down = controls[button_ids[0]] if button_ids else controls[cid]
            controls[cid].setNavigation(controls[cid], down, step(card_ids, index, -1), step(card_ids, index, 1))
        for index, cid in enumerate(button_ids):
            up = controls[card_ids[min(self._nc_card, len(card_ids) - 1)]] if card_ids else controls[cid]
            controls[cid].setNavigation(up, controls[cid], step(button_ids, index, -1), step(button_ids, index, 1))
        if cards:
            self._canvas.set_card(self._nc_card)
        log("Up Next focus wired: cards %s, buttons %s" % (card_ids, button_ids))

    def _choose_card(self, index):
        """The Queue: this card is the chosen one. Play names its episode."""
        self._nc_card = index
        self._canvas.set_card(index)
        if index < len(self._nc_queue):
            row = queue_row(self.addon, self._nc_queue[index])
            texts = texts_for(self.addon, self.next_episode, "", 0, 0.0)
            label = cv._caps(texts.play_one.format(ep=row[0] or row[1]), self._canvas.look or {"caps": False})
            self._canvas.set_text("skip_label", label)

    def _play_card(self, index):
        """A later card of the Queue: that episode becomes the one to play."""
        if 0 < index < len(self._nc_queue) and self._nc_queue[index] is not self.next_episode:
            chosen = dict(self._nc_queue[index])
            self.next_episode.clear()
            self.next_episode.update(chosen)
        self._finish(True)

    # ----------------------------------------------------------------- progress
    def _set_bar_percent(self, pct):
        canvas = self._canvas
        if canvas is None:
            return
        key = int(round(float(pct) * 10))
        if key != self._nc_last:
            self._nc_last = key
            canvas.set_percent(pct)

    def _start_progress_driver(self):
        if getattr(self, "_closing", False):
            return
        if str(reader(self.addon, self.draft)("bar")).strip().lower() == "steps":
            return  # Bar: Steps. It moves once a second, with the countdown (``_update_countdown``)
        from smooth_progress import ProgressDriver

        self._progress_driver = ProgressDriver(
            "skippy-next-canvas-progress",
            self._bar_percent,
            self._set_bar_percent,
            position=self._head,
            still_wanted=lambda: not getattr(self, "_closing", False),
        ).start()

    def _update_countdown(self, head, bar=True):
        canvas = self._canvas
        if canvas is None:
            return
        try:
            left = seconds_left(head, self.total)
            shown, secs = clock(left), str(max(0, int(round(float(left)))))  # the same second in both
            if (shown, secs) != getattr(self, "_nc_shown", None):
                self._nc_shown = (shown, secs)
                tick(canvas, shown, secs)
            beating = "true" if left <= cv.PULSE_SECONDS else ""
            if beating != getattr(self, "_beating", ""):
                self._beating = beating
                self.setProperty("skippy_dialog_pulse", beating)
            if bar:
                self._set_bar_percent(self._bar_percent(head) or 0.0)
        except Exception as exc:
            log("Next episode popup (drawn): updating the countdown failed: %s" % exc)

    def close(self):
        """Leave the way Leaves says, then close."""
        canvas = self._canvas
        if canvas is not None and not getattr(self, "_left", False):
            self._left = True
            try:
                self.setProperty("skippy_dialog_out", "true")
                xbmc.sleep(int(canvas.leave_ms) + 30)
            except Exception:
                pass
        draw.reveal()  # never leave the flag behind
        super(NextCanvasDialog, self).close()

    # -------------------------------------------------------------------- input
    def onAction(self, action):
        super(NextCanvasDialog, self).onAction(action)
        self._follow_focus()

    def onFocus(self, controlId):
        self._follow_focus()

    def _follow_focus(self):
        canvas = self._canvas
        if canvas is None or getattr(self, "_closing", False):
            return
        try:
            name = self._nc_names.get(self.getFocusId()) or ("close" if self.getFocusId() == cv.ID_CLOSE else "skip")
            canvas.set_focus(name)
            if name in cv.HOT_IDS and int(name[1:]) - 1 != self._nc_card:
                self._choose_card(int(name[1:]) - 1)
                # Up from the buttons comes back to this card
                self._wire_focus()
        except Exception:
            pass

    def onClick(self, controlId):
        try:
            cid = int(controlId)
        except (TypeError, ValueError):
            return
        name = self._nc_names.get(cid, "")
        if name in cv.HOT_IDS:
            self._play_card(int(name[1:]) - 1)
        elif cid == cv.ID_SKIP:
            self._play_card(self._nc_card)
        elif cid == cv.ID_MORE and not self._nc_queue:
            # Watch credits: the popup goes, the next episode starts when the credits have run
            from next_episode_state import AFTER_CREDITS

            self._finish(AFTER_CREDITS)
        elif cid == cv.ID_MORE:
            # Play a later one: on to the cards, the one after the chosen
            later = min(self._nc_card + 1, len(self._nc_queue) - 1)
            try:
                self.setFocusId(cv.HOT_IDS["q%d" % (later + 1)])
            except Exception:
                pass
            self._follow_focus()
        elif cid == cv.ID_CLOSE:
            self._finish(False)
