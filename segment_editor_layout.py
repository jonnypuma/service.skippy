# -*- coding: utf-8 -*-
"""Which layout the segment editor opens in, and the arithmetic of its timeline.

Three layouts, one setting (``segment_editor_layout``), the same 39 buttons and control ids in each:

* ``side``    - the segments in a list at the left, everything else in a drawer along the bottom
  (``SegmentEditorDialogA.xml``); the default;
* ``drawer``  - everything in one drawer along the bottom, the segments as a row of chips
  (``SegmentEditorDialogB.xml``);
* ``classic`` - the large panel of earlier versions (``SegmentEditorDialog.xml``), whose nine row
  buttons follow the highlighted row.

The two new files are written by ``tools/gen_segment_editor_layouts.py``. Nothing here needs Kodi.
"""
from __future__ import annotations

from collections import namedtuple

SETTING_KEY = "segment_editor_layout"
LAYOUT_SIDE, LAYOUT_DRAWER, LAYOUT_CLASSIC = "side", "drawer", "classic"
LAYOUTS = (LAYOUT_SIDE, LAYOUT_DRAWER, LAYOUT_CLASSIC)
DEFAULT_LAYOUT = LAYOUT_SIDE
LAYOUT_NAMES = {LAYOUT_SIDE: "List and drawer", LAYOUT_DRAWER: "Drawer", LAYOUT_CLASSIC: "Classic"}
XML_FILES = {
    LAYOUT_SIDE: "SegmentEditorDialogA.xml",
    LAYOUT_DRAWER: "SegmentEditorDialogB.xml",
    LAYOUT_CLASSIC: "SegmentEditorDialog.xml",
}

# Timeline controls (only the two new layouts have them).
TRACK_ID = 5099
BLOCK_IDS = tuple(range(5100, 5120))
PLAYHEAD_ID = 5130
SELECTED_MARK_ID = 5131
END_LABEL_ID = 5132
MIN_BLOCK_WIDTH = 6
# List and drawer (round 3): times under the track, a frame round the highlighted segment, a word in
# every block, and a thin bar over the track that stands for the whole file.
TIME_START_ID, TIME_END_ID, TIME_NOW_ID = 5133, 5134, 5135
OUTLINE_ID = 5138
BLOCK_LABEL_IDS = tuple(range(5140, 5160))
OVERVIEW_ID = 5139
OVERVIEW_BLOCK_IDS = tuple(range(5160, 5180))
OVERVIEW_WINDOW_ID = 5180
TITLE_BOX_ID = 5181  # where the large "4 segments" is drawn
# Layout A in 720p units: its list panel, the place of the title inside it, the title's size, the track's width
PANEL_A = (16, 33, 424, 657)
TITLE_BOX = (19, 36, 386, 34)
TITLE_SIZE = 28
TRACK_A_WIDTH = 771
MIN_SPAN = 20.0  # the track never shows less than this many seconds
ROOM = 0.34  # how much more than the connected segments the track shows (the mockup: 2:14 of segments on 3:00)
JOIN_GAP = 2.0  # segments this close count as connected
TIME_SEG_START_ID, TIME_SEG_END_ID = 5136, 5137  # the times under the highlighted segment's ends
HANDLE_IDS = (5182, 5183)  # the two handles inside the highlighted block
PLAYHEAD_HEAD_ID = 5184  # the marker on top of the playhead
# The small labels of the List and drawer layout. The skin's smallest font is larger than the mockup's
# small capitals, so the editor zooms these to size: (id, how the text is aligned in its box).
KICKER_ID, HEAD_TIMELINE_ID, HEAD_SEEK_ID, HEAD_MARK_ID, HEAD_FILE_ID, HEAD_SELECTED_ID = 5185, 5186, 5187, 5188, 5189, 5190
TAG_LIVE_ID, TAG_OVERLAY_ID = 5191, 5192
HEAD_LOOK_ID = 5193  # the header of the Look row
SMALL_LABELS = (
    (KICKER_ID, "l"), (HEAD_TIMELINE_ID, "l"), (HEAD_SEEK_ID, "l"), (HEAD_MARK_ID, "l"), (HEAD_FILE_ID, "l"),
    (HEAD_SELECTED_ID, "l"), (HEAD_LOOK_ID, "l"), (END_LABEL_ID, "r"), (TAG_LIVE_ID, "c"), (TAG_OVERLAY_ID, "c"),
    (TIME_START_ID, "l"), (TIME_END_ID, "r"),
)
# labels the editor moves about: they are zoomed around their own middle
MOVING_LABELS = (TIME_NOW_ID, TIME_SEG_START_ID, TIME_SEG_END_ID) + BLOCK_LABEL_IDS
SMALL_SIZE = 15.0  # the mockup's small capitals, in pixels of a 1080 screen
SMALL_FONT = "font10"  # the font these labels are written in
SOURCE_NAMES = {"edl": "Local EDL", "chapters": "Chapters", "chapter": "Chapters", "theintrodb": "TheIntroDB",
                "introdb": "IntroDB.app", "xml": "Chapter file", "nfo": "NFO", "manual": "Manual", "user": "Manual"}
LABEL_MIN_WIDTH = 44  # a block narrower than this has no word in it

# Colour chip per segment type: the texture seg_<key>.png (tools/gen_modal_style_textures.py).
CHIP_COLORS = {
    "intro": "E8B04B", "recap": "7FB4FF", "commercial": "FF5C6C", "prologue": "45D0C0", "preview": "C8DC4A",
    "credits": "B494FF", "epilogue": "F08BD0", "bts": "6FD08A", "featurette": "E8793A", "main": "CFD4DC",
    "segment": "8A93A3", "other": "8A93A3",
    # for a type the user added (Segment keywords): each gets one of these by its name, and keeps it
    "extra1": "5AD1F0", "extra2": "F0D06A", "extra3": "A0E05A", "extra4": "F09A9A", "extra5": "9AA8FF",
    "extra6": "E07AF0", "extra7": "4FC79A", "extra8": "D9A066",
}
EXTRA_COLOURS = 8
_CHIP_ALIASES = {
    "behind the scenes": "bts", "behind_the_scenes": "bts", "behindthescenes": "bts",
    "cold open": "prologue", "cold_open": "prologue", "outro": "credits", "ad": "commercial", "ads": "commercial",
    "advertisement": "commercial", "opening": "intro", "ending": "credits", "trailer": "preview",
}

Block = namedtuple("Block", "left width texture index")


# The List and drawer layout has a look of its own, chosen in the editor (its Look row): Fused Glass
# Dark (the default, the look it was drawn in, like the Studio), Frost or Clear. The other two layouts
# follow the Window style setting.
STYLE_KEY = "segment_editor_style"
EDITOR_STYLES = ("fg_dark", "fg_frost", "fg_clear")
DEFAULT_STYLE = EDITOR_STYLES[0]
LOOK_BUTTON_IDS = (5044, 5045, 5046)  # the Look row: the dark overlay, the panels, the video small or full screen
VIDEO_ID = 5048  # List and drawer: the video window above the timeline (drawn while Window.Property(ed_video) is true)
# where it is, in pixels of a 720 screen: over the drawer, under the two tags, 16:9
VIDEO_RECT = (562, 72, 592, 333)
VIDEO_KEY = "segment_editor_small_video"  # the setting: the video small above the timeline (true) or full screen
STAGE_XML = "SkipVideoStageEditor.xml"  # the plain window under the editor while the video is small (video_stage)


def editor_style(value) -> str:
    key = str(value or "").strip().lower()
    return key if key in EDITOR_STYLES else DEFAULT_STYLE


def next_style(style) -> str:
    return EDITOR_STYLES[(EDITOR_STYLES.index(editor_style(style)) + 1) % len(EDITOR_STYLES)]


def style_for(layout, addon=None):
    """The window look of a layout (a key of skippy_modal_style): the editor's own choice for List and
    drawer (the default when no add-on is given or the setting cannot be read), None for a layout that
    follows the Window style setting."""
    if normalize(layout) != LAYOUT_SIDE:
        return None
    try:
        return editor_style(addon.getSetting(STYLE_KEY)) if addon is not None else DEFAULT_STYLE
    except Exception:
        return DEFAULT_STYLE


def normalize(value, default=DEFAULT_LAYOUT) -> str:
    key = str(value or "").strip().lower()
    return key if key in LAYOUTS else default


def current_layout(addon=None) -> str:
    """The layout the user chose; the default when the setting cannot be read."""
    try:
        if addon is None:
            import xbmcaddon  # late: unit tests load this module without Kodi

            addon = xbmcaddon.Addon()
        return normalize(addon.getSetting(SETTING_KEY))
    except Exception:
        return DEFAULT_LAYOUT


def small_video(addon) -> bool:
    """The List and drawer layout shows the video small above the timeline (the default) or full screen."""
    try:
        return (addon.getSetting(VIDEO_KEY) or "true").lower() != "false"
    except Exception:
        return True


def xml_base(layout) -> str:
    """The XML file of a layout, before the window look is applied to its name."""
    return XML_FILES[normalize(layout)]


def chip_key(label) -> str:
    """The colour key of a segment label: a built-in type, a spare colour for a type of the user's own, or
    ``other`` for no name at all."""
    key = str(label or "").strip().lower()
    key = _CHIP_ALIASES.get(key, key)
    key = key.replace(" ", "_")
    key = _CHIP_ALIASES.get(key, key)
    if key in CHIP_COLORS and not key.startswith("extra"):
        return key
    if not key:
        return "other"
    # A type of the user's own: one of the spare colours, chosen by its name. The same name has the same
    # colour on every device and after every restart; nobody has to pick one.
    import zlib

    return "extra%d" % (zlib.crc32(key.encode("utf-8")) % EXTRA_COLOURS + 1)


def chip_texture(label) -> str:
    return "seg_%s.png" % chip_key(label)


def clock(seconds) -> str:
    """``m:ss`` or ``h:mm:ss`` for a time in the video (``0:00`` for none)."""
    try:
        total = max(0, int(float(seconds)))
    except (TypeError, ValueError):
        total = 0
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return "%d:%02d:%02d" % (hours, minutes, secs) if hours else "%d:%02d" % (minutes, secs)


def block_word(name, length, width, per_letter=9.6, pad=18.0) -> str:
    """What is written in a block ``width`` wide (720p units): the name with its length when both fit,
    the name alone when only that fits, nothing when even that would be cut."""
    name = str(name or "").upper()
    both = "%s · %s" % (name, length) if length else name
    for text in (both, name):
        if text and len(text) * per_letter + pad <= width:
            return text
    return ""


def small_zoom(font_size, wanted=SMALL_SIZE) -> float:
    """The zoom (1.0 = none) that brings a font of ``font_size`` pixels to the mockup's small size. A font
    that is already that small, or whose size is not known, is left alone."""
    try:
        font_size = float(font_size)
    except (TypeError, ValueError):
        return 1.0
    if font_size <= wanted * 1.04:
        return 1.0
    return max(0.5, wanted / font_size)


def source_name(source) -> str:
    """How a segment's source is written in the list: Local EDL, Chapters, TheIntroDB ..."""
    text = str(source or "").strip()
    return SOURCE_NAMES.get(text.lower(), text)


def block_texture(label) -> str:
    """The picture of a block on the zoomed track: the type's colour with round corners."""
    return "segb_%s.png" % chip_key(label)


def connected_span(segments, index, gap=JOIN_GAP):
    """From where to where the group of segments reaches that the segment ``index`` belongs to: every
    segment that touches or overlaps it, directly or through others (an intro right after a recap,
    a preview inside the credits). ``segments`` is a sequence of ``(start, end, ...)``. None when
    there is no such segment."""
    spans = []
    for item in segments:
        try:
            spans.append((float(item[0]), float(item[1])))
        except (TypeError, ValueError, IndexError):
            spans.append(None)
    if not (0 <= index < len(spans)) or spans[index] is None:
        return None
    first, last = spans[index]
    grown = True
    while grown:
        grown = False
        for span in spans:
            if span is None:
                continue
            start, end = span
            if start <= last + gap and end >= first - gap and (start < first or end > last):
                first, last = min(first, start), max(last, end)
                grown = True
    return first, last


def timeline_window(segment, duration, min_span=MIN_SPAN, room=ROOM) -> tuple:
    """The stretch of the file the track shows. ``segment`` is ``(start, end)`` of what has to be on it:
    the highlighted segment with those connected to it (``connected_span``). The stretch is that and
    ``room`` more, shared between both sides (all of it at one side when the other is the start or the
    end of the file), and never less than ``min_span`` seconds; the whole file when nothing is
    highlighted or the file is that short. In a long film a segment is a sliver of the whole: this
    keeps the group that is being worked on as wide as the track."""
    try:
        duration = float(duration or 0)
    except (TypeError, ValueError):
        duration = 0.0
    if duration <= 0:
        return 0.0, 0.0
    if not segment or duration <= min_span:
        return 0.0, duration
    try:
        start, end = float(segment[0]), float(segment[1])
    except (TypeError, ValueError, IndexError):
        return 0.0, duration
    span = min(duration, max(min_span, (end - start) * (1.0 + room)))
    first = min(max(0.0, (start + end) / 2.0 - span / 2.0), duration - span)
    return first, first + span


def window_blocks(segments, first, last, track_width, max_blocks=len(BLOCK_IDS), min_width=MIN_BLOCK_WIDTH):
    """``timeline_blocks`` for a track that shows the stretch ``first`` to ``last`` of the file: a
    segment outside it has no block, one that crosses its end is cut there."""
    try:
        first, last, track_width = float(first), float(last), int(track_width or 0)
    except (TypeError, ValueError):
        return []
    span = last - first
    if span <= 0 or track_width <= 0:
        return []
    out = []
    for index, (start, end, label) in enumerate(segments):
        if len(out) >= max_blocks:
            break
        try:
            start, end = float(start), float(end)
        except (TypeError, ValueError):
            continue
        if end <= first or start >= last:
            continue
        start, end = max(start, first), min(max(end, start), last)
        left = int(round((start - first) / span * track_width))
        width = max(int(round((end - start) / span * track_width)), min(min_width, track_width))
        if left + width > track_width:
            left = max(0, track_width - width)
        out.append(Block(left, width, chip_texture(label), index))
    return out


def window_offset(seconds, first, last, track_width) -> int:
    """Where a time stands on the track that shows ``first`` to ``last``; -1 when it is outside."""
    try:
        seconds, first, last, track_width = float(seconds), float(first), float(last), int(track_width or 0)
    except (TypeError, ValueError):
        return -1
    if last <= first or track_width <= 0 or seconds < first or seconds > last:
        return -1
    return int(round((seconds - first) / (last - first) * track_width))


def timeline_blocks(segments, duration, track_width, max_blocks=len(BLOCK_IDS), min_width=MIN_BLOCK_WIDTH):
    """Where each segment sits on a track ``track_width`` wide that stands for ``duration`` seconds.

    ``segments`` is a sequence of ``(start_seconds, end_seconds, label)`` in list order. Returns
    ``Block(left, width, texture, index)`` for the first ``max_blocks`` of them; a segment is never
    narrower than ``min_width`` and never leaves the track. Nothing without a duration or a track.
    """
    try:
        duration = float(duration or 0)
        track_width = int(track_width or 0)
    except (TypeError, ValueError):
        return []
    if duration <= 0 or track_width <= 0:
        return []
    out = []
    for index, (start, end, label) in enumerate(segments):
        if len(out) >= max_blocks:
            break
        try:
            start, end = float(start), float(end)
        except (TypeError, ValueError):
            continue
        start = min(max(start, 0.0), duration)
        end = min(max(end, start), duration)
        left = int(round(start / duration * track_width))
        width = max(int(round((end - start) / duration * track_width)), min(min_width, track_width))
        if left + width > track_width:
            left = max(0, track_width - width)
        out.append(Block(left, width, chip_texture(label), index))
    return out


def playhead_left(current, duration, track_width) -> int:
    """Offset of the playhead on the track, or -1 when it cannot be placed."""
    try:
        current, duration, track_width = float(current), float(duration or 0), int(track_width or 0)
    except (TypeError, ValueError):
        return -1
    if duration <= 0 or track_width <= 0:
        return -1
    return int(round(min(max(current, 0.0), duration) / duration * track_width))


def short_time(seconds) -> str:
    """``h:mm:ss`` or ``m:ss`` for the end of the track."""
    try:
        total = int(round(float(seconds)))
    except (TypeError, ValueError):
        return ""
    if total <= 0:
        return ""
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return "%d:%02d:%02d" % (hours, minutes, secs) if hours else "%d:%02d" % (minutes, secs)
