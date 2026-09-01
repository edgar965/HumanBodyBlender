# -*- coding: utf-8 -*-
import logging
import bpy
from bpy.props import (IntProperty, FloatProperty, BoolProperty, EnumProperty)
from ..cloth.kleidungsstueck import GARMENT_REGIONS
from ..cloth.modifikatoren import _sync_modifier_settings
logger = logging.getLogger(__name__)


PRIMITIVE_TYPES = [
    ('PRIM_SKIRT',      "Skirt",       "Open cone from waist"),
    ('PRIM_PANTS',      "Pants",       "Two tubes for legs"),
    ('PRIM_TOP',        "Top",         "Cylinder around torso"),
    ('PRIM_ARMS',       "Arms",        "Tubes around both arms"),
    ('PRIM_NECK',       "Neck",        "Tube around neck"),
    ('PRIM_HEAD',       "Head",        "Cap around head"),
    ('PRIM_SHOES',      "Shoes",       "Tubes around feet"),
    ('PRIM_DISC',       "Disc",        "Flat circular disc"),
    ('PRIM_SPHERE',     "Sphere",      "UV sphere"),
    ('PRIM_OVAL_DISC',  "Oval Disc",   "Elliptical disc"),
    ('PRIM_TRIANGLE',   "Triangle",    "Subdivided triangle"),
    ('PRIM_PUFFER',     "Puffer",      "Half-sphere domes (down jacket)"),
]


TEMPLATE_TYPES = [
    ('TPL_TSHIRT', "T-Shirt", "Torso + arm sleeves"),
    ('TPL_PANTS',  "Pants",   "Body-conforming trousers"),
    ('TPL_SKIRT',  "Skirt",   "Measured waist skirt"),
    ('TPL_DRESS',  "Dress",   "Torso + skirt combo"),
]


def _on_setting_update(self, context):
    _sync_modifier_settings(context)


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


class HumanBodyClothBuilderProps(bpy.types.PropertyGroup):
    garment_region: EnumProperty(
        name="Garment",
        description="Body region for garment creation",
        items=GARMENT_REGIONS,
        default='TOP',
    )
    looseness: FloatProperty(
        name="Looseness",
        description="How loose the garment fits (0 = skin-tight, 2 = very loose / cylindrical)",
        default=0.5, min=0.0, max=2.0, soft_max=1.5, step=5,
        precision=2,
    )
    simulation_frames: IntProperty(
        name="Simulation Frames",
        description="End frame for cloth simulation cache",
        default=5000, min=1, soft_max=10000,
        update=_on_setting_update,
    )
    sim_quality: IntProperty(
        name="Sim Quality",
        description="Cloth simulation quality steps",
        default=4, min=1, max=20, soft_max=5,
        update=_on_setting_update,
    )
    collision_quality: IntProperty(
        name="Collision Quality",
        description="Collision detection quality",
        default=2, min=1, max=20, soft_max=5,
        update=_on_setting_update,
    )
    collision_distance: FloatProperty(
        name="Collision Distance",
        description="Inner and outer collision distance",
        default=0.005, min=0.0, max=1.0, step=0.1,
        precision=4,
        update=_on_setting_update,
    )
    use_triangulate: BoolProperty(
        name="Triangulate",
        description="Add triangulate modifier after cloth for better simulation",
        default=True,
    )
    pin_scale: FloatProperty(
        name="Pin Scale",
        description="Display size of pin empties",
        default=0.1, min=0.001, max=1.0,
    )
    pin_shape: EnumProperty(
        name="Pin Shape",
        description="Display shape for pin empties",
        items=[
            ('PLAIN_AXES', "Plain Axes", ""),
            ('ARROWS', "Arrows", ""),
            ('CIRCLE', "Circle", ""),
            ('CUBE', "Cube", ""),
            ('SPHERE', "Sphere", ""),
            ('CONE', "Cone", ""),
        ],
        default='PLAIN_AXES',
    )
    fit_offset: FloatProperty(
        name="Fit Offset",
        description="Shrinkwrap offset distance for fit-to-body",
        default=0.01, min=0.0, max=0.5, step=0.1,
        precision=4,
    )
    fit_corrective_iters: IntProperty(
        name="Corrective Iterations",
        description="Corrective smooth iterations for fit-to-body",
        default=5, min=0, max=50,
    )
