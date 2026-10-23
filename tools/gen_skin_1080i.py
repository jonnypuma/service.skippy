"""Generate the 1080i skin XMLs from the 720p ones (the 720p files are the source of truth).

Layout numbers are multiplied by 1.5 (rounded half up), so a layout change is made once,
in ``resources/skins/default/720p``, then ``python tools/gen_skin_1080i.py`` rewrites 1080i.
Default run only reports drift (differences beyond +-1px rounding); ``--write`` only creates
missing 1080i files; ``--overwrite`` regenerates every file not listed in ``MANUAL`` (this
changes hand-tuned values by up to 1px, so review the diff). Exit code 1 when drift is found.
Files ending in ``-Jon.xml`` are personal variants and are left alone.
"""
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "resources", "skins", "default")
SRC, DST = os.path.join(ROOT, "720p"), os.path.join(ROOT, "1080i")
FACTOR = 1.5

# Tags whose numeric text is a screen distance.
_TAGS = (
    "posx|posy|left|top|right|bottom|width|height|textoffsetx|textoffsety|textwidth|"
    "shadowoffsetx|shadowoffsety|itemgap|spacing|padding|offsetx|offsety|radiusx|radiusy|textspace"
)
_NUM = r"-?\d+(?:\.\d+)?"


def _s(v):
    n = float(v) * FACTOR
    r = int(n + 0.5) if n >= 0 else -int(-n + 0.5)
    return str(r)


def _scale_pair(text):
    return ",".join(_s(p) if re.fullmatch(_NUM, p.strip()) else p for p in text.split(","))


def convert(xml):
    # <width>430</width> and friends (plain numbers only; "auto", "100%" and infolabels are kept).
    xml = re.sub(
        r"(<(?:%s)(?: [^>]*)?>)(%s)(</)" % (_TAGS, _NUM),
        lambda m: m.group(1) + _s(m.group(2)) + m.group(3),
        xml,
    )
    # <effect type="slide" start="0,-150" end="0,0" ...>
    def effect(m):
        tag = m.group(0)
        if 'type="slide"' not in tag:
            return tag
        return re.sub(
            r'\b(start|end)="([^"]*)"', lambda a: '%s="%s"' % (a.group(1), _scale_pair(a.group(2))), tag
        )

    xml = re.sub(r"<effect\b[^>]*>", effect, xml)
    # <itemlayout width="960" height="48"> sizes
    return re.sub(
        r"<((?:item|focused)layout)\b([^>]*)>",
        lambda m: "<%s%s>" % (
            m.group(1),
            re.sub(r'\b(width|height)="(%s)"' % _NUM, lambda a: '%s="%s"' % (a.group(1), _s(a.group(2))), m.group(2)),
        ),
        xml,
    )


# The other three corner files are derived from the *_TopLeft master (720p): only the window
# position and the slide direction differ. Values are (posx, posy) of the panel group.
CORNERS = {
    "SkipDialog": {"TopRight": (840, 0), "BottomLeft": (10, 620), "BottomRight": (840, 620)},
    "Minimal_Skip_Dialog": {"TopRight": (1045, 0), "BottomLeft": (10, 674), "BottomRight": (1045, 674)},
}


def derive_corner(top_left_xml, posx, posy):
    head, sep, rest = top_left_xml.partition('<control type="group"')  # window coords stay as is
    rest = re.sub(r"(<posx>)10(</posx>)", r"\g<1>%d\g<2>" % posx, rest, count=1)
    rest = re.sub(r"(<posy>)0(</posy>)", r"\g<1>%d\g<2>" % posy, rest, count=1)
    xml = head + sep + rest
    if posy:  # bottom corners slide in from / out to the bottom
        xml = xml.replace('end="0,-100"', 'end="0,100"').replace('start="0,-150"', 'start="0,150"')
    return xml


def corner_sources():
    """``{filename: expected 720p text}`` for the derived corner files."""
    out = {}
    for base, corners in CORNERS.items():
        with open(os.path.join(SRC, "%s_TopLeft.xml" % base), encoding="utf-8", newline="") as fh:
            master = fh.read()
        for corner, (x, y) in corners.items():
            out["%s_%s.xml" % (base, corner)] = derive_corner(master, x, y)
    return out


# Files whose 1080i version is intentionally different (own fonts / extra controls); never rewritten.
MANUAL = {"SegmentEditorDialog.xml", "SegmentMarkerTypePicker.xml", "SkipDialog.xml"}


def _norm_lines(text):
    out = []
    for line in text.replace("\r", "").splitlines():
        line = line.strip()
        if line and not line.startswith("<?xml"):
            out.append(line)
    return out


def drift(expected, actual):
    """Human-readable differences beyond rounding (+-1), slide offsets and fonts."""
    a, b = _norm_lines(expected), _norm_lines(actual)
    if len(a) != len(b):
        return ["line count %d (from 720p) vs %d (1080i)" % (len(a), len(b))]
    found = []
    for n, (x, y) in enumerate(zip(a, b), 1):
        if x == y or "type=\"slide\"" in x or x.startswith("<font>"):
            continue
        if re.sub(_NUM, "#", x) != re.sub(_NUM, "#", y):
            if re.search(r"<font>", x) and re.search(r"<font>", y):
                continue
            found.append("line %d: %s  <>  %s" % (n, x[:60], y[:60]))
            continue
        nx, ny = re.findall(_NUM, x), re.findall(_NUM, y)
        if any(abs(float(p) - float(q)) > 1 for p, q in zip(nx, ny)):
            found.append("line %d: %s  <>  %s" % (n, x[:60], y[:60]))
    return found


def main(argv):
    write = "--write" in argv or "--overwrite" in argv
    overwrite = "--overwrite" in argv
    problems = 0
    for name, expected in sorted(corner_sources().items()):
        path = os.path.join(SRC, name)
        with open(path, encoding="utf-8", newline="") as fh:
            current = fh.read()
        if current != expected:
            problems += 1
            print("%s: 720p corner differs from its TopLeft master" % name)
            if write:
                with open(path, "w", encoding="utf-8", newline="") as fh:
                    fh.write(expected)
                print("%s: rewritten from TopLeft" % name)
    for name in sorted(os.listdir(SRC)):
        if not name.endswith(".xml") or name.endswith("-Jon.xml"):
            continue
        with open(os.path.join(SRC, name), encoding="utf-8", newline="") as fh:
            out = convert(fh.read())
        dst_path = os.path.join(DST, name)
        old = ""
        if os.path.exists(dst_path):
            with open(dst_path, encoding="utf-8", newline="") as fh:
                old = fh.read()
        if name in MANUAL:
            print("%s: manual file, skipped" % name)
            continue
        diffs = drift(out, old) if old else ["missing"]
        if diffs:
            problems += 1
            print("%s: DRIFT" % name)
            for d in diffs[:5]:
                print("    " + d)
        if write and (not old or (overwrite and old != out)):
            with open(dst_path, "w", encoding="utf-8", newline="") as fh:
                fh.write(out)
            print("%s: rewritten from 720p" % name)
    print("Drift in %d file(s)." % problems)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
