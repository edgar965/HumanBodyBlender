# SPDX-License-Identifier: GPL-3.0-or-later
#
# Geometric Assets — simple primitives placed on body regions.

import bpy
import bmesh
from bpy.props import (EnumProperty, FloatProperty, FloatVectorProperty,
                       IntProperty)
from mathutils import Vector, Matrix
import math

from .preview import find_body_obj

# ---------------------------------------------------------------------------
# Enum items
# ---------------------------------------------------------------------------

GEO_REGIONS = [
    ("ARMS",  "Arme",   ""),
    ("HANDS", "Haende", ""),
    ("NECK",  "Hals",   ""),
    ("HEAD",  "Kopf",   ""),
    ("TORSO", "Rumpf",  ""),
    ("LEGS",  "Beine",  ""),
    ("FEET",  "Fuesse", ""),
]

GEO_SHAPES = [
    ("CYLINDER", "Zylinder", ""),
    ("BOX",      "Quader",   ""),
    ("TRIANGLE", "Dreieck",  ""),
    ("DISC",     "Scheibe",  ""),
]

# ---------------------------------------------------------------------------
# Region vertex filter (world-space bounds, female rest pose)
# ---------------------------------------------------------------------------

# (z_min, z_max, abs_x_min, abs_x_max)  — None means no constraint
_REGION_BOUNDS = {
    "HEAD":  (1.42, 2.0,  None, 0.15),
    "NECK":  (1.28, 1.42, None, 0.08),
    "TORSO": (0.70, 1.28, None, 0.20),
    "ARMS":  (0.60, 1.22, 0.20, 0.50),
    "HANDS": (0.40, 0.60, 0.25, None),
    "LEGS":  (0.05, 0.70, None, 0.15),
    "FEET":  (-0.01, 0.05, None, None),
}


def _get_region_data(body, region):
    """Scan evaluated body mesh, return (center, size, normal) for *region*.

    center : Vector — centroid of region vertices
    size   : Vector(3) — bounding-box dimensions
    normal : Vector — average outward direction (from body center)
    """
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = body.evaluated_get(depsgraph)
    eval_mesh = eval_obj.to_mesh()
    mat_w = body.matrix_world

    bounds = _REGION_BOUNDS[region]
    z_min, z_max, ax_min, ax_max = bounds

    positions = []
    for v in eval_mesh.vertices:
        co = mat_w @ v.co
        if not (z_min <= co.z <= z_max):
            continue
        ax = abs(co.x)
        if ax_min is not None and ax < ax_min:
            continue
        if ax_max is not None and ax > ax_max:
            continue
        positions.append(co)

    eval_obj.to_mesh_clear()

    if not positions:
        return Vector((0, 0, 1)), Vector((0.1, 0.1, 0.1)), Vector((0, 1, 0))

    # Centroid
    center = Vector((0, 0, 0))
    for p in positions:
        center += p
    center /= len(positions)

    # Bounding box
    xs = [p.x for p in positions]
    ys = [p.y for p in positions]
    zs = [p.z for p in positions]
    size = Vector((max(xs) - min(xs),
                   max(ys) - min(ys),
                   max(zs) - min(zs)))

    # Average outward direction (from body center-line)
    body_center = Vector((0, 0, center.z))
    normal = (center - body_center).normalized()
    if normal.length < 0.01:
        normal = Vector((0, -1, 0))  # front-facing fallback

    return center, size, normal


# ---------------------------------------------------------------------------
# PropertyGroup
# ---------------------------------------------------------------------------

class HumanBodyGeoAssetProps(bpy.types.PropertyGroup):
    region: EnumProperty(
        name="Region",
        items=GEO_REGIONS,
        default="TORSO",
    )
    shape: EnumProperty(
        name="Shape",
        items=GEO_SHAPES,
        default="CYLINDER",
    )
    offset: FloatProperty(
        name="Abstand",
        default=0.01, min=0.0, max=0.1,
        step=0.1, precision=3,
    )
    scale: FloatProperty(
        name="Groesse",
        default=1.0, min=0.1, max=5.0,
        step=1, precision=2,
    )
    segments: IntProperty(
        name="Segmente",
        default=16, min=3, max=64,
    )
    color: FloatVectorProperty(
        name="Farbe",
        subtype='COLOR',
        default=(0.6, 0.6, 0.6),
        min=0, max=1, size=3,
    )


# ---------------------------------------------------------------------------
# Create operator
# ---------------------------------------------------------------------------

GEO_TAG = "hb_geo_asset"


def _create_material(name, color):
    """Create a simple Principled BSDF material."""
    mat = bpy.data.materials.new(name=f"hb_geo_{name}")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs['Base Color'].default_value = (*color, 1.0)
    mat.diffuse_color = (*color, 1.0)
    return mat


def _region_orientation(region):
    """Return a rotation Matrix for the primitive based on region.

    Cylinders / triangles have their length axis along Z by default.
    We rotate them to align with the region's main axis.
    """
    if region in ("TORSO", "NECK", "HEAD", "LEGS"):
        # Vertical — no rotation needed (Z-up is default)
        return Matrix.Identity(4)
    if region == "ARMS":
        # Horizontal along X axis
        return Matrix.Rotation(math.radians(90), 4, 'Y')
    if region == "FEET":
        # Horizontal along Y axis
        return Matrix.Rotation(math.radians(90), 4, 'X')
    if region == "HANDS":
        # Slightly tilted down
        return Matrix.Rotation(math.radians(70), 4, 'Y')
    return Matrix.Identity(4)


class HUMANBODY_OT_create_geo_asset(bpy.types.Operator):
    """Create a geometric primitive on a body region"""
    bl_idname = "humanbody.create_geo_asset"
    bl_label = "Erstellen"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if obj and obj.type == 'MESH' and obj.data.get("humanbody"):
            return True
        for o in context.scene.objects:
            if o.type == 'MESH' and o.data.get("humanbody"):
                return True
        return False

    def execute(self, context):
        body = find_body_obj(context)
        if not body:
            self.report({'WARNING'}, "No HumanBody object found")
            return {'CANCELLED'}

        props = context.scene.humanbody_geo_asset
        region = props.region
        shape = props.shape
        scale = props.scale
        segments = props.segments
        offset = props.offset

        center, size, normal = _get_region_data(body, region)

        # Compute dimensions from region bounding box
        # Use the smaller two axes for radius, largest for height
        dims = sorted([size.x, size.y, size.z])
        radius = max(dims[0], dims[1]) * 0.5 * scale * 0.5
        height = dims[2] * scale * 0.5

        # Ensure minimums
        radius = max(radius, 0.005)
        height = max(height, 0.01)

        bm = bmesh.new()

        if shape == "CYLINDER":
            bmesh.ops.create_cone(
                bm,
                segments=segments,
                radius1=radius,
                radius2=radius,
                depth=height,
            )
        elif shape == "BOX":
            bmesh.ops.create_cube(bm, size=1.0)
            # Scale to match region
            sx = max(size.x * scale * 0.5, 0.01)
            sy = max(size.y * scale * 0.5, 0.01)
            sz = max(size.z * scale * 0.5, 0.01)
            bmesh.ops.scale(
                bm,
                vec=(sx, sy, sz),
                verts=bm.verts[:],
            )
        elif shape == "TRIANGLE":
            bmesh.ops.create_cone(
                bm,
                segments=3,
                radius1=radius,
                radius2=radius,
                depth=height,
            )
        elif shape == "DISC":
            thin = 0.002 * scale
            bmesh.ops.create_cone(
                bm,
                segments=segments,
                radius1=radius,
                radius2=radius,
                depth=thin,
            )

        # Apply region-based rotation
        rot_mat = _region_orientation(region)
        bmesh.ops.transform(bm, matrix=rot_mat, verts=bm.verts[:])

        # Position: center + normal * offset
        pos = center + normal * offset
        bmesh.ops.translate(bm, vec=pos, verts=bm.verts[:])

        # Create mesh and object
        mesh = bpy.data.meshes.new(f"hb_geo_{region}_{shape}")
        bm.to_mesh(mesh)
        bm.free()

        obj = bpy.data.objects.new(f"GeoAsset_{region}_{shape}", mesh)
        context.collection.objects.link(obj)

        # Smooth shading
        for poly in obj.data.polygons:
            poly.use_smooth = True

        # Material
        mat = _create_material(f"{region}_{shape}", props.color)
        obj.data.materials.append(mat)

        # Tag as geo asset
        obj[GEO_TAG] = True

        # Parent to body
        obj.parent = body
        obj.matrix_parent_inverse = body.matrix_world.inverted()

        self.report({'INFO'}, f"Geometric Asset erstellt: {region} / {shape}")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Remove operator
# ---------------------------------------------------------------------------

class HUMANBODY_OT_remove_geo_assets(bpy.types.Operator):
    """Remove all geometric assets from the scene"""
    bl_idname = "humanbody.remove_geo_assets"
    bl_label = "Alle entfernen"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        for obj in context.scene.objects:
            if obj.get(GEO_TAG):
                return True
        return False

    def execute(self, context):
        removed = 0
        to_remove = [obj for obj in context.scene.objects if obj.get(GEO_TAG)]
        for obj in to_remove:
            bpy.data.objects.remove(obj, do_unlink=True)
            removed += 1
        self.report({'INFO'}, f"{removed} Geometric Asset(s) entfernt")
        return {'FINISHED'}
