# SPDX-License-Identifier: GPL-3.0-or-later
#
# Rig and pose system for HumanBody addon.
# Pre-generated AutoRig loading, pose loading.

import os
import logging

from .klassenanmeldung import Klassenanmeldung
import bpy

# Die Bauteile liegen in `rig_teile/`. Hier bleibt, was Blender
# sieht: die Klassen und die Anmeldung.
from .rig_teile.gesichtsknochen import Gesichtsknochen
from .rig_teile.gewichte import Gewichte
from .rig_teile.posenoperatoren import (
    HUMANBODY_OT_clear_pose, HUMANBODY_OT_load_pose,
)
from .rig_teile.rigpfade import Rigpfade

# Die Bauteile liegen in `rig_teile/`. Hier bleibt, was Blender
# sieht: die Klassen und die Anmeldung.
# DIE OEFFENTLICHE SCHNITTSTELLE: `animation.py`, `anim/bvhladen.py`,
# `ui_teile/zeichnen_weitere.py` und `haare/frisurladen.py` holen
# diese beiden aus `rig`. Sie sind die Weiterleitung.
from .charakter.charakterpruefung import Charakterpruefung
from .rig_teile.rigsuche import Rigsuche

# Die Bauteile liegen in `rig_teile/`. Hier bleibt, was Blender
# sieht: die Klassen und die Anmeldung.
from .rig_teile.rigentfernen import HUMANBODY_OT_remove_rig


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# NPZ utilities
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Rig setup helpers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Shared helper: find rig for a HumanBody object
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Pose system
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class HUMANBODY_OT_add_rig(bpy.types.Operator):
    bl_idname = "humanbody.add_rig"
    bl_label = "Add Rig"
    bl_description = "Add Rigify armature rig to the character"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = Charakterpruefung.charakter(
            context, self, "Select a HumanBody character first")
        if not obj:
            return {'CANCELLED'}

        if Rigsuche._find_rig(obj):
            self.report({'WARNING'}, "Rig already exists. Remove first.")
            return {'CANCELLED'}

        autorig_blend = Rigpfade._get_autorig_blend_path()
        if not os.path.isfile(autorig_blend):
            self.report({'ERROR'}, f"AutoRig file not found: {autorig_blend}")
            return {'CANCELLED'}

        rig = self._rig_einlesen(context, autorig_blend)
        if not rig:
            self.report({'ERROR'}, "HumanBody_Rig not found in autorig.blend")
            return {'CANCELLED'}

        self._knochen_einrichten(obj, rig)
        self._netz_anbinden(context, obj, rig)

        def_bones = sum(1 for b in rig.data.bones if b.name.startswith("DEF-"))
        self.report({'INFO'},
                    f"Rig added ({len(rig.data.bones)} bones, "
                    f"{def_bones} deformation)")
        return {'FINISHED'}

    # ------------------------------------------------------------ Bausteine

    @staticmethod
    def _rig_einlesen(context, autorig_blend):
        u"""Das fertige Rigify-Rig aus der mitgelieferten .blend holen.

        Blender haengt bei einem Namenskonflikt `.001` an. Deshalb wird
        VOR dem Laden gemerkt, was schon da ist, und danach die
        Differenz gesucht — auf `bpy.data.objects["HumanBody_Rig"]` zu
        vertrauen holte sonst ein altes Rig statt des neuen.
        """
        existing = set(bpy.data.objects.keys())
        with bpy.data.libraries.load(autorig_blend, link=False) as (data_from, data_to):
            data_to.objects = ["HumanBody_Rig"]

        # Find the newly imported rig (handles name conflicts)
        rig = None
        for o in bpy.data.objects:
            if o.name not in existing and o.type == 'ARMATURE':
                rig = o
                break
        if not rig:
            rig = bpy.data.objects.get("HumanBody_Rig")
        if not rig:
            return None

        context.collection.objects.link(rig)
        rig.name = "HumanBody_Rig"
        rig["humanbody_rig"] = True
        return rig

    @staticmethod
    def _knochen_einrichten(obj, rig):
        u"""Gewichte einlesen, Gesichtsknochen und FK-Modus einstellen.

        Die Gliedmassen kommen im IK-Modus aus der Datei; die
        Animationen des Projekts sind aber FK. `IK_FK = 1.0` heisst
        „ganz FK" — ohne das laufen alle Retargets ins Leere, weil die
        FK-Knochen zwar gesetzt, aber nicht ausgewertet werden.
        """
        # Import bone weights from NPZ
        weights_npz = Rigpfade._get_weights_npz_path()
        if os.path.isfile(weights_npz):
            n = Gewichte._import_weights(obj, weights_npz)
            logger.info("Imported %d bone weight groups from NPZ", n)

        # Enable deformation on MCH/ORG bones that carry NPZ weights
        Gesichtsknochen._enable_face_deform_bones(rig)

        # Switch limbs to FK mode (default is IK)
        for pname in ("upper_arm_parent.L", "upper_arm_parent.R",
                      "thigh_parent.L", "thigh_parent.R"):
            pb = rig.pose.bones.get(pname)
            if pb and "IK_FK" in pb:
                pb["IK_FK"] = 1.0

        # Set Rigify properties for correct FK pose behaviour
        Gesichtsknochen._setup_rigify_properties(rig)

    @staticmethod
    def _netz_anbinden(context, obj, rig):
        u"""Netz ans Rig haengen und den Modifikator nach vorn schieben.

        Die Reihenfolge der Modifikatoren entscheidet: Wird erst
        unterteilt und dann verformt, rechnet Blender die Verformung auf
        dem feinen Netz — vielfach teurer, und an den Gelenken sieht es
        anders aus. Deshalb wandert ARMATURE ganz nach oben.
        """
        obj.parent = rig
        obj.matrix_parent_inverse = rig.matrix_world.inverted()

        mod = obj.modifiers.new("HumanBody_Rig", "ARMATURE")
        mod.use_vertex_groups = True
        mod.use_deform_preserve_volume = True
        mod.object = rig

        # Place ARMATURE modifier first (before subdivision etc.)
        with context.temp_override(object=obj):
            while obj.modifiers.find(mod.name) > 0:
                bpy.ops.object.modifier_move_up(modifier=mod.name)

        # Restore selection
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        context.view_layer.objects.active = obj


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = (
    HUMANBODY_OT_add_rig,
    HUMANBODY_OT_remove_rig,
    HUMANBODY_OT_load_pose,
    HUMANBODY_OT_clear_pose,
)


def register():
    Klassenanmeldung.an(classes)


def unregister():
    Klassenanmeldung.ab(classes)
