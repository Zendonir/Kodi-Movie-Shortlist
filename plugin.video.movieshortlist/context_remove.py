# -*- coding: utf-8 -*-
"""Context menu item "Remove from movie shortlist" (kodi.context.item)."""

import sys

from resources.lib import context

if __name__ == '__main__':
    context.run('remove', getattr(sys, 'listitem', None))
