# -*- coding: utf-8 -*-
import logging
import contextlib

import bpy
from ..rigaktionen import Rigaktionen
logger = logging.getLogger(__name__)
from .knochenlisten import _CMU_BVH_BONES, _V4_EXTRA_BONES
from .knochenlisten import _MOCAPNET_BVH_BONES
from .knochenlisten import _OPENPOSE_TO_CMU


class Bvhimport:
    u"""Die frueheren Modulfunktionen, gebuendelt."""

    @staticmethod
    def _import_bvh_armature(context, bvh_path):
        """Import BVH as a new armature, return (bvh_rig, f_start, f_end)."""
        bvh_fps, bvh_nframes = Rigaktionen._parse_bvh_info(bvh_path)
        orig = set(context.scene.objects)
        bpy.ops.import_anim.bvh(
            filepath=bvh_path,
            global_scale=1.0,
            frame_start=1,
            use_fps_scale=False,
            use_cyclic=False,
            rotate_mode='NATIVE',
            axis_forward='-Z',
            axis_up='Y',
        )
        bvh_rig = None
        for o in set(context.scene.objects) - orig:
            if o.type == 'ARMATURE':
                bvh_rig = o
                break
        return bvh_rig, 1, max(bvh_nframes, 1)

    @staticmethod
    @contextlib.contextmanager
    def _knochen_bearbeiten(context, rig):
        u"""Im Bearbeitungsmodus des Rigs — danach alles wie vorher.

        ZWEIMAL DASSELBE RITUAL (01.09.2026): `_normalize_openpose_bones`
        und `_filter_bvh_bones` schrieben je sechs Zeilen, um in den
        Bearbeitungsmodus zu kommen, und je zwei, um das aktive Objekt
        zurueckzusetzen.

        WARUM DER UMWEG UEBER DAS AKTIVE OBJEKT: `edit_bones` gibt es
        NUR im Bearbeitungsmodus, und `bpy.ops.object.mode_set` wirkt
        immer auf das aktive Objekt — man kann kein Rig benennen. Also
        muss das BVH-Rig kurz aktiv werden. Was vorher aktiv war, ist
        die Auswahl des Nutzers und gehoert wiederhergestellt.

        `finally` statt gerader Reihenfolge: Bricht die Arbeit an den
        Knochen ab, bliebe Blender sonst im Bearbeitungsmodus stehen —
        und jeder folgende Operator laeuft dort ins Leere.
        """
        vorher = context.view_layer.objects.active
        context.view_layer.objects.active = rig
        rig.select_set(True)
        if context.object and context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.mode_set(mode='EDIT')
        try:
            yield rig.data.edit_bones
        finally:
            bpy.ops.object.mode_set(mode='OBJECT')
            if vorher and vorher.name in bpy.data.objects:
                context.view_layer.objects.active = vorher

    @staticmethod
    def _normalize_openpose_bones(context, bvh_rig):
        """Rename OpenPose-style BVH bones to CMU-style names.

        Also updates FCurve data_paths.
        """
        if 'rShldr' not in bvh_rig.data.bones:
            return False

        renamed = 0
        with Bvhimport._knochen_bearbeiten(context, bvh_rig) as knochen:
            for old_name, new_name in _OPENPOSE_TO_CMU.items():
                eb = knochen.get(old_name)
                if eb:
                    eb.name = new_name
                    renamed += 1

        if bvh_rig.animation_data and bvh_rig.animation_data.action:
            for fc in Rigaktionen._get_action_fcurves(bvh_rig.animation_data.action):
                for old_name, new_name in _OPENPOSE_TO_CMU.items():
                    old_path = f'pose.bones["{old_name}"]'
                    if old_path in fc.data_path:
                        fc.data_path = fc.data_path.replace(old_path,
                                                            f'pose.bones["{new_name}"]')
                        break

        logger.info("normalized %s OpenPose bones → CMU names", renamed)
        return True

    @staticmethod
    def _filter_bvh_bones(context, bvh_rig, is_mocapnet, is_v4=False):
        """Remove unmapped BVH bones to speed up KBS bake.

        Keeps mapped bones + their ancestors (to preserve hierarchy).
        """
        mapped = _MOCAPNET_BVH_BONES if is_mocapnet else _CMU_BVH_BONES
        if is_v4:
            mapped = mapped | _V4_EXTRA_BONES

        keep = set()
        for bname in mapped:
            bone = bvh_rig.data.bones.get(bname)
            while bone:
                keep.add(bone.name)
                bone = bone.parent

        total = len(bvh_rig.data.bones)
        if not keep or len(keep) >= total:
            return

        with Bvhimport._knochen_bearbeiten(context, bvh_rig) as knochen:
            for eb in list(knochen):
                if eb.name not in keep:
                    knochen.remove(eb)

        remaining = set(b.name for b in bvh_rig.data.bones)
        if bvh_rig.animation_data and bvh_rig.animation_data.action:
            fcurves = Rigaktionen._get_action_fcurves(bvh_rig.animation_data.action)
            to_remove = []
            for fc in fcurves:
                if 'pose.bones["' in fc.data_path:
                    bname = fc.data_path.split('pose.bones["')[1].split('"]')[0]
                    if bname not in remaining:
                        to_remove.append(fc)
            for fc in to_remove:
                try:
                    fcurves.remove(fc)
                # stumm gewollt: Die Kurve kann bereits entfernt sein, wenn zwei
                # Filter greifen. In einer Schleife ueber hunderte Kurven.
                except Exception:
                    pass

        removed = total - len(bvh_rig.data.bones)
        logger.info("filtered BVH: %s -> %s bones (%s removed)",
                    total, len(bvh_rig.data.bones), removed)

    @staticmethod
    def _scale_to_match(bvh_rig, ziel_rig):
        """Scale bvh_rig so its height matches ziel_rig."""
        th = Rigaktionen._rig_height(ziel_rig)
        sh = Rigaktionen._rig_height(bvh_rig)
        if sh > 0.001:
            s = th / sh
            bvh_rig.scale = (s, s, s)
