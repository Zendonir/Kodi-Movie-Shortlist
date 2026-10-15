# -*- coding: utf-8 -*-
"""Read-only access to Kodi's video library via JSON-RPC.

JSON-RPC is used instead of touching the database directly, so it works the
same for the local SQLite database and for a shared MySQL/MariaDB library.
Nothing in here writes to the library.
"""

import json
import unicodedata

import xbmc

from . import common

# Error codes defined by the JSON-RPC spec, as returned by Kodi.
ERROR_INVALID_PARAMS = -32602

# Properties used for displaying a movie (all are valid Video.Fields.Movie).
DETAIL_PROPERTIES = [
    'title', 'originaltitle', 'sorttitle', 'year', 'premiered', 'runtime', 'genre',
    'plot', 'plotoutline', 'tagline', 'mpaa', 'director', 'writer', 'studio', 'country',
    'cast', 'set', 'setid', 'tag', 'trailer', 'top250', 'userrating', 'ratings',
    'uniqueid', 'playcount', 'lastplayed', 'resume', 'dateadded', 'file', 'art',
    'streamdetails',
]

# Small set used to identify a movie when adding it / re-locating it.
REFERENCE_PROPERTIES = ['title', 'year', 'file', 'uniqueid']


class LibraryUnavailable(Exception):
    """The video library (e.g. a remote MariaDB server) cannot be accessed."""


def _call(method, params=None):
    """Execute a JSON-RPC request. Returns (result, error)."""
    request = {'jsonrpc': '2.0', 'id': 1, 'method': method}
    if params:
        request['params'] = params
    raw = xbmc.executeJSONRPC(json.dumps(request))
    try:
        response = json.loads(raw)
    except (TypeError, ValueError):
        common.log('Invalid JSON-RPC response for {0}'.format(method), xbmc.LOGERROR)
        raise LibraryUnavailable(method)
    if not isinstance(response, dict):
        raise LibraryUnavailable(method)
    error = response.get('error')
    if error:
        return None, error if isinstance(error, dict) else {'code': 0, 'message': str(error)}
    return response.get('result'), None


def is_available():
    """Check whether the video database can be opened."""
    try:
        result, error = _call('VideoLibrary.GetMovies',
                              {'limits': {'start': 0, 'end': 1}, 'properties': []})
    except LibraryUnavailable:
        return False
    if error:
        common.log('Video library not available: {0}'.format(error.get('message')),
                   xbmc.LOGWARNING)
        return False
    return isinstance(result, dict)


def get_movie(movieid, properties=None):
    """Return the movie details dict, or None if the movie does not exist.

    Raises LibraryUnavailable when the database cannot be accessed.
    """
    result, error = _call('VideoLibrary.GetMovieDetails',
                          {'movieid': int(movieid),
                           'properties': properties or REFERENCE_PROPERTIES})
    if error:
        if error.get('code') == ERROR_INVALID_PARAMS:
            # Kodi answers "invalid params" for unknown ids.
            return None
        common.log('GetMovieDetails({0}) failed: {1}'.format(movieid, error.get('message')),
                   xbmc.LOGWARNING)
        raise LibraryUnavailable(error.get('message'))
    details = (result or {}).get('moviedetails')
    if not isinstance(details, dict) or not details.get('movieid'):
        return None
    return details


def find_movies_by_title(title):
    """Return library movies with exactly this title (reference properties only)."""
    if not title:
        return []
    result, error = _call('VideoLibrary.GetMovies', {
        'filter': {'field': 'title', 'operator': 'is', 'value': title},
        'properties': REFERENCE_PROPERTIES,
    })
    if error:
        common.log('Title lookup failed: {0}'.format(error.get('message')), xbmc.LOGWARNING)
        raise LibraryUnavailable(error.get('message'))
    movies = (result or {}).get('movies')
    return movies if isinstance(movies, list) else []


def _norm(text):
    return unicodedata.normalize('NFKC', text or '').casefold().strip()


def matches(entry, details):
    """Decide whether library ``details`` describe the stored ``entry``.

    Kodi may re-use ids (SQLite) or a library may be rebuilt, so the stored
    id alone is not trusted blindly.
    """
    if entry.get('file') and entry.get('file') == details.get('file'):
        return True
    stored_ids = entry.get('uniqueid') or {}
    library_ids = details.get('uniqueid') or {}
    shared = [key for key in stored_ids if key in library_ids]
    if shared:
        return any(stored_ids[key] == library_ids[key] for key in shared)
    if not entry.get('title'):
        # Old/minimal entry without identifying data: trust the id.
        return True
    if _norm(entry.get('title')) != _norm(details.get('title')):
        return False
    stored_year = entry.get('year') or 0
    library_year = details.get('year') or 0
    return not stored_year or not library_year or stored_year == library_year


def relocate(entry):
    """Try to find a movie whose id changed (e.g. after a library rebuild).

    Returns the details (reference properties) or None.
    """
    for candidate in find_movies_by_title(entry.get('title')):
        if matches(entry, candidate):
            return candidate
    return None


def reference_from_details(details):
    """Extract the identifying subset stored in the shortlist."""
    uniqueid = details.get('uniqueid')
    return {
        'title': details.get('title') or '',
        'year': details.get('year') or 0,
        'file': details.get('file') or '',
        'uniqueid': uniqueid if isinstance(uniqueid, dict) else {},
    }
