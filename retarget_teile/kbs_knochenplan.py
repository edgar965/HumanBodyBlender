# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Welcher BVH-Knochen welchem Rigify-Knochen entspricht.

AUS `_kbs_run_pass` HERAUSGELOEST (01.09.2026)
==============================================
Die drei Zuordnungen standen als sechzig Zeilen Zuweisungen mitten in
der Funktion, mehrere pro Zeile durch Semikolon getrennt::

    ts.spine.hips = 'hip';        ts.spine.spine = 'abdomen'
    ts.spine.spine1 = 'chest';    ts.spine.spine2 = 'neck'

Das ist eine Tabelle, in Anweisungen geschrieben. Man kann sie nicht
ansehen, ohne sie zu lesen, nicht vergleichen und nicht pruefen — und
ein vertauschter Name faellt nur als schiefe Animation auf.

Jetzt stehen die drei Plaene nebeneinander, in derselben Reihenfolge.
Wer wissen will, was MocapNET „chest" nennt und CMU „Spine1", liest zwei
Zeilen untereinander.

DIE STRUKTUR
============
Aussen die Gliedmasse, wie die KBS-Erweiterung sie fuehrt (`spine`,
`left_arm`, `right_arm`, `left_leg`, `right_leg`), innen die Rolle
(`hips`, `spine`, …). Ein flacher Eintrag wie `root` wird direkt gesetzt.
"""


class Kbsknochenplan:
    u"""Die Knochenzuordnungen der KBS-Erweiterung."""

    #: Quelle: MocapNET/OpenPose-BVH (Kleinschreibung, andere Namen).
    MOCAPNET = {
        'spine': {'hips': 'hip', 'spine': 'abdomen', 'spine1': 'chest',
                  'spine2': 'neck', 'neck': 'neck1', 'head': 'head'},
        'left_arm': {'shoulder': 'lcollar', 'arm': 'lshoulder',
                     'forearm': 'lelbow', 'hand': 'lhand'},
        'right_arm': {'shoulder': 'rcollar', 'arm': 'rshoulder',
                      'forearm': 'relbow', 'hand': 'rhand'},
        'left_leg': {'upleg': 'lhip', 'leg': 'lknee',
                     'foot': 'lfoot', 'toe': 'toe1-1.l'},
        'right_leg': {'upleg': 'rhip', 'leg': 'rknee',
                      'foot': 'rfoot', 'toe': 'toe1-1.r'},
    }

    #: Quelle: CMU/Mixamo-BVH (die verbreitete Grossschreibung).
    CMU = {
        'spine': {'hips': 'Hips', 'spine': 'Spine', 'spine1': 'Spine1',
                  'spine2': 'Neck', 'neck': 'Neck1', 'head': 'Head'},
        'left_arm': {'shoulder': 'LeftShoulder', 'arm': 'LeftArm',
                     'forearm': 'LeftForeArm', 'hand': 'LeftHand'},
        'right_arm': {'shoulder': 'RightShoulder', 'arm': 'RightArm',
                      'forearm': 'RightForeArm', 'hand': 'RightHand'},
        'left_leg': {'upleg': 'LeftUpLeg', 'leg': 'LeftLeg',
                     'foot': 'LeftFoot', 'toe': 'LeftToeBase'},
        'right_leg': {'upleg': 'RightUpLeg', 'leg': 'RightLeg',
                      'foot': 'RightFoot', 'toe': 'RightToeBase'},
    }

    #: Ziel: das Rigify-Rig. `_fk`-Knochen, weil KBS auf die
    #: Vorwaertskinematik backt; die Umschaltung macht `_set_fk_mode`.
    RIGIFY = {
        'spine': {'hips': 'torso', 'spine': 'spine_fk.001',
                  'spine1': 'spine_fk.002', 'spine2': 'spine_fk.003',
                  'neck': 'neck', 'head': 'head'},
        'left_arm': {'shoulder': 'shoulder.L', 'arm': 'upper_arm_fk.L',
                     'forearm': 'forearm_fk.L', 'hand': 'hand_fk.L'},
        'right_arm': {'shoulder': 'shoulder.R', 'arm': 'upper_arm_fk.R',
                      'forearm': 'forearm_fk.R', 'hand': 'hand_fk.R'},
        'left_leg': {'upleg': 'thigh_fk.L', 'leg': 'shin_fk.L',
                     'foot': 'foot_fk.L', 'toe': 'toe_fk.L'},
        'right_leg': {'upleg': 'thigh_fk.R', 'leg': 'shin_fk.R',
                      'foot': 'foot_fk.R', 'toe': 'toe_fk.R'},
        'root': 'root',
    }

    @staticmethod
    def quelle(is_mocapnet):
        u"""Der Plan fuer das erkannte BVH-Format."""
        return (Kbsknochenplan.MOCAPNET if is_mocapnet
                else Kbsknochenplan.CMU)

    @staticmethod
    def setzen(einstellungen, plan):
        u"""Traegt einen Plan in `data.retarget_retarget` ein."""
        for name, wert in plan.items():
            if isinstance(wert, dict):
                glied = getattr(einstellungen, name)
                for rolle, knochen in wert.items():
                    setattr(glied, rolle, knochen)
            else:
                setattr(einstellungen, name, wert)
