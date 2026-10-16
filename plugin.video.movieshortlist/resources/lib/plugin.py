# -*- coding: utf-8 -*-
"""Plugin entry point: main menu, shortlist view and list actions."""

import os
import random
from urllib.parse import parse_qsl, urlencode

import xbmc
import xbmcgui
import xbmcplugin

from . import common, library, listing, properties, shortlist, sorting, storage

LAST_RANDOM_PROPERTY = 'movieshortlist.lastrandom'


def plugin_url(**params):
    return common.PLUGIN_URL + ('?' + urlencode(params) if params else '')


def run_plugin_command(**params):
    return 'RunPlugin({0})'.format(plugin_url(**params))


def current_sort_order():
    try:
        order = common.addon().getSettingInt('sort_order')
    except Exception:  # pylint: disable=broad-except
        order = sorting.SORT_ADDED
    return order if order in sorting.SORT_ORDERS else sorting.SORT_ADDED


# --------------------------------------------------------------------------- views

def show_main_menu(handle):
    count = len(storage.read_entries())
    order = current_sort_order()
    media = os.path.join(common.addon().getAddonInfo('path'), 'resources', 'media')
    fanart = common.addon().getAddonInfo('fanart')
    menu = [
        (plugin_url(action='list'), common.localize(32011, count), 'DefaultMovies.png', True),
        (plugin_url(action='random'), common.localize(32012), os.path.join(media, 'random.png'), False),
        (plugin_url(action='sort'),
         common.localize(32013, common.localize(sorting.SORT_LABELS[order])),
         os.path.join(media, 'sort.png'), False),
        (plugin_url(action='clear'), common.localize(32014), os.path.join(media, 'clear.png'), False),
    ]
    items = []
    for url, label, icon, is_folder in menu:
        listitem = xbmcgui.ListItem(label=label, offscreen=True)
        listitem.setArt({'icon': icon, 'thumb': icon, 'fanart': fanart})
        items.append((url, listitem, is_folder))
    xbmcplugin.setPluginCategory(handle, common.addon_name())
    xbmcplugin.addDirectoryItems(handle, items, len(items))
    xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)


def _empty_item():
    listitem = xbmcgui.ListItem(label=common.localize(32027), offscreen=True)
    listitem.setArt({'icon': 'DefaultIconInfo.png', 'thumb': 'DefaultIconInfo.png'})
    return plugin_url(action='noop'), listitem, False


def show_shortlist(handle):
    xbmcplugin.setPluginCategory(handle, common.localize(32010))
    try:
        movies = shortlist.load_movies()
    except library.LibraryUnavailable:
        common.notify(common.localize(32029), icon='DefaultIconError.png')
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    if not movies:
        xbmcplugin.setContent(handle, 'files')
        url, listitem, is_folder = _empty_item()
        xbmcplugin.addDirectoryItem(handle, url, listitem, is_folder)
        xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)
        return

    xbmcplugin.setContent(handle, 'movies')
    items = []
    for _entry, details in sorting.sort_movies(movies, current_sort_order()):
        movieid = details.get('movieid')
        context_menu = [
            (common.localize(32002), run_plugin_command(action='remove', movieid=movieid)),
            (common.localize(32012), run_plugin_command(action='random')),
            (common.localize(32015), run_plugin_command(action='sort')),
            (common.localize(32014), run_plugin_command(action='clear')),
        ]
        url, listitem = listing.build_listitem(details, context_menu)
        items.append((url, listitem, False))
    xbmcplugin.addDirectoryItems(handle, items, len(items))
    # Order is controlled by the add-on's own sort setting ("Sortierung").
    xbmcplugin.addSortMethod(handle, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)


# ------------------------------------------------------------------------- actions

def pick_random():
    try:
        movies = shortlist.load_movies()
    except library.LibraryUnavailable:
        common.notify(common.localize(32029), icon='DefaultIconError.png')
        return
    if not movies:
        common.notify(common.localize(32026))
        return
    window = xbmcgui.Window(properties.HOME_WINDOW_ID)
    last = window.getProperty(LAST_RANDOM_PROPERTY)
    candidates = [item for item in movies if str(item[1].get('movieid')) != last] or movies
    _entry, details = random.choice(candidates)
    window.setProperty(LAST_RANDOM_PROPERTY, str(details.get('movieid')))
    common.log('Random pick: {0}'.format(details.get('title')))
    _url, listitem = listing.build_listitem(details)
    # The native video info dialog shows poster, fanart, plot and ratings and
    # offers "Play"/"Resume" - playback only starts if the user confirms there.
    xbmcgui.Dialog().info(listitem)


def change_sort_order():
    order = current_sort_order()
    labels = [common.localize(sorting.SORT_LABELS[value]) for value in sorting.SORT_ORDERS]
    choice = xbmcgui.Dialog().select(common.localize(32015), labels,
                                     preselect=sorting.SORT_ORDERS.index(order))
    if choice < 0 or sorting.SORT_ORDERS[choice] == order:
        return
    common.addon().setSettingInt('sort_order', sorting.SORT_ORDERS[choice])
    common.refresh_container_if_plugin()


def clear_shortlist():
    if not storage.read_entries():
        common.notify(common.localize(32026))
        return
    if not xbmcgui.Dialog().yesno(common.localize(32014), common.localize(32024)):
        return
    try:
        storage.clear()
    except storage.StorageError:
        common.notify(common.localize(32032), icon='DefaultIconError.png')
        return
    properties.sync([])
    common.notify(common.localize(32025))
    common.refresh_container_if_plugin()


def remove_movie(movieid):
    status, title = shortlist.remove_movie(movieid)
    shortlist.notify_remove_result(status, title)
    common.refresh_container_if_plugin()


# -------------------------------------------------------------------------- router

def run(argv):
    try:
        handle = int(argv[1]) if len(argv) > 1 else -1
    except ValueError:
        handle = -1
    query = argv[2][1:] if len(argv) > 2 and argv[2].startswith('?') else ''
    params = dict(parse_qsl(query))
    action = params.get('action', '')
    common.log('Plugin call: action={0!r} params={1!r}'.format(action, params))

    try:
        if action == '':
            properties.sync(storage.read_entries())
            show_main_menu(handle)
        elif action == 'list':
            show_shortlist(handle)
        elif action == 'random':
            pick_random()
        elif action == 'sort':
            change_sort_order()
        elif action == 'clear':
            clear_shortlist()
        elif action == 'remove':
            try:
                movieid = int(params.get('movieid', '0'))
            except ValueError:
                movieid = 0
            if movieid > 0:
                remove_movie(movieid)
        elif action == 'noop':
            pass
        else:
            common.log('Unknown action {0!r}'.format(action), xbmc.LOGWARNING)
            if handle >= 0:
                xbmcplugin.endOfDirectory(handle, succeeded=False)
    except Exception as exc:  # pylint: disable=broad-except
        common.log('Unexpected error in action {0!r}: {1!r}'.format(action, exc), xbmc.LOGERROR)
        import traceback
        common.log(traceback.format_exc(), xbmc.LOGERROR)
        common.notify(common.localize(32036), icon='DefaultIconError.png')
        if handle >= 0 and action in ('', 'list'):
            xbmcplugin.endOfDirectory(handle, succeeded=False)
