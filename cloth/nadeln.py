# -*- coding: utf-8 -*-
import copy
import logging
import bpy
logger = logging.getLogger(__name__)
from .modifikatorsuche import _get_modifiers
from .namen import PIN_GROUP_NAME


def _reset_pin_locations(context):
    """Reset hook modifiers and pin transforms to deltas."""
    for obj in context.scene.objects:
        if not hasattr(obj, 'modifiers'):
            continue

        hook_mods = [m for m in obj.modifiers if m.type == 'HOOK']
        if not hook_mods:
            continue

        with context.temp_override(active_object=obj, object=obj,
                                   selected_objects=[obj],
                                   selected_editable_objects=[obj],
                                   edit_object=obj,
                                   mode='EDIT_MESH'):
            bpy.ops.object.mode_set(mode='EDIT')
            for mod in hook_mods:
                try:
                    bpy.ops.object.hook_reset(modifier=mod.name)
                # stumm gewollt: hook_reset wirft, wenn der Modifikator kein
                # Ziel hat. Dann ist nichts zurueckzusetzen.
                except RuntimeError:
                    pass
            bpy.ops.object.mode_set(mode='OBJECT')

        # Reset pin empties
        for mod in hook_mods:
            pin = mod.object
            if pin and pin.get('is_pin'):
                with context.temp_override(active_object=pin, object=pin,
                                           selected_objects=[pin],
                                           selected_editable_objects=[pin]):
                    bpy.ops.object.transforms_to_deltas(mode='ALL')


def _add_pin(context):
    """Add a pin to selected vertices in edit mode."""
    garment = context.active_object
    if not garment or garment.type != 'MESH':
        return

    props = context.scene.humanbody_cloth_builder

    # Assign selected verts to pinned group
    if PIN_GROUP_NAME not in garment.vertex_groups:
        garment.vertex_groups.new(name=PIN_GROUP_NAME)

    # Set pinned group as active and assign selected verts
    vg_index = garment.vertex_groups[PIN_GROUP_NAME].index
    garment.vertex_groups.active_index = vg_index
    bpy.ops.object.vertex_group_assign()

    # Snap cursor to selection
    orig_cursor = copy.copy(context.scene.cursor.location)
    bpy.ops.view3d.snap_cursor_to_selected()

    # Switch to object mode and create empty
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.empty_add(type=props.pin_shape, align='WORLD')

    pin = context.active_object
    pin.name = "Pin"
    pin['is_pin'] = True
    pin.empty_display_size = props.pin_scale
    pin.empty_display_type = props.pin_shape

    # Restore cursor
    context.scene.cursor.location = orig_cursor

    # Convert transforms to deltas
    bpy.ops.object.transforms_to_deltas(mode='ALL')

    # Select garment, go to edit mode, add hook
    context.view_layer.objects.active = garment
    garment.select_set(True)
    pin.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.object.hook_add_selob(use_bone=False)

    # Move hook modifiers to index 0
    hook_mods = [m for m in garment.modifiers if m.type == 'HOOK']
    for mod in hook_mods:
        with context.temp_override(active_object=garment, object=garment):
            bpy.ops.object.modifier_move_to_index(
                modifier=mod.name, index=0)

    # Ensure cloth modifier uses pin group
    cloth_mods = _get_modifiers('CLOTH', [garment])
    if cloth_mods:
        cloth_mods[0].settings.vertex_group_mass = PIN_GROUP_NAME


def _get_hook_modifiers_using_pin(obj, pin_empty):
    """Find hook modifiers on obj that reference pin_empty."""
    result = []
    for mod in obj.modifiers:
        if mod.type == 'HOOK' and mod.object == pin_empty:
            result.append(mod)
    return result


def _remove_selected_pins(context):
    """Remove selected pin empties and their hook modifiers."""
    pins_to_remove = [o for o in context.selected_objects
                      if o.get('is_pin')]

    for pin in pins_to_remove:
        # Find all objects that have hook modifiers using this pin
        for obj in context.scene.objects:
            if not hasattr(obj, 'modifiers'):
                continue
            hooks = _get_hook_modifiers_using_pin(obj, pin)
            for mod in hooks:
                # Remove verts from pinned group
                if PIN_GROUP_NAME in obj.vertex_groups:
                    vg = obj.vertex_groups[PIN_GROUP_NAME]
                    try:
                        vg.remove(list(mod.vertex_indices))
                    # stumm gewollt: Der Index kann schon weg sein, wenn das
                    # Netz neu gebaut wurde. Der Modifikator faellt gleich
                    # darunter ohnehin.
                    except Exception:
                        pass
                obj.modifiers.remove(mod)

        bpy.data.objects.remove(pin, do_unlink=True)


def _clear_pins(context, garment):
    """Remove all pins for a garment."""
    pins = []
    for mod in garment.modifiers:
        if mod.type == 'HOOK' and mod.object and mod.object.get('is_pin'):
            pins.append(mod.object)

    for pin in pins:
        hooks = _get_hook_modifiers_using_pin(garment, pin)
        for mod in hooks:
            garment.modifiers.remove(mod)
        bpy.data.objects.remove(pin, do_unlink=True)

    # Clear pinned vertex group
    if PIN_GROUP_NAME in garment.vertex_groups:
        vg = garment.vertex_groups[PIN_GROUP_NAME]
        all_indices = list(range(len(garment.data.vertices)))
        vg.remove(all_indices)
