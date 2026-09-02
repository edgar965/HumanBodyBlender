# SPDX-License-Identifier: GPL-3.0-or-later
#
# BVH motion capture retargeting for HumanBody addon.
# Extracted from animation.py — retarget_rokoko, retarget_kbs + helpers.
u"""Rokoko-Retarget: Rumpf und Beine Bild fuer Bild, Arme ueber Zwaenge.

AUFGETEILT (01.09.2026)
=======================
`retarget_rokoko` war 232 Zeilen, dann 94, jetzt unter 50. Die Bauteile
liegen in `retarget_teile/`:

    rokoko_start.py    BVH einlesen, Format erkennen, Groesse angleichen
    rokoko_knochen.py  Knochen einordnen, Armzwaenge setzen und loesen
    rokoko_rahmen.py   ein einzelnes Bild stellen

ZWEI VERFAHREN IN EINER FUNKTION
================================
Rumpf, Beine und Wurzel werden hier gerechnet — Bild fuer Bild, mit
Konjugation und Zielkorrektur. Die Arme nicht: Sie bekommen
COPY_ROTATION-Zwaenge im Weltbezug, und `nla.bake()` rechnet sie in
Blenders C++-Loeser aus. Fuer die Arme ist das um ein Vielfaches
schneller, fuer den Rumpf liefert es das falsche Ergebnis. Deshalb die
Zweiteilung, und deshalb die Zeitmessung im Protokoll: Sie sagt, welche
der beiden Haelften eine lange Aufnahme aufhaelt.
"""

import os
import logging
import time

import bpy

from .rigaktionen import Rigaktionen

# Die Bauteile liegen in `retarget_teile/`. Hier bleibt, was Blender
# sieht: die Klassen und die Anmeldung.
from .retarget_teile.rokoko_knochen import Rokokoknochen
from .retarget_teile.rokoko_rahmen import Rokokorahmen
from .retarget_teile.rokoko_start import Rokokostart
from .retarget_teile.knochenlisten import _ROKOKO_MAP_CMU, _ROKOKO_MAP_MOCAPNET, _V4_FINGER_MAP

logger = logging.getLogger(__name__)


class Rokoko:
    u"""Der Rokoko-Retarget in seinen acht Schritten."""

    @staticmethod
    def retarget_rokoko(context, rig, bvh_path):
        """Retarget BVH: v0.46 spine/legs per-frame + arms via COPY_ROTATION constraints + nla.bake().

        Spine + legs + root: conjugation + aim correction per-frame.
        Arms: COPY_ROTATION constraints (WORLD space) on BVH bones → nla.bake() (C++ solver).

        Returns (action, f_start, f_end).
        """
        t0 = time.time()

        # 1. Import BVH, scale to match
        lage = Rokokostart.lesen(context, rig, bvh_path,
                                 _ROKOKO_MAP_MOCAPNET, _ROKOKO_MAP_CMU,
                                 _V4_FINGER_MAP)

        # 2./3. Knochen einordnen und den Armen ihre Zwaenge geben
        fingerziele = _V4_FINGER_MAP.values() if lage.is_v4 else ()
        plan = Rokokoknochen.einordnen(lage.bvh_rig, rig, lage.bone_map,
                                       lage.bvh_mw, lage.rig_mw, fingerziele)
        arm_constraints = Rokokoknochen.armzwang_setzen(rig, lage.bvh_rig, plan)

        # 4. Create action + per-frame processing for spine/legs/root
        Rokoko._aktion_anlegen(rig, bvh_path)
        t1 = time.time()
        for frame in range(lage.f_start, lage.f_end + 1):
            Rokokorahmen.stellen(context, rig, lage.bvh_rig, plan, frame,
                                 lage.bvh_mw, lage.rig_mw, lage.is_v4)
        t2 = time.time()
        logger.info("  per-frame spine/legs done in %.1fs", t2 - t1)

        # 5. Bake arm constraints via nla.bake() (C++ solver)
        t3, t4 = Rokoko._arme_backen(context, rig, lage, len(arm_constraints))

        # 6./7. Zwaenge loesen, BVH-Rig entfernen
        Rokokoknochen.armzwang_loesen(rig, arm_constraints)
        if lage.bvh_rig and lage.bvh_rig.name in bpy.data.objects:
            bpy.data.objects.remove(lage.bvh_rig, do_unlink=True)

        # 8. Post-process
        Rigaktionen._set_fk_mode(rig)

        act = rig.animation_data.action if rig.animation_data else None
        if not act:
            raise RuntimeError("Rokoko TEST retarget produced no action")

        logger.info("Rokoko TEST complete in %.1fs (per-frame %.1fs + bake "
                    "%.1fs): %s, %d fcurves", time.time() - t0, t2 - t1,
                    t4 - t3, act.name,
                    len(Rigaktionen._get_action_fcurves(act)))
        return act, lage.f_start, lage.f_end

    # ------------------------------------------------------------ Bausteine

    @staticmethod
    def _aktion_anlegen(rig, bvh_path):
        u"""Eine leere Aktion, benannt nach der BVH-Datei."""
        stem = os.path.splitext(os.path.basename(bvh_path))[0]
        act = bpy.data.actions.new(name=f"RokokoTest_{stem}")
        if not rig.animation_data:
            rig.animation_data_create()
        rig.animation_data.action = act
        return act

    @staticmethod
    def _arme_backen(context, rig, lage, anzahl):
        u"""Die Armzwaenge in Schluesselbilder umrechnen lassen.

        `visual_keying=True` ist der Punkt: Gebacken wird, was man SIEHT
        — das Ergebnis der Zwaenge — und nicht die (leeren) eigenen
        Drehungen der Knochen. `clear_constraints=False`, weil die
        Zwaenge gleich danach von Hand geloest werden; Blender wuerde sie
        sonst schon hier entfernen und die Rueckgabe waere wertlos.

        Zurueck kommen die beiden Zeitpunkte fuers Protokoll.
        """
        context.view_layer.objects.active = rig
        bpy.ops.object.mode_set(mode='POSE')

        logger.info("baking %s arm bones via nla.bake()...", anzahl)
        t3 = time.time()
        bpy.ops.nla.bake(
            frame_start=lage.f_start,
            frame_end=lage.f_end,
            only_selected=False,
            visual_keying=True,
            clear_constraints=False,
            bake_types={'POSE'},
        )
        t4 = time.time()
        logger.info("  nla.bake() arms done in %.1fs", t4 - t3)

        bpy.ops.object.mode_set(mode='OBJECT')
        return t3, t4
