# -*- coding: utf-8 -*-
import logging
import bpy
from bpy.props import IntProperty, FloatProperty, EnumProperty
logger = logging.getLogger(__name__)
from .eigenschaften import PRIMITIVE_TYPES


class HumanBodyClothPrimitiveProps(bpy.types.PropertyGroup):
    prim_type: EnumProperty(
        name="Primitive",
        description="Type of primitive cloth shape",
        items=PRIMITIVE_TYPES,
        default='PRIM_SKIRT',
    )
    segments: IntProperty(
        name="Segments",
        description="Vertices per ring",
        default=32, min=12, max=64,
    )
    prim_length: FloatProperty(
        name="Length",
        description="Length of the garment along Z",
        default=0.40, min=0.05, max=1.5, step=1,
        precision=2, subtype='DISTANCE',
    )
    prim_flare: FloatProperty(
        name="Flare",
        description="Outward flare factor (skirt only)",
        default=0.3, min=0.0, max=2.0, step=5,
        precision=2,
    )
    prim_radius: FloatProperty(
        name="Radius",
        description="Radius for disc / sphere / triangle",
        default=0.15, min=0.02, max=1.0, step=1,
        precision=3, subtype='DISTANCE',
    )
    prim_z: FloatProperty(
        name="Z Position",
        description="Vertical position for disc / sphere / triangle",
        default=1.00, min=-0.05, max=1.80, step=1,
        precision=2, subtype='DISTANCE',
    )
    prim_count: IntProperty(
        name="Rows",
        description="Number of dome rows (puffer)",
        default=4, min=1, max=12,
    )
