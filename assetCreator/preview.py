# SPDX-License-Identifier: GPL-3.0-or-later
#
# Preview mesh creation (Z-Range + Image modes) for the Asset Creator.

import logging

import bpy
import bmesh
import numpy as np
from mathutils import Vector

from . import image_analysis

logger = logging.getLogger(__name__)

# Preview object tag
PREVIEW_TAG = "hb_asset_preview"

# ---------------------------------------------------------------------------
# Category-based body region filter
# ---------------------------------------------------------------------------
# For each category, define which face positions are ALLOWED.
# Faces outside these rules are excluded even if inside the Z-range.

def _face_allowed_for_category(center, category):
    """Return True if a face at *center* (world space) belongs to *category*.

    Rules filter out body parts that don't belong to the garment type.
    Rest-pose reference:
        Head/face  z > 1.42
        Arms       z 0.85–1.22, |x| 0.20–0.50
        Hands      z 0.40–0.60, |x| > 0.25
        Feet       z < 0.05
    """
    x, z = center.x, center.z

    if category == "Tops":
        if z > 1.42:                            # head / face
            return False
        if abs(x) > 0.25 and z < 0.60:         # hands only
            return False
        return True

    if category == "Bottoms":
        if abs(x) > 0.18 and z > 0.75:         # arms / shoulders
            return False
        return True

    if category == "Full":
        if z > 1.42:                            # head
            return False
        if abs(x) > 0.25 and z < 0.60:         # hands only
            return False
        return True

    if category == "Underwear":
        if abs(x) > 0.16:                      # only pelvis width
            return False
        return True

    if category == "Shoes":
        if abs(x) > 0.12:                      # feet are narrow
            return False
        return True

    # Accessories — no filtering
    return True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def find_body_obj(context):
    """Find the HumanBody mesh object."""
    obj = context.active_object
    if obj and obj.type == 'MESH' and obj.data.get("humanbody"):
        return obj
    for o in context.scene.objects:
        if o.type == 'MESH' and o.data.get("humanbody"):
            return o
    return None


def find_preview(context):
    """Find the current preview object, if any."""
    for obj in context.scene.objects:
        if obj.type == 'MESH' and obj.data.get(PREVIEW_TAG):
            return obj
    return None


def remove_preview(context):
    """Remove existing preview object."""
    preview = find_preview(context)
    if preview:
        bpy.data.objects.remove(preview, do_unlink=True)


def _create_material(props):
    """Create a simple Principled BSDF material from props."""
    mat = bpy.data.materials.new(name=f"hb_preview_{props.name_}")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs['Base Color'].default_value = (*props.color, 1.0)
        bsdf.inputs['Roughness'].default_value = props.roughness
        bsdf.inputs['Metallic'].default_value = props.metallic
    mat.diffuse_color = (*props.color, 1.0)
    return mat


def _grow_selection(bm, iterations):
    """Grow face selection by N iterations."""
    for _ in range(iterations):
        new_select = set()
        for face in bm.faces:
            if face.select:
                for edge in face.edges:
                    for linked_face in edge.link_faces:
                        if not linked_face.select:
                            new_select.add(linked_face)
        for f in new_select:
            f.select = True


def _apply_drape(bm, mat_w, drape_strength, body_bvh):
    """Create a smooth garment hull outside the body.

    1. **Offset** all vertices along normals — lifts the shell off the body
       so that subsequent smoothing does not push vertices INTO the body.
    2. **Laplacian smoothing** — removes body detail (breasts, belly button).
       Boundary edges (hem, neckline, sleeves) are pinned.
    3. **Collision fix** — any vertex that ended up inside the body despite
       the pre-offset is pushed back to body surface + gap.
    """
    if drape_strength < 0.01:
        return

    bm.verts.ensure_lookup_table()
    n = len(bm.verts)
    if n < 4:
        return

    # ── Step 1: Pre-offset along normals ─────────────────────────────────
    # Lift the shell off the body so smoothing has room to work.
    # drape 0.5 → 8 mm, drape 1.0 → 15 mm
    pre_offset = drape_strength * 0.015
    bm.normal_update()
    for v in bm.verts:
        v.co = v.co + v.normal * pre_offset

    # ── Step 2: Laplacian smoothing ──────────────────────────────────────
    # drape 0→0, 0.5→50, 1.0→100 iterations
    smooth_iters = int(drape_strength * 100)

    # Pin boundary edges (hem, neckline, sleeve openings stay in place)
    boundary_verts = set()
    for edge in bm.edges:
        if edge.is_boundary:
            boundary_verts.add(edge.verts[0])
            boundary_verts.add(edge.verts[1])

    interior_verts = [v for v in bm.verts if v not in boundary_verts]

    logger.info("Drape: %d interior / %d boundary / %d total verts, "
                "%d smooth iters, pre-offset=%.3f",
                len(interior_verts), len(boundary_verts), n,
                smooth_iters, pre_offset)

    if interior_verts and smooth_iters > 0:
        for _ in range(smooth_iters):
            bmesh.ops.smooth_vert(bm, verts=interior_verts, factor=0.5,
                                  use_axis_x=True, use_axis_y=True,
                                  use_axis_z=False)

    # ── Step 3: Collision fix (safety net) ───────────────────────────────
    # After offset + smooth, most vertices are outside the body.
    # Push back any that still penetrate.
    min_gap = 0.003
    bm.verts.ensure_lookup_table()
    pushed = 0
    for v in bm.verts:
        loc, normal, idx, dist = body_bvh.find_nearest(v.co)
        if loc is None:
            continue
        direction = v.co - loc
        if direction.dot(normal) <= 0:      # inside the body
            v.co = loc + normal * min_gap
            pushed += 1

    logger.info("Drape done: %d verts pushed back (collision fix)", pushed)


def _finalize_preview(context, props, bm, body, offset_weights=None):
    """Create object from BMesh, add modifiers, parent to body.

    Parameters
    ----------
    offset_weights : dict[int, float] or None
        If given, per-vertex weights for the ``hb_offset_weight`` vertex
        group used by the Displace modifier.  Keys are BMesh vertex indices.
    """
    if len(bm.faces) == 0:
        bm.free()
        return None

    mesh = bpy.data.meshes.new(f"hb_preview_{props.name_}")
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new(f"Preview_{props.name_}", mesh)
    context.collection.objects.link(obj)

    # Tag as preview
    obj.data[PREVIEW_TAG] = True

    # Copy transforms from body
    obj.matrix_world = body.matrix_world.copy()

    # Material
    mat = _create_material(props)
    obj.data.materials.append(mat)

    # Smooth shading
    for poly in obj.data.polygons:
        poly.use_smooth = True

    # Vertex group for variable offset (Image mode) or uniform (Z-Range)
    vg = obj.vertex_groups.new(name="hb_offset_weight")
    if offset_weights:
        for vi, w in offset_weights.items():
            vg.add([vi], w, 'REPLACE')
    else:
        # All vertices get weight 1.0
        vg.add(list(range(len(mesh.vertices))), 1.0, 'REPLACE')

    # Displace modifier (base offset from body)
    mod_disp = obj.modifiers.new(name="hb_offset", type='DISPLACE')
    mod_disp.direction = 'NORMAL'
    mod_disp.mid_level = 0.0
    mod_disp.vertex_group = "hb_offset_weight"
    if offset_weights:
        mod_disp.strength = props.image_offset_max
    else:
        mod_disp.strength = props.offset

    # Waviness — organic surface variation via procedural Cloud texture
    waviness = getattr(props, 'waviness', 0.0)
    if waviness > 0.01:
        tex = bpy.data.textures.new(f"hb_wave_{props.name_}", type='CLOUDS')
        tex.noise_scale = 0.06
        tex.noise_depth = 3
        mod_wave = obj.modifiers.new(name="hb_wave", type='DISPLACE')
        mod_wave.texture = tex
        mod_wave.direction = 'NORMAL'
        mod_wave.texture_coords = 'LOCAL'
        mod_wave.mid_level = 0.5
        mod_wave.strength = waviness * 0.008

    # Solidify modifier
    if props.thickness > 0:
        mod_solid = obj.modifiers.new(name="hb_solidify", type='SOLIDIFY')
        mod_solid.thickness = props.thickness
        mod_solid.offset = 1.0

    # Corrective smooth
    if props.smoothing > 0:
        mod_smooth = obj.modifiers.new(name="hb_smooth", type='CORRECTIVE_SMOOTH')
        mod_smooth.use_pin_boundary = True
        mod_smooth.iterations = int(props.smoothing * 10)

    # Parent to body
    obj.parent = body
    obj.matrix_parent_inverse = body.matrix_world.inverted()

    logger.info("Created asset preview: %s (%d faces)", props.name_,
                len(mesh.polygons))
    return obj


# ---------------------------------------------------------------------------
# Z-Range mode
# ---------------------------------------------------------------------------

def create_preview(context, props):
    """Create a preview mesh from the body using Z-range face selection."""
    from mathutils.bvhtree import BVHTree

    body = find_body_obj(context)
    if not body:
        return None

    remove_preview(context)

    depsgraph = context.evaluated_depsgraph_get()
    eval_obj = body.evaluated_get(depsgraph)
    eval_mesh = eval_obj.to_mesh()

    # Build BVH from full body mesh (local space) for collision checks
    bm_body = bmesh.new()
    bm_body.from_mesh(eval_mesh)
    body_bvh = BVHTree.FromBMesh(bm_body)
    bm_body.free()

    bm = bmesh.new()
    bm.from_mesh(eval_mesh)
    bm.faces.ensure_lookup_table()

    mat_w = body.matrix_world

    for f in bm.faces:
        f.select = False

    x_limit = 0.50 if props.include_arms else 0.20

    category = props.category

    for face in bm.faces:
        center = mat_w @ face.calc_center_median()
        if props.z_min <= center.z <= props.z_max:
            if abs(center.x) <= x_limit:
                if _face_allowed_for_category(center, category):
                    face.select = True
            elif props.include_arms:
                if _face_allowed_for_category(center, category):
                    face.select = True

    _grow_selection(bm, props.grow)

    faces_to_delete = [f for f in bm.faces if not f.select]
    bmesh.ops.delete(bm, geom=faces_to_delete, context='FACES')

    # Garment hull: smooth → collision fix → straight hang
    _apply_drape(bm, mat_w, props.drape, body_bvh)

    eval_obj.to_mesh_clear()
    return _finalize_preview(context, props, bm, body)


# ---------------------------------------------------------------------------
# Image mode
# ---------------------------------------------------------------------------

def create_preview_from_image(context, props, image_path):
    """Create a preview mesh using image-based garment detection.

    1. Load image → foreground mask
    2. Project body vertices (x, z) into image space
    3. Classify faces as covered / not covered
    4. Compute per-vertex offset weights from silhouette analysis
    5. Build preview with variable Displace
    """
    from mathutils.bvhtree import BVHTree

    body = find_body_obj(context)
    if not body:
        return None

    remove_preview(context)

    # Load image via Blender
    bpy_img = bpy.data.images.load(image_path, check_existing=True)
    pixels = image_analysis.load_image_pixels(bpy_img)
    h, w = pixels.shape[:2]

    fg_mask = image_analysis.classify_foreground(
        pixels, props.image_bg_mode, props.image_threshold)

    # Evaluated body mesh
    depsgraph = context.evaluated_depsgraph_get()
    eval_obj = body.evaluated_get(depsgraph)
    eval_mesh = eval_obj.to_mesh()

    # Build BVH from full body mesh (local space) for collision checks
    bm_body = bmesh.new()
    bm_body.from_mesh(eval_mesh)
    body_bvh = BVHTree.FromBMesh(bm_body)
    bm_body.free()

    mat_w = body.matrix_world

    # Collect world-space vertex positions
    n_verts = len(eval_mesh.vertices)
    verts_world = np.empty((n_verts, 3), dtype=np.float32)
    for i, v in enumerate(eval_mesh.vertices):
        co = mat_w @ v.co
        verts_world[i] = (co.x, co.y, co.z)

    verts_xz = verts_world[:, [0, 2]]  # (N, 2) — x and z

    # Auto-fit scale
    body_bounds = image_analysis.compute_body_bounds(verts_xz)
    sx, sz, ox, oz = image_analysis.auto_fit_scale(body_bounds, fg_mask)

    # Apply user scale
    sx *= props.image_scale
    sz *= props.image_scale

    # Build BMesh
    bm = bmesh.new()
    bm.from_mesh(eval_mesh)
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()

    # Face centers in world space → image UV
    n_faces = len(bm.faces)
    face_centers_xz = np.empty((n_faces, 2), dtype=np.float32)
    for i, face in enumerate(bm.faces):
        c = mat_w @ face.calc_center_median()
        face_centers_xz[i] = (c.x, c.z)

    face_uv = image_analysis.vertex_to_image_uv(
        face_centers_xz, sx, sz, ox, oz, w, h)

    covered = image_analysis.classify_garment_faces(
        face_centers_xz, face_uv, fg_mask, w, h)

    # Select covered faces (with category filter)
    category = props.category
    for f in bm.faces:
        f.select = False
    for i, face in enumerate(bm.faces):
        if covered[i]:
            center = mat_w @ face.calc_center_median()
            if _face_allowed_for_category(center, category):
                face.select = True

    _grow_selection(bm, props.grow)

    # Delete non-selected
    faces_to_delete = [f for f in bm.faces if not f.select]
    bmesh.ops.delete(bm, geom=faces_to_delete, context='FACES')

    if len(bm.faces) == 0:
        bm.free()
        eval_obj.to_mesh_clear()
        return None

    # Compute offset profile
    bm.verts.ensure_lookup_table()
    remaining_xz = np.empty((len(bm.verts), 2), dtype=np.float32)
    remaining_z = np.empty(len(bm.verts), dtype=np.float32)
    for i, v in enumerate(bm.verts):
        co = mat_w @ v.co
        remaining_xz[i] = (co.x, co.z)
        remaining_z[i] = co.z

    z_values, profile_weights = image_analysis.compute_offset_profile(
        verts_xz, fg_mask, sx, sz, ox, oz, w, h)

    per_vert_w = image_analysis.interpolate_vertex_weights(
        remaining_z, z_values, profile_weights)

    # Map: lerp between offset_min and offset_max via weight
    # The vertex group weight controls Displace strength (0..1 * max_strength)
    # So we remap: w=0 → offset_min/offset_max, w=1 → 1.0
    offset_min = props.image_offset_min
    offset_max = max(props.image_offset_max, 1e-6)
    min_ratio = offset_min / offset_max

    offset_weights = {}
    for i in range(len(bm.verts)):
        raw = float(per_vert_w[i])
        mapped = min_ratio + raw * (1.0 - min_ratio)
        offset_weights[i] = mapped

    # Garment hull: smooth → collision fix → straight hang
    _apply_drape(bm, mat_w, props.drape, body_bvh)

    eval_obj.to_mesh_clear()
    return _finalize_preview(context, props, bm, body,
                             offset_weights=offset_weights)
