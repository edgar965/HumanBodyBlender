# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Was vor dem Rokoko-Retarget feststehen muss.

AUS `retarget_rokoko` HERAUSGELOEST (01.09.2026)
================================================
Die ersten dreissig Zeilen der Funktion stellten acht Werte fest, die
danach alle weitergereicht wurden: die eingelesene BVH-Armatur, die
Knochenkarte, zwei Formatkennzeichen, den Bildbereich und die beiden
Weltmatrizen. Acht Werte, die zusammengehoeren und immer gemeinsam
auftreten, sind ein Gegenstand.

WIE DAS FORMAT ERKANNT WIRD
===========================
Am Wurzelknochen: MocapNET nennt ihn `hip`, CMU und Mixamo `Hips`.
Gibt es zusaetzlich `__jaw`, ist es MocapNET v4 — dann kommen die
Fingerknochen dazu. Beides sind Merkmale der Datei selbst; einen Namen
oder eine Kopfzeile, die das Format nennt, hat BVH nicht.

DIE WELTMATRIZEN WERDEN KOPIERT
===============================
`matrix_world.copy()` — nicht die Matrix selbst. Blender gibt eine
lebende Sicht zurueck: Sobald das Retarget das Rig bewegt, aendert sich
auch die Matrix, die man sich gemerkt hat. Die Rechnung braucht aber
die Lage VOR dem Lauf.
"""
import logging

import bpy

from ..rigaktionen import Rigaktionen
from .bvhimport import Bvhimport

logger = logging.getLogger(__name__)


class Rokokostart:
    u"""Die Ausgangslage eines Rokoko-Retargets."""

    __slots__ = ('bvh_rig', 'bone_map', 'is_v4', 'fmt',
                 'f_start', 'f_end', 'bvh_mw', 'rig_mw')

    def __init__(self, bvh_rig, bone_map, is_v4, fmt, f_start, f_end,
                 bvh_mw, rig_mw):
        #: Die eingelesene BVH-Armatur (wird am Ende entfernt).
        self.bvh_rig = bvh_rig
        #: BVH-Knochenname -> Rigify-Knochenname.
        self.bone_map = bone_map
        #: MocapNET v4 — mit Fingern.
        self.is_v4 = is_v4
        #: Der Formatname fuers Protokoll.
        self.fmt = fmt
        #: Erstes und letztes Bild.
        self.f_start = f_start
        self.f_end = f_end
        #: Die Weltmatrizen VOR dem Lauf.
        self.bvh_mw = bvh_mw
        self.rig_mw = rig_mw

    @staticmethod
    def lesen(context, rig, bvh_path, karte_mocapnet, karte_cmu,
              karte_finger):
        u"""BVH einlesen, Format erkennen, Groesse angleichen."""
        bvh_rig, f_start, f_end = Bvhimport._import_bvh_armature(
            context, bvh_path)
        if not bvh_rig:
            raise RuntimeError("BVH import produced no armature")

        is_mocapnet = 'hip' in bvh_rig.data.bones
        is_v4 = is_mocapnet and '__jaw' in bvh_rig.data.bones
        if is_mocapnet:
            Bvhimport._normalize_openpose_bones(context, bvh_rig)
        bone_map = dict(karte_mocapnet) if is_mocapnet else dict(karte_cmu)
        if is_v4:
            bone_map.update(karte_finger)
        fmt = ("MocapNET v4" if is_v4
               else ("MocapNET" if is_mocapnet else "CMU"))
        logger.info("Rokoko TEST retarget (%s): constraints for arms...", fmt)

        Bvhimport._scale_to_match(bvh_rig, rig)
        Rigaktionen._set_fk_mode(rig)
        context.view_layer.update()

        if context.object and context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        return Rokokostart(bvh_rig, bone_map, is_v4, fmt, f_start, f_end,
                           bvh_rig.matrix_world.copy(),
                           rig.matrix_world.copy())
