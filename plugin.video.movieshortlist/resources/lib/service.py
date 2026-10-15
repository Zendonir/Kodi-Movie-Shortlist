# -*- coding: utf-8 -*-
"""Background service: publishes the shortlist ids for the context menu.

Kodi starts service add-ons after a profile has been loaded and stops them
before another profile is loaded (CProfileManager / CServiceAddonManager). This keeps the context menu labels
("add" / "remove") correct right after start-up and after profile changes.
"""

import xbmc

from . import common, properties, storage


def run():
    monitor = xbmc.Monitor()
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
