# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Welcher Morph in welche Gruppe gehoert — ohne Blender-Oberflaeche.

AUS `_draw_parts_body` HERAUSGELOEST (01.09.2026)
=================================================
Die Zeichenfunktion war 108 Zeilen, und ihre ersten vierzig taten
ueberhaupt nichts Sichtbares: Sie ordneten die Morphs nach Hauptgruppe
und Unterkategorie, je nachdem, ob ein Suchtext gesetzt ist. Reine
Datenarbeit, mitten im Layoutcode.

Hier steht sie fuer sich. Der Unterschied ist nicht nur Ordnung: Diese
Zuordnung laesst sich pruefen, ohne dass Blender laeuft — die
Zeichenfunktion nicht.
"""
from .zonen import Zonen


class Morphgruppen:
    u"""Ordnet Morphs nach Hauptgruppe und Unterkategorie."""

    @staticmethod
    def bauen(morpher, filt):
        u"""``{Hauptgruppe: {Unterkategorie: [Morph, …]}}``.

        Mit Suchtext wird ueber alle Morphs gefiltert, ohne ihn werden
        die fertigen Kategorien des Morphers uebernommen — das ist der
        haeufige Fall und spart den Durchlauf.
        """
        main_groups = {}
        if filt:
            for morph in morpher.l2_morphs:
                if filt not in morph.name.lower():
                    continue
                main = Zonen._group_category(morph.category)
                if main not in main_groups:
                    main_groups[main] = {}
                sub = morph.category
                if sub not in main_groups[main]:
                    main_groups[main][sub] = []
                main_groups[main][sub].append(morph)
        else:
            for cat, morphs in morpher._categories.items():
                main = Zonen._group_category(cat)
                if main not in main_groups:
                    main_groups[main] = {}
                main_groups[main][cat] = morphs
        return main_groups

    @staticmethod
    def verstellt(obj_data, untergruppen):
        u"""Steht in dieser Hauptgruppe irgendein Morph auf einem Wert?

        Die Oberflaeche zeigt daran, welche Gruppe der Nutzer schon
        angefasst hat.
        """
        for morphs in untergruppen.values():
            for morph in morphs:
                if abs(obj_data.get("hb_L2_" + morph.name, 0.0)) > 0.001:
                    return True
        return False

    @staticmethod
    def kurzname(voller_name, unterkategorie):
        u"""Der Morphname ohne die vorangestellte Unterkategorie."""
        prefix = unterkategorie + "_"
        kurz = voller_name
        if kurz.startswith(prefix):
            kurz = kurz[len(prefix):]
        return kurz.replace("_", " ")
