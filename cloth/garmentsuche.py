# -*- coding: utf-8 -*-
import logging
from ..assetCreator.preview import find_body_obj
logger = logging.getLogger(__name__)
from .modifikatorsuche import _has_modifier


def _find_garment(context):
    """Find a garment (non-HumanBody mesh) — active object first, then
    selected objects, then children of the HumanBody, then any scene mesh."""
    obj = context.active_object
    if obj and obj.type == 'MESH' and not obj.data.get("humanbody"):
        return obj
    for o in context.selected_objects:
        if o.type == 'MESH' and not o.data.get("humanbody"):
            return o
    # Fallback: check children of HumanBody
    body = find_body_obj(context)
    if body:
        for child in body.children:
            if child.type == 'MESH' and not child.data.get("humanbody"):
                return child
    # Last resort: any non-HumanBody mesh in scene
    for o in context.scene.objects:
        if o.type == 'MESH' and not o.data.get("humanbody"):
            return o
    return None


def _poll_garment(context):
    """A non-HumanBody mesh is active or selected."""
    return _find_garment(context) is not None


def _poll_garment_and_body(context):
    """A garment is available AND a HumanBody exists."""
    if not _poll_garment(context):
        return False
    return find_body_obj(context) is not None


def _poll_garment_has_cloth(context):
    """A garment with cloth modifier is available."""
    g = _find_garment(context)
    if not g:
        return False
    return _has_modifier(g, 'CLOTH')
