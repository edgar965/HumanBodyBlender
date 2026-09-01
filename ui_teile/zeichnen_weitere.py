# -*- coding: utf-8 -*-
from ..rig import _find_rig, _list_poses
from ..animation import _list_animations, _ANIM_CATEGORIES, _PROC_PREFIX
from ..haare.haarpfade import _list_hairstyles
from .zeichnen_koerper import _poll_humanbody


def _draw_hair_body(layout, context):
    """Draw logic for the Hair / Brows / Lashes panel."""
    import bpy as _bpy
    props = context.scene.humanbody
    obj = context.active_object

    layout.separator()

    # ---- Hair ----
    # Check if any hair exists (on body or as hair object)
    has_hair = False
    if obj:
        for ps in obj.particle_systems:
            if ps.settings.type == 'HAIR':
                has_hair = True
                break
    if not has_hair:
        for o in _bpy.data.objects:
            if o.get("humanbody_hair"):
                has_hair = True
                break

    # Hair color
    layout.prop(props, "hair_color")

    # Hair assets (from .blend files)
    assets = _list_hairstyles()
    if assets:
        layout.separator()
        layout.label(text="Hair Assets:", icon='ASSET_MANAGER')
        col = layout.column(align=True)
        for key, label in assets:
            icon = 'STRANDS' if 'particle' in key else 'MESH_DATA'
            op = col.operator("humanbody.load_hairstyle",
                              text=label, icon=icon)
            op.asset_key = key

    layout.separator()

    # Procedural hair section
    layout.label(text="Procedural:", icon='OUTLINER_OB_CURVES')
    layout.prop(props, "hair_length")
    layout.prop(props, "hair_count")
    row = layout.row(align=True)
    row.operator("humanbody.create_hair", icon='STRANDS')

    layout.separator()

    # Remove / Recolor
    if has_hair:
        row = layout.row(align=True)
        row.operator("humanbody.recolor_hair", icon='COLOR')
        row.operator("humanbody.remove_hair", icon='X')


def _draw_rig_body(layout, context):
    """Draw logic for the Rig panel."""
    obj = context.active_object
    rig = _find_rig(obj) if obj else None

    if rig:
        layout.label(text=f"Rig: {rig.name} ({len(rig.data.bones)} bones)",
                     icon='ARMATURE_DATA')
        layout.operator("humanbody.remove_rig", text="Remove Rig", icon='X')
    else:
        layout.label(text="No rig attached", icon='INFO')
        layout.operator("humanbody.add_rig", text="Add Rig",
                        icon='ARMATURE_DATA')


def _draw_pose_body(layout, context):
    """Draw logic for the Pose panel."""
    obj = context.active_object
    rig = _find_rig(obj) if obj else None

    if not rig:
        layout.label(text="Add a rig first", icon='INFO')
        return

    # Clear pose button
    layout.operator("humanbody.clear_pose", text="Reset Pose", icon='LOOP_BACK')
    layout.separator()

    # List available poses
    poses = _list_poses()
    if not poses:
        layout.label(text="No poses found", icon='INFO')
        return

    layout.label(text=f"{len(poses)} Poses:", icon='POSE_HLT')
    col = layout.column(align=True)
    for name, label in poses:
        op = col.operator("humanbody.load_pose", text=label, icon='ARMATURE_DATA')
        op.pose_name = name


def _draw_animation_body(layout, context):
    """Draw logic for the Animation panel (BVH motion capture)."""
    props = context.scene.humanbody
    obj = context.active_object
    rig = _find_rig(obj) if obj else None

    if not rig:
        layout.label(text="Add a rig first", icon='INFO')
        return

    # Stop button + Speed slider
    row = layout.row(align=True)
    row.operator("humanbody.stop_animation", text="Stop", icon='CANCEL')
    row.prop(props, "anim_speed", slider=True)

    row = layout.row(align=True)
    row.operator("humanbody.batch_retarget", text="Pre-cache All", icon='FILE_CACHE')
    row.operator("humanbody.mocapnet_webui", text="", icon='URL')
    layout.separator()

    # Get animations
    anims = _list_animations()
    if not anims:
        layout.label(text="No animations found", icon='INFO')
        return

    selected = props.anim_selected
    ordered = [name for name, _ in _ANIM_CATEGORIES if name in anims]
    if (not selected or selected not in anims) and ordered:
        selected = ordered[0]

    # Two-column layout: categories left, items right
    split = layout.split(factor=0.25)

    # LEFT: category buttons
    left = split.column(align=True)
    for cat_name, cat_icon in _ANIM_CATEGORIES:
        if cat_name not in anims:
            continue
        count = len(anims[cat_name])
        is_sel = (selected == cat_name)
        op = left.operator("humanbody.select_anim_cat",
                           text=f"{cat_name} ({count})",
                           depress=is_sel, icon=cat_icon)
        op.category = cat_name

    # RIGHT: animation items
    right = split.column()
    if selected and selected in anims:
        col = right.column(align=True)
        for label, path in anims[selected]:
            is_bvh = not path.startswith(_PROC_PREFIX)
            if is_bvh:
                row = col.row(align=True)
                op = row.operator("humanbody.load_animation",
                                  text=label, icon='PLAY')
                op.bvh_path = path
                op.anim_name = label
                op2 = row.operator("humanbody.load_bvh_native",
                                   text="", icon='IMPORT')
                op2.bvh_path = path
                op2.anim_name = label
            else:
                op = col.operator("humanbody.load_animation",
                                  text=label, icon='PLAY')
                op.bvh_path = path
                op.anim_name = label


def _draw_randomize_body(layout, context):
    """Draw logic for the Randomize panel."""
    props = context.scene.humanbody
    layout.prop(props, "randomize_strength", slider=True)
    layout.operator("humanbody.randomize", icon='RNDCURVE')


def _draw_finalize_body(layout, context):
    """Draw logic for the Finalize panel."""
    layout.label(text="Bake current shape into mesh:", icon='INFO')
    layout.operator("humanbody.finalize", icon='CHECKMARK')


def _draw_file_io_body(layout, context):
    """Draw logic for the File I/O panel."""
    has_char = _poll_humanbody(context)
    if has_char:
        row = layout.row(align=True)
        row.operator("humanbody.export_character", icon='EXPORT')
        row.operator("humanbody.import_settings", icon='IMPORT')
        layout.separator()

    layout.operator("humanbody.import_character", icon='MESH_DATA',
                     text="Import New Character")
