# -*- coding: utf-8 -*-
u"""Die Garderobe — Kategorien links, Kleidungsstuecke rechts.

AUFGETEILT (01.09.2026)
=======================
`_draw_wardrobe_body` (98 Zeilen) ist in vier Methoden zerlegt; die
Gruppierung nach Kategorie steckt in `garderobengruppen.py` und braucht
kein Blender. `_draw_asset_creator_body` (89 Zeilen) liegt jetzt in
`zeichnen_assetbau.py` — samt dem Import ins Leere, der dort stand.
"""
from ..garderobe.assetsuche import Assetsuche, WARDROBE_CATEGORIES
from ..garderobe.materialvorgaben import Materialvorgaben
from .garderobengruppen import Garderobengruppen


class Garderobenseite:
    u"""Die Bedienfelder der Garderobe."""

    @staticmethod
    def _draw_wardrobe_body(layout, context):
        """Wardrobe panel with category buttons left, items right (like Parts)."""
        props = context.scene.humanbody
        obj = context.active_object

        all_assets = Assetsuche.discover_assets()
        fitted_names = {n for _, n in Assetsuche.get_fitted_assets(obj)}

        # Search bar
        row = layout.row(align=True)
        row.prop(props, "wardrobe_search", text="", icon='VIEWZOOM')

        cat_assets = Garderobengruppen.bauen(all_assets,
                                             props.wardrobe_search.lower())
        if not cat_assets:
            layout.label(text="No assets found", icon='INFO')
            return

        selected = Garderobengruppen.gewaehlt(props.wardrobe_selected,
                                              cat_assets)

        # --- Two-column split ---
        split = layout.split(factor=0.28)
        Garderobenseite._kategorien(split, cat_assets, fitted_names, selected)
        Garderobenseite._stuecke(split, obj, cat_assets.get(selected),
                                 fitted_names)

    # ------------------------------------------------------------ Bausteine

    @staticmethod
    def _kategorien(split, cat_assets, fitted_names, selected):
        u"""LINKE SPALTE: je Kategorie ein Knopf mit Anzahl.

        Eine Kategorie, aus der etwas angezogen ist, bekommt statt ihres
        Symbols einen gefuellten Punkt.
        """
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

    @staticmethod
    def _stuecke(split, obj, assets, fitted_names):
        u"""RECHTE SPALTE: je Kleidungsstueck ein Kasten."""
        right = split.column()
        if not assets:
            return
        for asset in assets:
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
                Garderobenseite._stellschrauben(box, obj, asset)

    @staticmethod
    def _stellschrauben(box, obj, asset):
        u"""Materialvorgaben, Versatz und Glaettung eines angezogenen Stuecks."""
        child = None
        for c, n in Assetsuche.get_fitted_assets(obj):
            if n == asset.name:
                child = c
                break
        if not child:
            return
        info = Assetsuche.find_asset_info(asset.name)
        if info:
            presets = Materialvorgaben.get_material_presets(info)
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

    @staticmethod
    def _draw_geo_assets_body(layout, context):
        """Draw logic for the Geometric Assets panel."""
        from ..assetCreator.geometric import GEO_TAG

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
