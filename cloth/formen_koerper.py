# -*- coding: utf-8 -*-
import logging
import bmesh
logger = logging.getLogger(__name__)
from .netzbau import _bmesh_ring
from .netzbau import _bmesh_ring_yz
from .netzbau import _bridge_rings
from .netzbau import _finish_primitive
from .koerpermass import _measure_arm_at_x
from .koerpermass import _measure_body_at_z
from .koerpermass import _measure_leg_at_z


def _create_prim_skirt(context, body, segments, length, flare):
    """Open cone from waist downward."""
    waist_z = 0.92
    gap = 0.015
    cx, cy, r_body = _measure_body_at_z(body, waist_z)
    r_top = r_body + gap

    n_rings = max(3, int(length / 0.03))
    bm = bmesh.new()
    rings = []
    pin_verts = None

    for i in range(n_rings):
        t = i / max(n_rings - 1, 1)
        z = waist_z - t * length
        r = r_top * (1.0 + flare * t)
        ring = _bmesh_ring(bm, cx, cy, z, r, segments)
        if i == 0:
            pin_verts = list(ring)
        if rings:
            _bridge_rings(bm, rings[-1], ring)
        rings.append(ring)

    return _finish_primitive(context, bm, "Cloth_Prim_Skirt", body, pin_verts)


def _create_prim_top(context, body, segments, length):
    """Open cylinder around torso from shoulders down."""
    shoulder_z = 1.30
    gap = 0.015
    bottom_z = max(shoulder_z - length, 0.70)

    n_rings = max(3, int((shoulder_z - bottom_z) / 0.03))
    bm = bmesh.new()
    rings = []
    pin_verts = None

    for i in range(n_rings):
        t = i / max(n_rings - 1, 1)
        z = shoulder_z - t * (shoulder_z - bottom_z)
        cx, cy, r_body = _measure_body_at_z(body, z, x_limit=0.20)
        r = r_body + gap
        ring = _bmesh_ring(bm, cx, cy, z, r, segments)
        if i == 0:
            pin_verts = list(ring)
        if rings:
            _bridge_rings(bm, rings[-1], ring)
        rings.append(ring)

    return _finish_primitive(context, bm, "Cloth_Prim_Top", body, pin_verts,
                             color=(0.35, 0.25, 0.20, 1.0))


def _create_prim_pants(context, body, segments, length):
    """Two tubes for legs, merged at hip."""
    waist_z = 0.92
    crotch_z = 0.68
    ankle_z = max(waist_z - length, 0.06)
    gap = 0.012

    bm = bmesh.new()

    for side in ('left', 'right'):
        rings = []
        # Below crotch: centered on leg
        n_leg = max(2, int((crotch_z - ankle_z) / 0.03))
        for i in range(n_leg):
            t = i / max(n_leg - 1, 1)
            z = ankle_z + t * (crotch_z - ankle_z)
            cx, cy, r_body = _measure_leg_at_z(body, z, side)
            r = r_body + gap
            ring = _bmesh_ring(bm, cx, cy, z, r, segments)
            if rings:
                _bridge_rings(bm, rings[-1], ring)
            rings.append(ring)

        # Above crotch: blend from leg center to body center
        n_hip = max(2, int((waist_z - crotch_z) / 0.03))
        leg_cx, leg_cy, _ = _measure_leg_at_z(body, crotch_z, side)
        for i in range(1, n_hip + 1):
            t = i / n_hip
            z = crotch_z + t * (waist_z - crotch_z)
            body_cx, body_cy, _ = _measure_body_at_z(body, z, x_limit=0.20)
            _, _, r_leg = _measure_leg_at_z(body, z, side)
            cx = leg_cx + (body_cx - leg_cx) * t
            cy = leg_cy + (body_cy - leg_cy) * t
            r = r_leg + gap
            ring = _bmesh_ring(bm, cx, cy, z, r, segments)
            if rings:
                _bridge_rings(bm, rings[-1], ring)
            rings.append(ring)

    # Merge overlapping verts at hip/waist
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.008)

    # Find pin verts by Z position AFTER remove_doubles
    bm.verts.ensure_lookup_table()
    pin_indices = [v.index for v in bm.verts if v.co.z >= waist_z - 0.02]

    return _finish_primitive(context, bm, "Cloth_Prim_Pants", body, pin_indices,
                             color=(0.15, 0.18, 0.35, 1.0))


def _create_prim_arms(context, body, segments, length):
    """Tubes around both arms (YZ-plane rings perpendicular to arm axis)."""
    shoulder_x = 0.22  # where arm starts laterally
    gap = 0.012

    bm = bmesh.new()
    all_pin_verts = []

    for side in ('left', 'right'):
        sign = 1.0 if side == 'left' else -1.0
        rings = []
        n_rings = max(3, int(length / 0.03))
        for i in range(n_rings):
            t = i / max(n_rings - 1, 1)
            x = sign * (shoulder_x + t * length)
            cy, cz, r_arm = _measure_arm_at_x(body, x)
            r = r_arm + gap
            ring = _bmesh_ring_yz(bm, x, cy, cz, r, segments)
            if i == 0:
                all_pin_verts.extend(ring)
            if rings:
                _bridge_rings(bm, rings[-1], ring)
            rings.append(ring)

    return _finish_primitive(context, bm, "Cloth_Prim_Arms", body, all_pin_verts,
                             color=(0.35, 0.25, 0.20, 1.0))


def _create_prim_neck(context, body, segments, length):
    """Tube around the neck."""
    neck_top_z = 1.42
    gap = 0.010
    neck_bot_z = max(neck_top_z - length, 1.28)

    n_rings = max(3, int((neck_top_z - neck_bot_z) / 0.02))
    bm = bmesh.new()
    rings = []
    pin_verts = None

    for i in range(n_rings):
        t = i / max(n_rings - 1, 1)
        z = neck_top_z - t * (neck_top_z - neck_bot_z)
        cx, cy, r_body = _measure_body_at_z(body, z, z_tol=0.02)
        r = r_body + gap
        ring = _bmesh_ring(bm, cx, cy, z, r, segments)
        if i == 0:
            pin_verts = list(ring)
        if rings:
            _bridge_rings(bm, rings[-1], ring)
        rings.append(ring)

    return _finish_primitive(context, bm, "Cloth_Prim_Neck", body, pin_verts,
                             color=(0.40, 0.35, 0.30, 1.0))


def _create_prim_head(context, body, segments, length):
    """Tube/cap around the head."""
    head_top_z = 1.68
    gap = 0.012
    head_bot_z = max(head_top_z - length, 1.42)

    n_rings = max(3, int((head_top_z - head_bot_z) / 0.02))
    bm = bmesh.new()
    rings = []
    pin_verts = None

    for i in range(n_rings):
        t = i / max(n_rings - 1, 1)
        z = head_bot_z + t * (head_top_z - head_bot_z)
        cx, cy, r_body = _measure_body_at_z(body, z, z_tol=0.02)
        r = r_body + gap
        # Taper towards top
        taper = 1.0 - 0.3 * t * t
        r *= taper
        ring = _bmesh_ring(bm, cx, cy, z, r, segments)
        if i == 0:
            pin_verts = list(ring)
        if rings:
            _bridge_rings(bm, rings[-1], ring)
        rings.append(ring)

    # Close top with a fan
    if rings:
        top_ring = rings[-1]
        top_z = head_top_z
        cx = sum(v.co.x for v in top_ring) / len(top_ring)
        cy = sum(v.co.y for v in top_ring) / len(top_ring)
        cap_vert = bm.verts.new((cx, cy, top_z + 0.02))
        n = len(top_ring)
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new([top_ring[i], top_ring[j], cap_vert])

    return _finish_primitive(context, bm, "Cloth_Prim_Head", body, pin_verts,
                             color=(0.50, 0.40, 0.35, 1.0))


def _create_prim_shoes(context, body, segments, length):
    """Tubes around both feet."""
    ankle_z = 0.10
    gap = 0.010
    toe_z = max(ankle_z - length, -0.02)

    bm = bmesh.new()
    all_pin_verts = []

    for side in ('left', 'right'):
        rings = []
        n_rings = max(3, int((ankle_z - toe_z) / 0.02))
        for i in range(n_rings):
            t = i / max(n_rings - 1, 1)
            z = ankle_z - t * (ankle_z - toe_z)
            cx, cy, r_body = _measure_leg_at_z(body, z, side, z_tol=0.02)
            r = r_body + gap
            # Slight taper at toe
            if t > 0.6:
                r *= 1.0 - 0.2 * ((t - 0.6) / 0.4)
            ring = _bmesh_ring(bm, cx, cy, z, r, segments)
            if i == 0:
                all_pin_verts.extend(ring)
            if rings:
                _bridge_rings(bm, rings[-1], ring)
            rings.append(ring)

        # Close toe with fan
        if rings:
            toe_ring = rings[-1]
            cz = toe_z
            fcx = sum(v.co.x for v in toe_ring) / len(toe_ring)
            fcy = sum(v.co.y for v in toe_ring) / len(toe_ring)
            cap = bm.verts.new((fcx, fcy, cz - 0.01))
            n = len(toe_ring)
            for k in range(n):
                j = (k + 1) % n
                bm.faces.new([toe_ring[k], toe_ring[j], cap])

    return _finish_primitive(context, bm, "Cloth_Prim_Shoes", body, all_pin_verts,
                             color=(0.12, 0.10, 0.08, 1.0))
