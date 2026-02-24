# SPDX-License-Identifier: GPL-3.0-or-later
#
# Asset Creator subpackage for HumanBody addon.
# Creates clothing assets from body-shell faces with live preview.

import bpy

from .properties import HumanBodyAssetCreatorProps
from .operators import (
    HUMANBODY_OT_create_asset_preview,
    HUMANBODY_OT_save_asset,
    HUMANBODY_OT_delete_asset_preview,
)
from .brush import HUMANBODY_OT_brush_offset
from .preview import find_preview, find_body_obj
from .geometric import (
    HumanBodyGeoAssetProps,
    HUMANBODY_OT_create_geo_asset,
    HUMANBODY_OT_remove_geo_assets,
)

# Re-export for backward compatibility with ui.py
_find_preview = find_preview
_find_body_obj = find_body_obj

classes = (
    HumanBodyAssetCreatorProps,
    HumanBodyGeoAssetProps,
    HUMANBODY_OT_create_asset_preview,
    HUMANBODY_OT_brush_offset,
    HUMANBODY_OT_save_asset,
    HUMANBODY_OT_delete_asset_preview,
    HUMANBODY_OT_create_geo_asset,
    HUMANBODY_OT_remove_geo_assets,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.humanbody_asset_creator = bpy.props.PointerProperty(
        type=HumanBodyAssetCreatorProps)
    bpy.types.Scene.humanbody_geo_asset = bpy.props.PointerProperty(
        type=HumanBodyGeoAssetProps)


def unregister():
    if hasattr(bpy.types.Scene, "humanbody_geo_asset"):
        del bpy.types.Scene.humanbody_geo_asset
    if hasattr(bpy.types.Scene, "humanbody_asset_creator"):
        del bpy.types.Scene.humanbody_asset_creator
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
