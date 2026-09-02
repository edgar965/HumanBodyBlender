# -*- coding: utf-8 -*-
import random
import logging
import bpy
logger = logging.getLogger(__name__)
from .modifikatorsuche import Modifikatorsuche
from .nadeln import Nadeln
from .modifikatoren import Modifikatoren
from .namen import CLOTH_TRIANGULATION


class Stoffaktionen:
    u"""Die frueheren Modulfunktionen, gebuendelt."""

    @staticmethod
    def _run_simulation(context):
        """Set end frame and play animation for cloth sim."""
        props = context.scene.humanbody_cloth_builder
        context.scene.frame_end = props.simulation_frames
        Modifikatoren._sync_modifier_settings(context)
        bpy.context.scene.sync_mode = 'NONE'
        bpy.ops.screen.animation_play()

    @staticmethod
    def _stop_simulation(context):
        """Stop animation playback."""
        if bpy.context.screen.is_animation_playing:
            bpy.ops.screen.animation_play()

    @staticmethod
    def _reset_simulation(context):
        """Jump to frame 1 and reset pin locations."""
        bpy.ops.screen.frame_jump(end=False)
        Nadeln._reset_pin_locations(context)

    @staticmethod
    def _fit_to_body(context, garment, body):
        """Shrinkwrap garment to body + corrective smooth, then apply."""
        props = context.scene.humanbody_cloth_builder

        with context.temp_override(active_object=garment, object=garment,
                                   selected_objects=[garment],
                                   selected_editable_objects=[garment]):
            # Shrinkwrap
            bpy.ops.object.modifier_add(type='SHRINKWRAP')
            sw = garment.modifiers[-1]
            sw.wrap_method = 'TARGET_PROJECT'
            sw.wrap_mode = 'OUTSIDE_SURFACE'
            sw.offset = props.fit_offset
            sw.target = body

            # Corrective smooth — bind with shrinkwrap hidden
            sw.show_viewport = False
            bpy.ops.object.modifier_add(type='CORRECTIVE_SMOOTH')
            cs = garment.modifiers[-1]
            cs.rest_source = 'BIND'
            cs.iterations = props.fit_corrective_iters
            bpy.ops.object.correctivesmooth_bind(modifier=cs.name)
            sw.show_viewport = True

            # Apply both
            bpy.ops.object.modifier_apply(modifier=sw.name)
            bpy.ops.object.modifier_apply(modifier=cs.name)

        logger.info("Fit garment '%s' to body", garment.name)

    @staticmethod
    def _apply_base(context, garment):
        """Bake cloth simulation into mesh (apply cloth modifier as shape)."""
        cloth_mods = Modifikatorsuche._get_modifiers('CLOTH', [garment])
        if not cloth_mods:
            return

        with context.temp_override(active_object=garment, object=garment,
                                   selected_objects=[garment],
                                   selected_editable_objects=[garment]):
            # Apply cloth as shape key
            bpy.ops.object.modifier_apply_as_shapekey(
                keep_modifier=False, modifier=cloth_mods[0].name)

            # Set cloth shape key value to 1, basis to 0
            if garment.data.shape_keys and garment.data.shape_keys.key_blocks:
                for kb in garment.data.shape_keys.key_blocks:
                    kb.value = 0.0
                garment.data.shape_keys.key_blocks[-1].value = 1.0

                # Apply the shape key (flatten)
                bpy.ops.object.shape_key_move(type='BOTTOM')
                while len(garment.data.shape_keys.key_blocks) > 1:
                    garment.active_shape_key_index = 0
                    bpy.ops.object.shape_key_remove()
                bpy.ops.object.shape_key_remove()

        # Remove triangulate too
        tri = garment.modifiers.get(CLOTH_TRIANGULATION)
        if tri:
            garment.modifiers.remove(tri)

        # Reset pins
        Nadeln._reset_pin_locations(context)

        logger.info("Applied cloth base on: %s", garment.name)

    @staticmethod
    def _shake_cloth(context, garment):
        """Shrink then expand cloth to create random wrinkles."""
        cloth_mods = Modifikatorsuche._get_modifiers('CLOTH', [garment])
        if not cloth_mods:
            return

        mod = cloth_mods[0]

        # Random shrink/expand
        mod.settings.shrink_min = random.uniform(-0.3, -0.05)
        mod.settings.shrink_max = random.uniform(0.05, 0.3)

        logger.info("Shake cloth on: %s (shrink: %.3f..%.3f)",
                    garment.name, mod.settings.shrink_min, mod.settings.shrink_max)
