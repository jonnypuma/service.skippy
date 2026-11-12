#!/usr/bin/env python3
"""pyflakes over the add-on's own Python files (``-Jon`` variants and scratch files skipped).

Re-export imports marked ``# noqa: F401`` are not reported: pyflakes itself ignores that
marker, and the facades (``remote_segments.py`` and friends) import names on purpose.
Exit code 1 when anything is reported. Run from the add-on root:

    python3 tools/lint.py
"""

import os
import sys

try:
    from pyflakes import api, messages, reporter
except ImportError:
    sys.exit("pyflakes is not installed: pip install --user pyflakes")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def python_files():
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
        for name in sorted(files):
            if not name.endswith(".py") or "-Jon" in name:
                continue
            if os.path.basename(base) == "tools" and name.startswith("_"):
                continue
            yield os.path.join(base, name)


class _Collect(reporter.Reporter):
    def __init__(self):
        super().__init__(sys.stdout, sys.stderr)
        self.found = []

    def flake(self, message):
        self.found.append(message)


def _noqa_reexport(message, lines):
    if not isinstance(message, messages.UnusedImport):
        return False
    line = lines[message.lineno - 1] if 0 < message.lineno <= len(lines) else ""
    return "noqa: F401" in line


def main():
    problems = 0
    for path in python_files():
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
        collect = _Collect()
        api.check(source, path, collect)
        lines = source.splitlines()
        for message in collect.found:
            if _noqa_reexport(message, lines):
                continue
            problems += 1
            print(str(message).replace(ROOT + os.sep, ""))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
