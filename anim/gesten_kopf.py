# -*- coding: utf-8 -*-
import math
import logging
logger = logging.getLogger(__name__)
from .keyframes import Keyframes


class Kopfgesten:
    u"""Die frueheren Modulfunktionen, gebuendelt."""

    #: So oft geht der Kopf in den 80 Bildern hin und zurueck. Drei
    #: Perioden sehen als Schleife natuerlich aus und lassen Anfang und
    #: Ende beim selben Wert zusammentreffen.
    PERIODEN = 3

    #: Achsen, wie `Keyframes._deg` sie erwartet.
    NICKEN, DREHEN = 0, 1

    @staticmethod
    def _achse(achse, wert):
        u"""(x, y, z) — *wert* auf der genannten Achse, sonst glatt 0."""
        return tuple(wert if i == achse else 0 for i in range(3))

    @staticmethod
    def _schwingen(rig, achse, ausschlag, nackenanteil, n=80):
        u"""Kopf und Nacken um EINE Achse schwingen lassen.

        Nicken und Kopfschuetteln standen bis zum 01.09.2026 als zwei
        Methoden nebeneinander, sieben Zeilen Wort fuer Wort gleich.
        Verschieden waren nur drei Zahlen: die Achse, der Ausschlag in
        Grad (12 beim Nicken, 18 beim Schuetteln) und wie weit der
        Nacken mitgeht.

        Der Nacken geht nur zum Teil mit: Bewegte er sich genauso weit
        wie der Kopf, kaeme die Drehung aus der Brust statt aus dem Hals.
        """
        kopf = Keyframes._pb(rig, 'head')
        nacken = Keyframes._pb(rig, 'neck')
        if not kopf:
            return 0, n
        for f in range(n + 1):
            welle = math.sin(f / n * Kopfgesten.PERIODEN * 2 * math.pi)
            wert = welle * ausschlag
            kopf.rotation_quaternion = Keyframes._deg(
                *Kopfgesten._achse(achse, wert))
            Keyframes._kf(kopf, f)
            if nacken:
                nacken.rotation_quaternion = Keyframes._deg(
                    *Kopfgesten._achse(achse, wert * nackenanteil))
                Keyframes._kf(nacken, f)
        return 0, n

    @staticmethod
    def _gen_nod_yes(rig):
        """Head nods yes (80 frames, loopable)."""
        return Kopfgesten._schwingen(rig, Kopfgesten.NICKEN, 12, 0.3)

    @staticmethod
    def _gen_shake_no(rig):
        """Head shakes no (80 frames, loopable)."""
        return Kopfgesten._schwingen(rig, Kopfgesten.DREHEN, 18, 0.2)

    @staticmethod
    def _gen_look_around(rig):
        """Look left, right, up, center (160 frames)."""
        N = 160
        head = Keyframes._pb(rig, 'head')
        neck = Keyframes._pb(rig, 'neck')
        if not head:
            return 0, N

        # (frame, pitch_X, yaw_Y)
        # +X = lean back (look up), -X = lean forward (look down)
        # +Y = turn right, -Y = turn left
        keyframes = [
            (0,    0,   0),     # center
            (30,   0,  -30),    # look left (-Y)
            (55,   0,  -30),    # hold
            (80,   0,   30),    # look right (+Y)
            (105,  0,   30),    # hold
            (125,  12,   0),    # look up (+X)
            (140, -10,   0),    # look down (-X)
            (160,  0,   0),     # center
        ]

        for frame, pitch, yaw in keyframes:
            head.rotation_quaternion = Keyframes._deg(pitch, yaw, 0)
            Keyframes._kf(head, frame)
            if neck:
                neck.rotation_quaternion = Keyframes._deg(pitch * 0.3, yaw * 0.3, 0)
                Keyframes._kf(neck, frame)

        return 0, N

    @staticmethod
    def _gen_greeting(rig):
        """Small bow greeting (80 frames)."""
        N = 80
        spine1 = Keyframes._pb(rig, 'spine_fk.001')
        spine3 = Keyframes._pb(rig, 'spine_fk.003')
        head = Keyframes._pb(rig, 'head')
        neck = Keyframes._pb(rig, 'neck')

        for f in range(N + 1):
            t = f / N
            if t < 0.3:
                s = t / 0.3
                bow = s * 20
            elif t < 0.5:
                bow = 20
            else:
                s = (t - 0.5) / 0.5
                bow = 20 * (1 - s)

            # Bow forward: -X = lean forward
            if spine1:
                spine1.rotation_quaternion = Keyframes._deg(-bow, 0, 0)
                Keyframes._kf(spine1, f)
            if spine3:
                spine3.rotation_quaternion = Keyframes._deg(-bow * 0.6, 0, 0)
                Keyframes._kf(spine3, f)
            if head:
                head.rotation_quaternion = Keyframes._deg(-bow * 0.4, 0, 0)
                Keyframes._kf(head, f)
            if neck:
                neck.rotation_quaternion = Keyframes._deg(-bow * 0.3, 0, 0)
                Keyframes._kf(neck, f)

        return 0, N
