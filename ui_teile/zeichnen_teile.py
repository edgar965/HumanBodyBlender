# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Das Bedienfeld „Parts" — Kategorien links, Schieber rechts.

AUS `zeichnen_koerper.py` HERAUSGELOEST (01.09.2026)
====================================================
`_draw_parts_body` war 108 Zeilen und tat drei verschiedene Dinge: Es
baute die Gruppenzuordnung (jetzt `morphgruppen.py`), zeichnete die
Kategorieknoepfe und zeichnete die Schieber. Dazwischen lagen die
Ausstiege „keine Morphdaten" und „nichts passt zum Suchtext", die man
in der Mitte der Funktion suchen musste.

Jetzt steht der Ablauf oben und passt in einen Blick.
"""
from ..morphing import Morpher
from .morphgruppen import Morphgruppen
from .zeichnen_koerper import Koerperseite
from .zonen import _MAIN_CATEGORIES
from .wahlknopf import Wahlknopf


class Teileseite:
    u"""Die Morphschieber, nach Koerperregion gruppiert."""

    @staticmethod
    def zeichnen(layout, context):
        """Shared draw logic for the Parts morph sliders with main category grouping."""
        props = context.scene.humanbody
        obj = context.active_object
        m = Morpher.get(obj)

        if not m.l2_morphs:
            layout.label(text="No morph data loaded")
            return

        Teileseite._kopf(layout, props)

        main_groups = Morphgruppen.bauen(m, props.filter_text.lower())
        if not main_groups:
            layout.label(text="No morphs match filter")
            return

        selected = Teileseite._gewaehlt(props.parts_selected, main_groups)

        # --- Two-column split: main categories left, sliders right ---
        split = layout.split(factor=0.22)
        Teileseite._kategorien(split, obj, main_groups, selected)
        Teileseite._schieber(split, obj, main_groups.get(selected))

    # ------------------------------------------------------------ Bausteine

    @staticmethod
    def _kopf(layout, props):
        u"""Der Knopf „am Modell waehlen" und das Suchfeld."""
        # Derselbe Umschalter wie im Hauptpanel, hier der Bequemlichkeit
        # halber ueber dem Teilebaum.
        Wahlknopf.zeichnen(layout)

        # Search bar
        row = layout.row(align=True)
        row.prop(props, "filter_text", text="", icon='VIEWZOOM')

    @staticmethod
    def _gewaehlt(selected, main_groups):
        u"""Die angezeigte Hauptgruppe — die erste, wenn keine passt."""
        ordered_mains = [name for name, _ in _MAIN_CATEGORIES
                         if name in main_groups]
        if (not selected or selected not in main_groups) and ordered_mains:
            return ordered_mains[0]
        return selected

    @staticmethod
    def _kategorien(split, obj, main_groups, selected):
        u"""LINKE SPALTE: ein Knopf je Hauptgruppe.

        Eine Gruppe, in der etwas verstellt ist, bekommt statt ihres
        Symbols einen gefuellten Punkt.
        """
        left = split.column(align=True)
        obj_data = obj.data
        for main_name, main_icon in _MAIN_CATEGORIES:
            if main_name not in main_groups:
                continue
            is_selected = (selected == main_name)
            nonzero = Morphgruppen.verstellt(obj_data, main_groups[main_name])

            icon = main_icon if not nonzero else 'RADIOBUT_ON'
            op = left.operator("humanbody.select_category",
                               text=main_name,
                               depress=is_selected,
                               icon=icon)
            op.category = main_name

    @staticmethod
    def _schieber(split, obj, subcats):
        u"""RECHTE SPALTE: je Unterkategorie ein Kasten mit Schiebern."""
        right = split.column()
        if not subcats:
            return
        for sub_name in sorted(subcats.keys()):
            # Subcategory header
            box = right.box()
            box.label(text=sub_name, icon='MESH_DATA')
            col = box.column(align=True)
            for morph in subcats[sub_name]:
                Koerperseite._draw_daz_custom_prop(
                    col, obj, "hb_L2_" + morph.name,
                    Morphgruppen.kurzname(morph.name, sub_name))
