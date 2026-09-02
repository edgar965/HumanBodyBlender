# -*- coding: utf-8 -*-
import logging
logger = logging.getLogger(__name__)


class Flaechenwahl:
    u"""Die frueheren Modulfunktionen, gebuendelt."""

    @staticmethod
    def _face_allowed_for_category(center, category):
        """Return True if a face at *center* (world space) belongs to *category*.

        Rules filter out body parts that don't belong to the garment type.
        Rest-pose reference:
            Head/face  z > 1.42
            Arms       z 0.85–1.22, |x| 0.20–0.50
            Hands      z 0.40–0.60, |x| > 0.25
            Feet       z < 0.05
        """
        x, z = center.x, center.z

        if category == "Tops":
            if z > 1.42:                            # head / face
                return False
            if abs(x) > 0.25 and z < 0.60:         # hands only
                return False
            return True

        if category == "Bottoms":
            if abs(x) > 0.18 and z > 0.75:         # arms / shoulders
                return False
            return True

        if category == "Full":
            if z > 1.42:                            # head
                return False
            if abs(x) > 0.25 and z < 0.60:         # hands only
                return False
            return True

        if category == "Underwear":
            if abs(x) > 0.16:                      # only pelvis width
                return False
            return True

        if category == "Shoes":
            if abs(x) > 0.12:                      # feet are narrow
                return False
            return True

        # Accessories — no filtering
        return True

    @staticmethod
    def _grow_selection(bm, iterations):
        """Grow face selection by N iterations."""
        for _ in range(iterations):
            new_select = set()
            for face in bm.faces:
                if face.select:
                    for edge in face.edges:
                        for linked_face in edge.link_faces:
                            if not linked_face.select:
                                new_select.add(linked_face)
            for f in new_select:
                f.select = True


#: Die frueheren Modulnamen — die Importpfade von
#: aussen bleiben damit unveraendert.
_face_allowed_for_category = Flaechenwahl._face_allowed_for_category
_grow_selection = Flaechenwahl._grow_selection
