# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Das Bedienfeld „Asset Creator" — sieben Kaesten untereinander.

AUS `zeichnen_garderobe.py` HERAUSGELOEST (01.09.2026)
======================================================
`_draw_asset_creator_body` war 89 Zeilen. Die Abschnitte standen als
`# --- … ---` schon da; sie sind jetzt Methoden.

EIN IMPORT INS LEERE, GLEICH DANEBEN
====================================
Die erste Zeile der Funktion lautete::

    from . import assetCreator as asset_creator

`ui_teile/assetCreator` gibt es nicht — das Paket liegt eine Ebene
hoeher. Und `find_preview` ist seit dem Aufteilen eine Methode von
`Vorschausuche`, keine Modulfunktion mehr. Zwei Fehler in einer Zeile,
die erst beim Zeichnen des Bedienfelds aufgefallen waeren: In Blender
zeigt ein Panel, dessen `draw` wirft, nur eine rote Zeile an; das Addon
laeuft weiter.

`test_addon_importe` hat die Stelle nicht gesehen, weil `from . import x`
kein `module` traegt — geprueft wurde nur der Modulpfad, nie der Name
dahinter. Die Pruefung ist seit dem 01.09.2026 erweitert.
"""
from ..assetCreator.vorschau.vorschausuche import Vorschausuche


class Assetbauseite:
    u"""Das Bedienfeld, mit dem eigene Kleidungsstuecke entstehen."""

    @staticmethod
    def zeichnen(layout, context):
        """Draw logic for the Asset Creator panel."""
        ac = context.scene.humanbody_asset_creator
        preview = Vorschausuche.find_preview(context)

        # Name + Category
        layout.prop(ac, "name_", text="Name")
        layout.prop(ac, "category")

        layout.separator()

        # --- Mode toggle ---
        row = layout.row(align=True)
        row.prop(ac, "creation_mode", expand=True)

        Assetbauseite._zbereich(layout, ac)
        Assetbauseite._bild(layout, ac)
        Assetbauseite._passform(layout, ac)
        Assetbauseite._material(layout, ac)
        Assetbauseite._knoepfe(layout, preview)
        Assetbauseite._pinsel(layout, ac, preview)

    # ---------------------------------------------------------- Die Kaesten

    @staticmethod
    def _zbereich(layout, ac):
        u"""Ausschnitt nach Hoehe — nur in der Betriebsart ZRANGE."""
        if ac.creation_mode != "ZRANGE":
            return
        box = layout.box()
        box.label(text="Cutout", icon='MOD_BOOLEAN')
        col = box.column(align=True)
        col.prop(ac, "z_max", text="Z Top")
        col.prop(ac, "z_min", text="Z Bottom")
        box.prop(ac, "include_arms")

    @staticmethod
    def _bild(layout, ac):
        u"""Umriss aus einem Bild — nur in der Betriebsart IMAGE."""
        if ac.creation_mode != "IMAGE":
            return
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

    @staticmethod
    def _passform(layout, ac):
        u"""Dicke, Glaettung, Fall — fuer beide Betriebsarten."""
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

    @staticmethod
    def _material(layout, ac):
        u"""Farbe, Rauheit, Metallanteil."""
        box = layout.box()
        box.label(text="Material", icon='MATERIAL')
        box.prop(ac, "color", text="")
        col = box.column(align=True)
        col.prop(ac, "roughness")
        col.prop(ac, "metallic")

    @staticmethod
    def _knoepfe(layout, preview):
        u"""Vorschau erzeugen, sichern, verwerfen."""
        layout.separator()

        row = layout.row(align=True)
        row.scale_y = 1.3
        row.operator("humanbody.create_asset_preview",
                     text="Update Preview", icon='FILE_REFRESH')
        if preview:
            row.operator("humanbody.save_asset",
                         text="Save Asset", icon='FILE_TICK')
        row = layout.row(align=True)
        if preview:
            row.operator("humanbody.remove_asset_preview",
                         text="Delete Preview", icon='X')
            row.label(text=f"{len(preview.data.polygons)} faces",
                      icon='MESH_DATA')

    @staticmethod
    def _pinsel(layout, ac, preview):
        u"""Den Versatz von Hand nachziehen — nur mit Vorschau."""
        if not preview:
            return
        layout.separator()
        box = layout.box()
        box.label(text="Brush Editor", icon='BRUSH_DATA')
        box.operator("humanbody.brush_offset",
                     text="Edit Offset", icon='BRUSH_DATA')
        col = box.column(align=True)
        col.prop(ac, "brush_radius")
        col.prop(ac, "brush_strength")
