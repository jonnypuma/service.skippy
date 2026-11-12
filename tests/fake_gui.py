# -*- coding: utf-8 -*-
"""A small stand-in for ``xbmcgui`` controls and windows, for testing dialogs built in Python.

It keeps what a dialog does to its controls (labels, text, focus, scrolling, navigation,
positions) so a test can drive ``onInit`` / ``onClick`` / ``onAction`` and look at the result.
``load(module_name)`` imports a fresh copy of a module with this fake as ``xbmcgui``.
"""

import importlib.util
import itertools
import os
import sys
from unittest.mock import patch

_ids = itertools.count(3000)

ACTION_MOVE_LEFT = 1
ACTION_MOVE_RIGHT = 2
ACTION_MOVE_UP = 3
ACTION_MOVE_DOWN = 4
ACTION_PAGE_UP = 5
ACTION_PAGE_DOWN = 6
ACTION_SELECT_ITEM = 7
ACTION_PREVIOUS_MENU = 10
ACTION_NAV_BACK = 92
ALIGN_CENTER = 6
ALIGN_LEFT = 0
ALIGN_CENTER_Y = 4


class Action:
    def __init__(self, action_id):
        self._id = action_id

    def getId(self):
        return self._id

    def getButtonCode(self):
        return 0


class Control:
    def __init__(self, x=0, y=0, w=0, h=0, *args, **kwargs):
        self._id = next(_ids)
        self.x, self.y, self.w, self.h = x, y, w, h
        self.args = args
        self.kwargs = kwargs
        self.label = args[0] if args and isinstance(args[0], str) else ""
        self.text = ""
        self.visible = True
        self.enabled = True
        self.navigation = None
        self.diffuse = None
        self.scrolled_to = None
        self.items = []
        self.selected = 0

    def getId(self):
        return self._id

    def setVisible(self, visible):
        self.visible = bool(visible)

    def isVisible(self):
        return self.visible

    def setEnabled(self, enabled):
        self.enabled = bool(enabled)

    def setLabel(self, label="", *args, **kwargs):
        self.label = label

    def getLabel(self):
        return self.label

    def setText(self, text):
        self.text = text

    def getText(self):
        return self.text

    def scroll(self, position):
        self.scrolled_to = position

    def setNavigation(self, up, down, left, right):
        self.navigation = (up, down, left, right)

    def controlUp(self, other):
        self._nav("up", other)

    def controlDown(self, other):
        self._nav("down", other)

    def controlLeft(self, other):
        self._nav("left", other)

    def controlRight(self, other):
        self._nav("right", other)

    def _nav(self, side, other):
        if not isinstance(self.navigation, dict):
            self.navigation = {}
        self.navigation[side] = other

    def setColorDiffuse(self, color):
        self.diffuse = color

    def setPosition(self, x, y):
        self.x, self.y = x, y

    def setWidth(self, w):
        self.w = w

    def setHeight(self, h):
        self.h = h

    def getX(self):
        return self.x

    def getY(self):
        return self.y

    def getWidth(self):
        return self.w

    def getHeight(self):
        return self.h

    def setImage(self, path, *args):
        self.image = path

    def setSelected(self, selected):
        self.selected = selected

    # list controls
    def addItem(self, item):
        self.items.append(item)

    def addItems(self, items):
        self.items.extend(items)

    def reset(self):
        self.items = []

    def size(self):
        return len(self.items)

    def getSelectedPosition(self):
        return self.selected

    def selectItem(self, index):
        self.selected = index

    def getListItem(self, index):
        return self.items[index]

    def getSelectedItem(self):
        return self.items[self.selected] if self.items else None


class ControlButton(Control):
    def __init__(self, x, y, w, h, label, *args, **kwargs):
        super().__init__(x, y, w, h, label, *args, **kwargs)


class ControlImage(Control):
    def __init__(self, x, y, w, h, filename, *args, **kwargs):
        super().__init__(x, y, w, h, *args, **kwargs)
        self.image = filename


class ControlLabel(Control):
    pass


class ControlFadeLabel(Control):
    pass


class ControlTextBox(Control):
    def __init__(self, x, y, w, h, *args, **kwargs):
        super().__init__(x, y, w, h, *args, **kwargs)
        self.label = ""


class ControlList(Control):
    pass


class ControlEdit(Control):
    pass


class ControlRadioButton(Control):
    pass


class ControlSlider(Control):
    pass


class ControlGroup(Control):
    pass


class ListItem:
    def __init__(self, label="", label2="", *args, **kwargs):
        self.label = label
        self.label2 = label2
        self.properties = {}

    def getLabel(self):
        return self.label

    def setLabel(self, label):
        self.label = label

    def getLabel2(self):
        return self.label2

    def setLabel2(self, label):
        self.label2 = label

    def setProperty(self, key, value):
        self.properties[key] = value

    def getProperty(self, key):
        return self.properties.get(key, "")

    def setArt(self, art):
        self.properties["art"] = art


class _Window:
    def __init__(self, *args, **kwargs):
        self.controls = []
        self.focus = None
        self.closed = False
        self.shown = False
        self.properties = {}

    def addControl(self, control):
        self.controls.append(control)

    def addControls(self, controls):
        self.controls.extend(controls)

    def removeControl(self, control):
        if control in self.controls:
            self.controls.remove(control)

    def removeControls(self, controls):
        for control in controls:
            self.removeControl(control)

    def getControl(self, control_id):
        for control in self.controls:
            if control.getId() == control_id:
                return control
        raise RuntimeError("Non-Existent Control %d" % control_id)

    def setFocus(self, control):
        self.focus = control

    def setFocusId(self, control_id):
        self.focus = self.getControl(control_id)

    def getFocus(self):
        return self.focus

    def getFocusId(self):
        return self.focus.getId() if self.focus is not None else 0

    def setProperty(self, key, value):
        self.properties[key] = value

    def getProperty(self, key):
        return self.properties.get(key, "")

    def clearProperty(self, key):
        self.properties.pop(key, None)

    def show(self):
        self.shown = True

    def close(self):
        self.closed = True

    def doModal(self):
        """Run onInit, then the test's ``on_modal(window)`` hook, if any, as the user."""
        self.shown = True
        if hasattr(self, "onInit"):
            self.onInit()
        hook = getattr(sys.modules[__name__], "on_modal", None)
        if hook is not None:
            hook(self)

    # helpers for tests
    def press(self, control):
        """Click ``control`` the way Kodi reports it to a WindowDialog."""
        self.focus = control
        self.onControl(control) if hasattr(self, "onControl") else self.onClick(control.getId())

    def act(self, action_id):
        self.onAction(Action(action_id))

    def labels(self):
        return [c.label for c in self.controls if isinstance(c, ControlButton)]


class WindowDialog(_Window):
    pass


class Window(_Window):
    pass


class WindowXMLDialog(_Window):
    pass


class WindowXML(_Window):
    pass


class Dialog:
    """``answers`` are popped in order by yesno / select / input; every call lands in ``calls``."""

    answers = []
    calls = []

    def _answer(self, kind, default, args, kwargs):
        Dialog.calls.append((kind, args, kwargs))
        return Dialog.answers.pop(0) if Dialog.answers else default

    def yesno(self, *args, **kwargs):
        return self._answer("yesno", False, args, kwargs)

    def ok(self, *args, **kwargs):
        Dialog.calls.append(("ok", args, kwargs))
        return True

    def notification(self, *args, **kwargs):
        Dialog.calls.append(("notification", args, kwargs))

    def select(self, *args, **kwargs):
        return self._answer("select", -1, args, kwargs)

    def input(self, *args, **kwargs):
        return self._answer("input", "", args, kwargs)


def dialog_calls(kind):
    """The ``args`` of every recorded Dialog call of ``kind`` ("ok", "notification", ...)."""
    return [args for k, args, _kwargs in Dialog.calls if k == kind]


def with_id(control, control_id):
    """Give ``control`` a fixed id, like a control defined in a skin XML."""
    control._id = control_id
    return control


on_modal = None


def load(module_name, test):
    """Import a fresh copy of ``module_name`` with this module as ``xbmcgui``; returns it.

    The real module is imported first so its dependencies are loaded (and cached) against
    the usual stubs; only the fresh copy sees the fake, and only while it is executed.
    """
    importlib.import_module(module_name)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    spec = importlib.util.spec_from_file_location(
        "%s_under_test" % module_name, os.path.join(root, "%s.py" % module_name)
    )
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"xbmcgui": sys.modules[__name__]}):
        spec.loader.exec_module(module)
    return module


def reset():
    global on_modal
    on_modal = None
    Dialog.answers = []
    Dialog.calls = []
