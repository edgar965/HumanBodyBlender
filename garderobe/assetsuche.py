# -*- coding: utf-8 -*-
import os
import logging
logger = logging.getLogger(__name__)
from .yamlleser import _load_yaml

from ..pfade import Projektpfade

#: Zuerst die Kerndaten, dann die geteilte Sammlung.
_ASSETS_DIR = str(Projektpfade.assets())

_HUMANBODY_ASSETS_DIR = os.path.join(
    r"A:\3DTools\HumanBodyAssets", "characters", "mb_female", "assets")
_asset_cache = None
_CATEGORY_DIRS = {"Tops", "Bottoms", "Skirts", "Full", "Underwear", "Shoes",
                  "Accessories", "Other"}



def _get_assets_dir():
    """Return the assets directory path."""
    if os.path.isdir(_ASSETS_DIR):
        return _ASSETS_DIR
    if os.path.isdir(_HUMANBODY_ASSETS_DIR):
        return _HUMANBODY_ASSETS_DIR
    return None


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


# Auto-categorization by name keywords
_NAME_CAT_MAP = {
    "pants": "Bottoms", "trousers": "Bottoms", "jeans": "Bottoms",
    "btm": "Bottoms", "tights": "Bottoms",
    "skirt": "Skirts", "rock": "Skirts", "minirock": "Skirts",
    "top": "Tops", "shirt": "Tops", "jumper": "Tops", "jacket": "Tops",
    "boots": "Shoes", "shoes": "Shoes",
    "gloves": "Accessories", "hat": "Accessories", "headpiece": "Accessories",
    "dress": "Full", "suit_full": "Full", "dresses": "Full",
    "hair": "Hair",
    "thong": "Underwear", "panties": "Underwear", "bra": "Underwear",
}


def _guess_category(name):
    """Guess asset category from name when config says 'Other'."""
    lower = name.lower()
    for key, cat in _NAME_CAT_MAP.items():
        if key in lower:
            return cat
    return "Other"


class AssetInfo:
    """Metadata for a discovered asset."""
    __slots__ = ("name", "directory", "blend_file", "config",
                 "category", "tags", "label")

    def __init__(self, name, directory):
        self.name = name
        self.directory = directory
        self.blend_file = ""
        self.config = {}
        self.category = "Other"
        self.tags = []
        self.label = name.replace("_", " ").replace(".", " ")

        # Find blend file
        blend = os.path.join(directory, "asset.blend")
        if os.path.isfile(blend):
            self.blend_file = blend
        else:
            # Try name.blend
            blend = os.path.join(directory, name + ".blend")
            if os.path.isfile(blend):
                self.blend_file = blend

        # Load config
        conf_path = os.path.join(directory, "config.yaml")
        conf = _load_yaml(conf_path)
        if conf:
            self.config = conf
            self.category = conf.get("category", "Other")
            if isinstance(self.category, str):
                self.category = self.category.strip('"')
            self.tags = conf.get("tags", [])

        # Normalize category names
        _CAT_NORMALIZE = {"Dresses": "Full"}
        self.category = _CAT_NORMALIZE.get(self.category, self.category)

        # Auto-categorize when config is missing or says "Other"
        if self.category == "Other":
            self.category = _guess_category(name)


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


def discover_assets():
    """Scan the assets directory and return list of AssetInfo.

    Supports both flat layout and category-subdirectory layout:
      assets/Tops/jeans.blend   -> category = Tops
      assets/my_asset.blend     -> category guessed from name
    """
    global _asset_cache
    if _asset_cache is not None:
        return _asset_cache

    assets_dir = _get_assets_dir()
    if not assets_dir:
        _asset_cache = []
        return _asset_cache

    result = []
    for entry in sorted(os.listdir(assets_dir)):
        full = os.path.join(assets_dir, entry)

        if os.path.isdir(full) and entry in _CATEGORY_DIRS:
            # Category subdirectory — scan contents with category override
            result.extend(_scan_dir_for_assets(full, category_override=entry))
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

    _asset_cache = result
    logger.info("Discovered %d wardrobe assets", len(result))
    return result


def invalidate_cache():
    global _asset_cache
    _asset_cache = None


def get_filtered_assets(category="ALL", search=""):
    """Return assets filtered by category and search string."""
    assets = discover_assets()
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


def get_fitted_assets(char_obj):
    """Return list of (object, asset_name) for fitted assets on a character."""
    result = []
    for child in char_obj.children:
        if child.type == 'MESH' and child.data.get("hb_wardrobe_asset"):
            result.append((child, child.data["hb_wardrobe_asset"]))
    return result


def find_asset_info(name):
    """Find AssetInfo by name."""
    for a in discover_assets():
        if a.name == name:
            return a
    return None
