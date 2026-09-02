# -*- coding: utf-8 -*-
import logging
import bpy
from bpy.props import (IntProperty, FloatProperty, BoolProperty, EnumProperty)
from ..cloth.kleidungsregionen import Kleidungsregionen

# Die Bauteile liegen in `cloth/`. Hier bleibt, was Blender
# sieht: die Klassen und die Anmeldung.
from .stofffelder import Stofffelder
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


class HumanBodyClothBuilderProps(bpy.types.PropertyGroup):
    garment_region: EnumProperty(
        name="Garment",
        description="Body region for garment creation",
        items=Kleidungsregionen.AUSWAHL,
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
        update=Stofffelder._on_setting_update,
    )
    sim_quality: IntProperty(
        name="Sim Quality",
        description="Cloth simulation quality steps",
        default=4, min=1, max=20, soft_max=5,
        update=Stofffelder._on_setting_update,
    )
    collision_quality: IntProperty(
        name="Collision Quality",
        description="Collision detection quality",
        default=2, min=1, max=20, soft_max=5,
        update=Stofffelder._on_setting_update,
    )
    collision_distance: FloatProperty(
        name="Collision Distance",
        description="Inner and outer collision distance",
        default=0.005, min=0.0, max=1.0, step=0.1,
        precision=4,
        update=Stofffelder._on_setting_update,
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
