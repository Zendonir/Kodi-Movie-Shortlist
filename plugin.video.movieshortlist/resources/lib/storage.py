# -*- coding: utf-8 -*-
"""Persistent storage of the shortlist in the add-on profile directory.

The file lives in ``special://profile/addon_data/plugin.video.movieshortlist/``
which Kodi resolves per Kodi profile, so every profile gets its own list.

Only references are stored (movieid plus a few identifying fields that are
needed to detect re-used or changed ids); all displayed metadata is read
live from Kodi's library via JSON-RPC.
"""

import json
import os
import time
from contextlib import contextmanager

import xbmc
import xbmcvfs

from . import common

FILE_NAME = 'shortlist.json'
LOCK_NAME = 'shortlist.lock'
FORMAT_VERSION = 1

_LOCK_TIMEOUT = 5.0
_LOCK_STALE_AFTER = 30.0


class StorageError(Exception):
    """Raised when the shortlist cannot be written."""


def _profile_dir():
    path = xbmcvfs.translatePath(common.addon().getAddonInfo('profile'))
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)
    return path


def _file_path():
    return os.path.join(_profile_dir(), FILE_NAME)


def make_entry(movieid, title='', year=0, file_path='', uniqueid=None, added=None):
    """Build a normalised storage entry."""
    ids = {}
    for key, value in (uniqueid or {}).items():
        if isinstance(key, str) and isinstance(value, str) and key and value:
            ids[key] = value
    return {
        'movieid': int(movieid),
        'title': title if isinstance(title, str) else '',
        'year': year if isinstance(year, int) else 0,
        'file': file_path if isinstance(file_path, str) else '',
        'uniqueid': ids,
        'added': float(added) if added is not None else time.time(),
    }


def _sanitize(raw_entries):
    """Drop malformed or duplicate entries instead of failing completely."""
    entries = []  # type: list
    seen = set()
    if not isinstance(raw_entries, list):
        return entries
    for raw in raw_entries:
        if not isinstance(raw, dict):
            continue
        movieid = raw.get('movieid')
        if isinstance(movieid, bool) or not isinstance(movieid, int) or movieid <= 0:
            continue
        if movieid in seen:
            continue
        added = raw.get('added')
        if isinstance(added, bool) or not isinstance(added, (int, float)):
            added = 0.0
        seen.add(movieid)
        entries.append(make_entry(movieid, raw.get('title'), raw.get('year'), raw.get('file'),
                                  raw.get('uniqueid') if isinstance(raw.get('uniqueid'), dict) else None,
                                  added))
    return entries


def _backup_corrupt_file(path):
    backup = '{0}.corrupt-{1}'.format(path, time.strftime('%Y%m%d-%H%M%S'))
    try:
        os.replace(path, backup)
        common.log('Corrupt shortlist moved to {0}'.format(backup), xbmc.LOGWARNING)
    except OSError as exc:
        common.log('Could not move corrupt shortlist away: {0}'.format(exc), xbmc.LOGERROR)


def read_entries():
    """Return the stored entries (list of dicts). Never raises."""
    try:
        path = _file_path()
    except OSError as exc:
        common.log('Profile directory not accessible: {0}'.format(exc), xbmc.LOGERROR)
        return []
    if not os.path.exists(path):
        return []
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            data = json.load(handle)
        if not isinstance(data, dict) or not isinstance(data.get('entries'), list):
            raise ValueError('unexpected structure')
    except (ValueError, UnicodeDecodeError) as exc:
        common.log('Shortlist file is damaged ({0}), starting with an empty list'.format(exc),
                   xbmc.LOGWARNING)
        _backup_corrupt_file(path)
        common.notify(common.localize(32031))
        return []
    except OSError as exc:
        common.log('Could not read shortlist: {0}'.format(exc), xbmc.LOGERROR)
        return []
    return _sanitize(data['entries'])


def _write_entries(entries):
    path = _file_path()
    tmp_path = path + '.tmp'
    data = {'version': FORMAT_VERSION, 'entries': entries}
    try:
        with open(tmp_path, 'w', encoding='utf-8') as handle:
            json.dump(data, handle, ensure_ascii=False, indent=1)
            handle.flush()
            os.fsync(handle.fileno())
        for attempt in range(20):
            try:
                os.replace(tmp_path, path)
                break
            except PermissionError:
                # Windows refuses to replace a file another process is reading
                # at this very moment; that read takes only milliseconds.
                if attempt == 19:
                    raise
                time.sleep(0.05)
    except OSError as exc:
        common.log('Could not write shortlist: {0}'.format(exc), xbmc.LOGERROR)
        raise StorageError(str(exc))


@contextmanager
def _locked():
    """Simple cross-process lock (context menu scripts and the plugin run in
    separate Python interpreters and may write concurrently)."""
    lock_path = os.path.join(_profile_dir(), LOCK_NAME)
    deadline = time.time() + _LOCK_TIMEOUT
    fd = None
    while fd is None:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                if time.time() - os.path.getmtime(lock_path) > _LOCK_STALE_AFTER:
                    os.remove(lock_path)
                    continue
            except OSError:
                continue
            if time.time() > deadline:
                common.log('Shortlist lock timed out, continuing without lock', xbmc.LOGWARNING)
                break
            time.sleep(0.05)
        except OSError as exc:
            common.log('Could not create lock file: {0}'.format(exc), xbmc.LOGWARNING)
            break
    try:
        yield
    finally:
        if fd is not None:
            os.close(fd)
            try:
                os.remove(lock_path)
            except OSError:
                pass


def add(entry):
    """Add an entry. Returns False if the movie is already on the list."""
    with _locked():
        entries = read_entries()
        if any(item['movieid'] == entry['movieid'] for item in entries):
            return False
        entries.append(entry)
        _write_entries(entries)
    return True


def remove(movieid):
    """Remove a movie by id. Returns the removed entry or None."""
    with _locked():
        entries = read_entries()
        remaining = [item for item in entries if item['movieid'] != movieid]
        if len(remaining) == len(entries):
            return None
        removed = next(item for item in entries if item['movieid'] == movieid)
        _write_entries(remaining)
    return removed


def clear():
    """Remove all entries. Returns the number of removed entries."""
    with _locked():
        count = len(read_entries())
        _write_entries([])
    return count


def apply_validation(relocated, missing):
    """Persist the result of a library validation run.

    :param relocated: dict old movieid -> updated entry (movie got a new id)
    :param missing: set of movieids that no longer exist in the library
    """
    if not relocated and not missing:
        return
    with _locked():
        entries = read_entries()
        result = []
        seen = set()
        for item in entries:
            if item['movieid'] in missing:
                continue
            item = relocated.get(item['movieid'], item)
            if item['movieid'] in seen:
                continue
            seen.add(item['movieid'])
            result.append(item)
        _write_entries(result)
