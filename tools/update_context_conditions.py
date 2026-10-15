#!/usr/bin/env python3
"""Regenerate the <visible> conditions of the context menu items in addon.xml.

The number of slots must match properties.SLOT_COUNT in resources/lib.
Usage: python3 tools/update_context_conditions.py
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDON_DIR = os.path.join(ROOT, 'plugin.video.movieshortlist')
ADDON_XML = os.path.join(ADDON_DIR, 'addon.xml')
PROPERTIES_PY = os.path.join(ADDON_DIR, 'resources', 'lib', 'properties.py')

BASE = ('String.IsEqual(ListItem.DBType,movie) + !String.IsEmpty(ListItem.DBID) + '
        '!String.StartsWith(Container.FolderPath,plugin://plugin.video.movieshortlist/)')


def slot_count():
    with open(PROPERTIES_PY, encoding='utf-8') as handle:
        return int(re.search(r'^SLOT_COUNT = (\d+)$', handle.read(), re.M).group(1))


def listed_condition(count):
    slots = ' | '.join(
        'String.IsEqual(Window(Home).Property(movieshortlist.slot{0}),ListItem.DBID)'.format(i)
        for i in range(1, count + 1))
    return '[' + slots + ']'


def conditions(count):
    listed = listed_condition(count)
    return {'context_add.py': BASE + ' + !' + listed,
            'context_remove.py': BASE + ' + ' + listed}


def main():
    with open(ADDON_XML, encoding='utf-8') as handle:
        xml = handle.read()
    for library, condition in conditions(slot_count()).items():
        pattern = re.compile(r'(<item library="' + re.escape(library) +
                             r'">\s*<label>\d+</label>\s*<visible>)(.*?)(</visible>)', re.S)
        xml, replaced = pattern.subn(lambda m: m.group(1) + condition + m.group(3), xml)
        if replaced != 1:
            sys.exit('context item for {0} not found in addon.xml'.format(library))
    with open(ADDON_XML, 'w', encoding='utf-8') as handle:
        handle.write(xml)
    print('addon.xml updated')


if __name__ == '__main__':
    main()
