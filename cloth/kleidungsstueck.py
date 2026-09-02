# -*- coding: utf-8 -*-
u"""Ein Kleidungsstueck aus einer Koerperregion — der Ablauf.

AUFGETEILT (01.09.2026)
=======================
`_create_garment` war 133 Zeilen und lief in vier Abschnitten ab. Die
stehen jetzt in eigenen Bauteilen; hier bleibt die Reihenfolge, in der
sie aufgerufen werden — und die ist die eigentliche Aussage:

    Regionsvorgaben  ->  Netz vom Koerper  ->  waehlen
                     ->  aufblasen  ->  naehpunkte  ->  Objekt

    kleidungsregionen.py  Z-Bereich, Arme, Kategorie je Region
    kleidungsnetz.py      waehlen / aufblasen / naehpunkte  (bmesh)
    kleidungsobjekt.py    Netz, Merkmale, Modifikator, Material  (bpy)

Die Rumpfe sind unveraendert; nur der Ausstieg „keine Flaeche uebrig"
liest sich anders, weil das Aufraeumen jetzt an einer Stelle steht.
"""
import logging

import bmesh

from .kleidungsnetz import Kleidungsnetz
from .kleidungsobjekt import Kleidungsobjekt
from .kleidungsregionen import Kleidungsregionen

logger = logging.getLogger(__name__)


class Kleidungsstueck:
    u"""Der Ablauf vom Koerpernetz zum fertigen Kleidungsstueck."""

    @staticmethod
    def _create_garment(context, body, region_key):
        """Create a garment mesh from a body region.

        Simple approach: duplicate body faces, offset along normals, solidify.
        The body mesh topology already wraps each leg/arm correctly — no
        cylindrical math needed.  Looseness comes from the cloth simulation
        (shrink / pressure), not from geometry deformation.
        """
        preset = Kleidungsregionen.VORGABEN[region_key]

        depsgraph = context.evaluated_depsgraph_get()
        eval_obj = body.evaluated_get(depsgraph)
        eval_mesh = eval_obj.to_mesh()
        mat_w = body.matrix_world

        bm = bmesh.new()
        bm.from_mesh(eval_mesh)
        bm.faces.ensure_lookup_table()

        try:
            if not Kleidungsnetz.waehlen(bm, mat_w, preset):
                bm.free()
                logger.info("Keine Flaeche in Region '%s' — kein Kleidungsstueck",
                            region_key)
                return None

            looseness = context.scene.humanbody_cloth_builder.looseness
            offset = Kleidungsnetz.aufblasen(bm, looseness)
            pin_indices = Kleidungsnetz.naehpunkte(bm, mat_w)
        finally:
            eval_obj.to_mesh_clear()

        return Kleidungsobjekt.bauen(context, body, region_key, bm,
                                     pin_indices, looseness, offset)
