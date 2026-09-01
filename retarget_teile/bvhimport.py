# -*- coding: utf-8 -*-
import logging
import bpy
from ..rigaktionen import _parse_bvh_info, _get_action_fcurves, _rig_height
logger = logging.getLogger(__name__)
from .knochenlisten import _CMU_BVH_BONES, _V4_EXTRA_BONES
from .knochenlisten import _MOCAPNET_BVH_BONES
from .knochenlisten import _OPENPOSE_TO_CMU


def _import_bvh_armature(context, bvh_path):
    """Import BVH as a new armature, return (bvh_rig, f_start, f_end)."""
    bvh_fps, bvh_nframes = _parse_bvh_info(bvh_path)
    orig = set(context.scene.objects)
    bpy.ops.import_anim.bvh(
        filepath=bvh_path,
        global_scale=1.0,
        frame_start=1,
        use_fps_scale=False,
        use_cyclic=False,
        rotate_mode='NATIVE',
        axis_forward='-Z',
        axis_up='Y',
    )
    bvh_rig = None
    for o in set(context.scene.objects) - orig:
        if o.type == 'ARMATURE':
            bvh_rig = o
            break
    return bvh_rig, 1, max(bvh_nframes, 1)


def _normalize_openpose_bones(context, bvh_rig):
    """Rename OpenPose-style BVH bones to CMU-style names.

    Also updates FCurve data_paths.
    """
    if 'rShldr' not in bvh_rig.data.bones:
        return False

    prev_active = context.view_layer.objects.active
    context.view_layer.objects.active = bvh_rig
    bvh_rig.select_set(True)
    if context.object and context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.mode_set(mode='EDIT')

    renamed = 0
    for old_name, new_name in _OPENPOSE_TO_CMU.items():
        eb = bvh_rig.data.edit_bones.get(old_name)
        if eb:
            eb.name = new_name
            renamed += 1

    bpy.ops.object.mode_set(mode='OBJECT')

    if bvh_rig.animation_data and bvh_rig.animation_data.action:
        for fc in _get_action_fcurves(bvh_rig.animation_data.action):
            for old_name, new_name in _OPENPOSE_TO_CMU.items():
                old_path = f'pose.bones["{old_name}"]'
                if old_path in fc.data_path:
                    fc.data_path = fc.data_path.replace(old_path,
                                                        f'pose.bones["{new_name}"]')
                    break

    if prev_active and prev_active.name in bpy.data.objects:
        context.view_layer.objects.active = prev_active

    logger.info("normalized %s OpenPose bones → CMU names", renamed)
    return True


def _filter_bvh_bones(context, bvh_rig, is_mocapnet, is_v4=False):
    """Remove unmapped BVH bones to speed up KBS bake.

    Keeps mapped bones + their ancestors (to preserve hierarchy).
    """
    mapped = _MOCAPNET_BVH_BONES if is_mocapnet else _CMU_BVH_BONES
    if is_v4:
        mapped = mapped | _V4_EXTRA_BONES

    keep = set()
    for bname in mapped:
        bone = bvh_rig.data.bones.get(bname)
        while bone:
            keep.add(bone.name)
            bone = bone.parent

    total = len(bvh_rig.data.bones)
    if not keep or len(keep) >= total:
        return

    prev_active = context.view_layer.objects.active
    context.view_layer.objects.active = bvh_rig
    bvh_rig.select_set(True)
    if context.object and context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.mode_set(mode='EDIT')
    for eb in list(bvh_rig.data.edit_bones):
        if eb.name not in keep:
            bvh_rig.data.edit_bones.remove(eb)
    bpy.ops.object.mode_set(mode='OBJECT')

    remaining = set(b.name for b in bvh_rig.data.bones)
    if bvh_rig.animation_data and bvh_rig.animation_data.action:
        fcurves = _get_action_fcurves(bvh_rig.animation_data.action)
        to_remove = []
        for fc in fcurves:
            if 'pose.bones["' in fc.data_path:
                bname = fc.data_path.split('pose.bones["')[1].split('"]')[0]
                if bname not in remaining:
                    to_remove.append(fc)
        for fc in to_remove:
            try:
                fcurves.remove(fc)
            # stumm gewollt: Die Kurve kann bereits entfernt sein, wenn zwei
            # Filter greifen. In einer Schleife ueber hunderte Kurven.
            except Exception:
                pass

    removed = total - len(bvh_rig.data.bones)
    logger.info("filtered BVH: %s -> %s bones (%s removed)",
                total, len(bvh_rig.data.bones), removed)

    if prev_active and prev_active.name in bpy.data.objects:
        context.view_layer.objects.active = prev_active


def _scale_to_match(src_rig, tgt_rig):
    """Scale src_rig so its height matches tgt_rig."""
    th = _rig_height(tgt_rig)
    sh = _rig_height(src_rig)
    if sh > 0.001:
        s = th / sh
        src_rig.scale = (s, s, s)
