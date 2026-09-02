# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Die drei Fassungen nebeneinander stellen: BVH | Rokoko | KBS.

Der zweite Teil von `HUMANBODY_OT_load_bvh_native.execute`. Wenn er
laeuft, ist das Retargeting fertig — hier geht es nur noch darum, was
man sieht: das rohe BVH-Skelett links bei x = −2, das Hauptrig in der
Mitte, die KBS-Kopie rechts bei x = +2, alle drei auf demselben Boden
und in derselben Tiefe.

WARUM DIE AUSRICHTUNG NOETIG IST
================================
Die drei kommen aus verschiedenen Quellen und bringen jeweils ihre
eigene Nullhoehe mit. Ohne den Abgleich steht das BVH-Skelett je nach
Aufnahme einen halben Meter ueber oder unter dem Rig — und der Vergleich
zeigt dann vor allem diesen Versatz statt der Bewegung, um die es geht.

Bezug ist das mittlere Rig: sein linker Fuss gibt den Boden, seine
Wurzel die Tiefe.
"""
import logging

import bpy

from ..retarget_teile.bvhimport import Bvhimport

logger = logging.getLogger(__name__)

#: Die Namen, unter denen der linke Fuss in den drei Rigs auftaucht.
FUSS_DEF = ("foot_fk.L", "ORG-foot.L", "DEF-foot.L")
FUSS_BVH = ("LeftFoot", "lFoot", "foot.L")


class Vergleichsaufbau:
    u"""Aufstellen, ausrichten, Abspielbereich setzen."""

    @staticmethod
    def bvh_skelett(context, bvh_pfad, rig):
        u"""Das rohe BVH-Skelett links danebenstellen — oder None.

        MocapNET erkennt man am Knochen `hip`, seine v4-Fassung zusaetzlich
        an `__jaw`. Beide brauchen eine Namensangleichung, bevor gefiltert
        wird; sonst bleiben Knochen stehen, die keine Entsprechung haben.
        """
        bvh_rig, _, _ = Bvhimport._import_bvh_armature(context, bvh_pfad)
        if not bvh_rig:
            return None
        is_mocapnet = 'hip' in bvh_rig.data.bones
        is_v4 = is_mocapnet and '__jaw' in bvh_rig.data.bones
        if is_mocapnet:
            Bvhimport._normalize_openpose_bones(context, bvh_rig)
        Bvhimport._filter_bvh_bones(context, bvh_rig, is_mocapnet, is_v4=is_v4)
        bvh_rig.name = "BVH_Preview"
        bvh_rig.show_in_front = True
        Bvhimport._scale_to_match(bvh_rig, rig)
        bvh_rig.location.x = -2.0
        bvh_rig.data.display_type = 'STICK'
        return bvh_rig

    @staticmethod
    def tiefe_angleichen(bvh_rig, rig):
        u"""Das Hauptrig auf die Huefttiefe des BVH-Skeletts schieben."""
        if not bvh_rig:
            return
        hips_name = "hip" if "hip" in bvh_rig.pose.bones else "Hips"
        bvh_hip = (bvh_rig.matrix_world
                   @ bvh_rig.pose.bones[hips_name].matrix).to_translation()
        rig_root = (rig.matrix_world
                    @ rig.pose.bones["root"].matrix).to_translation()
        rig.location.y -= (rig_root.y - bvh_hip.y)

    @staticmethod
    def bezugspunkte(rig):
        u"""``(Bodenhoehe, Wurzelpunkt)`` des mittleren Rigs."""
        bpy.context.view_layer.update()
        ground_z = 0.0
        for fname in FUSS_DEF:
            pb = rig.pose.bones.get(fname)
            if pb:
                ground_z = (rig.matrix_world @ pb.matrix).to_translation().z
                break
        center_root = (rig.matrix_world
                       @ rig.pose.bones["root"].matrix).to_translation()
        return ground_z, center_root

    @staticmethod
    def hoehe_angleichen(bvh_rig, ground_z):
        u"""Das BVH-Skelett auf denselben Boden setzen."""
        if not bvh_rig:
            return
        for bname in FUSS_BVH:
            pb = bvh_rig.pose.bones.get(bname)
            if not pb:
                continue
            fuss_z = (bvh_rig.matrix_world @ pb.matrix).to_translation().z
            bvh_rig.location.z -= (fuss_z - ground_z)
            return

    @staticmethod
    def abspielen(context, obj, letzter_frame):
        u"""Bildbereich, Tempo, Auswahl — und die Wiedergabe starten.

        Das Tempo kommt aus `anim_speed` und wirkt ueber `fps_base`: Ein
        Wert von 2.0 halbiert die Basis, die Wiedergabe laeuft doppelt so
        schnell. `max(0.1, …)` faengt die Null ab — sie waere eine
        Division durch Null, kein langsames Abspielen.
        """
        context.scene.frame_start = 1
        context.scene.frame_end = letzter_frame
        context.scene.frame_set(1)

        speed = getattr(context.scene.humanbody, 'anim_speed', 1.0)
        context.scene.render.fps_base = 1.0 / max(0.1, speed)

        for o in context.view_layer.objects:
            o.select_set(o == obj)
        context.view_layer.objects.active = obj

        try:
            bpy.ops.screen.animation_play()
        # stumm gewollt: Die Wiedergabe zu starten ist Beiwerk. Ist kein
        # Fenster da (Hintergrundlauf), gibt es nichts zu starten.
        except Exception:
            pass
