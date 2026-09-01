# SPDX-License-Identifier: GPL-3.0-or-later
#
# Animation system for HumanBody addon.
# BVH motion capture retargeting, procedural animations, and animation catalog.

import os
import logging

import bpy

from .rig import _find_rig

from .pfade import Projektpfade
logger = logging.getLogger(__name__)

from .rigaktionen import _parse_bvh_info, _assign_action
from .retarget import retarget_rokoko
from .retarget_teile.kbs import retarget_kbs

# Die Bauteile liegen in `anim/`. Hier bleiben die Operatoren und die
# Anmeldung — das, was Blender sieht.
from .anim.katalog import (
    _HUMANBODY_ROOT, _ANIM_CATEGORIES, _PROC_PREFIX, _list_animations,
)
from .anim.prozedural import _PROCEDURAL_ANIMS, _generate_procedural
from .anim.zwischenspeicher import (
    _get_cache_dir, _load_cached_action, _save_action_cache,
)
from .anim.viewport import (
    _set_cloth_viewport, _hide_meshes_for_retarget,
    _show_meshes_after_retarget, _optimize_viewport, _restore_viewport,
    _cleanup_old_anim,
)
from .anim.bvhladen import HUMANBODY_OT_load_bvh_native


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
        obj = context.active_object
        if not obj or not obj.data.get("humanbody"):
            self.report({'ERROR'}, "Select a HumanBody character")
            return {'CANCELLED'}

        rig = _find_rig(obj)
        if not rig:
            self.report({'ERROR'}, "Add a rig first")
            return {'CANCELLED'}

        _cleanup_old_anim(context, rig)

        # Optimize viewport for smooth playback
        _set_cloth_viewport(False)
        _optimize_viewport(context)

        if self.bvh_path.startswith(_PROC_PREFIX):
            # Procedural animation — instant generation
            proc_key = self.bvh_path[len(_PROC_PREFIX):]
            if proc_key not in _PROCEDURAL_ANIMS:
                self.report({'ERROR'}, f"Unknown procedural: {proc_key}")
                return {'CANCELLED'}
            context.scene.render.fps = 60
            act, f_start, f_end = _generate_procedural(rig, proc_key)
        else:
            # BVH animation
            if not os.path.isfile(self.bvh_path):
                self.report({'ERROR'}, f"BVH not found: {self.bvh_path}")
                return {'CANCELLED'}

            # Set scene FPS from BVH file
            bvh_fps, _ = _parse_bvh_info(self.bvh_path)
            context.scene.render.fps = bvh_fps

            # Try cache first
            act, f_start, f_end = _load_cached_action(rig, self.bvh_path)
            if not act:
                # KBS retarget on temp copy (same pattern as test button)
                rig_tmp = rig.copy()
                rig_tmp.data = rig.data.copy()
                rig_tmp.name = "TMP_retarget"
                context.collection.objects.link(rig_tmp)
                _hide_meshes_for_retarget(rig_tmp)
                try:
                    if rig_tmp.animation_data:
                        rig_tmp.animation_data.action = None
                    act, f_start, f_end = retarget_rokoko(
                        context, rig_tmp, self.bvh_path)
                    if act:
                        _assign_action(rig, act)
                        _save_action_cache(self.bvh_path, act)
                except Exception as e:
                    logger.exception("Retarget fehlgeschlagen")
                    self.report({'ERROR'}, f"Retargeting failed: {e}")
                finally:
                    _show_meshes_after_retarget(rig_tmp)
                    if rig_tmp.name in bpy.data.objects:
                        bpy.data.objects.remove(rig_tmp, do_unlink=True)
                if not act:
                    return {'CANCELLED'}

        act.name = f"HB_Anim_{self.anim_name}"
        total = f_end - f_start + 1
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
            if 0 < total and not context.screen.is_animation_playing:
                bpy.ops.screen.animation_play()
        # stumm gewollt: Die Wiedergabe zu starten ist Beiwerk — ohne Fenster
        # gibt es keine.
        except Exception:
            pass

        self.report({'INFO'}, f"Animation: {self.anim_name}")
        return {'FINISHED'}


class HUMANBODY_OT_stop_animation(bpy.types.Operator):
    bl_idname = "humanbody.stop_animation"
    bl_label = "Stop Animation"
    bl_description = "Stop and remove current animation"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if not obj or not obj.data.get("humanbody"):
            return {'CANCELLED'}

        rig = _find_rig(obj)
        if rig:
            _cleanup_old_anim(context, rig)

        # Stop playback
        if context.screen.is_animation_playing:
            bpy.ops.screen.animation_play()

        # Restore viewport settings
        _set_cloth_viewport(True)
        _restore_viewport(context)

        context.scene.frame_set(1)
        self.report({'INFO'}, "Animation stopped")
        return {'FINISHED'}


class HUMANBODY_OT_batch_retarget(bpy.types.Operator):
    bl_idname = "humanbody.batch_retarget"
    bl_label = "Pre-cache All Animations"
    bl_description = "Retarget all BVH animations and cache the results for instant playback"
    bl_options = {'REGISTER'}

    def execute(self, context):
        obj = context.active_object
        if not obj or not obj.data.get("humanbody"):
            self.report({'ERROR'}, "Select a HumanBody character")
            return {'CANCELLED'}
        rig = _find_rig(obj)
        if not rig:
            self.report({'ERROR'}, "Add a rig first")
            return {'CANCELLED'}

        anims = _list_animations()
        cache_dir = _get_cache_dir()
        cached, retargeted, failed = 0, 0, 0

        for cat_name, items in anims.items():
            for label, path in items:
                if path.startswith(_PROC_PREFIX):
                    continue
                stem = os.path.splitext(os.path.basename(path))[0]
                cache_path = os.path.join(cache_dir, f"{stem}.blend")
                if os.path.isfile(cache_path):
                    cached += 1
                    continue
                _cleanup_old_anim(context, rig)
                _hide_meshes_for_retarget(rig)
                try:
                    act, _, _ = retarget_kbs(context, rig, path)
                    _save_action_cache(path, act)
                    retargeted += 1
                except Exception as e:
                    logger.warning("Batch cache failed for %s: %s", stem, e)
                    failed += 1
                finally:
                    _show_meshes_after_retarget(rig)

        _cleanup_old_anim(context, rig)
        msg = f"Cached {retargeted} new, {cached} already cached"
        if failed:
            msg += f", {failed} failed"
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class HUMANBODY_OT_mocapnet_webui(bpy.types.Operator):
    bl_idname = "humanbody.mocapnet_webui"
    bl_label = "MocapNET Web-UI"
    bl_description = "Start MocapNET Django server and open web UI for video-to-BVH processing"
    bl_options = {'REGISTER'}

    _WEBAPP_DIR = str(Projektpfade.webapp())
    _PORT = 8081

    def execute(self, context):
        import subprocess
        import webbrowser
        import socket

        # Check if server is already running
        running = False
        try:
            with socket.create_connection(("127.0.0.1", self._PORT), timeout=1):
                running = True
        # stumm gewollt: Genau das ist die Antwort: Wer nicht annimmt, laeuft
        # nicht. Ein Log je Pruefung waere Rauschen.
        except (ConnectionRefusedError, OSError):
            pass

        if not running:
            manage_py = os.path.join(self._WEBAPP_DIR, "manage.py")
            if not os.path.isfile(manage_py):
                self.report({'ERROR'}, f"Django project not found at {self._WEBAPP_DIR}")
                return {'CANCELLED'}
            subprocess.Popen(
                ["python", manage_py, "runserver", str(self._PORT)],
                cwd=self._WEBAPP_DIR,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self.report({'INFO'}, f"MocapNET server started on port {self._PORT}")
        else:
            self.report({'INFO'}, "MocapNET server already running")

        webbrowser.open(f"http://127.0.0.1:{self._PORT}/")
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
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
