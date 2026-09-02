# -*- coding: utf-8 -*-
import logging
import bpy
from ..assetCreator.vorschau.vorschausuche import Vorschausuche
from ..cloth.koerpermass import Koerpermass
from ..cloth.schablonen import Schablonen
from ..cloth.modifikatoren import Modifikatoren
from ..koerperoperator import MitKoerper
logger = logging.getLogger(__name__)


class HUMANBODY_OT_cloth_tpl_create(MitKoerper, bpy.types.Operator):
    """Create a template garment around the body"""
    bl_idname = "humanbody.cloth_tpl_create"
    bl_label = "Create Template"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        body = Vorschausuche.find_body_obj(context)
        props = context.scene.humanbody_cloth_template
        tt = props.template_type
        segs = props.segments
        # Tightness → gap: 1.0 (tight) = 0.005, 0.0 (loose) = 0.025
        gap = 0.005 + (1.0 - props.tightness) * 0.020
        t_ext = props.top_extend
        b_ext = props.bottom_extend

        Koerpermass._prepare_body_eval(body)
        try:
            creators = {
                'TPL_TSHIRT': lambda: Schablonen._create_tpl_tshirt(context, body, segs, gap, t_ext, b_ext),
                'TPL_PANTS':  lambda: Schablonen._create_tpl_pants(context, body, segs, gap, t_ext, b_ext),
                'TPL_SKIRT':  lambda: Schablonen._create_tpl_skirt(context, body, segs, gap, t_ext, b_ext),
                'TPL_DRESS':  lambda: Schablonen._create_tpl_dress(context, body, segs, gap, t_ext, b_ext),
            }

            garment = creators.get(tt, creators['TPL_TSHIRT'])()
        finally:
            Koerpermass._cleanup_body_eval()

        if garment is None:
            self.report({'ERROR'}, "Failed to create template")
            return {'CANCELLED'}

        # Push outside body to prevent clipping
        Koerpermass._push_outside_body(context, garment, body, offset=max(gap, 0.005))

        Modifikatoren._add_cloth(context, garment)
        Modifikatoren._add_collision(context, body)
        self.report({'INFO'}, f"Created {tt}: {garment.name}")
        return {'FINISHED'}
