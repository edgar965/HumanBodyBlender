# -*- coding: utf-8 -*-
import math
import logging
import bmesh
logger = logging.getLogger(__name__)
from .kuppelbau import Kuppelbau
from .netzbau import Netzbau
from .koerpermass import Koerpermass


class Geometrieformen:
    u"""Die frueheren Modulfunktionen, gebuendelt."""

    #: Wie weit die ovale Scheibe in X breiter ist als in Y.
    OVAL_X = 1.6

    @staticmethod
    def _scheibe(context, body, segments, radius, z_pos, name, farbe,
                 x_faktor=None):
        """Eine flache Scheibe aus ineinanderliegenden Ringen.

        RUND UND OVAL WAREN ZWEI METHODEN (01.09.2026), sechzehn Zeilen
        gleich. Verschieden waren drei Dinge: der Name, die Farbe und
        ob der Ring in X gestreckt wird — und dafuer baute die ovale
        Fassung ihren Ring selbst nach, statt `_bmesh_ring` zu rufen.

        Ineinanderliegende Ringe statt eines Faechers aus dem
        Mittelpunkt: Die Stoffsimulation braucht ueberall aehnlich
        grosse Vierecke, sonst zieht sich das Netz in der Mitte
        zusammen. Nur der innerste Ring wird zum Mittelpunkt gefaltet.
        """
        cx, cy, _ = Koerpermass._measure_body_at_z(body, z_pos)
        bm = bmesh.new()
        anzahl = max(3, int(radius / 0.03))
        mitte = bm.verts.new((cx, cy, z_pos))
        ringe = []
        for ri in range(1, anzahl + 1):
            t = ri / anzahl
            rx = None if x_faktor is None else radius * x_faktor * t
            ring = Netzbau._bmesh_ring(bm, cx, cy, z_pos, radius * t,
                                       segments, radius_x=rx)
            if ri == 1:
                n = len(ring)
                for i in range(n):
                    bm.faces.new([mitte, ring[i], ring[(i + 1) % n]])
            else:
                Netzbau._bridge_rings(bm, ringe[-1], ring)
            ringe.append(ring)
        # Genadelt wird der aeussere Ring — der Rand haelt, der Rest faellt.
        return Netzbau._finish_primitive(context, bm, name, body,
                                         ringe[-1] if ringe else [],
                                         color=farbe)

    @staticmethod
    def _create_prim_disc(context, body, segments, radius, z_pos):
        """Flat disc with concentric rings at *z_pos* for good cloth topology."""
        return Geometrieformen._scheibe(
            context, body, segments, radius, z_pos, "Cloth_Prim_Disc",
            (0.50, 0.45, 0.40, 1.0))

    @staticmethod
    def _create_prim_oval_disc(context, body, segments, radius, z_pos):
        """Elliptical disc (1.6x wider in X) at *z_pos*."""
        return Geometrieformen._scheibe(
            context, body, segments, radius, z_pos, "Cloth_Prim_OvalDisc",
            (0.45, 0.40, 0.35, 1.0), x_faktor=Geometrieformen.OVAL_X)

    @staticmethod
    def _create_prim_sphere(context, body, segments, radius, z_pos):
        """UV sphere at body center at *z_pos*."""
        cx, cy, _ = Koerpermass._measure_body_at_z(body, z_pos)
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=segments,
                                   v_segments=max(4, segments // 2),
                                   radius=radius)
        for v in bm.verts:
            v.co.x += cx
            v.co.y += cy
            v.co.z += z_pos

        # Pin: top-most ring of vertices
        bm.verts.ensure_lookup_table()
        z_max = max(v.co.z for v in bm.verts)
        pin_verts = [v for v in bm.verts if v.co.z >= z_max - 0.005]

        return Netzbau._finish_primitive(context, bm, "Cloth_Prim_Sphere", body, pin_verts,
                                 color=(0.45, 0.35, 0.30, 1.0))


    @staticmethod
    def _create_prim_triangle(context, body, segments, radius, z_pos):
        """Subdivided equilateral triangle at *z_pos*."""
        cx, cy, _ = Koerpermass._measure_body_at_z(body, z_pos)
        bm = bmesh.new()

        # Three corners of equilateral triangle (point up)
        corners = []
        for i in range(3):
            angle = 2.0 * math.pi * i / 3 - math.pi / 2
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            corners.append(bm.verts.new((x, y, z_pos)))

        bm.faces.new(corners)

        # Subdivide for cloth sim resolution
        cuts = max(2, segments // 4)
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=cuts)

        # Pin: the 3 original corner vertices (may have shifted index after subdiv)
        bm.verts.ensure_lookup_table()
        # Find outermost verts as pin
        dists = []
        for v in bm.verts:
            d = math.sqrt((v.co.x - cx) ** 2 + (v.co.y - cy) ** 2)
            dists.append((d, v))
        dists.sort(key=lambda x: -x[0])
        pin_verts = [v for _, v in dists[:3]]

        return Netzbau._finish_primitive(context, bm, "Cloth_Prim_Triangle", body, pin_verts,
                                 color=(0.40, 0.45, 0.35, 1.0))

    @staticmethod
    def _create_prim_puffer(context, body, segments, length, count):
        """Multiple half-sphere domes arranged in rows around the torso.

        *count*: number of rows.  Columns are auto-calculated from circumference.

        Die einzelne Kuppel baut `kuppelbau.py`; hier steht nur, WO sie
        hinkommt. Die Spaltenzahl richtet sich nach dem Umfang an dieser
        Hoehe — eine Reihe an der Hueft ist breiter als eine an der
        Schulter und bekommt mehr Kuppeln, ohne dass jemand rechnet.
        """
        shoulder_z = 1.30
        gap = 0.018
        row_height = length / max(count, 1)

        bm = bmesh.new()
        all_pin_verts = []
        dome_rings_n = 4
        dome_segs = max(8, segments // 4)

        for row_idx in range(count):
            z_center = shoulder_z - (row_idx + 0.5) * row_height
            cx_body, cy_body, r_body = Koerpermass._measure_body_at_z(body, z_center)
            r_base = r_body + gap

            circumference = 2.0 * math.pi * r_base
            puff_r = row_height * 0.45
            n_cols = max(4, int(circumference / (puff_r * 2.2)))

            for col_idx in range(n_cols):
                angle = 2.0 * math.pi * col_idx / n_cols
                # Stagger odd rows by half a column
                if row_idx % 2 == 1:
                    angle += math.pi / n_cols
                dome_dir_x = math.cos(angle)
                dome_dir_y = math.sin(angle)

                erster = Kuppelbau.bauen(
                    bm,
                    cx_body + r_base * dome_dir_x,
                    cy_body + r_base * dome_dir_y,
                    z_center, dome_dir_x, dome_dir_y, puff_r,
                    dome_rings_n, dome_segs, Netzbau._bridge_rings)
                # Nur die oberste Reihe wird angenaeht — sie haelt das
                # ganze Kleidungsstueck.
                if row_idx == 0:
                    all_pin_verts.extend(erster)

        return Netzbau._finish_primitive(context, bm, "Cloth_Prim_Puffer", body, all_pin_verts,
                                 color=(0.35, 0.30, 0.45, 1.0))
