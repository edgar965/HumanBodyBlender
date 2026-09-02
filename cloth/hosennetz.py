# -*- coding: utf-8 -*-
u"""Das Beinnetz einer Hose: zwei Roehren, an der Huefte verschmolzen.

STAND ZWEIMAL IM PROJEKT (01.09.2026)
=====================================
`Koerperformen._create_prim_pants` und `Schablonen._create_tpl_pants`
bauten dasselbe Netz — 22 Zeilen Wort fuer Wort gleich, bis in die
Zwischenkommentare. Verschieden waren nur acht Zahlen: Bundhoehe,
Saumhoehe, Zugabe und wie fein die Ringe liegen. Die Schablone ist
feiner (Schritt 0,012 statt 0,03) und darf oben und unten verlaengert
werden; die Grundform rechnet ihre Saumhoehe aus einer Laenge.

WIE DAS NETZ ENTSTEHT
=====================
Je Bein wird von unten nach oben ein Ring nach dem anderen gelegt und
mit dem vorigen verbunden. Unterhalb des Schritts sitzt der Ring auf
der Beinmitte; oberhalb wandert seine Mitte linear zur Koerpermitte,
waehrend der Radius der des Beins bleibt — sonst steht die Hose an der
Huefte vom Koerper ab. Zum Schluss verschmelzen die Punkte, an denen
sich beide Roehren treffen.

Die Nadelpunkte werden ERST DANACH gesucht: `remove_doubles` vergibt
die Indizes neu, eine vorher gemerkte Liste zeigt hinterher auf andere
Punkte.
"""
import bmesh

from .koerpermass import Koerpermass
from .netzbau import Netzbau

__all__ = ['Hosennetz']


class Hosennetz:
    u"""Ein Hosennetz aus gemessenen Bein- und Koerperradien."""

    #: Hoehe des Schritts — dort wechselt die Bauart von Bein auf Huefte.
    SCHRITT_Z = 0.68

    #: Punkte naeher als das verschmelzen an der Huefte zu einem.
    VERSCHMELZEN = 0.008

    #: So weit unter dem Bund gilt ein Punkt noch als Nadelpunkt.
    NADELRAND = 0.02

    @staticmethod
    def bauen(body, segments, bund_z, saum_z, zugabe, ringschritt,
              mindest_bein, mindest_huefte):
        u"""(bmesh, Nadelindizes) — das fertige Netz beider Beine.

        `ringschritt` ist der angestrebte Hoehenabstand der Ringe;
        `mindest_bein` und `mindest_huefte` sind die Untergrenzen fuer
        ihre Anzahl, damit auch eine sehr kurze Hose noch ein Netz hat.
        """
        schritt_z = Hosennetz.SCHRITT_Z
        bm = bmesh.new()
        for seite in ('left', 'right'):
            ringe = []
            Hosennetz._bein(bm, ringe, body, seite, segments, saum_z,
                            schritt_z, zugabe, ringschritt, mindest_bein)
            Hosennetz._huefte(bm, ringe, body, seite, segments, bund_z,
                              schritt_z, zugabe, ringschritt, mindest_huefte)
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:],
                                 dist=Hosennetz.VERSCHMELZEN)
        bm.verts.ensure_lookup_table()
        nadeln = [v.index for v in bm.verts
                  if v.co.z >= bund_z - Hosennetz.NADELRAND]
        return bm, nadeln

    @staticmethod
    def _bein(bm, ringe, body, seite, segments, saum_z, schritt_z,
              zugabe, ringschritt, mindestens):
        u"""Unterhalb des Schritts: jeder Ring sitzt auf der Beinmitte."""
        anzahl = max(mindestens, int((schritt_z - saum_z) / ringschritt))
        for i in range(anzahl):
            t = i / max(anzahl - 1, 1)
            z = saum_z + t * (schritt_z - saum_z)
            cx, cy, r_koerper = Koerpermass._measure_leg_at_z(body, z, seite)
            Hosennetz._anfuegen(bm, ringe, cx, cy, z, r_koerper + zugabe,
                                segments)

    @staticmethod
    def _huefte(bm, ringe, body, seite, segments, bund_z, schritt_z,
                zugabe, ringschritt, mindestens):
        u"""Oberhalb des Schritts: die Mitte wandert zur Koerpermitte.

        Der Radius bleibt der des Beins — mit dem Koerperradius stuende
        die Hose an der Huefte ab.
        """
        anzahl = max(mindestens, int((bund_z - schritt_z) / ringschritt))
        bein_cx, bein_cy, _ = Koerpermass._measure_leg_at_z(
            body, schritt_z, seite)
        for i in range(1, anzahl + 1):
            t = i / anzahl
            z = schritt_z + t * (bund_z - schritt_z)
            koerper_cx, koerper_cy, _ = Koerpermass._measure_body_at_z(
                body, z, x_limit=0.20)
            _, _, r_bein = Koerpermass._measure_leg_at_z(body, z, seite)
            cx = bein_cx + (koerper_cx - bein_cx) * t
            cy = bein_cy + (koerper_cy - bein_cy) * t
            Hosennetz._anfuegen(bm, ringe, cx, cy, z, r_bein + zugabe,
                                segments)

    @staticmethod
    def _anfuegen(bm, ringe, cx, cy, z, radius, segments):
        u"""Einen Ring legen und mit dem vorigen verbinden."""
        ring = Netzbau._bmesh_ring(bm, cx, cy, z, radius, segments)
        if ringe:
            Netzbau._bridge_rings(bm, ringe[-1], ring)
        ringe.append(ring)
