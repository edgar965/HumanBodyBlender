# -*- coding: utf-8 -*-
import logging
import bpy
logger = logging.getLogger(__name__)
from .modifikatorsuche import Modifikatorsuche


class Knochengewichte:
    u"""Die frueheren Modulfunktionen, gebuendelt."""

    @staticmethod
    def _find_body_armature(body):
        """Return the armature object driving *body*, or None."""
        if body.parent and body.parent.type == 'ARMATURE':
            return body.parent
        for mod in body.modifiers:
            if mod.type == 'ARMATURE' and mod.object:
                return mod.object
        return None

    @staticmethod
    def _transfer_bone_weights(garment, body, only_indices=None):
        """Transfer vertex-group weights from *body* to *garment* via KDTree.

        For each garment vertex (or only those in *only_indices*), finds the
        nearest body vertex (evaluated mesh) and copies all bone-weight groups.

        Transferring only to pinned vertices prevents the armature from
        deforming cloth-simulated areas (e.g., skirt below waist).
        """
        from mathutils.kdtree import KDTree

        # Build KDTree from ORIGINAL body vertices so indices match
        # body.data.vertices for weight lookup.  The evaluated mesh may have
        # more vertices (Subdivision, etc.) causing index mismatches.
        mat_body = body.matrix_world
        n_body = len(body.data.vertices)
        kd = KDTree(n_body)
        for i, v in enumerate(body.data.vertices):
            kd.insert(mat_body @ v.co, i)
        kd.balance()

        # Map body vertex group indices to names
        body_groups = {vg.index: vg.name for vg in body.vertex_groups}

        # Create matching vertex groups on garment
        for _, name in body_groups.items():
            if name not in garment.vertex_groups:
                garment.vertex_groups.new(name=name)

        garment_groups = {vg.name: vg for vg in garment.vertex_groups}
        mat_garment = garment.matrix_world

        # Determine which garment vertices to process
        if only_indices is not None:
            target_set = set(only_indices)
        else:
            target_set = None

        # For each target garment vertex, copy weights from nearest body vertex
        for gv in garment.data.vertices:
            if target_set is not None and gv.index not in target_set:
                continue
            gv_world = mat_garment @ gv.co
            _, body_vi, _ = kd.find(gv_world)

            body_vert = body.data.vertices[body_vi]
            for vge in body_vert.groups:
                group_name = body_groups.get(vge.group)
                if group_name and group_name in garment_groups:
                    garment_groups[group_name].add([gv.index], vge.weight, 'REPLACE')

        n_transferred = len(target_set) if target_set else len(garment.data.vertices)
        logger.info("Transferred bone weights to %d/%d verts on '%s'",
                    n_transferred, len(garment.data.vertices), garment.name)

    @staticmethod
    def _add_armature_to_garment(context, garment, body):
        """Copy the body's armature setup to the garment so it follows animation.

        Adds an ARMATURE modifier (before Cloth) and transfers bone weights
        to all vertices.  The cloth sim's pin group controls which vertices
        are physically simulated vs armature-only.
        """
        rig = Knochengewichte._find_body_armature(body)
        if rig is None:
            return

        # Already has an armature modifier → skip
        if Modifikatorsuche._has_modifier(garment, 'ARMATURE'):
            return

        # Parent garment to armature (same as body)
        garment.parent = rig
        garment.matrix_parent_inverse = rig.matrix_world.inverted()

        # Add ARMATURE modifier
        arm_mod = garment.modifiers.new("HumanBody_Rig", "ARMATURE")
        arm_mod.use_vertex_groups = True
        arm_mod.use_deform_preserve_volume = True
        arm_mod.object = rig

        # Move armature modifier to first position (before cloth, solidify, etc.)
        with context.temp_override(object=garment):
            bpy.ops.object.modifier_move_to_index(modifier=arm_mod.name, index=0)

        # Transfer bone weights to ALL vertices
        Knochengewichte._transfer_bone_weights(garment, body)
