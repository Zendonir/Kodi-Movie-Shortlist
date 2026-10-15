# -*- coding: utf-8 -*-
"""Context menu item "Add to movie shortlist" (kodi.context.item)."""

import sys

from resources.lib import context

if __name__ == '__main__':
    context.run('add', getattr(sys, 'listitem', None))
