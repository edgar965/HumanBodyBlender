# -*- coding: utf-8 -*-
import math
import logging
logger = logging.getLogger(__name__)
from .keyframes import _deg
from .keyframes import _kf
from .keyframes import _kf_loc
from .keyframes import _pb
from .keyframes import _wrot


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
