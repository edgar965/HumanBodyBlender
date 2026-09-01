# -*- coding: utf-8 -*-
import logging
import bpy
from ..assetCreator.preview import find_body_obj
from ..cloth.koerpermass import (
    _prepare_body_eval, _cleanup_body_eval, _push_outside_body,
)
from ..cloth.formen_koerper import (
    _create_prim_skirt, _create_prim_top, _create_prim_pants,
    _create_prim_arms, _create_prim_neck, _create_prim_head,
    _create_prim_shoes,
)
from ..cloth.formen_geometrie import (
    _create_prim_disc, _create_prim_sphere, _create_prim_oval_disc,
    _create_prim_triangle, _create_prim_puffer,
)
from ..cloth.schablonen import (
    _create_tpl_tshirt, _create_tpl_pants, _create_tpl_skirt,
    _create_tpl_dress,
)
from ..cloth.modifikatoren import _add_cloth, _add_collision
logger = logging.getLogger(__name__)


class HUMANBODY_OT_cloth_prim_create(bpy.types.Operator):
    """Create a primitive cloth shape around the body"""
    bl_idname = "humanbody.cloth_prim_create"
    bl_label = "Create Primitive"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return find_body_obj(context) is not None

    def execute(self, context):
        body = find_body_obj(context)
        props = context.scene.humanbody_cloth_primitive
        pt = props.prim_type
        segs = props.segments
        length = props.prim_length
        flare = props.prim_flare
        radius = props.prim_radius
        z_pos = props.prim_z
        count = props.prim_count

        _prepare_body_eval(body)
        try:
            creators = {
                'PRIM_SKIRT':     lambda: _create_prim_skirt(context, body, segs, length, flare),
                'PRIM_TOP':       lambda: _create_prim_top(context, body, segs, length),
                'PRIM_PANTS':     lambda: _create_prim_pants(context, body, segs, length),
                'PRIM_ARMS':      lambda: _create_prim_arms(context, body, segs, length),
                'PRIM_NECK':      lambda: _create_prim_neck(context, body, segs, length),
                'PRIM_HEAD':      lambda: _create_prim_head(context, body, segs, length),
                'PRIM_SHOES':     lambda: _create_prim_shoes(context, body, segs, length),
                'PRIM_DISC':      lambda: _create_prim_disc(context, body, segs, radius, z_pos),
                'PRIM_SPHERE':    lambda: _create_prim_sphere(context, body, segs, radius, z_pos),
                'PRIM_OVAL_DISC': lambda: _create_prim_oval_disc(context, body, segs, radius, z_pos),
                'PRIM_TRIANGLE':  lambda: _create_prim_triangle(context, body, segs, radius, z_pos),
                'PRIM_PUFFER':    lambda: _create_prim_puffer(context, body, segs, length, count),
            }

            garment = creators.get(pt, creators['PRIM_SKIRT'])()
        finally:
            _cleanup_body_eval()

        if garment is None:
            self.report({'ERROR'}, "Failed to create primitive")
            return {'CANCELLED'}

        _add_cloth(context, garment)
        _add_collision(context, body)
        self.report({'INFO'}, f"Created {pt}: {garment.name}")
        return {'FINISHED'}


class HUMANBODY_OT_cloth_tpl_create(bpy.types.Operator):
    """Create a template garment around the body"""
    bl_idname = "humanbody.cloth_tpl_create"
    bl_label = "Create Template"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return find_body_obj(context) is not None

    def execute(self, context):
        body = find_body_obj(context)
        props = context.scene.humanbody_cloth_template
        tt = props.template_type
        segs = props.segments
        # Tightness → gap: 1.0 (tight) = 0.005, 0.0 (loose) = 0.025
        gap = 0.005 + (1.0 - props.tightness) * 0.020
        t_ext = props.top_extend
        b_ext = props.bottom_extend

        _prepare_body_eval(body)
        try:
            creators = {
                'TPL_TSHIRT': lambda: _create_tpl_tshirt(context, body, segs, gap, t_ext, b_ext),
                'TPL_PANTS':  lambda: _create_tpl_pants(context, body, segs, gap, t_ext, b_ext),
                'TPL_SKIRT':  lambda: _create_tpl_skirt(context, body, segs, gap, t_ext, b_ext),
                'TPL_DRESS':  lambda: _create_tpl_dress(context, body, segs, gap, t_ext, b_ext),
            }

            garment = creators.get(tt, creators['TPL_TSHIRT'])()
        finally:
            _cleanup_body_eval()

        if garment is None:
            self.report({'ERROR'}, "Failed to create template")
            return {'CANCELLED'}

        # Push outside body to prevent clipping
        _push_outside_body(context, garment, body, offset=max(gap, 0.005))

        _add_cloth(context, garment)
        _add_collision(context, body)
        self.report({'INFO'}, f"Created {tt}: {garment.name}")
        return {'FINISHED'}
