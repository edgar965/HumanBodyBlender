# SPDX-License-Identifier: GPL-3.0-or-later
#
# Preview mesh creation (Z-Range + Image modes) for the Asset Creator.

import logging

import bmesh

# Die Bauteile liegen in `vorschau/`. Hier bleibt, was Blender
# sieht: die Klassen und die Anmeldung.
from .vorschau.drapierung import Drapierung

# Die Bauteile liegen in `vorschau/`. Hier bleibt, was Blender
# sieht: die Klassen und die Anmeldung.
# DIE WEITERLEITUNG IST WEG (01.09.2026). `Vorschausuche`,
# `PREVIEW_TAG` und `create_preview_from_image` standen hier als
# oeffentliche Schnittstelle des Bereichs; alle Nutzer holen sie
# inzwischen bei ihrem Bauteil. Was hier steht, benutzt diese Datei
# auch selbst.
from .vorschau.vorschausuche import Vorschausuche
from .vorschau.flaechenwahl import Flaechenwahl


logger = logging.getLogger(__name__)

# Preview object tag


# ---------------------------------------------------------------------------
# Category-based body region filter
# ---------------------------------------------------------------------------
# For each category, define which face positions are ALLOWED.
# Faces outside these rules are excluded even if inside the Z-range.


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Z-Range mode
# ---------------------------------------------------------------------------


class Vorschau:
    u"""Die frueheren Modulfunktionen, gebuendelt."""

    @staticmethod
    def create_preview(context, props):
        """Create a preview mesh from the body using Z-range face selection."""
        from mathutils.bvhtree import BVHTree

        gefunden = Vorschausuche.koerpernetz(context)
        if not gefunden:
            return None
        body, eval_obj, eval_mesh = gefunden

        # Build BVH from full body mesh (local space) for collision checks
        bm_body = bmesh.new()
        bm_body.from_mesh(eval_mesh)
        body_bvh = BVHTree.FromBMesh(bm_body)
        bm_body.free()

        bm = bmesh.new()
        bm.from_mesh(eval_mesh)
        bm.faces.ensure_lookup_table()

        mat_w = body.matrix_world

        for f in bm.faces:
            f.select = False

        x_limit = 0.50 if props.include_arms else 0.20

        category = props.category

        for face in bm.faces:
            center = mat_w @ face.calc_center_median()
            if props.z_min <= center.z <= props.z_max:
                if abs(center.x) <= x_limit:
                    if Flaechenwahl._face_allowed_for_category(center, category):
                        face.select = True
                elif props.include_arms:
                    if Flaechenwahl._face_allowed_for_category(center, category):
                        face.select = True

        Flaechenwahl._grow_selection(bm, props.grow)

        faces_to_delete = [f for f in bm.faces if not f.select]
        bmesh.ops.delete(bm, geom=faces_to_delete, context='FACES')

        # Garment hull: smooth → collision fix → straight hang
        Drapierung._apply_drape(bm, mat_w, props.drape, body_bvh)

        eval_obj.to_mesh_clear()
        return Drapierung._finalize_preview(context, props, bm, body)




# ---------------------------------------------------------------------------
# Image mode
# ---------------------------------------------------------------------------
