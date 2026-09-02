# -*- coding: utf-8 -*-
from ..morphing import Morpher
from .wahlknopf import Wahlknopf


class Koerperseite:
    u"""Die frueheren Modulfunktionen, gebuendelt."""

    @staticmethod
    def _draw_daz_slider(layout, data, prop_name, label):
        """Standard Blender property row: label left, value right."""
        layout.prop(data, prop_name, text=label)

    @staticmethod
    def _draw_daz_custom_prop(layout, obj, key, label):
        """Full-width native Blender slider: [Label ═══slider═══ value]"""
        if key not in obj.data:
            return
        layout.prop(obj.data, f'["{key}"]', text=label, slider=True)

    @staticmethod
    def _draw_main_body(layout, context):
        """Shared draw logic for the main HumanBody panel."""
        obj = context.active_object

        if not obj or obj.type != 'MESH' or not obj.data.get("humanbody"):
            layout.operator("humanbody.import_character", icon='IMPORT')
            layout.label(text="Select a HumanBody character", icon='INFO')
            return False

        # Der Umschalter der Teilewahl — im Hauptpanel gross.
        Wahlknopf.zeichnen(layout, hoehe=1.3)

        return True

    @staticmethod
    def _draw_body_type(layout, context):
        """Shared draw logic for the Body Type sub-panel."""
        props = context.scene.humanbody

        # Body Type combo
        layout.prop(props, "body_type", text="Body Type")

        layout.separator()

        # Quick Adjust sliders
        Koerperseite._draw_daz_slider(layout, props, "meta_age", "Age")
        Koerperseite._draw_daz_slider(layout, props, "meta_mass", "Mass")
        Koerperseite._draw_daz_slider(layout, props, "meta_tone", "Tone")
        Koerperseite._draw_daz_slider(layout, props, "meta_height", "Height (cm)")

        layout.separator()

        row = layout.row(align=True)
        row.operator("humanbody.update_morphs", icon='FILE_REFRESH')
        row.operator("humanbody.reset_morphs", icon='LOOP_BACK')


    @staticmethod
    def _draw_favorites_body(layout, context):
        """Shared draw logic for the Currently Used panel."""
        obj = context.active_object
        m = Morpher.get(obj)

        count = 0
        col = layout.column(align=True)
        for morph in m.l2_morphs:
            val = obj.data.get("hb_L2_" + morph.name, 0.0)
            if abs(val) > 0.001:
                Koerperseite._draw_daz_custom_prop(col, obj, "hb_L2_" + morph.name,
                                      morph.name.replace("_", " "))
                count += 1

        if count == 0:
            layout.label(text="No morphs active")

    @staticmethod
    def _poll_humanbody(context):
        obj = context.active_object
        return obj and obj.type == 'MESH' and obj.data.get("humanbody")

    @staticmethod
    def _draw_materials_body(layout, context):
        """Draw logic for the Materials panel."""
        props = context.scene.humanbody
        obj = context.active_object
        mats = obj.data.materials if obj else []

        # Eye color preset
        layout.prop(props, "eye_color")

        if len(mats) < 10:
            layout.label(text="Import character first", icon='INFO')
            return

        layout.separator()

        # Editable material Base Color (directly on shader node)
        _MAT_LABELS = [
            (0,  "Skin",           'USER'),
            (9,  "Nails - Hand",   'BONE_DATA'),
            (10, "Nails - Feet",   'BONE_DATA'),
            (6,  "Iris",           'HIDE_OFF'),
            (4,  "Sclera",         'SHADING_SOLID'),
            (8,  "Teeth",          'MESH_DATA'),
            (7,  "Tongue",         'MESH_DATA'),
            (3,  "Pupil",          'PMARKER_ACT'),
            (1,  "Areola",         'MESH_CIRCLE'),
            (2,  "Eyelash",        'HIDE_OFF'),
        ]
        box = layout.box()
        for idx, label, icon in _MAT_LABELS:
            if idx >= len(mats):
                continue
            mat = mats[idx]
            if mat and mat.node_tree:
                for node in mat.node_tree.nodes:
                    if node.type == 'BSDF_PRINCIPLED':
                        row = box.row(align=True)
                        row.label(text=label, icon=icon)
                        row.prop(node.inputs['Base Color'], "default_value", text="")
                        break

        layout.separator()
        layout.label(text="Skin & nails auto-update with Body Type", icon='INFO')
