# -*- coding: utf-8 -*-
import bpy
from mathutils import Vector, Matrix
import math


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


class Geometrieassets:
    u"""Die frueheren Modulfunktionen, gebuendelt."""

    @staticmethod
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

    @staticmethod
    def _create_material(name, color):
        """Create a simple Principled BSDF material."""
        mat = bpy.data.materials.new(name=f"hb_geo_{name}")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs['Base Color'].default_value = (*color, 1.0)
        mat.diffuse_color = (*color, 1.0)
        return mat

    @staticmethod
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
