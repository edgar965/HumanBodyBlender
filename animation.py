# SPDX-License-Identifier: GPL-3.0-or-later
#
# Animation system for HumanBody addon.
# BVH motion capture retargeting, procedural animations, and animation catalog.

import os
import logging

from .klassenanmeldung import Klassenanmeldung
import bpy

from .rig_teile.rigsuche import Rigsuche
from .charakter.charakterpruefung import Charakterpruefung
from .anim.retargetlauf import Retargetlauf

logger = logging.getLogger(__name__)

from .rigaktionen import Rigaktionen
from .retarget import Rokoko

# Die Bauteile liegen in `anim/`. Hier bleiben die Operatoren und die
# Anmeldung — das, was Blender sieht.
from .anim.katalog import _HUMANBODY_ROOT, _PROC_PREFIX
from .anim.prozedural import Prozedural, _PROCEDURAL_ANIMS
from .anim.viewport import Ansichtsfenster
from .anim.bvhladen import HUMANBODY_OT_load_bvh_native

# Die Bauteile liegen in `anim/`. Hier bleibt, was Blender
# sieht: die Klassen und die Anmeldung.
from .anim.mocapnetweb import HUMANBODY_OT_mocapnet_webui
from .anim.stapelretarget import HUMANBODY_OT_batch_retarget


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

if not os.path.isdir(_HUMANBODY_ROOT):
    _HUMANBODY_ROOT = r"A:\3DTools\HumanBody"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Procedural Animation Generators
#
# Bone axis reference (from Rigify diagnostic):
#   Spine/Head/Neck:  local X=right, Y=up, Z=backward
#   Thigh/Shin:       local X=right, Y=down(bone), Z=forward
#   Upper arm:        complex axes -> use _wrot() for world-space rotations
#   Forearm:          local X ~ vertical -> _deg(-angle,0,0) = elbow flex
#   Foot:             local X=right, Y=backward+down, Z=down
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Walk & Run procedural animations
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Procedural animation catalog: key -> (label, category, generator_func)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class HUMANBODY_OT_load_animation(bpy.types.Operator):
    bl_idname = "humanbody.load_animation"
    bl_label = "Load Animation"
    bl_description = "Load an animation (BVH or procedural)"
    bl_options = {'REGISTER', 'UNDO'}

    bvh_path: bpy.props.StringProperty()
    anim_name: bpy.props.StringProperty()

    def execute(self, context):
        obj, rig = Charakterpruefung.rig_holen(context, self)
        if not rig:
            return {'CANCELLED'}

        Ansichtsfenster._cleanup_old_anim(context, rig)

        # Optimize viewport for smooth playback
        Ansichtsfenster._set_cloth_viewport(False)
        Ansichtsfenster._optimize_viewport(context)

        if self.bvh_path.startswith(_PROC_PREFIX):
            act, f_start, f_end = self._prozedural(context, rig)
        else:
            act, f_start, f_end = self._aus_bvh(context, rig)
        if not act:
            return {'CANCELLED'}

        act.name = f"HB_Anim_{self.anim_name}"
        self._abspielen(context, obj, f_start, f_end)
        self.report({'INFO'}, f"Animation: {self.anim_name}")
        return {'FINISHED'}

    # ------------------------------------------------------------ Bausteine

    def _prozedural(self, context, rig):
        u"""Eine gerechnete Bewegung — ohne Datei, ohne Retarget."""
        proc_key = self.bvh_path[len(_PROC_PREFIX):]
        if proc_key not in _PROCEDURAL_ANIMS:
            self.report({'ERROR'}, f"Unknown procedural: {proc_key}")
            return None, 0, 0
        context.scene.render.fps = 60
        return Prozedural._generate_procedural(rig, proc_key)

    def _aus_bvh(self, context, rig):
        u"""Eine BVH-Datei, ueber den Rokoko-Retarget auf einer Kopie.

        Die Bildrate kommt aus der Datei: Ein mit 30 Bildern je Sekunde
        aufgenommener Gang laeuft in einer 24er-Szene sonst zu langsam,
        ohne dass etwas falsch aussieht.
        """
        if not os.path.isfile(self.bvh_path):
            self.report({'ERROR'}, f"BVH not found: {self.bvh_path}")
            return None, 0, 0

        # Set scene FPS from BVH file
        bvh_fps, _ = Rigaktionen._parse_bvh_info(self.bvh_path)
        context.scene.render.fps = bvh_fps

        act, f_start, f_end = Retargetlauf.holen(
            context, rig, self.bvh_path, "TMP_retarget",
            Rokoko.retarget_rokoko, netze_verstecken=True)
        if act:
            Rigaktionen._assign_action(rig, act)
        else:
            self.report({'ERROR'}, "Retargeting failed")
        return act, f_start, f_end

    def _abspielen(self, context, obj, f_start, f_end):
        u"""Bildbereich setzen, Auswahl zuruecknehmen, Wiedergabe starten.

        Die Geschwindigkeit sitzt in `fps_base`, nicht in `fps`: So
        bleibt die Bildrate der Aufnahme erhalten und nur die Wiedergabe
        wird gedehnt.
        """
        context.scene.frame_start = f_start
        context.scene.frame_end = f_end
        context.scene.frame_set(f_start)

        # Apply speed from UI slider
        speed = getattr(context.scene.humanbody, 'anim_speed', 1.0)
        context.scene.render.fps_base = 1.0 / max(0.1, speed)

        # Restore selection to body mesh
        for o in context.view_layer.objects:
            o.select_set(o == obj)
        context.view_layer.objects.active = obj

        try:
            if f_start <= f_end and not context.screen.is_animation_playing:
                bpy.ops.screen.animation_play()
        # stumm gewollt: Die Wiedergabe zu starten ist Beiwerk — ohne Fenster
        # gibt es keine.
        except Exception:
            pass


class HUMANBODY_OT_stop_animation(bpy.types.Operator):
    bl_idname = "humanbody.stop_animation"
    bl_label = "Stop Animation"
    bl_description = "Stop and remove current animation"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if not Charakterpruefung.ist_charakter(obj):
            return {'CANCELLED'}

        rig = Rigsuche._find_rig(obj)
        if rig:
            Ansichtsfenster._cleanup_old_anim(context, rig)

        # Stop playback
        if context.screen.is_animation_playing:
            bpy.ops.screen.animation_play()

        # Restore viewport settings
        Ansichtsfenster._set_cloth_viewport(True)
        Ansichtsfenster._restore_viewport(context)

        context.scene.frame_set(1)
        self.report({'INFO'}, "Animation stopped")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = (
    HUMANBODY_OT_load_animation,
    HUMANBODY_OT_stop_animation,
    HUMANBODY_OT_load_bvh_native,
    HUMANBODY_OT_batch_retarget,
    HUMANBODY_OT_mocapnet_webui,
)


def register():
    Klassenanmeldung.an(classes)


def unregister():
    Klassenanmeldung.ab(classes)
