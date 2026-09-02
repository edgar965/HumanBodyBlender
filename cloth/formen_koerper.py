# -*- coding: utf-8 -*-
import logging
import bmesh
logger = logging.getLogger(__name__)
from .netzbau import Netzbau
from .hosennetz import Hosennetz
from .ringschlauch import Ringschlauch
from .koerpermass import Koerpermass


class Koerperformen:
    u"""Die frueheren Modulfunktionen, gebuendelt."""

    @staticmethod
    def _create_prim_skirt(context, body, segments, length, flare):
        """Open cone from waist downward."""
        waist_z = 0.92
        gap = 0.015
        cx, cy, r_body = Koerpermass._measure_body_at_z(body, waist_z)

        bm = bmesh.new()
        # Der Rock misst den Koerper EINMAL an der Taille und weitet
        # sich von dort — anders als Oberteil oder Hose, die auf jeder
        # Hoehe neu messen. Deshalb ein fester Messwert und die
        # Verjuengung als Weitung.
        #
        # NICHT BITGLEICH mit der frueheren Fassung: Die rechnete
        # `waist_z - t * length`, der Schlauch rechnet
        # `von_z + t * (bis_z - von_z)`. `0.92 - 0.2` ist als Gleitkomma
        # nicht genau 0,72, also ist die Schrittweite im letzten Bit
        # anders. Gemessen ueber 18 Faelle (Laenge/Weitung/Segmente):
        # hoechstens 1,1e-16 m, ausschliesslich in Z — das letzte Bit
        # eines double, ein Zehntel Femtometer.
        _, pin_verts = Ringschlauch.bauen(
            bm, lambda z: (cx, cy, r_body), waist_z, waist_z - length,
            max(3, int(length / 0.03)), gap, segments,
            verjuengung=lambda t: 1.0 + flare * t)
        return Netzbau._finish_primitive(context, bm, "Cloth_Prim_Skirt",
                                         body, pin_verts)

    @staticmethod
    def _create_prim_top(context, body, segments, length):
        """Open cylinder around torso from shoulders down."""
        shoulder_z = 1.30
        gap = 0.015
        bottom_z = max(shoulder_z - length, 0.70)

        n_rings = max(3, int((shoulder_z - bottom_z) / 0.03))
        bm = bmesh.new()
        _rings, pin_verts = Ringschlauch.bauen(
            bm, lambda z: Koerpermass._measure_body_at_z(body, z, x_limit=0.20),
            shoulder_z, bottom_z, n_rings, gap, segments)

        return Netzbau._finish_primitive(context, bm, "Cloth_Prim_Top", body, pin_verts,
                                 color=(0.35, 0.25, 0.20, 1.0))

    @staticmethod
    def _create_prim_pants(context, body, segments, length):
        """Zwei Roehren fuer die Beine, an der Huefte verschmolzen.

        Das Netz baut `Hosennetz` — es stand bis zum 01.09.2026 hier und
        in `Schablonen._create_tpl_pants` je einmal, Wort fuer Wort
        gleich. Der Unterschied sind die Zahlen: Diese Grundform rechnet
        ihre Saumhoehe aus der Laenge und legt die Ringe grob (0,03).
        """
        bund_z = 0.92
        bm, nadeln = Hosennetz.bauen(
            body, segments, bund_z, max(bund_z - length, 0.06),
            zugabe=0.012, ringschritt=0.03, mindest_bein=2, mindest_huefte=2)
        return Netzbau._finish_primitive(context, bm, "Cloth_Prim_Pants", body,
                                         nadeln, color=(0.15, 0.18, 0.35, 1.0))

    @staticmethod
    def _create_prim_arms(context, body, segments, length):
        """Tubes around both arms (YZ-plane rings perpendicular to arm axis)."""
        shoulder_x = 0.22  # where arm starts laterally
        gap = 0.012

        bm = bmesh.new()
        all_pin_verts = []

        for side in ('left', 'right'):
            sign = 1.0 if side == 'left' else -1.0
            rings = []
            n_rings = max(3, int(length / 0.03))
            for i in range(n_rings):
                t = i / max(n_rings - 1, 1)
                x = sign * (shoulder_x + t * length)
                cy, cz, r_arm = Koerpermass._measure_arm_at_x(body, x)
                r = r_arm + gap
                ring = Netzbau._bmesh_ring_yz(bm, x, cy, cz, r, segments)
                if i == 0:
                    all_pin_verts.extend(ring)
                if rings:
                    Netzbau._bridge_rings(bm, rings[-1], ring)
                rings.append(ring)

        return Netzbau._finish_primitive(context, bm, "Cloth_Prim_Arms", body, all_pin_verts,
                                 color=(0.35, 0.25, 0.20, 1.0))

    @staticmethod
    def _create_prim_neck(context, body, segments, length):
        """Tube around the neck."""
        neck_top_z = 1.42
        gap = 0.010
        neck_bot_z = max(neck_top_z - length, 1.28)

        n_rings = max(3, int((neck_top_z - neck_bot_z) / 0.02))
        bm = bmesh.new()
        _rings, pin_verts = Ringschlauch.bauen(
            bm, lambda z: Koerpermass._measure_body_at_z(body, z, z_tol=0.02),
            neck_top_z, neck_bot_z, n_rings, gap, segments)

        return Netzbau._finish_primitive(context, bm, "Cloth_Prim_Neck", body, pin_verts,
                                 color=(0.40, 0.35, 0.30, 1.0))

    @staticmethod
    def _create_prim_head(context, body, segments, length):
        """Tube/cap around the head."""
        head_top_z = 1.68
        gap = 0.012
        head_bot_z = max(head_top_z - length, 1.42)

        n_rings = max(3, int((head_top_z - head_bot_z) / 0.02))
        bm = bmesh.new()
        rings, pin_verts = Ringschlauch.bauen(
            bm, lambda z: Koerpermass._measure_body_at_z(body, z, z_tol=0.02),
            head_bot_z, head_top_z, n_rings, gap, segments,
            # Taper towards top
            verjuengung=lambda t: 1.0 - 0.3 * t * t)

        # Close top with a fan
        if rings:
            Netzbau.kappe_fan(bm, rings[-1], head_top_z + 0.02)

        return Netzbau._finish_primitive(context, bm, "Cloth_Prim_Head", body, pin_verts,
                                 color=(0.50, 0.40, 0.35, 1.0))

    @staticmethod
    def _create_prim_shoes(context, body, segments, length):
        """Tubes around both feet."""
        ankle_z = 0.10
        gap = 0.010
        toe_z = max(ankle_z - length, -0.02)

        bm = bmesh.new()
        all_pin_verts = []

        for side in ('left', 'right'):
            n_rings = max(3, int((ankle_z - toe_z) / 0.02))
            rings, pin_verts = Ringschlauch.bauen(
                bm,
                lambda z, s=side: Koerpermass._measure_leg_at_z(
                    body, z, s, z_tol=0.02),
                ankle_z, toe_z, n_rings, gap, segments,
                # Slight taper at toe
                verjuengung=lambda t: (1.0 - 0.2 * ((t - 0.6) / 0.4)
                                       if t > 0.6 else 1.0))
            all_pin_verts.extend(pin_verts or [])

            # Close toe with fan
            if rings:
                Netzbau.kappe_fan(bm, rings[-1], toe_z - 0.01)

        return Netzbau._finish_primitive(context, bm, "Cloth_Prim_Shoes", body, all_pin_verts,
                                 color=(0.12, 0.10, 0.08, 1.0))
