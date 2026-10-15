# -*- coding: utf-8 -*-
"""Shared helpers: add-on handle, localisation, logging and notifications."""

import xbmc
import xbmcaddon
import xbmcgui

ADDON_ID = 'plugin.video.movieshortlist'
PLUGIN_URL = 'plugin://{0}/'.format(ADDON_ID)

_ADDON = None
_DEBUG = None


def addon():
    """Return the (cached) xbmcaddon.Addon instance of this add-on."""
    global _ADDON
    if _ADDON is None:
        _ADDON = xbmcaddon.Addon(ADDON_ID)
    return _ADDON


def localize(string_id, *args):
    """Return a localised add-on string, optionally formatted with ``args``."""
    text = addon().getLocalizedString(string_id)
    if args:
        try:
            text = text.format(*args)
        except (IndexError, KeyError, ValueError):
            pass
    return text


def addon_name():
    return addon().getAddonInfo('name')


def addon_icon():
    return addon().getAddonInfo('icon')


def _debug_enabled():
    global _DEBUG
    if _DEBUG is None:
        try:
            _DEBUG = addon().getSettingBool('debug_logging')
        except Exception:  # pylint: disable=broad-except
            _DEBUG = False
    return _DEBUG


def log(message, level=xbmc.LOGDEBUG):
    """Write to the Kodi log.

    Debug messages are only promoted to INFO when the add-on setting
    "debug logging" is enabled, so the Kodi log stays clean by default.
    """
    if level == xbmc.LOGDEBUG and _debug_enabled():
        level = xbmc.LOGINFO
    xbmc.log('[{0}] {1}'.format(ADDON_ID, message), level)


def notify(message, icon=None, time_ms=3000):
    """Show a standard Kodi toast notification (no sound)."""
    xbmcgui.Dialog().notification(addon_name(), message, icon or addon_icon(), time_ms, False)


def container_is_plugin():
    """True if the currently shown container belongs to this add-on."""
    return xbmc.getInfoLabel('Container.FolderPath').startswith(PLUGIN_URL)


def refresh_container_if_plugin():
    if container_is_plugin():
        xbmc.executebuiltin('Container.Refresh')
