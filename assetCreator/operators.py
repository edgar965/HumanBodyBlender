# SPDX-License-Identifier: GPL-3.0-or-later
#
# Operators and save logic for the Asset Creator.

import os
import logging

import bpy

from ..assetCreator.vorschau.vorschausuche import Vorschausuche
from .preview import Vorschau
from .vorschau.bildvorschau import Bildvorschau

# Die Bauteile liegen in `assetCreator/`. Hier bleibt, was Blender
# sieht: die Klassen und die Anmeldung.
from .assetspeicher import Assetspeicher
from ..koerperoperator import MitKoerper

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Save asset
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class HUMANBODY_OT_create_asset_preview(MitKoerper, bpy.types.Operator):
    """Create or update an asset preview from body faces"""
    bl_idname = "humanbody.create_asset_preview"
    bl_label = "Update Preview"
    bl_description = "Create/update asset preview from body shell"
    bl_options = {'REGISTER', 'UNDO'}

    # Operator properties for scripted calls (optional overrides)
    name: bpy.props.StringProperty(default="")
    category: bpy.props.StringProperty(default="")
    z_min: bpy.props.FloatProperty(default=-999)
    z_max: bpy.props.FloatProperty(default=-999)
    offset: bpy.props.FloatProperty(default=-999)
    thickness: bpy.props.FloatProperty(default=-999)
    color: bpy.props.FloatVectorProperty(size=3, default=(-1, -1, -1))
    roughness: bpy.props.FloatProperty(default=-999)
    metallic: bpy.props.FloatProperty(default=-999)
    include_arms: bpy.props.BoolProperty(default=False)
    include_arms_set: bpy.props.BoolProperty(default=False)
    grow: bpy.props.IntProperty(default=-1)

    def execute(self, context):
        ac = context.scene.humanbody_asset_creator

        # Apply operator overrides (for scripted calls only)
        if self.name:
            ac.name_ = self.name
        if self.category:
            ac.category = self.category
        if self.z_min > -900:
            ac.z_min = self.z_min
        if self.z_max > -900:
            ac.z_max = self.z_max
        if self.offset > -900:
            ac.offset = self.offset
        if self.thickness > -900:
            ac.thickness = self.thickness
        if self.color[0] >= 0:
            ac.color = self.color
        if self.roughness > -900:
            ac.roughness = self.roughness
        if self.metallic > -900:
            ac.metallic = self.metallic
        if self.grow >= 0:
            ac.grow = self.grow
        if self.include_arms_set:
            ac.include_arms = self.include_arms

        # Mode dispatch
        if ac.creation_mode == "IMAGE":
            path = bpy.path.abspath(ac.image_path)
            if not path or not os.path.isfile(path):
                self.report({'ERROR'}, "No valid image file selected")
                return {'CANCELLED'}
            obj = Bildvorschau.create_preview_from_image(context, ac, path)
            if obj is None:
                self.report({'WARNING'},
                            "No garment faces detected — adjust threshold")
                return {'CANCELLED'}
        else:
            obj = Vorschau.create_preview(context, ac)
            if obj is None:
                self.report({'WARNING'},
                            "No faces in Z range — adjust sliders")
                return {'CANCELLED'}

        self.report({'INFO'},
                    f"Preview: {ac.name_} ({len(obj.data.polygons)} faces)")
        return {'FINISHED'}


class HUMANBODY_OT_save_asset(bpy.types.Operator):
    """Save the preview mesh as a permanent wardrobe asset"""
    bl_idname = "humanbody.save_asset"
    bl_label = "Save Asset"
    bl_description = "Save preview as wardrobe asset (.blend + config.yaml)"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return Vorschausuche.find_preview(context) is not None

    def execute(self, context):
        ac = context.scene.humanbody_asset_creator
        ok, msg = Assetspeicher.save_asset(context, ac)
        if ok:
            self.report({'INFO'}, f"Saved: {ac.name_} -> {msg}")
        else:
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}
        return {'FINISHED'}


class HUMANBODY_OT_remove_asset_preview(bpy.types.Operator):
    """Remove the asset preview mesh"""
    bl_idname = "humanbody.remove_asset_preview"
    bl_label = "Delete Preview"
    bl_description = "Remove the preview mesh from the scene"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return Vorschausuche.find_preview(context) is not None

    def execute(self, context):
        Vorschausuche.remove_preview(context)
        self.report({'INFO'}, "Preview removed")
        return {'FINISHED'}
