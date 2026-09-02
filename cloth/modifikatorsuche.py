# -*- coding: utf-8 -*-
import logging
import bpy
logger = logging.getLogger(__name__)


class Modifikatorsuche:
    u"""Die frueheren Modulfunktionen, gebuendelt."""

    @staticmethod
    def _get_modifiers(mod_type, objects=None):
        """Return list of modifiers of a given type from objects."""
        result = []
        if objects is None:
            objects = bpy.context.selected_objects
        for obj in objects:
            if not hasattr(obj, 'modifiers'):
                continue
            for mod in obj.modifiers:
                if mod.type == mod_type:
                    result.append(mod)
        return result

    @staticmethod
    def _has_modifier(obj, mod_type):
        """Check if object has a modifier of given type."""
        if not hasattr(obj, 'modifiers'):
            return False
        for mod in obj.modifiers:
            if mod.type == mod_type:
                return True
        return False
