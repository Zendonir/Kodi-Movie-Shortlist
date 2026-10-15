# -*- coding: utf-8 -*-
"""Sort orders of the shortlist (pure Python, no Kodi dependency)."""

import unicodedata

SORT_ADDED = 0
SORT_TITLE = 1
SORT_YEAR = 2
SORT_IMDB = 3
SORT_RUNTIME = 4

SORT_ORDERS = (SORT_ADDED, SORT_TITLE, SORT_YEAR, SORT_IMDB, SORT_RUNTIME)

# Localised labels (strings.po ids) for each sort order.
SORT_LABELS = {
    SORT_ADDED: 32040,
    SORT_TITLE: 32041,
    SORT_YEAR: 32042,
    SORT_IMDB: 32043,
    SORT_RUNTIME: 32044,
}


def title_key(details):
    """Case- and accent-insensitive title key (honours Kodi's sort title)."""
    text = details.get('sorttitle') or details.get('title') or ''
    decomposed = unicodedata.normalize('NFKD', text)
    return ''.join(ch for ch in decomposed if not unicodedata.combining(ch)).casefold()


def imdb_rating(details):
    """IMDb rating of a movie or None if the library has none."""
    ratings = details.get('ratings')
    if not isinstance(ratings, dict):
        return None
    imdb = ratings.get('imdb')
    if not isinstance(imdb, dict):
        return None
    rating = imdb.get('rating')
    if isinstance(rating, (int, float)) and not isinstance(rating, bool) and rating > 0:
        return float(rating)
    return None


def _positive_int(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 0


def sort_movies(items, order):
    """Sort a list of (entry, details) tuples. Missing values always go last."""
    if order == SORT_TITLE:
        return sorted(items, key=lambda item: title_key(item[1]))
    if order == SORT_YEAR:
        return sorted(items, key=lambda item: (_positive_int(item[1].get('year')) == 0,
                                               -_positive_int(item[1].get('year')),
                                               title_key(item[1])))
    if order == SORT_IMDB:
        def imdb_key(item):
            rating = imdb_rating(item[1])
            return (rating is None, -(rating or 0.0), title_key(item[1]))
        return sorted(items, key=imdb_key)
    if order == SORT_RUNTIME:
        return sorted(items, key=lambda item: (_positive_int(item[1].get('runtime')) == 0,
                                               _positive_int(item[1].get('runtime')),
                                               title_key(item[1])))
    # SORT_ADDED (default): newest first; stable for equal timestamps.
    indexed = list(enumerate(items))
    indexed.sort(key=lambda pair: (-(pair[1][0].get('added') or 0.0), -pair[0]))
    return [item for _, item in indexed]
