# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Was in JEDEM Bild passiert: Rumpf, Wurzel, Beine, Schluessel.

Aus `retarget.retarget_rokoko` herausgeloest (01.09.2026), Abschnitt 4.
Der Rumpf der Schleife war mit rund 70 Zeilen der laengste
zusammenhaengende Block der 232-Zeilen-Funktion — und der einzige, der
je Bild laeuft. Was ihn umgibt, laeuft einmal.

DIE REIHENFOLGE IST NICHT BELIEBIG
==================================
1. Konjugation setzt Rumpf und Beine grob.
2. Die v4-Daempfung nimmt die Huefte zurueck und verteilt die
   Vorlage auf die Wirbelkette — MocapNET v4 uebertreibt sie.
3. Die Wurzel folgt dem Huefversatz.
4. `view_layer.update()`, DANN die Zielkorrektur: Sie misst die
   Weltrichtung der Knochen und braucht die eben gesetzten Werte.
5. Erst zuletzt die Schluessel.

Zwischen den Zielebenen steht ebenfalls ein `update()`: Der Unterschenkel
rechnet auf der Stellung des Oberschenkels, nicht auf der davor.
"""
import logging

from mathutils import Quaternion, Vector

logger = logging.getLogger(__name__)

#: Wie stark MocapNET v4 die Huefte uebertreibt, und wie die Vorlage auf
#: die Wirbelkette verteilt wird. Aus dem Augenschein gewonnen, nicht
#: gemessen — die Werte standen so schon in der alten Fassung.
V4_HUEFTE = 0.5
V4_REST = 0.35
V4_WIRBEL = [("spine_fk.001", 0.25), ("spine_fk.002", 0.20),
             ("spine_fk.003", 0.20)]


class Rokokorahmen:
    u"""Ein Bild stellen — vier Schritte in fester Reihenfolge."""

    @staticmethod
    def stellen(context, rig, bvh_rig, plan, frame, bvh_mw, rig_mw, is_v4):
        u"""Ein einzelnes Bild setzen und verschluesseln."""
        context.scene.frame_set(frame)
        Rokokorahmen._konjugieren(rig, bvh_rig, plan)
        if is_v4:
            Rokokorahmen._huefte_daempfen(rig)
        pb_root = Rokokorahmen._wurzel_setzen(rig, bvh_rig, plan,
                                              bvh_mw, rig_mw)
        context.view_layer.update()
        Rokokorahmen._beine_ausrichten(context, rig, bvh_rig, plan,
                                       bvh_mw, rig_mw)
        Rokokorahmen._verschluesseln(rig, plan, frame, pb_root)

    # ------------------------------------------------------------- Schritte

    @staticmethod
    def _konjugieren(rig, bvh_rig, plan):
        u"""``M @ q @ M⁻¹`` — die Drehung ins Ruhesystem des Rigs holen."""
        for src_name, tgt_name, M in plan.conj_pairs:
            pb_src = bvh_rig.pose.bones.get(src_name)
            pb_tgt = rig.pose.bones.get(tgt_name)
            if not pb_src or not pb_tgt:
                continue
            src_q = pb_src.matrix_basis.to_quaternion()
            pb_tgt.rotation_quaternion = M @ src_q @ M.inverted()

    @staticmethod
    def _huefte_daempfen(rig):
        u"""MocapNET v4: Vorlage aus der Huefte in die Wirbelkette geben."""
        pb_torso = rig.pose.bones.get("torso")
        if not pb_torso:
            return
        winkel = pb_torso.rotation_quaternion.to_euler('XYZ')
        lehne = winkel.x * V4_HUEFTE
        winkel.x = lehne * V4_REST
        pb_torso.rotation_quaternion = winkel.to_quaternion()
        for name, anteil in V4_WIRBEL:
            pb = rig.pose.bones.get(name)
            if pb:
                pb.rotation_quaternion = Quaternion((1, 0, 0), lehne * anteil)

    @staticmethod
    def _wurzel_setzen(rig, bvh_rig, plan, bvh_mw, rig_mw):
        u"""Die Wurzel dem Huefversatz nachfuehren; gibt den Knochen zurueck."""
        pb_root = rig.pose.bones.get("root")
        if not (plan.hips_src and pb_root
                and plan.hips_rest_world is not None):
            return pb_root
        pb_hips = bvh_rig.pose.bones.get(plan.hips_src)
        if pb_hips:
            jetzt = (bvh_mw @ pb_hips.matrix).to_translation()
            versatz = jetzt - plan.hips_rest_world
            pb_root.location = rig_mw.inverted().to_3x3() @ versatz
        return pb_root

    @staticmethod
    def _beine_ausrichten(context, rig, bvh_rig, plan, bvh_mw, rig_mw):
        u"""Die Y-Achse jedes Beinknochens auf die des BVH-Knochens drehen.

        Von oben nach unten, mit `update()` zwischen den Ebenen: Der
        Unterschenkel haengt am Oberschenkel, und die Weltrichtung, die
        hier gemessen wird, gilt erst nach dessen Korrektur.
        """
        for ebene in plan.aim_levels:
            for src_name, tgt_name in ebene:
                pb_src = bvh_rig.pose.bones.get(src_name)
                pb_tgt = rig.pose.bones.get(tgt_name)
                if not pb_src or not pb_tgt:
                    continue
                src_y = (bvh_mw @ pb_src.matrix).to_3x3() @ Vector((0, 1, 0))
                tgt_y = (rig_mw @ pb_tgt.matrix).to_3x3() @ Vector((0, 1, 0))
                aim_q = tgt_y.rotation_difference(src_y)
                jetzt = (rig_mw @ pb_tgt.matrix).to_3x3()
                gewuenscht = (aim_q.to_matrix() @ jetzt).to_4x4()
                lokal = rig.convert_space(
                    pose_bone=pb_tgt, matrix=gewuenscht,
                    from_space='WORLD', to_space='LOCAL')
                pb_tgt.rotation_quaternion = lokal.to_quaternion()
            context.view_layer.update()

    @staticmethod
    def _verschluesseln(rig, plan, frame, pb_root):
        u"""Schluessel fuer Rumpf, Beine und die uebersprungenen Knochen.

        Die Arme bleiben aussen vor — ihre Schluessel entstehen beim
        Backen. Wer sie hier setzte, ueberschriebe das Ergebnis.
        """
        for tgt_name in plan.bildknochen:
            pb = rig.pose.bones.get(tgt_name)
            if not pb:
                continue
            if tgt_name in plan.skip_bones:
                pb.rotation_quaternion = Quaternion()
            pb.keyframe_insert(data_path="rotation_quaternion", frame=frame)
        if pb_root:
            pb_root.keyframe_insert(data_path="location", frame=frame)
