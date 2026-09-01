# -*- coding: utf-8 -*-
import logging
import bpy
from mathutils import Quaternion, Vector
from ..rigaktionen import (
    _parse_bvh_info, _set_fk_mode, _get_action_fcurves, _transfer_root_motion,
)
logger = logging.getLogger(__name__)
from .knochenlisten import _SPINE_MERGE_BONES
from .fcurves import _apply_fcurve_data
from .fcurves import _extract_fcurve_data
from .bvhimport import _filter_bvh_bones
from .bvhimport import _import_bvh_armature
from .bvhimport import _normalize_openpose_bones
from .bvhimport import _scale_to_match


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
        # stumm gewollt: Aufraeumen im finally: in den Objektmodus zurueck.
        # Steht kein Objekt bereit, ist nichts umzuschalten.
        except Exception:
            pass
        if not keep_bvh and bvh_rig and bvh_rig.name in bpy.data.objects:
            bpy.data.objects.remove(bvh_rig, do_unlink=True)

    act = rig.animation_data.action if rig.animation_data else None
    return act, f_start, f_end


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
    logger.info("KBS %s: single BVH import, filtering bones...", fmt)

    _filter_bvh_bones(context, bvh_rig, is_mocapnet)
    _scale_to_match(bvh_rig, rig)

    if context.object and context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    orig_bones = set(b.name for b in rig.data.bones)

    # --- Pass 1: match_transform='Pose' → correct spine ---
    logger.info("KBS %s pass 1/2: spine (match_transform='Pose')", fmt)
    act_spine, f_start, f_end = _kbs_run_pass(
        context, rig, bvh_path, is_mocapnet, 'Pose',
        bvh_rig=bvh_rig, keep_bvh=True)
    if not act_spine:
        raise RuntimeError("KBS pass 1 produced no action")
    spine_data = _extract_fcurve_data(act_spine, _SPINE_MERGE_BONES)
    logger.info("saved %s spine fcurves", len(spine_data))

    _reset_rig_for_kbs(context, rig, orig_bones)

    # --- Pass 2: match_transform='Bone' → correct arms/legs ---
    logger.info("KBS %s pass 2/2: limbs (match_transform='Bone')", fmt)
    act_final, f_start, f_end = _kbs_run_pass(
        context, rig, bvh_path, is_mocapnet, 'Bone',
        bvh_rig=bvh_rig, keep_bvh=False)
    if not act_final:
        raise RuntimeError("KBS pass 2 produced no action")

    _apply_fcurve_data(act_final, spine_data)
    logger.info("merged spine from 'Pose' into 'Bone' action")

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
        logger.info("removed %s KBS intermediate bones", len(extra_bones))

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
        logger.info("zeroed %s spurious location fcurves", zeroed)

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
        logger.info("zeroed %s head/shoulder rotation fcurves", rot_zeroed)

    _set_fk_mode(rig)
    _transfer_root_motion(rig)

    act = rig.animation_data.action if rig.animation_data else None
    if not act:
        raise RuntimeError("KBS Extension retarget produced no action")

    logger.info("KBS Extension complete: %s, %s fcurves",
                act.name, len(_get_action_fcurves(act)))
    return act, f_start, f_end
