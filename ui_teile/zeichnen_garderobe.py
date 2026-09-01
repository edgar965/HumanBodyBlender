# -*- coding: utf-8 -*-
from .. import wardrobe
from ..wardrobe import WARDROBE_CATEGORIES


def _draw_wardrobe_body(layout, context):
    """Wardrobe panel with category buttons left, items right (like Parts)."""
    props = context.scene.humanbody
    obj = context.active_object

    all_assets = wardrobe.discover_assets()
    fitted_names = {n for _, n in wardrobe.get_fitted_assets(obj)}

    # Search bar
    row = layout.row(align=True)
    row.prop(props, "wardrobe_search", text="", icon='VIEWZOOM')

    search = props.wardrobe_search.lower()

    # Group assets by category
    cat_assets = {}
    for a in all_assets:
        if a.category == "Hair":
            continue  # Hair is in the Hair panel
        if search and search not in a.name.lower() and \
           not any(search in t.lower() for t in a.tags):
            continue
        cat = a.category
        if cat not in cat_assets:
            cat_assets[cat] = []
        cat_assets[cat].append(a)

    if not cat_assets:
        layout.label(text="No assets found", icon='INFO')
        return

    # Auto-select first category
    selected = props.wardrobe_selected
    ordered = [name for name, _ in WARDROBE_CATEGORIES if name in cat_assets]
    if (not selected or selected not in cat_assets) and ordered:
        selected = ordered[0]

    # --- Two-column split ---
    split = layout.split(factor=0.28)

    # LEFT: category buttons
    left = split.column(align=True)
    for cat_name, cat_icon in WARDROBE_CATEGORIES:
        if cat_name not in cat_assets:
            continue
        count = len(cat_assets[cat_name])
        fitted_count = sum(1 for a in cat_assets[cat_name]
                           if a.name in fitted_names)
        is_sel = (selected == cat_name)
        icon = 'RADIOBUT_ON' if fitted_count > 0 else cat_icon
        op = left.operator("humanbody.select_wardrobe_cat",
                           text=f"{cat_name} ({count})",
                           depress=is_sel, icon=icon)
        op.category = cat_name

    # RIGHT: items in selected category
    right = split.column()

    if selected and selected in cat_assets:
        for asset in cat_assets[selected]:
            is_fitted = asset.name in fitted_names
            box = right.box()
            row = box.row(align=True)
            row.label(text=asset.label,
                      icon='CHECKMARK' if is_fitted else 'MESH_DATA')
            if is_fitted:
                op = row.operator("humanbody.wardrobe_remove",
                                  text="", icon='X')
                op.asset_name = asset.name
            else:
                op = row.operator("humanbody.wardrobe_add",
                                  text="", icon='ADD')
                op.asset_name = asset.name

            # Show controls for fitted assets
            if is_fitted:
                child = None
                for c, n in wardrobe.get_fitted_assets(obj):
                    if n == asset.name:
                        child = c
                        break
                if child:
                    info = wardrobe.find_asset_info(asset.name)
                    if info:
                        presets = wardrobe.get_material_presets(info)
                        if presets:
                            row2 = box.row(align=True)
                            for key, label in presets.items():
                                op = row2.operator(
                                    "humanbody.wardrobe_preset", text=label)
                                op.asset_name = asset.name
                                op.preset_key = key
                    offset_mod = child.modifiers.get("hb_offset")
                    if offset_mod:
                        box.prop(offset_mod, "strength", text="Offset")
                    smooth_mod = child.modifiers.get("hb_smooth")
                    if smooth_mod:
                        box.prop(smooth_mod, "iterations", text="Smoothing")


def _draw_asset_creator_body(layout, context):
    """Draw logic for the Asset Creator panel."""
    from . import assetCreator as asset_creator

    ac = context.scene.humanbody_asset_creator
    preview = asset_creator.find_preview(context)

    # Name + Category
    layout.prop(ac, "name_", text="Name")
    layout.prop(ac, "category")

    layout.separator()

    # --- Mode toggle ---
    row = layout.row(align=True)
    row.prop(ac, "creation_mode", expand=True)

    # --- Z-Range mode ---
    if ac.creation_mode == "ZRANGE":
        box = layout.box()
        box.label(text="Cutout", icon='MOD_BOOLEAN')
        col = box.column(align=True)
        col.prop(ac, "z_max", text="Z Top")
        col.prop(ac, "z_min", text="Z Bottom")
        box.prop(ac, "include_arms")

    # --- Image mode ---
    if ac.creation_mode == "IMAGE":
        box = layout.box()
        box.label(text="Image", icon='IMAGE_DATA')
        box.prop(ac, "image_path", text="")
        col = box.column(align=True)
        col.prop(ac, "image_bg_mode")
        col.prop(ac, "image_threshold")
        col.prop(ac, "image_scale")

        box2 = layout.box()
        box2.label(text="Offset Range", icon='DRIVER_DISTANCE')
        col = box2.column(align=True)
        col.prop(ac, "image_offset_min", text="Min")
        col.prop(ac, "image_offset_max", text="Max")

    # --- Passform (shared) ---
    box = layout.box()
    box.label(text="Fit", icon='MOD_CLOTH')
    col = box.column(align=True)
    if ac.creation_mode == "ZRANGE":
        col.prop(ac, "offset")
    col.prop(ac, "thickness")
    col.prop(ac, "smoothing")
    col.prop(ac, "waviness")
    col.prop(ac, "drape")
    col.prop(ac, "grow")

    # --- Material ---
    box = layout.box()
    box.label(text="Material", icon='MATERIAL')
    box.prop(ac, "color", text="")
    col = box.column(align=True)
    col.prop(ac, "roughness")
    col.prop(ac, "metallic")

    layout.separator()

    # --- Buttons ---
    row = layout.row(align=True)
    row.scale_y = 1.3
    row.operator("humanbody.create_asset_preview",
                 text="Update Preview", icon='FILE_REFRESH')
    if preview:
        row.operator("humanbody.save_asset",
                     text="Save Asset", icon='FILE_TICK')
    row = layout.row(align=True)
    if preview:
        row.operator("humanbody.delete_asset_preview",
                     text="Delete Preview", icon='X')
        row.label(text=f"{len(preview.data.polygons)} faces",
                  icon='MESH_DATA')

    # --- Brush Editor ---
    if preview:
        layout.separator()
        box = layout.box()
        box.label(text="Brush Editor", icon='BRUSH_DATA')
        box.operator("humanbody.brush_offset",
                     text="Edit Offset", icon='BRUSH_DATA')
        col = box.column(align=True)
        col.prop(ac, "brush_radius")
        col.prop(ac, "brush_strength")


def _draw_geo_assets_body(layout, context):
    """Draw logic for the Geometric Assets panel."""
    from .assetCreator.geometric import GEO_TAG

    props = context.scene.humanbody_geo_asset

    layout.prop(props, "region")
    layout.prop(props, "shape")

    layout.separator()

    col = layout.column(align=True)
    col.prop(props, "offset")
    col.prop(props, "scale")
    col.prop(props, "segments")

    layout.separator()
    layout.prop(props, "color")

    layout.separator()

    row = layout.row(align=True)
    row.scale_y = 1.3
    row.operator("humanbody.create_geo_asset", icon='MESH_CYLINDER')

    # "Alle entfernen" only when geo assets exist
    has_geo = any(obj.get(GEO_TAG) for obj in context.scene.objects)
    if has_geo:
        row = layout.row(align=True)
        row.operator("humanbody.remove_geo_assets", icon='X')
