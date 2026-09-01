# SPDX-License-Identifier: GPL-3.0-or-later
#
# Operators for the HumanBody addon.
# HumanBodyIO consolidates all character I/O and morph operations.
# Thin Blender operator wrappers delegate to HumanBodyIO methods.

import logging

import bpy

# Die Bauteile liegen in `charakter/`. Hier bleibt, was Blender
# sieht: die Klassen und die Anmeldung.
from .charakter.charakterdatei import HumanBodyIO
from .charakter.materialien import _sync_hb_material_colors


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Material helpers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# HumanBodyIO — consolidated business logic
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Operator wrappers (thin delegates to HumanBodyIO)
# ---------------------------------------------------------------------------

class HUMANBODY_OT_import_character(bpy.types.Operator):
    bl_idname = "humanbody.import_character"
    bl_label = "Import Character"
    bl_description = "Import the HumanBody base mesh"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj, err = HumanBodyIO.import_character(context)
        if err:
            self.report({'ERROR'}, err)
            return {'CANCELLED'}
        self.report({'INFO'}, f"Imported HumanBody character: {obj.name}")
        return {'FINISHED'}


class HUMANBODY_OT_update_morphs(bpy.types.Operator):
    bl_idname = "humanbody.update_morphs"
    bl_label = "Update"
    bl_description = "Force-update the mesh from current morph values"

    def execute(self, context):
        if not HumanBodyIO.update_morphs(context):
            return {'CANCELLED'}
        return {'FINISHED'}


class HUMANBODY_OT_reset_morphs(bpy.types.Operator):
    bl_idname = "humanbody.reset_morphs"
    bl_label = "Reset"
    bl_description = "Reset all morph sliders to zero"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if not HumanBodyIO.reset_morphs(context):
            return {'CANCELLED'}
        return {'FINISHED'}


class HUMANBODY_OT_randomize(bpy.types.Operator):
    bl_idname = "humanbody.randomize"
    bl_label = "Randomize"
    bl_description = "Randomize morph values with gaussian distribution"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        count, err = HumanBodyIO.randomize(context)
        if err:
            self.report({'WARNING'}, err)
            return {'CANCELLED'}
        strength = context.scene.humanbody.randomize_strength
        self.report({'INFO'},
                    f"Randomized {count} morphs (strength={strength:.0%})")
        return {'FINISHED'}


class HUMANBODY_OT_finalize(bpy.types.Operator):
    bl_idname = "humanbody.finalize"
    bl_label = "Apply Morphs"
    bl_description = "Bake current morph state into the mesh and reset all sliders"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ok, msg = HumanBodyIO.finalize(context)
        if not ok:
            self.report({'WARNING'}, msg)
            return {'CANCELLED'}
        self.report({'INFO'}, "Morphs baked into mesh. Sliders reset.")
        return {'FINISHED'}


class HUMANBODY_OT_export_character(bpy.types.Operator):
    bl_idname = "humanbody.export_character"
    bl_label = "Export"
    bl_description = "Export character settings to JSON file"

    filepath: bpy.props.StringProperty(
        subtype='FILE_PATH', default="character.json")
    filter_glob: bpy.props.StringProperty(
        default="*.json", options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        ok, path = HumanBodyIO.export_character(context, self.filepath)
        if not ok:
            self.report({'WARNING'}, path)
            return {'CANCELLED'}
        self.report({'INFO'}, f"Character exported to {path}")
        return {'FINISHED'}


class HUMANBODY_OT_import_settings(bpy.types.Operator):
    bl_idname = "humanbody.import_settings"
    bl_label = "Import"
    bl_description = "Import character settings from JSON file"

    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    filter_glob: bpy.props.StringProperty(
        default="*.json", options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        ok, msg = HumanBodyIO.import_settings(context, self.filepath)
        if not ok:
            self.report({'WARNING' if 'Select' in msg else 'ERROR'}, msg)
            return {'CANCELLED'}
        self.report({'INFO'}, f"Character imported from {msg}")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Depsgraph handler
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = (
    HUMANBODY_OT_import_character,
    HUMANBODY_OT_update_morphs,
    HUMANBODY_OT_reset_morphs,
    HUMANBODY_OT_randomize,
    HUMANBODY_OT_finalize,
    HUMANBODY_OT_export_character,
    HUMANBODY_OT_import_settings,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.app.handlers.depsgraph_update_post.append(_sync_hb_material_colors)


def unregister():
    if _sync_hb_material_colors in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_sync_hb_material_colors)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
