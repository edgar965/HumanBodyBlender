# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Das Bedienfeld „Cloth Builder" — fuenf Kaesten, fuenf Methoden.

AUS `zeichnen_stoff.py` HERAUSGELOEST (01.09.2026)
==================================================
`_draw_cloth_builder_body` war 119 Zeilen und zeichnete fuenf Kaesten
untereinander: Setup, Simulation, Cloth Settings, Pinning, Fit & Apply.
Die Grenzen standen als `# --- … ---` schon im Code — sie waren nur
keine Methoden.

`zeichnen()` liest sich jetzt wie das Bedienfeld aussieht. Was in einem
Kasten steht, steht in einer Methode; die Aufrufreihenfolge ist die
Reihenfolge auf dem Bildschirm.

Die Zeilen sind unveraendert uebernommen.
"""
from ..cloth.modifikatorsuche import Modifikatorsuche
from ..cloth.garmentsuche import Garmentsuche
from .stoffsimulation import Stoffsimulation


class Stoffbauseite:
    u"""Das Bedienfeld, mit dem aus einer Koerperregion Stoff wird."""

    @staticmethod
    def zeichnen(layout, context):
        """Draw logic for the Cloth Builder panel."""
        from ..assetCreator.vorschau.vorschausuche import Vorschausuche

        props = context.scene.humanbody_cloth_builder
        body = Vorschausuche.find_body_obj(context)
        garment = Garmentsuche._find_garment(context)

        has_cloth = False
        if garment:
            has_cloth = Modifikatorsuche._has_modifier(garment, 'CLOTH')

        Stoffbauseite._aufbau(layout, props, body, garment, has_cloth)
        Stoffbauseite._simulation(layout, props)
        Stoffbauseite._stoffwerte(layout, garment, has_cloth)
        Stoffbauseite._nadeln(layout, props)
        Stoffbauseite._anpassen(layout, props)

    # ---------------------------------------------------------- Die Kaesten

    @staticmethod
    def _aufbau(layout, props, body, garment, has_cloth):
        u"""Region, Weite, und was mit dem gefundenen Kleidungsstueck geht."""
        box = layout.box()
        box.label(text="Setup", icon='MODIFIER')

        # Region selector — always visible
        box.prop(props, "garment_region")
        box.prop(props, "looseness", slider=True)

        if has_cloth and garment:
            row = box.row(align=True)
            row.label(text=f"Cloth: {garment.name}", icon='MOD_CLOTH')
            cloth_mods = Modifikatorsuche._get_modifiers('CLOTH', [garment])
            if cloth_mods:
                row.prop(cloth_mods[0], "show_viewport", text="",
                         icon='HIDE_OFF' if cloth_mods[0].show_viewport else 'HIDE_ON')
            row.operator("humanbody.cloth_remove", text="", icon='X')
            # Rebuild + Remove
            row = box.row(align=True)
            row.operator("humanbody.cloth_rebuild", text="Rebuild",
                         icon='FILE_REFRESH')
            row.operator("humanbody.cloth_remove_garment", text="Remove",
                         icon='TRASH')
        elif garment:
            box.label(text=f"Target: {garment.name}", icon='MESH_DATA')
            row = box.row(align=True)
            row.scale_y = 1.3
            row.operator("humanbody.cloth_add", icon='MOD_CLOTH')
            row.operator("humanbody.cloth_remove_garment", text="",
                         icon='TRASH')
        else:
            row = box.row(align=True)
            row.scale_y = 1.3
            row.operator("humanbody.cloth_add", icon='MOD_CLOTH')

        if body:
            row = box.row(align=True)
            has_coll = Modifikatorsuche._has_modifier(body, 'COLLISION')
            icon = 'CHECKMARK' if has_coll else 'ERROR'
            row.label(text=f"Collision: {body.name}", icon=icon)

    @staticmethod
    def _simulation(layout, props):
        u"""Abspielknoepfe und die vier Einstellungen darunter."""
        box = Stoffsimulation.zeichnen(layout)
        col = box.column(align=True)
        col.prop(props, "simulation_frames")
        col.prop(props, "sim_quality")
        col.prop(props, "collision_quality")
        col.prop(props, "collision_distance")

    @staticmethod
    def _stoffwerte(layout, garment, has_cloth):
        u"""Der Blender-Modifikator selbst — nur wenn es einen gibt."""
        if not (has_cloth and garment):
            return
        cloth_mods = Modifikatorsuche._get_modifiers('CLOTH', [garment])
        if not cloth_mods:
            return
        mod = cloth_mods[0]
        box = layout.box()
        box.label(text="Cloth Settings", icon='PREFERENCES')

        col = box.column(align=True)
        col.prop(mod.collision_settings, "use_self_collision",
                 text="Self Collision")
        col.prop(mod.settings, "use_pressure")
        if mod.settings.use_pressure:
            col.prop(mod.settings, "uniform_pressure_force",
                     text="Pressure Force")
        col.prop(mod.settings, "shrink_min", text="Shrink Min")
        col.prop(mod.settings, "bending_stiffness",
                 text="Bending Stiffness")

    @staticmethod
    def _nadeln(layout, props):
        u"""Die Punkte, an denen der Stoff haengenbleibt."""
        box = layout.box()
        box.label(text="Pinning", icon='PINNED')

        col = box.column(align=True)
        col.prop(props, "pin_scale")
        col.prop(props, "pin_shape")

        row = box.row(align=True)
        row.operator("humanbody.cloth_add_pin", icon='PINNED')

        row = box.row(align=True)
        row.operator("humanbody.cloth_remove_pin", text="Remove Selected",
                     icon='UNPINNED')
        row.operator("humanbody.cloth_clear_pins", text="Clear All", icon='X')

    @staticmethod
    def _anpassen(layout, props):
        u"""Anlegen, uebernehmen, ausschuetteln."""
        box = layout.box()
        box.label(text="Fit & Apply", icon='CHECKMARK')

        col = box.column(align=True)
        col.prop(props, "fit_offset", text="Offset")
        col.prop(props, "fit_corrective_iters", text="Corrective Iterations")

        box.operator("humanbody.cloth_fit_to_body", icon='MOD_SHRINKWRAP')
        box.operator("humanbody.cloth_apply_base", icon='CHECKMARK')

        row = box.row(align=True)
        row.operator("humanbody.cloth_shake", icon='RNDCURVE')
        row.operator("humanbody.cloth_paint_weight", icon='WPAINT_HLT')
