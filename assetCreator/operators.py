# SPDX-License-Identifier: GPL-3.0-or-later
#
# Operators and save logic for the Asset Creator.

import os
import logging

import bpy

from .preview import find_body_obj, find_preview, remove_preview
from .preview import create_preview, create_preview_from_image

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Save asset
# ---------------------------------------------------------------------------

def save_asset(context, props):
    """Save the preview mesh as a wardrobe asset.

    1. Create asset directory: data/assets/{category}/{name}/
    2. Apply modifiers (bake)
    3. Save asset.blend (mesh + material only)
    4. Generate config.yaml
    5. Invalidate wardrobe cache
    6. Remove preview, load via wardrobe
    """
    from .. import wardrobe

    preview = find_preview(context)
    if not preview:
        return False, "No preview to save"

    body = find_body_obj(context)
    if not body:
        return False, "No HumanBody character found"

    name = props.name_
    category = props.category

    # Asset directory (in HumanBody core data)
    _tools = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    _hb = os.path.join(_tools, "HumanBody") if os.path.isdir(os.path.join(_tools, "HumanBody")) else r"A:\3DTools\HumanBody"
    assets_dir = os.path.join(_hb, "data", "assets")
    cat_dir = os.path.join(assets_dir, category)
    asset_dir = os.path.join(cat_dir, name)

    os.makedirs(asset_dir, exist_ok=True)

    # Apply all modifiers to bake the mesh
    context.view_layer.objects.active = preview
    for mod in preview.modifiers[:]:
        try:
            bpy.ops.object.modifier_apply(modifier=mod.name)
        except Exception as e:
            logger.warning("Could not apply modifier %s: %s", mod.name, e)

    # Unparent but keep transform
    preview.parent = None
    preview.matrix_world = body.matrix_world.copy()

    # Save as .blend file
    blend_path = os.path.join(asset_dir, "asset.blend")

    mesh_data = preview.data
    materials = [m for m in mesh_data.materials if m]

    data_blocks = {preview, mesh_data}
    data_blocks.update(materials)
    for mat in materials:
        if mat.node_tree:
            data_blocks.add(mat.node_tree)

    bpy.data.libraries.write(blend_path, data_blocks, fake_user=True)

    # Generate config.yaml
    config_path = os.path.join(asset_dir, "config.yaml")
    _write_config_yaml(config_path, props)

    # Remove preview object
    bpy.data.objects.remove(preview, do_unlink=True)

    # Invalidate wardrobe cache
    wardrobe.invalidate_cache()

    logger.info("Saved asset: %s -> %s", name, blend_path)
    return True, blend_path


def _write_config_yaml(path, props):
    """Write a config.yaml for the saved asset."""
    lines = [
        f'name: "{props.name_}"',
        f'category: "{props.category}"',
        f'tags: []',
        f'parameters:',
        f'  offset:',
    ]

    if props.creation_mode == 'IMAGE':
        lines.append(f'    default: {props.image_offset_max}')
    else:
        lines.append(f'    default: {props.offset}')

    lines += [
        f'    min: -0.01',
        f'    max: 0.05',
        f'  smoothing:',
        f'    default: {props.smoothing}',
        f'material:',
        f'  color: [{props.color[0]:.3f}, {props.color[1]:.3f}, {props.color[2]:.3f}]',
        f'  roughness: {props.roughness}',
        f'  metallic: {props.metallic}',
        f'creation:',
    ]

    if props.creation_mode == 'IMAGE':
        lines += [
            f'  method: "image"',
            f'  image_threshold: {props.image_threshold}',
            f'  image_bg_mode: "{props.image_bg_mode}"',
            f'  image_scale: {props.image_scale}',
            f'  offset_min: {props.image_offset_min}',
            f'  offset_max: {props.image_offset_max}',
            f'  thickness: {props.thickness}',
            f'  grow: {props.grow}',
        ]
    else:
        lines += [
            f'  method: "zrange"',
            f'  z_min: {props.z_min}',
            f'  z_max: {props.z_max}',
            f'  include_arms: {str(props.include_arms).lower()}',
            f'  offset: {props.offset}',
            f'  thickness: {props.thickness}',
            f'  grow: {props.grow}',
        ]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class HUMANBODY_OT_create_asset_preview(bpy.types.Operator):
    """Create or update an asset preview from body faces"""
    bl_idname = "humanbody.create_asset_preview"
    bl_label = "Update Preview"
    bl_description = "Create/update asset preview from body shell"
    bl_options = {'REGISTER', 'UNDO'}

    # Operator properties for scripted calls (optional overrides)
    name: bpy.props.StringProperty(default="")
    category: bpy.props.StringProperty(default="")
    z_min: bpy.props.FloatProperty(default=-999)
    z_max: bpy.props.FloatProperty(default=-999)
    offset: bpy.props.FloatProperty(default=-999)
    thickness: bpy.props.FloatProperty(default=-999)
    color: bpy.props.FloatVectorProperty(size=3, default=(-1, -1, -1))
    roughness: bpy.props.FloatProperty(default=-999)
    metallic: bpy.props.FloatProperty(default=-999)
    include_arms: bpy.props.BoolProperty(default=False)
    include_arms_set: bpy.props.BoolProperty(default=False)
    grow: bpy.props.IntProperty(default=-1)

    @classmethod
    def poll(cls, context):
        return find_body_obj(context) is not None

    def execute(self, context):
        ac = context.scene.humanbody_asset_creator

        # Apply operator overrides (for scripted calls only)
        if self.name:
            ac.name_ = self.name
        if self.category:
            ac.category = self.category
        if self.z_min > -900:
            ac.z_min = self.z_min
        if self.z_max > -900:
            ac.z_max = self.z_max
        if self.offset > -900:
            ac.offset = self.offset
        if self.thickness > -900:
            ac.thickness = self.thickness
        if self.color[0] >= 0:
            ac.color = self.color
        if self.roughness > -900:
            ac.roughness = self.roughness
        if self.metallic > -900:
            ac.metallic = self.metallic
        if self.grow >= 0:
            ac.grow = self.grow
        if self.include_arms_set:
            ac.include_arms = self.include_arms

        # Mode dispatch
        if ac.creation_mode == "IMAGE":
            path = bpy.path.abspath(ac.image_path)
            if not path or not os.path.isfile(path):
                self.report({'ERROR'}, "No valid image file selected")
                return {'CANCELLED'}
            obj = create_preview_from_image(context, ac, path)
            if obj is None:
                self.report({'WARNING'},
                            "No garment faces detected — adjust threshold")
                return {'CANCELLED'}
        else:
            obj = create_preview(context, ac)
            if obj is None:
                self.report({'WARNING'},
                            "No faces in Z range — adjust sliders")
                return {'CANCELLED'}

        self.report({'INFO'},
                    f"Preview: {ac.name_} ({len(obj.data.polygons)} faces)")
        return {'FINISHED'}


class HUMANBODY_OT_save_asset(bpy.types.Operator):
    """Save the preview mesh as a permanent wardrobe asset"""
    bl_idname = "humanbody.save_asset"
    bl_label = "Save Asset"
    bl_description = "Save preview as wardrobe asset (.blend + config.yaml)"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return find_preview(context) is not None

    def execute(self, context):
        ac = context.scene.humanbody_asset_creator
        ok, msg = save_asset(context, ac)
        if ok:
            self.report({'INFO'}, f"Saved: {ac.name_} -> {msg}")
        else:
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}
        return {'FINISHED'}


class HUMANBODY_OT_delete_asset_preview(bpy.types.Operator):
    """Remove the asset preview mesh"""
    bl_idname = "humanbody.delete_asset_preview"
    bl_label = "Delete Preview"
    bl_description = "Remove the preview mesh from the scene"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return find_preview(context) is not None

    def execute(self, context):
        remove_preview(context)
        self.report({'INFO'}, "Preview removed")
        return {'FINISHED'}
