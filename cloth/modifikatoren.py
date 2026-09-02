# -*- coding: utf-8 -*-
import logging
import bpy
from ..assetCreator.vorschau.vorschausuche import Vorschausuche
logger = logging.getLogger(__name__)
from .knochengewichte import Knochengewichte
from .namen import (
    CLOTH_TRIANGULATION,
    PIN_GROUP_NAME,
    PRESSURE_GROUP_NAME,
    SHRINKING_GROUP_NAME,
    STIFFNESS_GROUP_NAME)
from .modifikatorsuche import Modifikatorsuche


class Modifikatoren:
    u"""Die frueheren Modulfunktionen, gebuendelt."""

    @staticmethod
    def _add_default_vertex_groups(obj):
        """Create pinned/stiffness/shrinking/pressure vertex groups and assign
        them to the cloth modifier."""
        group_names = [PIN_GROUP_NAME, STIFFNESS_GROUP_NAME,
                       SHRINKING_GROUP_NAME, PRESSURE_GROUP_NAME]

        for name in group_names:
            if name not in obj.vertex_groups:
                vg = obj.vertex_groups.new(name=name)
                # Fill pressure group with weight 1.0 on all verts
                if name == PRESSURE_GROUP_NAME:
                    all_indices = list(range(len(obj.data.vertices)))
                    vg.add(all_indices, 1.0, 'REPLACE')

        # Assign groups to cloth modifier
        cloth_mods = Modifikatorsuche._get_modifiers('CLOTH', [obj])
        if cloth_mods:
            mod = cloth_mods[0]
            mod.settings.vertex_group_mass = PIN_GROUP_NAME
            mod.settings.vertex_group_bending = STIFFNESS_GROUP_NAME
            mod.settings.vertex_group_shrink = SHRINKING_GROUP_NAME
            mod.settings.vertex_group_pressure = PRESSURE_GROUP_NAME

    @staticmethod
    def _sync_modifier_settings(context):
        """Push PropertyGroup values to all Cloth/Collision modifiers in scene."""
        props = context.scene.humanbody_cloth_builder

        for obj in context.scene.objects:
            if not hasattr(obj, 'modifiers'):
                continue

            for mod in obj.modifiers:
                if mod.type == 'CLOTH':
                    mod.point_cache.frame_end = props.simulation_frames
                    mod.settings.quality = props.sim_quality
                    mod.collision_settings.collision_quality = props.collision_quality
                    mod.collision_settings.distance_min = props.collision_distance
                    mod.collision_settings.self_distance_min = props.collision_distance

                if mod.type == 'COLLISION' and obj.collision:
                    obj.collision.thickness_outer = props.collision_distance
                    obj.collision.thickness_inner = props.collision_distance

    @staticmethod
    def _add_cloth(context, garment):
        """Add CLOTH modifier to garment + auto-add COLLISION to body."""
        if Modifikatorsuche._has_modifier(garment, 'CLOTH'):
            return

        props = context.scene.humanbody_cloth_builder
        Modifikatoren._nadelgewichte(garment)

        # Add cloth modifier
        with context.temp_override(active_object=garment, object=garment,
                                   selected_objects=[garment],
                                   selected_editable_objects=[garment]):
            bpy.ops.object.modifier_add(type='CLOTH')

        # Configure cloth settings (like Bystedt)
        cloth_mods = Modifikatorsuche._get_modifiers('CLOTH', [garment])
        if cloth_mods:
            mod = cloth_mods[0]
            mod.settings.shrink_max = 0.5
            # Enable self-collision
            mod.collision_settings.use_self_collision = True
            mod.collision_settings.self_distance_min = 0.005

        # Add default vertex groups
        Modifikatoren._add_default_vertex_groups(garment)

        # Sync global settings
        Modifikatoren._sync_modifier_settings(context)

        # Triangulate modifier after cloth
        if props.use_triangulate:
            tri = garment.modifiers.get(CLOTH_TRIANGULATION)
            if not tri:
                tri = garment.modifiers.new(name=CLOTH_TRIANGULATION,
                                            type='TRIANGULATE')
                tri.quad_method = 'LONGEST_DIAGONAL'
                tri.keep_custom_normals = True

        # Auto-add collision to body
        body = Vorschausuche.find_body_obj(context)
        if body:
            Modifikatoren._add_collision(context, body)
            # Auto-add armature if body has one (for animation tracking)
            Knochengewichte._add_armature_to_garment(context, garment, body)

        logger.info("Added cloth to: %s", garment.name)

    @staticmethod
    def _nadelgewichte(garment):
        u"""Die Vertexgruppe `pinned` — mit weichem Verlauf nach unten.

        Ein Kleidungsstueck, das nur am Bund festgenaeht ist, rutscht bei
        einer Animation vom Koerper: Die Simulation zieht es nach unten,
        waehrend der Koerper laeuft. Ein Kleidungsstueck, das ueberall
        festhaengt, hat keinen Faltenwurf mehr.

        Deshalb der Verlauf: Am Bund 1.0, dann linear ueber die Hoehe von
        0.80 auf 0.15 hinunter. Oben folgt der Stoff dem Skelett, unten
        darf er schwingen.

        Ohne Nadeln (`hb_pin_indices` leer oder fehlend) bleibt die
        Gruppe leer — dann simuliert alles frei.
        """
        pin_indices = list(garment.data.get('hb_pin_indices', []))
        if PIN_GROUP_NAME not in garment.vertex_groups:
            garment.vertex_groups.new(name=PIN_GROUP_NAME)
        vg = garment.vertex_groups[PIN_GROUP_NAME]
        if not pin_indices:
            return vg

        pin_set = set(pin_indices)
        # Find Z range of pin ring to compute gradient
        pin_zs = [garment.data.vertices[vi].co.z for vi in pin_indices
                  if vi < len(garment.data.vertices)]
        pin_z = max(pin_zs) if pin_zs else 1.0
        all_zs = [v.co.z for v in garment.data.vertices]
        z_min = min(all_zs) if all_zs else 0.0
        z_span = max(pin_z - z_min, 0.01)

        vg.add(pin_indices, 1.0, 'REPLACE')
        # Non-pinned: gradient from pin_z (0.8) down to z_min (0.15)
        for v in garment.data.vertices:
            if v.index in pin_set:
                continue
            t = max(0.0, (v.co.z - z_min) / z_span)  # 0 at bottom, 1 at pin
            vg.add([v.index], 0.15 + t * 0.65, 'REPLACE')
        return vg

    @staticmethod
    def _add_collision(context, body):
        """Add COLLISION modifier to body (idempotent)."""
        if Modifikatorsuche._has_modifier(body, 'COLLISION'):
            return

        with context.temp_override(active_object=body, object=body,
                                   selected_objects=[body],
                                   selected_editable_objects=[body]):
            bpy.ops.object.modifier_add(type='COLLISION')

        if body.collision:
            body.collision.use_normal = True

        Modifikatoren._sync_modifier_settings(context)
        logger.info("Added collision to: %s", body.name)

    @staticmethod
    def _remove_cloth(context, garment):
        """Remove CLOTH + TRIANGULATE modifiers from garment."""
        to_remove = []
        for mod in garment.modifiers:
            if mod.type == 'CLOTH' or mod.name == CLOTH_TRIANGULATION:
                to_remove.append(mod.name)

        for name in to_remove:
            mod = garment.modifiers.get(name)
            if mod:
                garment.modifiers.remove(mod)

        logger.info("Removed cloth from: %s", garment.name)
