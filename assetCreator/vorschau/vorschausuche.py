# -*- coding: utf-8 -*-
import logging
import bpy
#: Das Merkmal, an dem eine Vorschau erkannt wird. Es steht HIER und
#: nicht in `preview.py`: Von dort geholt entstuende ein Ring —
#: `preview` importiert dieses Modul.
PREVIEW_TAG = "hb_asset_preview"
logger = logging.getLogger(__name__)


def find_body_obj(context):
    """Find the HumanBody mesh object."""
    obj = context.active_object
    if obj and obj.type == 'MESH' and obj.data.get("humanbody"):
        return obj
    for o in context.scene.objects:
        if o.type == 'MESH' and o.data.get("humanbody"):
            return o
    return None


def find_preview(context):
    """Find the current preview object, if any."""
    for obj in context.scene.objects:
        if obj.type == 'MESH' and obj.data.get(PREVIEW_TAG):
            return obj
    return None


def remove_preview(context):
    """Remove existing preview object."""
    preview = find_preview(context)
    if preview:
        bpy.data.objects.remove(preview, do_unlink=True)


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
