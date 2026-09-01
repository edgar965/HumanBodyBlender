# -*- coding: utf-8 -*-
import math
import logging
logger = logging.getLogger(__name__)
from .keyframes import _deg
from .keyframes import _kf
from .keyframes import _pb


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
