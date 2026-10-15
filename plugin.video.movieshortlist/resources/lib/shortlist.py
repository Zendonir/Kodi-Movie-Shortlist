# -*- coding: utf-8 -*-
"""Combines the stored references with live library data."""

import xbmc

from . import common, library, properties, storage


def load_movies():
    """Return a list of (entry, details) for all movies on the shortlist.

    - Movies whose id now points to a different movie, or that were re-added
      to the library with a new id, are re-located by title/year/ids.
    - Movies that no longer exist are removed from the shortlist (only after
      the library was confirmed to be reachable).

    Raises library.LibraryUnavailable if the video database cannot be read.
    """
    entries = storage.read_entries()
    if not entries:
        return []
    if not library.is_available():
        raise library.LibraryUnavailable('video database not available')

    resolved = []
    relocated = {}
    missing = set()
    used_ids = {entry['movieid'] for entry in entries}

    for entry in entries:
        details = library.get_movie(entry['movieid'], library.DETAIL_PROPERTIES)
        if details is None:
            # Make sure "not found" is not caused by the detail query itself.
            probe = library.get_movie(entry['movieid'], library.REFERENCE_PROPERTIES)
            if probe is not None:
                common.log('Detail query failed for movie {0}, showing basic data'
                           .format(entry['movieid']), xbmc.LOGWARNING)
                details = probe
        if details is not None and not library.matches(entry, details):
            common.log('Movie id {0} now belongs to a different movie'.format(entry['movieid']))
            details = None

        if details is None:
            found = library.relocate(entry)
            if found is not None and found['movieid'] not in used_ids:
                new_entry = storage.make_entry(found['movieid'], added=entry.get('added'),
                                               **_reference_kwargs(found))
                details = library.get_movie(found['movieid'], library.DETAIL_PROPERTIES) or found
                common.log('Movie "{0}" re-located: id {1} -> {2}'.format(
                    entry.get('title'), entry['movieid'], found['movieid']), xbmc.LOGINFO)
                relocated[entry['movieid']] = new_entry
                used_ids.add(found['movieid'])
                entry = new_entry
            else:
                common.log('Movie "{0}" (id {1}) is no longer in the library'.format(
                    entry.get('title'), entry['movieid']), xbmc.LOGINFO)
                missing.add(entry['movieid'])
                continue

        resolved.append((entry, details))

    if relocated or missing:
        try:
            storage.apply_validation(relocated, missing)
        except storage.StorageError:
            common.notify(common.localize(32032))
        properties.sync(storage.read_entries())
        if missing:
            common.notify(common.localize(32028, len(missing)))
    return resolved


def _reference_kwargs(details):
    ref = library.reference_from_details(details)
    return {'title': ref['title'], 'year': ref['year'], 'file_path': ref['file'],
            'uniqueid': ref['uniqueid']}


def add_movie(movieid):
    """Add a library movie. Returns (status, title).

    status is one of 'added', 'exists', 'notfound', 'unavailable', 'error'.
    """
    try:
        details = library.get_movie(movieid, library.REFERENCE_PROPERTIES)
    except library.LibraryUnavailable:
        return 'unavailable', ''
    if details is None:
        return 'notfound', ''
    entry = storage.make_entry(movieid, **_reference_kwargs(details))
    try:
        added = storage.add(entry)
    except storage.StorageError:
        return 'error', entry['title']
    properties.sync(storage.read_entries())
    return ('added' if added else 'exists'), entry['title']


def remove_movie(movieid):
    """Remove a movie. Returns (status, title); status 'removed', 'absent' or 'error'."""
    try:
        removed = storage.remove(movieid)
    except storage.StorageError:
        return 'error', ''
    properties.sync(storage.read_entries())
    if removed is None:
        return 'absent', ''
    return 'removed', removed.get('title') or ''


def notify_add_result(status, title, icon=None):
    messages = {
        'added': (32020, True),
        'exists': (32021, True),
        'notfound': (32030, False),
        'unavailable': (32029, False),
        'error': (32032, False),
    }
    string_id, with_title = messages.get(status, (32036, False))
    message = common.localize(string_id, title) if with_title else common.localize(string_id)
    common.notify(message, icon=icon)


def notify_remove_result(status, title, icon=None):
    if status == 'removed':
        common.notify(common.localize(32022, title), icon=icon)
    elif status == 'absent':
        common.notify(common.localize(32023))
    else:
        common.notify(common.localize(32032))
