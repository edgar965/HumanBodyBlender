# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Die Bewegung vom BVH aufs Rigify-Rig uebertragen.

AUS `retarget_bvh` HERAUSGELOEST (01.09.2026)
=============================================
Der letzte und laengste Block der 144-Zeilen-Funktion: Bilder auswaehlen,
ausduennen, Zielrig vorbereiten, in Bloecken uebertragen, zentrieren.

ZWEI GRENZEN, DIE MAN KENNEN MUSS
=================================
`MAX_RETARGET_FRAMES = 500`: Eine lange Aufnahme wird ausgeduennt, sonst
haengt Blenders Oberflaeche minutenlang. Ausgeduennt heisst wirklich
weglassen (`frames[::step]`), nicht mitteln — die Bewegung wird gerade,
nicht langsamer.

Die Bloecke zu hundert Bildern sind keine Ausduennung, sondern der Weg,
wie `CAnimation.retarget` seinen Fortschritt meldet: Es bekommt Nummer
und Gesamtzahl mit und schreibt daraus die Anzeige.

`changeTargetData` / `restoreTargetData` schaltet Beschraenkungen und
Treiber am Zielrig ab. Das MUSS im `finally` zurueck, sonst bleibt das
Rig in einem Zustand stehen, in dem die Rigify-Regler nichts mehr tun —
und das sieht nicht nach einem Fehler aus, sondern nach einem kaputten
Rig.
"""
import logging

logger = logging.getLogger(__name__)

#: Maximum frames to retarget (prevents UI freeze on long animations)
MAX_RETARGET_FRAMES = 500

#: Wie viele Bilder je Aufruf an `CAnimation.retarget` gehen.
BLOCK = 100


class Dazuebertragen:
    u"""Der Uebertragungslauf ueber alle Bilder."""

    @staticmethod
    def fahren(context, rig, srcRig, scn, ueberspringen):
        u"""Uebertraegt die Bewegung. Zurueck kommt (Aktion, erstes, letztes)."""
        from retarget_bvh.utils import setCurrentFrame, setInterpolation
        from retarget_bvh.load import activateObject
        from retarget_bvh.source import setSourceArmature
        from retarget_bvh.bsettings import mcpRna as mcp
        from retarget_bvh.target import findTargetArmature
        from retarget_bvh.retarget import (
            CAnimation, changeTargetData, restoreTargetData,
        )
        from retarget_bvh.t_pose import setRigToFK
        from retarget_bvh.loop import getActiveFrames, centerAnimation

        frames = Dazuebertragen._bilder(srcRig, getActiveFrames)

        activateObject(context, rig)
        if rig.animation_data:
            rig.animation_data.action = None
        setRigToFK(rig)
        setCurrentFrame(scn, frames[0])

        oldData = changeTargetData(rig, scn)
        setSourceArmature(srcRig, scn)
        mcp(scn).TargetRig = "Rigify 3"
        mcp(scn).TargetTPose = "Default"
        info = findTargetArmature(context, rig, False)
        anim = CAnimation(srcRig, rig, info, context)

        for bone_name in ueberspringen:
            anim.boneAnims.pop(bone_name, None)

        anim.putInTPoses(context)

        try:
            Dazuebertragen._bloecke(anim, frames, context)
            setCurrentFrame(scn, frames[0])
        finally:
            restoreTargetData(oldData)

        act = rig.animation_data.action
        centerAnimation(context, rig, act)
        setInterpolation(rig)
        return act, int(min(frames)), int(max(frames))

    # ------------------------------------------------------------ Bausteine

    @staticmethod
    def _bilder(srcRig, getActiveFrames):
        u"""Die zu uebertragenden Bilder, notfalls ausgeduennt."""
        frames = getActiveFrames(srcRig, -9999, 9999)
        if not frames:
            raise RuntimeError("No animation frames in BVH file")

        if len(frames) > MAX_RETARGET_FRAMES:
            step = len(frames) // MAX_RETARGET_FRAMES + 1
            frames = frames[::step]
            logger.info("Subsampled to %s frames (step %s)",
                        len(frames), step)
        return frames

    @staticmethod
    def _bloecke(anim, frames, context):
        u"""Die Bilder in Hundertergruppen uebertragen."""
        n_frames = len(frames)
        idx = 0
        while idx < n_frames:
            block = frames[idx:idx + BLOCK]
            anim.retarget(block, context, idx, n_frames)
            idx += BLOCK
