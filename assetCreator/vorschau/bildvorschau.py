# -*- coding: utf-8 -*-
import logging
import bpy
import bmesh
import numpy as np
from .. import image_analysis
logger = logging.getLogger(__name__)
from .drapierung import _apply_drape
from .flaechenwahl import _face_allowed_for_category
from .drapierung import _finalize_preview
from .flaechenwahl import _grow_selection
from .vorschausuche import find_body_obj
from .vorschausuche import remove_preview


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
