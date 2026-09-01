# SPDX-License-Identifier: GPL-3.0-or-later
#
# Rig and pose system for HumanBody addon.
# Pre-generated AutoRig loading, pose loading.

import os
import logging

import bpy

# Die Bauteile liegen in `rig_teile/`. Hier bleibt, was Blender
# sieht: die Klassen und die Anmeldung.
from .rig_teile.gesichtsknochen import (
    _enable_face_deform_bones, _setup_rigify_properties,
)
from .rig_teile.gewichte import _import_weights
from .rig_teile.posenoperatoren import (
    HUMANBODY_OT_clear_pose, HUMANBODY_OT_load_pose,
)
from .rig_teile.rigpfade import _get_autorig_blend_path, _get_weights_npz_path

# Die Bauteile liegen in `rig_teile/`. Hier bleibt, was Blender
# sieht: die Klassen und die Anmeldung.
# DIE OEFFENTLICHE SCHNITTSTELLE: `animation.py`, `anim/bvhladen.py`,
# `ui_teile/zeichnen_weitere.py` und `haare/frisurladen.py` holen
# diese beiden aus `rig`. Sie sind die Weiterleitung.
from .rig_teile.rigsuche import _find_rig, _list_poses  # noqa: F401


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# NPZ utilities
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Rig setup helpers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Shared helper: find rig for a HumanBody object
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Pose system
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class HUMANBODY_OT_add_rig(bpy.types.Operator):
    bl_idname = "humanbody.add_rig"
    bl_label = "Add Rig"
    bl_description = "Add Rigify armature rig to the character"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH' or not obj.data.get("humanbody"):
            self.report({'ERROR'}, "Select a HumanBody character first")
            return {'CANCELLED'}

        if _find_rig(obj):
            self.report({'WARNING'}, "Rig already exists. Remove first.")
            return {'CANCELLED'}

        autorig_blend = _get_autorig_blend_path()
        if not os.path.isfile(autorig_blend):
            self.report({'ERROR'}, f"AutoRig file not found: {autorig_blend}")
            return {'CANCELLED'}

        # Import pre-generated AutoRig
        existing = set(bpy.data.objects.keys())
        with bpy.data.libraries.load(autorig_blend, link=False) as (data_from, data_to):
            data_to.objects = ["HumanBody_Rig"]

        # Find the newly imported rig (handles name conflicts)
        rig = None
        for o in bpy.data.objects:
            if o.name not in existing and o.type == 'ARMATURE':
                rig = o
                break
        if not rig:
            rig = bpy.data.objects.get("HumanBody_Rig")
        if not rig:
            self.report({'ERROR'}, "HumanBody_Rig not found in autorig.blend")
            return {'CANCELLED'}

        context.collection.objects.link(rig)
        rig.name = "HumanBody_Rig"
        rig["humanbody_rig"] = True

        # Import bone weights from NPZ
        weights_npz = _get_weights_npz_path()
        if os.path.isfile(weights_npz):
            n = _import_weights(obj, weights_npz)
            logger.info("Imported %d bone weight groups from NPZ", n)

        # Enable deformation on MCH/ORG bones that carry NPZ weights
        _enable_face_deform_bones(rig)

        # Switch limbs to FK mode (default is IK)
        for pname in ("upper_arm_parent.L", "upper_arm_parent.R",
                       "thigh_parent.L", "thigh_parent.R"):
            pb = rig.pose.bones.get(pname)
            if pb and "IK_FK" in pb:
                pb["IK_FK"] = 1.0

        # Set Rigify properties for correct FK pose behaviour
        _setup_rigify_properties(rig)

        # Parent mesh to rig + add ARMATURE modifier
        obj.parent = rig
        obj.matrix_parent_inverse = rig.matrix_world.inverted()

        mod = obj.modifiers.new("HumanBody_Rig", "ARMATURE")
        mod.use_vertex_groups = True
        mod.use_deform_preserve_volume = True
        mod.object = rig

        # Place ARMATURE modifier first (before subdivision etc.)
        with context.temp_override(object=obj):
            while obj.modifiers.find(mod.name) > 0:
                bpy.ops.object.modifier_move_up(modifier=mod.name)

        # Restore selection
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        context.view_layer.objects.active = obj

        def_bones = sum(1 for b in rig.data.bones if b.name.startswith("DEF-"))
        self.report({'INFO'},
                    f"Rig added ({len(rig.data.bones)} bones, "
                    f"{def_bones} deformation)")
        return {'FINISHED'}


class HUMANBODY_OT_remove_rig(bpy.types.Operator):
    bl_idname = "humanbody.remove_rig"
    bl_label = "Remove Rig"
    bl_description = "Remove armature rig from the character"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        # obj.type PRUEFEN, bevor obj.data angefasst wird: Bei einem Empty ist
        # obj.data None, und .get() darauf beendet den Operator mit einem
        # Traceback statt mit der Meldung darunter. HUMANBODY_OT_add_rig macht
        # es seit jeher richtig, diese drei nicht (Review 13.08.2026).
        if not obj or obj.type != 'MESH' or not obj.data.get("humanbody"):
            self.report({'ERROR'}, "Select a HumanBody character first")
            return {'CANCELLED'}

        rig = _find_rig(obj)

        # Remove armature modifiers
        for mod in list(obj.modifiers):
            if mod.type == 'ARMATURE':
                obj.modifiers.remove(mod)

        # Remove DEF- vertex groups (Rigify weight groups)
        for vg in list(obj.vertex_groups):
            if vg.name.startswith("DEF-"):
                obj.vertex_groups.remove(vg)

        # Unparent
        if obj.parent and obj.parent.type == 'ARMATURE':
            obj.parent = None
            obj.matrix_world = obj.matrix_world  # keep position

        # Delete rig
        removed = []
        if rig:
            removed.append(rig.name)
            bpy.data.objects.remove(rig, do_unlink=True)

        if removed:
            self.report({'INFO'}, f"Rig removed ({', '.join(removed)})")
        else:
            self.report({'WARNING'}, "No rig found")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = (
    HUMANBODY_OT_add_rig,
    HUMANBODY_OT_remove_rig,
    HUMANBODY_OT_load_pose,
    HUMANBODY_OT_clear_pose,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
