# SPDX-License-Identifier: GPL-3.0-or-later
#
# Preview mesh creation (Z-Range + Image modes) for the Asset Creator.

import logging

import bmesh

# Die Bauteile liegen in `vorschau/`. Hier bleibt, was Blender
# sieht: die Klassen und die Anmeldung.
from .vorschau.drapierung import _apply_drape, _finalize_preview
from .vorschau.flaechenwahl import _face_allowed_for_category, _grow_selection

# Die Bauteile liegen in `vorschau/`. Hier bleibt, was Blender
# sieht: die Klassen und die Anmeldung.
# DIE OEFFENTLICHE SCHNITTSTELLE DES BEREICHS: `cloth/`,
# `assetCreator/operators.py` und `geometric.py` holen diese Namen
# aus `preview`. Sie sehen unbenutzt aus und sind die Weiterleitung.
from .vorschau.vorschausuche import (  # noqa: F401
    PREVIEW_TAG, find_body_obj, find_preview, remove_preview,
    _create_material,
)
from .vorschau.flaechenwahl import (  # noqa: F401
    _face_allowed_for_category, _grow_selection,
)
from .vorschau.bildvorschau import create_preview_from_image  # noqa: F401


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

def create_preview(context, props):
    """Create a preview mesh from the body using Z-range face selection."""
    from mathutils.bvhtree import BVHTree

    body = find_body_obj(context)
    if not body:
        return None

    remove_preview(context)

    depsgraph = context.evaluated_depsgraph_get()
    eval_obj = body.evaluated_get(depsgraph)
    eval_mesh = eval_obj.to_mesh()

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
                if _face_allowed_for_category(center, category):
                    face.select = True
            elif props.include_arms:
                if _face_allowed_for_category(center, category):
                    face.select = True

    _grow_selection(bm, props.grow)

    faces_to_delete = [f for f in bm.faces if not f.select]
    bmesh.ops.delete(bm, geom=faces_to_delete, context='FACES')

    # Garment hull: smooth → collision fix → straight hang
    _apply_drape(bm, mat_w, props.drape, body_bvh)

    eval_obj.to_mesh_clear()
    return _finalize_preview(context, props, bm, body)


# ---------------------------------------------------------------------------
# Image mode
# ---------------------------------------------------------------------------

