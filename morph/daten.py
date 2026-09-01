# -*- coding: utf-8 -*-
import os
import logging
from humanbody_core.morphing import (
    MorphData as _CoreMorphData, CharacterDefaults as _CoreCharacterDefaults,
)
from ..pfade import Projektpfade

#: Der Kern liegt in einem anderen Repo; sein Pfad steht in
#: `pfade.py`. Nicht aus `morphing.py` holen — das importiert
#: dieses Modul und der Ring waere zurueck.
HUMANBODY_ROOT = str(Projektpfade.humanbody())
logger = logging.getLogger(__name__)


class MorphData(_CoreMorphData):
    """MorphData with path helpers pointing to HumanBody data."""

    def __init__(self):
        data_dir = os.path.join(HUMANBODY_ROOT, "data", "humanBody")
        super().__init__(data_dir=data_dir)

    @staticmethod
    def _addon_dir():
        """Return addon root directory."""
        return os.path.dirname(__file__)

    @staticmethod
    def _addon_data_dir():
        """Return HumanBody/data/humanBody."""
        return os.path.join(HUMANBODY_ROOT, "data", "humanBody")

    @staticmethod
    def _morphs_dir():
        return os.path.join(HUMANBODY_ROOT, "data", "humanBody", "morphs")


class CharacterDefaults(_CoreCharacterDefaults):
    """CharacterDefaults loading from HumanBody's settings.yaml."""

    def load(self, settings_path=None):
        if settings_path is None:
            settings_path = os.path.join(HUMANBODY_ROOT, "settings.yaml")
        super().load(settings_path)


# Singletons
char_defaults = CharacterDefaults()


morph_data = MorphData()


def _nail_color(skin_rgb):
    """Slightly lighter/pinker version of skin color for nails."""
    r, g, b = skin_rgb
    return (min(1.0, r * 1.15 + 0.05),
            min(1.0, g * 0.95 + 0.04),
            min(1.0, b * 0.9 + 0.03))
