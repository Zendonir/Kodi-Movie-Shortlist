#!/usr/bin/env python3
"""Build the installable ZIPs and the Kodi repository.

Usage: python3 tools/build_release.py

Creates
  dist/plugin.video.movieshortlist-<version>.zip   add-on, for manual installation
  dist/repository.movieshortlist-<version>.zip     repository add-on (enables auto-updates)
  repo/                                            what Kodi downloads from GitHub:
    addons.xml, addons.xml.md5
    <addon id>/<addon id>-<version>.zip (+ .sha256), icon/fanart

Release workflow: raise the version in plugin.video.movieshortlist/addon.xml,
run this script, commit and push to main. Kodi installations with the
repository add-on pick up the new version with their next update check.
"""

import hashlib
import os
import re
import shutil
import xml.etree.ElementTree as ET
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDONS = ('plugin.video.movieshortlist', 'repository.movieshortlist')
DIST_DIR = os.path.join(ROOT, 'dist')
REPO_DIR = os.path.join(ROOT, 'repo')
EXCLUDE_DIRS = {'__pycache__'}
EXCLUDE_SUFFIXES = ('.pyc', '.pyo', '.orig', '.rej', '~')
# Fixed timestamp -> rebuilding unchanged sources gives byte-identical ZIPs.
ZIP_DATE = (2026, 1, 1, 0, 0, 0)


def addon_info(addon_id):
    path = os.path.join(ROOT, addon_id, 'addon.xml')
    root = ET.parse(path).getroot()
    if root.get('id') != addon_id:
        raise SystemExit('{0}: id in addon.xml does not match folder'.format(addon_id))
    return root.get('version'), root


def build_zip(addon_id, version, target):
    source = os.path.join(ROOT, addon_id)
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for folder, dirs, files in os.walk(source):
            dirs[:] = sorted(d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith('.'))
            for name in sorted(files):
                if name.endswith(EXCLUDE_SUFFIXES) or name.startswith('.'):
                    continue
                path = os.path.join(folder, name)
                # Kodi expects the add-on id as the top-level folder inside the ZIP.
                arcname = '/'.join([addon_id] + os.path.relpath(path, source).split(os.sep))
                info = zipfile.ZipInfo(arcname, ZIP_DATE)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                with open(path, 'rb') as handle:
                    archive.writestr(info, handle.read())


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(65536), b''):
            digest.update(chunk)
    return digest.hexdigest()


def copy_art(addon_id, root, target_dir):
    """Copy icon/fanart so Kodi can show them before installation."""
    for asset in root.iter('assets'):
        for element in asset:
            if element.text:
                source = os.path.join(ROOT, addon_id, element.text)
                destination = os.path.join(target_dir, element.text)
                os.makedirs(os.path.dirname(destination), exist_ok=True)
                shutil.copyfile(source, destination)


def main():
    os.makedirs(DIST_DIR, exist_ok=True)
    os.makedirs(REPO_DIR, exist_ok=True)
    index_parts = []
    for addon_id in ADDONS:
        version, root = addon_info(addon_id)
        dist_zip = os.path.join(DIST_DIR, '{0}-{1}.zip'.format(addon_id, version))
        build_zip(addon_id, version, dist_zip)

        target_dir = os.path.join(REPO_DIR, addon_id)
        os.makedirs(target_dir, exist_ok=True)
        repo_zip = os.path.join(target_dir, os.path.basename(dist_zip))
        shutil.copyfile(dist_zip, repo_zip)
        with open(repo_zip + '.sha256', 'w', encoding='ascii') as handle:
            handle.write(sha256(repo_zip))
        copy_art(addon_id, root, target_dir)

        with open(os.path.join(ROOT, addon_id, 'addon.xml'), encoding='utf-8') as handle:
            xml = handle.read()
        xml = re.sub(r'^<\?xml[^>]*\?>\s*', '', xml).strip()
        index_parts.append(xml)
        print('{0} {1}'.format(addon_id, version))

    index = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<addons>\n'
             + '\n'.join(index_parts) + '\n</addons>\n')
    ET.fromstring(index.encode('utf-8'))  # must stay valid XML
    index_path = os.path.join(REPO_DIR, 'addons.xml')
    with open(index_path, 'w', encoding='utf-8', newline='\n') as handle:
        handle.write(index)
    with open(index_path, 'rb') as handle:
        md5 = hashlib.md5(handle.read()).hexdigest()
    with open(index_path + '.md5', 'w', encoding='ascii') as handle:
        handle.write(md5)
    print('repo/addons.xml updated')


if __name__ == '__main__':
    main()
