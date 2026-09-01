# -*- coding: utf-8 -*-
import os
import logging
import bpy
from ..morphing import Morpher, char_defaults, morph_data, MorphData, _nail_color
from ..properties import HumanBodyProperties
from ..haare.haarfarben import EYE_COLORS
logger = logging.getLogger(__name__)
from .materialien import _make_bsdf_mat


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
        HumanBodyIO.create_body_materials(obj, skin_rgb, eye_rgb)

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
    def create_body_materials(obj, skin_rgb, eye_rgb):
        """Create all body materials matching char.blend face assignments.

        Slots: 0=Skin, 1=Censor/Areola, 2=Eyelash, 3=Pupil, 4=Sclera,
               5=Cornea, 6=Iris, 7=Tongue, 8=Teeth, 9=Nails_Hand, 10=Nails_Feet
        """
        nr = _nail_color(skin_rgb)

        # Cornea (transparent)
        cornea = bpy.data.materials.new("HB_Cornea")
        cornea.use_nodes = True
        tree = cornea.node_tree
        tree.nodes.clear()
        trans = tree.nodes.new('ShaderNodeBsdfTransparent')
        trans.location = (0, 0)
        out = tree.nodes.new('ShaderNodeOutputMaterial')
        out.location = (300, 0)
        tree.links.new(trans.outputs[0], out.inputs[0])
        cornea.diffuse_color = (1.0, 1.0, 1.0, 0.0)
        try:
            cornea.surface_render_method = 'DITHERED'
        # stumm gewollt: Das Feld gibt es erst ab Blender 4.2. Fehlt es,
        # bleibt die Vorgabe stehen — gewollt.
        except (AttributeError, TypeError):
            pass

        slot_mats = [
            _make_bsdf_mat("HB_Skin", skin_rgb, sss=0.3),
            _make_bsdf_mat("HB_Censor", skin_rgb, sss=0.3),
            _make_bsdf_mat("HB_Eyelash", (0.015, 0.015, 0.015)),
            _make_bsdf_mat("HB_Pupil", (0.005, 0.005, 0.005),
                           roughness=0.0),
            _make_bsdf_mat("HB_Sclera", (0.9, 0.88, 0.87), roughness=0.3),
            cornea,
            _make_bsdf_mat("HB_Iris", eye_rgb, roughness=0.3),
            _make_bsdf_mat("HB_Tongue", (0.4, 0.1, 0.08),
                           roughness=0.6, sss=0.2),
            _make_bsdf_mat("HB_Teeth", (0.85, 0.82, 0.76), roughness=0.3),
            _make_bsdf_mat("HB_Nails_Hand", nr, roughness=0.3),
            _make_bsdf_mat("HB_Nails_Feet", nr, roughness=0.3),
        ]

        mats = obj.data.materials
        for i, new_mat in enumerate(slot_mats):
            if i < len(mats):
                mats[i] = new_mat
            else:
                mats.append(new_mat)

        # Split nails: slot 9 = hand, slot 10 = feet
        for poly in obj.data.polygons:
            if poly.material_index == 9:
                cz = sum(obj.data.vertices[vi].co.z
                         for vi in poly.vertices) / len(poly.vertices)
                if cz < 0.5:
                    poly.material_index = 10

    @staticmethod
    def update_morphs(context):
        """Force-update the mesh from current morph values. Returns bool."""
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            return False
        m = Morpher.get(obj)
        props = context.scene.humanbody
        m.set_body_type(props.body_type)
        HumanBodyProperties._sync_meta_to_obj(props, obj)
        m.apply_meta_morphs()
        m.update()
        return True

    @staticmethod
    def reset_morphs(context):
        """Reset all morph sliders to zero. Returns bool."""
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            return False
        m = Morpher.get(obj)
        lm = char_defaults.l2_mass
        for morph in m.l2_morphs:
            if Morpher._is_mass_morph(morph.name):
                obj.data["hb_L2_" + morph.name] = lm.default
            else:
                obj.data["hb_L2_" + morph.name] = 0.0
        props = context.scene.humanbody
        props.meta_age = char_defaults.age.default
        props.meta_mass = char_defaults.mass.default
        props.meta_tone = char_defaults.tone.default
        props.meta_height = char_defaults.height.default
        HumanBodyProperties._sync_meta_to_obj(props, obj)
        m.update()
        return True

    @staticmethod
    def randomize(context):
        """Randomize morph values. Returns (count, error_msg)."""
        import random
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            return 0, "No mesh selected"
        m = Morpher.get(obj)
        if not m.l2_morphs:
            return 0, "No morphs loaded"

        props = context.scene.humanbody
        strength = props.randomize_strength
        count = 0

        for morph in m.l2_morphs:
            key = "hb_L2_" + morph.name
            if Morpher._is_mass_morph(morph.name):
                lm = char_defaults.l2_mass
                center = lm.default
                spread = (lm.max - lm.min) * 0.25 * strength
                val = random.gauss(center, spread)
                obj.data[key] = int(max(lm.min, min(lm.max, val)))
            else:
                spread = 0.5 * strength
                val = random.gauss(0.0, spread)
                obj.data[key] = max(-1.0, min(1.0, val))
            count += 1

        m.update()
        return count, ""

    @staticmethod
    def finalize(context):
        """Bake current morph state into mesh. Returns (bool, msg)."""
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            return False, "No mesh selected"
        m = Morpher.get(obj)
        if m.basis is None:
            return False, "No morph data loaded"

        m.update()
        new_basis = m.morphed.copy()
        m.basis = new_basis

        lm = char_defaults.l2_mass
        for morph in m.l2_morphs:
            key = "hb_L2_" + morph.name
            if Morpher._is_mass_morph(morph.name):
                obj.data[key] = lm.default
            else:
                obj.data[key] = 0.0

        obj.data["hb_meta_age"] = 0.0
        obj.data["hb_meta_mass"] = 0.0
        obj.data["hb_meta_tone"] = 0.0
        obj.data["hb_meta_height"] = 0.0

        props = context.scene.humanbody
        props.meta_age = char_defaults.age.default
        props.meta_mass = char_defaults.mass.default
        props.meta_tone = char_defaults.tone.default
        props.meta_height = char_defaults.height.default

        morph_data.l1[m.body_type] = MorphData.np_ro64(new_basis)
        m.update()
        return True, ""

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
