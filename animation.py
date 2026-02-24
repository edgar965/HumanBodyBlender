# SPDX-License-Identifier: GPL-3.0-or-later
#
# Animation system for HumanBody addon.
# BVH motion capture retargeting, procedural animations, and animation catalog.

import math
import os
import logging

import bpy
from mathutils import Quaternion, Euler, Vector

from .rig import _find_rig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# BVH animations live in HumanBody/data (core data repo)
_TOOLS_ROOT = os.path.dirname(os.path.dirname(__file__))
_HUMANBODY_ROOT = os.path.join(_TOOLS_ROOT, "HumanBody")
if not os.path.isdir(_HUMANBODY_ROOT):
    _HUMANBODY_ROOT = r"A:\3DTools\HumanBody"
_BVH_DIR = os.path.join(_HUMANBODY_ROOT, "data", "animations", "bvh")

# Animation catalog: file_stem -> description
# Order within each category section defines display order in UI.
_BVH_CATALOG = {
    # MocapNET
    "test_Mocapv4": "MocapNET v4 Test (shuffle dance, Full Body)",
    "testOpenPose": "MocapNET Test (shuffle dance, OpenPose)",
    "testMediaPipe": "MocapNET Test (shuffle dance, MediaPipe)",
    "mocapnet_sample": "CMU Sample (164 joints)",
    "mocapnet_tpose": "T-Pose",
    "mocapnet_help": "Help Gesture",
    "mocapnet_push": "Push Gesture",
    "mocapnet_doubleclap": "Double Clap",
    "mocapnet_handsup": "Hands Up",
    "mocapnet_leftkick": "Left Kick",
    "mocapnet_rightkick": "Right Kick",
    "mocapnet_waveleft": "Wave Left",
    "mocapnet_waveright": "Wave Right",
    "mocapnet_lefthandcircle": "Left Hand Circle",
    "mocapnet_righthandcircle": "Right Hand Circle",
    # Walk
    "walk_short": "Walk (short)",
    "01_01": "playground - forward jumps, turn around",
    "05_01": "walk",
    "02_02": "walk",
    "03_01": "walk on uneven terrain",
    "133_14": "Walk Left",
    "133_17": "Walk Right",
    "133_07": "Walk Jump",
    "133_24": "Walk ZigZag",
    "136_12": "Walk Backwards Crouched",
    "136_28": "Walk on Toes",
    "141_29": "Random Walk",
    "139_12": "Run in Circles",
    "137_37": "Sexy Lady Wait",
    "01_04": "playground - climb",
    "01_13": "playground - climb, go under, jump down",
    "01_14": "playground - climb, jump down, dangle, legs push off against",
    "13_26": "direct traffic, wave",
    "13_27": "direct traffic, wave, point",
    "13_28": "direct traffic, wave, point",
    # Sport
    "02_07": "swordplay",
    "02_03": "run/jog",
    "02_04": "jump, balance",
    "02_05": "punch/strike",
    "02_06": "bend over, scoop up, rise, lift arm",
    "02_08": "swordplay",
    "02_10": "wash self",
    "03_02": "walk on uneven terrain",
    "03_03": "walk on uneven terrain",
    "03_04": "walk on uneven terrain",
    "13_13": "forward jump",
    # Dance
    "64_01": "Swing",
    "61_01": "salsa dance",
    "61_02": "salsa dance",
    "05_02": "expressive arms, pirouette",
    "05_03": "sideways arabesque, turn step, folding arms",
    "05_04": "sideways arabesque, folding arms, bending back",
    "05_05": "cou-de-pied, raised leg, jete en tourant",
    "05_06": "cartwheel-like, pirouettes, jete",
    "05_07": "small jetes, attitude, pirouette, turn",
    "05_08": "rond de jambe, jete, turn",
    "05_09": "glissade devant, derriere, arabesque",
    "05_10": "glissade devant, derriere, arabesque",
    "05_11": "sideways steps, pirouette",
    "05_12": "arms high, pointe tendue, rotation",
    "05_13": "small jetes, pirouette",
    "05_14": "retire derriere, arabesque",
    "05_15": "retire derriere, arabesque",
    "05_16": "coupe dessous, jete en tourant",
    "05_17": "coupe dessous, grand jete en tourant",
    "05_18": "arabesque, jete en tourant, bending back",
    "05_19": "arabesque, jete en tourant, bending back",
    "05_20": "arabesque, jete en tourant, bending back",
    # Home
    "13_07": "unscrew bottlecap, drink soda",
    "13_14": "laugh",
    "13_15": "laugh",
    "13_16": "laugh",
    "13_17": "boxing",
    "13_18": "boxing",
    "13_19": "forward jump",
    "13_20": "wash windows",
    "13_21": "wash windows",
    "13_22": "wash windows",
    "13_23": "sweep floor",
    "13_24": "sweep floor",
    "13_25": "sweep floor",
    "13_08": "unscrew bottlecap, drink soda, screw on bottlecap",
    "13_09": "drink soda",
    "13_10": "jump up to grab, reach for, tiptoe",
    "13_11": "forward jump",
    "13_12": "jump up to grab, reach for, tiptoe",
    "14_10": "wash windows",
    "14_11": "wash windows",
    "14_12": "wash windows",
    "14_13": "mop floor",
    "14_14": "jumping jacks, jog, squats, side twists, stretches",
    "14_15": "mop floor",
    "14_16": "sweep floor",
}

_ANIM_CATEGORIES = [
    ("MocapNET", 'OUTLINER_OB_ARMATURE'),
    ("Walk",  'ANIM_DATA'),
    ("Sport", 'POSE_HLT'),
    ("Dance", 'OUTLINER_OB_CURVES'),
    ("Home",  'HOME'),
]

# Prefix for procedural animation paths (not real files)
_PROC_PREFIX = "@proc:"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_bvh_info(bvh_path):
    """Read Frames count and Frame Time from BVH header.

    Returns (fps, n_frames).
    """
    n_frames = 0
    fps = 120
    with open(bvh_path, 'r') as f:
        for line in f:
            stripped = line.strip()
            if stripped.startswith('Frames:'):
                n_frames = int(stripped.split(':')[1])
            elif 'Frame Time' in stripped:
                parts = stripped.split(':')
                if len(parts) >= 2:
                    ft = float(parts[1].strip())
                    if ft > 0:
                        fps = round(1.0 / ft)
                break
    return fps, n_frames


def _rig_height(rig):
    """Height of armature (rest pose) from lowest to highest bone endpoint."""
    bones = rig.data.bones
    if not bones:
        return 1.7
    zs = []
    for b in bones:
        zs.append(b.head_local.z)
        zs.append(b.tail_local.z)
    return max(zs) - min(zs) if zs else 1.7


def _deg(x, y, z):
    """Euler degrees in bone-local space -> Quaternion.

    For spine/head/neck bones (local axes ~ world axes):
      X rotation: +lean_back / -lean_forward
      Y rotation: +turn_right / -turn_left
      Z rotation: +tilt_left  / -tilt_right

    For thigh/shin (local X ~ world right):
      +X = hip/knee flexion (leg forward / knee bend)
      -X = extension

    For forearm (local X ~ vertical):
      -X = elbow flexion (bend)
      +X = elbow extension
    """
    return Euler((math.radians(x), math.radians(y), math.radians(z))).to_quaternion()


def _wrot(pb, *axis_angle_pairs):
    """World-space rotation(s) -> bone rotation_quaternion.

    Each pair is ((wx, wy, wz), angle_deg).  Applied in order.

    World axes: X = right, Y = forward, Z = up.
    """
    world_rot = Quaternion((1, 0, 0, 0))
    for axis, angle in axis_angle_pairs:
        world_rot = Quaternion(Vector(axis), math.radians(angle)) @ world_rot
    rest_q = pb.bone.matrix_local.to_3x3().to_quaternion()
    return rest_q.conjugated() @ world_rot @ rest_q


def _kf(bone, frame):
    """Insert rotation_quaternion keyframe on *bone* at *frame*."""
    bone.keyframe_insert(data_path="rotation_quaternion", frame=frame)


def _kf_loc(bone, frame):
    """Insert location keyframe on *bone* at *frame*."""
    bone.keyframe_insert(data_path="location", frame=frame)


def _pb(rig, name):
    """Get pose bone by name, or None."""
    return rig.pose.bones.get(name)


def _set_fk_mode(rig):
    """Set IK/FK switches to 1.0 (FK mode) on Rigify rig."""
    count = 0
    for pb in rig.pose.bones:
        for key in list(pb.keys()):
            kl = key.lower()
            if 'ik_fk' in kl or 'fk_ik' in kl or key == 'IK_FK':
                try:
                    pb[key] = 1.0
                    count += 1
                except Exception:
                    pass
    print(f"[Animation] FK mode: {count} IK/FK switches set")
    return count


def _transfer_root_motion(rig):
    """Move torso location keyframes to root bone, zero torso location."""
    ad = rig.animation_data
    if not ad or not ad.action:
        return
    act = ad.action
    try:
        fcs = act.fcurves
        new_fc = act.fcurves.new
    except Exception:
        try:
            layer = act.layers[0]
            strip = layer.strips[0]
            slot = ad.action_slot
            cb = strip.channelbag(slot)
            fcs = cb.fcurves
            new_fc = cb.fcurves.new
        except Exception:
            return
    torso_loc = {}
    root_loc = {}
    for fc in fcs:
        if 'pose.bones["torso"]' in fc.data_path and fc.data_path.endswith('location'):
            torso_loc[fc.array_index] = fc
        if 'pose.bones["root"]' in fc.data_path and fc.data_path.endswith('location'):
            root_loc[fc.array_index] = fc
    if not torso_loc or root_loc:
        return
    for axis in range(3):
        src = torso_loc.get(axis)
        if not src:
            continue
        dst = new_fc(data_path='pose.bones["root"].location', index=axis)
        for kp in src.keyframe_points:
            dst.keyframe_points.insert(kp.co[0], kp.co[1])
        for kp in src.keyframe_points:
            kp.co[1] = 0.0
            kp.handle_left[1] = 0.0
            kp.handle_right[1] = 0.0
    print(f"[Animation] Root motion transferred torso -> root ({len(torso_loc)} axes)")


# ---------------------------------------------------------------------------
# Procedural Animation Generators
#
# Bone axis reference (from Rigify diagnostic):
#   Spine/Head/Neck:  local X=right, Y=up, Z=backward
#   Thigh/Shin:       local X=right, Y=down(bone), Z=forward
#   Upper arm:        complex axes -> use _wrot() for world-space rotations
#   Forearm:          local X ~ vertical -> _deg(-angle,0,0) = elbow flex
#   Foot:             local X=right, Y=backward+down, Z=down
# ---------------------------------------------------------------------------

def _gen_idle(rig):
    """Idle: subtle breathing + weight shift (120 frames, loopable)."""
    N = 120
    spine1 = _pb(rig, 'spine_fk.001')
    spine3 = _pb(rig, 'spine_fk.003')
    head = _pb(rig, 'head')

    for f in range(N + 1):
        t = f / N * 2.0 * math.pi
        # Breathing: slight forward lean on exhale
        breath = math.sin(t) * 1.5
        # Slow side sway (half frequency)
        sway = math.sin(t * 0.5) * 0.8

        if spine1:
            # -X = lean forward (exhale), +Z = tilt left
            spine1.rotation_quaternion = _deg(-breath, 0, sway)
            _kf(spine1, f)
        if spine3:
            spine3.rotation_quaternion = _deg(-breath * 0.5, 0, sway * 0.3)
            _kf(spine3, f)
        if head:
            # Compensate: slight back lean, tilt opposite to body sway
            head.rotation_quaternion = _deg(breath * 0.3, 0, -sway * 0.4)
            _kf(head, f)

    return 0, N


def _gen_wave(rig):
    """Wave right hand (90 frames)."""
    N = 90
    upper_r = _pb(rig, 'upper_arm_fk.R')
    fore_r = _pb(rig, 'forearm_fk.R')
    hand_r = _pb(rig, 'hand_fk.R')

    for f in range(N + 1):
        t = f / N
        wave = 0

        if t < 0.33:
            # Raise arm
            s = t / 0.33
            raise_angle = s * 140
            fore_flex = s * 100
        elif t < 0.78:
            # Hold + wave hand
            raise_angle = 140
            fore_flex = 100
            s = (t - 0.33) / 0.45
            wave = math.sin(s * 4 * math.pi) * 25
        else:
            # Lower arm
            s = (t - 0.78) / 0.22
            raise_angle = 140 * (1 - s)
            fore_flex = 100 * (1 - s)

        if upper_r:
            # Raise right arm: -Y rotation (lateral raise for R side)
            # Plus slight forward angle: -Z rotation (forward for R side)
            upper_r.rotation_quaternion = _wrot(upper_r,
                ((0, 1, 0), -raise_angle),
                ((0, 0, 1), -15),
            )
            _kf(upper_r, f)
        if fore_r:
            # Elbow flexion: -X in bone local space
            fore_r.rotation_quaternion = _deg(-fore_flex, 0, 0)
            _kf(fore_r, f)
        if hand_r:
            # Wrist wave: small Y rotation (turn) in bone local
            hand_r.rotation_quaternion = _deg(0, wave, 0)
            _kf(hand_r, f)

    return 0, N


def _gen_nod_yes(rig):
    """Head nods yes (80 frames, loopable)."""
    N = 80
    head = _pb(rig, 'head')
    neck = _pb(rig, 'neck')
    if not head:
        return 0, N

    for f in range(N + 1):
        t = f / N
        # Nod: oscillate forward (-X) and back (+X)
        nod = math.sin(t * 3 * 2 * math.pi) * 12
        head.rotation_quaternion = _deg(nod, 0, 0)
        _kf(head, f)
        if neck:
            neck.rotation_quaternion = _deg(nod * 0.3, 0, 0)
            _kf(neck, f)

    return 0, N


def _gen_shake_no(rig):
    """Head shakes no (80 frames, loopable)."""
    N = 80
    head = _pb(rig, 'head')
    neck = _pb(rig, 'neck')
    if not head:
        return 0, N

    for f in range(N + 1):
        t = f / N
        # Turn head left/right: Y rotation (+Y = turn right, -Y = turn left)
        shake = math.sin(t * 3 * 2 * math.pi) * 18
        head.rotation_quaternion = _deg(0, shake, 0)
        _kf(head, f)
        if neck:
            neck.rotation_quaternion = _deg(0, shake * 0.2, 0)
            _kf(neck, f)

    return 0, N


def _gen_look_around(rig):
    """Look left, right, up, center (160 frames)."""
    N = 160
    head = _pb(rig, 'head')
    neck = _pb(rig, 'neck')
    if not head:
        return 0, N

    # (frame, pitch_X, yaw_Y)
    # +X = lean back (look up), -X = lean forward (look down)
    # +Y = turn right, -Y = turn left
    keyframes = [
        (0,    0,   0),     # center
        (30,   0,  -30),    # look left (-Y)
        (55,   0,  -30),    # hold
        (80,   0,   30),    # look right (+Y)
        (105,  0,   30),    # hold
        (125,  12,   0),    # look up (+X)
        (140, -10,   0),    # look down (-X)
        (160,  0,   0),     # center
    ]

    for frame, pitch, yaw in keyframes:
        head.rotation_quaternion = _deg(pitch, yaw, 0)
        _kf(head, frame)
        if neck:
            neck.rotation_quaternion = _deg(pitch * 0.3, yaw * 0.3, 0)
            _kf(neck, frame)

    return 0, N


def _gen_stretch(rig):
    """Arms stretch up and back down (120 frames)."""
    N = 120
    upper_l = _pb(rig, 'upper_arm_fk.L')
    upper_r = _pb(rig, 'upper_arm_fk.R')
    fore_l = _pb(rig, 'forearm_fk.L')
    fore_r = _pb(rig, 'forearm_fk.R')
    spine1 = _pb(rig, 'spine_fk.001')
    spine3 = _pb(rig, 'spine_fk.003')

    for f in range(N + 1):
        t = f / N
        if t < 0.35:
            s = t / 0.35
            raise_angle = s * 170
            back_lean = s * 8
        elif t < 0.65:
            raise_angle = 170
            back_lean = 8
        else:
            s = (t - 0.65) / 0.35
            raise_angle = 170 * (1 - s)
            back_lean = 8 * (1 - s)

        # Raise both arms: +Y for L, -Y for R (lateral raise)
        if upper_l:
            upper_l.rotation_quaternion = _wrot(upper_l, ((0, 1, 0), raise_angle))
            _kf(upper_l, f)
        if upper_r:
            upper_r.rotation_quaternion = _wrot(upper_r, ((0, 1, 0), -raise_angle))
            _kf(upper_r, f)
        # Keep forearms straight
        if fore_l:
            fore_l.rotation_quaternion = Quaternion((1, 0, 0, 0))
            _kf(fore_l, f)
        if fore_r:
            fore_r.rotation_quaternion = Quaternion((1, 0, 0, 0))
            _kf(fore_r, f)
        # Slight back lean (+X = lean back)
        if spine1:
            spine1.rotation_quaternion = _deg(back_lean, 0, 0)
            _kf(spine1, f)
        if spine3:
            spine3.rotation_quaternion = _deg(back_lean * 0.6, 0, 0)
            _kf(spine3, f)

    return 0, N


def _gen_greeting(rig):
    """Small bow greeting (80 frames)."""
    N = 80
    spine1 = _pb(rig, 'spine_fk.001')
    spine3 = _pb(rig, 'spine_fk.003')
    head = _pb(rig, 'head')
    neck = _pb(rig, 'neck')

    for f in range(N + 1):
        t = f / N
        if t < 0.3:
            s = t / 0.3
            bow = s * 20
        elif t < 0.5:
            bow = 20
        else:
            s = (t - 0.5) / 0.5
            bow = 20 * (1 - s)

        # Bow forward: -X = lean forward
        if spine1:
            spine1.rotation_quaternion = _deg(-bow, 0, 0)
            _kf(spine1, f)
        if spine3:
            spine3.rotation_quaternion = _deg(-bow * 0.6, 0, 0)
            _kf(spine3, f)
        if head:
            head.rotation_quaternion = _deg(-bow * 0.4, 0, 0)
            _kf(head, f)
        if neck:
            neck.rotation_quaternion = _deg(-bow * 0.3, 0, 0)
            _kf(neck, f)

    return 0, N


def _gen_hands_on_hips(rig):
    """Hands on hips pose transition (60 frames, holds)."""
    N = 60
    upper_l = _pb(rig, 'upper_arm_fk.L')
    upper_r = _pb(rig, 'upper_arm_fk.R')
    fore_l = _pb(rig, 'forearm_fk.L')
    fore_r = _pb(rig, 'forearm_fk.R')

    for f in range(N + 1):
        t = f / N
        s = min(t / 0.3, 1.0)

        # Arms slightly out to the sides and backward
        if upper_l:
            upper_l.rotation_quaternion = _wrot(upper_l,
                ((0, 1, 0), 35 * s),    # raise L arm out (+Y)
                ((0, 0, 1), -20 * s),   # swing backward (-Z for L)
            )
            _kf(upper_l, f)
        if upper_r:
            upper_r.rotation_quaternion = _wrot(upper_r,
                ((0, 1, 0), -35 * s),   # raise R arm out (-Y)
                ((0, 0, 1), 20 * s),    # swing backward (+Z for R)
            )
            _kf(upper_r, f)
        # Elbows bent sharply
        if fore_l:
            fore_l.rotation_quaternion = _deg(-110 * s, 0, 0)
            _kf(fore_l, f)
        if fore_r:
            fore_r.rotation_quaternion = _deg(-110 * s, 0, 0)
            _kf(fore_r, f)

    return 0, N


def _gen_clap(rig):
    """Clapping (100 frames, loopable)."""
    N = 100
    upper_l = _pb(rig, 'upper_arm_fk.L')
    upper_r = _pb(rig, 'upper_arm_fk.R')
    fore_l = _pb(rig, 'forearm_fk.L')
    fore_r = _pb(rig, 'forearm_fk.R')

    for f in range(N + 1):
        t = f / N
        clap = math.sin(t * 6 * 2 * math.pi)
        spread = max(0, clap) * 12  # hands apart when positive

        # Arms in front, slightly raised
        if upper_l:
            upper_l.rotation_quaternion = _wrot(upper_l,
                ((0, 0, 1), 50 - spread),   # forward swing (+Z for L)
                ((0, 1, 0), 15),             # slight lateral raise (+Y for L)
            )
            _kf(upper_l, f)
        if upper_r:
            upper_r.rotation_quaternion = _wrot(upper_r,
                ((0, 0, 1), -50 + spread),   # forward swing (-Z for R)
                ((0, 1, 0), -15),             # slight lateral raise (-Y for R)
            )
            _kf(upper_r, f)
        # Elbows bent
        if fore_l:
            fore_l.rotation_quaternion = _deg(-80, 0, 0)
            _kf(fore_l, f)
        if fore_r:
            fore_r.rotation_quaternion = _deg(-80, 0, 0)
            _kf(fore_r, f)

    return 0, N


def _gen_weight_shift(rig):
    """Weight shift side to side (120 frames, loopable)."""
    N = 120
    torso = _pb(rig, 'torso')
    spine1 = _pb(rig, 'spine_fk.001')
    head = _pb(rig, 'head')

    for f in range(N + 1):
        t = f / N * 2 * math.pi
        sway = math.sin(t) * 4

        if torso:
            torso.location = (math.sin(t) * 0.02, 0, 0)
            _kf_loc(torso, f)
        if spine1:
            # +Z = tilt left, -Z = tilt right
            spine1.rotation_quaternion = _deg(0, 0, sway)
            _kf(spine1, f)
        if head:
            # Compensate head tilt
            head.rotation_quaternion = _deg(0, 0, -sway * 0.5)
            _kf(head, f)

    return 0, N


# ---------------------------------------------------------------------------
# Walk & Run procedural animations
# ---------------------------------------------------------------------------

def _gen_walk(rig):
    """Walk cycle with root translation (120 frames = 2 full cycles)."""
    N = 120
    CYCLE = 60  # frames per cycle

    torso   = _pb(rig, 'torso')
    spine1  = _pb(rig, 'spine_fk.001')
    spine3  = _pb(rig, 'spine_fk.003')
    head    = _pb(rig, 'head')
    upper_l = _pb(rig, 'upper_arm_fk.L')
    upper_r = _pb(rig, 'upper_arm_fk.R')
    fore_l  = _pb(rig, 'forearm_fk.L')
    fore_r  = _pb(rig, 'forearm_fk.R')
    thigh_l = _pb(rig, 'thigh_fk.L')
    thigh_r = _pb(rig, 'thigh_fk.R')
    shin_l  = _pb(rig, 'shin_fk.L')
    shin_r  = _pb(rig, 'shin_fk.R')
    foot_l  = _pb(rig, 'foot_fk.L')
    foot_r  = _pb(rig, 'foot_fk.R')

    # Gait parameters
    STRIDE   = 0.55    # forward distance per cycle (meters)
    HIP_FLEX = 22.0    # hip flexion/extension amplitude (degrees)
    KNEE_MAX = 42.0    # max knee flexion during swing
    ARM_SWING = 16.0   # arm swing amplitude
    BODY_LEAN = 2.0    # lateral torso lean
    BOB       = 0.008  # vertical bounce (meters)
    SWAY      = 0.008  # lateral sway (meters)

    for f in range(N + 1):
        phase = (f % CYCLE) / CYCLE * 2 * math.pi
        # Character faces -Y.
        # _deg(+X) on thigh = foot moves to +Y = BACKWARD in char space.
        # _deg(-X) on thigh = foot moves to -Y = FORWARD in char space.
        # s = -sin(phase): when s < 0, hip_l < 0, L leg forward.
        s = -math.sin(phase)

        # --- Root motion (forward = -Y for this character) ---
        fwd = f * STRIDE / CYCLE
        bob = abs(math.sin(phase)) * BOB
        sway_x = math.sin(phase) * SWAY
        if torso:
            torso.location = (sway_x, -fwd, bob)
            _kf_loc(torso, f)

        # --- Torso ---
        if spine1:
            spine1.rotation_quaternion = _deg(
                0,
                s * 2.5,          # Y twist
                -s * BODY_LEAN,   # Z tilt
            )
            _kf(spine1, f)
        if spine3:
            spine3.rotation_quaternion = _deg(0, s * 1.5, 0)
            _kf(spine3, f)
        if head:
            head.rotation_quaternion = _deg(0, -s * 1.5, 0)
            _kf(head, f)

        # --- Legs ---
        hip_l = s * HIP_FLEX  # negative = L leg forward
        hip_r = -hip_l

        # +_deg on shin = knee FLEXION (bend). Bend during forward swing.
        # L leg forward when s < 0 → knee_l bends when -s > 0.
        knee_l = max(0, -s) * KNEE_MAX
        knee_r = max(0, s) * KNEE_MAX

        if thigh_l:
            thigh_l.rotation_quaternion = _deg(hip_l, 0, 0)
            _kf(thigh_l, f)
        if thigh_r:
            thigh_r.rotation_quaternion = _deg(hip_r, 0, 0)
            _kf(thigh_r, f)
        if shin_l:
            shin_l.rotation_quaternion = _deg(knee_l, 0, 0)
            _kf(shin_l, f)
        if shin_r:
            shin_r.rotation_quaternion = _deg(knee_r, 0, 0)
            _kf(shin_r, f)

        # Foot dorsiflexion during swing, plantarflexion at push-off
        foot_l_ang = math.sin(phase + 0.3) * 8
        foot_r_ang = math.sin(phase + math.pi + 0.3) * 8
        if foot_l:
            foot_l.rotation_quaternion = _deg(foot_l_ang, 0, 0)
            _kf(foot_l, f)
        if foot_r:
            foot_r.rotation_quaternion = _deg(foot_r_ang, 0, 0)
            _kf(foot_r, f)

        # --- Arms (cross-lateral counter-balance via Z + elbow pump) ---
        # arm_osc > 0 when L arm backward / R arm forward
        arm_osc = math.sin(phase)  # = -s
        z_arm = arm_osc * ARM_SWING
        if upper_l:
            upper_l.rotation_quaternion = _wrot(upper_l,
                ((0, 0, 1), z_arm))
            _kf(upper_l, f)
        if upper_r:
            upper_r.rotation_quaternion = _wrot(upper_r,
                ((0, 0, 1), z_arm))
            _kf(upper_r, f)
        # Elbow pump: +_deg on forearm = flexion (hand forward)
        elbow_base = 25
        elbow_osc = arm_osc * 15
        if fore_l:
            fore_l.rotation_quaternion = _deg(elbow_base - elbow_osc, 0, 0)
            _kf(fore_l, f)
        if fore_r:
            fore_r.rotation_quaternion = _deg(elbow_base + elbow_osc, 0, 0)
            _kf(fore_r, f)

    return 0, N


def _gen_run(rig):
    """Run cycle with root translation (100 frames = ~2.5 cycles)."""
    N = 100
    CYCLE = 40  # shorter cycle = faster pace

    torso   = _pb(rig, 'torso')
    spine1  = _pb(rig, 'spine_fk.001')
    spine3  = _pb(rig, 'spine_fk.003')
    head    = _pb(rig, 'head')
    upper_l = _pb(rig, 'upper_arm_fk.L')
    upper_r = _pb(rig, 'upper_arm_fk.R')
    fore_l  = _pb(rig, 'forearm_fk.L')
    fore_r  = _pb(rig, 'forearm_fk.R')
    thigh_l = _pb(rig, 'thigh_fk.L')
    thigh_r = _pb(rig, 'thigh_fk.R')
    shin_l  = _pb(rig, 'shin_fk.L')
    shin_r  = _pb(rig, 'shin_fk.R')
    foot_l  = _pb(rig, 'foot_fk.L')
    foot_r  = _pb(rig, 'foot_fk.R')

    STRIDE    = 1.0     # longer stride
    HIP_FLEX  = 35.0    # more hip movement
    KNEE_MAX  = 65.0    # higher knee lift
    ARM_SWING = 28.0    # bigger arm swing
    FORE_FLEX = 35.0    # elbows bent (runner pose)
    BODY_LEAN = 3.0
    BOB       = 0.018   # more bounce
    SWAY      = 0.006
    FWD_LEAN  = 5.0     # slight forward lean when running

    for f in range(N + 1):
        phase = (f % CYCLE) / CYCLE * 2 * math.pi
        # Character faces -Y.  s > 0 = L leg swings forward (toward -Y).
        s = -math.sin(phase)

        # --- Root (forward = -Y) ---
        fwd = f * STRIDE / CYCLE
        bob = abs(math.sin(phase)) * BOB
        sway_x = math.sin(phase) * SWAY
        if torso:
            torso.location = (sway_x, -fwd, bob)
            _kf_loc(torso, f)

        # --- Torso: forward lean + twist ---
        if spine1:
            spine1.rotation_quaternion = _deg(
                -FWD_LEAN,
                s * 3,
                -s * BODY_LEAN,
            )
            _kf(spine1, f)
        if spine3:
            spine3.rotation_quaternion = _deg(-FWD_LEAN * 0.3, s * 2, 0)
            _kf(spine3, f)
        if head:
            head.rotation_quaternion = _deg(FWD_LEAN * 0.6, 0, 0)
            _kf(head, f)

        # --- Legs ---
        hip_l = s * HIP_FLEX
        hip_r = -hip_l

        # Knee bends during forward swing (L fwd when s < 0, R fwd when s > 0)
        knee_l = max(0, -s) * KNEE_MAX
        knee_r = max(0, s) * KNEE_MAX

        if thigh_l:
            thigh_l.rotation_quaternion = _deg(hip_l, 0, 0)
            _kf(thigh_l, f)
        if thigh_r:
            thigh_r.rotation_quaternion = _deg(hip_r, 0, 0)
            _kf(thigh_r, f)
        if shin_l:
            shin_l.rotation_quaternion = _deg(knee_l, 0, 0)
            _kf(shin_l, f)
        if shin_r:
            shin_r.rotation_quaternion = _deg(knee_r, 0, 0)
            _kf(shin_r, f)

        foot_l_ang = math.sin(phase + 0.4) * 12
        foot_r_ang = math.sin(phase + math.pi + 0.4) * 12
        if foot_l:
            foot_l.rotation_quaternion = _deg(foot_l_ang, 0, 0)
            _kf(foot_l, f)
        if foot_r:
            foot_r.rotation_quaternion = _deg(foot_r_ang, 0, 0)
            _kf(foot_r, f)

        # --- Arms (cross-lateral: Z rotation + elbow pump) ---
        arm_osc = math.sin(phase)  # = -s; >0 when L arm back / R arm fwd
        z_arm = arm_osc * ARM_SWING
        if upper_l:
            upper_l.rotation_quaternion = _wrot(upper_l,
                ((0, 0, 1), z_arm))
            _kf(upper_l, f)
        if upper_r:
            upper_r.rotation_quaternion = _wrot(upper_r,
                ((0, 0, 1), z_arm))
            _kf(upper_r, f)
        # Elbow pump: +_deg on forearm = flexion (hand forward)
        elbow_osc = arm_osc * 20
        if fore_l:
            fore_l.rotation_quaternion = _deg(FORE_FLEX - elbow_osc, 0, 0)
            _kf(fore_l, f)
        if fore_r:
            fore_r.rotation_quaternion = _deg(FORE_FLEX + elbow_osc, 0, 0)
            _kf(fore_r, f)

    return 0, N


# ---------------------------------------------------------------------------
# Procedural animation catalog: key -> (label, category, generator_func)
# ---------------------------------------------------------------------------

_PROCEDURAL_ANIMS = {
    "run":           ("Run",               "Walk",  _gen_run),
    "idle":          ("Idle (breathing)",   "Home",  _gen_idle),
    "wave":          ("Wave hand",          "Home",  _gen_wave),
    "nod_yes":       ("Nod yes",            "Home",  _gen_nod_yes),
    "shake_no":      ("Shake head no",      "Home",  _gen_shake_no),
    "look_around":   ("Look around",        "Home",  _gen_look_around),
    "stretch":       ("Stretch arms",       "Home",  _gen_stretch),
    "greeting":      ("Greeting bow",       "Home",  _gen_greeting),
    "hands_on_hips": ("Hands on hips",      "Home",  _gen_hands_on_hips),
    "clap":          ("Clapping",           "Home",  _gen_clap),
    "weight_shift":  ("Weight shift",       "Home",  _gen_weight_shift),
}


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

def _assign_action(rig, act):
    """Assign action to rig with proper Blender 5.0 slot binding + FK mode."""
    if not rig or not act:
        return
    if not rig.animation_data:
        rig.animation_data_create()
    rig.animation_data.action = act
    # Blender 5.0 layered actions: rebind slot to target rig
    if hasattr(act, 'slots') and hasattr(rig.animation_data, 'action_slot') and act.slots:
        slot = act.slots[0]
        rig_id = f"OB{rig.name}"
        if hasattr(slot, 'identifier') and slot.identifier != rig_id:
            try:
                slot.identifier = rig_id
            except Exception:
                pass
        rig.animation_data.action_slot = slot
    # Ensure FK mode so animated FK bones drive DEF bones
    _set_fk_mode(rig)


def _get_action_fcurves(act):
    """Get fcurves from action, compatible with Blender 4.x and 5.0+."""
    if hasattr(act, 'fcurves') and act.fcurves is not None:
        try:
            len(act.fcurves)
            return act.fcurves
        except Exception:
            pass
    # Blender 5.0: layered actions
    if act.layers:
        strip = act.layers[0].strips[0]
        for slot in act.slots:
            bag = strip.channelbag(slot, ensure=False)
            if bag:
                return bag.fcurves
    return []


def _list_animations():
    """Return dict: category -> [(label, path_or_proc_key), ...]

    Scans BVH directories AND adds procedural animations.
    Labels come from _BVH_CATALOG if available, otherwise from filename.
    """
    result = {}
    if os.path.isdir(_BVH_DIR):
        for cat_name, _ in _ANIM_CATEGORIES:
            cat_dir = os.path.join(_BVH_DIR, cat_name)
            if not os.path.isdir(cat_dir):
                continue
            # Build set of available files in this category
            available = {}
            for fname in os.listdir(cat_dir):
                if fname.endswith(".bvh"):
                    available[fname[:-4]] = os.path.join(cat_dir, fname)
            items = []
            # Add files in catalog order first
            for stem in _BVH_CATALOG:
                if stem in available:
                    items.append((_BVH_CATALOG[stem], available.pop(stem)))
            # Then any remaining files not in catalog (alphabetical)
            for stem in sorted(available):
                items.append((stem.replace("_", " "), available[stem]))
            if items:
                result[cat_name] = items

    # Add procedural animations by category
    for key, (label, cat, _func) in _PROCEDURAL_ANIMS.items():
        cat_list = result.setdefault(cat, [])
        cat_list.insert(0, (label, _PROC_PREFIX + key))

    return result


def _generate_procedural(rig, proc_key):
    """Generate a procedural animation on *rig*.

    Returns (action, f_start, f_end).
    """
    label, _cat, gen_func = _PROCEDURAL_ANIMS[proc_key]
    act_name = f"HB_Proc_{proc_key}"

    act = bpy.data.actions.new(act_name)
    _assign_action(rig, act)

    f_start, f_end = gen_func(rig)
    print(f"[Animation] Generated procedural: {label} ({f_end - f_start + 1} frames)")
    return act, f_start, f_end


def _get_retarget_func():
    """Import retarget function from convert module."""
    from .convert.convertDazPoseBvhToBlender import retarget_bvh
    return retarget_bvh


def _get_cache_dir():
    """Return path to animation cache directory (auto-created)."""
    d = os.path.join(_HUMANBODY_ROOT, "data", "animations", "cache")
    os.makedirs(d, exist_ok=True)
    return d


def _load_cached_action(rig, bvh_path, prefix="HB_Anim", cache_suffix=""):
    """Try loading a cached action from cache/{stem}{cache_suffix}.blend.

    Returns (action, f_start, f_end) or (None, 0, 0).
    """
    stem = os.path.splitext(os.path.basename(bvh_path))[0]
    blend_path = os.path.join(_get_cache_dir(), f"{stem}{cache_suffix}.blend")
    if not os.path.isfile(blend_path):
        return None, 0, 0

    action_name = f"{prefix}_{stem}"

    try:
        with bpy.data.libraries.load(blend_path) as (data_from, data_to):
            if not data_from.actions:
                return None, 0, 0
            # Load the first (only) action, rename after
            data_to.actions = [data_from.actions[0]]

        act = data_to.actions[0]
        if not act:
            return None, 0, 0

        act.name = action_name

        # Assign to rig
        _assign_action(rig, act)

        # Determine frame range from fcurves
        fcs = _get_action_fcurves(act)
        if fcs:
            frames = set()
            for fc in fcs:
                for kp in fc.keyframe_points:
                    frames.add(int(kp.co[0]))
            if frames:
                f_start = min(frames)
                f_end = max(frames)
                print(f"[Animation] Cache hit: {action_name} ({f_end - f_start + 1} frames)")
                _set_fk_mode(rig)
                return act, f_start, f_end

        print(f"[Animation] Cache hit: {action_name} (no keyframes, default range)")
        _set_fk_mode(rig)
        return act, 1, 250
    except Exception as e:
        print(f"[Animation] Cache load failed: {e}")
        return None, 0, 0


def _save_action_cache(bvh_path, act, cache_suffix=""):
    """Save a retargeted action to cache/{stem}{cache_suffix}.blend."""
    stem = os.path.splitext(os.path.basename(bvh_path))[0]
    blend_path = os.path.join(_get_cache_dir(), f"{stem}{cache_suffix}.blend")
    try:
        bpy.data.libraries.write(blend_path, {act}, fake_user=True)
        print(f"[Animation] Cached: {act.name} → {blend_path}")
    except Exception as e:
        print(f"[Animation] Cache save failed: {e}")


def _retarget(context, rig, bvh_path):
    """Load BVH and retarget using convertDazPoseBvhToBlender (old method)."""
    retarget = _get_retarget_func()
    return retarget(context, rig, bvh_path)



def _flip_animation_180(torso_loc, torso_rot):
    """Flip animation 180° around Z axis.

    Negates X and Y location keyframes, pre-multiplies rotation by 180° Z.
    This turns a backward-walking animation into a forward-walking one.

    180° Z quaternion = (w=0, x=0, y=0, z=1).
    Pre-multiply: (0,0,0,1) @ (qw,qx,qy,qz) = (-qz, -qy, qx, qw).
    """
    # Negate X and Y location
    for idx in (0, 1):
        fc = torso_loc.get(idx)
        if fc:
            for kp in fc.keyframe_points:
                kp.co[1] = -kp.co[1]
            fc.update()

    # Pre-multiply rotation by 180° around Z
    if len(torso_rot) < 4:
        return
    fc_w = torso_rot[0]
    fc_x = torso_rot[1]
    fc_y = torso_rot[2]
    fc_z = torso_rot[3]

    n_kp = len(fc_w.keyframe_points)
    for i in range(n_kp):
        qw = fc_w.keyframe_points[i].co[1]
        qx = fc_x.keyframe_points[i].co[1]
        qy = fc_y.keyframe_points[i].co[1]
        qz = fc_z.keyframe_points[i].co[1]
        # (0,0,0,1) @ (qw,qx,qy,qz) = (-qz, -qy, qx, qw)
        fc_w.keyframe_points[i].co[1] = -qz
        fc_x.keyframe_points[i].co[1] = -qy
        fc_y.keyframe_points[i].co[1] = qx
        fc_z.keyframe_points[i].co[1] = qw

    for fc in torso_rot.values():
        fc.update()


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


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class HUMANBODY_OT_load_animation(bpy.types.Operator):
    bl_idname = "humanbody.load_animation"
    bl_label = "Load Animation"
    bl_description = "Load an animation (BVH or procedural)"
    bl_options = {'REGISTER', 'UNDO'}

    bvh_path: bpy.props.StringProperty()
    anim_name: bpy.props.StringProperty()

    def execute(self, context):
        obj = context.active_object
        if not obj or not obj.data.get("humanbody"):
            self.report({'ERROR'}, "Select a HumanBody character")
            return {'CANCELLED'}

        rig = _find_rig(obj)
        if not rig:
            self.report({'ERROR'}, "Add a rig first")
            return {'CANCELLED'}

        _cleanup_old_anim(context, rig)

        # Optimize viewport for smooth playback
        _set_cloth_viewport(False)
        _optimize_viewport(context)

        if self.bvh_path.startswith(_PROC_PREFIX):
            # Procedural animation — instant generation
            proc_key = self.bvh_path[len(_PROC_PREFIX):]
            if proc_key not in _PROCEDURAL_ANIMS:
                self.report({'ERROR'}, f"Unknown procedural: {proc_key}")
                return {'CANCELLED'}
            context.scene.render.fps = 60
            act, f_start, f_end = _generate_procedural(rig, proc_key)
        else:
            # BVH animation
            if not os.path.isfile(self.bvh_path):
                self.report({'ERROR'}, f"BVH not found: {self.bvh_path}")
                return {'CANCELLED'}

            # Set scene FPS from BVH file
            bvh_fps, _ = _parse_bvh_info(self.bvh_path)
            context.scene.render.fps = bvh_fps

            # Try cache first
            act, f_start, f_end = _load_cached_action(rig, self.bvh_path)
            if not act:
                # KBS retarget on temp copy (same pattern as test button)
                rig_tmp = rig.copy()
                rig_tmp.data = rig.data.copy()
                rig_tmp.name = "TMP_retarget"
                context.collection.objects.link(rig_tmp)
                _hide_meshes_for_retarget(rig_tmp)
                try:
                    if rig_tmp.animation_data:
                        rig_tmp.animation_data.action = None
                    act, f_start, f_end = retarget_rokoko(
                        context, rig_tmp, self.bvh_path)
                    if act:
                        _assign_action(rig, act)
                        _save_action_cache(self.bvh_path, act)
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    self.report({'ERROR'}, f"Retargeting failed: {e}")
                finally:
                    _show_meshes_after_retarget(rig_tmp)
                    if rig_tmp.name in bpy.data.objects:
                        bpy.data.objects.remove(rig_tmp, do_unlink=True)
                if not act:
                    return {'CANCELLED'}

        act.name = f"HB_Anim_{self.anim_name}"
        total = f_end - f_start + 1
        context.scene.frame_start = f_start
        context.scene.frame_end = f_end
        context.scene.frame_set(f_start)

        # Apply speed from UI slider
        speed = getattr(context.scene.humanbody, 'anim_speed', 1.0)
        context.scene.render.fps_base = 1.0 / max(0.1, speed)

        # Restore selection to body mesh
        for o in context.view_layer.objects:
            o.select_set(o == obj)
        context.view_layer.objects.active = obj

        try:
            if 0 < total and not context.screen.is_animation_playing:
                bpy.ops.screen.animation_play()
        except Exception:
            pass

        self.report({'INFO'}, f"Animation: {self.anim_name}")
        return {'FINISHED'}


class HUMANBODY_OT_stop_animation(bpy.types.Operator):
    bl_idname = "humanbody.stop_animation"
    bl_label = "Stop Animation"
    bl_description = "Stop and remove current animation"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if not obj or not obj.data.get("humanbody"):
            return {'CANCELLED'}

        rig = _find_rig(obj)
        if rig:
            _cleanup_old_anim(context, rig)

        # Stop playback
        if context.screen.is_animation_playing:
            bpy.ops.screen.animation_play()

        # Restore viewport settings
        _set_cloth_viewport(True)
        _restore_viewport(context)

        context.scene.frame_set(1)
        self.report({'INFO'}, "Animation stopped")
        return {'FINISHED'}


class HUMANBODY_OT_load_bvh_native(bpy.types.Operator):
    bl_idname = "humanbody.load_bvh_native"
    bl_label = "BVH Compare"
    bl_description = (
        "3-way compare: BVH skeleton | Rokoko | KBS retarget"
    )
    bl_options = {'REGISTER', 'UNDO'}

    bvh_path: bpy.props.StringProperty()
    anim_name: bpy.props.StringProperty()

    def execute(self, context):
        if not os.path.isfile(self.bvh_path):
            self.report({'ERROR'}, f"BVH not found: {self.bvh_path}")
            return {'CANCELLED'}

        obj = context.active_object
        if not obj or not obj.data.get("humanbody"):
            self.report({'ERROR'}, "Select a HumanBody character")
            return {'CANCELLED'}
        rig = _find_rig(obj)
        if not rig:
            self.report({'ERROR'}, "Add a rig first")
            return {'CANCELLED'}

        # --- Parse BVH file info ---
        bvh_fps, bvh_nframes = _parse_bvh_info(self.bvh_path)

        context.scene.render.fps = bvh_fps
        context.scene.render.fps_base = 1.0

        # --- Cleanup previous previews ---
        for o in list(bpy.data.objects):
            if (o.name.startswith("BVH_Preview")
                    or o.name.startswith("Rig_Preview")
                    or o.name.startswith("Preview_")
                    or o.name.startswith("KBS_Preview")
                    or o.name.startswith("KBS_")
                    or o.name.startswith("ROK_Preview")
                    or o.name.startswith("ROK_")
                    or o.name.startswith("ROK46_Preview")
                    or o.name.startswith("ROK46_")
                    or o.name.startswith("RTEST_Preview")
                    or o.name.startswith("RTEST_")
                    or o.name.startswith("TMP_")):
                bpy.data.objects.remove(o, do_unlink=True)

        _cleanup_old_anim(context, rig)
        _set_cloth_viewport(False)
        _optimize_viewport(context)

        # ---- Helper: deep-copy rig with mesh children ----
        def _copy_rig(src_rig, name_prefix):
            try:
                rc = src_rig.copy()
                rc.data = src_rig.data.copy()
                rc.name = f"{name_prefix}_Preview"
                context.collection.objects.link(rc)
                for pb in rc.pose.bones:
                    for c in pb.constraints:
                        if hasattr(c, 'target') and c.target == src_rig:
                            c.target = rc
                if rc.data.animation_data:
                    for drv_fc in rc.data.animation_data.drivers:
                        for var in drv_fc.driver.variables:
                            for tgt in var.targets:
                                if tgt.id == src_rig:
                                    tgt.id = rc
                for child in list(src_rig.children):
                    if child.type != 'MESH':
                        continue
                    mc = child.copy()
                    mc.data = child.data.copy()
                    mc.name = f"{name_prefix}_{child.name}"
                    context.collection.objects.link(mc)
                    mc.parent = rc
                    mc.parent_type = child.parent_type
                    mc.parent_bone = child.parent_bone
                    mc.matrix_parent_inverse = child.matrix_parent_inverse.copy()
                    for mod in mc.modifiers:
                        if mod.type == 'ARMATURE' and mod.object == src_rig:
                            mod.object = rc
                        if mod.type == 'CLOTH':
                            mod.show_viewport = False
                            mod.show_render = False
                return rc
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"[Animation] Rig copy '{name_prefix}' failed: {e}")
                return None

        def _style_preview_rig(rc):
            if not rc or rc.name not in bpy.data.objects:
                return
            rc.show_in_front = True
            rc.data.display_type = 'STICK'
            rc.data.show_bone_custom_shapes = False
            rc.data.show_bone_colors = False
            for bc_copy in rc.data.collections:
                bc_orig = rig.data.collections.get(bc_copy.name)
                bc_copy.is_visible = bc_orig.is_visible if bc_orig else False

        def _align_rig(rc, ground_z, center_root_pos):
            if not rc or rc.name not in bpy.data.objects:
                return
            for fname in ("foot_fk.L", "ORG-foot.L", "DEF-foot.L"):
                pb = rc.pose.bones.get(fname)
                if pb:
                    foot = (rc.matrix_world @ pb.matrix).to_translation()
                    rc.location.z -= (foot.z - ground_z)
                    break
            root_pb = rc.pose.bones.get("root")
            if root_pb:
                rpos = (rc.matrix_world @ root_pb.matrix).to_translation()
                rc.location.y -= (rpos.y - center_root_pos.y)

        # ============================================================
        # PHASE 1: Retargets on temp copies (no BVH_Preview yet)
        # ============================================================

        # ---- Rokoko retarget → action for main rig ----
        act, f_start, f_end = _load_cached_action(rig, self.bvh_path)
        if not act:
            rig_tmp = rig.copy()
            rig_tmp.data = rig.data.copy()
            rig_tmp.name = "TMP_rok_retarget"
            context.collection.objects.link(rig_tmp)
            try:
                if rig_tmp.animation_data:
                    rig_tmp.animation_data.action = None
                act, f_start, f_end = retarget_rokoko(
                    context, rig_tmp, self.bvh_path)
                if act:
                    _save_action_cache(self.bvh_path, act)
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.report({'WARNING'}, f"Rokoko retarget failed: {e}")
                act = None
                f_start, f_end = 1, bvh_nframes
            finally:
                try:
                    bpy.data.objects.remove(rig_tmp, do_unlink=True)
                except Exception:
                    pass

        if act:
            act.name = f"HB_Anim_{self.anim_name}"
            _assign_action(rig, act)

        # ---- KBS retarget → action for KBS copy ----
        act_kbs = None
        act_kbs, _, _ = _load_cached_action(rig, self.bvh_path, "HB_KBS", "_kbs")
        if act:
            _assign_action(rig, act)
        if not act_kbs:
            rig_tmp2 = rig.copy()
            rig_tmp2.data = rig.data.copy()
            rig_tmp2.name = "TMP_kbs_retarget"
            context.collection.objects.link(rig_tmp2)
            try:
                if rig_tmp2.animation_data:
                    rig_tmp2.animation_data.action = None
                act_kbs, _, _ = retarget_kbs(
                    context, rig_tmp2, self.bvh_path)
                if act_kbs:
                    _save_action_cache(self.bvh_path, act_kbs, "_kbs")
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"[Animation] KBS retarget failed: {e}")
            finally:
                try:
                    bpy.data.objects.remove(rig_tmp2, do_unlink=True)
                except Exception:
                    pass

        if act_kbs:
            act_kbs.name = f"HB_KBS_{self.anim_name}"

        # ============================================================
        # PHASE 2: Display setup (retargets done, scene is clean)
        # ============================================================

        # ---- LEFT: BVH native skeleton (filtered to mapped bones) ----
        bvh_rig, _, _ = _import_bvh_armature(context, self.bvh_path)
        if bvh_rig:
            is_mocapnet = 'hip' in bvh_rig.data.bones
            is_v4_preview = is_mocapnet and '__jaw' in bvh_rig.data.bones
            if is_mocapnet:
                _normalize_openpose_bones(context, bvh_rig)
            _filter_bvh_bones(context, bvh_rig, is_mocapnet, is_v4=is_v4_preview)
            bvh_rig.name = "BVH_Preview"
            bvh_rig.show_in_front = True
            _scale_to_match(bvh_rig, rig)
            bvh_rig.location.x = -2.0
            bvh_rig.data.display_type = 'STICK'

        # ---- CENTER: Main rig with Rokoko action ----
        rig.location.x = 0.0

        # ---- RIGHT: KBS copy with KBS action ----
        rig_kbs = _copy_rig(rig, "KBS")
        if rig_kbs:
            rig_kbs.location.x = 2.0
            if act_kbs:
                _assign_action(rig_kbs, act_kbs)

        # ---- Align all models at frame 1 ----
        bpy.context.scene.frame_set(1)
        bpy.context.view_layer.update()

        # Use BVH hips Y for depth alignment
        if bvh_rig:
            hips_name = "hip" if "hip" in bvh_rig.pose.bones else "Hips"
            bvh_hip = (bvh_rig.matrix_world
                       @ bvh_rig.pose.bones[hips_name].matrix).to_translation()
            rig_root = (rig.matrix_world
                        @ rig.pose.bones["root"].matrix).to_translation()
            rig.location.y -= (rig_root.y - bvh_hip.y)

        # Ground level from main rig foot
        bpy.context.view_layer.update()
        ground_z = 0.0
        for fname in ("foot_fk.L", "ORG-foot.L", "DEF-foot.L"):
            pb = rig.pose.bones.get(fname)
            if pb:
                ground_z = (rig.matrix_world @ pb.matrix).to_translation().z
                break
        center_root = (rig.matrix_world
                       @ rig.pose.bones["root"].matrix).to_translation()

        # Align BVH skeleton height
        if bvh_rig:
            for bname in ("LeftFoot", "lFoot", "foot.L"):
                pb = bvh_rig.pose.bones.get(bname)
                if pb:
                    bvh_foot_z = (bvh_rig.matrix_world @ pb.matrix).to_translation().z
                    bvh_rig.location.z -= (bvh_foot_z - ground_z)
                    break

        _align_rig(rig_kbs, ground_z, center_root)

        # ---- Frame range and playback ----
        context.scene.frame_start = 1
        context.scene.frame_end = max(bvh_nframes, f_end if act else 1)
        context.scene.frame_set(1)

        speed = getattr(context.scene.humanbody, 'anim_speed', 1.0)
        context.scene.render.fps_base = 1.0 / max(0.1, speed)

        # Restore selection to body
        for o in context.view_layer.objects:
            o.select_set(o == obj)
        context.view_layer.objects.active = obj

        try:
            bpy.ops.screen.animation_play()
        except Exception:
            pass

        fname = os.path.basename(self.bvh_path)
        self.report({'INFO'},
                     f"3-way: BVH | Rokoko | KBS — {fname}")
        return {'FINISHED'}


class HUMANBODY_OT_batch_retarget(bpy.types.Operator):
    bl_idname = "humanbody.batch_retarget"
    bl_label = "Pre-cache All Animations"
    bl_description = "Retarget all BVH animations and cache the results for instant playback"
    bl_options = {'REGISTER'}

    def execute(self, context):
        obj = context.active_object
        if not obj or not obj.data.get("humanbody"):
            self.report({'ERROR'}, "Select a HumanBody character")
            return {'CANCELLED'}
        rig = _find_rig(obj)
        if not rig:
            self.report({'ERROR'}, "Add a rig first")
            return {'CANCELLED'}

        anims = _list_animations()
        cache_dir = _get_cache_dir()
        cached, retargeted, failed = 0, 0, 0

        for cat_name, items in anims.items():
            for label, path in items:
                if path.startswith(_PROC_PREFIX):
                    continue
                stem = os.path.splitext(os.path.basename(path))[0]
                cache_path = os.path.join(cache_dir, f"{stem}.blend")
                if os.path.isfile(cache_path):
                    cached += 1
                    continue
                _cleanup_old_anim(context, rig)
                _hide_meshes_for_retarget(rig)
                try:
                    act, _, _ = retarget_kbs(context, rig, path)
                    _save_action_cache(path, act)
                    retargeted += 1
                except Exception as e:
                    print(f"[Animation] Batch cache failed for {stem}: {e}")
                    failed += 1
                finally:
                    _show_meshes_after_retarget(rig)

        _cleanup_old_anim(context, rig)
        msg = f"Cached {retargeted} new, {cached} already cached"
        if failed:
            msg += f", {failed} failed"
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class HUMANBODY_OT_mocapnet_webui(bpy.types.Operator):
    bl_idname = "humanbody.mocapnet_webui"
    bl_label = "MocapNET Web-UI"
    bl_description = "Start MocapNET Django server and open web UI for video-to-BVH processing"
    bl_options = {'REGISTER'}

    _WEBAPP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                               "HumanBodyWeb")
    _PORT = 8081

    def execute(self, context):
        import subprocess
        import webbrowser
        import socket

        # Check if server is already running
        running = False
        try:
            with socket.create_connection(("127.0.0.1", self._PORT), timeout=1):
                running = True
        except (ConnectionRefusedError, OSError):
            pass

        if not running:
            manage_py = os.path.join(self._WEBAPP_DIR, "manage.py")
            if not os.path.isfile(manage_py):
                self.report({'ERROR'}, f"Django project not found at {self._WEBAPP_DIR}")
                return {'CANCELLED'}
            subprocess.Popen(
                ["python", manage_py, "runserver", str(self._PORT)],
                cwd=self._WEBAPP_DIR,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self.report({'INFO'}, f"MocapNET server started on port {self._PORT}")
        else:
            self.report({'INFO'}, "MocapNET server already running")

        webbrowser.open(f"http://127.0.0.1:{self._PORT}/")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Retarget module (imported late to avoid circular dependency)
# ---------------------------------------------------------------------------

from .retarget import (  # noqa: E402
    retarget_rokoko, retarget_kbs,
    _import_bvh_armature, _normalize_openpose_bones,
    _filter_bvh_bones, _scale_to_match,
)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = (
    HUMANBODY_OT_load_animation,
    HUMANBODY_OT_stop_animation,
    HUMANBODY_OT_load_bvh_native,
    HUMANBODY_OT_batch_retarget,
    HUMANBODY_OT_mocapnet_webui,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
