# SPDX-License-Identifier: GPL-3.0-or-later
#
# Morphing engine for HumanBody addon.
# Delegates pure-math computation to humanbody_core;
# handles Blender-specific mesh updates and material changes.

import sys

from .pfade import Projektpfade
import logging


# HumanBody core library lives at A:\3DTools\HumanBody.
# Die Wurzel kommt aus `pfade.py` — siehe dort, warum nicht per
# `dirname`-Kette.
HUMANBODY_ROOT = str(Projektpfade.humanbody())
if HUMANBODY_ROOT not in sys.path:
    sys.path.insert(0, HUMANBODY_ROOT)


# Die Bauteile liegen in `morph/`. Hier bleibt, was Blender
# sieht: die Klassen und die Anmeldung.
from .morph.morpher import Morpher

# Die Bauteile liegen in `morph/`. Hier bleibt, was Blender
# sieht: die Klassen und die Anmeldung.
# DIE OEFFENTLICHE SCHNITTSTELLE DES BEREICHS. Fuenf Module holen
# diese Namen aus `morphing` — `ui.py`, `operators.py`,
# `properties.py`, `haare/haarpfade.py`, `charakter/charakterdatei.py`.
# Sie sehen unbenutzt aus und sind die Weiterleitung.
from .morph.daten import (  # noqa: F401
    MorphData, CharacterDefaults, char_defaults, morph_data,
    _nail_color,
)


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# MorphData — extends core with addon-specific path methods
# Overwrites the name "MorphData" so existing code (operators.py, hair.py)
# that calls MorphData._addon_data_dir() keeps working.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Morpher — applies morphs to a Blender mesh
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Material helpers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register():
    char_defaults.load()
    morph_data.load()


def unregister():
    Morpher._morphers.clear()
