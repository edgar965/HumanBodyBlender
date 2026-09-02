# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Eine einzelne Halbkugel, die vom Koerper wegzeigt.

AUS `_create_prim_puffer` HERAUSGELOEST (01.09.2026)
====================================================
Die Funktion war 74 Zeilen und dreifach verschachtelt: Reihen, Spalten,
Ringe — und die innerste Schleife baute die Punkte eines Rings. Wer die
Kuppelform aendern wollte, musste sich durch zwei Schleifen lesen, die
nur die Position bestimmen.

Hier steht die Kuppel, dort die Anordnung.

WARUM DIE RINGE SO GERECHNET WERDEN
===================================
Eine Halbkugel, die nach aussen zeigt, laesst sich nicht als
gewoehnliche UV-Kugel bauen: Ihre Achse ist die Richtung vom
Koerpermittelpunkt weg, und die ist je Spalte eine andere.

Deshalb wird sie in Ringen aufgebaut. `phi` laeuft von 0 bis 90 Grad;
der Ringradius folgt dem Kosinus, die Hoehe ueber der Koerperflaeche dem
Sinus. Jeder Ring liegt in der Ebene SENKRECHT zur Kuppelrichtung —
daher die Ueberkreuzung `(-dir_y, +dir_x)` in der Punktrechnung: Das ist
der um 90 Grad gedrehte Richtungsvektor.

Wird ein Ring zu klein (unter 2 mm), endet die Kuppel mit einem einzelnen
Punkt statt mit einem entarteten Ring — sonst entstehen dort Flaechen mit
null Ausdehnung, an denen Blenders Normalenrechnung stolpert.
"""
import math

#: Ab diesem Ringradius wird abgeschlossen (Meter).
KAPPENSCHWELLE = 0.002


class Kuppelbau:
    u"""Baut eine nach aussen zeigende Halbkugel in ein BMesh."""

    @staticmethod
    def bauen(bm, px, py, z_center, dir_x, dir_y, puff_r, ringe, segmente,
              brueckenbau):
        u"""Eine Kuppel. Zurueck kommt ihr aeusserster Ring (oder []).

        `brueckenbau(bm, ring_a, ring_b)` verbindet zwei Ringe — das
        macht `Netzbau._bridge_rings`; es wird uebergeben, damit dieses
        Modul nicht auf den Netzbau zeigen muss.
        """
        dome_rings = []
        for ri in range(ringe + 1):
            t = ri / ringe
            phi = t * math.pi * 0.5  # 0 to pi/2
            ring_r = puff_r * math.cos(phi)
            # Dome rises outward from body surface
            rise = puff_r * math.sin(phi)
            rcx = px + dir_x * rise
            rcy = py + dir_y * rise

            if ring_r < KAPPENSCHWELLE:
                Kuppelbau._kappe(bm, rcx, rcy, z_center, dome_rings)
                break

            ring = Kuppelbau._ring(bm, rcx, rcy, z_center, ring_r,
                                   dir_x, dir_y, segmente)
            if dome_rings:
                brueckenbau(bm, dome_rings[-1], ring)
            dome_rings.append(ring)
        return dome_rings[0] if dome_rings else []

    @staticmethod
    def _ring(bm, rcx, rcy, z_center, ring_r, dir_x, dir_y, segmente):
        u"""Ein Ring senkrecht zur Kuppelrichtung."""
        ring = []
        for si in range(segmente):
            a = 2.0 * math.pi * si / segmente
            # Ring perpendicular to dome direction
            rx = rcx + ring_r * (-dir_y * math.cos(a))
            ry = rcy + ring_r * (dir_x * math.cos(a))
            rz = z_center + ring_r * math.sin(a)
            ring.append(bm.verts.new((rx, ry, rz)))
        return ring

    @staticmethod
    def _kappe(bm, rcx, rcy, z_center, dome_rings):
        u"""Den letzten Ring zu einem Punkt schliessen."""
        cap = bm.verts.new((rcx, rcy, z_center))
        if not dome_rings:
            return cap
        prev = dome_rings[-1]
        np_ = len(prev)
        for k in range(np_):
            j = (k + 1) % np_
            bm.faces.new([prev[k], prev[j], cap])
        return cap
