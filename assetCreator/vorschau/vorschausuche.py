# -*- coding: utf-8 -*-
import logging
import bpy
#: Das Merkmal, an dem eine Vorschau erkannt wird. Es steht HIER und
#: nicht in `preview.py`: Von dort geholt entstuende ein Ring —
#: `preview` importiert dieses Modul.
PREVIEW_TAG = "hb_asset_preview"
logger = logging.getLogger(__name__)


class Vorschausuche:
    u"""Die frueheren Modulfunktionen, gebuendelt."""

    @staticmethod
    def find_body_obj(context):
        """Find the HumanBody mesh object."""
        obj = context.active_object
        if obj and obj.type == 'MESH' and obj.data.get("humanbody"):
            return obj
        for o in context.scene.objects:
            if o.type == 'MESH' and o.data.get("humanbody"):
                return o
        return None

    @staticmethod
    def find_preview(context):
        """Find the current preview object, if any."""
        for obj in context.scene.objects:
            if obj.type == 'MESH' and obj.data.get(PREVIEW_TAG):
                return obj
        return None

    @staticmethod
    def remove_preview(context):
        """Remove existing preview object."""
        preview = Vorschausuche.find_preview(context)
        if preview:
            bpy.data.objects.remove(preview, do_unlink=True)

    @staticmethod
    def koerpernetz(context):
        u"""(Koerper, ausgewertetes Objekt, Netz) — oder None ohne Koerper.

        Die sieben Zeilen davor standen bis zum 01.09.2026 zweimal:
        in `Vorschaubau.create_preview` und in
        `Bildvorschau.create_preview_from_image`. Beide raeumen zuerst
        eine alte Vorschau weg — sonst haengt die neue neben der alten
        in der Szene.

        AUSGEWERTET, NICHT ROH: `evaluated_get` liefert das Netz NACH
        allen Modifikatoren. Auf dem Rohnetz laege die Vorschau auf der
        unglaetteten Grundform und schnitte durch den sichtbaren
        Koerper.
        """
        koerper = Vorschausuche.find_body_obj(context)
        if not koerper:
            return None
        Vorschausuche.remove_preview(context)
        graph = context.evaluated_depsgraph_get()
        ausgewertet = koerper.evaluated_get(graph)
        return koerper, ausgewertet, ausgewertet.to_mesh()

    @staticmethod
    def _create_material(props):
        """Create a simple Principled BSDF material from props."""
        mat = bpy.data.materials.new(name=f"hb_preview_{props.name_}")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs['Base Color'].default_value = (*props.color, 1.0)
            bsdf.inputs['Roughness'].default_value = props.roughness
            bsdf.inputs['Metallic'].default_value = props.metallic
        mat.diffuse_color = (*props.color, 1.0)
        return mat


#: Die frueheren Modulnamen — die Importpfade von
#: aussen bleiben damit unveraendert.
find_body_obj = Vorschausuche.find_body_obj
find_preview = Vorschausuche.find_preview
remove_preview = Vorschausuche.remove_preview
_create_material = Vorschausuche._create_material
