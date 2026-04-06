# SPDX-License-Identifier: GPL-3.0-or-later

bl_info = {
    "name": "HumanBody",
    "author": "Edgar",
    "version": (0, 0, 33),
    "blender": (5, 0, 0),
    "location": "View3D > Sidebar > HumanBody",
    "description": "Parametric human body with Daz3D-style morphing UI",
    "category": "Mesh",
}

import bpy
from . import morphing, properties, operators
from . import rig, animation, hair, wardrobe, cloth_builder, ui
from . import assetCreator as asset_creator


def register():
    morphing.register()         # load char_defaults + morph_data
    properties.register()       # HumanBodyProperties → Scene.humanbody
    operators.register()        # all operators + material-sync handler
    rig.register()
    animation.register()
    hair.register()
    wardrobe.register()
    asset_creator.register()
    cloth_builder.register()
    ui.register()


def unregister():
    ui.unregister()
    cloth_builder.unregister()
    asset_creator.unregister()
    wardrobe.unregister()
    hair.unregister()
    animation.unregister()
    rig.unregister()
    operators.unregister()
    properties.unregister()
    morphing.unregister()
