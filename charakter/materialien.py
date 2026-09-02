# -*- coding: utf-8 -*-
import logging
import bpy
logger = logging.getLogger(__name__)


class Materialien:
    u"""Die frueheren Modulfunktionen, gebuendelt."""

    @staticmethod
    def _lip_color(skin_rgb):
        """Slightly darker/rosier version of skin color for lips."""
        r, g, b = skin_rgb
        return (min(1.0, r * 0.85 + 0.12),
                min(1.0, g * 0.55 + 0.04),
                min(1.0, b * 0.50 + 0.03))

    @staticmethod
    def _assign_lip_faces(obj, slot_index=10):
        """Identify lip faces on the skin (slot 0) and reassign to slot_index.

        Pure distance-based: skin faces with any vertex within 6mm of front
        teeth, constrained to the mouth Z/Y region.
        """
        from mathutils import kdtree as _kd

        teeth_verts = []
        for poly in obj.data.polygons:
            if poly.material_index == 8:
                for vi in poly.vertices:
                    v = obj.data.vertices[vi]
                    if v.co.y < -0.11:
                        teeth_verts.append(v.co.copy())

        if not teeth_verts:
            return

        kd = _kd.KDTree(len(teeth_verts))
        for i, co in enumerate(teeth_verts):
            kd.insert(co, i)
        kd.balance()

        lip_faces = set()
        for poly in obj.data.polygons:
            if poly.material_index != 0:
                continue
            cy = sum(obj.data.vertices[vi].co.y for vi in poly.vertices) / len(poly.vertices)
            cz = sum(obj.data.vertices[vi].co.z for vi in poly.vertices) / len(poly.vertices)
            if cy > -0.08 or cz < 1.46 or cz > 1.54:
                continue
            for vi in poly.vertices:
                _, _, dist = kd.find(obj.data.vertices[vi].co)
                if dist < 0.006:
                    lip_faces.add(poly.index)
                    break

        for poly in obj.data.polygons:
            if poly.index in lip_faces:
                poly.material_index = slot_index

    @staticmethod
    def _assign_eyebrow_faces(obj, src_slot=2, dst_slot=11):
        """Assign visible eyebrow area on the SKIN to the eyebrow slot."""
        from mathutils import kdtree as _kd

        brow_verts = []
        for poly in obj.data.polygons:
            if poly.material_index != src_slot:
                continue
            cz = sum(obj.data.vertices[vi].co.z for vi in poly.vertices) / len(poly.vertices)
            if cz >= 1.566:
                for vi in poly.vertices:
                    brow_verts.append(obj.data.vertices[vi].co.copy())

        if not brow_verts:
            return

        kd = _kd.KDTree(len(brow_verts))
        for i, co in enumerate(brow_verts):
            kd.insert(co, i)
        kd.balance()

        for poly in obj.data.polygons:
            if poly.material_index != 0:
                continue
            cz = sum(obj.data.vertices[vi].co.z for vi in poly.vertices) / len(poly.vertices)
            if cz < 1.54 or cz > 1.62:
                continue
            for vi in poly.vertices:
                _, _, dist = kd.find(obj.data.vertices[vi].co)
                if dist < 0.010:
                    poly.material_index = dst_slot
                    break

        for poly in obj.data.polygons:
            if poly.material_index != src_slot:
                continue
            cz = sum(obj.data.vertices[vi].co.z for vi in poly.vertices) / len(poly.vertices)
            if cz >= 1.566:
                poly.material_index = dst_slot

    @staticmethod
    def _make_bsdf_mat(name, color, roughness=0.5, sss=0.0):
        """Create a Principled BSDF material."""
        mat = bpy.data.materials.new(name=name)
        mat.use_nodes = True
        tree = mat.node_tree
        tree.nodes.clear()
        bsdf = tree.nodes.new('ShaderNodeBsdfPrincipled')
        bsdf.location = (0, 0)
        bsdf.inputs['Base Color'].default_value = (*color, 1.0)
        bsdf.inputs['Roughness'].default_value = roughness
        if sss > 0:
            bsdf.inputs['Subsurface Weight'].default_value = sss
            bsdf.inputs['Subsurface Radius'].default_value = (1.0, 0.2, 0.1)
        out = tree.nodes.new('ShaderNodeOutputMaterial')
        out.location = (300, 0)
        tree.links.new(bsdf.outputs[0], out.inputs[0])
        mat.diffuse_color = (*color, 1.0)
        return mat

    @staticmethod
    @bpy.app.handlers.persistent
    def _sync_hb_material_colors(scene, depsgraph=None):
        """Sync Principled BSDF Base Color -> diffuse_color for HB_ materials.

        The Materials panel color picker edits the node input, but Solid
        viewport mode only reads mat.diffuse_color.  This handler keeps
        them in sync.
        """
        for mat in bpy.data.materials:
            if not mat.name.startswith("HB_") or not mat.node_tree:
                continue
            dc = mat.diffuse_color
            for node in mat.node_tree.nodes:
                if node.type == 'BSDF_PRINCIPLED':
                    bc = node.inputs['Base Color'].default_value
                    if (abs(bc[0] - dc[0]) > 0.001 or
                            abs(bc[1] - dc[1]) > 0.001 or
                            abs(bc[2] - dc[2]) > 0.001):
                        mat.diffuse_color = (bc[0], bc[1], bc[2], 1.0)
                    break
