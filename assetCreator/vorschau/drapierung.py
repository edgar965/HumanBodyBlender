# -*- coding: utf-8 -*-
u"""Aus einer Koerperflaeche wird eine Stoffhuelle.

AUFGETEILT (01.09.2026)
=======================
`_apply_drape` (66 Zeilen) hatte seine drei Schritte als `── Step N ──`
markiert; sie sind jetzt drei Methoden. `_finalize_preview` (85 Zeilen)
hat seine vier Modifikatoren an `vorschaumodifikatoren.py` abgegeben.
"""
import logging
import bpy
import bmesh
logger = logging.getLogger(__name__)
from .vorschausuche import Vorschausuche, PREVIEW_TAG
from .vorschaumodifikatoren import Vorschaumodifikatoren

#: Wie weit ein Punkt mindestens vom Koerper wegbleibt, in Metern.
MINDESTABSTAND = 0.003


class Drapierung:
    u"""Die Stoffhuelle und das fertige Vorschauobjekt."""

    @staticmethod
    def _apply_drape(bm, mat_w, drape_strength, body_bvh):
        """Create a smooth garment hull outside the body.

        1. **Offset** all vertices along normals — lifts the shell off the body
           so that subsequent smoothing does not push vertices INTO the body.
        2. **Laplacian smoothing** — removes body detail (breasts, belly button).
           Boundary edges (hem, neckline, sleeves) are pinned.
        3. **Collision fix** — any vertex that ended up inside the body despite
           the pre-offset is pushed back to body surface + gap.
        """
        if drape_strength < 0.01:
            return

        bm.verts.ensure_lookup_table()
        n = len(bm.verts)
        if n < 4:
            return

        pre_offset = Drapierung._vorversatz(bm, drape_strength)
        Drapierung._glaetten(bm, drape_strength, n, pre_offset)
        Drapierung._kollision_beheben(bm, body_bvh)

    # ------------------------------------------------------ Die drei Schritte

    @staticmethod
    def _vorversatz(bm, drape_strength):
        u"""Die Huelle vom Koerper abheben — bevor geglaettet wird.

        Ohne diesen Schritt zieht die Glaettung die Flaeche IN den Koerper
        hinein: Sie mittelt ueber die Nachbarn, und an einer gewoelbten
        Stelle liegt der Mittelwert innerhalb der Woelbung.

        drape 0.5 → 8 mm, drape 1.0 → 15 mm.
        """
        pre_offset = drape_strength * 0.015
        bm.normal_update()
        for v in bm.verts:
            v.co = v.co + v.normal * pre_offset
        return pre_offset

    @staticmethod
    def _glaetten(bm, drape_strength, n, pre_offset):
        u"""Koerperdetails wegmitteln, Raender festhalten.

        Geglaettet wird nur in x und y (`use_axis_z=False`): Der Stoff
        soll die Woelbungen verlieren, aber nicht in der Hoehe wandern —
        sonst rutscht ein Saum nach oben.

        drape 0→0, 0.5→50, 1.0→100 Durchgaenge.
        """
        smooth_iters = int(drape_strength * 100)

        # Pin boundary edges (hem, neckline, sleeve openings stay in place)
        boundary_verts = set()
        for edge in bm.edges:
            if edge.is_boundary:
                boundary_verts.add(edge.verts[0])
                boundary_verts.add(edge.verts[1])

        interior_verts = [v for v in bm.verts if v not in boundary_verts]

        logger.info("Drape: %d interior / %d boundary / %d total verts, "
                    "%d smooth iters, pre-offset=%.3f",
                    len(interior_verts), len(boundary_verts), n,
                    smooth_iters, pre_offset)

        if interior_verts and smooth_iters > 0:
            for _ in range(smooth_iters):
                bmesh.ops.smooth_vert(bm, verts=interior_verts, factor=0.5,
                                      use_axis_x=True, use_axis_y=True,
                                      use_axis_z=False)

    @staticmethod
    def _kollision_beheben(bm, body_bvh):
        u"""Das Sicherungsnetz: Punkte im Koerper nach aussen setzen.

        Nach Versatz und Glaettung liegen die meisten Punkte aussen. Wer
        drinsteckt, wird auf die Koerperoberflaeche plus Mindestabstand
        gesetzt. Erkannt wird das am Vorzeichen: Zeigt die Verbindung vom
        naechsten Oberflaechenpunkt zum Netzpunkt GEGEN die Normale,
        liegt der Punkt innen.
        """
        bm.verts.ensure_lookup_table()
        pushed = 0
        for v in bm.verts:
            loc, normal, _idx, _dist = body_bvh.find_nearest(v.co)
            if loc is None:
                continue
            direction = v.co - loc
            if direction.dot(normal) <= 0:      # inside the body
                v.co = loc + normal * MINDESTABSTAND
                pushed += 1

        logger.info("Drape done: %d verts pushed back (collision fix)", pushed)

    # ---------------------------------------------------- Das Vorschauobjekt

    @staticmethod
    def _finalize_preview(context, props, bm, body, offset_weights=None):
        """Create object from BMesh, add modifiers, parent to body.

        Parameters
        ----------
        offset_weights : dict[int, float] or None
            If given, per-vertex weights for the ``hb_offset_weight`` vertex
            group used by the Displace modifier.  Keys are BMesh vertex indices.
        """
        if len(bm.faces) == 0:
            bm.free()
            return None

        mesh = bpy.data.meshes.new(f"hb_preview_{props.name_}")
        bm.to_mesh(mesh)
        bm.free()

        obj = bpy.data.objects.new(f"Preview_{props.name_}", mesh)
        context.collection.objects.link(obj)

        # Tag as preview
        obj.data[PREVIEW_TAG] = True

        # Copy transforms from body
        obj.matrix_world = body.matrix_world.copy()

        # Material
        obj.data.materials.append(Vorschausuche._create_material(props))

        # Smooth shading
        for poly in obj.data.polygons:
            poly.use_smooth = True

        Vorschaumodifikatoren.gewichtsgruppe(obj, mesh, offset_weights)
        Vorschaumodifikatoren.alle_haengen(obj, props, offset_weights)

        # Parent to body
        obj.parent = body
        obj.matrix_parent_inverse = body.matrix_world.inverted()

        logger.info("Created asset preview: %s (%d faces)", props.name_,
                    len(mesh.polygons))
        return obj
