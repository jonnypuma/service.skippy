# -*- coding: utf-8 -*-
"""Put a ``skip_canvas`` drawing on a Kodi window.

The plates and the two buttons are slots of the skin file (a nine-slice border cannot be given
from Python); every text, icon and bar is a control made here, at the exact size the design asks
for. A font is taken from the active skin and zoomed to the wanted size, so a 32 pixel headline is
32 pixels in any skin.

``stage`` draws the same thing small inside another window (the Studio's live preview): every
control is zoomed around the stage's corner.
"""

from __future__ import annotations

import os
import re
import time

import skip_canvas as cv
import skip_canvas_looks as looks

# Estuary's sizes, for a skin whose font file cannot be read: name -> (size, heavy)
_FALLBACK_FONTS = {"font10": (20.0, False), "font12": (25.0, False), "font13": (30.0, False), "font14": (32.0, False),
                   "font27": (27.0, False), "font30": (30.0, False), "font37": (37.0, False), "font45": (45.0, False)}
_ALIGN = {"l": 4, "r": 5, "c": 6}  # with the vertical middle
_HEAVY = re.compile(r"bold|black|heavy|medium", re.I)


def parse_fonts(text, wanted="") -> dict:
    """``{name: (size, heavy)}`` of the plain ``fontNN`` fonts of a skin's font set (``wanted``, else the
    first). Fonts of another family than most of them (a fallback Arial among the skin's own) are left
    out, so every text is in one typeface; ``heavy`` says the file is a bold or semi-bold cut."""
    sets = re.findall(r'<fontset\s+id="([^"]*)"[^>]*>(.*?)</fontset>', text, re.S)
    body = next((b for name, b in sets if name.strip().lower() == wanted), sets[0][1] if sets else text)
    rows = []
    for font in re.findall(r"<font>(.*?)</font>", body, re.S):
        name = re.search(r"<name>\s*([^<]+?)\s*</name>", font)
        size = re.search(r"<size>\s*([0-9.]+)\s*</size>", font)
        filename = re.search(r"<filename>\s*([^<]+?)\s*</filename>", font)
        style = re.search(r"<style>\s*([^<]+?)\s*</style>", font)
        if name and size and filename and re.fullmatch(r"font\d+", name.group(1)) and not style:
            base = os.path.basename(filename.group(1).replace("\\", "/"))
            family = re.split(r"[-_. ]", base)[0].lower()
            rows.append((name.group(1), float(size.group(1)), family, bool(_HEAVY.search(base))))
    if not rows:
        return {}
    families = [row[2] for row in rows]
    main = max(set(families), key=families.count)
    found = {}
    for name, size, family, heavy in rows:
        if family == main:
            found.setdefault(name, (size, heavy))
    return found


_FONT_CACHE = {}


def read_fonts() -> dict:
    """The fonts of the active skin (``parse_fonts``), or Estuary's sizes when its font file cannot be read.
    Kept per skin folder and font set: reading the file costs a slow box a fifteenth of a second."""
    try:
        import xbmc
        import xbmcvfs

        wanted = (xbmc.getInfoLabel("Skin.Font") or "").strip().lower()
        for folder in ("1080i", "720p", "xml"):
            path = xbmcvfs.translatePath("special://skin/%s/Font.xml" % folder)
            if os.path.isfile(path):
                key = (path, wanted, os.path.getmtime(path))
                if key in _FONT_CACHE:
                    return _FONT_CACHE[key]
                with open(path, encoding="utf-8", errors="replace") as handle:
                    found = parse_fonts(handle.read(), wanted)
                if found:
                    _FONT_CACHE.clear()
                    _FONT_CACHE[key] = found
                    return found
    except Exception:
        pass
    return dict(_FALLBACK_FONTS)


def pick_font(fonts, size, bold=False) -> tuple:
    """``(font name, zoom percent, wrap)`` that draws text ``size`` pixels high. A bold text takes a
    bold or semi-bold file of the skin when it has one (``wrap`` False), else the nearest font inside
    bold tags (``wrap`` True). The font is zoomed the rest of the way; none within four percent."""
    wrap = False
    pool = {name: value for name, value in fonts.items() if value[1] == bool(bold)}
    if not pool:
        pool, wrap = fonts, bool(bold)
    name, (have, _heavy) = min(pool.items(), key=lambda item: (abs(item[1][0] - size), item[0]))
    zoom = 100.0 * size / have
    return name, (100.0 if abs(zoom - 100.0) < 4.0 else zoom), wrap


def big_label(window, left, top, width, height, text, size, bold=True, color="FFFFFFFF"):
    """A label at a size the skin may have no font for: its nearest font, zoomed the rest of the way.
    ``left`` ... ``size`` are in the window's own units. Returns the control (already on the window),
    or None when it could not be made."""
    try:
        import xbmcgui

        font, percent, wrap = pick_font(read_fonts(), size, bold)
        zoom = percent / 100.0
        shown = "[B]%s[/B]" % text if wrap else text
        zoomed = abs(zoom - 1.0) > 1e-3
        x, y = int(left), int(round(top + height / 2.0 - height / zoom / 2.0))
        # made below the screen until it has its zoom (see PARK): else it shows a frame at the wrong size
        control = xbmcgui.ControlLabel(x, y + (PARK if zoomed else 0), int(width / zoom),
                                       int(height / zoom), shown, font=font, textColor=color, alignment=0x4)
        window.addControl(control)
        if zoomed:
            control.setAnimations([("conditional", "effect=zoom start=%.3f end=%.3f center=%d,%d time=0 condition=true"
                                    % (percent, percent, int(left), int(top + height / 2.0)))])
            control.setPosition(x, y)
        return control
    except Exception:
        return None


# The shade under a text that lies on the video: dark copies of the text (right, down, how dark) and how
# dark the soft patch behind the line is. The mockups write such texts with a close and a wide shadow.
# Few copies on purpose: every control is a call into Kodi, and a slow box shows that.
# The shadow falls to the lower right.
SHADES = {
    "Off": ((), 0.0),
    "Mild": (((2, 2, 0.5),), 0.0),
    "Medium": (((2, 2, 0.6),), 0.22),
    "Strong": (((2, 2, 0.7),), 0.38),
    "Heavy": (((2, 2, 0.7), (3, 3, 0.4)), 0.5),
}
# The dark line around the letters: how dark its copies are, and whether the four straight
# directions are drawn besides the four corners.
OUTLINE = {"Light": (0.45, False), "Medium": (0.85, False), "Strong": (1.0, True)}


def outline_level(value) -> str:
    """The outline strength of an option value (earlier versions stored a yes / no)."""
    if value is True:
        return "Medium"
    if value is False or value is None:
        return "Off"
    return value if value in OUTLINE else "Off"


# Tried 2026-11-19: giving a control its animations before it is on the window. Kodi ignores them then (the
# texts came at their font's own size), so this stays off.
ANIMATE_FIRST = False
# A control made here shows the moment it is on the window, a frame or two before it has the animations that
# zoom it and hide it until the dialog shows: its texts flashed, large and at full strength (frame grabs on the
# PC). Kodi takes no animation before the control is on the window, so it is made this far below the screen
# and moved to its place right after its animations.
PARK = 4000
BUSY = "skippy_canvas_busy"  # on the Home window: the skin file of the drawn dialogs is unseen while it says true


def _weak(window):
    """The window, held weakly. A window keeps its Canvas and the Canvas its window: Python's collector does not
    see through Kodi's window objects, so that ring was never freed, and Kodi gives a window's id (13000 to
    13099) back only when the Python object goes. Every dialog shown used one up for good: after a hundred Kodi
    said "maximum number of windows reached" and no dialog opened until it was restarted."""
    try:
        import weakref

        return weakref.proxy(window)
    except Exception:
        return window


def conceal():
    """Have a drawn dialog unseen from its first frame: call before its window opens, and ``reveal`` when
    it is complete. (A window's own animation does not see the window's own properties, hence Home.)"""
    try:
        import xbmcgui

        global _concealed_at
        if xbmcgui.Window(10000).getProperty(BUSY) != "true":
            xbmcgui.Window(10000).setProperty(BUSY, "true")
            _concealed_at = time.time()
    except Exception:
        pass


_concealed_at = 0.0


def concealed_wait():
    """Kodi needs a frame or two to act on the flag. Before anything is put on the window, wait out what is left
    of that: put there sooner, the texts showed for one frame (frame grabs on the PC, where a drawing takes 40 ms)."""
    left = SETTLE_MS / 1000.0 - (time.time() - _concealed_at)
    if left > 0:
        try:
            import xbmc

            xbmc.sleep(int(left * 1000) + 1)
        except Exception:
            pass


SETTLE_MS = 0


def settle():
    """Wait until Kodi has taken up the animations given to the parts made here: uncovered a frame too early,
    the texts showed for one frame at full strength and without their zoom (seen in frame grabs on the PC)."""
    try:
        import xbmc

        xbmc.sleep(SETTLE_MS)
    except Exception:
        pass


def reveal():
    try:
        import xbmcgui

        xbmcgui.Window(10000).setProperty(BUSY, "")
    except Exception:
        pass
WORKERS = 12  # calls into Kodi made side by side


def _side_by_side(calls):
    """Run ``(function, arguments)`` pairs on a few threads and wait for all of them. Kodi lets go of
    Python while one of its calls waits, so the waits overlap."""
    import threading

    calls = list(calls)
    if len(calls) <= 1:
        for function, arguments in calls:
            function(*arguments)
        return

    def work(share):
        for function, arguments in share:
            try:
                function(*arguments)
            except Exception:
                pass

    count = min(WORKERS, len(calls))
    threads = [threading.Thread(target=work, args=(calls[index::count],), daemon=True) for index in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(8.0)


class Canvas:
    """One drawing on one window. ``folder`` is ``"1080"`` or ``"720"`` (the skin folder in use)."""

    def __init__(self, window, folder, media, offset=0, stage=None, fonts=None, prefix="skippy_dialog"):
        self.window = _weak(window)
        self.folder = "720" if str(folder).startswith("720") else "1080"
        self.unit = 1.0 if self.folder == "1080" else 2.0 / 3.0
        self.media = media
        self.offset = offset
        self.base_stage = stage  # (left, top, zoom percent) in window units, or None: the Studio's small screen
        self.stage = stage  # the same with the drawing's own zoom (Size on screen) worked in
        self.fonts = fonts or read_fonts()
        # the window properties the motion hangs on: <prefix>_ready shows the dialog (the real dialog
        # sets skippy_dialog_ready), <prefix>_out makes it leave, <prefix>_pulse makes it beat
        self.prefix = prefix
        self.moves = ()  # the animations of a part made here, for the drawing in hand
        self.leave_ms = 0
        self.made = []
        self.pending = []  # controls made but not yet on the window: they go there in one call
        self.parked = {}  # id of a pending control -> where it belongs (it is made off the screen)
        self.pending_anims = []
        self.pending_texts = []  # (text box, its text): a text box takes its text once it is on the window
        self.timing = {}
        self.slot_times = []
        self.used = set()  # the window properties this canvas has set: only those need clearing
        self.jobs = None  # while a drawing is made: the places to set at its end
        self.tinted = False  # a drawing has coloured the plate of the button in focus (Focus style)
        self.by_key = {}
        self.look = None
        self.options = None
        self.drawing = None
        self.focused = "skip"

    # ------------------------------------------------------------------ helpers
    def _u(self, value) -> int:
        return int(round(value * self.unit))

    def _rect(self, rect) -> tuple:
        x, y, w, h = rect
        left, top = self._u(x), self._u(y)
        return left, top, max(1, self._u(x + w) - left), max(1, self._u(y + h) - top)

    def _path(self, name) -> str:
        return os.path.join(self.media, name)

    def _zoom(self, control, anchor=None, percent=100.0, extra=()):
        """The control's own zoom (a font to its size, around ``anchor``) and the stage's, as one."""
        anims = list(extra)
        z = percent / 100.0
        if self.stage:
            left, top, stage_zoom = self.stage
            s = stage_zoom / 100.0
            ax, ay = anchor if anchor else (0.0, 0.0)
            total = z * s
            if abs(1.0 - total) < 1e-4:
                total = 0.9999
            cx = (left + s * ax * (1.0 - z)) / (1.0 - total)
            cy = (top + s * ay * (1.0 - z)) / (1.0 - total)
            anims.append(("conditional", "effect=zoom start=%.3f end=%.3f center=%.2f,%.2f time=0 condition=true"
                          % (total * 100, total * 100, cx, cy)))
        elif abs(z - 1.0) > 1e-3 and anchor:
            anims.append(("conditional", "effect=zoom start=%.3f end=%.3f center=%.2f,%.2f time=0 condition=true"
                          % (percent, percent, anchor[0], anchor[1])))
        anims.extend(self.moves)
        if anims:
            self.pending_anims.append((control, anims))

    def _flush(self):
        """Put what was made on the window in one call (every call into Kodi waits for a frame on a slow
        box), then give each control its zoom."""
        import time

        started = time.time()
        if ANIMATE_FIRST:
            # A control takes its animations before it is on the window: it then comes at its size and hidden
            # until the dialog shows, and the calls do not wait for Kodi to draw a frame.
            for control, anims in self.pending_anims:
                try:
                    control.setAnimations(anims)
                except Exception:
                    pass
        if self.pending:
            if not self.offset:
                concealed_wait()
            try:
                self.window.addControls(self.pending)
            except Exception:
                for control in self.pending:
                    try:
                        self.window.addControl(control)
                    except Exception:
                        pass
        added = time.time()
        for control, text in self.pending_texts:
            try:
                control.setText(text)
            except Exception:
                pass
        self.pending_texts = []
        if not ANIMATE_FIRST:
            moves = dict((id(control), anims) for control, anims in self.pending_anims)

            def animate(control, anims):
                # its animations first (they hide it until the dialog shows), then onto the screen
                try:
                    if anims:
                        control.setAnimations(anims)
                except Exception:
                    pass
                try:
                    at = self.parked.get(id(control))
                    if at is not None:
                        control.setPosition(int(at[0]), int(at[1]))
                except Exception:
                    pass

            _side_by_side([(animate, (control, moves.get(id(control)))) for control in self.pending])
        self.parked = {}
        self.timing.update(controls=len(self.pending), zooms=len(self.pending_anims),
                           add_ms=int((added - started) * 1000), zoom_ms=int((time.time() - added) * 1000))
        self.pending, self.pending_anims = [], []

    def _add(self, control, key=None, op=None, at=None):
        """``at``: where the control belongs. It was made ``PARK`` below that, off the screen, and ``_flush``
        brings it there once it has its animations."""
        self.pending.append(control)
        if at is not None:
            self.parked[id(control)] = at
        self.made.append(control)
        if key:
            self.by_key[key] = (control, op)
        return control

    def _ink(self, op):
        if op.get("ink_acc"):
            # the ring inside a button: the accent the look uses on its focus colour, else the button ink
            return self.look["foc_acc"] if self.focused == op["ink_acc"] else self.look["btn_ink"]
        if op.get("bg"):
            # a disc that stands for a button: the focus colour with the focus, else the card's
            if self.focused == op["bg"]:
                return self.look["foc"]
            plate = self.look.get("plate") or (40, 44, 52, 255)
            return plate[:3] + (max(plate[3], 200),)
        which = op.get("ink")
        if which:
            colour = cv.ink(self.look, which, self.focused == which)
            return looks.with_alpha(colour, op.get("share", 1.0))
        return op.get("color") or self.look["ink"]

    # --------------------------------------------------------------------- draw
    def clear(self):
        if self.made:
            try:
                self.window.removeControls(self.made)
            except Exception:
                for control in self.made:
                    try:
                        self.window.removeControl(control)
                    except Exception:
                        pass
        self.made, self.by_key = [], {}
        # Only what an earlier drawing set: on a window that was just opened there is nothing to clear, and
        # every call into Kodi costs a slow box time before the dialog shows.
        for name in self.used:
            self.window.setProperty(name, "")
        self.used = set()
        if not self.offset:
            # The third button and the places that only take the focus are always written, empty first: seen
            # on Kodi 21, a button whose property is set once, after the window opened, stays unseen.
            for name in list(cv.HOT_IDS) + ["more"]:
                self.window.setProperty("cv_hot_" + name, "")

    def condition(self, name) -> str:
        return "String.IsEqual(Window.Property(%s_%s),true)" % (self.prefix, name)

    def _set_motion(self, options, drawing, animate):
        """Work out the motion of this drawing: for what is made here (``self.moves``), for the group
        of the card and the buttons, and for the shade behind them. Returns the last two."""
        if not animate:
            self.moves, self.leave_ms = (), 0
            return [], []
        cx = (drawing.left + drawing.width / 2.0) * self.unit
        cy = (drawing.top + drawing.height / 2.0) * self.unit
        from_right = drawing.left + drawing.width / 2.0 >= cv.SCREEN_W / 2.0
        shown, leaving, beating = self.condition("ready"), self.condition("out"), self.condition("pulse")
        # the group lives in the screen's own units (the Studio zooms the group it sits in) ...
        group = cv.motion(options, (cx, cy), from_right, shown, leaving, beating)
        shade = cv.motion(options, (cx, cy), from_right, shown, leaving, beating, fade_only=True)
        # ... what is made here is placed on the window itself, so on the Studio's small screen its
        # distances and its centre are those of the small screen
        left, top, stage_zoom = self.base_stage or (0.0, 0.0, 100.0)
        s = stage_zoom / 100.0
        self.moves = tuple(cv.motion(options, (left + s * cx, top + s * cy), from_right, shown, leaving, beating, reach=s))
        self.leave_ms = cv.LEAVE_MS.get(options.leave, 160)
        return group, shade

    def draw(self, options, texts, focused="skip", animate=True, build=None):
        """``build`` is the function that makes the drawing (``skip_canvas.draw``; the Up Next popup has its own)."""
        import time

        started = time.time()
        if not self.offset:
            # The real dialog is unseen until its window calls ``reveal``: when everything is placed and sized
            # and the focus is where it starts. Should that call never come, it shows after three seconds.
            conceal()
            import threading

            timer = threading.Timer(3.0, reveal)
            timer.daemon = True
            timer.start()
        return self._draw(options, texts, focused, animate, build, started)

    def reveal(self):
        if not self.offset:
            reveal()

    def _draw(self, options, texts, focused, animate, build, started):
        import xbmcgui

        import time

        self.clear()
        self.options, self.focused = options, focused
        self.slot_times = []
        self.jobs = []  # places of skin-file controls, set together at the end of the drawing
        self.drawing = drawing = (build or cv.draw)(options, texts)
        self.timing_design_ms = int((time.time() - started) * 1000)
        # Size on screen: the group of the card and the buttons is zoomed around the drawing's anchor, and
        # what is made here follows with the same zoom
        seen = drawing.zoom / 100.0
        ax, ay = drawing.anchor[0] * self.unit, drawing.anchor[1] * self.unit
        if abs(seen - 1.0) < 1e-3:
            self.stage = self.base_stage
        else:
            left, top, stage_zoom = self.base_stage or (0.0, 0.0, 100.0)
            s = stage_zoom / 100.0
            self.stage = (left + s * ax * (1.0 - seen), top + s * ay * (1.0 - seen), stage_zoom * seen)
        group_moves, shade_moves = self._set_motion(options, drawing, animate)
        try:
            self.window.getControl(cv.ID_ZOOM + self.offset).setAnimations([(
                "conditional", "effect=zoom start=%.3f end=%.3f center=%.2f,%.2f time=0 condition=true"
                % (drawing.zoom, drawing.zoom, ax, ay))] + group_moves)
            behind = ["overlay9", "overlay"]
            if any((op["t"] == "pic" and op.get("shape") == "back") or op.get("slot") == "back_shade" for op in drawing.ops):
                behind += ["back", "back_shade"]  # Takeover: the picture behind everything comes and goes with the rest
            for slot in behind:
                self.window.getControl(cv.SLOT_IDS[slot] + self.offset).setAnimations(
                    shade_moves or [("conditional", "effect=fade start=100 end=100 time=0 condition=true")])
        except Exception:
            pass
        self.look = cv.adjusted(looks.look(options.look, drawing.corners), options)
        code, corners = options.look, drawing.corners
        slot_pictures = {
            "plate": cv.picture(code, corners, "plate", self.folder), "plate2": cv.picture(code, corners, "plate", self.folder),
            "box": cv.picture(code, corners, "box", self.folder), "chip": cv.picture(code, corners, "chip", self.folder),
            "plate_c": cv.picture(code, corners, "platec", self.folder),
            "plate_m": cv.picture(code, corners, "platem", self.folder),
            "plate_h": cv.picture(code, corners, "plate", self.folder),
            "box2": cv.picture(code, corners, "box", self.folder), "box3": cv.picture(code, corners, "box", self.folder),
            "outline": cv.picture(code, corners, "outl", self.folder),
        }
        for op in drawing.ops:
            kind = op["t"]
            if kind == "slot":
                name = op.get("tex") or slot_pictures.get(op["slot"], "")
                if name == "shadow":
                    name = "cv_shadow%s%s_%s.png" % ("_s" if op["slot"].startswith("shadow_s") else "",
                                                     "_h" if self.look["r"] == 0 else "", self.folder)
                elif name == "glow":
                    name = "cv_glow_%s_%s.png" % (code, self.folder)
                elif name == "frame":
                    name = cv.picture(code, corners, "frame", self.folder)
                if name in ("rd", "rdg"):
                    name = "cv_ov_%s_%s.png" % (name, self.folder)
                elif op["slot"] == "overlay" and name:
                    name = "cv_ov_%s.png" % name
                self._slot(op["slot"], name, op["rect"])
                if op.get("color"):
                    self.window.setProperty(cv.slot_property(op["slot"], self.offset) + "_c", looks.argb(op["color"])[2:])
            elif kind == "button":
                pill = op.get("pill")
                off = cv.picture(code, corners, op.get("off") if op.get("off") in ("tile", "ptile") else
                                 ("pill" if pill else "btn"), self.folder)
                on = cv.picture(code, corners, op.get("on") or ("pillfoc" if pill else "foc"), self.folder)
                which = op["which"]
                style = getattr(options, "focus_style", "Look")
                if style == "Outline" and not op.get("on"):
                    on = cv.picture(code, corners, "pillfocl" if pill else "focl", self.folder)
                if style != "Look" or self.tinted:
                    # Focus style: the plate of the button in focus in the accent colour, or as a line in the
                    # ink of the look. Set back to plain when a drawing before this one had coloured it.
                    tint = {"Accent": options.accent or self.look["acc"], "Outline": self.look["ink"]}.get(style, (255, 255, 255, 255))
                    try:
                        self.window.getControl(cv.SLOT_IDS[which + "_on"] + self.offset).setColorDiffuse(looks.argb(tint))
                        self.tinted = style != "Look"
                    except Exception:
                        pass
                if op.get("bare"):
                    # the button draws nothing itself (a disc made here stands for it): only its place
                    if not self.offset:
                        self._place(cv.ID_SKIP if which == "skip" else cv.ID_CLOSE, op["rect"])
                    continue
                if op.get("ghost"):
                    off = ""  # nothing behind it until it has the focus
                if op.get("off") == "ghost":
                    off = "cv_ghost_%s.png" % self.folder  # a dark pill on the bare video
                if self.offset:
                    # a preview copy: Skip has the focus, Close has not
                    self._slot(which + ("_on" if which == focused else "_off"), on if which == focused else off, op["rect"])
                else:
                    self._slot(which + "_off", off, op["rect"])
                    self._slot(which + "_on", on, op["rect"])
                    self._place(cv.BUTTON_IDS.get(which, cv.ID_CLOSE), op["rect"])
                    if which == "more":
                        self.window.setProperty("cv_hot_more", "1")
                        self.used.add("cv_hot_more")  # the third button is unseen until it is placed
            elif kind == "hot":
                # a place that takes the focus and draws nothing (a card of the Queue)
                if not self.offset and op.get("name") in cv.HOT_IDS:
                    self._place(cv.HOT_IDS[op["name"]], op["rect"])
                    self.window.setProperty("cv_hot_" + op["name"], "1")
                    self.used.add("cv_hot_" + op["name"])
            elif kind in ("rect", "img"):
                left, top, width, height = self._rect(op["rect"])
                name = "sl_white.png" if kind == "rect" else op["tex"]
                strength = outline_level(getattr(options, "text_outline", "Medium"))
                if op.get("shadow") and strength != "Off" and not drawing.overlaid:
                    for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
                        under = xbmcgui.ControlImage(left + dx, top + dy + PARK, width, height, self._path(name),
                                                     colorDiffuse=looks.argb((0, 0, 0, int(235 * OUTLINE[strength][0]))))
                        self._add(under, at=(left + dx, top + dy))
                        self._zoom(under)
                control = xbmcgui.ControlImage(left, top + PARK, width, height, self._path(name),
                                               colorDiffuse=looks.argb(self._ink(op)))
                self._add(control, op.get("key"), op, at=(left, top))
                self._zoom(control)
            elif kind == "fillslot":
                # a fill cut to the shape it lies in (the Skip tile, a pill): a picture slot above the buttons
                rounded = {"fill_h": self.look["rb"] > 100, "fill_p": self.look["rb"] > 100,
                           "fill_b": self.look["ri"] > 0}.get(op["slot"], self.look["r"] > 0)
                name = "cv_%s_%s.png" % (op["slot"], self.folder) if rounded else "sl_white.png"
                self._slot(op["slot"], name, op["rect"])
                try:
                    control = self.window.getControl(cv.SLOT_IDS[op["slot"]] + self.offset)
                    control.setColorDiffuse(looks.argb(self._ink(op)))
                    self.by_key[op["key"]] = (control, op)
                except Exception:
                    pass
            elif kind == "text":
                if op.get("shadow"):
                    self._shade(op)
                self._text(op)
            elif kind == "pic":
                # a picture of the library: a slot of the skin file, which cuts its corners
                shape = op.get("shape", "r")
                slot = {"back": "back", "logo": "logo", "s": "pic_s", "h": "pic_h", "r2": "pic2", "r3": "pic3",
                        "p": "pic_po", "ph": "pic_po_h", "card": "pic_card"}.get(shape, "pic")
                edges = getattr(options, "art_edges", "Look")
                if (self.look["ri"] == 0 if edges not in ("Straight", "Rounded") else edges == "Straight"):
                    # a look with hard corners, or Artwork edges Straight
                    slot = {"pic": "pic_h", "pic_s": "pic_h", "pic2": "pic2_h", "pic3": "pic3_h", "pic_po": "pic_po_h",
                            "pic_card": "pic_card_h"}.get(slot, slot)
                self._slot(slot, op.get("src") or "", op["rect"])
                if slot == "back" and op.get("src") and not op.get("own_shade"):
                    self._slot("back_shade", "cv_ov_take.png", op["rect"])
                    self.window.setProperty(cv.slot_property("back_shade", self.offset) + "_c", "FFFFFFFF")
            elif kind == "para":
                self._para(op)
            elif kind == "video":
                # Takeover + video: the window file's video window shows what is playing (where the window file has
                # it). The Studio's small screen has no video: a dark stand-in with a play mark takes its place.
                if self.offset:
                    import xbmcgui

                    left, top, width, height = self._rect(op["rect"])
                    control = xbmcgui.ControlImage(left, top + PARK, width, height, self._path("sl_white.png"),
                                                   colorDiffuse=looks.argb((8, 10, 14, 235)))
                    self._add(control, at=(left, top))
                    self._zoom(control)
                    size = min(width, height) // 4
                    mark = xbmcgui.ControlImage(left + (width - size) // 2, top + (height - size) // 2 + PARK, size, size,
                                                self._path("cv_ic_play.png"), colorDiffuse=looks.argb((255, 255, 255, 200)))
                    self._add(mark, at=(left + (width - size) // 2, top + (height - size) // 2))
                    self._zoom(mark)
                else:
                    self.window.setProperty("cv_video", "true")
                    self.used.add("cv_video")
        made_ms = int((time.time() - started) * 1000)
        places = len(self.jobs or [])
        place_ms = self._run_jobs()
        self.timing = {"build_ms": made_ms, "design_ms": self.timing_design_ms, "places": places, "place_ms": place_ms}
        self._flush()
        self.set_card(0)  # a design with cards to pick from: the first is the chosen one
        self.set_percent(texts.percent)
        self.timing["total_ms"] = int((time.time() - started) * 1000)
        return drawing

    def _shade(self, op):
        """A text on the video: a soft dark patch behind the line and dark copies under the letters."""
        import xbmcgui

        level = getattr(self.options, "text_shadow", "Mild")
        overlaid = getattr(self.drawing, "overlaid", False)
        if overlaid and level in ("Medium", "Strong", "Heavy"):
            level = "Mild"  # a shade already lies behind these texts
        copies, patch = SHADES.get(level, SHADES["Mild"])
        strength = outline_level(getattr(self.options, "text_outline", "Medium"))
        if strength != "Off" and not overlaid:
            # a dark line around the letters: dark copies, one towards each corner (and each side when Strong)
            dark, straight = OUTLINE[strength]
            reach = 2 if op["size"] >= 30 and strength != "Light" else 1
            around = [(dx * reach, dy * reach, dark) for dx in (-1, 1) for dy in (-1, 1)]
            if straight:
                around += [(dx * reach, dy * reach, dark) for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))]
            copies = tuple(around) + tuple(copies)
        x, y, w, h = op["rect"]
        size = op["size"]
        if patch:
            plain = str(op["text"]).replace("[B]", "").replace("[/B]", "")
            wide = min(w, cv.estimate(plain, size, op.get("bold")))
            align = op.get("align", "l")
            start = x + w - wide if align == "r" else (x + (w - wide) / 2.0 if align == "c" else x)
            left, top, width, height = self._rect((start - size * 1.3, y + h / 2.0 - size * 1.4, wide + 2.6 * size, size * 2.8))
            control = xbmcgui.ControlImage(left, top + PARK, width, height, self._path("cv_txglow.png"),
                                           colorDiffuse=looks.argb((0, 0, 0, int(255 * patch))))
            self._add(control, at=(left, top))
            self._zoom(control)
        for index, (dx, dy, dark) in enumerate(copies):
            self._text(dict(op, rect=(x + dx, y + dy, w, h), color=(0, 0, 0, int(255 * dark)), key=None, ink=None,
                            shadow_of="%s:%d" % (op.get("key") or id(op), index)))

    def _slot(self, slot, name, rect):
        import time

        t0 = time.time()
        self.window.setProperty(cv.slot_property(slot, self.offset), name)
        self.used.add(cv.slot_property(slot, self.offset))
        t1 = time.time()
        self._place(cv.SLOT_IDS[slot] + self.offset, rect)
        self.slot_times.append((slot, int((t1 - t0) * 1000), int((time.time() - t1) * 1000)))

    def _place(self, control_id, rect):
        """Put a control of the skin file at its place. While a drawing is being made the places are
        collected and set side by side at its end (``_run_jobs``)."""
        if self.jobs is not None:
            self.jobs.append((control_id, rect))
            return
        self._place_now(control_id, rect)

    def _place_now(self, control_id, rect):
        try:
            control = self.window.getControl(control_id)
        except Exception:
            return
        left, top, width, height = self._rect(rect)
        try:
            control.setPosition(left, top)
            control.setWidth(width)
            control.setHeight(height)
        except Exception:
            pass

    def _run_jobs(self):
        """Set the collected places. Every call into Kodi waits until it has drawn its frame (some 30 to 40
        ms on a box that is playing video), and a control needs four of them; one after the other that is
        a second and more for a dialog. Side by side they share the frames."""
        import time

        jobs, self.jobs = self.jobs or [], None
        started = time.time()
        _side_by_side([(self._place_now, job) for job in jobs])
        return int((time.time() - started) * 1000)

    def _text(self, op):
        import xbmcgui

        left, top, width, height = self._rect(op["rect"])
        font, percent, wrap = pick_font(self.fonts, op["size"] * self.unit, op.get("bold"))
        z = percent / 100.0
        align = op.get("align", "l")
        # the label is laid out at the font's own size and zoomed around its anchor to the wanted one
        box_w, box_h = max(1, int(round(width / z))), max(1, int(round(height / z)))
        if align == "r":
            anchor = (left + width, top + height / 2.0)
            x = left + width - box_w
        elif align == "c":
            anchor = (left + width / 2.0, top + height / 2.0)
            x = int(round(left + width / 2.0 - box_w / 2.0))
        else:
            anchor = (left, top + height / 2.0)
            x = left
        y = int(round(top + height / 2.0 - box_h / 2.0))
        op = dict(op, font=font, wrap=wrap, placed=(x, y, z, op["rect"][0]))
        control = xbmcgui.ControlLabel(x, y + PARK, box_w, box_h, self._shown(op), font=font,
                                       textColor=looks.argb(self._ink(op)), alignment=_ALIGN[align])
        self._add(control, op.get("key") or ("shade:%s" % op["shadow_of"] if op.get("shadow_of") else None), op, at=(x, y))
        self._zoom(control, anchor, percent)

    def _para(self, op):
        """A text of several lines (a plot): a text box, its font zoomed to the wanted size."""
        import xbmcgui

        left, top, width, height = self._rect(op["rect"])
        font, percent, _wrap = pick_font(self.fonts, op["size"] * self.unit, False)
        z = percent / 100.0
        if op.get("lines"):
            # a text box cuts by the pixel: it is exactly as high as its lines, so no half line shows
            height = int(op["lines"] * op["size"] * self.unit * 1.22)
        try:
            control = xbmcgui.ControlTextBox(left, top + PARK, max(1, int(round(width / z))), max(1, int(round(height / z))),
                                             font=font, textColor=looks.argb(self._ink(op)))
        except Exception:
            return
        self._add(control, op.get("key"), op, at=(left, top))
        self.pending_texts.append((control, str(op.get("text") or "")))
        self._zoom(control, (left, top), percent)

    def _shown(self, op) -> str:
        text = "[B]%s[/B]" % op["text"] if op.get("wrap") else op["text"]
        if op.get("ink") or op.get("ink_acc"):
            # What is written on a button changes colour with the focus. A label keeps the colour it was made
            # with (Kodi does not take a new one with a new text), so the colour is written into the text.
            text = "[COLOR %s]%s[/COLOR]" % (looks.argb(self._ink(op))[2:], text)
        return text

    # ------------------------------------------------------------------ updates
    def set_text(self, key, text):
        for index in range(12):
            shade = self.by_key.get("shade:%s:%d" % (key, index))
            if not shade:
                break
            shade[1]["text"] = text
            try:
                shade[0].setLabel(self._shown(shade[1]), textColor=looks.argb(shade[1]["color"]))
            except Exception:
                pass
        found = self.by_key.get(key)
        if found:
            control, op = found
            op["text"] = text
            try:
                control.setLabel(self._shown(op), textColor=looks.argb(self._ink(op)))
            except Exception:
                pass

    def set_percent(self, percent):
        """Move the bar: the fill is as wide as this share of its track."""
        ring = self.by_key.get("ring")
        if ring:
            name = cv.ring_frame(percent)
            if ring[1].get("tex") != name:
                ring[1]["tex"] = name
                try:
                    ring[0].setImage(self._path(name))
                except Exception:
                    pass
        share = max(0.0, min(100.0, float(percent))) / 100.0
        for key in ("playhead", "arc", "now", "fillcap"):
            self._follow(key, share)
        found = self.by_key.get("fill")
        if not found:
            return
        control, op = found
        x, y, w, h = op["track"]
        if op.get("reveal"):
            # a veil that gives the picture free from the left as the time runs
            left = self._u(x + w * share)
            width = self._u(x + w) - left
            try:
                control.setPosition(left, self._u(y))
                control.setWidth(max(1, width))
                control.setVisible(width > 0)
            except Exception:
                pass
            return
        least = op.get("min")
        if least:
            # a fill cut to a round shape cannot be smaller than its round end: under that it fades in
            extent = (h if op.get("vertical") else w) * share
            colour = self._ink(op)
            colour = colour[:3] + (int(colour[3] * min(1.0, extent / least)),)
            extent = min(max(extent, least), (h if op.get("vertical") else w) - op.get("stop", 0.0))
            share = extent / (h if op.get("vertical") else w) if share > 0 else 0.0
            try:
                control.setColorDiffuse(looks.argb(colour))
            except Exception:
                pass
        if op.get("vertical"):
            # a fill that rises from the foot of its track
            bottom = self._u(y + h)
            height = max(1, bottom - self._u(y + h * (1.0 - share))) if share > 0 else 1
            try:
                control.setPosition(self._u(x), bottom - height)
                control.setHeight(height)
                control.setVisible(share > 0)
            except Exception:
                pass
            return
        width = max(1, self._u(x + w * share) - self._u(x)) if share > 0 else 1
        try:
            control.setWidth(width)
            control.setVisible(share > 0)
        except Exception:
            pass

    def _follow(self, key, share):
        """Move what stands at the playhead: the mark itself, the arc that starts there, the time under it."""
        found = self.by_key.get(key)
        if not found or not found[1] or "follow" not in found[1]:
            return
        control, op = found
        follow = op["follow"]
        head = follow["x0"] + follow["span"] * share
        x, y, w, h = op["rect"]
        try:
            if follow["mode"] == "arc":
                op["rect"] = (head, y, max(4.0, follow["end"] - head), h)
                left, top, width, height = self._rect(op["rect"])
                control.setPosition(left, top)
                control.setWidth(width)
            elif follow["mode"] == "label":
                # a label is zoomed around a fixed point, so a step of its own counts for that much less
                x0, y0, zoom, left0 = op["placed"]
                step = ((head - w / 2.0) - left0) * self.unit / zoom
                control.setPosition(int(round(x0 + step)), y0)
            else:
                op["rect"] = (head - w / 2.0, y, w, h)
                left, top, _width, _height = self._rect(op["rect"])
                control.setPosition(left, top)
        except Exception:
            pass

    def set_card(self, index):
        """The Queue: this card is the chosen one. The frame moves to it and the others are dimmed."""
        cards = [op for op in self.drawing.ops if op["t"] == "hot"] if self.drawing else []
        if not cards:
            return
        index = max(0, min(len(cards) - 1, int(index)))
        x, y, w, h = cards[index]["rect"]
        h = w * cards[index].get("ratio", h / w)  # the frame stands around the picture, not the lines under it
        self._place(cv.SLOT_IDS["outline"] + self.offset, (x - 6, y - 6, w + 12, h + 12))
        for number in range(len(cards)):
            found = self.by_key.get("veil%d" % number)
            if found:
                try:
                    found[0].setVisible(number != index)
                except Exception:
                    pass

    def set_focus(self, which):
        """Skip or Close has the focus: what is written on the two buttons changes colour."""
        if which == self.focused:
            return
        self.focused = which
        for key, (control, op) in self.by_key.items():
            if not op or not (op.get("ink") or op.get("ink_acc") or op.get("bg")):
                continue
            colour = looks.argb(self._ink(op))
            try:
                if op["t"] == "text":
                    control.setLabel(self._shown(op), textColor=colour)
                else:
                    control.setColorDiffuse(colour)
            except Exception:
                pass
