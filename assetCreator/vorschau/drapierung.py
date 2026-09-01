# -*- coding: utf-8 -*-
import logging
import bpy
import bmesh
logger = logging.getLogger(__name__)
from .vorschausuche import _create_material
from .vorschausuche import PREVIEW_TAG


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
