# -*- coding: utf-8 -*-
"""Window properties that let the context menu know which movies are listed.

Kodi evaluates the ``<visible>`` condition of a context menu item without
running Python, so the add-on publishes the movie ids of the shortlist as
properties of the Home window (id 10000):

    Window(Home).Property(movieshortlist.slot1) = "123"
    ...
    Window(Home).Property(movieshortlist.slot50) = ""

addon.xml compares every slot with ``ListItem.DBID`` using
``String.IsEqual(Window(Home).Property(movieshortlist.slotN),ListItem.DBID)``,
which gives an exact match (``String.Contains`` would mistake id 12 for 112).
SLOT_COUNT must match the number of slots in addon.xml (checked by the tests).
"""

import xbmcgui

HOME_WINDOW_ID = 10000
SLOT_COUNT = 50
SLOT_PREFIX = 'movieshortlist.slot'
COUNT_PROPERTY = 'movieshortlist.count'


def slot_name(index):
    return '{0}{1}'.format(SLOT_PREFIX, index)


def sync(entries):
    """Publish the ids of the newest SLOT_COUNT entries."""
    window = xbmcgui.Window(HOME_WINDOW_ID)
    newest_first = sorted(entries, key=lambda entry: entry.get('added') or 0.0, reverse=True)
    ids = [str(entry['movieid']) for entry in newest_first[:SLOT_COUNT]]
    for index in range(1, SLOT_COUNT + 1):
        if index <= len(ids):
            window.setProperty(slot_name(index), ids[index - 1])
        else:
            window.clearProperty(slot_name(index))
    window.setProperty(COUNT_PROPERTY, str(len(entries)))


def clear():
    window = xbmcgui.Window(HOME_WINDOW_ID)
    for index in range(1, SLOT_COUNT + 1):
        window.clearProperty(slot_name(index))
    window.clearProperty(COUNT_PROPERTY)
