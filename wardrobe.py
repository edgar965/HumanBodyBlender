# SPDX-License-Identifier: GPL-3.0-or-later
#
# Wardrobe system for HumanBody addon.
# Discovers, imports, and manages clothing/accessory assets.

import logging

import bpy

# Die Bauteile liegen in `garderobe/`. Hier bleibt, was Blender
# sieht: die Klassen und die Anmeldung.
from .garderobe.assetsuche import find_asset_info, get_fitted_assets
from .garderobe.materialvorgaben import apply_material_preset

from .pfade import Projektpfade

# DIE OEFFENTLICHE SCHNITTSTELLE DES BEREICHS. Diese Namen sehen
# unbenutzt aus und sind es nicht: `ui_teile/zeichnen_garderobe.py`
# und `assetCreator/operators.py` rufen sie als `wardrobe.x()`.
# Wer sie hier herausnimmt, bricht beide — ohne dass etwas
# uebersetzungsfehlerhaft wuerde.
from .garderobe.assetsuche import (  # noqa: F401
    WARDROBE_CATEGORIES, AssetInfo, discover_assets,
    invalidate_cache, get_filtered_assets, get_fitted_assets,
    find_asset_info,
)
from .garderobe.materialvorgaben import (  # noqa: F401
    get_material_presets, apply_material_preset,
)

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

def import_asset(context, asset_info, char_obj):
    """Import an asset and attach it to the character."""
    if not asset_info.blend_file:
        return None

    # Import all objects from the blend file
    with bpy.data.libraries.load(asset_info.blend_file, link=False) as (data_from, data_to):
        data_to.objects = data_from.objects[:]

    imported = []
    for obj in data_to.objects:
        if obj is not None:
            context.collection.objects.link(obj)
            imported.append(obj)

    if not imported:
        return None

    # Find the main mesh object
    asset_obj = None
    for obj in imported:
        if obj.type == 'MESH':
            asset_obj = obj
            break
    if asset_obj is None:
        asset_obj = imported[0]

    # Tag as wardrobe asset
    asset_obj.data["hb_wardrobe_asset"] = asset_info.name

    # Parent to character
    asset_obj.parent = char_obj
    asset_obj.matrix_parent_inverse = char_obj.matrix_world.inverted()

    # Add offset modifier (Displace along normals)
    offset_conf = {}
    params = asset_info.config.get("parameters", {})
    if isinstance(params, dict):
        offset_conf = params.get("offset", {})

    mod = asset_obj.modifiers.new(name="hb_offset", type='DISPLACE')
    mod.direction = 'NORMAL'
    mod.mid_level = 0.0
    mod.strength = offset_conf.get("default", 0.001) if isinstance(offset_conf, dict) else 0.001

    # Add corrective smooth
    smooth_conf = {}
    if isinstance(params, dict):
        smooth_conf = params.get("smoothing", {})

    mod_s = asset_obj.modifiers.new(name="hb_smooth", type='CORRECTIVE_SMOOTH')
    mod_s.use_pin_boundary = True
    default_smooth = smooth_conf.get("default", 0.0) if isinstance(smooth_conf, dict) else 0.0
    mod_s.iterations = int(default_smooth * 10)

    # Smooth shading
    for poly in asset_obj.data.polygons:
        poly.use_smooth = True

    # Remove any extra imported objects that aren't the main mesh
    for obj in imported:
        if obj != asset_obj and obj.type != 'ARMATURE':
            bpy.data.objects.remove(obj, do_unlink=True)

    logger.info("Imported wardrobe asset: %s", asset_info.name)
    return asset_obj


def remove_asset(asset_obj):
    """Remove a fitted asset from the scene."""
    name = asset_obj.data.get("hb_wardrobe_asset", asset_obj.name)
    bpy.data.objects.remove(asset_obj, do_unlink=True)
    logger.info("Removed wardrobe asset: %s", name)


# ---------------------------------------------------------------------------
# Material presets
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class HUMANBODY_OT_wardrobe_add(bpy.types.Operator):
    bl_idname = "humanbody.wardrobe_add"
    bl_label = "Add Asset"
    bl_description = "Import and fit a wardrobe asset"
    bl_options = {'REGISTER', 'UNDO'}

    asset_name: bpy.props.StringProperty()

    def execute(self, context):
        char_obj = context.active_object
        if not char_obj or not char_obj.data.get("humanbody"):
            self.report({'ERROR'}, "Select a HumanBody character first")
            return {'CANCELLED'}

        info = find_asset_info(self.asset_name)
        if not info:
            self.report({'ERROR'}, f"Asset not found: {self.asset_name}")
            return {'CANCELLED'}

        # Check if already fitted
        for child, name in get_fitted_assets(char_obj):
            if name == self.asset_name:
                self.report({'WARNING'}, f"Asset already fitted: {info.label}")
                return {'CANCELLED'}

        obj = import_asset(context, info, char_obj)
        if obj is None:
            self.report({'ERROR'}, f"Failed to import: {self.asset_name}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Added: {info.label}")
        return {'FINISHED'}


class HUMANBODY_OT_wardrobe_remove(bpy.types.Operator):
    bl_idname = "humanbody.wardrobe_remove"
    bl_label = "Remove Asset"
    bl_description = "Remove a fitted wardrobe asset"
    bl_options = {'REGISTER', 'UNDO'}

    asset_name: bpy.props.StringProperty()

    def execute(self, context):
        char_obj = context.active_object
        if not char_obj or not char_obj.data.get("humanbody"):
            self.report({'ERROR'}, "Select a HumanBody character first")
            return {'CANCELLED'}

        for child, name in get_fitted_assets(char_obj):
            if name == self.asset_name:
                remove_asset(child)
                self.report({'INFO'}, f"Removed: {self.asset_name}")
                return {'FINISHED'}

        self.report({'WARNING'}, f"Asset not found on character: {self.asset_name}")
        return {'CANCELLED'}


class HUMANBODY_OT_wardrobe_preset(bpy.types.Operator):
    bl_idname = "humanbody.wardrobe_preset"
    bl_label = "Apply Preset"
    bl_description = "Apply a material color preset"

    asset_name: bpy.props.StringProperty()
    preset_key: bpy.props.StringProperty()

    def execute(self, context):
        char_obj = context.active_object
        if not char_obj:
            return {'CANCELLED'}

        info = find_asset_info(self.asset_name)
        if not info:
            return {'CANCELLED'}

        for child, name in get_fitted_assets(char_obj):
            if name == self.asset_name:
                apply_material_preset(child, info, self.preset_key)
                self.report({'INFO'}, f"Preset: {self.preset_key}")
                return {'FINISHED'}

        return {'CANCELLED'}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = (
    HUMANBODY_OT_wardrobe_add,
    HUMANBODY_OT_wardrobe_remove,
    HUMANBODY_OT_wardrobe_preset,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
