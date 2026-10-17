# -*- coding: utf-8 -*-
"""Minimal in-memory fakes of the Kodi Python modules for unit tests.

Only the functions used by the add-on are implemented. The real API
signatures were verified separately with mypy against Kodistubs 21.
"""

import json
import os
import re
import sys
import types

ADDON_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         'plugin.video.movieshortlist')


def _load_strings():
    path = os.path.join(ADDON_DIR, 'resources', 'language', 'resource.language.en_gb',
                        'strings.po')
    with open(path, encoding='utf-8') as handle:
        text = handle.read()
    strings = {}
    for match in re.finditer(r'msgctxt "#(\d+)"\nmsgid "((?:[^"\\]|\\.)*)"', text):
        strings[int(match.group(1))] = match.group(2).replace('\\"', '"')
    return strings


class FakeLibrary:
    """Fake video library answering the JSON-RPC calls used by the add-on."""

    def __init__(self):
        self.movies = {}
        self.available = True
        self.calls = []

    def add_movie(self, movieid, title, year=2000, **extra):
        movie = {
            'movieid': movieid, 'label': title, 'title': title, 'year': year,
            'file': extra.pop('file', 'D:\\Movies\\{0} ({1})\\{0}.mkv'.format(title, year)),
            'uniqueid': extra.pop('uniqueid', {'imdb': 'tt{0:07d}'.format(movieid)}),
        }
        movie.update(extra)
        self.movies[movieid] = movie
        return movie

    def handle(self, request):
        self.calls.append(request)
        method = request['method']
        params = request.get('params', {})
        if not self.available:
            return {'id': 1, 'jsonrpc': '2.0',
                    'error': {'code': -32603, 'message': 'Internal error.'}}
        if method == 'VideoLibrary.GetMovieDetails':
            movie = self.movies.get(params['movieid'])
            if movie is None:
                return {'id': 1, 'jsonrpc': '2.0',
                        'error': {'code': -32602, 'message': 'Invalid params.'}}
            details = {key: value for key, value in movie.items()
                       if key in params.get('properties', []) or key in ('movieid', 'label')}
            return {'id': 1, 'jsonrpc': '2.0', 'result': {'moviedetails': details}}
        if method == 'VideoLibrary.GetMovies':
            movies = list(self.movies.values())
            flt = params.get('filter')
            if flt:
                assert flt['field'] == 'title' and flt['operator'] == 'is'
                movies = [m for m in movies if m['title'].lower() == flt['value'].lower()]
            props = params.get('properties', [])
            result = [{key: value for key, value in m.items()
                       if key in props or key in ('movieid', 'label')} for m in movies]
            limits = params.get('limits')
            if limits:
                result = result[limits['start']:limits['end']]
            return {'id': 1, 'jsonrpc': '2.0', 'result': {'movies': result, 'limits': {
                'start': 0, 'end': len(result), 'total': len(self.movies)}}}
        return {'id': 1, 'jsonrpc': '2.0', 'error': {'code': -32601, 'message': 'Method not found.'}}


class State:
    """Global state shared by all fake modules."""

    def __init__(self, profile_dir):
        self.profile_dir = profile_dir
        self.library = FakeLibrary()
        self.window_properties = {}
        self.notifications = []
        self.builtins = []
        self.log = []
        self.settings = {'sort_order': 0, 'debug_logging': False, 'remove_watched': True}
        self.info_labels = {}
        self.yesno_answer = False
        self.select_answer = -1
        self.dialog_calls = []
        self.directory = None
        self.strings = _load_strings()


STATE = None


def install(profile_dir):
    """Create fresh fake modules and register them in sys.modules."""
    global STATE
    STATE = State(profile_dir)

    # ------------------------------------------------------------------ xbmc
    xbmc = types.ModuleType('xbmc')
    xbmc.LOGDEBUG, xbmc.LOGINFO, xbmc.LOGWARNING, xbmc.LOGERROR = 0, 1, 2, 3

    def log(msg, level=0):
        STATE.log.append((level, msg))

    def execute_jsonrpc(raw):
        return json.dumps(STATE.library.handle(json.loads(raw)))

    def executebuiltin(command, wait=False):
        STATE.builtins.append(command)

    def get_info_label(label):
        return STATE.info_labels.get(label, '')

    class Monitor:
        def abortRequested(self):
            return True

        def waitForAbort(self, timeout=-1):
            return True

    class _Record:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    class InfoTagVideo:
        def __init__(self):
            self.values = {}
            self.streams = []

        def __getattr__(self, name):
            if name.startswith('set'):
                def setter(*args):
                    self.values[name[3:]] = args if len(args) > 1 else args[0]
                return setter
            if name.startswith('add'):
                def adder(stream):
                    self.streams.append((name, stream))
                return adder
            raise AttributeError(name)

        def getDbId(self):
            return self.values.get('DbId', -1)

        def getMediaType(self):
            return self.values.get('MediaType', '')

    xbmc.log = log
    xbmc.executeJSONRPC = execute_jsonrpc
    xbmc.executebuiltin = executebuiltin
    xbmc.getInfoLabel = get_info_label
    xbmc.Monitor = Monitor
    xbmc.InfoTagVideo = InfoTagVideo
    xbmc.Actor = type('Actor', (_Record,), {})
    xbmc.VideoStreamDetail = type('VideoStreamDetail', (_Record,), {})
    xbmc.AudioStreamDetail = type('AudioStreamDetail', (_Record,), {})
    xbmc.SubtitleStreamDetail = type('SubtitleStreamDetail', (_Record,), {})

    # --------------------------------------------------------------- xbmcgui
    xbmcgui = types.ModuleType('xbmcgui')

    class ListItem:
        def __init__(self, label='', label2='', path='', offscreen=False):
            self.label = label
            self.path = path
            self.art = {}
            self.context_menu = []
            self.tag = InfoTagVideo()

        def setArt(self, art):
            self.art.update(art)

        def getArt(self, key):
            return self.art.get(key, '')

        def getVideoInfoTag(self):
            return self.tag

        def addContextMenuItems(self, items, replaceItems=False):
            self.context_menu.extend(items)

        def getLabel(self):
            return self.label

    class Window:
        def __init__(self, window_id=-1):
            assert window_id == 10000

        def setProperty(self, key, value):
            STATE.window_properties[key.lower()] = value

        def getProperty(self, key):
            return STATE.window_properties.get(key.lower(), '')

        def clearProperty(self, key):
            STATE.window_properties.pop(key.lower(), None)

    class Dialog:
        def notification(self, heading, message, icon='', time=0, sound=True):
            STATE.notifications.append(message)

        def yesno(self, heading, message, nolabel='', yeslabel='', autoclose=0, defaultbutton=0):
            STATE.dialog_calls.append(('yesno', heading, message))
            return STATE.yesno_answer

        def select(self, heading, items, autoclose=0, preselect=-1, useDetails=False):
            STATE.dialog_calls.append(('select', heading, items, preselect))
            return STATE.select_answer

        def info(self, item):
            STATE.dialog_calls.append(('info', item))
            return True

    xbmcgui.ListItem = ListItem
    xbmcgui.Window = Window
    xbmcgui.Dialog = Dialog

    # ------------------------------------------------------------ xbmcplugin
    xbmcplugin = types.ModuleType('xbmcplugin')
    xbmcplugin.SORT_METHOD_UNSORTED = 40

    def _directory():
        if STATE.directory is None:
            STATE.directory = {'items': [], 'content': None, 'sort': [], 'ended': None,
                               'category': None}
        return STATE.directory

    def add_directory_item(handle, url, listitem, isFolder=False, totalItems=0):
        _directory()['items'].append((url, listitem, isFolder))
        return True

    def add_directory_items(handle, items, totalItems=0):
        _directory()['items'].extend(items)
        return True

    def end_of_directory(handle, succeeded=True, updateListing=False, cacheToDisc=True):
        _directory()['ended'] = succeeded

    xbmcplugin.addDirectoryItem = add_directory_item
    xbmcplugin.addDirectoryItems = add_directory_items
    xbmcplugin.endOfDirectory = end_of_directory
    xbmcplugin.setContent = lambda handle, content: _directory().__setitem__('content', content)
    xbmcplugin.addSortMethod = lambda handle, method, labelMask='', label2Mask='': \
        _directory()['sort'].append(method)
    xbmcplugin.setPluginCategory = lambda handle, category: \
        _directory().__setitem__('category', category)

    # ------------------------------------------------------------- xbmcaddon
    xbmcaddon = types.ModuleType('xbmcaddon')

    class Addon:
        def __init__(self, addon_id=None):
            pass

        def getLocalizedString(self, string_id):
            return STATE.strings.get(string_id, '')

        def getAddonInfo(self, key):
            return {'name': 'Movie Shortlist', 'icon': 'icon.png', 'fanart': 'fanart.jpg',
                    'path': ADDON_DIR, 'profile': STATE.profile_dir,
                    'id': 'plugin.video.movieshortlist'}[key]

        def getSettingBool(self, key):
            return bool(STATE.settings[key])

        def getSettingInt(self, key):
            return int(STATE.settings[key])

        def setSettingInt(self, key, value):
            STATE.settings[key] = value
            return True

    xbmcaddon.Addon = Addon

    # --------------------------------------------------------------- xbmcvfs
    xbmcvfs = types.ModuleType('xbmcvfs')
    xbmcvfs.translatePath = lambda path: path

    for name, module in (('xbmc', xbmc), ('xbmcgui', xbmcgui), ('xbmcplugin', xbmcplugin),
                         ('xbmcaddon', xbmcaddon), ('xbmcvfs', xbmcvfs)):
        sys.modules[name] = module

    # Reload add-on modules so they bind to the fresh fakes.
    if ADDON_DIR not in sys.path:
        sys.path.insert(0, ADDON_DIR)
    for name in list(sys.modules):
        if name == 'resources' or name.startswith('resources.'):
            del sys.modules[name]
    return STATE
