# -*- coding: utf-8 -*-
"""Builds library-like ListItems from JSON-RPC movie details.

The ListItem path is the real file of the library movie and the info tag
carries the library ``dbid``. Kodi therefore treats a click like one in the
movie library: the "default select action" (play / resume / choose / info)
applies, external players from playercorefactory.xml are selected by the
file path, and the watched state / resume point are stored for that file,
i.e. for the library movie itself.
"""

import xbmc
import xbmcgui

ART_KEYS = ('poster', 'fanart', 'thumb', 'banner', 'clearlogo', 'clearart', 'landscape',
            'discart', 'keyart', 'characterart')


def _str_list(value):
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item]
    if isinstance(value, str) and value:
        return [value]
    return []


def _int(value):
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _float(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return 0.0


def _str(value):
    return value if isinstance(value, str) else ''


def build_art(details):
    art = {}
    source = details.get('art') if isinstance(details.get('art'), dict) else {}
    for key in ART_KEYS:
        value = source.get(key)
        if isinstance(value, str) and value:
            art[key] = value
    if 'thumb' not in art and art.get('poster'):
        art['thumb'] = art['poster']
    if not art.get('poster') and not art.get('thumb'):
        art['icon'] = 'DefaultVideo.png'
    return art


def _set_ratings(tag, details):
    ratings = details.get('ratings')
    if not isinstance(ratings, dict):
        return
    converted = {}
    default = ''
    for name, data in ratings.items():
        if not isinstance(data, dict):
            continue
        rating = _float(data.get('rating'))
        if rating <= 0:
            continue
        converted[name] = (rating, _int(data.get('votes')))
        if data.get('default'):
            default = name
    if converted:
        tag.setRatings(converted, default or next(iter(converted)))


def _set_streams(tag, details):
    streams = details.get('streamdetails')
    if not isinstance(streams, dict):
        return
    for video in streams.get('video') or []:
        if isinstance(video, dict):
            tag.addVideoStream(xbmc.VideoStreamDetail(
                width=_int(video.get('width')), height=_int(video.get('height')),
                aspect=_float(video.get('aspect')), duration=_int(video.get('duration')),
                codec=_str(video.get('codec')), stereomode=_str(video.get('stereomode')),
                language=_str(video.get('language')), hdrtype=_str(video.get('hdrtype'))))
    for audio in streams.get('audio') or []:
        if isinstance(audio, dict):
            channels = audio.get('channels')
            tag.addAudioStream(xbmc.AudioStreamDetail(
                channels=channels if isinstance(channels, int) else -1,
                codec=_str(audio.get('codec')), language=_str(audio.get('language'))))
    for subtitle in streams.get('subtitle') or []:
        if isinstance(subtitle, dict):
            tag.addSubtitleStream(xbmc.SubtitleStreamDetail(language=_str(subtitle.get('language'))))


def _set_cast(tag, details):
    cast = details.get('cast')
    if not isinstance(cast, list):
        return
    actors = []
    for member in cast:
        if isinstance(member, dict) and _str(member.get('name')):
            actors.append(xbmc.Actor(_str(member.get('name')), _str(member.get('role')),
                                     _int(member.get('order')), _str(member.get('thumbnail'))))
    if actors:
        tag.setCast(actors)


def build_listitem(details, context_menu=None):
    """Return (url, ListItem) for a movie dict from VideoLibrary.GetMovieDetails."""
    movieid = _int(details.get('movieid'))
    file_path = _str(details.get('file'))
    title = _str(details.get('title')) or _str(details.get('label'))

    listitem = xbmcgui.ListItem(label=title, path=file_path, offscreen=True)
    listitem.setArt(build_art(details))

    tag = listitem.getVideoInfoTag()
    tag.setMediaType('movie')
    tag.setDbId(movieid)
    tag.setTitle(title)
    tag.setFilenameAndPath(file_path)
    tag.setOriginalTitle(_str(details.get('originaltitle')))
    tag.setSortTitle(_str(details.get('sorttitle')))
    tag.setYear(_int(details.get('year')))
    tag.setPremiered(_str(details.get('premiered')))
    tag.setDuration(_int(details.get('runtime')))
    tag.setGenres(_str_list(details.get('genre')))
    tag.setPlot(_str(details.get('plot')))
    tag.setPlotOutline(_str(details.get('plotoutline')))
    tag.setTagLine(_str(details.get('tagline')))
    tag.setMpaa(_str(details.get('mpaa')))
    tag.setDirectors(_str_list(details.get('director')))
    tag.setWriters(_str_list(details.get('writer')))
    tag.setStudios(_str_list(details.get('studio')))
    tag.setCountries(_str_list(details.get('country')))
    tag.setTags(_str_list(details.get('tag')))
    tag.setTrailer(_str(details.get('trailer')))
    tag.setTop250(_int(details.get('top250')))
    tag.setUserRating(_int(details.get('userrating')))
    tag.setPlaycount(_int(details.get('playcount')))
    tag.setLastPlayed(_str(details.get('lastplayed')))
    tag.setDateAdded(_str(details.get('dateadded')))
    if _str(details.get('set')):
        tag.setSet(_str(details.get('set')))
        tag.setSetId(_int(details.get('setid')))

    uniqueid = details.get('uniqueid')
    if isinstance(uniqueid, dict):
        ids = {key: value for key, value in uniqueid.items()
               if isinstance(key, str) and isinstance(value, str) and value}
        if ids:
            default_id = 'imdb' if 'imdb' in ids else next(iter(ids))
            tag.setUniqueIDs(ids, default_id)
            if 'imdb' in ids:
                tag.setIMDBNumber(ids['imdb'])

    _set_ratings(tag, details)

    resume = details.get('resume')
    if isinstance(resume, dict) and _float(resume.get('position')) > 0:
        tag.setResumePoint(_float(resume.get('position')), _float(resume.get('total')))

    _set_streams(tag, details)
    _set_cast(tag, details)

    if context_menu:
        listitem.addContextMenuItems(context_menu)
    return file_path, listitem
