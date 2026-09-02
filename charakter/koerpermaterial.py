# -*- coding: utf-8 -*-
u"""Koerpermaterial — aus `charakterdatei` herausgeloest."""
# -*- coding: utf-8 -*-
import logging
import bpy
from ..morph.daten import Morphdaten
logger = logging.getLogger(__name__)
from .materialien import Materialien


class Koerpermaterial:
    u"""Aus `HumanBodyIO` herausgeloest, Rumpf unveraendert."""

    @staticmethod
    def create_body_materials(obj, skin_rgb, eye_rgb):
        """Create all body materials matching char.blend face assignments.

        Slots: 0=Skin, 1=Censor/Areola, 2=Eyelash, 3=Pupil, 4=Sclera,
               5=Cornea, 6=Iris, 7=Tongue, 8=Teeth, 9=Nails_Hand, 10=Nails_Feet
        """
        nr = Morphdaten._nail_color(skin_rgb)

        # Cornea (transparent)
        cornea = bpy.data.materials.new("HB_Cornea")
        cornea.use_nodes = True
        tree = cornea.node_tree
        tree.nodes.clear()
        trans = tree.nodes.new('ShaderNodeBsdfTransparent')
        trans.location = (0, 0)
        out = tree.nodes.new('ShaderNodeOutputMaterial')
        out.location = (300, 0)
        tree.links.new(trans.outputs[0], out.inputs[0])
        cornea.diffuse_color = (1.0, 1.0, 1.0, 0.0)
        try:
            cornea.surface_render_method = 'DITHERED'
        # stumm gewollt: Das Feld gibt es erst ab Blender 4.2. Fehlt es,
        # bleibt die Vorgabe stehen — gewollt.
        except (AttributeError, TypeError):
            pass

        slot_mats = [
            Materialien._make_bsdf_mat("HB_Skin", skin_rgb, sss=0.3),
            Materialien._make_bsdf_mat("HB_Censor", skin_rgb, sss=0.3),
            Materialien._make_bsdf_mat("HB_Eyelash", (0.015, 0.015, 0.015)),
            Materialien._make_bsdf_mat("HB_Pupil", (0.005, 0.005, 0.005),
                           roughness=0.0),
            Materialien._make_bsdf_mat("HB_Sclera", (0.9, 0.88, 0.87), roughness=0.3),
            cornea,
            Materialien._make_bsdf_mat("HB_Iris", eye_rgb, roughness=0.3),
            Materialien._make_bsdf_mat("HB_Tongue", (0.4, 0.1, 0.08),
                           roughness=0.6, sss=0.2),
            Materialien._make_bsdf_mat("HB_Teeth", (0.85, 0.82, 0.76), roughness=0.3),
            Materialien._make_bsdf_mat("HB_Nails_Hand", nr, roughness=0.3),
            Materialien._make_bsdf_mat("HB_Nails_Feet", nr, roughness=0.3),
        ]

        mats = obj.data.materials
        for i, new_mat in enumerate(slot_mats):
            if i < len(mats):
                mats[i] = new_mat
            else:
                mats.append(new_mat)

        # Split nails: slot 9 = hand, slot 10 = feet
        for poly in obj.data.polygons:
            if poly.material_index == 9:
                cz = sum(obj.data.vertices[vi].co.z
                         for vi in poly.vertices) / len(poly.vertices)
                if cz < 0.5:
                    poly.material_index = 10
