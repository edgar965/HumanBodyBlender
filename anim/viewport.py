# -*- coding: utf-8 -*-
import logging
import bpy
from .altbestand import Altbestand
logger = logging.getLogger(__name__)



class Ansichtsfenster:
    u"""Die frueheren Modulfunktionen, gebuendelt."""

    #: Die waehrend des Retargets abgehaengten Handler.
    ausgesetzte = []

    @staticmethod
    def _set_cloth_viewport(enable):
        """Enable/disable CLOTH modifiers in viewport (ARMATURE stays active)."""
        for obj in bpy.data.objects:
            if obj.type != 'MESH':
                continue
            for mod in obj.modifiers:
                if mod.type == 'CLOTH':
                    mod.show_viewport = enable

    @staticmethod
    def _hide_meshes_for_retarget(rig):
        """Hide all mesh children to speed up frame-by-frame retarget."""
        for child in rig.children:
            if child.type == 'MESH' and not child.hide_get():
                child.hide_set(True)
                child["_hb_was_visible"] = True

    @staticmethod
    def _show_meshes_after_retarget(rig):
        """Restore meshes hidden by _hide_meshes_for_retarget."""
        for child in rig.children:
            if child.get("_hb_was_visible"):
                child.hide_set(False)
                del child["_hb_was_visible"]

    @staticmethod
    def _optimize_viewport(context):
        """Optimize viewport for smooth animation playback.

        - Suspend depsgraph handlers (material sync, morph update)
        - Simplify: reduce SubSurf to 0 (body 70k → 18k verts)
        - Disable heavy garment modifiers (Solidify, Corrective Smooth)
        - Hide rig widget objects
        - Frame-drop sync for real-time playback
        """
        scene = context.scene

        # Suspend depsgraph handlers — they run every frame and are unnecessary
        # during animation (material colors & morph values don't change)
        handlers = bpy.app.handlers.depsgraph_update_post
        Ansichtsfenster.ausgesetzte = [h for h in handlers
                               if getattr(h, '__module__', '').startswith('HumanBody')]
        for h in Ansichtsfenster.ausgesetzte:
            handlers.remove(h)

        # Store original settings for restore
        scene["_hb_anim_simplify"] = scene.render.use_simplify
        scene["_hb_anim_subdiv"] = scene.render.simplify_subdivision

        # Global simplify: all SubSurf → level 0
        scene.render.use_simplify = True
        scene.render.simplify_subdivision = 0

        # Frame-drop: skip frames to maintain real-time speed
        scene.sync_mode = 'FRAME_DROP'

        # Disable heavy modifiers on garments (keep only ARMATURE)
        for obj in bpy.data.objects:
            if obj.type != 'MESH':
                continue
            for mod in obj.modifiers:
                if mod.type in ('SOLIDIFY', 'CORRECTIVE_SMOOTH', 'SHRINKWRAP'):
                    mod.show_viewport = False

        # Hide WGT- widget collection/objects (150+ tiny meshes)
        for col in bpy.data.collections:
            if col.name.startswith("WGT") or col.name.startswith("WGTS"):
                col.hide_viewport = True
        for obj in bpy.data.objects:
            if obj.name.startswith("WGT-"):
                obj.hide_viewport = True

    @staticmethod
    def _restore_viewport(context):
        """Restore viewport settings after animation."""
        scene = context.scene

        # Re-register suspended depsgraph handlers
        handlers = bpy.app.handlers.depsgraph_update_post
        for h in Ansichtsfenster.ausgesetzte:
            if h not in handlers:
                handlers.append(h)
        Ansichtsfenster.ausgesetzte = []

        # Restore simplify
        if "_hb_anim_simplify" in scene:
            scene.render.use_simplify = bool(scene["_hb_anim_simplify"])
            del scene["_hb_anim_simplify"]
        else:
            scene.render.use_simplify = False

        if "_hb_anim_subdiv" in scene:
            scene.render.simplify_subdivision = int(scene["_hb_anim_subdiv"])
            del scene["_hb_anim_subdiv"]

        scene.sync_mode = 'NONE'

        # Re-enable garment modifiers
        for obj in bpy.data.objects:
            if obj.type != 'MESH':
                continue
            for mod in obj.modifiers:
                if mod.type in ('SOLIDIFY', 'CORRECTIVE_SMOOTH', 'SHRINKWRAP'):
                    mod.show_viewport = True

        # Un-hide widgets
        for col in bpy.data.collections:
            if col.name.startswith("WGT") or col.name.startswith("WGTS"):
                col.hide_viewport = False
        for obj in bpy.data.objects:
            if obj.name.startswith("WGT-"):
                obj.hide_viewport = False

    @staticmethod
    def _cleanup_old_anim(context, rig):
        """Reste des vorigen Laufs entfernen — siehe `Altbestand`.

        Stand bis zum 01.09.2026 hier: mit 33 Verzweigungen die
        verschachteltste Funktion des Addons, fuenf Aufgaben in einem
        Rumpf. Vier Aufrufstellen rufen sie weiterhin unter diesem
        Namen.
        """
        Altbestand.raeumen(context, rig)
