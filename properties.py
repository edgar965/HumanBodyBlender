# SPDX-License-Identifier: GPL-3.0-or-later
#
# HumanBody scene properties (PropertyGroup for the N-panel UI).

import bpy

from .morphing import Morpher, char_defaults, morph_data, MorphData
from .hair import EYE_COLORS, HAIR_COLORS


class HumanBodyProperties(bpy.types.PropertyGroup):

    @staticmethod
    def _enum_items_body_types(self, context):
        """EnumProperty items callback for body types."""
        return [(t, t, "") for t in MorphData.BODY_TYPES]

    @staticmethod
    def _update_body_type(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            return
        m = Morpher.get(obj)
        m.set_body_type(self.body_type)
        m.set_gender(char_defaults.gender.to_internal(self.gender) / 2.0 + 0.5)
        m.update()

    @staticmethod
    def _update_gender(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            return
        m = Morpher.get(obj)
        m.set_gender(char_defaults.gender.to_internal(self.gender) / 2.0 + 0.5)
        m.update()

    @staticmethod
    def _update_eye_color(self, context):
        """Called when eye color changes — update iris material (slot 6)."""
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            return
        mats = obj.data.materials
        if len(mats) <= 6 or not mats[6] or not mats[6].node_tree:
            return
        rgb = EYE_COLORS.get(self.eye_color, (0.08, 0.20, 0.65))
        mats[6].diffuse_color = (*rgb, 1.0)
        for node in mats[6].node_tree.nodes:
            if node.type == 'BSDF_PRINCIPLED':
                node.inputs['Base Color'].default_value = (*rgb, 1.0)

    @staticmethod
    def _update_meta(self, context):
        """Called when any meta slider (age/mass/tone) changes."""
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            return
        HumanBodyProperties._sync_meta_to_obj(self, obj)
        m = Morpher.get(obj)
        m.apply_meta_morphs()
        m.update()

    @staticmethod
    def _sync_meta_to_obj(props, obj):
        """Write meta slider values to mesh custom props so Morpher can read them."""
        obj.data["hb_meta_age"] = char_defaults.age.to_internal(props.meta_age)
        obj.data["hb_meta_mass"] = char_defaults.mass.to_internal(props.meta_mass)
        obj.data["hb_meta_tone"] = char_defaults.tone.to_internal(props.meta_tone)
        obj.data["hb_meta_height"] = char_defaults.height.to_internal(props.meta_height)

    body_type: bpy.props.EnumProperty(
        name="Body Type",
        items=_enum_items_body_types.__func__,
        update=_update_body_type.__func__,
    )
    gender: bpy.props.IntProperty(
        name="Gender",
        description="0 = Female, 100 = Male",
        default=char_defaults.gender.default,
        min=char_defaults.gender.min,
        max=char_defaults.gender.max,
        update=_update_gender.__func__,
    )
    # Meta morphs
    meta_age: bpy.props.IntProperty(
        name="Age",
        description="Character age in years",
        default=char_defaults.age.default,
        min=char_defaults.age.min,
        max=char_defaults.age.max,
        update=_update_meta.__func__,
    )
    meta_mass: bpy.props.IntProperty(
        name="Mass",
        description="Body mass in kg",
        default=char_defaults.mass.default,
        min=char_defaults.mass.min,
        max=char_defaults.mass.max,
        update=_update_meta.__func__,
    )
    meta_tone: bpy.props.IntProperty(
        name="Tone",
        description="Muscle tone",
        default=char_defaults.tone.default,
        min=char_defaults.tone.min,
        max=char_defaults.tone.max,
        update=_update_meta.__func__,
    )
    meta_height: bpy.props.IntProperty(
        name="Height",
        description="Character height in cm",
        default=char_defaults.height.default,
        min=char_defaults.height.min,
        max=char_defaults.height.max,
        update=_update_meta.__func__,
    )
    # UI state
    filter_text: bpy.props.StringProperty(
        name="Filter",
        description="Search morph names",
        default="",
        options={'TEXTEDIT_UPDATE'},
    )
    category_filter: bpy.props.EnumProperty(
        name="Category",
        items=lambda self, ctx: [("ALL", "All", "")] + [(c, c, "") for c in morph_data.categories],
    )
    eye_color: bpy.props.EnumProperty(
        name="Eye Color",
        items=lambda self, ctx: [(k, k, "") for k in EYE_COLORS.keys()],
        update=_update_eye_color.__func__,
    )
    show_sub_items: bpy.props.BoolProperty(
        name="Show Sub Items",
        default=True,
    )
    parts_selected: bpy.props.StringProperty(
        name="Selected Part",
        description="Currently selected body part category",
        default="",
    )
    # Wardrobe UI state
    wardrobe_category: bpy.props.EnumProperty(
        name="Wardrobe Category",
        items=[
            ("ALL", "All", ""),
            ("Tops", "Tops", ""),
            ("Bottoms", "Bottoms", ""),
            ("Dresses", "Dresses", ""),
            ("Shoes", "Shoes", ""),
            ("Accessories", "Accessories", ""),
            ("Hair", "Hair", ""),
            ("Other", "Other", ""),
        ],
    )
    wardrobe_selected: bpy.props.StringProperty(
        name="Selected Wardrobe Category",
        default="",
    )
    anim_selected: bpy.props.StringProperty(
        name="Selected Animation Category",
        default="",
    )
    wardrobe_search: bpy.props.StringProperty(
        name="Search",
        description="Search wardrobe assets",
        default="",
        options={'TEXTEDIT_UPDATE'},
    )
    # Randomize UI state
    randomize_strength: bpy.props.FloatProperty(
        name="Strength",
        description="Randomization strength",
        default=0.5,
        min=0.0,
        max=1.0,
    )
    # Hair properties
    hair_color: bpy.props.EnumProperty(
        name="Hair Color",
        items=lambda self, ctx: [(k, k, "") for k in HAIR_COLORS.keys()],
    )
    hair_length: bpy.props.FloatProperty(
        name="Length",
        description="Hair strand length in meters",
        default=0.15,
        min=0.01,
        max=1.0,
        subtype='DISTANCE',
    )
    hair_count: bpy.props.IntProperty(
        name="Count",
        description="Number of parent hair strands",
        default=500,
        min=50,
        max=10000,
    )

    # Animation speed
    @staticmethod
    def _update_anim_speed(self, context):
        """Adjust fps_base to change playback speed in real-time."""
        speed = max(0.1, self.anim_speed)
        context.scene.render.fps_base = 1.0 / speed

    anim_speed: bpy.props.FloatProperty(
        name="Speed",
        description="Animation playback speed multiplier",
        default=1.0,
        min=0.1,
        max=3.0,
        step=10,
        update=_update_anim_speed.__func__,
    )


def register():
    bpy.utils.register_class(HumanBodyProperties)
    bpy.types.Scene.humanbody = bpy.props.PointerProperty(
        type=HumanBodyProperties)


def unregister():
    del bpy.types.Scene.humanbody
    bpy.utils.unregister_class(HumanBodyProperties)
