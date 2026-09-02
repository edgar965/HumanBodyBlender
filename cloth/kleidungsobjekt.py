# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Aus dem fertigen Netz wird ein Blender-Objekt.

AUS `_create_garment` HERAUSGELOEST (01.09.2026)
================================================
Der zweite Teil der frueheren 133-Zeilen-Funktion: alles ab `bm.to_mesh`.
Hier haengt jeder Schritt an `bpy.data` — Netz, Objekt, Merkmale,
Modifikator, Elternschaft, Material. Kein `bmesh` mehr.

Die Trennung ist nicht nur Laenge: `kleidungsnetz.py` laesst sich ohne
Szene denken, dieses Modul nicht. Wer die Stoffdicke oder die Farbe
aendert, sucht hier und nirgends sonst.
"""
import logging

import bpy

from .kleidungsregionen import Kleidungsregionen
from .netzbau import Netzbau
from .namen import CLOTH_GARMENT_TAG

logger = logging.getLogger(__name__)


class Kleidungsobjekt:
    u"""Netz, Merkmale, Modifikator und Material eines Kleidungsstuecks."""

    @staticmethod
    def bauen(context, body, region_key, bm, pin_indices, looseness, offset):
        u"""Das fertige Objekt — verankert am Koerper, mit Stoffmaterial.

        `bm` wird dabei geleert (`bm.free()`); der Aufrufer darf es
        danach nicht mehr anfassen.
        """
        label = Kleidungsregionen.beschriftung(region_key)
        mesh = bpy.data.meshes.new(f"hb_cloth_{label}")
        bm.to_mesh(mesh)
        bm.free()

        obj = bpy.data.objects.new(f"Cloth_{label}", mesh)
        context.collection.objects.link(obj)

        # Tag as cloth garment
        obj.data[CLOTH_GARMENT_TAG] = region_key
        obj.data['hb_pin_indices'] = pin_indices  # Store for _add_cloth

        # Copy transforms, smooth shading
        obj.matrix_world = body.matrix_world.copy()
        # Je lockerer das Stueck sitzt, desto dicker der Stoff.
        Netzbau.stoffhuelle(obj, body,
                            0.002 + min(looseness, 1.0) * 0.002)

        Kleidungsobjekt._material(obj, label)

        logger.info("Created cloth garment '%s' (%d faces, offset=%.3f, looseness=%.2f)",
                    label, len(mesh.polygons), offset, looseness)
        return obj

    @staticmethod
    def _material(obj, label):
        u"""Ein graublaues Stoffmaterial, matt und wenig spiegelnd."""
        mat = bpy.data.materials.new(name=f"hb_cloth_{label}")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs['Base Color'].default_value = (0.25, 0.30, 0.45, 1.0)
            bsdf.inputs['Roughness'].default_value = 0.8
            bsdf.inputs['Specular IOR Level'].default_value = 0.2
        mat.diffuse_color = (0.7, 0.7, 0.75, 1.0)
        obj.data.materials.append(mat)
        return mat
