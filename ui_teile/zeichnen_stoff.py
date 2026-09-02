# -*- coding: utf-8 -*-
u"""Die beiden Stoffseiten, die aus einem Grundkoerper oder einer Vorlage
ein Kleidungsstueck erzeugen.

AUFGETEILT (01.09.2026)
=======================
`_draw_cloth_builder_body` (119 Zeilen) liegt jetzt in
`zeichnen_stoffbau.py`, und der Simulationskasten — der hier dreimal
wortgleich stand — in `stoffsimulation.py`.
"""
from .stoffsimulation import Stoffsimulation


class Stoffseite:
    u"""Die Bedienfelder fuer Grundkoerper und Vorlagen."""

    @staticmethod
    def _draw_cloth_primitive_body(layout, context):
        """Draw logic for the Cloth Primitive panel."""
        props = context.scene.humanbody_cloth_primitive
        pt = props.prim_type

        # Primitive type selector
        layout.prop(props, "prim_type")

        col = layout.column(align=True)
        col.prop(props, "segments")

        # Body-wrap types: length
        _BODY_TYPES = {'PRIM_SKIRT', 'PRIM_PANTS', 'PRIM_TOP', 'PRIM_ARMS',
                       'PRIM_NECK', 'PRIM_HEAD', 'PRIM_SHOES', 'PRIM_PUFFER'}
        # Freeform types: radius + z position
        _FREE_TYPES = {'PRIM_DISC', 'PRIM_SPHERE', 'PRIM_OVAL_DISC', 'PRIM_TRIANGLE'}

        if pt in _BODY_TYPES:
            col.prop(props, "prim_length")
        if pt in _FREE_TYPES:
            col.prop(props, "prim_radius")
            col.prop(props, "prim_z")
        if pt == 'PRIM_SKIRT':
            col.prop(props, "prim_flare")
        if pt == 'PRIM_PUFFER':
            col.prop(props, "prim_count")

        layout.separator()

        # Create button
        row = layout.row(align=True)
        row.scale_y = 1.3
        row.operator("humanbody.cloth_prim_create", icon='MESH_CONE')

        # Simulation controls (shared)
        layout.separator()
        Stoffsimulation.zeichnen(layout)

    @staticmethod
    def _draw_cloth_template_body(layout, context):
        """Draw logic for the Cloth Template panel."""
        props = context.scene.humanbody_cloth_template

        # Template type selector
        layout.prop(props, "template_type")
        layout.prop(props, "segments")
        layout.prop(props, "tightness", slider=True)
        row = layout.row(align=True)
        row.prop(props, "top_extend")
        row.prop(props, "bottom_extend")

        layout.separator()

        # Create button
        row = layout.row(align=True)
        row.scale_y = 1.3
        row.operator("humanbody.cloth_tpl_create", icon='MOD_CLOTH')

        # Simulation controls (shared)
        layout.separator()
        Stoffsimulation.zeichnen(layout)
