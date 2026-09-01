# -*- coding: utf-8 -*-
import os
import logging
import bpy
from ..rig import _find_rig
from ..rigaktionen import _parse_bvh_info, _assign_action
from ..retarget import retarget_rokoko
from ..retarget_teile.kbs import retarget_kbs
from ..retarget_teile.bvhimport import (
    _import_bvh_armature, _normalize_openpose_bones,
    _filter_bvh_bones, _scale_to_match,
)
logger = logging.getLogger(__name__)
from .viewport import _cleanup_old_anim
from .zwischenspeicher import _load_cached_action
from .viewport import _optimize_viewport
from .zwischenspeicher import _save_action_cache
from .viewport import _set_cloth_viewport


class HUMANBODY_OT_load_bvh_native(bpy.types.Operator):
    bl_idname = "humanbody.load_bvh_native"
    bl_label = "BVH Compare"
    bl_description = (
        "3-way compare: BVH skeleton | Rokoko | KBS retarget"
    )
    bl_options = {'REGISTER', 'UNDO'}

    bvh_path: bpy.props.StringProperty()
    anim_name: bpy.props.StringProperty()

    def execute(self, context):
        if not os.path.isfile(self.bvh_path):
            self.report({'ERROR'}, f"BVH not found: {self.bvh_path}")
            return {'CANCELLED'}

        obj = context.active_object
        if not obj or not obj.data.get("humanbody"):
            self.report({'ERROR'}, "Select a HumanBody character")
            return {'CANCELLED'}
        rig = _find_rig(obj)
        if not rig:
            self.report({'ERROR'}, "Add a rig first")
            return {'CANCELLED'}

        # --- Parse BVH file info ---
        bvh_fps, bvh_nframes = _parse_bvh_info(self.bvh_path)

        context.scene.render.fps = bvh_fps
        context.scene.render.fps_base = 1.0

        # --- Cleanup previous previews ---
        for o in list(bpy.data.objects):
            if (o.name.startswith("BVH_Preview")
                    or o.name.startswith("Rig_Preview")
                    or o.name.startswith("Preview_")
                    or o.name.startswith("KBS_Preview")
                    or o.name.startswith("KBS_")
                    or o.name.startswith("ROK_Preview")
                    or o.name.startswith("ROK_")
                    or o.name.startswith("ROK46_Preview")
                    or o.name.startswith("ROK46_")
                    or o.name.startswith("RTEST_Preview")
                    or o.name.startswith("RTEST_")
                    or o.name.startswith("TMP_")):
                bpy.data.objects.remove(o, do_unlink=True)

        _cleanup_old_anim(context, rig)
        _set_cloth_viewport(False)
        _optimize_viewport(context)

        # ---- Helper: deep-copy rig with mesh children ----
        def _copy_rig(src_rig, name_prefix):
            try:
                rc = src_rig.copy()
                rc.data = src_rig.data.copy()
                rc.name = f"{name_prefix}_Preview"
                context.collection.objects.link(rc)
                for pb in rc.pose.bones:
                    for c in pb.constraints:
                        if hasattr(c, 'target') and c.target == src_rig:
                            c.target = rc
                if rc.data.animation_data:
                    for drv_fc in rc.data.animation_data.drivers:
                        for var in drv_fc.driver.variables:
                            for tgt in var.targets:
                                if tgt.id == src_rig:
                                    tgt.id = rc
                for child in list(src_rig.children):
                    if child.type != 'MESH':
                        continue
                    mc = child.copy()
                    mc.data = child.data.copy()
                    mc.name = f"{name_prefix}_{child.name}"
                    context.collection.objects.link(mc)
                    mc.parent = rc
                    mc.parent_type = child.parent_type
                    mc.parent_bone = child.parent_bone
                    mc.matrix_parent_inverse = child.matrix_parent_inverse.copy()
                    for mod in mc.modifiers:
                        if mod.type == 'ARMATURE' and mod.object == src_rig:
                            mod.object = rc
                        if mod.type == 'CLOTH':
                            mod.show_viewport = False
                            mod.show_render = False
                return rc
            except Exception as e:
                logger.exception("Retarget fehlgeschlagen")
                logger.warning("Rig copy '%s' failed: %s", name_prefix, e)
                return None

        def _style_preview_rig(rc):
            if not rc or rc.name not in bpy.data.objects:
                return
            rc.show_in_front = True
            rc.data.display_type = 'STICK'
            rc.data.show_bone_custom_shapes = False
            rc.data.show_bone_colors = False
            for bc_copy in rc.data.collections:
                bc_orig = rig.data.collections.get(bc_copy.name)
                bc_copy.is_visible = bc_orig.is_visible if bc_orig else False

        def _align_rig(rc, ground_z, center_root_pos):
            if not rc or rc.name not in bpy.data.objects:
                return
            for fname in ("foot_fk.L", "ORG-foot.L", "DEF-foot.L"):
                pb = rc.pose.bones.get(fname)
                if pb:
                    foot = (rc.matrix_world @ pb.matrix).to_translation()
                    rc.location.z -= (foot.z - ground_z)
                    break
            root_pb = rc.pose.bones.get("root")
            if root_pb:
                rpos = (rc.matrix_world @ root_pb.matrix).to_translation()
                rc.location.y -= (rpos.y - center_root_pos.y)

        # ============================================================
        # PHASE 1: Retargets on temp copies (no BVH_Preview yet)
        # ============================================================

        # ---- Rokoko retarget → action for main rig ----
        act, f_start, f_end = _load_cached_action(rig, self.bvh_path)
        if not act:
            rig_tmp = rig.copy()
            rig_tmp.data = rig.data.copy()
            rig_tmp.name = "TMP_rok_retarget"
            context.collection.objects.link(rig_tmp)
            try:
                if rig_tmp.animation_data:
                    rig_tmp.animation_data.action = None
                act, f_start, f_end = retarget_rokoko(
                    context, rig_tmp, self.bvh_path)
                if act:
                    _save_action_cache(self.bvh_path, act)
            except Exception as e:
                logger.exception("Retarget fehlgeschlagen")
                self.report({'WARNING'}, f"Rokoko retarget failed: {e}")
                act = None
            finally:
                try:
                    bpy.data.objects.remove(rig_tmp, do_unlink=True)
                # stumm gewollt: Aufraeumen im finally. Ein Fehler hier wuerde
                # den echten Fehler darueber verdecken.
                except Exception:
                    pass

        if act:
            act.name = f"HB_Anim_{self.anim_name}"
            _assign_action(rig, act)

        # ---- KBS retarget → action for KBS copy ----
        act_kbs = None
        act_kbs, _, _ = _load_cached_action(rig, self.bvh_path, "HB_KBS", "_kbs")
        if act:
            _assign_action(rig, act)
        if not act_kbs:
            rig_tmp2 = rig.copy()
            rig_tmp2.data = rig.data.copy()
            rig_tmp2.name = "TMP_kbs_retarget"
            context.collection.objects.link(rig_tmp2)
            try:
                if rig_tmp2.animation_data:
                    rig_tmp2.animation_data.action = None
                act_kbs, _, _ = retarget_kbs(
                    context, rig_tmp2, self.bvh_path)
                if act_kbs:
                    _save_action_cache(self.bvh_path, act_kbs, "_kbs")
            except Exception as e:
                logger.exception("Retarget fehlgeschlagen")
                logger.warning("KBS retarget failed: %s", e)
            finally:
                try:
                    bpy.data.objects.remove(rig_tmp2, do_unlink=True)
                # stumm gewollt: Aufraeumen im finally, siehe oben. Die
                # Ursache steht schon im Log.
                except Exception:
                    pass

        if act_kbs:
            act_kbs.name = f"HB_KBS_{self.anim_name}"

        # ============================================================
        # PHASE 2: Display setup (retargets done, scene is clean)
        # ============================================================

        # ---- LEFT: BVH native skeleton (filtered to mapped bones) ----
        bvh_rig, _, _ = _import_bvh_armature(context, self.bvh_path)
        if bvh_rig:
            is_mocapnet = 'hip' in bvh_rig.data.bones
            is_v4_preview = is_mocapnet and '__jaw' in bvh_rig.data.bones
            if is_mocapnet:
                _normalize_openpose_bones(context, bvh_rig)
            _filter_bvh_bones(context, bvh_rig, is_mocapnet, is_v4=is_v4_preview)
            bvh_rig.name = "BVH_Preview"
            bvh_rig.show_in_front = True
            _scale_to_match(bvh_rig, rig)
            bvh_rig.location.x = -2.0
            bvh_rig.data.display_type = 'STICK'

        # ---- CENTER: Main rig with Rokoko action ----
        rig.location.x = 0.0

        # ---- RIGHT: KBS copy with KBS action ----
        rig_kbs = _copy_rig(rig, "KBS")
        if rig_kbs:
            rig_kbs.location.x = 2.0
            if act_kbs:
                _assign_action(rig_kbs, act_kbs)

        # ---- Align all models at frame 1 ----
        bpy.context.scene.frame_set(1)
        bpy.context.view_layer.update()

        # Use BVH hips Y for depth alignment
        if bvh_rig:
            hips_name = "hip" if "hip" in bvh_rig.pose.bones else "Hips"
            bvh_hip = (bvh_rig.matrix_world
                       @ bvh_rig.pose.bones[hips_name].matrix).to_translation()
            rig_root = (rig.matrix_world
                        @ rig.pose.bones["root"].matrix).to_translation()
            rig.location.y -= (rig_root.y - bvh_hip.y)

        # Ground level from main rig foot
        bpy.context.view_layer.update()
        ground_z = 0.0
        for fname in ("foot_fk.L", "ORG-foot.L", "DEF-foot.L"):
            pb = rig.pose.bones.get(fname)
            if pb:
                ground_z = (rig.matrix_world @ pb.matrix).to_translation().z
                break
        center_root = (rig.matrix_world
                       @ rig.pose.bones["root"].matrix).to_translation()

        # Align BVH skeleton height
        if bvh_rig:
            for bname in ("LeftFoot", "lFoot", "foot.L"):
                pb = bvh_rig.pose.bones.get(bname)
                if pb:
                    bvh_foot_z = (bvh_rig.matrix_world @ pb.matrix).to_translation().z
                    bvh_rig.location.z -= (bvh_foot_z - ground_z)
                    break

        _align_rig(rig_kbs, ground_z, center_root)

        # ---- Frame range and playback ----
        context.scene.frame_start = 1
        context.scene.frame_end = max(bvh_nframes, f_end if act else 1)
        context.scene.frame_set(1)

        speed = getattr(context.scene.humanbody, 'anim_speed', 1.0)
        context.scene.render.fps_base = 1.0 / max(0.1, speed)

        # Restore selection to body
        for o in context.view_layer.objects:
            o.select_set(o == obj)
        context.view_layer.objects.active = obj

        try:
            bpy.ops.screen.animation_play()
        # stumm gewollt: Die Wiedergabe zu starten ist Beiwerk. Ist kein
        # Fenster da (Hintergrundlauf), gibt es nichts zu starten.
        except Exception:
            pass

        fname = os.path.basename(self.bvh_path)
        self.report({'INFO'},
                     f"3-way: BVH | Rokoko | KBS — {fname}")
        return {'FINISHED'}
