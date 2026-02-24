# SPDX-License-Identifier: GPL-3.0-or-later
#
# BVH motion capture retargeting for HumanBody addon.
# Extracted from animation.py — retarget_rokoko, retarget_kbs + helpers.

import math
import os
import logging

import bpy
from mathutils import Quaternion, Euler, Vector

from .animation import (
    _parse_bvh_info,
    _set_fk_mode,
    _get_action_fcurves,
    _assign_action,
    _transfer_root_motion,
    _rig_height,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# BVH bone sets (for filtering)
# ---------------------------------------------------------------------------

_CMU_BVH_BONES = {
    'Hips', 'Spine', 'Spine1', 'Neck', 'Neck1', 'Head',
    'LeftShoulder', 'LeftArm', 'LeftForeArm', 'LeftHand',
    'RightShoulder', 'RightArm', 'RightForeArm', 'RightHand',
    'LeftUpLeg', 'LeftLeg', 'LeftFoot', 'LeftToeBase',
    'RightUpLeg', 'RightLeg', 'RightFoot', 'RightToeBase',
}

_MOCAPNET_BVH_BONES = {
    'hip', 'abdomen', 'chest', 'neck', 'neck1', 'head',
    'lcollar', 'lshoulder', 'lelbow', 'lhand',
    'rcollar', 'rshoulder', 'relbow', 'rhand',
    'lhip', 'lknee', 'lfoot', 'toe1-1.l',
    'rhip', 'rknee', 'rfoot', 'toe1-1.r',
}


# ---------------------------------------------------------------------------
# Retarget mapping tables: BVH bone → Rigify FK bone
# ---------------------------------------------------------------------------

_ROKOKO_MAP_CMU = {
    "Hips": "torso", "LowerBack": "spine_fk.001",
    "Spine": "spine_fk.002", "Spine1": "spine_fk.003",
    "Neck1": "neck", "Head": "head",
    "LeftShoulder": "shoulder.L", "LeftArm": "upper_arm_fk.L",
    "LeftForeArm": "forearm_fk.L", "LeftHand": "hand_fk.L",
    "RightShoulder": "shoulder.R", "RightArm": "upper_arm_fk.R",
    "RightForeArm": "forearm_fk.R", "RightHand": "hand_fk.R",
    "LeftUpLeg": "thigh_fk.L", "LeftLeg": "shin_fk.L",
    "LeftFoot": "foot_fk.L",
    "RightUpLeg": "thigh_fk.R", "RightLeg": "shin_fk.R",
    "RightFoot": "foot_fk.R",
}

_ROKOKO_MAP_MOCAPNET = {
    "hip": "torso", "abdomen": "spine_fk.001",
    "chest": "spine_fk.002", "neck": "spine_fk.003",
    "neck1": "neck", "head": "head",
    "lcollar": "shoulder.L", "lshoulder": "upper_arm_fk.L",
    "lelbow": "forearm_fk.L", "lhand": "hand_fk.L",
    "rcollar": "shoulder.R", "rshoulder": "upper_arm_fk.R",
    "relbow": "forearm_fk.R", "rhand": "hand_fk.R",
    "lhip": "thigh_fk.L", "lknee": "shin_fk.L", "lfoot": "foot_fk.L",
    "rhip": "thigh_fk.R", "rknee": "shin_fk.R", "rfoot": "foot_fk.R",
}

# MocapNET v4 finger bones → Rigify finger bones
_V4_FINGER_MAP = {}
for _side_bvh, _side_rig in [('.l', '.L'), ('.r', '.R')]:
    _thumb_src = 'lthumb' if _side_bvh == '.l' else 'rthumb'
    _V4_FINGER_MAP[_thumb_src] = f"thumb.01_master{_side_rig}"
    _V4_FINGER_MAP[f"finger1-2{_side_bvh}"] = f"thumb.02{_side_rig}"
    _V4_FINGER_MAP[f"finger1-3{_side_bvh}"] = f"thumb.03{_side_rig}"
    for _fn, _rn in [('2', 'index'), ('3', 'middle'), ('4', 'ring'), ('5', 'pinky')]:
        _V4_FINGER_MAP[f"finger{_fn}-1{_side_bvh}"] = f"f_{_rn}.01_master{_side_rig}"
        _V4_FINGER_MAP[f"finger{_fn}-2{_side_bvh}"] = f"f_{_rn}.02{_side_rig}"
        _V4_FINGER_MAP[f"finger{_fn}-3{_side_bvh}"] = f"f_{_rn}.03{_side_rig}"
del _side_bvh, _side_rig, _thumb_src, _fn, _rn

_V4_EXTRA_BONES = set(_V4_FINGER_MAP.keys())

# OpenPose → CMU bone name normalization
_OPENPOSE_TO_CMU = {
    'rCollar': 'rcollar', 'rShldr': 'rshoulder', 'rForeArm': 'relbow',
    'rHand': 'rhand', 'rThigh': 'rhip', 'rShin': 'rknee', 'rFoot': 'rfoot',
    'rButtock': 'rbuttock',
    'lCollar': 'lcollar', 'lShldr': 'lshoulder', 'lForeArm': 'lelbow',
    'lHand': 'lhand', 'lThigh': 'lhip', 'lShin': 'lknee', 'lFoot': 'lfoot',
    'lButtock': 'lbuttock',
    'toe1-1.R': 'toe1-1.r', 'toe1-2.R': 'toe1-2.r',
    'toe2-1.R': 'toe2-1.r', 'toe2-2.R': 'toe2-2.r', 'toe2-3.R': 'toe2-3.r',
    'toe3-1.R': 'toe3-1.r', 'toe3-2.R': 'toe3-2.r', 'toe3-3.R': 'toe3-3.r',
    'toe4-1.R': 'toe4-1.r', 'toe4-2.R': 'toe4-2.r', 'toe4-3.R': 'toe4-3.r',
    'toe5-1.R': 'toe5-1.r', 'toe5-2.R': 'toe5-2.r', 'toe5-3.R': 'toe5-3.r',
    'toe1-1.L': 'toe1-1.l', 'toe1-2.L': 'toe1-2.l',
    'toe2-1.L': 'toe2-1.l', 'toe2-2.L': 'toe2-2.l', 'toe2-3.L': 'toe2-3.l',
    'toe3-1.L': 'toe3-1.l', 'toe3-2.L': 'toe3-2.l', 'toe3-3.L': 'toe3-3.l',
    'toe4-1.L': 'toe4-1.l', 'toe4-2.L': 'toe4-2.l', 'toe4-3.L': 'toe4-3.l',
    'toe5-1.L': 'toe5-1.l', 'toe5-2.L': 'toe5-2.l', 'toe5-3.L': 'toe5-3.l',
}


# ---------------------------------------------------------------------------
# KBS helpers
# ---------------------------------------------------------------------------

# Spine bones whose fcurves are taken from the 'Pose' pass (correct spine).
_SPINE_MERGE_BONES = {
    "torso", "spine_fk.001", "spine_fk.002", "spine_fk.003", "neck", "head",
}


def _extract_fcurve_data(act, bone_names):
    """Save keyframe data for bones from an action.

    Returns {(data_path, array_index): [(frame, value, handle_left, handle_right), ...]}
    """
    saved = {}
    for fc in _get_action_fcurves(act):
        for bname in bone_names:
            if f'"{bname}"' in fc.data_path:
                kps = []
                for kp in fc.keyframe_points:
                    kps.append((kp.co[0], kp.co[1],
                                (kp.handle_left[0], kp.handle_left[1]),
                                (kp.handle_right[0], kp.handle_right[1]),
                                kp.interpolation))
                saved[(fc.data_path, fc.array_index)] = kps
                break
    return saved


def _apply_fcurve_data(act, saved, rig=None):
    """Overwrite fcurves in act with previously saved keyframe data.

    If *rig* is given, also creates NEW fcurves for saved entries that have
    no matching fcurve in *act* (required for merging spine data into a
    Rokoko action that only contains limb rotations).
    """
    applied = set()
    for fc in _get_action_fcurves(act):
        key = (fc.data_path, fc.array_index)
        kps_data = saved.get(key)
        if not kps_data:
            continue
        applied.add(key)
        while len(fc.keyframe_points) < len(kps_data):
            fc.keyframe_points.insert(kps_data[0][0], kps_data[0][1])
        for i, (frame, value, hl, hr, interp) in enumerate(kps_data):
            if i < len(fc.keyframe_points):
                kp = fc.keyframe_points[i]
                kp.co = (frame, value)
                kp.handle_left = hl
                kp.handle_right = hr
                kp.interpolation = interp
        fc.update()

    missing = {k: v for k, v in saved.items() if k not in applied}
    if not missing or not rig:
        return

    new_fc_fn = None
    try:
        new_fc_fn = act.fcurves.new
        act.fcurves.new  # verify attribute exists
    except Exception:
        new_fc_fn = None
    if not new_fc_fn:
        try:
            layer = act.layers[0]
            strip = layer.strips[0]
            slot = rig.animation_data.action_slot
            cb = strip.channelbag(slot, ensure=True)
            new_fc_fn = cb.fcurves.new
        except Exception:
            print(f"[Animation] WARNING: cannot create fcurves in {act.name}")
            return

    created = 0
    for (data_path, array_index), kps_data in missing.items():
        fc = new_fc_fn(data_path=data_path, index=array_index)
        for frame, value, hl, hr, interp in kps_data:
            kp = fc.keyframe_points.insert(frame, value)
            kp.handle_left = hl
            kp.handle_right = hr
            kp.interpolation = interp
        fc.update()
        created += 1
    if created:
        print(f"[Animation]   created {created} new fcurves in {act.name}")


def _reset_rig_for_kbs(context, rig, orig_bone_names):
    """Reset rig between two KBS passes: remove action, pose, extra bones."""
    if rig.animation_data and rig.animation_data.action:
        act = rig.animation_data.action
        rig.animation_data.action = None
        if act.users == 0:
            bpy.data.actions.remove(act)

    for pb in rig.pose.bones:
        pb.rotation_quaternion = Quaternion()
        pb.location = Vector()
    context.view_layer.update()

    context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    for eb in list(rig.data.edit_bones):
        if eb.name not in orig_bone_names:
            rig.data.edit_bones.remove(eb)
    bpy.ops.object.mode_set(mode='OBJECT')
    context.view_layer.update()


def _kbs_run_pass(context, rig, bvh_path, is_mocapnet, match_transform,
                  bvh_rig=None, keep_bvh=False):
    """Run a single KBS retarget pass with specified match_transform.

    If bvh_rig is provided, reuses it instead of importing a new BVH.
    If keep_bvh is True, does not delete the BVH rig after bake.
    Returns (action, f_start, f_end).
    """
    if bvh_rig is None:
        bvh_rig, f_start, f_end = _import_bvh_armature(context, bvh_path)
        if not bvh_rig:
            raise RuntimeError("BVH import produced no armature")
        _scale_to_match(bvh_rig, rig)
    else:
        _, bvh_nframes = _parse_bvh_info(bvh_path)
        f_start, f_end = 1, max(bvh_nframes, 1)

    if context.object and context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    try:
        # Source (BVH) bone mappings
        ts = bvh_rig.data.retarget_retarget
        if is_mocapnet:
            ts.spine.hips = 'hip';        ts.spine.spine = 'abdomen'
            ts.spine.spine1 = 'chest';    ts.spine.spine2 = 'neck'
            ts.spine.neck = 'neck1';      ts.spine.head = 'head'
            ts.left_arm.shoulder = 'lcollar';    ts.left_arm.arm = 'lshoulder'
            ts.left_arm.forearm = 'lelbow';      ts.left_arm.hand = 'lhand'
            ts.right_arm.shoulder = 'rcollar';   ts.right_arm.arm = 'rshoulder'
            ts.right_arm.forearm = 'relbow';     ts.right_arm.hand = 'rhand'
            ts.left_leg.upleg = 'lhip';    ts.left_leg.leg = 'lknee'
            ts.left_leg.foot = 'lfoot';    ts.left_leg.toe = 'toe1-1.l'
            ts.right_leg.upleg = 'rhip';   ts.right_leg.leg = 'rknee'
            ts.right_leg.foot = 'rfoot';   ts.right_leg.toe = 'toe1-1.r'
        else:
            ts.spine.hips = 'Hips';      ts.spine.spine = 'Spine'
            ts.spine.spine1 = 'Spine1';  ts.spine.spine2 = 'Neck'
            ts.spine.neck = 'Neck1';     ts.spine.head = 'Head'
            ts.left_arm.shoulder = 'LeftShoulder';   ts.left_arm.arm = 'LeftArm'
            ts.left_arm.forearm = 'LeftForeArm';     ts.left_arm.hand = 'LeftHand'
            ts.right_arm.shoulder = 'RightShoulder'; ts.right_arm.arm = 'RightArm'
            ts.right_arm.forearm = 'RightForeArm';   ts.right_arm.hand = 'RightHand'
            ts.left_leg.upleg = 'LeftUpLeg';   ts.left_leg.leg = 'LeftLeg'
            ts.left_leg.foot = 'LeftFoot';     ts.left_leg.toe = 'LeftToeBase'
            ts.right_leg.upleg = 'RightUpLeg'; ts.right_leg.leg = 'RightLeg'
            ts.right_leg.foot = 'RightFoot';   ts.right_leg.toe = 'RightToeBase'

        # Target (Rigify) bone mappings
        rs = rig.data.retarget_retarget
        rs.spine.hips = 'torso';       rs.spine.spine = 'spine_fk.001'
        rs.spine.spine1 = 'spine_fk.002'; rs.spine.spine2 = 'spine_fk.003'
        rs.spine.neck = 'neck';        rs.spine.head = 'head'
        rs.left_arm.shoulder = 'shoulder.L';    rs.left_arm.arm = 'upper_arm_fk.L'
        rs.left_arm.forearm = 'forearm_fk.L';   rs.left_arm.hand = 'hand_fk.L'
        rs.right_arm.shoulder = 'shoulder.R';   rs.right_arm.arm = 'upper_arm_fk.R'
        rs.right_arm.forearm = 'forearm_fk.R';  rs.right_arm.hand = 'hand_fk.R'
        rs.left_leg.upleg = 'thigh_fk.L';  rs.left_leg.leg = 'shin_fk.L'
        rs.left_leg.foot = 'foot_fk.L';    rs.left_leg.toe = 'toe_fk.L'
        rs.right_leg.upleg = 'thigh_fk.R'; rs.right_leg.leg = 'shin_fk.R'
        rs.right_leg.foot = 'foot_fk.R';   rs.right_leg.toe = 'toe_fk.R'
        rs.root = 'root'

        # Context: BVH active, Rigify selected
        for o in list(context.selected_objects):
            o.select_set(False)
        rig.select_set(True)
        bvh_rig.select_set(True)
        context.view_layer.objects.active = bvh_rig
        context.view_layer.update()

        def _do_kbs():
            bpy.ops.object.mode_set(mode='POSE')
            bpy.ops.armature.retarget_constrain_to_armature(
                src_preset='--Current--', trg_preset='--Current--',
                match_transform=match_transform)
            bpy.ops.object.mode_set(mode='OBJECT')
            context.view_layer.objects.active = bvh_rig
            bpy.ops.armature.retarget_bake_constrained_actions(do_bake=True)

        try:
            with context.temp_override(
                    object=bvh_rig,
                    active_object=bvh_rig,
                    selected_objects=[rig, bvh_rig]):
                _do_kbs()
        except RuntimeError:
            area_3d = next((a for a in bpy.context.screen.areas
                            if a.type == 'VIEW_3D'), None) if hasattr(bpy.context, 'screen') else None
            if area_3d:
                region = next((r for r in area_3d.regions
                               if r.type == 'WINDOW'), area_3d.regions[0])
                with bpy.context.temp_override(
                        window=bpy.context.window,
                        area=area_3d, region=region):
                    _do_kbs()
            else:
                raise

        if rig.animation_data:
            rig.animation_data.use_nla = False
        bpy.ops.object.mode_set(mode='OBJECT')

    finally:
        try:
            if context.object and context.object.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
        except Exception:
            pass
        if not keep_bvh and bvh_rig and bvh_rig.name in bpy.data.objects:
            bpy.data.objects.remove(bvh_rig, do_unlink=True)

    act = rig.animation_data.action if rig.animation_data else None
    return act, f_start, f_end


# ---------------------------------------------------------------------------
# BVH import + bone utilities
# ---------------------------------------------------------------------------

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

    print(f"[Animation]   normalized {renamed} OpenPose bones → CMU names")
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
            except Exception:
                pass

    removed = total - len(bvh_rig.data.bones)
    print(f"[Animation]   filtered BVH: {total} -> {len(bvh_rig.data.bones)} bones "
          f"({removed} removed)")

    if prev_active and prev_active.name in bpy.data.objects:
        context.view_layer.objects.active = prev_active


def _scale_to_match(src_rig, tgt_rig):
    """Scale src_rig so its height matches tgt_rig."""
    th = _rig_height(tgt_rig)
    sh = _rig_height(src_rig)
    if sh > 0.001:
        s = th / sh
        src_rig.scale = (s, s, s)


# ---------------------------------------------------------------------------
# Main retarget functions
# ---------------------------------------------------------------------------

def retarget_kbs(context, rig, bvh_path):
    """Retarget BVH via KBS-DEV Retarget Extension.

    Two-pass approach for all BVH formats:
      Pass 1: match_transform='Pose'  → correct spine rotations
      Pass 2: match_transform='Bone'  → correct arm/leg rotations
    Then merge spine fcurves from pass 1 into pass 2 result.

    Returns (action, f_start, f_end).
    """
    bpy.ops.preferences.addon_enable(module='bl_ext.user_default.retarget')

    bvh_rig, f_start, f_end = _import_bvh_armature(context, bvh_path)
    if not bvh_rig:
        raise RuntimeError("BVH import produced no armature")
    is_mocapnet = 'hip' in bvh_rig.data.bones
    if is_mocapnet:
        _normalize_openpose_bones(context, bvh_rig)
    fmt = "MocapNET" if is_mocapnet else "CMU"
    print(f"[Animation] KBS {fmt}: single BVH import, filtering bones...")

    _filter_bvh_bones(context, bvh_rig, is_mocapnet)
    _scale_to_match(bvh_rig, rig)

    if context.object and context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    orig_bones = set(b.name for b in rig.data.bones)

    # --- Pass 1: match_transform='Pose' → correct spine ---
    print(f"[Animation] KBS {fmt} pass 1/2: spine (match_transform='Pose')")
    act_spine, f_start, f_end = _kbs_run_pass(
        context, rig, bvh_path, is_mocapnet, 'Pose',
        bvh_rig=bvh_rig, keep_bvh=True)
    if not act_spine:
        raise RuntimeError("KBS pass 1 produced no action")
    spine_data = _extract_fcurve_data(act_spine, _SPINE_MERGE_BONES)
    print(f"[Animation]   saved {len(spine_data)} spine fcurves")

    _reset_rig_for_kbs(context, rig, orig_bones)

    # --- Pass 2: match_transform='Bone' → correct arms/legs ---
    print(f"[Animation] KBS {fmt} pass 2/2: limbs (match_transform='Bone')")
    act_final, f_start, f_end = _kbs_run_pass(
        context, rig, bvh_path, is_mocapnet, 'Bone',
        bvh_rig=bvh_rig, keep_bvh=False)
    if not act_final:
        raise RuntimeError("KBS pass 2 produced no action")

    _apply_fcurve_data(act_final, spine_data)
    print(f"[Animation]   merged spine from 'Pose' into 'Bone' action")

    # Remove KBS intermediate bones left from pass 2
    if context.object and context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    extra_bones = [eb.name for eb in rig.data.edit_bones
                   if eb.name not in orig_bones]
    for name in extra_bones:
        eb = rig.data.edit_bones.get(name)
        if eb:
            rig.data.edit_bones.remove(eb)
    bpy.ops.object.mode_set(mode='OBJECT')
    if extra_bones:
        print(f"[Animation]   removed {len(extra_bones)} KBS intermediate bones")

    # Zero out spurious location fcurves on FK bones.
    _KEEP_LOCATION = {"root", "torso"}
    zeroed = 0
    for fc in _get_action_fcurves(act_final):
        if not fc.data_path.endswith('.location'):
            continue
        if 'pose.bones["' not in fc.data_path:
            continue
        bname = fc.data_path.split('pose.bones["')[1].split('"]')[0]
        if bname not in _KEEP_LOCATION:
            for kp in fc.keyframe_points:
                kp.co[1] = 0.0
                kp.handle_left[1] = 0.0
                kp.handle_right[1] = 0.0
            fc.update()
            zeroed += 1
    if zeroed:
        print(f"[Animation]   zeroed {zeroed} spurious location fcurves")

    # Zero out head/shoulder rotation
    _ZERO_ROTATION_BONES = {"head", "shoulder.L", "shoulder.R"}
    rot_zeroed = 0
    for fc in _get_action_fcurves(act_final):
        if 'pose.bones["' not in fc.data_path:
            continue
        bname = fc.data_path.split('pose.bones["')[1].split('"]')[0]
        if bname not in _ZERO_ROTATION_BONES:
            continue
        if 'rotation_quaternion' in fc.data_path:
            identity_val = 1.0 if fc.array_index == 0 else 0.0
            for kp in fc.keyframe_points:
                kp.co[1] = identity_val
                kp.handle_left[1] = identity_val
                kp.handle_right[1] = identity_val
            fc.update()
            rot_zeroed += 1
        elif 'rotation_euler' in fc.data_path:
            for kp in fc.keyframe_points:
                kp.co[1] = 0.0
                kp.handle_left[1] = 0.0
                kp.handle_right[1] = 0.0
            fc.update()
            rot_zeroed += 1
    if rot_zeroed:
        print(f"[Animation]   zeroed {rot_zeroed} head/shoulder rotation fcurves")

    _set_fk_mode(rig)
    _transfer_root_motion(rig)

    act = rig.animation_data.action if rig.animation_data else None
    if not act:
        raise RuntimeError("KBS Extension retarget produced no action")

    print(f"[Animation] KBS Extension complete: {act.name}, "
          f"{len(_get_action_fcurves(act))} fcurves")
    return act, f_start, f_end


def retarget_rokoko(context, rig, bvh_path):
    """Retarget BVH: v0.46 spine/legs per-frame + arms via COPY_ROTATION constraints + nla.bake().

    Spine + legs + root: conjugation + aim correction per-frame.
    Arms: COPY_ROTATION constraints (WORLD space) on BVH bones → nla.bake() (C++ solver).

    Returns (action, f_start, f_end).
    """
    import time as _time
    t0 = _time.time()

    # 1. Import BVH, scale to match
    bvh_rig, f_start, f_end = _import_bvh_armature(context, bvh_path)
    if not bvh_rig:
        raise RuntimeError("BVH import produced no armature")
    is_mocapnet = 'hip' in bvh_rig.data.bones
    is_v4 = is_mocapnet and '__jaw' in bvh_rig.data.bones
    if is_mocapnet:
        _normalize_openpose_bones(context, bvh_rig)
    bone_map = dict(_ROKOKO_MAP_MOCAPNET) if is_mocapnet else dict(_ROKOKO_MAP_CMU)
    if is_v4:
        bone_map.update(_V4_FINGER_MAP)
    fmt = "MocapNET v4" if is_v4 else ("MocapNET" if is_mocapnet else "CMU")
    print(f"[Animation] Rokoko TEST retarget ({fmt}): constraints for arms...")

    _scale_to_match(bvh_rig, rig)
    _set_fk_mode(rig)
    context.view_layer.update()

    if context.object and context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    bvh_mw = bvh_rig.matrix_world.copy()
    rig_mw = rig.matrix_world.copy()

    # 2. Classify bones
    CONJ_SET = {"torso", "spine_fk.001", "spine_fk.002", "spine_fk.003",
                "neck",
                "thigh_fk.L", "thigh_fk.R", "shin_fk.L", "shin_fk.R",
                "foot_fk.L", "foot_fk.R"}
    SKIP_BONES = {"head", "shoulder.L", "shoulder.R"}
    _ARM_BONES = {"upper_arm_fk.L", "upper_arm_fk.R",
                  "forearm_fk.L", "forearm_fk.R",
                  "hand_fk.L", "hand_fk.R"}
    _CONSTRAINT_BONES = set(_ARM_BONES)
    if is_v4:
        _CONSTRAINT_BONES.update(set(_V4_FINGER_MAP.values()))

    conj_pairs = []
    tgt_to_src = {}

    for src_name, tgt_name in bone_map.items():
        src_bone = bvh_rig.data.bones.get(src_name)
        tgt_bone = rig.data.bones.get(tgt_name)
        if not src_bone or not tgt_bone:
            continue
        if tgt_name not in ("shoulder.L", "shoulder.R"):
            tgt_to_src[tgt_name] = src_name
        if tgt_name in CONJ_SET:
            src_rest_q = (bvh_mw @ src_bone.matrix_local).to_quaternion()
            tgt_rest_q = (rig_mw @ tgt_bone.matrix_local).to_quaternion()
            M = tgt_rest_q.inverted() @ src_rest_q
            conj_pairs.append((src_name, tgt_name, M))

    # Aim correction levels (legs only)
    _AIM_LEVELS = [
        ["thigh_fk.L", "thigh_fk.R"],
        ["shin_fk.L", "shin_fk.R"],
        ["foot_fk.L", "foot_fk.R"],
    ]
    aim_levels = []
    for names in _AIM_LEVELS:
        level = [(tgt_to_src[n], n) for n in names if n in tgt_to_src]
        if level:
            aim_levels.append(level)

    hips_src = tgt_to_src.get("torso")
    hips_rest_world = None
    if hips_src:
        hips_bone = bvh_rig.data.bones.get(hips_src)
        if hips_bone:
            hips_rest_world = (bvh_mw @ hips_bone.matrix_local).to_translation()

    # 3. Setup COPY_ROTATION constraints for arm + finger bones
    arm_constraints = []
    for tgt_name in _CONSTRAINT_BONES:
        src_name = tgt_to_src.get(tgt_name)
        if not src_name:
            continue
        pb_tgt = rig.pose.bones.get(tgt_name)
        pb_src = bvh_rig.pose.bones.get(src_name)
        if not pb_tgt or not pb_src:
            continue
        c = pb_tgt.constraints.new('COPY_ROTATION')
        c.name = "_rt_arm_test"
        c.target = bvh_rig
        c.subtarget = src_name
        c.target_space = 'WORLD'
        c.owner_space = 'WORLD'
        c.influence = 1.0
        arm_constraints.append((tgt_name, c.name))

    n_arm = sum(1 for t, _ in arm_constraints if t in _ARM_BONES)
    n_finger = len(arm_constraints) - n_arm
    print(f"[Animation]   {n_arm} arm + {n_finger} finger COPY_ROTATION constraints added")

    # 4. Create action + per-frame processing for spine/legs/root
    stem = os.path.splitext(os.path.basename(bvh_path))[0]
    act = bpy.data.actions.new(name=f"RokokoTest_{stem}")
    if not rig.animation_data:
        rig.animation_data_create()
    rig.animation_data.action = act

    perframe_tgt_bones = [t for _, t, _ in conj_pairs] + list(SKIP_BONES)

    t1 = _time.time()
    for frame in range(f_start, f_end + 1):
        context.scene.frame_set(frame)

        # Conjugation for torso + legs
        for src_name, tgt_name, M in conj_pairs:
            pb_src = bvh_rig.pose.bones.get(src_name)
            pb_tgt = rig.pose.bones.get(tgt_name)
            if not pb_src or not pb_tgt:
                continue
            src_q = pb_src.matrix_basis.to_quaternion()
            pb_tgt.rotation_quaternion = M @ src_q @ M.inverted()

        # v4: dampen + redistribute hip lean across the spine chain
        if is_v4:
            _pb_t = rig.pose.bones.get("torso")
            if _pb_t:
                _e = _pb_t.rotation_quaternion.to_euler('XYZ')
                _x_lean = _e.x * 0.5
                _e.x = _x_lean * 0.35
                _pb_t.rotation_quaternion = _e.to_quaternion()
                for _sn, _sf in [("spine_fk.001", 0.25),
                                  ("spine_fk.002", 0.20),
                                  ("spine_fk.003", 0.20)]:
                    _pb = rig.pose.bones.get(_sn)
                    if _pb:
                        _pb.rotation_quaternion = Quaternion((1, 0, 0), _x_lean * _sf)

        # Root location
        pb_root = rig.pose.bones.get("root")
        if hips_src and pb_root and hips_rest_world is not None:
            pb_hips = bvh_rig.pose.bones.get(hips_src)
            if pb_hips:
                hips_cur_world = (bvh_mw @ pb_hips.matrix).to_translation()
                delta = hips_cur_world - hips_rest_world
                delta_armature = rig_mw.inverted().to_3x3() @ delta
                pb_root.location = delta_armature

        context.view_layer.update()

        # Aim correction for legs
        for lvl_i in range(len(aim_levels)):
            for src_name, tgt_name in aim_levels[lvl_i]:
                pb_src = bvh_rig.pose.bones.get(src_name)
                pb_tgt = rig.pose.bones.get(tgt_name)
                if not pb_src or not pb_tgt:
                    continue
                src_y = (bvh_mw @ pb_src.matrix).to_3x3() @ Vector((0, 1, 0))
                tgt_y = (rig_mw @ pb_tgt.matrix).to_3x3() @ Vector((0, 1, 0))
                aim_q = tgt_y.rotation_difference(src_y)
                current_world = (rig_mw @ pb_tgt.matrix).to_3x3()
                corrected = aim_q.to_matrix() @ current_world
                desired = corrected.to_4x4()
                local = rig.convert_space(
                    pose_bone=pb_tgt, matrix=desired,
                    from_space='WORLD', to_space='LOCAL')
                pb_tgt.rotation_quaternion = local.to_quaternion()
            context.view_layer.update()

        # Keyframe spine/legs/skip (NOT arms — those come from bake)
        for tgt_name in perframe_tgt_bones:
            pb = rig.pose.bones.get(tgt_name)
            if not pb:
                continue
            if tgt_name in SKIP_BONES:
                pb.rotation_quaternion = Quaternion()
            pb.keyframe_insert(data_path="rotation_quaternion", frame=frame)
        if pb_root:
            pb_root.keyframe_insert(data_path="location", frame=frame)

    t2 = _time.time()
    print(f"[Animation]   per-frame spine/legs done in {t2 - t1:.1f}s")

    # 5. Bake arm constraints via nla.bake() (C++ solver)
    context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='POSE')

    print(f"[Animation]   baking {len(arm_constraints)} arm bones via nla.bake()...")
    t3 = _time.time()
    bpy.ops.nla.bake(
        frame_start=f_start,
        frame_end=f_end,
        only_selected=False,
        visual_keying=True,
        clear_constraints=False,
        bake_types={'POSE'},
    )
    t4 = _time.time()
    print(f"[Animation]   nla.bake() arms done in {t4 - t3:.1f}s")

    bpy.ops.object.mode_set(mode='OBJECT')

    # 6. Remove arm constraints
    for tgt_name, c_name in arm_constraints:
        pb = rig.pose.bones.get(tgt_name)
        if pb:
            c = pb.constraints.get(c_name)
            if c:
                pb.constraints.remove(c)

    # 7. Cleanup BVH rig
    if bvh_rig and bvh_rig.name in bpy.data.objects:
        bpy.data.objects.remove(bvh_rig, do_unlink=True)

    # 8. Post-process
    _set_fk_mode(rig)

    act = rig.animation_data.action if rig.animation_data else None
    if not act:
        raise RuntimeError("Rokoko TEST retarget produced no action")

    dt = _time.time() - t0
    print(f"[Animation] Rokoko TEST complete in {dt:.1f}s "
          f"(per-frame {t2 - t1:.1f}s + bake {t4 - t3:.1f}s): "
          f"{act.name}, {len(_get_action_fcurves(act))} fcurves")
    return act, f_start, f_end
