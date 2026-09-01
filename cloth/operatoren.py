# -*- coding: utf-8 -*-
import logging
import bpy
from ..assetCreator.preview import find_body_obj
from ..cloth.namen import CLOTH_GARMENT_TAG
from ..cloth.kleidungsstueck import _create_garment
from ..cloth.modifikatorsuche import _has_modifier
from ..cloth.modifikatoren import _add_cloth, _remove_cloth
from ..cloth.nadeln import _add_pin, _remove_selected_pins, _clear_pins
from ..cloth.stoffaktionen import (
    _run_simulation, _stop_simulation, _reset_simulation, _fit_to_body,
    _apply_base, _shake_cloth,
)
from ..cloth.garmentsuche import (
    _find_garment, _poll_garment, _poll_garment_and_body,
    _poll_garment_has_cloth,
)
logger = logging.getLogger(__name__)


class HUMANBODY_OT_cloth_add(bpy.types.Operator):
    """Create garment from body region and add cloth modifier"""
    bl_idname = "humanbody.cloth_add"
    bl_label = "Add Cloth"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return find_body_obj(context) is not None

    def execute(self, context):
        props = context.scene.humanbody_cloth_builder
        garment = _find_garment(context)

        # Auto-create garment if none exists
        if garment is None or _has_modifier(garment, 'CLOTH'):
            body = find_body_obj(context)
            garment = _create_garment(context, body, props.garment_region)
            if garment is None:
                self.report({'ERROR'}, "Failed to create garment")
                return {'CANCELLED'}

        _add_cloth(context, garment)
        self.report({'INFO'}, f"Added cloth to {garment.name}")
        return {'FINISHED'}


class HUMANBODY_OT_cloth_remove(bpy.types.Operator):
    """Remove cloth modifier from garment"""
    bl_idname = "humanbody.cloth_remove"
    bl_label = "Remove Cloth"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _poll_garment_has_cloth(context)

    def execute(self, context):
        garment = _find_garment(context)
        _remove_cloth(context, garment)
        self.report({'INFO'}, "Cloth removed")
        return {'FINISHED'}


class HUMANBODY_OT_cloth_rebuild(bpy.types.Operator):
    """Remove current garment and create a new one from selected region"""
    bl_idname = "humanbody.cloth_rebuild"
    bl_label = "Rebuild Garment"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return find_body_obj(context) is not None

    def execute(self, context):
        props = context.scene.humanbody_cloth_builder

        # Remove existing cloth garments
        to_remove = [o for o in context.scene.objects
                     if o.type == 'MESH' and o.data.get(CLOTH_GARMENT_TAG)]
        for obj in to_remove:
            # Also remove associated pin empties
            _clear_pins(context, obj)
            bpy.data.objects.remove(obj, do_unlink=True)

        # Remove collision from body
        body = find_body_obj(context)
        if body:
            for mod in list(body.modifiers):
                if mod.type == 'COLLISION':
                    body.modifiers.remove(mod)

        # Create new garment + cloth
        garment = _create_garment(context, body, props.garment_region)
        if garment is None:
            self.report({'ERROR'}, "Failed to create garment")
            return {'CANCELLED'}

        _add_cloth(context, garment)
        self.report({'INFO'}, f"Rebuilt: {garment.name}")
        return {'FINISHED'}


class HUMANBODY_OT_cloth_remove_garment(bpy.types.Operator):
    """Remove the garment mesh entirely"""
    bl_idname = "humanbody.cloth_remove_garment"
    bl_label = "Remove Garment"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _find_garment(context) is not None

    def execute(self, context):
        garment = _find_garment(context)
        name = garment.name
        _clear_pins(context, garment)
        bpy.data.objects.remove(garment, do_unlink=True)
        self.report({'INFO'}, f"Removed garment: {name}")
        return {'FINISHED'}


class HUMANBODY_OT_cloth_run_sim(bpy.types.Operator):
    """Play cloth simulation"""
    bl_idname = "humanbody.cloth_run_sim"
    bl_label = "Play Simulation"

    @classmethod
    def poll(cls, context):
        # Allow play if any cloth modifier exists in scene
        for obj in context.scene.objects:
            if _has_modifier(obj, 'CLOTH'):
                return True
        return False

    def execute(self, context):
        _run_simulation(context)
        return {'FINISHED'}


class HUMANBODY_OT_cloth_stop_sim(bpy.types.Operator):
    """Stop cloth simulation playback"""
    bl_idname = "humanbody.cloth_stop_sim"
    bl_label = "Stop Simulation"

    def execute(self, context):
        _stop_simulation(context)
        return {'FINISHED'}


class HUMANBODY_OT_cloth_reset_sim(bpy.types.Operator):
    """Reset simulation to frame 1"""
    bl_idname = "humanbody.cloth_reset_sim"
    bl_label = "Reset Simulation"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        _reset_simulation(context)
        self.report({'INFO'}, "Simulation reset")
        return {'FINISHED'}


class HUMANBODY_OT_cloth_add_pin(bpy.types.Operator):
    """Add a pin to selected vertices (Edit Mode)"""
    bl_idname = "humanbody.cloth_add_pin"
    bl_label = "Add Pin"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and obj.type == 'MESH'
                and obj.mode == 'EDIT'
                and not obj.data.get("humanbody"))

    def execute(self, context):
        _add_pin(context)
        self.report({'INFO'}, "Pin added")
        return {'FINISHED'}


class HUMANBODY_OT_cloth_remove_pin(bpy.types.Operator):
    """Remove selected pin empties"""
    bl_idname = "humanbody.cloth_remove_pin"
    bl_label = "Remove Selected Pins"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(o.get('is_pin') for o in context.selected_objects)

    def execute(self, context):
        _remove_selected_pins(context)
        self.report({'INFO'}, "Pins removed")
        return {'FINISHED'}


class HUMANBODY_OT_cloth_clear_pins(bpy.types.Operator):
    """Remove all pins from garment"""
    bl_idname = "humanbody.cloth_clear_pins"
    bl_label = "Clear All Pins"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _poll_garment(context)

    def execute(self, context):
        garment = _find_garment(context)
        _clear_pins(context, garment)
        self.report({'INFO'}, "All pins cleared")
        return {'FINISHED'}


class HUMANBODY_OT_cloth_fit_to_body(bpy.types.Operator):
    """Fit garment to body using Shrinkwrap + Corrective Smooth"""
    bl_idname = "humanbody.cloth_fit_to_body"
    bl_label = "Fit to Body"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _poll_garment_and_body(context)

    def execute(self, context):
        garment = _find_garment(context)
        body = find_body_obj(context)
        _fit_to_body(context, garment, body)
        self.report({'INFO'}, "Garment fitted to body")
        return {'FINISHED'}


class HUMANBODY_OT_cloth_apply_base(bpy.types.Operator):
    """Apply cloth simulation into mesh"""
    bl_idname = "humanbody.cloth_apply_base"
    bl_label = "Apply Base"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _poll_garment_has_cloth(context)

    def execute(self, context):
        garment = _find_garment(context)
        _apply_base(context, garment)
        self.report({'INFO'}, "Cloth simulation applied")
        return {'FINISHED'}


class HUMANBODY_OT_cloth_shake(bpy.types.Operator):
    """Randomize shrink values for natural wrinkles"""
    bl_idname = "humanbody.cloth_shake"
    bl_label = "Shake"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _poll_garment_has_cloth(context)

    def execute(self, context):
        garment = _find_garment(context)
        _shake_cloth(context, garment)
        self.report({'INFO'}, "Cloth shake applied")
        return {'FINISHED'}


class HUMANBODY_OT_cloth_paint_weight(bpy.types.Operator):
    """Enter weight paint mode for cloth vertex groups"""
    bl_idname = "humanbody.cloth_paint_weight"
    bl_label = "Paint Weight"

    @classmethod
    def poll(cls, context):
        return _poll_garment(context)

    def execute(self, context):
        garment = _find_garment(context)
        # Need garment to be active for weight paint mode
        context.view_layer.objects.active = garment
        if garment.mode != 'WEIGHT_PAINT':
            bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        else:
            bpy.ops.object.mode_set(mode='OBJECT')
        return {'FINISHED'}
