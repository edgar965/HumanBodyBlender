# -*- coding: utf-8 -*-
import os
import logging
import bpy
from ..morphing import Morpher, char_defaults, morph_data, MorphData
from ..properties import HumanBodyProperties
from ..haare.haarfarben import EYE_COLORS
from .koerpermaterial import Koerpermaterial
logger = logging.getLogger(__name__)


class HumanBodyIO:
    """All character I/O and morph operations as static methods.

    Operator classes below are thin wrappers that call these methods
    and translate the return values into Blender reports.
    """

    @staticmethod
    def import_character(context):
        """Import the HumanBody base mesh.

        Returns (obj, error_message).  *obj* is None on failure.
        """
        if not morph_data.loaded:
            morph_data.load()

        char_blend = os.path.join(MorphData._addon_data_dir(), "char.blend")
        if not os.path.isfile(char_blend):
            return None, f"char.blend not found: {char_blend}"

        # Remove default cube
        for o in list(context.collection.objects):
            if o.type == 'MESH' and o.name.startswith("Cube"):
                bpy.data.objects.remove(o, do_unlink=True)

        # Append mesh from char.blend
        with bpy.data.libraries.load(char_blend, link=False) as (data_from, data_to):
            if not data_from.objects:
                return None, "No objects in char.blend"
            data_to.objects = data_from.objects[:]

        obj = None
        for o in data_to.objects:
            if o is not None:
                context.collection.objects.link(o)
                if o.type == 'MESH':
                    obj = o

        if obj is None:
            return None, "No mesh object found in char.blend"

        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        context.view_layer.objects.active = obj
        obj.data["humanbody"] = True

        # Materials + morphing init
        props = context.scene.humanbody
        skin_rgb = MorphData._get_skin_color(props.body_type)
        eye_rgb = EYE_COLORS.get(props.eye_color, (0.08, 0.20, 0.65))
        Koerpermaterial.create_body_materials(obj, skin_rgb, eye_rgb)

        m = Morpher.get(obj)
        m.set_body_type(props.body_type)
        HumanBodyProperties._sync_meta_to_obj(props, obj)
        m.apply_meta_morphs()
        m.update()

        # Smooth shading
        for poly in obj.data.polygons:
            poly.use_smooth = True

        # Subdivision Surface
        mod = obj.modifiers.new(name="Subdivision", type='SUBSURF')
        mod.levels = 1
        mod.render_levels = 2

        return obj, ""






    @staticmethod
    def export_character(context, filepath):
        """Export character settings to JSON. Returns (bool, msg)."""
        import json
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            return False, "No mesh selected"
        m = Morpher.get(obj)
        props = context.scene.humanbody

        data = {
            "body_type": m.body_type,
            "meta_age": props.meta_age,
            "meta_mass": props.meta_mass,
            "meta_tone": props.meta_tone,
            "meta_height": props.meta_height,
            "l2_morphs": {},
        }

        lm = char_defaults.l2_mass
        for morph in m.l2_morphs:
            key = "hb_L2_" + morph.name
            val = obj.data.get(key, 0.0)
            if Morpher._is_mass_morph(morph.name):
                if val != lm.default:
                    data["l2_morphs"][morph.name] = val
            else:
                if abs(val) > 0.001:
                    data["l2_morphs"][morph.name] = round(val, 4)

        path = filepath
        if not path.endswith(".json"):
            path += ".json"

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        return True, path

    @staticmethod
    def import_settings(context, filepath):
        """Import character settings from JSON. Returns (bool, msg)."""
        import json
        obj = context.active_object
        if not obj or obj.type != 'MESH' or not obj.data.get("humanbody"):
            return False, "Select a HumanBody character first"

        if not os.path.isfile(filepath):
            return False, f"File not found: {filepath}"

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        props = context.scene.humanbody
        m = Morpher.get(obj)

        if "body_type" in data:
            props.body_type = data["body_type"]
            m.set_body_type(data["body_type"])
        if "meta_age" in data:
            props.meta_age = data["meta_age"]
        if "meta_mass" in data:
            props.meta_mass = data["meta_mass"]
        if "meta_tone" in data:
            props.meta_tone = data["meta_tone"]
        if "meta_height" in data:
            props.meta_height = data["meta_height"]

        HumanBodyProperties._sync_meta_to_obj(props, obj)
        m.apply_meta_morphs()

        for morph_name, val in data.get("l2_morphs", {}).items():
            obj.data["hb_L2_" + morph_name] = val

        m.update()
        return True, filepath
