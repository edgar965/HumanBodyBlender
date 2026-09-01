# -*- coding: utf-8 -*-
import logging
import bpy
import bmesh
from ..assetCreator.preview import _face_allowed_for_category, _grow_selection
from .namen import CLOTH_GARMENT_TAG
logger = logging.getLogger(__name__)


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
