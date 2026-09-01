# -*- coding: utf-8 -*-
import logging
import bpy
from mathutils import Quaternion
logger = logging.getLogger(__name__)


def _set_cloth_viewport(enable):
    """Enable/disable CLOTH modifiers in viewport (ARMATURE stays active)."""
    for obj in bpy.data.objects:
        if obj.type != 'MESH':
            continue
        for mod in obj.modifiers:
            if mod.type == 'CLOTH':
                mod.show_viewport = enable


def _hide_meshes_for_retarget(rig):
    """Hide all mesh children to speed up frame-by-frame retarget."""
    for child in rig.children:
        if child.type == 'MESH' and not child.hide_get():
            child.hide_set(True)
            child["_hb_was_visible"] = True


def _show_meshes_after_retarget(rig):
    """Restore meshes hidden by _hide_meshes_for_retarget."""
    for child in rig.children:
        if child.get("_hb_was_visible"):
            child.hide_set(False)
            del child["_hb_was_visible"]


_suspended_handlers = []


def _optimize_viewport(context):
    """Optimize viewport for smooth animation playback.

    - Suspend depsgraph handlers (material sync, morph update)
    - Simplify: reduce SubSurf to 0 (body 70k → 18k verts)
    - Disable heavy garment modifiers (Solidify, Corrective Smooth)
    - Hide rig widget objects
    - Frame-drop sync for real-time playback
    """
    global _suspended_handlers
    scene = context.scene

    # Suspend depsgraph handlers — they run every frame and are unnecessary
    # during animation (material colors & morph values don't change)
    handlers = bpy.app.handlers.depsgraph_update_post
    _suspended_handlers = [h for h in handlers
                           if getattr(h, '__module__', '').startswith('HumanBody')]
    for h in _suspended_handlers:
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


def _restore_viewport(context):
    """Restore viewport settings after animation."""
    global _suspended_handlers
    scene = context.scene

    # Re-register suspended depsgraph handlers
    handlers = bpy.app.handlers.depsgraph_update_post
    for h in _suspended_handlers:
        if h not in handlers:
            handlers.append(h)
    _suspended_handlers = []

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


def _cleanup_old_anim(context, rig):
    """Remove previous animation data and objects."""
    try:
        if context.screen.is_animation_playing:
            bpy.ops.screen.animation_play()
    # stumm gewollt: Die Wiedergabe anzuhalten ist Vorarbeit. Laeuft keine,
    # ist nichts zu tun.
    except Exception:
        pass
    for pbone in rig.pose.bones:
        for c in list(pbone.constraints):
            if c.name.startswith("hb_anim") or c.name.startswith("_rt"):
                pbone.constraints.remove(c)
    if rig.animation_data and rig.animation_data.action:
        act = rig.animation_data.action
        rig.animation_data.action = None
        if act.users == 0:
            bpy.data.actions.remove(act)
    for pbone in rig.pose.bones:
        pbone.rotation_quaternion = Quaternion((1, 0, 0, 0))
        pbone.rotation_euler = (0, 0, 0)
        pbone.location = (0, 0, 0)
    for o in list(bpy.data.objects):
        if o.get("humanbody_bvh"):
            bpy.data.objects.remove(o, do_unlink=True)
    for o in list(bpy.data.objects):
        if o.type == 'ARMATURE' and (
            o.name.startswith("BvhRig") or o.name.startswith("Y_")
            or o.name.startswith("BVH_Preview")
            or o.name.startswith("Rig_Preview")
            or o.name.startswith("_BVH_retarget_tmp")
            or o.name.startswith("ROK_Preview")
            or o.name.startswith("ROK_")
            or o.name.startswith("ROK46_Preview")
            or o.name.startswith("ROK46_")
            or o.name.startswith("RTEST_Preview")
            or o.name.startswith("RTEST_")
            or o.name.startswith("_Rokoko_")
        ):
            bpy.data.objects.remove(o, do_unlink=True)
    # Remove preview mesh copies
    for o in list(bpy.data.objects):
        if o.type == 'MESH' and (
            o.name.startswith("Preview_")
            or o.name.startswith("ROK_")
            or o.name.startswith("ROK46_")
            or o.name.startswith("RTEST_")
        ):
            bpy.data.objects.remove(o, do_unlink=True)
