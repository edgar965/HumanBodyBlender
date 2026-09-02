# -*- coding: utf-8 -*-
import logging
import bpy
from ..rig_teile.rigsuche import Rigsuche
logger = logging.getLogger(__name__)


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

        rig = Rigsuche._find_rig(obj)

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
