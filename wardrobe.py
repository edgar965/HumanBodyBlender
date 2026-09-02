# SPDX-License-Identifier: GPL-3.0-or-later
#
# Wardrobe system for HumanBody addon.
# Discovers, imports, and manages clothing/accessory assets.

import logging

from .klassenanmeldung import Klassenanmeldung
from .charakter.charakterpruefung import Charakterpruefung
import bpy

# Die Bauteile liegen in `garderobe/`. Hier bleibt, was Blender
# sieht: die Klassen und die Anmeldung.
from .garderobe.assetsuche import Assetsuche
from .garderobe.garderobenaktionen import Garderobenaktionen

from .pfade import Projektpfade

# DIE OEFFENTLICHE SCHNITTSTELLE DES BEREICHS: die Kategorienliste
# und der Datensatz. Beide sehen unbenutzt aus und sind es nicht —
# `ui_teile/zeichnen_garderobe.py` holt sie von hier.
# Die FUNKTIONEN standen bis zum 01.09.2026 ebenfalls in dieser
# Liste; sie liegen jetzt in `Assetsuche` und werden dort gerufen.
from .garderobe.assetsuche import (  # noqa: F401
    WARDROBE_CATEGORIES, AssetInfo,
)
from .garderobe.materialvorgaben import Materialvorgaben

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Asset paths
# ---------------------------------------------------------------------------

# Die Wurzeln kommen aus `pfade.py` — siehe dort.
_TOOLS_ROOT = str(Projektpfade.tools())
_HUMANBODY_ROOT = str(Projektpfade.humanbody())

# Fallback: HumanBodyAssets shared directory


# ---------------------------------------------------------------------------
# YAML loader (reuse from morphing)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Asset data class
# ---------------------------------------------------------------------------


# Asset cache


# Known category directory names


# ---------------------------------------------------------------------------
# Fitted asset tracking
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Import / Remove
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Material presets
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class MitAsset:
    u"""Ein Garderoben-Operator, der auf einem Charakter arbeitet.

    DREIMAL DIESELBE EINGANGSPRUEFUNG (01.09.2026) — und die dritte
    Fassung war eine andere: `wardrobe_preset` nahm `context.
    active_object` ungeprueft. Stand dort etwas anderes als ein
    Charakter, fand die Suche nach angepassten Teilen nichts und der
    Operator brach OHNE Meldung ab; der Nutzer sah einen Knopf, der
    nichts tut. Jetzt melden alle drei dasselbe.

    Ein Mixin OHNE `bpy.types.Operator` als Basis — so bleibt es von
    Blenders Anmeldung unberuehrt und taucht in `classes` nicht auf.
    `asset_name` bleibt bewusst in jeder Operatorklasse stehen:
    Eigenschaften sind Blenders Protokoll, wie `bl_idname`.
    """

    MELDUNG = "Select a HumanBody character first"

    def charakter(self, context):
        u"""Das aktive HumanBody-Netz — oder `None` samt Meldung."""
        return Charakterpruefung.charakter(context, self, MitAsset.MELDUNG)

    def angepasstes(self, charakter):
        u"""Das angepasste Teil dieses Namens — oder `None`.

        `wardrobe_remove` und `wardrobe_preset` suchten es je selbst,
        mit derselben Schleife.
        """
        for kind, name in Assetsuche.get_fitted_assets(charakter):
            if name == self.asset_name:
                return kind
        return None


class HUMANBODY_OT_wardrobe_add(MitAsset, bpy.types.Operator):
    bl_idname = "humanbody.wardrobe_add"
    bl_label = "Add Asset"
    bl_description = "Import and fit a wardrobe asset"
    bl_options = {'REGISTER', 'UNDO'}

    asset_name: bpy.props.StringProperty()

    def execute(self, context):
        char_obj = self.charakter(context)
        if not char_obj:
            return {'CANCELLED'}

        info = Assetsuche.find_asset_info(self.asset_name)
        if not info:
            self.report({'ERROR'}, f"Asset not found: {self.asset_name}")
            return {'CANCELLED'}

        # Check if already fitted
        for child, name in Assetsuche.get_fitted_assets(char_obj):
            if name == self.asset_name:
                self.report({'WARNING'}, f"Asset already fitted: {info.label}")
                return {'CANCELLED'}

        obj = Garderobenaktionen.import_asset(context, info, char_obj)
        if obj is None:
            self.report({'ERROR'}, f"Failed to import: {self.asset_name}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Added: {info.label}")
        return {'FINISHED'}


class HUMANBODY_OT_wardrobe_remove(MitAsset, bpy.types.Operator):
    bl_idname = "humanbody.wardrobe_remove"
    bl_label = "Remove Asset"
    bl_description = "Remove a fitted wardrobe asset"
    bl_options = {'REGISTER', 'UNDO'}

    asset_name: bpy.props.StringProperty()

    def execute(self, context):
        char_obj = self.charakter(context)
        if not char_obj:
            return {'CANCELLED'}

        teil = self.angepasstes(char_obj)
        if teil is None:
            self.report({'WARNING'},
                        f"Asset not found on character: {self.asset_name}")
            return {'CANCELLED'}
        Garderobenaktionen.remove_asset(teil)
        self.report({'INFO'}, f"Removed: {self.asset_name}")
        return {'FINISHED'}


class HUMANBODY_OT_wardrobe_preset(MitAsset, bpy.types.Operator):
    bl_idname = "humanbody.wardrobe_preset"
    bl_label = "Apply Preset"
    bl_description = "Apply a material color preset"

    asset_name: bpy.props.StringProperty()
    preset_key: bpy.props.StringProperty()

    def execute(self, context):
        char_obj = self.charakter(context)
        if not char_obj:
            return {'CANCELLED'}

        info = Assetsuche.find_asset_info(self.asset_name)
        if not info:
            return {'CANCELLED'}

        teil = self.angepasstes(char_obj)
        if teil is None:
            return {'CANCELLED'}
        Materialvorgaben.apply_material_preset(teil, info, self.preset_key)
        self.report({'INFO'}, f"Preset: {self.preset_key}")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = (
    HUMANBODY_OT_wardrobe_add,
    HUMANBODY_OT_wardrobe_remove,
    HUMANBODY_OT_wardrobe_preset,
)




# Blenders Addon-Protokoll ruft diese beiden AM MODUL — `__init__.py`
# reicht sie an alle zehn Teilmodule weiter. In der Klasse darueber
# ruft sie niemand mehr.
def register():
    Klassenanmeldung.an(classes)


def unregister():
    Klassenanmeldung.ab(classes)
