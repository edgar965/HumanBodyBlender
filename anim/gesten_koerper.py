# -*- coding: utf-8 -*-
import math
import logging
from mathutils import Quaternion
logger = logging.getLogger(__name__)
from .keyframes import _deg
from .keyframes import _kf
from .keyframes import _kf_loc
from .keyframes import _pb
from .keyframes import _wrot


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
