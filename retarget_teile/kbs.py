# -*- coding: utf-8 -*-
u"""Retarget ueber die KBS-DEV-Erweiterung — zwei Durchgaenge.

AUFGETEILT (01.09.2026)
=======================
`_kbs_run_pass` war 116 Zeilen, `retarget_kbs` 124. Zwei Drittel davon
waren Tabellen und Kurvenarbeit; beides liegt jetzt daneben:

    kbs_knochenplan.py   welcher BVH-Knochen welchem Rigify-Knochen
                         entspricht (MocapNET, CMU, Rigify)
    kbs_kurven.py        Ortsversatz und Kopfdrehung nachtraeglich nullen

Uebrig bleibt der Ablauf — und der ist der Grund fuer diese Datei:
KBS kann Rumpf und Glieder nicht gleichzeitig richtig, also laeuft es
zweimal und die Rumpfkurven aus dem ersten Durchgang werden in den
zweiten hineinkopiert.
"""
import logging
import bpy
from mathutils import Quaternion, Vector
from ..rigaktionen import Rigaktionen
logger = logging.getLogger(__name__)
from .knochenlisten import _SPINE_MERGE_BONES
from .fcurves import Fcurves
from .bvhimport import Bvhimport
from .kbs_knochenplan import Kbsknochenplan
from .kbs_kurven import Kbskurven


class Kbsanbindung:
    u"""Der zweistufige Retarget ueber die KBS-Erweiterung."""

    @staticmethod
    def _reset_rig_for_kbs(context, rig, orig_bone_names):
        """Reset rig between two KBS passes: remove action, pose, extra bones."""
        if rig.animation_data and rig.animation_data.action:
            act = rig.animation_data.action
            rig.animation_data.action = None
            if act.users == 0:
                bpy.data.actions.remove(act)

        for pb in rig.pose.bones:
            pb.rotation_quaternion = Quaternion()
            pb.location = Vector()
        context.view_layer.update()

        Kbsanbindung._zusatzknochen_weg(context, rig, orig_bone_names)

    @staticmethod
    def _zusatzknochen_weg(context, rig, orig_bone_names):
        u"""Die Hilfsknochen entfernen, die KBS ins Rig gehaengt hat.

        Zurueck kommen ihre Namen — die Anzahl steht im Protokoll.
        """
        context.view_layer.objects.active = rig
        rig.select_set(True)
        bpy.ops.object.mode_set(mode='EDIT')
        zusatz = [eb.name for eb in rig.data.edit_bones
                  if eb.name not in orig_bone_names]
        for name in zusatz:
            eb = rig.data.edit_bones.get(name)
            if eb:
                rig.data.edit_bones.remove(eb)
        bpy.ops.object.mode_set(mode='OBJECT')
        context.view_layer.update()
        return zusatz

    @staticmethod
    def _kbs_run_pass(context, rig, bvh_path, is_mocapnet, match_transform,
                      bvh_rig=None, keep_bvh=False):
        """Run a single KBS retarget pass with specified match_transform.

        If bvh_rig is provided, reuses it instead of importing a new BVH.
        If keep_bvh is True, does not delete the BVH rig after bake.
        Returns (action, f_start, f_end).
        """
        if bvh_rig is None:
            bvh_rig, f_start, f_end = Bvhimport._import_bvh_armature(context, bvh_path)
            if not bvh_rig:
                raise RuntimeError("BVH import produced no armature")
            Bvhimport._scale_to_match(bvh_rig, rig)
        else:
            _, bvh_nframes = Rigaktionen._parse_bvh_info(bvh_path)
            f_start, f_end = 1, max(bvh_nframes, 1)

        if context.object and context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        try:
            Kbsknochenplan.setzen(bvh_rig.data.retarget_retarget,
                                  Kbsknochenplan.quelle(is_mocapnet))
            Kbsknochenplan.setzen(rig.data.retarget_retarget,
                                  Kbsknochenplan.RIGIFY)

            # Context: BVH active, Rigify selected
            for o in list(context.selected_objects):
                o.select_set(False)
            rig.select_set(True)
            bvh_rig.select_set(True)
            context.view_layer.objects.active = bvh_rig
            context.view_layer.update()

            Kbsanbindung._backen(context, rig, bvh_rig, match_transform)

            if rig.animation_data:
                rig.animation_data.use_nla = False
            bpy.ops.object.mode_set(mode='OBJECT')

        finally:
            try:
                if context.object and context.object.mode != 'OBJECT':
                    bpy.ops.object.mode_set(mode='OBJECT')
            # stumm gewollt: Aufraeumen im finally: in den Objektmodus zurueck.
            # Steht kein Objekt bereit, ist nichts umzuschalten.
            except Exception:
                pass
            if not keep_bvh and bvh_rig and bvh_rig.name in bpy.data.objects:
                bpy.data.objects.remove(bvh_rig, do_unlink=True)

        act = rig.animation_data.action if rig.animation_data else None
        return act, f_start, f_end

    @staticmethod
    def _backen(context, rig, bvh_rig, match_transform):
        u"""Bindet das Rig an das BVH-Rig und backt die Bewegung.

        ZWEI ANLAEUFE: Die KBS-Operatoren verlangen einen Kontext, den
        `temp_override` mit Objekten allein nicht immer herstellt. Wirft
        der erste Versuch `RuntimeError`, wird ein 3D-Bereich des
        Fensters mit uebergeben — das ist der Kontext, den der Operator
        haette, wenn ihn jemand angeklickt haette. Gibt es keinen (etwa
        beim Lauf ohne Oberflaeche), wird der Fehler weitergereicht.
        """
        def _do_kbs():
            bpy.ops.object.mode_set(mode='POSE')
            bpy.ops.armature.retarget_constrain_to_armature(
                src_preset='--Current--', trg_preset='--Current--',
                match_transform=match_transform)
            bpy.ops.object.mode_set(mode='OBJECT')
            context.view_layer.objects.active = bvh_rig
            bpy.ops.armature.retarget_bake_constrained_actions(do_bake=True)

        try:
            with context.temp_override(
                    object=bvh_rig,
                    active_object=bvh_rig,
                    selected_objects=[rig, bvh_rig]):
                _do_kbs()
        except RuntimeError:
            area_3d = next((a for a in bpy.context.screen.areas
                            if a.type == 'VIEW_3D'), None) if hasattr(bpy.context, 'screen') else None
            if not area_3d:
                raise
            region = next((r for r in area_3d.regions
                           if r.type == 'WINDOW'), area_3d.regions[0])
            with bpy.context.temp_override(
                    window=bpy.context.window,
                    area=area_3d, region=region):
                _do_kbs()

    @staticmethod
    def retarget_kbs(context, rig, bvh_path):
        """Retarget BVH via KBS-DEV Retarget Extension.

        Two-pass approach for all BVH formats:
          Pass 1: match_transform='Pose'  → correct spine rotations
          Pass 2: match_transform='Bone'  → correct arm/leg rotations
        Then merge spine fcurves from pass 1 into pass 2 result.

        Returns (action, f_start, f_end).
        """
        bpy.ops.preferences.addon_enable(module='bl_ext.user_default.retarget')

        bvh_rig, is_mocapnet, fmt = Kbsanbindung._bvh_vorbereiten(
            context, rig, bvh_path)
        orig_bones = set(b.name for b in rig.data.bones)

        # --- Pass 1: match_transform='Pose' → correct spine ---
        logger.info("KBS %s pass 1/2: spine (match_transform='Pose')", fmt)
        act_spine, f_start, f_end = Kbsanbindung._kbs_run_pass(
            context, rig, bvh_path, is_mocapnet, 'Pose',
            bvh_rig=bvh_rig, keep_bvh=True)
        if not act_spine:
            raise RuntimeError("KBS pass 1 produced no action")
        spine_data = Fcurves._extract_fcurve_data(act_spine, _SPINE_MERGE_BONES)
        logger.info("saved %s spine fcurves", len(spine_data))

        Kbsanbindung._reset_rig_for_kbs(context, rig, orig_bones)

        # --- Pass 2: match_transform='Bone' → correct arms/legs ---
        logger.info("KBS %s pass 2/2: limbs (match_transform='Bone')", fmt)
        act_final, f_start, f_end = Kbsanbindung._kbs_run_pass(
            context, rig, bvh_path, is_mocapnet, 'Bone',
            bvh_rig=bvh_rig, keep_bvh=False)
        if not act_final:
            raise RuntimeError("KBS pass 2 produced no action")

        Fcurves._apply_fcurve_data(act_final, spine_data)
        logger.info("merged spine from 'Pose' into 'Bone' action")

        # Remove KBS intermediate bones left from pass 2
        if context.object and context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        zusatz = Kbsanbindung._zusatzknochen_weg(context, rig, orig_bones)
        if zusatz:
            logger.info("removed %s KBS intermediate bones", len(zusatz))

        Kbskurven.ort_nullen(Rigaktionen._get_action_fcurves(act_final))
        Kbskurven.drehung_nullen(Rigaktionen._get_action_fcurves(act_final))

        Rigaktionen._set_fk_mode(rig)
        Rigaktionen._transfer_root_motion(rig)

        act = rig.animation_data.action if rig.animation_data else None
        if not act:
            raise RuntimeError("KBS Extension retarget produced no action")

        logger.info("KBS Extension complete: %s, %s fcurves",
                    act.name, len(Rigaktionen._get_action_fcurves(act)))
        return act, f_start, f_end

    @staticmethod
    def _bvh_vorbereiten(context, rig, bvh_path):
        u"""BVH einlesen, Format erkennen, Knochen filtern, skalieren.

        Zurueck kommt `(bvh_rig, is_mocapnet, Formatname)`. Erkannt wird
        MocapNET daran, dass sein Wurzelknochen `hip` heisst — CMU und
        Mixamo nennen ihn `Hips`.
        """
        bvh_rig, _f_start, _f_end = Bvhimport._import_bvh_armature(
            context, bvh_path)
        if not bvh_rig:
            raise RuntimeError("BVH import produced no armature")
        is_mocapnet = 'hip' in bvh_rig.data.bones
        if is_mocapnet:
            Bvhimport._normalize_openpose_bones(context, bvh_rig)
        fmt = "MocapNET" if is_mocapnet else "CMU"
        logger.info("KBS %s: single BVH import, filtering bones...", fmt)

        Bvhimport._filter_bvh_bones(context, bvh_rig, is_mocapnet)
        Bvhimport._scale_to_match(bvh_rig, rig)

        if context.object and context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        return bvh_rig, is_mocapnet, fmt
