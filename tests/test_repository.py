# -*- coding: utf-8 -*-
"""Checks that the published Kodi repository matches the add-on sources."""

import hashlib
import os
import unittest
import xml.etree.ElementTree as ET
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDONS = ('plugin.video.movieshortlist', 'repository.movieshortlist')
RAW = 'https://raw.githubusercontent.com/Zendonir/Kodi-Movie-Shortlist/main/repo/'


def version_of(addon_id):
    return ET.parse(os.path.join(ROOT, addon_id, 'addon.xml')).getroot().get('version')


class RepositoryTests(unittest.TestCase):
    def test_index_lists_current_versions(self):
        index = ET.parse(os.path.join(ROOT, 'repo', 'addons.xml')).getroot()
        listed = {addon.get('id'): addon.get('version') for addon in index.findall('addon')}
        self.assertEqual(listed, {addon_id: version_of(addon_id) for addon_id in ADDONS},
                         'run python3 tools/build_release.py')

    def test_index_checksum(self):
        with open(os.path.join(ROOT, 'repo', 'addons.xml'), 'rb') as handle:
            md5 = hashlib.md5(handle.read()).hexdigest()
        with open(os.path.join(ROOT, 'repo', 'addons.xml.md5'), encoding='ascii') as handle:
            self.assertEqual(handle.read().strip(), md5)

    def test_zips_exist_with_hashes_and_layout(self):
        for addon_id in ADDONS:
            name = '{0}-{1}.zip'.format(addon_id, version_of(addon_id))
            repo_zip = os.path.join(ROOT, 'repo', addon_id, name)
            with open(repo_zip, 'rb') as handle:
                data = handle.read()
            with open(repo_zip + '.sha256', encoding='ascii') as handle:
                self.assertEqual(handle.read().strip(), hashlib.sha256(data).hexdigest())
            with open(os.path.join(ROOT, 'dist', name), 'rb') as handle:
                self.assertEqual(handle.read(), data)
            with zipfile.ZipFile(repo_zip) as archive:
                names = archive.namelist()
                self.assertTrue(all(n.startswith(addon_id + '/') for n in names))
                self.assertIn(addon_id + '/addon.xml', names)
                self.assertFalse([n for n in names if '__pycache__' in n or n.endswith('.pyc')])

    def test_repository_points_to_this_repo(self):
        root = ET.parse(os.path.join(ROOT, 'repository.movieshortlist', 'addon.xml')).getroot()
        directory = root.find("extension[@point='xbmc.addon.repository']/dir")
        self.assertEqual(directory.find('info').text, RAW + 'addons.xml')
        self.assertEqual(directory.find('checksum').text, RAW + 'addons.xml.md5')
        self.assertEqual(directory.find('datadir').text, RAW)
        self.assertEqual(directory.find('hashes').text, 'sha256')


if __name__ == '__main__':
    unittest.main()
