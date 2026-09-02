# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Ein Gangzyklus, Bild fuer Bild — einmal fuer alle Gangarten.

AUS `_gen_walk` UND `_gen_run` ZUSAMMENGELEGT (01.09.2026)
==========================================================
Die beiden Funktionen (115 und 109 Zeilen) hatten denselben Ablauf, in
derselben Reihenfolge, mit denselben Kommentaren — sie unterschieden
sich nur in Zahlen. Die stehen jetzt in `Gangwerte`.

DIE RICHTUNGEN, DIE MAN NICHT SIEHT
===================================
Die Figur schaut nach -Y. Daraus folgt fast alles, was hier
verwunderlich aussieht:

  * `_deg(+X)` an der Huefte schiebt den Fuss nach +Y, also NACH HINTEN.
  * `s = -sin(phase)`: bei `s < 0` steht das linke Bein vorn.
  * Das Knie beugt in der Schwungphase, also wenn sein Bein nach vorn
    geht — links bei `-s > 0`, rechts bei `s > 0`.
  * Die Arme gehen gegengleich zu den Beinen (`arm_osc = -s`).

Die Rumpfe sind aus `_gen_run` uebernommen; der Gehzyklus ergibt sich
daraus mit `vorlage=0` und `kopfdrehung=1.5`.
"""
import math

from .gangknochen import Gangknochen
from .keyframes import Keyframes


class Gangzyklus:
    u"""Erzeugt die Schluesselbilder eines Gangzyklus auf einem Rig."""

    @staticmethod
    def erzeugen(rig, werte):
        u"""Setzt den ganzen Zyklus. Zurueck kommt (erstes, letztes Bild)."""
        knochen = Gangknochen(rig)
        for f in range(werte.bilder + 1):
            phase = (f % werte.takt) / werte.takt * 2 * math.pi
            s = -math.sin(phase)
            Gangzyklus._wurzel(knochen, f, phase, werte)
            Gangzyklus._rumpf(knochen, f, s, werte)
            Gangzyklus._beine(knochen, f, s, phase, werte)
            Gangzyklus._arme(knochen, f, phase, werte)
        return 0, werte.bilder

    # ------------------------------------------------------------ Abschnitte

    @staticmethod
    def _wurzel(knochen, f, phase, werte):
        u"""Vorwaertsbewegung, Federn und seitliches Pendeln."""
        fwd = f * werte.schritt / werte.takt
        bob = abs(math.sin(phase)) * werte.federn
        sway_x = math.sin(phase) * werte.pendeln
        if knochen.torso:
            knochen.torso.location = (sway_x, -fwd, bob)
            Keyframes._kf_loc(knochen.torso, f)

    @staticmethod
    def _rumpf(knochen, f, s, werte):
        u"""Neigung nach vorn, Drehung um die Hochachse, Seitneigung.

        Brust und Kopf folgen der Vorlage mit 30 % und 60 % — so stand
        es im Laufzyklus, und beim Gehen (`vorlage=0`) faellt es weg.
        """
        if knochen.spine1:
            knochen.spine1.rotation_quaternion = Keyframes._deg(
                -werte.vorlage,
                s * werte.rumpfdrehung,
                -s * werte.seitneigung,
            )
            Keyframes._kf(knochen.spine1, f)
        if knochen.spine3:
            knochen.spine3.rotation_quaternion = Keyframes._deg(
                -werte.vorlage * 0.3, s * werte.brustdrehung, 0)
            Keyframes._kf(knochen.spine3, f)
        if knochen.head:
            knochen.head.rotation_quaternion = Keyframes._deg(
                werte.vorlage * 0.6, -s * werte.kopfdrehung, 0)
            Keyframes._kf(knochen.head, f)

    @staticmethod
    def _beine(knochen, f, s, phase, werte):
        u"""Huefte, Knie und Fussgelenk beider Beine."""
        hip_l = s * werte.huefte      # negativ = linkes Bein vorn
        hip_r = -hip_l

        # Das Knie beugt waehrend der Schwungphase nach vorn.
        knee_l = max(0, -s) * werte.knie
        knee_r = max(0, s) * werte.knie

        for gelenk, winkel in ((knochen.thigh_l, hip_l),
                               (knochen.thigh_r, hip_r),
                               (knochen.shin_l, knee_l),
                               (knochen.shin_r, knee_r)):
            if gelenk:
                gelenk.rotation_quaternion = Keyframes._deg(winkel, 0, 0)
                Keyframes._kf(gelenk, f)

        # Fuss: anheben in der Schwungphase, abstossen am Ende
        foot_l_ang = math.sin(phase + werte.fussphase) * werte.fusswinkel
        foot_r_ang = (math.sin(phase + math.pi + werte.fussphase)
                      * werte.fusswinkel)
        for gelenk, winkel in ((knochen.foot_l, foot_l_ang),
                               (knochen.foot_r, foot_r_ang)):
            if gelenk:
                gelenk.rotation_quaternion = Keyframes._deg(winkel, 0, 0)
                Keyframes._kf(gelenk, f)

    @staticmethod
    def _arme(knochen, f, phase, werte):
        u"""Armschwung gegengleich zu den Beinen, dazu die Ellbogen."""
        arm_osc = math.sin(phase)   # = -s; > 0 = linker Arm hinten
        z_arm = arm_osc * werte.armschwung
        for schulter in (knochen.upper_l, knochen.upper_r):
            if schulter:
                schulter.rotation_quaternion = Keyframes._wrot(
                    schulter, ((0, 0, 1), z_arm))
                Keyframes._kf(schulter, f)

        # +_deg am Unterarm beugt den Ellbogen (Hand nach vorn)
        elbow_osc = arm_osc * werte.ellbogenhub
        for gelenk, winkel in ((knochen.fore_l, werte.ellbogen - elbow_osc),
                               (knochen.fore_r, werte.ellbogen + elbow_osc)):
            if gelenk:
                gelenk.rotation_quaternion = Keyframes._deg(winkel, 0, 0)
                Keyframes._kf(gelenk, f)
