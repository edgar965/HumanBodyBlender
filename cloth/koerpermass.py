# -*- coding: utf-8 -*-
import math
import logging
import bpy
logger = logging.getLogger(__name__)


# Module-level cache for evaluated body vertices (world-space).
# Populated by _prepare_body_eval(), cleared by _cleanup_body_eval().
_body_eval_verts = None  # list of (x, y, z) tuples in world space


def _prepare_body_eval(body):
    """Evaluate depsgraph and cache world-space vertex positions.

    Must be called before any ``_measure_*`` function in an operator's
    ``execute()``.  Call ``_cleanup_body_eval()`` when finished.
    """
    global _body_eval_verts
    import bpy
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = body.evaluated_get(depsgraph)
    eval_mesh = eval_obj.to_mesh()
    mat_w = body.matrix_world
    _body_eval_verts = [(mat_w @ v.co).to_tuple() for v in eval_mesh.vertices]
    eval_obj.to_mesh_clear()


def _cleanup_body_eval():
    """Clear the evaluated vertex cache."""
    global _body_eval_verts
    _body_eval_verts = None


def _get_body_wverts(body):
    """Return list of (x, y, z) world-space verts — cached or fallback."""
    if _body_eval_verts is not None:
        return _body_eval_verts
    # Fallback: raw mesh (slower, less accurate with shape keys)
    mat_w = body.matrix_world
    return [(mat_w @ v.co).to_tuple() for v in body.data.vertices]


def _measure_body_at_z(body, z_target, z_tol=0.03, x_limit=None):
    """Return (cx, cy, max_radius) of body cross-section at *z_target*.

    Scans evaluated mesh vertices within *z_tol* of z_target.
    If *x_limit* is set, only vertices with ``|x| <= x_limit`` are used
    (excludes arms for torso measurements).
    """
    wverts = _get_body_wverts(body)
    xs, ys = [], []
    for wx, wy, wz in wverts:
        if abs(wz - z_target) <= z_tol:
            if x_limit is not None and abs(wx) > x_limit:
                continue
            xs.append(wx)
            ys.append(wy)
    if not xs:
        return (0.0, 0.0, 0.12)  # fallback
    cx = (min(xs) + max(xs)) * 0.5
    cy = (min(ys) + max(ys)) * 0.5
    max_r = max(math.sqrt((x - cx) ** 2 + (y - cy) ** 2) for x, y in zip(xs, ys))
    return (cx, cy, max(max_r, 0.01))


def _measure_leg_at_z(body, z_target, side='left', z_tol=0.03):
    """Return (cx, cy, max_radius) for one leg at *z_target*.

    *side*: 'left' (x > 0) or 'right' (x < 0) in world space.
    """
    wverts = _get_body_wverts(body)
    xs, ys = [], []
    for wx, wy, wz in wverts:
        if abs(wz - z_target) <= z_tol:
            if side == 'left' and wx >= 0.0:
                xs.append(wx)
                ys.append(wy)
            elif side == 'right' and wx <= 0.0:
                xs.append(wx)
                ys.append(wy)
    if not xs:
        off = 0.08 if side == 'left' else -0.08
        return (off, 0.0, 0.06)
    cx = (min(xs) + max(xs)) * 0.5
    cy = (min(ys) + max(ys)) * 0.5
    max_r = max(math.sqrt((x - cx) ** 2 + (y - cy) ** 2) for x, y in zip(xs, ys))
    return (cx, cy, max(max_r, 0.01))


def _measure_arm_at_x(body, x_target, x_tol=0.03, arm_z=1.20, arm_z_tol=0.20):
    """Return (cy, cz, max_radius) for arm cross-section at *x_target* (YZ plane).

    Works for both sides: x_target > 0 for left arm, < 0 for right arm.
    *arm_z* / *arm_z_tol*: Z-filter to exclude torso vertices that happen
    to be at the same X position.
    """
    wverts = _get_body_wverts(body)
    ys, zs = [], []
    for wx, wy, wz in wverts:
        if abs(wx - x_target) <= x_tol:
            # Z-filter: only arm-height vertices
            if abs(wz - arm_z) <= arm_z_tol:
                ys.append(wy)
                zs.append(wz)
    if not ys:
        return (0.0, 1.20, 0.04)  # fallback
    cy = (min(ys) + max(ys)) * 0.5
    cz = (min(zs) + max(zs)) * 0.5
    max_r = max(math.sqrt((y - cy) ** 2 + (z - cz) ** 2)
                for y, z in zip(ys, zs))
    return (cy, cz, max(max_r, 0.01))


def _push_outside_body(context, garment, body, offset=0.003):
    """Shrinkwrap-project garment outside body so no vertices clip inside."""
    with context.temp_override(active_object=garment, object=garment,
                               selected_objects=[garment],
                               selected_editable_objects=[garment]):
        bpy.ops.object.modifier_add(type='SHRINKWRAP')
        sw = garment.modifiers[-1]
        sw.wrap_method = 'TARGET_PROJECT'
        sw.wrap_mode = 'OUTSIDE_SURFACE'
        sw.offset = offset
        sw.target = body
        bpy.ops.object.modifier_apply(modifier=sw.name)
    logger.info("Pushed '%s' outside body (offset=%.4f)", garment.name, offset)
