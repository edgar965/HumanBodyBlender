# -*- coding: utf-8 -*-
import logging
import bmesh
logger = logging.getLogger(__name__)
from .netzbau import _bmesh_body_ring
from .netzbau import _bmesh_ring
from .netzbau import _bridge_rings
from .netzbau import _finish_primitive
from .koerpermass import _measure_body_at_z
from .koerpermass import _measure_leg_at_z


def _create_tpl_tshirt(context, body, segments, gap, top_ext=0.0, bot_ext=0.0):
    """T-Shirt: single continuous torso tube (neckline→waist).

    Uses body-conforming rings that follow the actual cross-section shape
    instead of perfect circles, so the fit is tight at shoulders/chest.
    """
    neck_z = 1.42 + top_ext
    waist_z = 0.78 - bot_ext

    bm = bmesh.new()
    pin_verts = []

    n_torso = max(10, int((neck_z - waist_z) / 0.012))
    torso_rings = []
    for i in range(n_torso):
        t = i / max(n_torso - 1, 1)
        z = neck_z - t * (neck_z - waist_z)
        ring = _bmesh_body_ring(bm, body, z, segments, gap, x_limit=0.20)
        if i == 0:
            pin_verts.extend(ring)
        if torso_rings:
            _bridge_rings(bm, torso_rings[-1], ring)
        torso_rings.append(ring)

    obj = _finish_primitive(context, bm, "Cloth_Tpl_TShirt", body, pin_verts,
                            color=(0.30, 0.35, 0.50, 1.0))

    # Light corrective smooth (not applied — stays as modifier)
    cs = obj.modifiers.new(name="hb_corrective", type='CORRECTIVE_SMOOTH')
    cs.iterations = 3
    cs.smooth_type = 'LENGTH_WEIGHTED'
    cs.use_only_smooth = True
    return obj


def _create_tpl_pants(context, body, segments, gap, top_ext=0.0, bot_ext=0.0):
    """Body-conforming pants with measured leg/body radii per ring."""
    waist_z = 0.92 + top_ext
    crotch_z = 0.68
    ankle_z = 0.08 - bot_ext

    bm = bmesh.new()

    for side in ('left', 'right'):
        rings = []
        # Below crotch — measured per ring on leg
        n_leg = max(8, int((crotch_z - ankle_z) / 0.012))
        for i in range(n_leg):
            t = i / max(n_leg - 1, 1)
            z = ankle_z + t * (crotch_z - ankle_z)
            cx, cy, r_body = _measure_leg_at_z(body, z, side)
            r = r_body + gap
            ring = _bmesh_ring(bm, cx, cy, z, r, segments)
            if rings:
                _bridge_rings(bm, rings[-1], ring)
            rings.append(ring)

        # Above crotch — blend to body center, use leg radius for tight fit
        n_hip = max(4, int((waist_z - crotch_z) / 0.012))
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

    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.008)

    # Find pin verts by Z position AFTER remove_doubles
    bm.verts.ensure_lookup_table()
    pin_indices = [v.index for v in bm.verts if v.co.z >= waist_z - 0.02]

    obj = _finish_primitive(context, bm, "Cloth_Tpl_Pants", body, pin_indices,
                            color=(0.15, 0.18, 0.35, 1.0))

    cs = obj.modifiers.new(name="hb_corrective", type='CORRECTIVE_SMOOTH')
    cs.iterations = 3
    cs.smooth_type = 'LENGTH_WEIGHTED'
    cs.use_only_smooth = True
    return obj


def _create_tpl_skirt(context, body, segments, gap, top_ext=0.0, bot_ext=0.0):
    """Body-conforming skirt with measured waist + flare."""
    waist_z = 1.00 + top_ext
    knee_z = 0.40 - bot_ext
    flare = 0.4

    cx_w, cy_w, r_waist = _measure_body_at_z(body, waist_z)
    r_top = r_waist + gap

    n_rings = max(10, int((waist_z - knee_z) / 0.012))
    bm = bmesh.new()
    rings = []
    pin_verts = None

    for i in range(n_rings):
        t = i / max(n_rings - 1, 1)
        z = waist_z - t * (waist_z - knee_z)
        r = r_top * (1.0 + flare * t)
        ring = _bmesh_ring(bm, cx_w, cy_w, z, r, segments)
        if i == 0:
            pin_verts = list(ring)
        if rings:
            _bridge_rings(bm, rings[-1], ring)
        rings.append(ring)

    obj = _finish_primitive(context, bm, "Cloth_Tpl_Skirt", body, pin_verts,
                            color=(0.40, 0.20, 0.25, 1.0))

    cs = obj.modifiers.new(name="hb_corrective", type='CORRECTIVE_SMOOTH')
    cs.iterations = 3
    cs.smooth_type = 'LENGTH_WEIGHTED'
    cs.use_only_smooth = True
    return obj


def _create_tpl_dress(context, body, segments, gap, top_ext=0.0, bot_ext=0.0):
    """Dress: measured torso tube (shoulder→waist) + flare skirt (waist→knee)."""
    shoulder_z = 1.30 + top_ext
    waist_z = 0.82
    knee_z = 0.40 - bot_ext
    flare = 0.35

    bm = bmesh.new()
    pin_verts = None

    # Torso — body-conforming rings (x_limit excludes arm verts)
    n_torso = max(8, int((shoulder_z - waist_z) / 0.012))
    rings = []
    for i in range(n_torso):
        t = i / max(n_torso - 1, 1)
        z = shoulder_z - t * (shoulder_z - waist_z)
        ring = _bmesh_body_ring(bm, body, z, segments, gap, x_limit=0.20)
        if i == 0:
            pin_verts = list(ring)
        if rings:
            _bridge_rings(bm, rings[-1], ring)
        rings.append(ring)

    # Skirt — flare cone from waist
    cx_w, cy_w, r_waist = _measure_body_at_z(body, waist_z)
    r_top = r_waist + gap
    n_skirt = max(8, int((waist_z - knee_z) / 0.012))
    for i in range(1, n_skirt + 1):
        t = i / n_skirt
        z = waist_z - t * (waist_z - knee_z)
        r = r_top * (1.0 + flare * t)
        ring = _bmesh_ring(bm, cx_w, cy_w, z, r, segments)
        _bridge_rings(bm, rings[-1], ring)
        rings.append(ring)

    obj = _finish_primitive(context, bm, "Cloth_Tpl_Dress", body, pin_verts,
                            color=(0.45, 0.20, 0.30, 1.0))

    cs = obj.modifiers.new(name="hb_corrective", type='CORRECTIVE_SMOOTH')
    cs.iterations = 3
    cs.smooth_type = 'LENGTH_WEIGHTED'
    cs.use_only_smooth = True
    return obj
