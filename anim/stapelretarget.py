# -*- coding: utf-8 -*-
import os
import logging
from ..charakter.charakterpruefung import Charakterpruefung
import bpy
from ..retarget_teile.kbs import Kbsanbindung
from ..anim.katalog import Katalog, _PROC_PREFIX
from ..anim.zwischenspeicher import Aktionsspeicher
from ..anim.viewport import Ansichtsfenster
logger = logging.getLogger(__name__)


class HUMANBODY_OT_batch_retarget(bpy.types.Operator):
    bl_idname = "humanbody.batch_retarget"
    bl_label = "Pre-cache All Animations"
    bl_description = "Retarget all BVH animations and cache the results for instant playback"
    bl_options = {'REGISTER'}

    def execute(self, context):
        obj, rig = Charakterpruefung.rig_holen(context, self)
        if not rig:
            return {'CANCELLED'}

        anims = Katalog._list_animations()
        cache_dir = Aktionsspeicher._get_cache_dir()
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
                Ansichtsfenster._cleanup_old_anim(context, rig)
                Ansichtsfenster._hide_meshes_for_retarget(rig)
                try:
                    act, _, _ = Kbsanbindung.retarget_kbs(context, rig, path)
                    Aktionsspeicher._save_action_cache(path, act)
                    retargeted += 1
                except Exception as e:
                    logger.warning("Batch cache failed for %s: %s", stem, e)
                    failed += 1
                finally:
                    Ansichtsfenster._show_meshes_after_retarget(rig)

        Ansichtsfenster._cleanup_old_anim(context, rig)
        msg = f"Cached {retargeted} new, {cached} already cached"
        if failed:
            msg += f", {failed} failed"
        self.report({'INFO'}, msg)
        return {'FINISHED'}
