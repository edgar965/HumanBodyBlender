# SPDX-License-Identifier: GPL-3.0-or-later
#
# Cloth Builder for HumanBody addon.
# Adapts patterns from Bystedt's Cloth Builder for integrated cloth simulation.

import copy
import math
import random
import logging

import bpy
import bmesh
from mathutils import Vector
from bpy.props import (IntProperty, FloatProperty, BoolProperty, EnumProperty)

from .assetCreator.preview import (find_body_obj, _face_allowed_for_category,
                                   _grow_selection)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PIN_GROUP_NAME = 'pinned'
STIFFNESS_GROUP_NAME = 'stiffness'
SHRINKING_GROUP_NAME = 'shrinking'
PRESSURE_GROUP_NAME = 'pressure'
CLOTH_TRIANGULATION = 'hb_cloth_triangulation'
CLOTH_GARMENT_TAG = 'hb_cloth_garment'

# Garment region presets — z_min, z_max, include_arms, category (for face filter)
GARMENT_REGIONS = [
    ('TOP',       "Top",       "Shirt / Jacket / Sweater"),
    ('PANTS',     "Pants",     "Trousers / Jeans"),
    ('SKIRT',     "Skirt",     "Skirt / Dress bottom"),
    ('FULL',      "Full",      "Full body suit / Dress"),
    ('UNDERWEAR', "Underwear", "Underwear / Bikini"),
    ('SHOES',     "Shoes",     "Shoes / Boots"),
]

GARMENT_PRESETS = {
    'TOP':       {'z_min': 0.72, 'z_max': 1.42, 'arms': True,  'cat': 'Tops',      'grow': 2},
    'PANTS':     {'z_min': 0.06, 'z_max': 0.82, 'arms': False, 'cat': 'Bottoms',   'grow': 2},
    'SKIRT':     {'z_min': 0.40, 'z_max': 0.82, 'arms': False, 'cat': 'Bottoms',   'grow': 2},
    'FULL':      {'z_min': 0.06, 'z_max': 1.42, 'arms': True,  'cat': 'Full',      'grow': 2},
    'UNDERWEAR': {'z_min': 0.70, 'z_max': 0.88, 'arms': False, 'cat': 'Underwear', 'grow': 2},
    'SHOES':     {'z_min': -0.02, 'z_max': 0.12, 'arms': False, 'cat': None,       'grow': 4},
}


# ---------------------------------------------------------------------------
# Garment auto-creation from body region
# ---------------------------------------------------------------------------

def _create_garment(context, body, region_key):
    """Create a garment mesh from a body region.

    Simple approach: duplicate body faces, offset along normals, solidify.
    The body mesh topology already wraps each leg/arm correctly — no
    cylindrical math needed.  Looseness comes from the cloth simulation
    (shrink / pressure), not from geometry deformation.
    """
    preset = GARMENT_PRESETS[region_key]
    z_min = preset['z_min']
    z_max = preset['z_max']
    include_arms = preset['arms']
    category = preset['cat']

    depsgraph = context.evaluated_depsgraph_get()
    eval_obj = body.evaluated_get(depsgraph)
    eval_mesh = eval_obj.to_mesh()
    mat_w = body.matrix_world

    # --- Select garment faces by Z-range + category filter ---
    bm = bmesh.new()
    bm.from_mesh(eval_mesh)
    bm.faces.ensure_lookup_table()

    x_limit = 0.50 if include_arms else 0.30

    for f in bm.faces:
        f.select = False

    for face in bm.faces:
        center = mat_w @ face.calc_center_median()
        if z_min <= center.z <= z_max:
            if abs(center.x) <= x_limit:
                if category is None or _face_allowed_for_category(center, category):
                    face.select = True
            elif include_arms:
                if category is None or _face_allowed_for_category(center, category):
                    face.select = True

    _grow_selection(bm, preset.get('grow', 2))

    faces_to_delete = [f for f in bm.faces if not f.select]
    bmesh.ops.delete(bm, geom=faces_to_delete, context='FACES')

    if len(bm.faces) == 0:
        bm.free()
        eval_obj.to_mesh_clear()
        return None

    looseness = context.scene.humanbody_cloth_builder.looseness

    # --- Simple normal offset ---
    # The body mesh already wraps each leg individually, so pushing
    # along normals produces a garment that conforms to each limb.
    bm.verts.ensure_lookup_table()
    bm.normal_update()

    offset = 0.004 + looseness * 0.008  # 4mm (tight) to 20mm (loose)
    for v in bm.verts:
        v.co = v.co + v.normal * offset

    # Light smoothing to clean seam artifacts
    all_verts = list(bm.verts)
    smooth_iters = 3 + int(looseness * 5)
    for _ in range(smooth_iters):
        bmesh.ops.smooth_vert(bm, verts=all_verts, factor=0.5,
                              use_axis_x=True, use_axis_y=True,
                              use_axis_z=True)

    eval_obj.to_mesh_clear()

    # --- Auto-pin: identify top boundary vertices for waistband/neckline ---
    bm.edges.ensure_lookup_table()
    boundary_verts = set()
    for edge in bm.edges:
        if edge.is_boundary:
            boundary_verts.add(edge.verts[0].index)
            boundary_verts.add(edge.verts[1].index)

    # Find Z-range of boundary and pin the top portion
    if boundary_verts:
        bv_z = [(vi, (mat_w @ bm.verts[vi].co).z) for vi in boundary_verts]
        z_top = max(z for _, z in bv_z)
        z_bot = min(z for _, z in bv_z)
        z_span = z_top - z_bot
        # Pin boundary verts in the top 15% of the garment height
        pin_threshold = z_top - z_span * 0.15
        pin_indices = [vi for vi, z in bv_z if z >= pin_threshold]
    else:
        pin_indices = []

    # Create Blender object
    label = {k: v for k, v, _ in GARMENT_REGIONS}.get(region_key, region_key)
    mesh = bpy.data.meshes.new(f"hb_cloth_{label}")
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new(f"Cloth_{label}", mesh)
    context.collection.objects.link(obj)

    # Tag as cloth garment
    obj.data[CLOTH_GARMENT_TAG] = region_key
    obj.data['hb_pin_indices'] = pin_indices  # Store for _add_cloth

    # Copy transforms, smooth shading
    obj.matrix_world = body.matrix_world.copy()
    for poly in obj.data.polygons:
        poly.use_smooth = True

    # Solidify — fabric thickness
    thickness = 0.002 + min(looseness, 1.0) * 0.002
    mod_solid = obj.modifiers.new(name="hb_solidify", type='SOLIDIFY')
    mod_solid.thickness = thickness
    mod_solid.offset = 1.0

    # Parent to body
    obj.parent = body
    obj.matrix_parent_inverse = body.matrix_world.inverted()

    # Fabric material
    mat = bpy.data.materials.new(name=f"hb_cloth_{label}")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs['Base Color'].default_value = (0.25, 0.30, 0.45, 1.0)
        bsdf.inputs['Roughness'].default_value = 0.8
        bsdf.inputs['Specular IOR Level'].default_value = 0.2
    mat.diffuse_color = (0.7, 0.7, 0.75, 1.0)
    obj.data.materials.append(mat)

    logger.info("Created cloth garment '%s' (%d faces, offset=%.3f, looseness=%.2f)",
                label, len(mesh.polygons), offset, looseness)
    return obj


# ---------------------------------------------------------------------------
# Body-measurement helpers (for Primitive / Template cloth)
# ---------------------------------------------------------------------------

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


def _add_cloth_material(obj, label, color=(0.25, 0.30, 0.45, 1.0)):
    """Attach a default fabric material to *obj*."""
    mat = bpy.data.materials.new(name=f"hb_cloth_{label}")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs['Base Color'].default_value = color
        bsdf.inputs['Roughness'].default_value = 0.8
        bsdf.inputs['Specular IOR Level'].default_value = 0.2
    mat.diffuse_color = color
    obj.data.materials.append(mat)


def _bmesh_ring(bm, cx, cy, z, radius, segments):
    """Create a ring of vertices in *bm*, return list of BMVerts."""
    verts = []
    for i in range(segments):
        angle = 2.0 * math.pi * i / segments
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        verts.append(bm.verts.new((x, y, z)))
    return verts


def _bmesh_body_ring(bm, body, z, segments, gap, x_limit=None, z_tol=0.03):
    """Create a ring that conforms to the body cross-section at *z*.

    Unlike _bmesh_ring (perfect circle), this measures the body radius at
    each angular direction and places vertices to match the actual shape.
    """
    wverts = _get_body_wverts(body)

    pts = []
    for wx, wy, wz in wverts:
        if abs(wz - z) <= z_tol:
            if x_limit is not None and abs(wx) > x_limit:
                continue
            pts.append((wx, wy))

    if not pts:
        return _bmesh_ring(bm, 0.0, 0.0, z, 0.12 + gap, segments)

    cx = (min(p[0] for p in pts) + max(p[0] for p in pts)) * 0.5
    cy = (min(p[1] for p in pts) + max(p[1] for p in pts)) * 0.5

    # Measure max body radius per angular wedge
    wedge = math.pi / segments * 2.0
    radii = []
    for i in range(segments):
        angle = 2.0 * math.pi * i / segments
        max_r = 0.01
        for px, py in pts:
            dx = px - cx
            dy = py - cy
            r = math.sqrt(dx * dx + dy * dy)
            if r < 0.001:
                continue
            pt_angle = math.atan2(dy, dx)
            da = (pt_angle - angle + math.pi) % (2.0 * math.pi) - math.pi
            if abs(da) <= wedge:
                if r > max_r:
                    max_r = r
        radii.append(max_r)

    # Smooth to avoid jagged edges
    smoothed = list(radii)
    for _ in range(2):
        temp = list(smoothed)
        for i in range(segments):
            prev_r = temp[(i - 1) % segments]
            nxt_r = temp[(i + 1) % segments]
            smoothed[i] = temp[i] * 0.5 + (prev_r + nxt_r) * 0.25

    verts = []
    for i in range(segments):
        angle = 2.0 * math.pi * i / segments
        r = smoothed[i] + gap
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        verts.append(bm.verts.new((x, y, z)))
    return verts


def _bmesh_ring_yz(bm, x, cy, cz, radius, segments):
    """Create a ring in the YZ plane at *x* (for arm sleeves), return BMVerts."""
    verts = []
    for i in range(segments):
        angle = 2.0 * math.pi * i / segments
        y = cy + radius * math.cos(angle)
        z = cz + radius * math.sin(angle)
        verts.append(bm.verts.new((x, y, z)))
    return verts


def _bridge_rings(bm, ring_a, ring_b):
    """Create quad faces between two rings of same length."""
    n = len(ring_a)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new([ring_a[i], ring_a[j], ring_b[j], ring_b[i]])


def _finish_primitive(context, bm, name, body, pin_verts, thickness=0.002,
                      color=(0.25, 0.30, 0.45, 1.0)):
    """Convert bmesh to object, tag, solidify, parent, material. Return obj.

    *pin_verts* can be a list of BMVerts OR a list of integer indices.
    """
    # bm.free() im finally (Review 13.08.2026): Die sechzehn `_create_*`-
    # Funktionen legen den bmesh an und geben ihn NICHT frei — das erledigt
    # bewusst diese Funktion hier. Damit hängt die Freigabe aber daran, dass
    # nichts davor scheitert: `ensure_lookup_table`, die Pin-Indizes,
    # `meshes.new` oder `to_mesh` können werfen, und dann bleibt der bmesh im
    # Speicher liegen. Blender räumt ihn nicht auf; er hält den Platz bis zum
    # Beenden. Ein `finally` kostet nichts und schließt alle diese Wege.
    try:
        bm.verts.ensure_lookup_table()
        if pin_verts and isinstance(pin_verts[0], int):
            pin_indices = list(pin_verts)
        else:
            pin_indices = [v.index for v in pin_verts] if pin_verts else []

        mesh = bpy.data.meshes.new(name)
        bm.to_mesh(mesh)
    finally:
        bm.free()

    obj = bpy.data.objects.new(name, mesh)
    context.collection.objects.link(obj)

    # Tag
    obj.data[CLOTH_GARMENT_TAG] = name
    obj.data['hb_pin_indices'] = pin_indices

    # Smooth shading
    for poly in obj.data.polygons:
        poly.use_smooth = True

    # Solidify
    mod_solid = obj.modifiers.new(name="hb_solidify", type='SOLIDIFY')
    mod_solid.thickness = thickness
    mod_solid.offset = 1.0

    # Parent to body
    obj.parent = body
    obj.matrix_parent_inverse = body.matrix_world.inverted()

    # Material
    _add_cloth_material(obj, name, color)

    return obj


# ---------------------------------------------------------------------------
# Primitive creation functions
# ---------------------------------------------------------------------------

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


def _create_prim_disc(context, body, segments, radius, z_pos):
    """Flat disc with concentric rings at *z_pos* for good cloth topology."""
    cx, cy, _ = _measure_body_at_z(body, z_pos)
    bm = bmesh.new()

    n_concentric = max(3, int(radius / 0.03))
    center_v = bm.verts.new((cx, cy, z_pos))
    rings = []

    for ri in range(1, n_concentric + 1):
        t = ri / n_concentric
        r = radius * t
        ring = _bmesh_ring(bm, cx, cy, z_pos, r, segments)
        if ri == 1:
            n = len(ring)
            for i in range(n):
                j = (i + 1) % n
                bm.faces.new([center_v, ring[i], ring[j]])
        else:
            _bridge_rings(bm, rings[-1], ring)
        rings.append(ring)

    # Pin: outer ring
    pin_verts = rings[-1] if rings else []
    return _finish_primitive(context, bm, "Cloth_Prim_Disc", body, pin_verts,
                             color=(0.50, 0.45, 0.40, 1.0))


def _create_prim_sphere(context, body, segments, radius, z_pos):
    """UV sphere at body center at *z_pos*."""
    cx, cy, _ = _measure_body_at_z(body, z_pos)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segments,
                               v_segments=max(4, segments // 2),
                               radius=radius)
    for v in bm.verts:
        v.co.x += cx
        v.co.y += cy
        v.co.z += z_pos

    # Pin: top-most ring of vertices
    bm.verts.ensure_lookup_table()
    z_max = max(v.co.z for v in bm.verts)
    pin_verts = [v for v in bm.verts if v.co.z >= z_max - 0.005]

    return _finish_primitive(context, bm, "Cloth_Prim_Sphere", body, pin_verts,
                             color=(0.45, 0.35, 0.30, 1.0))


def _create_prim_oval_disc(context, body, segments, radius, z_pos):
    """Elliptical disc (1.6x wider in X) at *z_pos*."""
    cx, cy, _ = _measure_body_at_z(body, z_pos)
    bm = bmesh.new()

    n_concentric = max(3, int(radius / 0.03))
    center_v = bm.verts.new((cx, cy, z_pos))
    rings = []

    for ri in range(1, n_concentric + 1):
        t = ri / n_concentric
        verts = []
        for i in range(segments):
            angle = 2.0 * math.pi * i / segments
            x = cx + radius * 1.6 * t * math.cos(angle)
            y = cy + radius * t * math.sin(angle)
            verts.append(bm.verts.new((x, y, z_pos)))
        if ri == 1:
            n = len(verts)
            for i in range(n):
                j = (i + 1) % n
                bm.faces.new([center_v, verts[i], verts[j]])
        else:
            _bridge_rings(bm, rings[-1], verts)
        rings.append(verts)

    pin_verts = rings[-1] if rings else []
    return _finish_primitive(context, bm, "Cloth_Prim_OvalDisc", body, pin_verts,
                             color=(0.45, 0.40, 0.35, 1.0))


def _create_prim_triangle(context, body, segments, radius, z_pos):
    """Subdivided equilateral triangle at *z_pos*."""
    cx, cy, _ = _measure_body_at_z(body, z_pos)
    bm = bmesh.new()

    # Three corners of equilateral triangle (point up)
    corners = []
    for i in range(3):
        angle = 2.0 * math.pi * i / 3 - math.pi / 2
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        corners.append(bm.verts.new((x, y, z_pos)))

    bm.faces.new(corners)

    # Subdivide for cloth sim resolution
    cuts = max(2, segments // 4)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=cuts)

    # Pin: the 3 original corner vertices (may have shifted index after subdiv)
    bm.verts.ensure_lookup_table()
    # Find outermost verts as pin
    dists = []
    for v in bm.verts:
        d = math.sqrt((v.co.x - cx) ** 2 + (v.co.y - cy) ** 2)
        dists.append((d, v))
    dists.sort(key=lambda x: -x[0])
    pin_verts = [v for _, v in dists[:3]]

    return _finish_primitive(context, bm, "Cloth_Prim_Triangle", body, pin_verts,
                             color=(0.40, 0.45, 0.35, 1.0))


def _create_prim_puffer(context, body, segments, length, count):
    """Multiple half-sphere domes arranged in rows around the torso.

    *count*: number of rows.  Columns are auto-calculated from circumference.
    """
    shoulder_z = 1.30
    gap = 0.018
    row_height = length / max(count, 1)

    bm = bmesh.new()
    all_pin_verts = []
    dome_rings_n = 4
    dome_segs = max(8, segments // 4)

    for row_idx in range(count):
        z_center = shoulder_z - (row_idx + 0.5) * row_height
        cx_body, cy_body, r_body = _measure_body_at_z(body, z_center)
        r_base = r_body + gap

        circumference = 2.0 * math.pi * r_base
        puff_r = row_height * 0.45
        n_cols = max(4, int(circumference / (puff_r * 2.2)))

        for col_idx in range(n_cols):
            angle = 2.0 * math.pi * col_idx / n_cols
            # Stagger odd rows by half a column
            if row_idx % 2 == 1:
                angle += math.pi / n_cols
            px = cx_body + r_base * math.cos(angle)
            py = cy_body + r_base * math.sin(angle)

            # Build half-sphere dome pointing outward from body center
            dome_dir_x = math.cos(angle)
            dome_dir_y = math.sin(angle)

            dome_rings = []
            for ri in range(dome_rings_n + 1):
                t = ri / dome_rings_n
                phi = t * math.pi * 0.5  # 0 to pi/2
                ring_r = puff_r * math.cos(phi)
                # Dome rises outward from body surface
                rise = puff_r * math.sin(phi)
                rcx = px + dome_dir_x * rise
                rcy = py + dome_dir_y * rise

                if ring_r < 0.002:
                    # Cap vertex
                    cap = bm.verts.new((rcx, rcy, z_center))
                    if dome_rings:
                        prev = dome_rings[-1]
                        np_ = len(prev)
                        for k in range(np_):
                            j = (k + 1) % np_
                            bm.faces.new([prev[k], prev[j], cap])
                    break

                ring = []
                for si in range(dome_segs):
                    a = 2.0 * math.pi * si / dome_segs
                    # Ring perpendicular to dome direction
                    rx = rcx + ring_r * (-dome_dir_y * math.cos(a))
                    ry = rcy + ring_r * (dome_dir_x * math.cos(a))
                    rz = z_center + ring_r * math.sin(a)
                    ring.append(bm.verts.new((rx, ry, rz)))

                if ri == 0 and row_idx == 0:
                    all_pin_verts.extend(ring)

                if dome_rings:
                    _bridge_rings(bm, dome_rings[-1], ring)
                dome_rings.append(ring)

    return _finish_primitive(context, bm, "Cloth_Prim_Puffer", body, all_pin_verts,
                             color=(0.35, 0.30, 0.45, 1.0))


# ---------------------------------------------------------------------------
# Template creation functions (measured radii per ring, high density)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Primitive / Template PropertyGroups
# ---------------------------------------------------------------------------

PRIMITIVE_TYPES = [
    ('PRIM_SKIRT',      "Skirt",       "Open cone from waist"),
    ('PRIM_PANTS',      "Pants",       "Two tubes for legs"),
    ('PRIM_TOP',        "Top",         "Cylinder around torso"),
    ('PRIM_ARMS',       "Arms",        "Tubes around both arms"),
    ('PRIM_NECK',       "Neck",        "Tube around neck"),
    ('PRIM_HEAD',       "Head",        "Cap around head"),
    ('PRIM_SHOES',      "Shoes",       "Tubes around feet"),
    ('PRIM_DISC',       "Disc",        "Flat circular disc"),
    ('PRIM_SPHERE',     "Sphere",      "UV sphere"),
    ('PRIM_OVAL_DISC',  "Oval Disc",   "Elliptical disc"),
    ('PRIM_TRIANGLE',   "Triangle",    "Subdivided triangle"),
    ('PRIM_PUFFER',     "Puffer",      "Half-sphere domes (down jacket)"),
]

TEMPLATE_TYPES = [
    ('TPL_TSHIRT', "T-Shirt", "Torso + arm sleeves"),
    ('TPL_PANTS',  "Pants",   "Body-conforming trousers"),
    ('TPL_SKIRT',  "Skirt",   "Measured waist skirt"),
    ('TPL_DRESS',  "Dress",   "Torso + skirt combo"),
]


class HumanBodyClothPrimitiveProps(bpy.types.PropertyGroup):
    prim_type: EnumProperty(
        name="Primitive",
        description="Type of primitive cloth shape",
        items=PRIMITIVE_TYPES,
        default='PRIM_SKIRT',
    )
    segments: IntProperty(
        name="Segments",
        description="Vertices per ring",
        default=32, min=12, max=64,
    )
    prim_length: FloatProperty(
        name="Length",
        description="Length of the garment along Z",
        default=0.40, min=0.05, max=1.5, step=1,
        precision=2, subtype='DISTANCE',
    )
    prim_flare: FloatProperty(
        name="Flare",
        description="Outward flare factor (skirt only)",
        default=0.3, min=0.0, max=2.0, step=5,
        precision=2,
    )
    prim_radius: FloatProperty(
        name="Radius",
        description="Radius for disc / sphere / triangle",
        default=0.15, min=0.02, max=1.0, step=1,
        precision=3, subtype='DISTANCE',
    )
    prim_z: FloatProperty(
        name="Z Position",
        description="Vertical position for disc / sphere / triangle",
        default=1.00, min=-0.05, max=1.80, step=1,
        precision=2, subtype='DISTANCE',
    )
    prim_count: IntProperty(
        name="Rows",
        description="Number of dome rows (puffer)",
        default=4, min=1, max=12,
    )


class HumanBodyClothTemplateProps(bpy.types.PropertyGroup):
    template_type: EnumProperty(
        name="Template",
        description="Type of template garment",
        items=TEMPLATE_TYPES,
        default='TPL_TSHIRT',
    )
    segments: IntProperty(
        name="Segments",
        description="Vertices per ring",
        default=32, min=16, max=64,
    )
    tightness: FloatProperty(
        name="Tightness",
        description="How tight the garment fits (0 = loose, 1 = skin-tight)",
        default=0.5, min=0.0, max=1.0, step=5,
        precision=2,
    )
    top_extend: FloatProperty(
        name="Top",
        description="Extend garment upward (positive = higher)",
        default=0.0, min=-0.30, max=0.30, step=1,
        precision=2, subtype='DISTANCE',
    )
    bottom_extend: FloatProperty(
        name="Bottom",
        description="Extend garment downward (positive = longer)",
        default=0.0, min=-0.30, max=0.50, step=1,
        precision=2, subtype='DISTANCE',
    )


# ---------------------------------------------------------------------------
# Primitive / Template Operators
# ---------------------------------------------------------------------------

class HUMANBODY_OT_cloth_prim_create(bpy.types.Operator):
    """Create a primitive cloth shape around the body"""
    bl_idname = "humanbody.cloth_prim_create"
    bl_label = "Create Primitive"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return find_body_obj(context) is not None

    def execute(self, context):
        body = find_body_obj(context)
        props = context.scene.humanbody_cloth_primitive
        pt = props.prim_type
        segs = props.segments
        length = props.prim_length
        flare = props.prim_flare
        radius = props.prim_radius
        z_pos = props.prim_z
        count = props.prim_count

        _prepare_body_eval(body)
        try:
            creators = {
                'PRIM_SKIRT':     lambda: _create_prim_skirt(context, body, segs, length, flare),
                'PRIM_TOP':       lambda: _create_prim_top(context, body, segs, length),
                'PRIM_PANTS':     lambda: _create_prim_pants(context, body, segs, length),
                'PRIM_ARMS':      lambda: _create_prim_arms(context, body, segs, length),
                'PRIM_NECK':      lambda: _create_prim_neck(context, body, segs, length),
                'PRIM_HEAD':      lambda: _create_prim_head(context, body, segs, length),
                'PRIM_SHOES':     lambda: _create_prim_shoes(context, body, segs, length),
                'PRIM_DISC':      lambda: _create_prim_disc(context, body, segs, radius, z_pos),
                'PRIM_SPHERE':    lambda: _create_prim_sphere(context, body, segs, radius, z_pos),
                'PRIM_OVAL_DISC': lambda: _create_prim_oval_disc(context, body, segs, radius, z_pos),
                'PRIM_TRIANGLE':  lambda: _create_prim_triangle(context, body, segs, radius, z_pos),
                'PRIM_PUFFER':    lambda: _create_prim_puffer(context, body, segs, length, count),
            }

            garment = creators.get(pt, creators['PRIM_SKIRT'])()
        finally:
            _cleanup_body_eval()

        if garment is None:
            self.report({'ERROR'}, "Failed to create primitive")
            return {'CANCELLED'}

        _add_cloth(context, garment)
        _add_collision(context, body)
        self.report({'INFO'}, f"Created {pt}: {garment.name}")
        return {'FINISHED'}


class HUMANBODY_OT_cloth_tpl_create(bpy.types.Operator):
    """Create a template garment around the body"""
    bl_idname = "humanbody.cloth_tpl_create"
    bl_label = "Create Template"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return find_body_obj(context) is not None

    def execute(self, context):
        body = find_body_obj(context)
        props = context.scene.humanbody_cloth_template
        tt = props.template_type
        segs = props.segments
        # Tightness → gap: 1.0 (tight) = 0.005, 0.0 (loose) = 0.025
        gap = 0.005 + (1.0 - props.tightness) * 0.020
        t_ext = props.top_extend
        b_ext = props.bottom_extend

        _prepare_body_eval(body)
        try:
            creators = {
                'TPL_TSHIRT': lambda: _create_tpl_tshirt(context, body, segs, gap, t_ext, b_ext),
                'TPL_PANTS':  lambda: _create_tpl_pants(context, body, segs, gap, t_ext, b_ext),
                'TPL_SKIRT':  lambda: _create_tpl_skirt(context, body, segs, gap, t_ext, b_ext),
                'TPL_DRESS':  lambda: _create_tpl_dress(context, body, segs, gap, t_ext, b_ext),
            }

            garment = creators.get(tt, creators['TPL_TSHIRT'])()
        finally:
            _cleanup_body_eval()

        if garment is None:
            self.report({'ERROR'}, "Failed to create template")
            return {'CANCELLED'}

        # Push outside body to prevent clipping
        _push_outside_body(context, garment, body, offset=max(gap, 0.005))

        _add_cloth(context, garment)
        _add_collision(context, body)
        self.report({'INFO'}, f"Created {tt}: {garment.name}")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# PropertyGroup
# ---------------------------------------------------------------------------

def _on_setting_update(self, context):
    _sync_modifier_settings(context)


class HumanBodyClothBuilderProps(bpy.types.PropertyGroup):
    garment_region: EnumProperty(
        name="Garment",
        description="Body region for garment creation",
        items=GARMENT_REGIONS,
        default='TOP',
    )
    looseness: FloatProperty(
        name="Looseness",
        description="How loose the garment fits (0 = skin-tight, 2 = very loose / cylindrical)",
        default=0.5, min=0.0, max=2.0, soft_max=1.5, step=5,
        precision=2,
    )
    simulation_frames: IntProperty(
        name="Simulation Frames",
        description="End frame for cloth simulation cache",
        default=5000, min=1, soft_max=10000,
        update=_on_setting_update,
    )
    sim_quality: IntProperty(
        name="Sim Quality",
        description="Cloth simulation quality steps",
        default=4, min=1, max=20, soft_max=5,
        update=_on_setting_update,
    )
    collision_quality: IntProperty(
        name="Collision Quality",
        description="Collision detection quality",
        default=2, min=1, max=20, soft_max=5,
        update=_on_setting_update,
    )
    collision_distance: FloatProperty(
        name="Collision Distance",
        description="Inner and outer collision distance",
        default=0.005, min=0.0, max=1.0, step=0.1,
        precision=4,
        update=_on_setting_update,
    )
    use_triangulate: BoolProperty(
        name="Triangulate",
        description="Add triangulate modifier after cloth for better simulation",
        default=True,
    )
    pin_scale: FloatProperty(
        name="Pin Scale",
        description="Display size of pin empties",
        default=0.1, min=0.001, max=1.0,
    )
    pin_shape: EnumProperty(
        name="Pin Shape",
        description="Display shape for pin empties",
        items=[
            ('PLAIN_AXES', "Plain Axes", ""),
            ('ARROWS', "Arrows", ""),
            ('CIRCLE', "Circle", ""),
            ('CUBE', "Cube", ""),
            ('SPHERE', "Sphere", ""),
            ('CONE', "Cone", ""),
        ],
        default='PLAIN_AXES',
    )
    fit_offset: FloatProperty(
        name="Fit Offset",
        description="Shrinkwrap offset distance for fit-to-body",
        default=0.01, min=0.0, max=0.5, step=0.1,
        precision=4,
    )
    fit_corrective_iters: IntProperty(
        name="Corrective Iterations",
        description="Corrective smooth iterations for fit-to-body",
        default=5, min=0, max=50,
    )


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _get_modifiers(mod_type, objects=None):
    """Return list of modifiers of a given type from objects."""
    result = []
    if objects is None:
        objects = bpy.context.selected_objects
    for obj in objects:
        if not hasattr(obj, 'modifiers'):
            continue
        for mod in obj.modifiers:
            if mod.type == mod_type:
                result.append(mod)
    return result


def _has_modifier(obj, mod_type):
    """Check if object has a modifier of given type."""
    if not hasattr(obj, 'modifiers'):
        return False
    for mod in obj.modifiers:
        if mod.type == mod_type:
            return True
    return False


def _add_default_vertex_groups(obj):
    """Create pinned/stiffness/shrinking/pressure vertex groups and assign
    them to the cloth modifier."""
    group_names = [PIN_GROUP_NAME, STIFFNESS_GROUP_NAME,
                   SHRINKING_GROUP_NAME, PRESSURE_GROUP_NAME]

    for name in group_names:
        if name not in obj.vertex_groups:
            vg = obj.vertex_groups.new(name=name)
            # Fill pressure group with weight 1.0 on all verts
            if name == PRESSURE_GROUP_NAME:
                all_indices = list(range(len(obj.data.vertices)))
                vg.add(all_indices, 1.0, 'REPLACE')

    # Assign groups to cloth modifier
    cloth_mods = _get_modifiers('CLOTH', [obj])
    if cloth_mods:
        mod = cloth_mods[0]
        mod.settings.vertex_group_mass = PIN_GROUP_NAME
        mod.settings.vertex_group_bending = STIFFNESS_GROUP_NAME
        mod.settings.vertex_group_shrink = SHRINKING_GROUP_NAME
        mod.settings.vertex_group_pressure = PRESSURE_GROUP_NAME


def _sync_modifier_settings(context):
    """Push PropertyGroup values to all Cloth/Collision modifiers in scene."""
    props = context.scene.humanbody_cloth_builder
    body = find_body_obj(context)

    for obj in context.scene.objects:
        if not hasattr(obj, 'modifiers'):
            continue

        for mod in obj.modifiers:
            if mod.type == 'CLOTH':
                mod.point_cache.frame_end = props.simulation_frames
                mod.settings.quality = props.sim_quality
                mod.collision_settings.collision_quality = props.collision_quality
                mod.collision_settings.distance_min = props.collision_distance
                mod.collision_settings.self_distance_min = props.collision_distance

            if mod.type == 'COLLISION' and obj.collision:
                obj.collision.thickness_outer = props.collision_distance
                obj.collision.thickness_inner = props.collision_distance


def _find_body_armature(body):
    """Return the armature object driving *body*, or None."""
    if body.parent and body.parent.type == 'ARMATURE':
        return body.parent
    for mod in body.modifiers:
        if mod.type == 'ARMATURE' and mod.object:
            return mod.object
    return None


def _transfer_bone_weights(garment, body, only_indices=None):
    """Transfer vertex-group weights from *body* to *garment* via KDTree.

    For each garment vertex (or only those in *only_indices*), finds the
    nearest body vertex (evaluated mesh) and copies all bone-weight groups.

    Transferring only to pinned vertices prevents the armature from
    deforming cloth-simulated areas (e.g., skirt below waist).
    """
    from mathutils.kdtree import KDTree

    # Build KDTree from ORIGINAL body vertices so indices match
    # body.data.vertices for weight lookup.  The evaluated mesh may have
    # more vertices (Subdivision, etc.) causing index mismatches.
    mat_body = body.matrix_world
    n_body = len(body.data.vertices)
    kd = KDTree(n_body)
    for i, v in enumerate(body.data.vertices):
        kd.insert(mat_body @ v.co, i)
    kd.balance()

    # Map body vertex group indices to names
    body_groups = {vg.index: vg.name for vg in body.vertex_groups}

    # Create matching vertex groups on garment
    for _, name in body_groups.items():
        if name not in garment.vertex_groups:
            garment.vertex_groups.new(name=name)

    garment_groups = {vg.name: vg for vg in garment.vertex_groups}
    mat_garment = garment.matrix_world

    # Determine which garment vertices to process
    if only_indices is not None:
        target_set = set(only_indices)
    else:
        target_set = None

    # For each target garment vertex, copy weights from nearest body vertex
    for gv in garment.data.vertices:
        if target_set is not None and gv.index not in target_set:
            continue
        gv_world = mat_garment @ gv.co
        _, body_vi, _ = kd.find(gv_world)

        body_vert = body.data.vertices[body_vi]
        for vge in body_vert.groups:
            group_name = body_groups.get(vge.group)
            if group_name and group_name in garment_groups:
                garment_groups[group_name].add([gv.index], vge.weight, 'REPLACE')

    n_transferred = len(target_set) if target_set else len(garment.data.vertices)
    logger.info("Transferred bone weights to %d/%d verts on '%s'",
                n_transferred, len(garment.data.vertices), garment.name)


def _add_armature_to_garment(context, garment, body):
    """Copy the body's armature setup to the garment so it follows animation.

    Adds an ARMATURE modifier (before Cloth) and transfers bone weights
    to all vertices.  The cloth sim's pin group controls which vertices
    are physically simulated vs armature-only.
    """
    rig = _find_body_armature(body)
    if rig is None:
        return

    # Already has an armature modifier → skip
    if _has_modifier(garment, 'ARMATURE'):
        return

    # Parent garment to armature (same as body)
    garment.parent = rig
    garment.matrix_parent_inverse = rig.matrix_world.inverted()

    # Add ARMATURE modifier
    arm_mod = garment.modifiers.new("HumanBody_Rig", "ARMATURE")
    arm_mod.use_vertex_groups = True
    arm_mod.use_deform_preserve_volume = True
    arm_mod.object = rig

    # Move armature modifier to first position (before cloth, solidify, etc.)
    with context.temp_override(object=garment):
        bpy.ops.object.modifier_move_to_index(modifier=arm_mod.name, index=0)

    # Transfer bone weights to ALL vertices
    _transfer_bone_weights(garment, body)


def _add_cloth(context, garment):
    """Add CLOTH modifier to garment + auto-add COLLISION to body."""
    if _has_modifier(garment, 'CLOTH'):
        return

    props = context.scene.humanbody_cloth_builder

    # Gradient pin: pinned vertices = 1.0, all others get a weight based on
    # distance from the pin ring so the garment follows the armature during
    # animation while still allowing some cloth simulation for wrinkles.
    pin_indices = list(garment.data.get('hb_pin_indices', []))
    if PIN_GROUP_NAME not in garment.vertex_groups:
        garment.vertex_groups.new(name=PIN_GROUP_NAME)
    vg = garment.vertex_groups[PIN_GROUP_NAME]
    if pin_indices:
        pin_set = set(pin_indices)
        # Find Z range of pin ring to compute gradient
        pin_zs = [garment.data.vertices[vi].co.z for vi in pin_indices
                   if vi < len(garment.data.vertices)]
        pin_z = max(pin_zs) if pin_zs else 1.0
        all_zs = [v.co.z for v in garment.data.vertices]
        z_min = min(all_zs) if all_zs else 0.0
        z_span = max(pin_z - z_min, 0.01)

        vg.add(pin_indices, 1.0, 'REPLACE')
        # Non-pinned: gradient from pin_z (0.8) down to z_min (0.15)
        for v in garment.data.vertices:
            if v.index in pin_set:
                continue
            t = max(0.0, (v.co.z - z_min) / z_span)  # 0 at bottom, 1 at pin
            weight = 0.15 + t * 0.65  # 0.15 → 0.80
            vg.add([v.index], weight, 'REPLACE')

    # Add cloth modifier
    with context.temp_override(active_object=garment, object=garment,
                               selected_objects=[garment],
                               selected_editable_objects=[garment]):
        bpy.ops.object.modifier_add(type='CLOTH')

    # Configure cloth settings (like Bystedt)
    cloth_mods = _get_modifiers('CLOTH', [garment])
    if cloth_mods:
        mod = cloth_mods[0]
        mod.settings.shrink_max = 0.5
        # Enable self-collision
        mod.collision_settings.use_self_collision = True
        mod.collision_settings.self_distance_min = 0.005

    # Add default vertex groups
    _add_default_vertex_groups(garment)

    # Sync global settings
    _sync_modifier_settings(context)

    # Triangulate modifier after cloth
    if props.use_triangulate:
        tri = garment.modifiers.get(CLOTH_TRIANGULATION)
        if not tri:
            tri = garment.modifiers.new(name=CLOTH_TRIANGULATION,
                                        type='TRIANGULATE')
            tri.quad_method = 'LONGEST_DIAGONAL'
            tri.keep_custom_normals = True

    # Auto-add collision to body
    body = find_body_obj(context)
    if body:
        _add_collision(context, body)
        # Auto-add armature if body has one (for animation tracking)
        _add_armature_to_garment(context, garment, body)

    logger.info("Added cloth to: %s", garment.name)


def _add_collision(context, body):
    """Add COLLISION modifier to body (idempotent)."""
    if _has_modifier(body, 'COLLISION'):
        return

    with context.temp_override(active_object=body, object=body,
                               selected_objects=[body],
                               selected_editable_objects=[body]):
        bpy.ops.object.modifier_add(type='COLLISION')

    if body.collision:
        body.collision.use_normal = True

    _sync_modifier_settings(context)
    logger.info("Added collision to: %s", body.name)


def _remove_cloth(context, garment):
    """Remove CLOTH + TRIANGULATE modifiers from garment."""
    to_remove = []
    for mod in garment.modifiers:
        if mod.type == 'CLOTH' or mod.name == CLOTH_TRIANGULATION:
            to_remove.append(mod.name)

    for name in to_remove:
        mod = garment.modifiers.get(name)
        if mod:
            garment.modifiers.remove(mod)

    logger.info("Removed cloth from: %s", garment.name)


def _run_simulation(context):
    """Set end frame and play animation for cloth sim."""
    props = context.scene.humanbody_cloth_builder
    context.scene.frame_end = props.simulation_frames
    _sync_modifier_settings(context)
    bpy.context.scene.sync_mode = 'NONE'
    bpy.ops.screen.animation_play()


def _stop_simulation(context):
    """Stop animation playback."""
    if bpy.context.screen.is_animation_playing:
        bpy.ops.screen.animation_play()


def _reset_simulation(context):
    """Jump to frame 1 and reset pin locations."""
    bpy.ops.screen.frame_jump(end=False)
    _reset_pin_locations(context)


def _reset_pin_locations(context):
    """Reset hook modifiers and pin transforms to deltas."""
    for obj in context.scene.objects:
        if not hasattr(obj, 'modifiers'):
            continue

        hook_mods = [m for m in obj.modifiers if m.type == 'HOOK']
        if not hook_mods:
            continue

        with context.temp_override(active_object=obj, object=obj,
                                   selected_objects=[obj],
                                   selected_editable_objects=[obj],
                                   edit_object=obj,
                                   mode='EDIT_MESH'):
            bpy.ops.object.mode_set(mode='EDIT')
            for mod in hook_mods:
                try:
                    bpy.ops.object.hook_reset(modifier=mod.name)
                except RuntimeError:
                    pass
            bpy.ops.object.mode_set(mode='OBJECT')

        # Reset pin empties
        for mod in hook_mods:
            pin = mod.object
            if pin and pin.get('is_pin'):
                with context.temp_override(active_object=pin, object=pin,
                                           selected_objects=[pin],
                                           selected_editable_objects=[pin]):
                    bpy.ops.object.transforms_to_deltas(mode='ALL')


def _add_pin(context):
    """Add a pin to selected vertices in edit mode."""
    garment = context.active_object
    if not garment or garment.type != 'MESH':
        return

    props = context.scene.humanbody_cloth_builder

    # Assign selected verts to pinned group
    if PIN_GROUP_NAME not in garment.vertex_groups:
        garment.vertex_groups.new(name=PIN_GROUP_NAME)

    # Set pinned group as active and assign selected verts
    vg_index = garment.vertex_groups[PIN_GROUP_NAME].index
    garment.vertex_groups.active_index = vg_index
    bpy.ops.object.vertex_group_assign()

    # Snap cursor to selection
    orig_cursor = copy.copy(context.scene.cursor.location)
    bpy.ops.view3d.snap_cursor_to_selected()

    # Switch to object mode and create empty
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.empty_add(type=props.pin_shape, align='WORLD')

    pin = context.active_object
    pin.name = "Pin"
    pin['is_pin'] = True
    pin.empty_display_size = props.pin_scale
    pin.empty_display_type = props.pin_shape

    # Restore cursor
    context.scene.cursor.location = orig_cursor

    # Convert transforms to deltas
    bpy.ops.object.transforms_to_deltas(mode='ALL')

    # Select garment, go to edit mode, add hook
    context.view_layer.objects.active = garment
    garment.select_set(True)
    pin.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.object.hook_add_selob(use_bone=False)

    # Move hook modifiers to index 0
    hook_mods = [m for m in garment.modifiers if m.type == 'HOOK']
    for mod in hook_mods:
        with context.temp_override(active_object=garment, object=garment):
            bpy.ops.object.modifier_move_to_index(
                modifier=mod.name, index=0)

    # Ensure cloth modifier uses pin group
    cloth_mods = _get_modifiers('CLOTH', [garment])
    if cloth_mods:
        cloth_mods[0].settings.vertex_group_mass = PIN_GROUP_NAME


def _get_hook_modifiers_using_pin(obj, pin_empty):
    """Find hook modifiers on obj that reference pin_empty."""
    result = []
    for mod in obj.modifiers:
        if mod.type == 'HOOK' and mod.object == pin_empty:
            result.append(mod)
    return result


def _remove_selected_pins(context):
    """Remove selected pin empties and their hook modifiers."""
    pins_to_remove = [o for o in context.selected_objects
                      if o.get('is_pin')]

    for pin in pins_to_remove:
        # Find all objects that have hook modifiers using this pin
        for obj in context.scene.objects:
            if not hasattr(obj, 'modifiers'):
                continue
            hooks = _get_hook_modifiers_using_pin(obj, pin)
            for mod in hooks:
                # Remove verts from pinned group
                if PIN_GROUP_NAME in obj.vertex_groups:
                    vg = obj.vertex_groups[PIN_GROUP_NAME]
                    try:
                        vg.remove(list(mod.vertex_indices))
                    except Exception:
                        pass
                obj.modifiers.remove(mod)

        bpy.data.objects.remove(pin, do_unlink=True)


def _clear_pins(context, garment):
    """Remove all pins for a garment."""
    pins = []
    for mod in garment.modifiers:
        if mod.type == 'HOOK' and mod.object and mod.object.get('is_pin'):
            pins.append(mod.object)

    for pin in pins:
        hooks = _get_hook_modifiers_using_pin(garment, pin)
        for mod in hooks:
            garment.modifiers.remove(mod)
        bpy.data.objects.remove(pin, do_unlink=True)

    # Clear pinned vertex group
    if PIN_GROUP_NAME in garment.vertex_groups:
        vg = garment.vertex_groups[PIN_GROUP_NAME]
        all_indices = list(range(len(garment.data.vertices)))
        vg.remove(all_indices)


def _fit_to_body(context, garment, body):
    """Shrinkwrap garment to body + corrective smooth, then apply."""
    props = context.scene.humanbody_cloth_builder

    with context.temp_override(active_object=garment, object=garment,
                               selected_objects=[garment],
                               selected_editable_objects=[garment]):
        # Shrinkwrap
        bpy.ops.object.modifier_add(type='SHRINKWRAP')
        sw = garment.modifiers[-1]
        sw.wrap_method = 'TARGET_PROJECT'
        sw.wrap_mode = 'OUTSIDE_SURFACE'
        sw.offset = props.fit_offset
        sw.target = body

        # Corrective smooth — bind with shrinkwrap hidden
        sw.show_viewport = False
        bpy.ops.object.modifier_add(type='CORRECTIVE_SMOOTH')
        cs = garment.modifiers[-1]
        cs.rest_source = 'BIND'
        cs.iterations = props.fit_corrective_iters
        bpy.ops.object.correctivesmooth_bind(modifier=cs.name)
        sw.show_viewport = True

        # Apply both
        bpy.ops.object.modifier_apply(modifier=sw.name)
        bpy.ops.object.modifier_apply(modifier=cs.name)

    logger.info("Fit garment '%s' to body", garment.name)


def _apply_base(context, garment):
    """Bake cloth simulation into mesh (apply cloth modifier as shape)."""
    cloth_mods = _get_modifiers('CLOTH', [garment])
    if not cloth_mods:
        return

    with context.temp_override(active_object=garment, object=garment,
                               selected_objects=[garment],
                               selected_editable_objects=[garment]):
        # Apply cloth as shape key
        bpy.ops.object.modifier_apply_as_shapekey(
            keep_modifier=False, modifier=cloth_mods[0].name)

        # Set cloth shape key value to 1, basis to 0
        if garment.data.shape_keys and garment.data.shape_keys.key_blocks:
            for kb in garment.data.shape_keys.key_blocks:
                kb.value = 0.0
            garment.data.shape_keys.key_blocks[-1].value = 1.0

            # Apply the shape key (flatten)
            bpy.ops.object.shape_key_move(type='BOTTOM')
            while len(garment.data.shape_keys.key_blocks) > 1:
                garment.active_shape_key_index = 0
                bpy.ops.object.shape_key_remove()
            bpy.ops.object.shape_key_remove()

    # Remove triangulate too
    tri = garment.modifiers.get(CLOTH_TRIANGULATION)
    if tri:
        garment.modifiers.remove(tri)

    # Reset pins
    _reset_pin_locations(context)

    logger.info("Applied cloth base on: %s", garment.name)


def _shake_cloth(context, garment):
    """Shrink then expand cloth to create random wrinkles."""
    cloth_mods = _get_modifiers('CLOTH', [garment])
    if not cloth_mods:
        return

    mod = cloth_mods[0]
    orig_min = mod.settings.shrink_min
    orig_max = mod.settings.shrink_max

    # Random shrink/expand
    mod.settings.shrink_min = random.uniform(-0.3, -0.05)
    mod.settings.shrink_max = random.uniform(0.05, 0.3)

    logger.info("Shake cloth on: %s (shrink: %.3f..%.3f)",
                garment.name, mod.settings.shrink_min, mod.settings.shrink_max)


# ---------------------------------------------------------------------------
# Poll / find helpers
# ---------------------------------------------------------------------------

def _find_garment(context):
    """Find a garment (non-HumanBody mesh) — active object first, then
    selected objects, then children of the HumanBody, then any scene mesh."""
    obj = context.active_object
    if obj and obj.type == 'MESH' and not obj.data.get("humanbody"):
        return obj
    for o in context.selected_objects:
        if o.type == 'MESH' and not o.data.get("humanbody"):
            return o
    # Fallback: check children of HumanBody
    body = find_body_obj(context)
    if body:
        for child in body.children:
            if child.type == 'MESH' and not child.data.get("humanbody"):
                return child
    # Last resort: any non-HumanBody mesh in scene
    for o in context.scene.objects:
        if o.type == 'MESH' and not o.data.get("humanbody"):
            return o
    return None


def _poll_garment(context):
    """A non-HumanBody mesh is active or selected."""
    return _find_garment(context) is not None


def _poll_garment_and_body(context):
    """A garment is available AND a HumanBody exists."""
    if not _poll_garment(context):
        return False
    return find_body_obj(context) is not None


def _poll_garment_has_cloth(context):
    """A garment with cloth modifier is available."""
    g = _find_garment(context)
    if not g:
        return False
    return _has_modifier(g, 'CLOTH')


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class HUMANBODY_OT_cloth_add(bpy.types.Operator):
    """Create garment from body region and add cloth modifier"""
    bl_idname = "humanbody.cloth_add"
    bl_label = "Add Cloth"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return find_body_obj(context) is not None

    def execute(self, context):
        props = context.scene.humanbody_cloth_builder
        garment = _find_garment(context)

        # Auto-create garment if none exists
        if garment is None or _has_modifier(garment, 'CLOTH'):
            body = find_body_obj(context)
            garment = _create_garment(context, body, props.garment_region)
            if garment is None:
                self.report({'ERROR'}, "Failed to create garment")
                return {'CANCELLED'}

        _add_cloth(context, garment)
        self.report({'INFO'}, f"Added cloth to {garment.name}")
        return {'FINISHED'}


class HUMANBODY_OT_cloth_remove(bpy.types.Operator):
    """Remove cloth modifier from garment"""
    bl_idname = "humanbody.cloth_remove"
    bl_label = "Remove Cloth"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _poll_garment_has_cloth(context)

    def execute(self, context):
        garment = _find_garment(context)
        _remove_cloth(context, garment)
        self.report({'INFO'}, "Cloth removed")
        return {'FINISHED'}


class HUMANBODY_OT_cloth_rebuild(bpy.types.Operator):
    """Remove current garment and create a new one from selected region"""
    bl_idname = "humanbody.cloth_rebuild"
    bl_label = "Rebuild Garment"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return find_body_obj(context) is not None

    def execute(self, context):
        props = context.scene.humanbody_cloth_builder

        # Remove existing cloth garments
        to_remove = [o for o in context.scene.objects
                     if o.type == 'MESH' and o.data.get(CLOTH_GARMENT_TAG)]
        for obj in to_remove:
            # Also remove associated pin empties
            _clear_pins(context, obj)
            bpy.data.objects.remove(obj, do_unlink=True)

        # Remove collision from body
        body = find_body_obj(context)
        if body:
            for mod in list(body.modifiers):
                if mod.type == 'COLLISION':
                    body.modifiers.remove(mod)

        # Create new garment + cloth
        garment = _create_garment(context, body, props.garment_region)
        if garment is None:
            self.report({'ERROR'}, "Failed to create garment")
            return {'CANCELLED'}

        _add_cloth(context, garment)
        self.report({'INFO'}, f"Rebuilt: {garment.name}")
        return {'FINISHED'}


class HUMANBODY_OT_cloth_remove_garment(bpy.types.Operator):
    """Remove the garment mesh entirely"""
    bl_idname = "humanbody.cloth_remove_garment"
    bl_label = "Remove Garment"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _find_garment(context) is not None

    def execute(self, context):
        garment = _find_garment(context)
        name = garment.name
        _clear_pins(context, garment)
        bpy.data.objects.remove(garment, do_unlink=True)
        self.report({'INFO'}, f"Removed garment: {name}")
        return {'FINISHED'}


class HUMANBODY_OT_cloth_run_sim(bpy.types.Operator):
    """Play cloth simulation"""
    bl_idname = "humanbody.cloth_run_sim"
    bl_label = "Play Simulation"

    @classmethod
    def poll(cls, context):
        # Allow play if any cloth modifier exists in scene
        for obj in context.scene.objects:
            if _has_modifier(obj, 'CLOTH'):
                return True
        return False

    def execute(self, context):
        _run_simulation(context)
        return {'FINISHED'}


class HUMANBODY_OT_cloth_stop_sim(bpy.types.Operator):
    """Stop cloth simulation playback"""
    bl_idname = "humanbody.cloth_stop_sim"
    bl_label = "Stop Simulation"

    def execute(self, context):
        _stop_simulation(context)
        return {'FINISHED'}


class HUMANBODY_OT_cloth_reset_sim(bpy.types.Operator):
    """Reset simulation to frame 1"""
    bl_idname = "humanbody.cloth_reset_sim"
    bl_label = "Reset Simulation"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        _reset_simulation(context)
        self.report({'INFO'}, "Simulation reset")
        return {'FINISHED'}


class HUMANBODY_OT_cloth_add_pin(bpy.types.Operator):
    """Add a pin to selected vertices (Edit Mode)"""
    bl_idname = "humanbody.cloth_add_pin"
    bl_label = "Add Pin"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and obj.type == 'MESH'
                and obj.mode == 'EDIT'
                and not obj.data.get("humanbody"))

    def execute(self, context):
        _add_pin(context)
        self.report({'INFO'}, "Pin added")
        return {'FINISHED'}


class HUMANBODY_OT_cloth_remove_pin(bpy.types.Operator):
    """Remove selected pin empties"""
    bl_idname = "humanbody.cloth_remove_pin"
    bl_label = "Remove Selected Pins"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(o.get('is_pin') for o in context.selected_objects)

    def execute(self, context):
        _remove_selected_pins(context)
        self.report({'INFO'}, "Pins removed")
        return {'FINISHED'}


class HUMANBODY_OT_cloth_clear_pins(bpy.types.Operator):
    """Remove all pins from garment"""
    bl_idname = "humanbody.cloth_clear_pins"
    bl_label = "Clear All Pins"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _poll_garment(context)

    def execute(self, context):
        garment = _find_garment(context)
        _clear_pins(context, garment)
        self.report({'INFO'}, "All pins cleared")
        return {'FINISHED'}


class HUMANBODY_OT_cloth_fit_to_body(bpy.types.Operator):
    """Fit garment to body using Shrinkwrap + Corrective Smooth"""
    bl_idname = "humanbody.cloth_fit_to_body"
    bl_label = "Fit to Body"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _poll_garment_and_body(context)

    def execute(self, context):
        garment = _find_garment(context)
        body = find_body_obj(context)
        _fit_to_body(context, garment, body)
        self.report({'INFO'}, "Garment fitted to body")
        return {'FINISHED'}


class HUMANBODY_OT_cloth_apply_base(bpy.types.Operator):
    """Apply cloth simulation into mesh"""
    bl_idname = "humanbody.cloth_apply_base"
    bl_label = "Apply Base"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _poll_garment_has_cloth(context)

    def execute(self, context):
        garment = _find_garment(context)
        _apply_base(context, garment)
        self.report({'INFO'}, "Cloth simulation applied")
        return {'FINISHED'}


class HUMANBODY_OT_cloth_shake(bpy.types.Operator):
    """Randomize shrink values for natural wrinkles"""
    bl_idname = "humanbody.cloth_shake"
    bl_label = "Shake"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _poll_garment_has_cloth(context)

    def execute(self, context):
        garment = _find_garment(context)
        _shake_cloth(context, garment)
        self.report({'INFO'}, "Cloth shake applied")
        return {'FINISHED'}


class HUMANBODY_OT_cloth_paint_weight(bpy.types.Operator):
    """Enter weight paint mode for cloth vertex groups"""
    bl_idname = "humanbody.cloth_paint_weight"
    bl_label = "Paint Weight"

    @classmethod
    def poll(cls, context):
        return _poll_garment(context)

    def execute(self, context):
        garment = _find_garment(context)
        # Need garment to be active for weight paint mode
        context.view_layer.objects.active = garment
        if garment.mode != 'WEIGHT_PAINT':
            bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        else:
            bpy.ops.object.mode_set(mode='OBJECT')
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = (
    HumanBodyClothBuilderProps,
    HumanBodyClothPrimitiveProps,
    HumanBodyClothTemplateProps,
    HUMANBODY_OT_cloth_prim_create,
    HUMANBODY_OT_cloth_tpl_create,
    HUMANBODY_OT_cloth_add,
    HUMANBODY_OT_cloth_remove,
    HUMANBODY_OT_cloth_rebuild,
    HUMANBODY_OT_cloth_remove_garment,
    HUMANBODY_OT_cloth_run_sim,
    HUMANBODY_OT_cloth_stop_sim,
    HUMANBODY_OT_cloth_reset_sim,
    HUMANBODY_OT_cloth_add_pin,
    HUMANBODY_OT_cloth_remove_pin,
    HUMANBODY_OT_cloth_clear_pins,
    HUMANBODY_OT_cloth_fit_to_body,
    HUMANBODY_OT_cloth_apply_base,
    HUMANBODY_OT_cloth_shake,
    HUMANBODY_OT_cloth_paint_weight,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.humanbody_cloth_builder = bpy.props.PointerProperty(
        type=HumanBodyClothBuilderProps)
    bpy.types.Scene.humanbody_cloth_primitive = bpy.props.PointerProperty(
        type=HumanBodyClothPrimitiveProps)
    bpy.types.Scene.humanbody_cloth_template = bpy.props.PointerProperty(
        type=HumanBodyClothTemplateProps)


def unregister():
    del bpy.types.Scene.humanbody_cloth_template
    del bpy.types.Scene.humanbody_cloth_primitive
    del bpy.types.Scene.humanbody_cloth_builder
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
