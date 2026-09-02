# -*- coding: utf-8 -*-
u"""Ein Kleidungsstueck aus dem Umriss eines Bildes.

AUFGETEILT (01.09.2026)
=======================
`create_preview_from_image` war 129 Zeilen. Die fuenf Schritte, die ihr
Docstring aufzaehlt, sind jetzt fuenf Methoden — vorher standen sie
untereinander im selben Rumpf, verbunden ueber ein Dutzend
Zwischenwerte.

Die sieben Werte der Bild-zu-Koerper-Abbildung liegen in
`bildabbildung.py`; sie wurden vorher einzeln durch drei Aufrufe
gereicht.

Dabei fiel `remaining_xz` weg: ein Feld mit einer Zeile je Netzpunkt,
gefuellt in derselben Schleife wie `remaining_z` — und nie gelesen.
"""
import logging

import bmesh
import numpy as np

from ..image_analysis import Bildanalyse
from .bildabbildung import Bildabbildung
from .drapierung import Drapierung
from .flaechenwahl import Flaechenwahl
from .vorschausuche import Vorschausuche

logger = logging.getLogger(__name__)


class Bildvorschau:
    u"""Der Ablauf vom Bild zum Vorschaunetz."""

    @staticmethod
    def create_preview_from_image(context, props, image_path):
        """Create a preview mesh using image-based garment detection.

        1. Load image → foreground mask
        2. Project body vertices (x, z) into image space
        3. Classify faces as covered / not covered
        4. Compute per-vertex offset weights from silhouette analysis
        5. Build preview with variable Displace
        """
        gefunden = Vorschausuche.koerpernetz(context)
        if not gefunden:
            return None
        body, eval_obj, eval_mesh = gefunden
        mat_w = body.matrix_world

        body_bvh = Bildvorschau._koerperbaum(eval_mesh)
        verts_xz = Bildvorschau._punkte_xz(eval_mesh, mat_w)
        abbildung = Bildabbildung.aus_bild(image_path, props, verts_xz)

        bm = bmesh.new()
        bm.from_mesh(eval_mesh)
        bm.faces.ensure_lookup_table()
        bm.verts.ensure_lookup_table()

        try:
            if not Bildvorschau._flaechen_waehlen(bm, mat_w, abbildung, props):
                bm.free()
                logger.info("Kein Umriss im Bild getroffen — keine Vorschau")
                return None

            offset_weights = Bildvorschau._gewichte(bm, mat_w, verts_xz,
                                                    abbildung, props)

            # Garment hull: smooth → collision fix → straight hang
            Drapierung._apply_drape(bm, mat_w, props.drape, body_bvh)
        finally:
            eval_obj.to_mesh_clear()

        return Drapierung._finalize_preview(context, props, bm, body,
                                            offset_weights=offset_weights)

    # ------------------------------------------------------------ Bausteine

    @staticmethod
    def _koerperbaum(eval_mesh):
        u"""Ein BVH-Baum ueber den GANZEN Koerper — fuer die Kollision.

        Er entsteht vor dem Wegschneiden: Der Stoff muss auch an den
        Stellen ausweichen, die spaeter nicht mehr zum Kleidungsstueck
        gehoeren.
        """
        from mathutils.bvhtree import BVHTree

        bm_body = bmesh.new()
        bm_body.from_mesh(eval_mesh)
        baum = BVHTree.FromBMesh(bm_body)
        bm_body.free()
        return baum

    @staticmethod
    def _punkte_xz(eval_mesh, mat_w):
        u"""Alle Koerperpunkte in Weltkoordinaten, nur (x, z)."""
        n_verts = len(eval_mesh.vertices)
        verts_world = np.empty((n_verts, 3), dtype=np.float32)
        for i, v in enumerate(eval_mesh.vertices):
            co = mat_w @ v.co
            verts_world[i] = (co.x, co.y, co.z)
        return verts_world[:, [0, 2]]      # (N, 2) — x and z

    @staticmethod
    def _flaechen_waehlen(bm, mat_w, abbildung, props):
        u"""Alles wegschneiden, was der Bildumriss nicht bedeckt.

        True, wenn danach noch Flaechen uebrig sind.
        """
        # Face centers in world space → image UV
        n_faces = len(bm.faces)
        face_centers_xz = np.empty((n_faces, 2), dtype=np.float32)
        for i, face in enumerate(bm.faces):
            c = mat_w @ face.calc_center_median()
            face_centers_xz[i] = (c.x, c.z)

        covered = abbildung.bedeckt(face_centers_xz)

        # Select covered faces (with category filter)
        category = props.category
        for f in bm.faces:
            f.select = False
        for i, face in enumerate(bm.faces):
            if covered[i]:
                center = mat_w @ face.calc_center_median()
                if Flaechenwahl._face_allowed_for_category(center, category):
                    face.select = True

        Flaechenwahl._grow_selection(bm, props.grow)

        # Delete non-selected
        faces_to_delete = [f for f in bm.faces if not f.select]
        bmesh.ops.delete(bm, geom=faces_to_delete, context='FACES')
        return len(bm.faces) > 0

    @staticmethod
    def _gewichte(bm, mat_w, verts_xz, abbildung, props):
        u"""Wie weit jeder Punkt vom Koerper absteht — als Gruppengewicht.

        Der Umriss im Bild sagt je Hoehe, wie weit der Stoff aussteht.
        Das Gewicht steuert spaeter die Staerke des Displace-Modifikators
        (0..1 mal Hoechstwert), deshalb wird auf das Verhaeltnis
        `offset_min / offset_max` umgerechnet: Gewicht 0 ergibt den
        kleinsten Abstand, Gewicht 1 den groessten.
        """
        bm.verts.ensure_lookup_table()
        remaining_z = np.empty(len(bm.verts), dtype=np.float32)
        for i, v in enumerate(bm.verts):
            remaining_z[i] = (mat_w @ v.co).z

        z_values, profile_weights = abbildung.profil(verts_xz)
        per_vert_w = Bildanalyse.interpolate_vertex_weights(
            remaining_z, z_values, profile_weights)

        offset_min = props.image_offset_min
        offset_max = max(props.image_offset_max, 1e-6)
        min_ratio = offset_min / offset_max

        offset_weights = {}
        for i in range(len(bm.verts)):
            raw = float(per_vert_w[i])
            offset_weights[i] = min_ratio + raw * (1.0 - min_ratio)
        return offset_weights
