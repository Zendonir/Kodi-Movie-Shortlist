# -*- coding: utf-8 -*-
"""Unit tests for Movie Shortlist (run: python3 -m unittest discover -s tests)."""

import json
import os
import re
import shutil
import sys
import tempfile
import time
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kodi_fakes  # noqa: E402

ADDON_DIR = kodi_fakes.ADDON_DIR
ADDON_XML = os.path.join(ADDON_DIR, 'addon.xml')
PLUGIN = 'plugin://plugin.video.movieshortlist/'


class Base(unittest.TestCase):
    def setUp(self):
        self.profile = tempfile.mkdtemp()
        self.state = kodi_fakes.install(self.profile)
        from resources.lib import (common, context, library, listing, plugin, properties,
                                   service, shortlist, sorting, storage)
        self.common, self.context, self.library = common, context, library
        self.listing, self.plugin, self.properties = listing, plugin, properties
        self.service, self.shortlist, self.sorting, self.storage = (service, shortlist,
                                                                     sorting, storage)
        lib = self.state.library
        lib.add_movie(1, 'Alien', 1979, runtime=7020, ratings={
            'imdb': {'rating': 8.5, 'votes': 900000, 'default': True},
            'themoviedb': {'rating': 8.1, 'votes': 14000, 'default': False}},
            art={'poster': 'image://poster1/', 'fanart': 'image://fanart1/'},
            genre=['Horror', 'Science Fiction'], plot='In space...', playcount=1,
            resume={'position': 0.0, 'total': 0.0})
        lib.add_movie(12, 'Ärger im Paradies', 1932, runtime=5000, ratings={},
                      art={}, genre=[], resume={'position': 1200.0, 'total': 5000.0})
        lib.add_movie(112, 'Zodiac', 2007, runtime=9420, ratings={
            'imdb': {'rating': 7.7, 'votes': 600000, 'default': False}},
            art={'poster': 'image://poster112/'}, uniqueid={'tmdb': '1949'})
        lib.add_movie(5, 'Brazil', 0, runtime=0, uniqueid={})

    def tearDown(self):
        shutil.rmtree(self.profile, ignore_errors=True)

    # helpers
    def run_plugin(self, query='', handle=1):
        self.state.directory = None
        self.plugin.run([PLUGIN, str(handle), query])
        return self.state.directory

    def listitem_for(self, movieid, mediatype='movie'):
        import xbmcgui
        item = xbmcgui.ListItem('x')
        if movieid:
            item.getVideoInfoTag().setDbId(movieid)
            item.getVideoInfoTag().setMediaType(mediatype)
        return item

    def stored_ids(self):
        return [entry['movieid'] for entry in self.storage.read_entries()]


class StorageTests(Base):
    def test_add_remove_clear_and_no_duplicates(self):
        self.assertEqual(self.shortlist.add_movie(1)[0], 'added')
        self.assertEqual(self.shortlist.add_movie(1)[0], 'exists')
        self.assertEqual(self.shortlist.add_movie(12)[0], 'added')
        self.assertEqual(self.stored_ids(), [1, 12])
        self.assertEqual(self.shortlist.remove_movie(1), ('removed', 'Alien'))
        self.assertEqual(self.shortlist.remove_movie(1)[0], 'absent')
        self.assertEqual(self.stored_ids(), [12])
        self.assertEqual(self.storage.clear(), 1)
        self.assertEqual(self.stored_ids(), [])

    def test_stores_only_references(self):
        self.shortlist.add_movie(1)
        with open(os.path.join(self.profile, 'shortlist.json'), encoding='utf-8') as handle:
            data = json.load(handle)
        self.assertEqual(data['version'], 1)
        self.assertEqual(set(data['entries'][0]),
                         {'movieid', 'title', 'year', 'file', 'uniqueid', 'added'})

    def test_persists_across_restart(self):
        self.shortlist.add_movie(1)
        state = kodi_fakes.install(self.profile)  # simulates a Kodi restart
        from resources.lib import storage
        self.assertEqual([e['movieid'] for e in storage.read_entries()], [1])
        self.assertIsNotNone(state)

    def test_corrupt_file_is_backed_up_and_reset(self):
        path = os.path.join(self.profile, 'shortlist.json')
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write('{"entries": [ broken')
        self.assertEqual(self.storage.read_entries(), [])
        self.assertTrue(any(name.startswith('shortlist.json.corrupt-')
                            for name in os.listdir(self.profile)))
        self.assertIn('The saved movie shortlist was damaged and has been reset',
                      self.state.notifications)
        # list keeps working afterwards
        self.assertEqual(self.shortlist.add_movie(1)[0], 'added')

    def test_malformed_entries_are_skipped(self):
        path = os.path.join(self.profile, 'shortlist.json')
        with open(path, 'w', encoding='utf-8') as handle:
            json.dump({'version': 1, 'entries': [
                {'movieid': 'x'}, {'movieid': -3}, 'junk', {'movieid': 1, 'added': 'y'},
                {'movieid': 1}, {'movieid': True}]}, handle)
        self.assertEqual(self.stored_ids(), [1])

    def test_separate_profiles_have_separate_lists(self):
        self.shortlist.add_movie(1)
        other = tempfile.mkdtemp()
        try:
            kodi_fakes.install(other)
            from resources.lib import storage
            self.assertEqual(storage.read_entries(), [])
        finally:
            shutil.rmtree(other, ignore_errors=True)

    def test_stale_lock_is_ignored(self):
        lock = os.path.join(self.profile, 'shortlist.lock')
        with open(lock, 'w', encoding='utf-8'):
            pass
        old = time.time() - 120
        os.utime(lock, (old, old))
        self.assertEqual(self.shortlist.add_movie(1)[0], 'added')
        self.assertFalse(os.path.exists(lock))


class LibraryTests(Base):
    def test_library_unavailable_does_not_prune(self):
        self.shortlist.add_movie(1)
        self.shortlist.add_movie(12)
        self.state.library.available = False
        with self.assertRaises(self.library.LibraryUnavailable):
            self.shortlist.load_movies()
        self.assertEqual(self.stored_ids(), [1, 12])
        self.assertEqual(self.shortlist.add_movie(5)[0], 'unavailable')

    def test_removed_movie_is_pruned_without_error(self):
        self.shortlist.add_movie(1)
        self.shortlist.add_movie(12)
        del self.state.library.movies[12]
        movies = self.shortlist.load_movies()
        self.assertEqual([d['movieid'] for _, d in movies], [1])
        self.assertEqual(self.stored_ids(), [1])
        self.assertIn('Removed 1 movie(s) that are no longer in the library',
                      self.state.notifications)

    def test_movie_with_new_id_is_relocated(self):
        self.shortlist.add_movie(112)
        movie = self.state.library.movies.pop(112)
        movie['movieid'] = 300
        self.state.library.movies[300] = movie
        movies = self.shortlist.load_movies()
        self.assertEqual([d['movieid'] for _, d in movies], [300])
        self.assertEqual(self.stored_ids(), [300])

    def test_reused_id_for_other_movie_is_not_shown(self):
        self.shortlist.add_movie(5)
        self.state.library.movies.pop(5)
        self.state.library.add_movie(5, 'Completely Different', 2020)
        self.assertEqual(self.shortlist.load_movies(), [])
        self.assertEqual(self.stored_ids(), [])

    def test_unknown_movie_cannot_be_added(self):
        self.assertEqual(self.shortlist.add_movie(999)[0], 'notfound')
        self.assertEqual(self.stored_ids(), [])

    def test_no_write_methods_are_used(self):
        self.shortlist.add_movie(1)
        self.run_plugin('?action=list')
        methods = {call['method'] for call in self.state.library.calls}
        self.assertTrue(methods <= {'VideoLibrary.GetMovies', 'VideoLibrary.GetMovieDetails'},
                        methods)

    def test_detail_properties_are_valid_jsonrpc_fields(self):
        # Video.Fields.Movie enum of Kodi 21 (xbmc/interfaces/json-rpc/schema/types.json)
        valid = {'title', 'genre', 'year', 'rating', 'director', 'trailer', 'tagline', 'plot',
                 'plotoutline', 'originaltitle', 'lastplayed', 'playcount', 'writer', 'studio',
                 'mpaa', 'cast', 'country', 'imdbnumber', 'runtime', 'set', 'showlink',
                 'streamdetails', 'top250', 'votes', 'fanart', 'thumbnail', 'file',
                 'sorttitle', 'resume', 'setid', 'dateadded', 'tag', 'art', 'userrating',
                 'ratings', 'premiered', 'uniqueid'}
        self.assertTrue(set(self.library.DETAIL_PROPERTIES) <= valid)
        self.assertTrue(set(self.library.REFERENCE_PROPERTIES) <= valid)


class SortingTests(Base):
    def items(self):
        for movieid in (1, 12, 112, 5):
            self.shortlist.add_movie(movieid)
            time.sleep(0.002)
        return self.shortlist.load_movies()

    def order(self, sort_order):
        return [d['movieid'] for _, d in self.sorting.sort_movies(self.items(), sort_order)]

    def test_added_newest_first(self):
        self.assertEqual(self.order(self.sorting.SORT_ADDED), [5, 112, 12, 1])

    def test_title_alphabetical_accent_insensitive(self):
        self.assertEqual(self.order(self.sorting.SORT_TITLE), [1, 12, 5, 112])

    def test_year_newest_first_missing_last(self):
        self.assertEqual(self.order(self.sorting.SORT_YEAR), [112, 1, 12, 5])

    def test_imdb_highest_first_missing_last(self):
        self.assertEqual(self.order(self.sorting.SORT_IMDB), [1, 112, 12, 5])

    def test_runtime_shortest_first_missing_last(self):
        self.assertEqual(self.order(self.sorting.SORT_RUNTIME), [12, 1, 112, 5])


class ListingTests(Base):
    def test_main_menu(self):
        self.shortlist.add_movie(1)
        directory = self.run_plugin('')
        labels = [item[1].label for item in directory['items']]
        self.assertEqual(labels, ['Show movie shortlist (1)', 'Pick a random movie',
                                  'Sort order: Order added (newest first)',
                                  'Clear movie shortlist'])
        self.assertTrue(directory['items'][0][2])          # list is a folder
        self.assertFalse(any(item[2] for item in directory['items'][1:]))
        self.assertTrue(directory['ended'])

    def test_list_is_library_like(self):
        self.shortlist.add_movie(1)
        directory = self.run_plugin('?action=list')
        self.assertEqual(directory['content'], 'movies')
        self.assertEqual(directory['sort'], [40])
        url, item, is_folder = directory['items'][0]
        movie = self.state.library.movies[1]
        # real file path -> Kodi plays it like a library item
        self.assertEqual(url, movie['file'])
        self.assertEqual(item.path, movie['file'])
        self.assertFalse(is_folder)
        values = item.tag.values
        self.assertEqual(values['DbId'], 1)
        self.assertEqual(values['MediaType'], 'movie')
        self.assertEqual(values['FilenameAndPath'], movie['file'])
        self.assertEqual(values['Year'], 1979)
        self.assertEqual(values['Duration'], 7020)
        self.assertEqual(values['Genres'], ['Horror', 'Science Fiction'])
        self.assertEqual(values['Playcount'], 1)
        self.assertEqual(values['Ratings'], ({'imdb': (8.5, 900000),
                                               'themoviedb': (8.1, 14000)}, 'imdb'))
        self.assertEqual(item.art['poster'], 'image://poster1/')
        self.assertEqual(item.art['fanart'], 'image://fanart1/')
        self.assertIn(('Remove from movie shortlist',
                       'RunPlugin(plugin://plugin.video.movieshortlist/?action=remove&movieid=1)'),
                      item.context_menu)

    def test_missing_poster_ratings_and_ids(self):
        self.shortlist.add_movie(12)
        self.shortlist.add_movie(5)
        directory = self.run_plugin('?action=list')
        items = {i[1].tag.values['DbId']: i[1] for i in directory['items']}
        self.assertEqual(items[12].art, {'icon': 'DefaultVideo.png'})
        self.assertNotIn('Ratings', items[12].tag.values)
        self.assertEqual(items[12].tag.values['ResumePoint'], (1200.0, 5000.0))
        self.assertNotIn('UniqueIDs', items[5].tag.values)

    def test_empty_list(self):
        directory = self.run_plugin('?action=list')
        self.assertEqual(len(directory['items']), 1)
        self.assertIn('empty', directory['items'][0][1].label)
        self.assertTrue(directory['ended'])

    def test_library_unavailable_list(self):
        self.shortlist.add_movie(1)
        self.state.library.available = False
        directory = self.run_plugin('?action=list')
        self.assertFalse(directory['ended'])
        self.assertIn('The video library is not available', self.state.notifications)


class ActionTests(Base):
    def test_clear_requires_confirmation(self):
        self.shortlist.add_movie(1)
        self.state.yesno_answer = False
        self.run_plugin('?action=clear', handle=-1)
        self.assertEqual(self.stored_ids(), [1])
        self.assertEqual(self.state.dialog_calls[-1][2],
                         'Do you want to remove all movies from the movie shortlist?')
        self.state.yesno_answer = True
        self.state.info_labels['Container.FolderPath'] = PLUGIN
        self.run_plugin('?action=clear', handle=-1)
        self.assertEqual(self.stored_ids(), [])
        self.assertIn('Container.Refresh', self.state.builtins)
        self.assertEqual(self.state.window_properties.get('movieshortlist.slot1'), None)

    def test_remove_from_list(self):
        self.shortlist.add_movie(1)
        self.state.info_labels['Container.FolderPath'] = PLUGIN + '?action=list'
        self.run_plugin('?action=remove&movieid=1', handle=-1)
        self.assertEqual(self.stored_ids(), [])
        self.assertIn('Container.Refresh', self.state.builtins)
        self.assertIn('"Alien" removed from the movie shortlist', self.state.notifications)
        self.assertIn(1, self.state.library.movies)  # never touches the library

    def test_random_shows_info_without_playing(self):
        self.shortlist.add_movie(1)
        self.shortlist.add_movie(112)
        self.run_plugin('?action=random', handle=-1)
        kinds = [call[0] for call in self.state.dialog_calls]
        self.assertEqual(kinds, ['info'])
        first = self.state.dialog_calls[0][1].tag.values['DbId']
        self.run_plugin('?action=random', handle=-1)
        second = self.state.dialog_calls[1][1].tag.values['DbId']
        self.assertNotEqual(first, second)  # does not repeat the previous pick
        self.assertFalse([b for b in self.state.builtins if b.startswith('PlayMedia')])

    def test_random_empty(self):
        self.run_plugin('?action=random', handle=-1)
        self.assertIn('The movie shortlist is empty', self.state.notifications)

    def test_sort_change(self):
        self.state.select_answer = 3
        self.run_plugin('?action=sort', handle=-1)
        self.assertEqual(self.state.settings['sort_order'], 3)

    def test_unexpected_error_is_reported(self):
        self.shortlist.add_movie(1)
        self.listing.build_listitem = None  # force a crash
        self.plugin.listing.build_listitem = None
        directory = self.run_plugin('?action=list')
        self.assertFalse(directory['ended'])
        self.assertIn('An unexpected error occurred (see Kodi log)', self.state.notifications)


class ContextMenuTests(Base):
    def test_add_and_remove_via_context_menu(self):
        self.context.run('add', self.listitem_for(1))
        self.assertEqual(self.stored_ids(), [1])
        self.assertIn('"Alien" added to the movie shortlist', self.state.notifications)
        self.context.run('add', self.listitem_for(1))
        self.assertIn('"Alien" is already on the movie shortlist', self.state.notifications)
        self.assertEqual(self.state.window_properties['movieshortlist.slot1'], '1')
        self.assertEqual(self.state.builtins, [])  # library view is not refreshed
        self.context.run('remove', self.listitem_for(1))
        self.assertEqual(self.stored_ids(), [])
        self.assertNotIn('movieshortlist.slot1', self.state.window_properties)

    def test_non_movie_is_rejected(self):
        self.context.run('add', self.listitem_for(7, 'episode'))
        self.assertEqual(self.stored_ids(), [])
        self.context.run('add', self.listitem_for(0))
        self.assertEqual(self.stored_ids(), [])

    def test_infolabel_fallback(self):
        self.state.info_labels['ListItem.DBID'] = '12'
        self.state.info_labels['ListItem.DBType'] = 'movie'
        self.context.run('add', None)
        self.assertEqual(self.stored_ids(), [12])

    def test_service_syncs_and_clears(self):
        self.shortlist.add_movie(1)
        self.state.window_properties.clear()
        self.service.run()
        # waitForAbort returns immediately in the fake -> properties cleared again
        self.assertNotIn('movieshortlist.slot1', self.state.window_properties)
        self.assertTrue(any('Service started' in msg for _, msg in self.state.log))


class ConditionEvaluator:
    """Tiny evaluator for the subset of Kodi's boolean grammar used in addon.xml."""

    TOKEN = re.compile(r'\s*(\[|\]|!|\+|\||[^\[\]!+|]+)')

    def __init__(self, labels):
        self.labels = labels

    def value(self, info):
        info = info.strip()
        prop = re.fullmatch(r'Window\(Home\)\.Property\((.+)\)', info)
        if prop:
            return self.labels['window'].get(prop.group(1).lower(), '')
        return self.labels.get(info, '')

    def atom(self, text):
        text = text.strip()
        match = re.fullmatch(r'String\.(IsEqual|StartsWith|IsEmpty)\((.*)\)', text)
        name, args = match.group(1), match.group(2)
        if name == 'IsEmpty':
            return self.value(args) == ''
        first, second = args.split(',', 1)
        left = self.value(first).lower()
        # second parameter: info label if known, else literal string
        right = (self.value(second) if second.startswith(('ListItem.', 'Window('))
                 else second).lower()
        return left == right if name == 'IsEqual' else left.startswith(right)

    def evaluate(self, expression):
        tokens = [t.strip() for t in self.TOKEN.findall(expression) if t.strip()]
        pos = 0

        def parse_or():
            nonlocal pos
            result = parse_and()
            while pos < len(tokens) and tokens[pos] == '|':
                pos += 1
                result = parse_and() or result
            return result

        def parse_and():
            nonlocal pos
            result = parse_not()
            while pos < len(tokens) and tokens[pos] == '+':
                pos += 1
                result = parse_not() and result
            return result

        def parse_not():
            nonlocal pos
            if tokens[pos] == '!':
                pos += 1
                return not parse_not()
            if tokens[pos] == '[':
                pos += 1
                result = parse_or()
                assert tokens[pos] == ']'
                pos += 1
                return result
            token = tokens[pos]
            pos += 1
            return self.atom(token)

        result = parse_or()
        assert pos == len(tokens)
        return result


class ManifestTests(Base):
    def conditions(self):
        tree = ET.parse(ADDON_XML)
        return {item.get('library'): item.find('visible').text for item in tree.iter('item')}

    def test_manifest_structure(self):
        root = ET.parse(ADDON_XML).getroot()
        self.assertEqual(root.get('id'), 'plugin.video.movieshortlist')
        points = [ext.get('point') for ext in root.findall('extension')]
        self.assertEqual(points[0], 'xbmc.python.pluginsource')
        self.assertIn('kodi.context.item', points)
        self.assertIn('xbmc.service', points)
        self.assertEqual(root.find("requires/import[@addon='xbmc.python']").get('version'),
                         '3.0.1')
        for ext in root.findall('extension'):
            library = ext.get('library')
            if library:
                self.assertTrue(os.path.exists(os.path.join(ADDON_DIR, library)), library)
        for library in self.conditions():
            self.assertTrue(os.path.exists(os.path.join(ADDON_DIR, library)), library)

    def test_slot_count_matches_properties(self):
        for condition in self.conditions().values():
            slots = re.findall(r'movieshortlist\.slot(\d+)\)', condition)
            self.assertEqual([int(s) for s in slots],
                             list(range(1, self.properties.SLOT_COUNT + 1)))
            self.assertEqual(condition.count('['), condition.count(']'))

    def evaluate(self, library, dbid, dbtype='movie', folder='videodb://movies/titles/'):
        labels = {'ListItem.DBID': str(dbid) if dbid else '', 'ListItem.DBType': dbtype,
                  'Container.FolderPath': folder, 'window': self.state.window_properties}
        return ConditionEvaluator(labels).evaluate(self.conditions()[library])

    def test_context_menu_toggles_exactly(self):
        self.shortlist.add_movie(112)
        # 112 is listed, 12 and 1 are not (no substring false positives)
        self.assertFalse(self.evaluate('context_add.py', 112))
        self.assertTrue(self.evaluate('context_remove.py', 112))
        for dbid in (12, 1, 11):
            self.assertTrue(self.evaluate('context_add.py', dbid))
            self.assertFalse(self.evaluate('context_remove.py', dbid))
        # not shown for TV episodes, items without DBID or inside the add-on
        self.assertFalse(self.evaluate('context_add.py', 7, dbtype='episode'))
        self.assertFalse(self.evaluate('context_add.py', 0))
        self.assertFalse(self.evaluate('context_remove.py', 112,
                                       folder=PLUGIN + '?action=list'))

    def test_strings_complete(self):
        used = set()
        for folder, _dirs, files in os.walk(ADDON_DIR):
            for name in files:
                if name.endswith(('.py', '.xml')):
                    with open(os.path.join(folder, name), encoding='utf-8') as handle:
                        text = handle.read()
                    used |= {int(n) for n in re.findall(r'(?<![-\d])(3[12]\d{3})\b', text)}
        for lang in ('en_gb', 'de_de'):
            path = os.path.join(ADDON_DIR, 'resources', 'language',
                                'resource.language.' + lang, 'strings.po')
            with open(path, encoding='utf-8') as handle:
                text = handle.read()
            defined = {int(n) for n in re.findall(r'msgctxt "#(\d+)"', text)}
            self.assertTrue(used <= defined, (lang, used - defined))
            if lang == 'de_de':
                self.assertNotIn('msgstr ""\n\nmsgctxt', text.split('msgctxt', 1)[1])


if __name__ == '__main__':
    unittest.main()
