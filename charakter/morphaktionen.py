# -*- coding: utf-8 -*-
u"""Morphaktionen — aus `charakterdatei` herausgeloest."""
# -*- coding: utf-8 -*-
import logging
from ..morphing import Morpher, char_defaults, morph_data, MorphData
from ..properties import HumanBodyProperties
logger = logging.getLogger(__name__)


class Morphaktionen:
    u"""Aus `HumanBodyIO` herausgeloest, Rumpf unveraendert."""

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
