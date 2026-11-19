# -*- coding: utf-8 -*-
"""For the tests of the next episode popup of earlier versions (``Card (legacy)``).

Since 8.28.0 a draft starts with the drawn Card. These tests are about the other one, so while one
of their modules runs, the draft starts with it; the default is put back afterwards.
"""
import next_episode_appearance as app
import next_layouts as nl

_saved = []


def use_legacy_card():
    _saved.append((app.DEFAULT_DRAFT[app.KEY_LAYOUT], app.DEFAULT_DRAFT[app.KEY_LAYOUT_LOOK]))
    app.DEFAULT_DRAFT[app.KEY_LAYOUT] = nl.LAYOUT_CARD
    app.DEFAULT_DRAFT[app.KEY_LAYOUT_LOOK] = "fgf"


def restore_default():
    if _saved:
        app.DEFAULT_DRAFT[app.KEY_LAYOUT], app.DEFAULT_DRAFT[app.KEY_LAYOUT_LOOK] = _saved.pop()
