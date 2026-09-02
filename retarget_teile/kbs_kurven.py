# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Kurven glattziehen, die der KBS-Retarget stehen laesst.

AUS `retarget_kbs` HERAUSGELOEST (01.09.2026)
=============================================
Die letzten fuenfzig Zeilen der 124-Zeilen-Funktion taten zweimal
dasselbe: durch alle F-Kurven laufen, den Knochennamen aus dem
Datenpfad klauben, und die Schluesselpunkte auf einen festen Wert
setzen. Der eigentliche Vorgang — Punkt, linker Griff, rechter Griff —
stand dabei dreimal im Code.

WARUM UEBERHAUPT GENULLT WIRD
=============================
Die KBS-Erweiterung backt Ortsversatz auf jeden FK-Knochen, obwohl nur
`root` und `torso` sich bewegen duerfen; ein Knochen mit eigenem
Ortsversatz reisst das Glied von seinem Elternteil weg. Kopf und
Schultern wiederum uebernimmt sie so aus dem BVH, dass die Figur den
Kopf verdreht — deshalb bekommen sie die Ruhedrehung.

Ein Punkt beim Datenpfad: Der Knochenname steckt als Zeichenkette
darin (`pose.bones["upper_arm_fk.L"].location`). Kurven ohne
`pose.bones["` gehoeren nicht zu einem Knochen und bleiben unangetastet.
"""
import logging

logger = logging.getLogger(__name__)

#: Nur diese beiden Knochen duerfen sich von der Stelle bewegen.
BEWEGLICH = {"root", "torso"}

#: Diese Knochen bekommen die Ruhedrehung.
OHNE_DREHUNG = {"head", "shoulder.L", "shoulder.R"}


class Kbskurven:
    u"""Nachbereitung der F-Kurven nach einem KBS-Durchgang."""

    @staticmethod
    def knochenname(datenpfad):
        u"""Der Knochen, zu dem eine F-Kurve gehoert — `None` bei keinem."""
        if 'pose.bones["' not in datenpfad:
            return None
        return datenpfad.split('pose.bones["')[1].split('"]')[0]

    @staticmethod
    def _fest(fcurve, wert):
        u"""Alle Schluesselpunkte samt Griffen auf einen Wert legen."""
        for kp in fcurve.keyframe_points:
            kp.co[1] = wert
            kp.handle_left[1] = wert
            kp.handle_right[1] = wert
        fcurve.update()

    @staticmethod
    def ort_nullen(fcurves):
        u"""Ortsversatz auf allen Knochen ausser `root` und `torso`."""
        zeroed = 0
        for fc in fcurves:
            if not fc.data_path.endswith('.location'):
                continue
            bname = Kbskurven.knochenname(fc.data_path)
            if bname is None or bname in BEWEGLICH:
                continue
            Kbskurven._fest(fc, 0.0)
            zeroed += 1
        if zeroed:
            logger.info("zeroed %s spurious location fcurves", zeroed)
        return zeroed

    @staticmethod
    def drehung_nullen(fcurves):
        u"""Kopf und Schultern auf die Ruhedrehung.

        Bei einem Quaternion ist die Ruhelage (1, 0, 0, 0) — der erste
        Kanal bekommt also 1.0, die drei anderen 0.0. Bei Eulerwinkeln
        sind es drei Nullen.
        """
        rot_zeroed = 0
        for fc in fcurves:
            bname = Kbskurven.knochenname(fc.data_path)
            if bname is None or bname not in OHNE_DREHUNG:
                continue
            if 'rotation_quaternion' in fc.data_path:
                Kbskurven._fest(fc, 1.0 if fc.array_index == 0 else 0.0)
                rot_zeroed += 1
            elif 'rotation_euler' in fc.data_path:
                Kbskurven._fest(fc, 0.0)
                rot_zeroed += 1
        if rot_zeroed:
            logger.info("zeroed %s head/shoulder rotation fcurves", rot_zeroed)
        return rot_zeroed
