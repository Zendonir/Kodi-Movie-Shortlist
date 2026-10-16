# -*- coding: utf-8 -*-
"""Context menu actions for movies in Kodi's video library."""

import xbmc

from . import common, shortlist


def _movie_from_listitem(listitem):
    """Return (movieid, poster) of the selected library movie or (0, '')."""
    movieid = 0
    media_type = ''
    poster = ''
    if listitem is not None:
        tag = listitem.getVideoInfoTag()
        movieid = tag.getDbId()
        media_type = tag.getMediaType()
        poster = listitem.getArt('poster') or listitem.getArt('thumb')
    if movieid <= 0:
        # Fallback for skins/views that do not pass a full info tag.
        try:
            movieid = int(xbmc.getInfoLabel('ListItem.DBID') or 0)
        except ValueError:
            movieid = 0
        media_type = media_type or xbmc.getInfoLabel('ListItem.DBType')
    if media_type and media_type != 'movie':
        return 0, ''
    return movieid, poster


def add(listitem):
    movieid, poster = _movie_from_listitem(listitem)
    if movieid <= 0:
        common.notify(common.localize(32033))
        return
    status, title = shortlist.add_movie(movieid)
    common.log('Add movie {0}: {1}'.format(movieid, status))
    shortlist.notify_add_result(status, title, icon=poster or None)


def remove(listitem):
    movieid, poster = _movie_from_listitem(listitem)
    if movieid <= 0:
        common.notify(common.localize(32033))
        return
    status, title = shortlist.remove_movie(movieid)
    common.log('Remove movie {0}: {1}'.format(movieid, status))
    shortlist.notify_remove_result(status, title, icon=poster or None)
    common.refresh_container_if_plugin()


def clear():
    # Same confirmation dialog as in the add-on menu.
    from . import plugin
    plugin.clear_shortlist()


def run(action, listitem):
    try:
        if action == 'add':
            add(listitem)
        elif action == 'clear':
            clear()
        else:
            remove(listitem)
    except Exception as exc:  # pylint: disable=broad-except
        import traceback
        common.log('Context menu action {0} failed: {1!r}\n{2}'.format(
            action, exc, traceback.format_exc()), xbmc.LOGERROR)
        common.notify(common.localize(32036), icon='DefaultIconError.png')
