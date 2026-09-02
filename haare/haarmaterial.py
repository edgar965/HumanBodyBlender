# -*- coding: utf-8 -*-
import logging
import bpy
logger = logging.getLogger(__name__)
from .haarfarben import HAIR_COLORS


class Haarmaterial:
    u"""Die frueheren Modulfunktionen, gebuendelt."""

    @staticmethod
    def _create_hair_material(name, color_key):
        """Create a Principled Hair BSDF material."""
        mat = bpy.data.materials.new(name)
        tree = mat.node_tree
        tree.nodes.clear()

        hair_node = tree.nodes.new("ShaderNodeBsdfHairPrincipled")
        hair_node.location = (0, 0)
        hair_node.parametrization = 'MELANIN'

        output = tree.nodes.new("ShaderNodeOutputMaterial")
        output.location = (300, 0)
        tree.links.new(hair_node.outputs[0], output.inputs[0])

        settings = HAIR_COLORS.get(color_key, {})
        hair_node.inputs[1].default_value = settings.get("melanin", 0.8)
        hair_node.inputs[2].default_value = settings.get("melanin_redness", 0.3)
        hair_node.inputs[5].default_value = settings.get("roughness", 0.5)
        hair_node.inputs[6].default_value = settings.get("radial_roughness", 0.05)
        hair_node.inputs[7].default_value = settings.get("coat", 0.0)
        hair_node.inputs[8].default_value = settings.get("ior", 1.45)
        hair_node.inputs[9].default_value = settings.get("offset", 0.035)
        hair_node.inputs[10].default_value = settings.get("random_color", 0.0)
        hair_node.inputs[11].default_value = settings.get("random_roughness", 0.0)

        vp = settings.get("viewport", (0.02, 0.02, 0.02))
        mat.diffuse_color = (vp[0], vp[1], vp[2], 1.0)

        return mat

    @staticmethod
    def _create_mesh_hair_material(name, color_key):
        """Create a Principled BSDF material for mesh-based hair."""
        mat = bpy.data.materials.new(name)
        tree = mat.node_tree
        tree.nodes.clear()

        bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
        bsdf.location = (0, 0)

        output = tree.nodes.new("ShaderNodeOutputMaterial")
        output.location = (300, 0)
        tree.links.new(bsdf.outputs[0], output.inputs[0])

        settings = HAIR_COLORS.get(color_key, {})
        vp = settings.get("viewport", (0.08, 0.04, 0.02))
        bsdf.inputs['Base Color'].default_value = (vp[0], vp[1], vp[2], 1.0)
        bsdf.inputs['Roughness'].default_value = 0.4

        mat.diffuse_color = (vp[0], vp[1], vp[2], 1.0)
        return mat

    @staticmethod
    def _apply_hair_color(mat, color_key):
        """Update an existing hair material's color settings."""
        if not mat or not mat.node_tree:
            return
        settings = HAIR_COLORS.get(color_key, {})
        vp = settings.get("viewport", (0.02, 0.02, 0.02))
        for node in mat.node_tree.nodes:
            if node.type == 'BSDF_HAIR_PRINCIPLED':
                node.inputs[1].default_value = settings.get("melanin", 0.8)
                node.inputs[2].default_value = settings.get("melanin_redness", 0.3)
                node.inputs[7].default_value = settings.get("coat", 0.0)
                node.inputs[8].default_value = settings.get("ior", 1.45)
                node.inputs[10].default_value = settings.get("random_color", 0.0)
                mat.diffuse_color = (vp[0], vp[1], vp[2], 1.0)
                return
            elif node.type == 'BSDF_PRINCIPLED' and mat.name.startswith("HumanBody_Hair"):
                node.inputs['Base Color'].default_value = (vp[0], vp[1], vp[2], 1.0)
                mat.diffuse_color = (vp[0], vp[1], vp[2], 1.0)
                return
