# SPDX-License-Identifier: GPL-3.0-or-later
#
# BVH motion capture retargeting for HumanBody addon.
# Extracted from animation.py — retarget_rokoko, retarget_kbs + helpers.

import os
import logging

import bpy
from mathutils import Quaternion, Vector

from .rigaktionen import _set_fk_mode, _get_action_fcurves

# Die Bauteile liegen in `retarget_teile/`. Hier bleibt, was Blender
# sieht: die Klassen und die Anmeldung.
from .retarget_teile.bvhimport import (
    _import_bvh_armature, _normalize_openpose_bones, _scale_to_match,
)
from .retarget_teile.knochenlisten import _ROKOKO_MAP_CMU, _ROKOKO_MAP_MOCAPNET, _V4_FINGER_MAP

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# BVH bone sets (for filtering)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Retarget mapping tables: BVH bone → Rigify FK bone
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# KBS helpers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# BVH import + bone utilities
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Main retarget functions
# ---------------------------------------------------------------------------


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
    logger.info("Rokoko TEST retarget (%s): constraints for arms...", fmt)

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
    logger.info("%s arm + %s finger COPY_ROTATION constraints added",
                n_arm, n_finger)

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
    logger.info("  per-frame spine/legs done in %.1fs", t2 - t1)

    # 5. Bake arm constraints via nla.bake() (C++ solver)
    context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='POSE')

    logger.info("baking %s arm bones via nla.bake()...", len(arm_constraints))
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
    logger.info("  nla.bake() arms done in %.1fs", t4 - t3)

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
    logger.info("Rokoko TEST complete in %.1fs (per-frame %.1fs + bake "
                "%.1fs): %s, %d fcurves", dt, t2 - t1, t4 - t3,
                act.name, len(_get_action_fcurves(act)))
    return act, f_start, f_end
