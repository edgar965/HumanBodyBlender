# SPDX-License-Identifier: GPL-3.0-or-later
#
# Rig and pose system for HumanBody addon.
# Pre-generated AutoRig loading, pose loading.

import os
import logging

import bpy
import numpy
from mathutils import Quaternion

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _addon_data_dir():
    """Return the addon's data directory."""
    return os.path.join(os.path.dirname(__file__), "data")


def _get_assets_root():
    """Get the parent directory of the addon (resolves symlinks/junctions)."""
    return os.path.dirname(os.path.realpath(os.path.dirname(__file__)))


def _get_autorig_blend_path():
    """Path to the pre-generated AutoRig .blend."""
    local = os.path.join(_addon_data_dir(), "autorig.blend")
    if os.path.isfile(local):
        return local
    return os.path.join(_get_assets_root(), "HumanBodyAssets", "autorig.blend")


def _get_weights_npz_path():
    """Path to the bone weight NPZ file."""
    local = os.path.join(_addon_data_dir(), "weights", "original.npz")
    if os.path.isfile(local):
        return local
    return os.path.join(_get_assets_root(), "HumanBodyAssets",
                        "characters", "mb_female", "weights", "original.npz")



def _get_poses_dir():
    """Path to the pose JSON directory."""
    local = os.path.join(_addon_data_dir(), "poses")
    if os.path.isdir(local):
        return local
    return os.path.join(_get_assets_root(), "HumanBodyAssets",
                        "characters", "mb_female", "poses")


# ---------------------------------------------------------------------------
# NPZ utilities
# ---------------------------------------------------------------------------

def _npz_names(z):
    """Decode null-separated UTF-8 names from NPZ 'names' array."""
    return [n.decode("utf-8") for n in bytes(z["names"]).split(b'\0')]


def _npz_vg_iter(z):
    """Yield (name, idx_array, weights_array) from a HumanBody NPZ file."""
    idx = z["idx"]
    weights = z["weights"]
    i = 0
    for name, cnt in zip(_npz_names(z), z["cnt"]):
        i2 = i + int(cnt)
        yield name, idx[i:i2], weights[i:i2]
        i = i2


# ---------------------------------------------------------------------------
# Rig setup helpers
# ---------------------------------------------------------------------------

def _import_weights(obj, npz_path):
    """Create bone vertex groups from a HumanBody weights NPZ file.

    Keeps DEF- prefix on group names — these match Rigify deformation
    bone names (DEF-spine.001) in the rig.
    """
    z = numpy.load(npz_path)
    count = 0
    for name, idx, weights in _npz_vg_iter(z):
        if name in obj.vertex_groups:
            obj.vertex_groups.remove(obj.vertex_groups[name])
        vg = obj.vertex_groups.new(name=name)
        for vi, w in zip(idx, weights):
            vg.add([int(vi)], float(w), 'REPLACE')
        count += 1
    return count


# MCH/ORG bones that carry HumanBody NPZ weights for face geometry.
# Rigify sets use_deform=False on these, but we need them to deform.
_FACE_DEFORM_BONES = [
    "MCH-eye.L", "MCH-eye.R",
    "MCH-lid.B.L.001", "MCH-lid.B.L.002", "MCH-lid.B.L.003",
    "MCH-lid.B.R.001", "MCH-lid.B.R.002", "MCH-lid.B.R.003",
    "MCH-lid.T.L.001", "MCH-lid.T.L.002", "MCH-lid.T.L.003",
    "MCH-lid.T.R.001", "MCH-lid.T.R.002", "MCH-lid.T.R.003",
    "ORG-teeth.B", "ORG-teeth.T",
]


def _enable_face_deform_bones(rig):
    """Enable use_deform on MCH/ORG bones that carry NPZ face weights."""
    count = 0
    for bname in _FACE_DEFORM_BONES:
        bone = rig.data.bones.get(bname)
        if bone and not bone.use_deform:
            bone.use_deform = True
            count += 1
    if count:
        logger.info("Enabled use_deform on %d face bones (MCH/ORG)", count)


def _setup_rigify_properties(rig):
    """Set Rigify custom properties for FK pose mode."""
    torso = rig.pose.bones.get("torso")
    if torso:
        torso["neck_follow"] = 1.0
        torso["head_follow"] = 1.0



# ---------------------------------------------------------------------------
# Shared helper: find rig for a HumanBody object
# ---------------------------------------------------------------------------

def _find_rig(obj):
    """Find the armature rig for a HumanBody object."""
    if obj.parent and obj.parent.type == 'ARMATURE':
        return obj.parent
    for mod in obj.modifiers:
        if mod.type == 'ARMATURE' and mod.object:
            return mod.object
    return None


# ---------------------------------------------------------------------------
# Pose system
# ---------------------------------------------------------------------------

def _list_poses():
    """Return list of (filename_no_ext, label) for available poses."""
    d = _get_poses_dir()
    if not os.path.isdir(d):
        return []
    result = []
    for f in sorted(os.listdir(d)):
        if f.endswith(".json"):
            name = f[:-5]
            label = name.replace("_", " ").title()
            result.append((name, label))
    return result


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


class HUMANBODY_OT_load_pose(bpy.types.Operator):
    bl_idname = "humanbody.load_pose"
    bl_label = "Load Pose"
    bl_description = "Load a pose from the pose library"
    bl_options = {'REGISTER', 'UNDO'}

    pose_name: bpy.props.StringProperty()

    def execute(self, context):
        import json

        obj = context.active_object
        # obj.type PRUEFEN, bevor obj.data angefasst wird: Bei einem Empty ist
        # obj.data None, und .get() darauf beendet den Operator mit einem
        # Traceback statt mit der Meldung darunter. HUMANBODY_OT_add_rig macht
        # es seit jeher richtig, diese drei nicht (Review 13.08.2026).
        if not obj or obj.type != 'MESH' or not obj.data.get("humanbody"):
            self.report({'ERROR'}, "Select a HumanBody character")
            return {'CANCELLED'}

        rig = _find_rig(obj)
        if not rig:
            self.report({'ERROR'}, "Add a rig first")
            return {'CANCELLED'}

        pose_path = os.path.join(_get_poses_dir(), self.pose_name + ".json")
        if not os.path.isfile(pose_path):
            self.report({'ERROR'}, f"Pose not found: {self.pose_name}")
            return {'CANCELLED'}

        with open(pose_path, "r", encoding="utf-8") as f:
            pose_data = json.load(f)

        # Set Rigify properties for pose mode
        torso = rig.pose.bones.get("torso")
        if torso:
            torso["neck_follow"] = 1.0
            torso["head_follow"] = 1.0

        # Clear current pose — need rig as active object for pose mode
        old_active = context.view_layer.objects.active
        bpy.ops.object.select_all(action='DESELECT')
        rig.select_set(True)
        context.view_layer.objects.active = rig
        try:
            bpy.ops.object.mode_set(mode="POSE")
            bpy.ops.pose.select_all(action="SELECT")
            bpy.ops.pose.loc_clear()
            bpy.ops.pose.rot_clear()
            bpy.ops.pose.scale_clear()
        finally:
            bpy.ops.object.mode_set(mode="OBJECT")
            if old_active:
                context.view_layer.objects.active = old_active

        # Apply Rigify quaternions
        applied = 0
        for rigify_name, quat_vals in pose_data.items():
            pbone = rig.pose.bones.get(rigify_name)
            if not pbone:
                continue
            pbone.rotation_mode = 'QUATERNION'
            pbone.rotation_quaternion = Quaternion(quat_vals)
            applied += 1

        # Adjust torso height for sitting poses
        if hasattr(context, "evaluated_depsgraph_get"):
            erig = rig.evaluated_get(context.evaluated_depsgraph_get())
            if torso:
                min_z = torso.head[2]
                for bone in erig.pose.bones:
                    if not bone.name.startswith("ORG-"):
                        continue
                    for attr in ("head", "tail"):
                        val = getattr(bone, attr)
                        if val[2] < min_z:
                            min_z = val[2]
                min_z = max(min_z, 0)
                torso.location = (0, 0, -min_z)

        context.view_layer.update()
        self.report({'INFO'}, f"Pose '{self.pose_name}' applied ({applied} bones)")
        return {'FINISHED'}


class HUMANBODY_OT_clear_pose(bpy.types.Operator):
    bl_idname = "humanbody.clear_pose"
    bl_label = "Clear Pose"
    bl_description = "Reset all bones to rest position"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        # obj.type PRUEFEN, bevor obj.data angefasst wird: Bei einem Empty ist
        # obj.data None, und .get() darauf beendet den Operator mit einem
        # Traceback statt mit der Meldung darunter. HUMANBODY_OT_add_rig macht
        # es seit jeher richtig, diese drei nicht (Review 13.08.2026).
        if not obj or obj.type != 'MESH' or not obj.data.get("humanbody"):
            return {'CANCELLED'}

        rig = _find_rig(obj)
        if not rig:
            self.report({'WARNING'}, "No rig found")
            return {'CANCELLED'}

        for pbone in rig.pose.bones:
            pbone.rotation_quaternion = Quaternion((1, 0, 0, 0))
            pbone.rotation_euler = (0, 0, 0)
            pbone.location = (0, 0, 0)
            pbone.scale = (1, 1, 1)

        context.view_layer.update()
        self.report({'INFO'}, "Pose cleared")
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
