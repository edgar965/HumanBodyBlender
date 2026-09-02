# -*- coding: utf-8 -*-
import os
import logging
logger = logging.getLogger(__name__)

from ..pfade import Projektpfade

# Die Bauteile liegen in `garderobe/`. Hier bleibt, was Blender
# sieht: die Klassen und die Anmeldung.
from .assetinfo import AssetInfo

#: Zuerst die Kerndaten, dann die geteilte Sammlung.
_ASSETS_DIR = str(Projektpfade.assets())

_HUMANBODY_ASSETS_DIR = os.path.join(
    r"A:\3DTools\HumanBodyAssets", "characters", "mb_female", "assets")
_CATEGORY_DIRS = {"Tops", "Bottoms", "Skirts", "Full", "Underwear", "Shoes",
                  "Accessories", "Other"}

# Wardrobe categories for the panel display
WARDROBE_CATEGORIES = [
    ("Tops",        'TRIA_UP'),
    ("Bottoms",     'TRIA_DOWN'),
    ("Skirts",      'MESH_CONE'),
    ("Full",        'USER'),
    ("Underwear",   'MOD_CLOTH'),
    ("Shoes",       'CONSTRAINT_BONE'),
    ("Accessories", 'PROP_CON'),
]


class Assetsuche:
    u"""Die frueheren Modulfunktionen, gebuendelt."""

    #: Der Katalog aller gefundenen Kleidungsstuecke; None = noch nicht gelesen.
    zwischenspeicher = None

    @staticmethod
    def _get_assets_dir():
        """Return the assets directory path."""
        if os.path.isdir(_ASSETS_DIR):
            return _ASSETS_DIR
        if os.path.isdir(_HUMANBODY_ASSETS_DIR):
            return _HUMANBODY_ASSETS_DIR
        return None

    @staticmethod
    def _scan_dir_for_assets(directory, category_override=None):
        """Scan a single directory for assets, return list of AssetInfo."""
        result = []
        for entry in sorted(os.listdir(directory)):
            full = os.path.join(directory, entry)

            if os.path.isdir(full):
                info = AssetInfo(entry, full)
                if info.blend_file:
                    if category_override:
                        info.category = category_override
                    result.append(info)
            elif entry.endswith(".blend") and not entry.startswith("."):
                name = entry[:-6]
                info = AssetInfo(name, directory)
                info.blend_file = full
                if category_override:
                    info.category = category_override
                result.append(info)
        return result

    @staticmethod
    def discover_assets():
        """Scan the assets directory and return list of AssetInfo.

        Supports both flat layout and category-subdirectory layout:
          assets/Tops/jeans.blend   -> category = Tops
          assets/my_asset.blend     -> category guessed from name
        """
        if Assetsuche.zwischenspeicher is not None:
            return Assetsuche.zwischenspeicher

        assets_dir = Assetsuche._get_assets_dir()
        if not assets_dir:
            Assetsuche.zwischenspeicher = []
            return Assetsuche.zwischenspeicher

        result = []
        for entry in sorted(os.listdir(assets_dir)):
            full = os.path.join(assets_dir, entry)

            if os.path.isdir(full) and entry in _CATEGORY_DIRS:
                # Category subdirectory — scan contents with category override
                result.extend(Assetsuche._scan_dir_for_assets(full, category_override=entry))
            elif os.path.isdir(full):
                # Folder-based asset at root level (legacy/flat layout)
                info = AssetInfo(entry, full)
                if info.blend_file:
                    result.append(info)
            elif entry.endswith(".blend") and not entry.startswith("."):
                # Standalone .blend file at root level
                name = entry[:-6]
                info = AssetInfo(name, assets_dir)
                info.blend_file = full
                result.append(info)

        Assetsuche.zwischenspeicher = result
        logger.info("Discovered %d wardrobe assets", len(result))
        return result

    @staticmethod
    def invalidate_cache():
        Assetsuche.zwischenspeicher = None

    @staticmethod
    def get_filtered_assets(category="ALL", search=""):
        """Return assets filtered by category and search string."""
        assets = Assetsuche.discover_assets()
        result = []
        search_lower = search.lower()
        for a in assets:
            if category != "ALL" and a.category != category:
                continue
            if search_lower:
                if search_lower not in a.name.lower() and \
                   not any(search_lower in t.lower() for t in a.tags):
                    continue
            result.append(a)
        return result

    @staticmethod
    def get_fitted_assets(char_obj):
        """Return list of (object, asset_name) for fitted assets on a character."""
        result = []
        for child in char_obj.children:
            if child.type == 'MESH' and child.data.get("hb_wardrobe_asset"):
                result.append((child, child.data["hb_wardrobe_asset"]))
        return result

    @staticmethod
    def find_asset_info(name):
        """Find AssetInfo by name."""
        for a in Assetsuche.discover_assets():
            if a.name == name:
                return a
        return None
