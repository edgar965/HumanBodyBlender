# -*- coding: utf-8 -*-
import os
import logging
import bpy
from mathutils import Quaternion
logger = logging.getLogger(__name__)
from .rigsuche import _find_rig
from .rigpfade import _get_poses_dir


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
