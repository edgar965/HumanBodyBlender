# -*- coding: utf-8 -*-
import logging
import bpy
from ..assetCreator.vorschau.vorschausuche import Vorschausuche
from ..cloth.koerpermass import Koerpermass
from ..cloth.formen_koerper import Koerperformen
from ..cloth.formen_geometrie import Geometrieformen
from ..cloth.modifikatoren import Modifikatoren
from ..koerperoperator import MitKoerper
logger = logging.getLogger(__name__)


class HUMANBODY_OT_cloth_prim_create(MitKoerper, bpy.types.Operator):
    """Create a primitive cloth shape around the body"""
    bl_idname = "humanbody.cloth_prim_create"
    bl_label = "Create Primitive"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        body = Vorschausuche.find_body_obj(context)
        props = context.scene.humanbody_cloth_primitive
        pt = props.prim_type
        segs = props.segments
        length = props.prim_length
        flare = props.prim_flare
        radius = props.prim_radius
        z_pos = props.prim_z
        count = props.prim_count

        Koerpermass._prepare_body_eval(body)
        try:
            creators = {
                'PRIM_SKIRT':     lambda: Koerperformen._create_prim_skirt(context, body, segs, length, flare),
                'PRIM_TOP':       lambda: Koerperformen._create_prim_top(context, body, segs, length),
                'PRIM_PANTS':     lambda: Koerperformen._create_prim_pants(context, body, segs, length),
                'PRIM_ARMS':      lambda: Koerperformen._create_prim_arms(context, body, segs, length),
                'PRIM_NECK':      lambda: Koerperformen._create_prim_neck(context, body, segs, length),
                'PRIM_HEAD':      lambda: Koerperformen._create_prim_head(context, body, segs, length),
                'PRIM_SHOES':     lambda: Koerperformen._create_prim_shoes(context, body, segs, length),
                'PRIM_DISC':      lambda: Geometrieformen._create_prim_disc(context, body, segs, radius, z_pos),
                'PRIM_SPHERE':    lambda: Geometrieformen._create_prim_sphere(context, body, segs, radius, z_pos),
                'PRIM_OVAL_DISC': lambda: Geometrieformen._create_prim_oval_disc(context, body, segs, radius, z_pos),
                'PRIM_TRIANGLE':  lambda: Geometrieformen._create_prim_triangle(context, body, segs, radius, z_pos),
                'PRIM_PUFFER':    lambda: Geometrieformen._create_prim_puffer(context, body, segs, length, count),
            }

            garment = creators.get(pt, creators['PRIM_SKIRT'])()
        finally:
            Koerpermass._cleanup_body_eval()

        if garment is None:
            self.report({'ERROR'}, "Failed to create primitive")
            return {'CANCELLED'}

        Modifikatoren._add_cloth(context, garment)
        Modifikatoren._add_collision(context, body)
        self.report({'INFO'}, f"Created {pt}: {garment.name}")
        return {'FINISHED'}
