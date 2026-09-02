# -*- coding: utf-8 -*-
import os
import logging
import bpy
from mathutils import Quaternion
logger = logging.getLogger(__name__)
from ..charakter.charakterpruefung import Charakterpruefung
from .rigpfade import Rigpfade


class HUMANBODY_OT_load_pose(bpy.types.Operator):
    bl_idname = "humanbody.load_pose"
    bl_label = "Load Pose"
    bl_description = "Load a pose from the pose library"
    bl_options = {'REGISTER', 'UNDO'}

    pose_name: bpy.props.StringProperty()

    def execute(self, context):
        import json

        obj, rig = Charakterpruefung.rig_holen(context, self)
        if not rig:
            return {'CANCELLED'}

        pose_path = os.path.join(Rigpfade._get_poses_dir(), self.pose_name + ".json")
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

        self._pose_leeren(context, rig)
        applied = self._drehungen_setzen(rig, pose_data)
        self._sitzhoehe(context, rig, torso)

        context.view_layer.update()
        self.report({'INFO'}, f"Pose '{self.pose_name}' applied ({applied} bones)")
        return {'FINISHED'}

    # ------------------------------------------------------------ Bausteine

    @staticmethod
    def _pose_leeren(context, rig):
        u"""Die aktuelle Pose zuruecksetzen.

        Das geht nur im Posenmodus, und dafuer muss das RIG aktiv sein —
        nicht das Netz. Die vorige Auswahl wird im `finally`
        wiederhergestellt, sonst steht der Nutzer nach einem Posenwechsel
        ploetzlich auf dem Skelett.
        """
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

    @staticmethod
    def _drehungen_setzen(rig, pose_data):
        u"""Die Quaternionen der Posendatei auf die Knochen legen.

        Knochen, die es im Rig nicht gibt, werden uebergangen: Die
        Posendateien stammen aus CharMorph und MB-Lab und fuehren Namen,
        die das Rigify-Rig nicht alle kennt.
        """
        applied = 0
        for rigify_name, quat_vals in pose_data.items():
            pbone = rig.pose.bones.get(rigify_name)
            if not pbone:
                continue
            pbone.rotation_mode = 'QUATERNION'
            pbone.rotation_quaternion = Quaternion(quat_vals)
            applied += 1
        return applied

    @staticmethod
    def _sitzhoehe(context, rig, torso):
        u"""Den Rumpf so weit anheben, dass nichts unter dem Boden steht.

        Bei einer Sitzpose wandern Gesaess und Fuesse unter die
        Nullebene. Gesucht wird der tiefste Punkt aller `ORG-`-Knochen im
        AUSGEWERTETEN Rig — also nach der Pose — und der Rumpf um genau
        so viel angehoben. Steht ohnehin nichts unter null, bleibt es.
        """
        if not (torso and hasattr(context, "evaluated_depsgraph_get")):
            return
        erig = rig.evaluated_get(context.evaluated_depsgraph_get())
        min_z = torso.head[2]
        for bone in erig.pose.bones:
            if not bone.name.startswith("ORG-"):
                continue
            for attr in ("head", "tail"):
                val = getattr(bone, attr)
                if val[2] < min_z:
                    min_z = val[2]
        torso.location = (0, 0, -max(min_z, 0))


class HUMANBODY_OT_clear_pose(bpy.types.Operator):
    bl_idname = "humanbody.clear_pose"
    bl_label = "Clear Pose"
    bl_description = "Reset all bones to rest position"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        _obj, rig = Charakterpruefung.rig_holen(context, self)
        if not rig:
            return {'CANCELLED'}

        for pbone in rig.pose.bones:
            pbone.rotation_quaternion = Quaternion((1, 0, 0, 0))
            pbone.rotation_euler = (0, 0, 0)
            pbone.location = (0, 0, 0)
            pbone.scale = (1, 1, 1)

        context.view_layer.update()
        self.report({'INFO'}, "Pose cleared")
        return {'FINISHED'}
