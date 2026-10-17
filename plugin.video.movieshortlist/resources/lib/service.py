# -*- coding: utf-8 -*-
"""Background service.

- Publishes the shortlist ids for the context menu. Kodi starts service
  add-ons after a profile has been loaded and stops them before another
  profile is loaded (CProfileManager / CServiceAddonManager), so the context
  menu labels ("add" / "remove") are correct after start-up and profile changes.
- Removes movies from the shortlist once they have been watched, so the list
  can be worked through movie by movie. Kodi announces
  ``VideoLibrary.OnUpdate`` with a ``playcount`` whenever the watched state of
  a library movie changes (CVideoDatabase::SetPlayCount) - no matter whether
  it was started from the shortlist, the random pick, the library or with an
  external player.
"""

import json

import xbmc
import xbmcaddon

from . import common, properties, shortlist, storage


def remove_watched_enabled():
    # A fresh Addon object always reflects the current settings.
    try:
        return xbmcaddon.Addon(common.ADDON_ID).getSettingBool('remove_watched')
    except Exception:  # pylint: disable=broad-except
        return True


def watched_movie_id(method, data):
    """Return the movie id if the notification says a movie was watched, else 0."""
    if method != 'VideoLibrary.OnUpdate':
        return 0
    try:
        payload = json.loads(data) if isinstance(data, str) else data
    except ValueError:
        return 0
    if not isinstance(payload, dict) or payload.get('transaction'):
        return 0
    playcount = payload.get('playcount')
    item = payload.get('item')
    if not isinstance(playcount, int) or isinstance(playcount, bool) or playcount <= 0:
        return 0
    if not isinstance(item, dict) or item.get('type') != 'movie':
        return 0
    movieid = item.get('id')
    return movieid if isinstance(movieid, int) and not isinstance(movieid, bool) else 0


def handle_notification(method, data):
    movieid = watched_movie_id(method, data)
    if movieid <= 0 or not remove_watched_enabled():
        return
    if not any(entry['movieid'] == movieid for entry in storage.read_entries()):
        return
    status, title = shortlist.remove_movie(movieid)
    common.log('Watched movie {0} removed from shortlist: {1}'.format(movieid, status),
               xbmc.LOGINFO)
    if status == 'removed':
        common.notify(common.localize(32050, title))
        common.refresh_container_if_plugin()


class ShortlistMonitor(xbmc.Monitor):
    def onNotification(self, sender, method, data):
        try:
            handle_notification(method, data)
        except Exception as exc:  # pylint: disable=broad-except
            common.log('Notification handling failed: {0!r}'.format(exc), xbmc.LOGERROR)


def run():
    monitor = ShortlistMonitor()
    try:
        entries = storage.read_entries()
        properties.sync(entries)
        common.log('Service started, {0} movie(s) on the shortlist'.format(len(entries)))
    except Exception as exc:  # pylint: disable=broad-except
        common.log('Could not initialise shortlist properties: {0!r}'.format(exc), xbmc.LOGERROR)
    monitor.waitForAbort()
    # Do not leak this profile's list into the next profile.
    properties.clear()
    common.log('Service stopped')
