# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Knochengewichte vom Koerper auf ein aufgesetztes Netz uebertragen.

AUS `_load_custom_hair` HERAUSGELOEST (01.09.2026)
==================================================
Fuenfunddreissig Zeilen mitten in einer Ladefunktion — und die einzige
Stelle, an der die Frisur ueberhaupt mit dem Skelett verbunden wird.
Ohne sie haengt das Haar im Raum, sobald der Kopf sich dreht.

WIE ES ARBEITET
===============
Fuer jeden Haarpunkt wird der naechstgelegene KOERPERpunkt gesucht (ueber
einen KD-Baum, sonst waere es Haarpunkte mal Koerperpunkte Vergleiche)
und dessen Gewichte werden uebernommen. Uebertragen werden nur die
`DEF-`-Gruppen: Das sind die Verformungsknochen: Nur sie bewegen
Geometrie. Die Steuerknochen des Rigify-Rigs haben keine.

Gerechnet wird in WELTkoordinaten. Haar und Koerper haben verschiedene
Objektursprunge; im eigenen Koordinatensystem laege der naechste Punkt
irgendwo.

`vg.weight(i)` WIRFT, WENN DER PUNKT NICHT IN DER GRUPPE IST
============================================================
Das ist Blenders Schnittstelle: Kein Gewicht heisst nicht „0.0", sondern
`RuntimeError`. Der leere `except` hier ist deshalb kein Verschlucken,
sondern die Uebersetzung von „steht nicht drin" nach „Gewicht null".
"""
import logging

logger = logging.getLogger(__name__)

#: Kleiner als das wird nicht uebertragen — solche Gewichte bewegen
#: nichts Sichtbares und blaehen die Gruppen auf.
SCHWELLE = 0.001


class Gewichtsuebertragung:
    u"""Uebertraegt `DEF-`-Gewichte vom naechsten Koerperpunkt."""

    @staticmethod
    def vom_koerper(koerper, ziel):
        u"""Alle `DEF-`-Gruppen des Koerpers auf `ziel` uebertragen.

        Zurueck kommt die Anzahl gesetzter Gewichte.
        """
        from mathutils.kdtree import KDTree

        # Nachschlagbaum ueber die Koerperpunkte, in Weltkoordinaten
        mat_body = koerper.matrix_world
        kd = KDTree(len(koerper.data.vertices))
        for i, v in enumerate(koerper.data.vertices):
            kd.insert(mat_body @ v.co, i)
        kd.balance()

        # Collect body DEF- vertex groups
        def_groups = {vg.index: vg for vg in koerper.vertex_groups
                      if vg.name.startswith("DEF-")}
        # Create matching groups on target
        for vg in def_groups.values():
            if vg.name not in ziel.vertex_groups:
                ziel.vertex_groups.new(name=vg.name)

        mat_ziel = ziel.matrix_world
        gesetzt = 0
        for hv in ziel.data.vertices:
            _co, body_vi, _dist = kd.find(mat_ziel @ hv.co)
            for _gi, vg in def_groups.items():
                try:
                    w = vg.weight(body_vi)
                # stumm gewollt: weight() wirft, wenn der Vertex nicht in
                # der Gruppe ist. Genau das heisst hier Gewicht null.
                except RuntimeError:
                    continue
                if w > SCHWELLE:
                    ziel.vertex_groups[vg.name].add([hv.index], w, 'REPLACE')
                    gesetzt += 1

        logger.info("Gewichte uebertragen: %d Werte aus %d DEF-Gruppen",
                    gesetzt, len(def_groups))
        return gesetzt
