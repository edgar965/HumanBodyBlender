# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Die vier Grundkoerper eines geometrischen Assets.

AUS `geometric.execute` HERAUSGELOEST (01.09.2026)
==================================================
Vier `elif`-Zweige mit rund vierzig Zeilen, von denen drei denselben
Aufruf machten::

    bmesh.ops.create_cone(bm, segments=…, radius1=r, radius2=r, depth=…)

Zylinder, Dreieck und Scheibe unterscheiden sich nur in der Segmentzahl
und der Tiefe — ein Dreieck ist ein Kegelstumpf mit drei Segmenten, eine
Scheibe einer mit sehr geringer Tiefe. Nur der Quader faellt heraus.

Steht das nebeneinander, sieht man es. Als vier Zweige untereinander
sieht man vier Formen.

WIE DIE MASSE ENTSTEHEN
=======================
Aus dem Huellquader der Koerperregion: die beiden kleineren Achsen
ergeben den Radius, die groesste die Hoehe. Ein Arm ist laenger als
dick, also wird der Zylinder darum laenger als dick — ohne dass jemand
je Region Werte pflegen muesste.
"""
import bmesh


class Geoformen:
    u"""Grundkoerper, aus den Massen einer Koerperregion gebaut."""

    #: Formname -> (Segmente oder None fuer „wie eingestellt",
    #: Faktor auf die Tiefe). Der Quader steht nicht darin, er hat
    #: keine Segmente.
    KEGEL = {
        'CYLINDER': (None, 1.0),
        'TRIANGLE': (3, 1.0),
        'DISC': (None, None),      # None = die duenne Scheibe
    }

    #: Dicke der Scheibe in Metern, vor der Nutzerskalierung.
    SCHEIBENDICKE = 0.002

    @staticmethod
    def masse(size, scale):
        u"""(Radius, Hoehe) aus dem Huellquader einer Region.

        Beide bekommen eine Untergrenze: Eine Region, die in einer Achse
        fast flach ist, ergaebe sonst einen Koerper ohne Ausdehnung —
        unsichtbar, aber vorhanden.
        """
        # Use the smaller two axes for radius, largest for height
        dims = sorted([size.x, size.y, size.z])
        radius = max(dims[0], dims[1]) * 0.5 * scale * 0.5
        height = dims[2] * scale * 0.5

        # Ensure minimums
        return max(radius, 0.005), max(height, 0.01)

    @staticmethod
    def bauen(shape, radius, height, segments, size, scale):
        u"""Ein frisches BMesh mit dem gewaehlten Grundkoerper."""
        bm = bmesh.new()
        if shape == 'BOX':
            Geoformen._quader(bm, size, scale)
        elif shape in Geoformen.KEGEL:
            eigene, tiefenfaktor = Geoformen.KEGEL[shape]
            tiefe = (Geoformen.SCHEIBENDICKE * scale
                     if tiefenfaktor is None else height * tiefenfaktor)
            bmesh.ops.create_cone(
                bm,
                segments=eigene if eigene is not None else segments,
                radius1=radius,
                radius2=radius,
                depth=tiefe,
            )
        return bm

    @staticmethod
    def _quader(bm, size, scale):
        u"""Ein Wuerfel, auf die Regionsmasse gezogen."""
        bmesh.ops.create_cube(bm, size=1.0)
        # Scale to match region
        bmesh.ops.scale(
            bm,
            vec=(max(size.x * scale * 0.5, 0.01),
                 max(size.y * scale * 0.5, 0.01),
                 max(size.z * scale * 0.5, 0.01)),
            verts=bm.verts[:],
        )
