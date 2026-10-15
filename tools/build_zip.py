#!/usr/bin/env python3
"""Build an installable Kodi add-on ZIP: dist/plugin.video.movieshortlist-<version>.zip

Usage: python3 tools/build_zip.py
"""

import os
import xml.etree.ElementTree as ET
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDON_ID = 'plugin.video.movieshortlist'
ADDON_DIR = os.path.join(ROOT, ADDON_ID)
EXCLUDE_DIRS = {'__pycache__', '.git', '.idea', '.vscode'}
EXCLUDE_SUFFIXES = ('.pyc', '.pyo', '.orig', '.rej', '~')


def main():
    version = ET.parse(os.path.join(ADDON_DIR, 'addon.xml')).getroot().get('version')
    os.makedirs(os.path.join(ROOT, 'dist'), exist_ok=True)
    target = os.path.join(ROOT, 'dist', '{0}-{1}.zip'.format(ADDON_ID, version))
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for folder, dirs, files in os.walk(ADDON_DIR):
            dirs[:] = sorted(d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith('.'))
            for name in sorted(files):
                if name.endswith(EXCLUDE_SUFFIXES) or name.startswith('.'):
                    continue
                path = os.path.join(folder, name)
                # Kodi expects the add-on id as the top-level folder inside the ZIP.
                arcname = os.path.join(ADDON_ID, os.path.relpath(path, ADDON_DIR))
                archive.write(path, arcname.replace(os.sep, '/'))
    print(target)


if __name__ == '__main__':
    main()
