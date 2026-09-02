# -*- coding: utf-8 -*-
import logging
import bpy
from bpy.props import IntProperty, FloatProperty, EnumProperty
logger = logging.getLogger(__name__)
from .eigenschaften import TEMPLATE_TYPES


class HumanBodyClothTemplateProps(bpy.types.PropertyGroup):
    template_type: EnumProperty(
        name="Template",
        description="Type of template garment",
        items=TEMPLATE_TYPES,
        default='TPL_TSHIRT',
    )
    segments: IntProperty(
        name="Segments",
        description="Vertices per ring",
        default=32, min=16, max=64,
    )
    tightness: FloatProperty(
        name="Tightness",
        description="How tight the garment fits (0 = loose, 1 = skin-tight)",
        default=0.5, min=0.0, max=1.0, step=5,
        precision=2,
    )
    top_extend: FloatProperty(
        name="Top",
        description="Extend garment upward (positive = higher)",
        default=0.0, min=-0.30, max=0.30, step=1,
        precision=2, subtype='DISTANCE',
    )
    bottom_extend: FloatProperty(
        name="Bottom",
        description="Extend garment downward (positive = longer)",
        default=0.0, min=-0.30, max=0.50, step=1,
        precision=2, subtype='DISTANCE',
    )
