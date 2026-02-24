# SPDX-License-Identifier: GPL-3.0-or-later
#
# Property definitions for the Asset Creator.

import bpy

# Asset categories for the enum
ASSET_CATEGORIES = [
    ("Tops", "Tops", ""),
    ("Bottoms", "Bottoms", ""),
    ("Full", "Full", ""),
    ("Underwear", "Underwear", ""),
    ("Shoes", "Shoes", ""),
    ("Accessories", "Accessories", ""),
]

# Z-range + arm presets per category (auto-applied on category change)
CATEGORY_PRESETS = {
    #                  z_min  z_max  arms   — body zones reference:
    #                                        feet <0.05, legs 0.05-0.70,
    #                                        pelvis 0.70-0.78, waist 0.78-0.90,
    #                                        chest 0.90-1.22, shoulders 1.22-1.32,
    #                                        neck 1.32-1.42, head >1.42
    "Tops":        {"z_min": 0.72, "z_max": 1.42, "include_arms": True},
    "Bottoms":     {"z_min": 0.06, "z_max": 0.82, "include_arms": False},
    "Full":        {"z_min": 0.06, "z_max": 1.42, "include_arms": True},
    "Underwear":   {"z_min": 0.70, "z_max": 0.88, "include_arms": False},
    "Shoes":       {"z_min": -0.01, "z_max": 0.08, "include_arms": False},
    "Accessories": None,
}


def _on_category_change(self, context):
    """Auto-set Z-range and arm toggle from category preset."""
    preset = CATEGORY_PRESETS.get(self.category)
    if preset:
        self.z_min = preset["z_min"]
        self.z_max = preset["z_max"]
        self.include_arms = preset["include_arms"]


class HumanBodyAssetCreatorProps(bpy.types.PropertyGroup):

    name_: bpy.props.StringProperty(
        name="Name",
        description="Asset name (used for filename)",
        default="new_asset",
    )
    category: bpy.props.EnumProperty(
        name="Category",
        items=ASSET_CATEGORIES,
        default="Tops",
        update=_on_category_change,
    )

    # --- Mode ---
    creation_mode: bpy.props.EnumProperty(
        name="Mode",
        items=[
            ("ZRANGE", "Z-Range", "Select faces by Z height range"),
            ("IMAGE", "Image", "Select faces from a clothing image"),
        ],
        default="ZRANGE",
    )

    # --- Z-Range settings ---
    z_min: bpy.props.FloatProperty(
        name="Z Bottom",
        description="Lower Z cutoff (world space)",
        default=0.72,
        min=-0.1, max=1.8, step=1, precision=3,
    )
    z_max: bpy.props.FloatProperty(
        name="Z Top",
        description="Upper Z cutoff (world space)",
        default=1.42,
        min=-0.1, max=1.8, step=1, precision=3,
    )
    include_arms: bpy.props.BoolProperty(
        name="Include Arms",
        description="Include arm faces (wider X range)",
        default=True,
    )
    offset: bpy.props.FloatProperty(
        name="Offset",
        description="Distance from body surface (Displace modifier)",
        default=0.005,
        min=-0.01, max=0.05, step=0.1, precision=4,
    )

    # --- Image settings ---
    image_path: bpy.props.StringProperty(
        name="Image",
        description="Path to clothing image (front view on body)",
        subtype='FILE_PATH',
    )
    image_threshold: bpy.props.FloatProperty(
        name="Threshold",
        description="Foreground detection threshold",
        default=0.5,
        min=0.0, max=1.0, step=1, precision=2,
    )
    image_bg_mode: bpy.props.EnumProperty(
        name="Background",
        items=[
            ("ALPHA", "Alpha Channel", "Use alpha for foreground detection"),
            ("DARK", "Dark BG", "Bright foreground on dark background"),
            ("LIGHT", "Light BG", "Dark foreground on light background"),
        ],
        default="ALPHA",
    )
    image_scale: bpy.props.FloatProperty(
        name="Scale",
        description="User scale factor for image fitting",
        default=1.0,
        min=0.1, max=5.0, step=1, precision=2,
    )
    image_offset_min: bpy.props.FloatProperty(
        name="Offset Min",
        description="Minimum offset for tight areas",
        default=0.001,
        min=0.0, max=0.01, step=0.1, precision=4,
    )
    image_offset_max: bpy.props.FloatProperty(
        name="Offset Max",
        description="Maximum offset for loose areas",
        default=0.02,
        min=0.001, max=0.1, step=0.1, precision=4,
    )

    # --- Shared fit settings ---
    thickness: bpy.props.FloatProperty(
        name="Thickness",
        description="Material thickness (Solidify modifier)",
        default=0.002,
        min=0.0, max=0.01, step=0.1, precision=4,
    )
    smoothing: bpy.props.FloatProperty(
        name="Smoothing",
        description="Corrective smooth strength (0 = off)",
        default=0.0,
        min=0.0, max=1.0, step=1, precision=2,
    )
    grow: bpy.props.IntProperty(
        name="Grow",
        description="Grow selection by N iterations (includes neighbor faces)",
        default=2,
        min=0, max=10,
    )
    waviness: bpy.props.FloatProperty(
        name="Waviness",
        description="Organic surface variation (0 = skin-tight, 1 = loose fabric)",
        default=0.4,
        min=0.0, max=1.0, step=1, precision=2,
    )
    drape: bpy.props.FloatProperty(
        name="Drape",
        description="Straight hang from widest point (0 = body-hugging, 1 = straight tube)",
        default=0.5,
        min=0.0, max=1.0, step=1, precision=2,
    )

    # --- Material ---
    color: bpy.props.FloatVectorProperty(
        name="Color",
        description="Base color",
        subtype='COLOR',
        default=(0.9, 0.9, 0.9),
        min=0.0, max=1.0, size=3,
    )
    roughness: bpy.props.FloatProperty(
        name="Roughness",
        description="Material roughness",
        default=0.5,
        min=0.0, max=1.0, step=1, precision=2,
    )
    metallic: bpy.props.FloatProperty(
        name="Metallic",
        description="Material metallic value",
        default=0.0,
        min=0.0, max=1.0, step=1, precision=2,
    )

    # --- Brush ---
    brush_radius: bpy.props.FloatProperty(
        name="Radius",
        description="Brush radius in world units",
        default=0.03,
        min=0.005, max=0.2, step=0.1, precision=3,
    )
    brush_strength: bpy.props.FloatProperty(
        name="Strength",
        description="Brush strength per stroke",
        default=0.05,
        min=0.001, max=0.5, step=1, precision=3,
    )
