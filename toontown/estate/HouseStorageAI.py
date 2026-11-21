"""
Saves each toon's house (furniture layout, attic, wallpaper, windows,
recently thrown-away items) as a small file on the server, under
<server-data-folder>/houses/<toonId>.json, and loads it on the next visit.
"""
import json
import os

from direct.directnotify import DirectNotifyGlobal

from toontown.catalog import CatalogItem
from toontown.catalog.CatalogItemList import CatalogItemList

notify = DirectNotifyGlobal.directNotify.newCategory('HouseStorageAI')

# What is kept for each list, and how much detail to store with it.
STORES = {
    'interiorItems': CatalogItem.Customization | CatalogItem.Location,
    'atticItems': CatalogItem.Customization,
    'atticWallpaper': CatalogItem.Customization,
    'atticWindows': CatalogItem.Customization,
    'deletedItems': CatalogItem.Customization,
    'wallpaper': CatalogItem.Customization,
    'windows': CatalogItem.Customization | CatalogItem.WindowPlacement,
}

MAX_DELETED_ITEMS = 10


def _folder(air):
    base = getattr(air, 'dataFolder', '') or ''
    return os.path.join(base, 'houses')


def _path(air, ownerId):
    return os.path.join(_folder(air), '%d.json' % ownerId)


def load(air, ownerId):
    """Returns a dict of CatalogItemLists, or None if this toon has no saved house yet."""
    if not ownerId:
        return None
    path = _path(air, ownerId)
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r') as f:
            raw = json.load(f)
        data = {}
        for key, store in STORES.items():
            blob = bytes.fromhex(raw.get(key, ''))
            data[key] = CatalogItemList(blob, store=store)
        return data
    except Exception as e:
        notify.warning('Could not read saved house for %s (%s); using a fresh house.' % (ownerId, e))
        return None


def _normalizeAngles(items):
    # Angles are stored in one byte each, so keep them between -180 and 180.
    for item in items:
        posHpr = getattr(item, 'posHpr', None)
        if posHpr:
            x, y, z, h, p, r = posHpr
            item.posHpr = (x, y, z, ((h + 180) % 360) - 180, ((p + 180) % 360) - 180, ((r + 180) % 360) - 180)


def save(air, ownerId, data):
    if not ownerId:
        return
    try:
        os.makedirs(_folder(air), exist_ok=True)
        raw = {}
        for key, store in STORES.items():
            items = data.get(key) or CatalogItemList()
            if store & CatalogItem.Location:
                _normalizeAngles(items)
            raw[key] = items.getBlob(store=store).hex()
        path = _path(air, ownerId)
        tmp = path + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(raw, f)
        os.replace(tmp, path)
    except Exception as e:
        notify.warning('Could not save house for %s: %s' % (ownerId, e))
