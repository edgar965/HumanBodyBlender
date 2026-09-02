# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Ein Schlauch aus Ringen, der dem Koerper folgt.

VIERMAL DERSELBE BLOCK (01.09.2026)
===================================
In `formen_koerper.py` stand er viermal — Oberteil, Hals, Kopf, Arme —
Zeile fuer Zeile gleich::

    for i in range(n_rings):
        t = i / max(n_rings - 1, 1)
        z = oben - t * (oben - unten)
        cx, cy, r_body = Koerpermass._measure_body_at_z(body, z)
        ring = Netzbau._bmesh_ring(bm, cx, cy, z, r_body + gap, segments)
        if i == 0:
            pin_verts = list(ring)
        if rings:
            Netzbau._bridge_rings(bm, rings[-1], ring)
        rings.append(ring)

Unterschiedlich waren nur die Hoehen, der Abstand und ob nach oben hin
verjuengt wird.

WARUM AM KOERPER GEMESSEN WIRD
==============================
Ein Zylinder mit festem Radius sitzt an der Taille zu weit und an der
Brust zu eng — und bei einem anderen Charakter wieder anders. Deshalb
wird JE RING der Koerperradius auf dieser Hoehe gemessen und der Abstand
(`gap`) daraufgelegt. Das Kleidungsstueck passt damit ohne Zutun zu
jedem Morph.

DER ERSTE RING WIRD ANGENAEHT
=============================
`pin_verts` sind die Punkte des ersten Rings — bei einem Oberteil der
Schulterrand, bei einer Hose der Bund. Sie halten das Kleidungsstueck in
der Simulation; ohne sie faellt es zu Boden.
"""
from .netzbau import Netzbau


class Ringschlauch:
    u"""Ringe entlang der Hochachse, am Koerper gemessen."""

    @staticmethod
    def bauen(bm, messer, von_z, bis_z, n_rings, gap, segments,
              verjuengung=None):
        u"""Ringe von `von_z` nach `bis_z`. Zurueck: (Ringe, Nadelpunkte).

        `von_z` ist der ERSTE Ring — bei einem Oberteil also oben, bei
        einem Kopfteil unten. Die Richtung ergibt sich aus den beiden
        Werten; die Nadeln sitzen immer am ersten.

        `messer(z)` liefert `(cx, cy, radius)` an dieser Hoehe. So deckt
        derselbe Schlauch Rumpf (`_measure_body_at_z`) und Bein
        (`_measure_leg_at_z`) ab — die unterscheiden sich nur darin, was
        sie messen.

        `verjuengung(t)` darf den Radius je Ring nachziehen; `t` laeuft
        von 0 (erster Ring) bis 1. Ohne Angabe bleibt es beim gemessenen
        Radius plus `gap`.
        """
        rings = []
        pin_verts = None

        for i in range(n_rings):
            t = i / max(n_rings - 1, 1)
            z = von_z + t * (bis_z - von_z)
            cx, cy, r_body = messer(z)
            r = r_body + gap
            if verjuengung is not None:
                r *= verjuengung(t)
            ring = Netzbau._bmesh_ring(bm, cx, cy, z, r, segments)
            if i == 0:
                pin_verts = list(ring)
            if rings:
                Netzbau._bridge_rings(bm, rings[-1], ring)
            rings.append(ring)
        return rings, pin_verts
