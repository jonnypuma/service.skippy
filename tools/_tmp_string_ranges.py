# -*- coding: utf-8 -*-
"""Report contiguous used strings.po id ranges (scratch helper)."""
import io
import os
import re

path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "resources",
    "language",
    "English",
    "strings.po",
)
text = io.open(path, encoding="utf-8").read()
ids = sorted(set(int(m) for m in re.findall(r'msgctxt "#(\d+)"', text)))
print("count", len(ids), "max", max(ids))
groups = []
start = prev = ids[0]
for i in ids[1:]:
    if i != prev + 1:
        groups.append((start, prev))
        start = i
    prev = i
groups.append((start, prev))
for a, b in groups:
    print("%d-%d" % (a, b) if a != b else str(a))
