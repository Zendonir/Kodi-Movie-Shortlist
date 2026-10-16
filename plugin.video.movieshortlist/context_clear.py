# -*- coding: utf-8 -*-
"""Context menu item "Clear movie shortlist" (kodi.context.item)."""

import sys

from resources.lib import context

if __name__ == '__main__':
    context.run('clear', getattr(sys, 'listitem', None))
