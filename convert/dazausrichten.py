# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Quell- und Zielarmatur aufeinander einstellen, bevor uebertragen wird.

AUS `retarget_bvh` HERAUSGELOEST (01.09.2026)
=============================================
Zwei Bloecke aus der 144-Zeilen-Funktion: das Zuordnen der Armaturen
(elf Aufrufe an die Fremdbibliothek, in einer Reihenfolge, die man nicht
tauschen darf) und das Angleichen der Groesse.

DIE REIHENFOLGE IST DAS EIGENTLICHE WISSEN
==========================================
`findTargetArmature` muss VOR `findSourceArmature` laufen, beide mit dem
jeweils aktiven Objekt; `renameBones` vor `normalizeSourceRig` vor
`putInTPose`. Steht eins davon falsch, entsteht keine Fehlermeldung —
die Bewegung sitzt nur schief. Deshalb steht die Kette hier an einer
Stelle, mit einem Namen darueber.

Rigify wird fest vorgegeben (`"Rigify 3"`), weil die automatische
Erkennung unter Blender 5.0 danebengreift.
"""
import logging

logger = logging.getLogger(__name__)


class Dazausrichten:
    u"""Zuordnung und Groessenangleich zwischen BVH- und Rigify-Armatur."""

    @staticmethod
    def zuordnen(context, rig, srcRig, scn):
        u"""Beide Armaturen erkennen lassen und die Quelle in T-Pose bringen."""
        from retarget_bvh.bsettings import mcpRna as mcp
        from retarget_bvh.utils import setActiveObject, setInterpolation
        from retarget_bvh.load import activateObject, renameBones
        from retarget_bvh.source import findSourceArmature, normalizeSourceRig
        from retarget_bvh.target import findTargetArmature
        from retarget_bvh.t_pose import putInTPose

        scn.frame_current = 0
        setActiveObject(context, srcRig)

        # Force Rigify 3 — auto-detection may fail on Blender 5.0
        mcp(scn).TargetRig = "Rigify 3"
        mcp(scn).TargetTPose = "Default"

        activateObject(context, rig)
        findTargetArmature(context, rig, False)

        activateObject(context, srcRig)
        findSourceArmature(context, srcRig, True)

        renameBones(srcRig, context)
        normalizeSourceRig(srcRig)
        putInTPose(context, srcRig, mcp(scn).SourceTPose)
        setInterpolation(srcRig)

    @staticmethod
    def groesse_angleichen(context, rig, srcRig):
        u"""Die Quellarmatur auf die Beinlaenge des Ziels skalieren.

        Gemessen wird am linken Oberschenkel (Huefte bis Knie). Fehlt
        einer der vier Knochen oder ist die Quelle entartet kurz, bleibt
        alles, wie es ist.

        Die Bewegung muss mitskaliert werden: Die Ortskurven stehen in
        Metern, ein doppelt so grosses Rig macht sonst halb so grosse
        Schritte. Das `use_connect = False` in der ersten Schleife ist
        noetig, weil ein verbundener Knochen seinem Elternteil folgt und
        sich nicht einzeln verschieben laesst.
        """
        import bpy
        from retarget_bvh.utils import setActiveObject, getTrgBone, getRnaFcurves

        trgThigh = getTrgBone("thigh.L", rig, force=True)
        trgShin = getTrgBone("shin.L", rig)
        srcThigh = getTrgBone("thigh.L", srcRig, force=True)
        srcShin = getTrgBone("shin.L", srcRig)
        if not (trgThigh and trgShin and srcThigh and srcShin):
            return
        trgLen = (trgThigh.head - trgShin.head).length
        srcLen = (srcThigh.head - srcShin.head).length
        if srcLen <= 1e-4:
            return

        scale = trgLen / srcLen
        logger.info("Rescaling by %.4f", scale)
        setActiveObject(context, srcRig)
        bpy.ops.object.mode_set(mode='EDIT')
        for eb in srcRig.data.edit_bones:
            eb.use_connect = False
        for eb in srcRig.data.edit_bones:
            eb.head *= scale
            eb.tail *= scale
        bpy.ops.object.mode_set(mode='OBJECT')
        for fcu in getRnaFcurves(srcRig):
            if fcu.data_path.split('.')[-1] == 'location':
                for kp in fcu.keyframe_points:
                    kp.co[1] *= scale
