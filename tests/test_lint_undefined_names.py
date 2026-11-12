# -*- coding: utf-8 -*-
"""No add-on module may use a name it never defines or imports.

Such a name only fails when its line runs, so a rarely used path (an online sidecar Merge
save, say) can ship broken. The check below needs only the standard library, so it always
runs; when pyflakes is installed (``pip install pyflakes``) its undefined-name check runs too.
"""

import builtins
import glob
import os
import symtable
import unittest

try:
    from pyflakes import api as pyflakes_api
    from pyflakes import messages as pyflakes_messages
    from pyflakes import reporter as pyflakes_reporter
except ImportError:  # pragma: no cover - depends on the machine running the tests
    pyflakes_api = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Personal variants of older files (see CLAUDE.md); they are not part of the add-on.
SKIP_SUFFIX = "-Jon.py"
_MODULE_DUNDERS = {
    "__name__", "__file__", "__doc__", "__spec__", "__loader__", "__package__",
    "__builtins__", "__path__", "__annotations__", "__dict__", "__class__",
}


def _modules():
    return [
        path
        for path in sorted(glob.glob(os.path.join(ROOT, "*.py")))
        if not path.endswith(SKIP_SUFFIX)
    ]


def undefined_globals(source, filename):
    """``[(name, line of its scope, scope)]`` for names used but never bound anywhere it could come from."""
    top = symtable.symtable(source, filename, "exec")
    defined = set(dir(builtins)) | _MODULE_DUNDERS
    for symbol in top.get_symbols():
        if symbol.is_assigned() or symbol.is_imported() or symbol.is_namespace():
            defined.add(symbol.get_name())

    def declared_globals(table):
        for symbol in table.get_symbols():
            if symbol.is_declared_global() and symbol.is_assigned():
                defined.add(symbol.get_name())
        for child in table.get_children():
            declared_globals(child)

    declared_globals(top)
    found = []

    def walk(table):
        for symbol in table.get_symbols():
            if not symbol.is_referenced():
                continue
            name = symbol.get_name()
            if table.get_type() == "module":
                bound = symbol.is_assigned() or symbol.is_imported() or symbol.is_namespace()
                missing = not bound and name not in defined
            else:
                missing = symbol.is_global() and name not in defined
            if missing:
                found.append((name, table.get_lineno(), table.get_name()))
        for child in table.get_children():
            walk(child)

    walk(top)
    return found


class UndefinedNameTests(unittest.TestCase):
    def test_no_module_uses_an_undefined_name(self):
        found = []
        for path in _modules():
            with open(path, encoding="utf-8") as handle:
                source = handle.read()
            for name, line, scope in undefined_globals(source, path):
                found.append("%s: %s in %s (line %d)" % (os.path.basename(path), name, scope, line))
        self.assertEqual(found, [])

    def test_the_check_finds_a_missing_name(self):
        source = (
            "import os\n"
            "def save(items):\n"
            "    return signature(items) == os.sep\n"
            "class Panel:\n"
            "    ROW = 40\n"
            "    def height(self):\n"
            "        return ROW * 2\n"
        )
        names = sorted(name for name, _line, _scope in undefined_globals(source, "sample.py"))
        self.assertEqual(names, ["ROW", "signature"])

    def test_the_check_accepts_what_python_accepts(self):
        source = (
            "import json as js\n"
            "from os import path\n"
            "_cache = None\n"
            "def outer():\n"
            "    local = 1\n"
            "    def inner():\n"
            "        return local + len(path.sep) + js.dumps(1).count('1')\n"
            "    return inner\n"
            "def remember():\n"
            "    global _later\n"
            "    _later = __name__\n"
            "def use():\n"
            "    return _later, _cache, [x for x in range(3)]\n"
        )
        self.assertEqual(undefined_globals(source, "sample.py"), [])


@unittest.skipIf(pyflakes_api is None, "pyflakes is not installed")
class PyflakesUndefinedNameTests(unittest.TestCase):
    def test_pyflakes_finds_no_undefined_name(self):
        class _Collect(pyflakes_reporter.Reporter):
            def __init__(self):
                self.messages = []
                self.errors = []

            def flake(self, message):
                self.messages.append(message)

            def syntaxError(self, filename, msg, lineno, offset, text):
                self.errors.append("%s:%s: %s" % (filename, lineno, msg))

            def unexpectedError(self, filename, msg):
                self.errors.append("%s: %s" % (filename, msg))

        found = []
        for path in _modules():
            collect = _Collect()
            with open(path, encoding="utf-8") as handle:
                pyflakes_api.check(handle.read(), path, collect)
            found.extend(collect.errors)
            for message in collect.messages:
                if isinstance(message, pyflakes_messages.UndefinedName):
                    found.append(
                        "%s:%s: %s"
                        % (os.path.basename(path), message.lineno, message.message % message.message_args)
                    )
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
