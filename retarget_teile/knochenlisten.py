# -*- coding: utf-8 -*-
import logging
logger = logging.getLogger(__name__)


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


# Spine bones whose fcurves are taken from the 'Pose' pass (correct spine).
_SPINE_MERGE_BONES = {
    "torso", "spine_fk.001", "spine_fk.002", "spine_fk.003", "neck", "head",
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
