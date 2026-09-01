# -*- coding: utf-8 -*-
from ..morphing import Morpher
from .zonen import _MAIN_CATEGORIES
from .zonen import _group_category
from .zustand import Anzeigezustand


def _draw_daz_slider(layout, data, prop_name, label):
    """Standard Blender property row: label left, value right."""
    layout.prop(data, prop_name, text=label)


def _draw_daz_custom_prop(layout, obj, key, label):
    """Full-width native Blender slider: [Label ═══slider═══ value]"""
    if key not in obj.data:
        return
    layout.prop(obj.data, f'["{key}"]', text=label, slider=True)


def _draw_main_body(layout, context):
    """Shared draw logic for the main HumanBody panel."""
    obj = context.active_object

    if not obj or obj.type != 'MESH' or not obj.data.get("humanbody"):
        layout.operator("humanbody.import_character", icon='IMPORT')
        layout.label(text="Select a HumanBody character", icon='INFO')
        return False

    # Pick mode toggle — always visible in main panel
    pick_row = layout.row(align=True)
    pick_row.scale_y = 1.3
    if Anzeigezustand.wahl_laeuft:
        pick_row.operator("humanbody.pick_part",
                          text="Exit Pick Mode",
                          icon='RESTRICT_SELECT_OFF', depress=True)
    else:
        pick_row.operator("humanbody.pick_part",
                          text="Click to Select on Model",
                          icon='RESTRICT_SELECT_OFF')

    return True


def _draw_body_type(layout, context):
    """Shared draw logic for the Body Type sub-panel."""
    props = context.scene.humanbody

    # Body Type combo
    layout.prop(props, "body_type", text="Body Type")

    layout.separator()

    # Quick Adjust sliders
    _draw_daz_slider(layout, props, "meta_age", "Age")
    _draw_daz_slider(layout, props, "meta_mass", "Mass")
    _draw_daz_slider(layout, props, "meta_tone", "Tone")
    _draw_daz_slider(layout, props, "meta_height", "Height (cm)")

    layout.separator()

    row = layout.row(align=True)
    row.operator("humanbody.update_morphs", icon='FILE_REFRESH')
    row.operator("humanbody.reset_morphs", icon='LOOP_BACK')


def _draw_parts_body(layout, context):
    """Shared draw logic for the Parts morph sliders with main category grouping."""
    props = context.scene.humanbody
    obj = context.active_object
    m = Morpher.get(obj)

    if not m.l2_morphs:
        layout.label(text="No morph data loaded")
        return

    # Pick-on-model button (also in main panel, repeated here for convenience)
    pick_row = layout.row(align=True)
    if Anzeigezustand.wahl_laeuft:
        pick_row.operator("humanbody.pick_part",
                          text="Exit Pick Mode",
                          icon='RESTRICT_SELECT_OFF', depress=True)
    else:
        pick_row.operator("humanbody.pick_part",
                          text="Click to Select on Model",
                          icon='RESTRICT_SELECT_OFF')

    # Search bar
    row = layout.row(align=True)
    row.prop(props, "filter_text", text="", icon='VIEWZOOM')

    filt = props.filter_text.lower()

    # Build main-group → subcategory → morphs mapping
    main_groups = {}  # main_cat -> {sub_cat -> [morph, ...]}
    if filt:
        for morph in m.l2_morphs:
            if filt not in morph.name.lower():
                continue
            main = _group_category(morph.category)
            if main not in main_groups:
                main_groups[main] = {}
            sub = morph.category
            if sub not in main_groups[main]:
                main_groups[main][sub] = []
            main_groups[main][sub].append(morph)
    else:
        for cat, morphs in m._categories.items():
            main = _group_category(cat)
            if main not in main_groups:
                main_groups[main] = {}
            main_groups[main][cat] = morphs

    if not main_groups:
        layout.label(text="No morphs match filter")
        return

    selected = props.parts_selected

    # Auto-select first main group
    ordered_mains = [name for name, _ in _MAIN_CATEGORIES if name in main_groups]
    if (not selected or selected not in main_groups) and ordered_mains:
        selected = ordered_mains[0]

    # --- Two-column split: main categories left, sliders right ---
    split = layout.split(factor=0.22)

    # LEFT COLUMN: main category buttons
    left = split.column(align=True)
    obj_data = obj.data
    for main_name, main_icon in _MAIN_CATEGORIES:
        if main_name not in main_groups:
            continue
        is_selected = (selected == main_name)

        # Check if any morph in this group is non-zero
        nonzero = False
        for morphs in main_groups[main_name].values():
            for morph in morphs:
                if abs(obj_data.get("hb_L2_" + morph.name, 0.0)) > 0.001:
                    nonzero = True
                    break
            if nonzero:
                break

        icon = main_icon if not nonzero else 'RADIOBUT_ON'
        op = left.operator("humanbody.select_category",
                           text=main_name,
                           depress=is_selected,
                           icon=icon)
        op.category = main_name

    # RIGHT COLUMN: sliders grouped by subcategory
    right = split.column()

    if selected and selected in main_groups:
        subcats = main_groups[selected]
        sorted_subs = sorted(subcats.keys())

        for sub_name in sorted_subs:
            morphs = subcats[sub_name]
            # Subcategory header
            box = right.box()
            box.label(text=sub_name, icon='MESH_DATA')
            col = box.column(align=True)
            prefix = sub_name + "_"
            prefix_len = len(prefix)
            for morph in morphs:
                short = morph.name
                if short.startswith(prefix):
                    short = short[prefix_len:]
                short = short.replace("_", " ")
                _draw_daz_custom_prop(col, obj, "hb_L2_" + morph.name,
                                      short)


def _draw_favorites_body(layout, context):
    """Shared draw logic for the Currently Used panel."""
    obj = context.active_object
    m = Morpher.get(obj)

    count = 0
    col = layout.column(align=True)
    for morph in m.l2_morphs:
        val = obj.data.get("hb_L2_" + morph.name, 0.0)
        if abs(val) > 0.001:
            _draw_daz_custom_prop(col, obj, "hb_L2_" + morph.name,
                                  morph.name.replace("_", " "))
            count += 1

    if count == 0:
        layout.label(text="No morphs active")


def _poll_humanbody(context):
    obj = context.active_object
    return obj and obj.type == 'MESH' and obj.data.get("humanbody")


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
