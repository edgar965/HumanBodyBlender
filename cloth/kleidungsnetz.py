# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Aus dem Koerpernetz wird ein Kleidungsnetz — die reine bmesh-Arbeit.

AUS `_create_garment` HERAUSGELOEST (01.09.2026)
================================================
Die Funktion war 133 Zeilen lang und tat vier Dinge nacheinander:
Flaechen waehlen, das Netz aufblasen, die Naehpunkte suchen, ein
Blender-Objekt bauen. Die ersten drei brauchen nur `bmesh` und eine
Matrix; das vierte haengt an `bpy.data` und legt Material, Modifikator
und Elternschaft an.

Hier stehen die ersten drei. Sie lassen sich einzeln lesen und einzeln
aendern — die Zahlen darin (4 mm bis 20 mm Versatz, oberste 15 % als
Naht) sind Stellschrauben, die man sonst in einer Bildschirmseite Code
suchen muss.

Die Rumpfe sind unveraendert uebernommen.
"""
import bmesh

from ..assetCreator.vorschau.flaechenwahl import Flaechenwahl


class Kleidungsnetz:
    u"""Die drei Netzschritte zwischen Koerper und Kleidungsstueck."""

    @staticmethod
    def waehlen(bm, mat_w, preset):
        u"""Alles wegschneiden, was nicht zur Region gehoert.

        True, wenn danach noch Flaechen uebrig sind. Bei `False` hat der
        Filter alles verworfen — dann gibt es kein Kleidungsstueck.
        """
        z_min = preset['z_min']
        z_max = preset['z_max']
        include_arms = preset['arms']
        category = preset['cat']
        x_limit = 0.50 if include_arms else 0.30

        for f in bm.faces:
            f.select = False

        for face in bm.faces:
            center = mat_w @ face.calc_center_median()
            if z_min <= center.z <= z_max:
                if abs(center.x) <= x_limit:
                    if category is None or Flaechenwahl._face_allowed_for_category(center, category):
                        face.select = True
                elif include_arms:
                    if category is None or Flaechenwahl._face_allowed_for_category(center, category):
                        face.select = True

        Flaechenwahl._grow_selection(bm, preset.get('grow', 2))

        faces_to_delete = [f for f in bm.faces if not f.select]
        bmesh.ops.delete(bm, geom=faces_to_delete, context='FACES')
        return len(bm.faces) > 0

    @staticmethod
    def aufblasen(bm, looseness):
        u"""Entlang der Normalen nach aussen schieben und glaetten.

        Das Koerpernetz umschliesst jedes Bein und jeden Arm bereits
        einzeln — ein Versatz entlang der Normalen ergibt deshalb ein
        Kleidungsstueck, das sich an jedes Glied anlegt. Zylindermathematik
        braucht es dafuer nicht; die Weite kommt spaeter aus der
        Simulation (Schrumpf und Druck).

        Zurueck kommt der verwendete Versatz — das Protokoll nennt ihn.
        """
        bm.verts.ensure_lookup_table()
        bm.normal_update()

        offset = 0.004 + looseness * 0.008  # 4mm (tight) to 20mm (loose)
        for v in bm.verts:
            v.co = v.co + v.normal * offset

        # Light smoothing to clean seam artifacts
        all_verts = list(bm.verts)
        smooth_iters = 3 + int(looseness * 5)
        for _ in range(smooth_iters):
            bmesh.ops.smooth_vert(bm, verts=all_verts, factor=0.5,
                                  use_axis_x=True, use_axis_y=True,
                                  use_axis_z=True)
        return offset

    @staticmethod
    def naehpunkte(bm, mat_w):
        u"""Die Punkte am oberen Rand — Bund oder Halsausschnitt.

        Gesucht sind die Randkanten; davon bleibt das oberste Sechstel
        der Hoehe. `modifikatoren._add_cloth` haengt daran spaeter die
        Vertexgruppe `pinned`.
        """
        bm.edges.ensure_lookup_table()
        boundary_verts = set()
        for edge in bm.edges:
            if edge.is_boundary:
                boundary_verts.add(edge.verts[0].index)
                boundary_verts.add(edge.verts[1].index)

        # Find Z-range of boundary and pin the top portion
        if not boundary_verts:
            return []
        bv_z = [(vi, (mat_w @ bm.verts[vi].co).z) for vi in boundary_verts]
        z_top = max(z for _, z in bv_z)
        z_bot = min(z for _, z in bv_z)
        z_span = z_top - z_bot
        # Pin boundary verts in the top 15% of the garment height
        pin_threshold = z_top - z_span * 0.15
        return [vi for vi, z in bv_z if z >= pin_threshold]
