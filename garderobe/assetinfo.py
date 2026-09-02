# -*- coding: utf-8 -*-
import os
import logging
from .yamlleser import Yamlleser
logger = logging.getLogger(__name__)


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
        conf = Yamlleser._load_yaml(conf_path)
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
            self.category = AssetInfo._guess_category(name)

    @staticmethod
    def _guess_category(name):
        """Guess asset category from name when config says 'Other'."""
        lower = name.lower()
        for key, cat in _NAME_CAT_MAP.items():
            if key in lower:
                return cat
        return "Other"
