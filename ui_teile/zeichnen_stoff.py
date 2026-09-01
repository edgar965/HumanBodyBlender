# -*- coding: utf-8 -*-
import bpy
from ..cloth.modifikatorsuche import _has_modifier, _get_modifiers
from ..cloth.garmentsuche import _find_garment


def _draw_cloth_builder_body(layout, context):
    """Draw logic for the Cloth Builder panel."""
    from .assetCreator.preview import find_body_obj

    props = context.scene.humanbody_cloth_builder
    body = find_body_obj(context)
    garment = _find_garment(context)

    has_cloth = False
    if garment:
        has_cloth = _has_modifier(garment, 'CLOTH')

    # --- Setup ---
    box = layout.box()
    box.label(text="Setup", icon='MODIFIER')

    # Region selector — always visible
    box.prop(props, "garment_region")
    box.prop(props, "looseness", slider=True)

    if has_cloth and garment:
        row = box.row(align=True)
        row.label(text=f"Cloth: {garment.name}", icon='MOD_CLOTH')
        cloth_mods = _get_modifiers('CLOTH', [garment])
        if cloth_mods:
            row.prop(cloth_mods[0], "show_viewport", text="",
                     icon='HIDE_OFF' if cloth_mods[0].show_viewport else 'HIDE_ON')
        row.operator("humanbody.cloth_remove", text="", icon='X')
        # Rebuild + Remove
        row = box.row(align=True)
        row.operator("humanbody.cloth_rebuild", text="Rebuild",
                     icon='FILE_REFRESH')
        row.operator("humanbody.cloth_remove_garment", text="Remove",
                     icon='TRASH')
    elif garment:
        box.label(text=f"Target: {garment.name}", icon='MESH_DATA')
        row = box.row(align=True)
        row.scale_y = 1.3
        row.operator("humanbody.cloth_add", icon='MOD_CLOTH')
        row.operator("humanbody.cloth_remove_garment", text="",
                     icon='TRASH')
    else:
        row = box.row(align=True)
        row.scale_y = 1.3
        row.operator("humanbody.cloth_add", icon='MOD_CLOTH')

    if body:
        row = box.row(align=True)
        has_coll = _has_modifier(body, 'COLLISION')
        icon = 'CHECKMARK' if has_coll else 'ERROR'
        row.label(text=f"Collision: {body.name}", icon=icon)

    # --- Simulation ---
    box = layout.box()
    box.label(text="Simulation", icon='PLAY')

    row = box.row(align=True)
    row.scale_y = 1.2
    if bpy.context.screen.is_animation_playing:
        row.operator("humanbody.cloth_stop_sim", text="Stop", icon='PAUSE')
    else:
        row.operator("humanbody.cloth_run_sim", text="Play", icon='PLAY')
    row.operator("humanbody.cloth_reset_sim", text="Reset", icon='LOOP_BACK')

    col = box.column(align=True)
    col.prop(props, "simulation_frames")
    col.prop(props, "sim_quality")
    col.prop(props, "collision_quality")
    col.prop(props, "collision_distance")

    # --- Cloth Settings (direct modifier access) ---
    if has_cloth and garment:
        cloth_mods = _get_modifiers('CLOTH', [garment])
        if cloth_mods:
            mod = cloth_mods[0]
            box = layout.box()
            box.label(text="Cloth Settings", icon='PREFERENCES')

            col = box.column(align=True)
            col.prop(mod.collision_settings, "use_self_collision",
                     text="Self Collision")
            col.prop(mod.settings, "use_pressure")
            if mod.settings.use_pressure:
                col.prop(mod.settings, "uniform_pressure_force",
                         text="Pressure Force")
            col.prop(mod.settings, "shrink_min", text="Shrink Min")
            col.prop(mod.settings, "bending_stiffness",
                     text="Bending Stiffness")

    # --- Pinning ---
    box = layout.box()
    box.label(text="Pinning", icon='PINNED')

    col = box.column(align=True)
    col.prop(props, "pin_scale")
    col.prop(props, "pin_shape")

    row = box.row(align=True)
    row.operator("humanbody.cloth_add_pin", icon='PINNED')

    row = box.row(align=True)
    row.operator("humanbody.cloth_remove_pin", text="Remove Selected",
                 icon='UNPINNED')
    row.operator("humanbody.cloth_clear_pins", text="Clear All", icon='X')

    # --- Fit & Apply ---
    box = layout.box()
    box.label(text="Fit & Apply", icon='CHECKMARK')

    col = box.column(align=True)
    col.prop(props, "fit_offset", text="Offset")
    col.prop(props, "fit_corrective_iters", text="Corrective Iterations")

    box.operator("humanbody.cloth_fit_to_body", icon='MOD_SHRINKWRAP')
    box.operator("humanbody.cloth_apply_base", icon='CHECKMARK')

    row = box.row(align=True)
    row.operator("humanbody.cloth_shake", icon='RNDCURVE')
    row.operator("humanbody.cloth_paint_weight", icon='WPAINT_HLT')


def _draw_cloth_primitive_body(layout, context):
    """Draw logic for the Cloth Primitive panel."""
    props = context.scene.humanbody_cloth_primitive
    pt = props.prim_type

    # Primitive type selector
    layout.prop(props, "prim_type")

    col = layout.column(align=True)
    col.prop(props, "segments")

    # Body-wrap types: length
    _BODY_TYPES = {'PRIM_SKIRT', 'PRIM_PANTS', 'PRIM_TOP', 'PRIM_ARMS',
                   'PRIM_NECK', 'PRIM_HEAD', 'PRIM_SHOES', 'PRIM_PUFFER'}
    # Freeform types: radius + z position
    _FREE_TYPES = {'PRIM_DISC', 'PRIM_SPHERE', 'PRIM_OVAL_DISC', 'PRIM_TRIANGLE'}

    if pt in _BODY_TYPES:
        col.prop(props, "prim_length")
    if pt in _FREE_TYPES:
        col.prop(props, "prim_radius")
        col.prop(props, "prim_z")
    if pt == 'PRIM_SKIRT':
        col.prop(props, "prim_flare")
    if pt == 'PRIM_PUFFER':
        col.prop(props, "prim_count")

    layout.separator()

    # Create button
    row = layout.row(align=True)
    row.scale_y = 1.3
    row.operator("humanbody.cloth_prim_create", icon='MESH_CONE')

    # Simulation controls (shared)
    layout.separator()
    box = layout.box()
    box.label(text="Simulation", icon='PLAY')
    row = box.row(align=True)
    row.scale_y = 1.2
    if bpy.context.screen.is_animation_playing:
        row.operator("humanbody.cloth_stop_sim", text="Stop", icon='PAUSE')
    else:
        row.operator("humanbody.cloth_run_sim", text="Play", icon='PLAY')
    row.operator("humanbody.cloth_reset_sim", text="Reset", icon='LOOP_BACK')


def _draw_cloth_template_body(layout, context):
    """Draw logic for the Cloth Template panel."""
    from .assetCreator.preview import find_body_obj

    props = context.scene.humanbody_cloth_template

    # Template type selector
    layout.prop(props, "template_type")
    layout.prop(props, "segments")
    layout.prop(props, "tightness", slider=True)
    row = layout.row(align=True)
    row.prop(props, "top_extend")
    row.prop(props, "bottom_extend")

    layout.separator()

    # Create button
    row = layout.row(align=True)
    row.scale_y = 1.3
    row.operator("humanbody.cloth_tpl_create", icon='MOD_CLOTH')

    # Simulation controls (shared)
    layout.separator()
    box = layout.box()
    box.label(text="Simulation", icon='PLAY')
    row = box.row(align=True)
    row.scale_y = 1.2
    if bpy.context.screen.is_animation_playing:
        row.operator("humanbody.cloth_stop_sim", text="Stop", icon='PAUSE')
    else:
        row.operator("humanbody.cloth_run_sim", text="Play", icon='PLAY')
    row.operator("humanbody.cloth_reset_sim", text="Reset", icon='LOOP_BACK')
