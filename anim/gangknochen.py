# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Die vierzehn Posenknochen, die ein Gangzyklus bewegt.

AUS `_gen_walk` / `_gen_run` HERAUSGELOEST (01.09.2026)
=======================================================
Beide Funktionen begannen mit denselben vierzehn `Keyframes._pb`-Zeilen.
Ein Knochenname, der sich im Rig aendert, musste zweimal nachgezogen
werden — und `_pb` gibt bei einem Tippfehler `None` zurueck, worauf jede
Verwendung ein `if knochen:` davor hat. Der Zyklus laeuft dann durch und
bewegt eben ein Glied weniger. Kein Fehler, keine Meldung.

Deshalb steht die Liste einmal hier, und `fehlend()` sagt, was das Rig
nicht hergegeben hat.
"""
import logging

from .keyframes import Keyframes

logger = logging.getLogger(__name__)


class Gangknochen:
    u"""Die Posenknochen eines Rigs, unter kurzen Namen."""

    #: Kurzname -> Knochenname im Rigify-Rig.
    NAMEN = {
        'torso': 'torso',
        'spine1': 'spine_fk.001',
        'spine3': 'spine_fk.003',
        'head': 'head',
        'upper_l': 'upper_arm_fk.L',
        'upper_r': 'upper_arm_fk.R',
        'fore_l': 'forearm_fk.L',
        'fore_r': 'forearm_fk.R',
        'thigh_l': 'thigh_fk.L',
        'thigh_r': 'thigh_fk.R',
        'shin_l': 'shin_fk.L',
        'shin_r': 'shin_fk.R',
        'foot_l': 'foot_fk.L',
        'foot_r': 'foot_fk.R',
    }

    __slots__ = tuple(NAMEN)

    def __init__(self, rig):
        for kurz, name in Gangknochen.NAMEN.items():
            setattr(self, kurz, Keyframes._pb(rig, name))
        fehlend = self.fehlend()
        if fehlend:
            logger.warning("Gangzyklus: %d Knochen fehlen im Rig — %s",
                           len(fehlend), ', '.join(fehlend))

    def fehlend(self):
        u"""Die Knochennamen, die das Rig nicht hat."""
        return sorted(name for kurz, name in Gangknochen.NAMEN.items()
                      if getattr(self, kurz) is None)
