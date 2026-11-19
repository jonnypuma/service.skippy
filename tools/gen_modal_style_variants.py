# -*- coding: utf-8 -*-
"""Write the per-look copies of the styled windows.

    python3 tools/gen_modal_style_variants.py           # write Name_<code>.xml next to each Name.xml
    python3 tools/gen_modal_style_variants.py --check   # exit 1 when a copy is missing or stale

``Name.xml`` is the Fused Glass Frost file and the only one to edit. A copy differs from it in
nothing but the texture prefix (``ms_fgf_`` -> ``ms_<code>_``): Kodi does not let a button take its
textures from a window property, so each look needs its own file. Runs over both ``720p`` and
``1080i`` (each folder's copies come from that folder's own file, so hand-tuned 1080i files keep
their values).
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import skippy_modal_style as style  # noqa: E402

SKINS = os.path.join(ROOT, "resources", "skins", "default")
RESOLUTIONS = ("720p", "1080i")
BASE_PREFIX = "ms_%s_" % style.DEFAULT_CODE


def variant_text(base_text: str, code: str) -> str:
    return base_text.replace(BASE_PREFIX, "ms_%s_" % code)


def expected() -> dict:
    """Path of every copy -> the text it must have."""
    out = {}
    for res in RESOLUTIONS:
        for base in style.STYLED_WINDOWS:
            path = os.path.join(SKINS, res, base)
            with open(path, encoding="utf-8", newline="") as handle:
                text = handle.read()
            for key, code in style.STYLE_CODES.items():
                if code == style.DEFAULT_CODE:
                    continue
                out[os.path.join(SKINS, res, style.xml_name(base, key))] = variant_text(text, code)
    return out


def stale() -> list:
    bad = []
    for path, text in expected().items():
        try:
            with open(path, encoding="utf-8", newline="") as handle:
                if handle.read() != text:
                    bad.append(path)
        except OSError:
            bad.append(path)
    return bad


def main(argv) -> int:
    if "--check" in argv:
        bad = stale()
        for path in bad:
            print("stale or missing:", os.path.relpath(path, ROOT))
        return 1 if bad else 0
    for path, text in expected().items():
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
    print("wrote %d files" % len(expected()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
