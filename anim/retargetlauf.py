# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Ein Retarget auf einer Wegwerfkopie des Rigs.

AUS `bvhladen.execute` HERAUSGELOEST (01.09.2026)
=================================================
Zweimal derselbe Ablauf stand untereinander im Rumpf — einmal fuer
Rokoko, einmal fuer KBS, rund fuenfundzwanzig Zeilen je Fall:
zwischengespeicherte Aktion suchen, sonst das Rig kopieren, die Kopie
in die Szene haengen, ihre Animation loesen, das Retarget fahren, das
Ergebnis in den Zwischenspeicher legen, und die Kopie im `finally`
wieder entfernen.

WARUM UEBERHAUPT AUF EINER KOPIE
================================
Beide Retargeter arbeiten IM Rig: Sie haengen Hilfsknochen an, setzen
Beschraenkungen, schalten Rigify-Regler um. Was danach nicht sauber
zurueckgenommen wird, bleibt im echten Rig stehen. Auf einer Kopie ist
das gleichgueltig — sie wird ohnehin weggeworfen, und mitgenommen wird
nur die entstandene Aktion.

Deshalb faengt der Lauf JEDE Ausnahme: Ein gescheitertes Retarget darf
den Vergleich nicht abbrechen, denn die anderen Spalten stehen bereits.
Die Ursache steht im Protokoll; nach aussen kommt `None`.
"""
import logging

import bpy

from .viewport import Ansichtsfenster
from .zwischenspeicher import Aktionsspeicher

logger = logging.getLogger(__name__)


class Retargetlauf:
    u"""Ein Retarget auf einer Kopie, mit Zwischenspeicher."""

    @staticmethod
    def holen(context, rig, bvh_path, kopiename, retargeter,
              praefix="HB_Anim", nachsilbe="", netze_verstecken=False):
        u"""Die Aktion zu diesem BVH — aus dem Speicher oder frisch gerechnet.

        Zurueck kommt `(Aktion, erstes Bild, letztes Bild)`; bei einem
        Fehlschlag `(None, 1, 1)`.
        """
        act, f_start, f_end = Aktionsspeicher._load_cached_action(
            rig, bvh_path, praefix, nachsilbe)
        if act:
            return act, f_start, f_end
        return Retargetlauf._rechnen(context, rig, bvh_path, kopiename,
                                     retargeter, nachsilbe, netze_verstecken)

    @staticmethod
    def _rechnen(context, rig, bvh_path, kopiename, retargeter, nachsilbe,
                 netze_verstecken=False):
        u"""Das Retarget auf einer Wegwerfkopie fahren.

        `netze_verstecken` blendet die Netze der Kopie waehrenddessen aus.
        Das spart bei einem langen Retarget spuerbar Zeit: Blender wertet
        sonst je Bild die Modifikatorkette jedes Netzes aus, obwohl
        niemand hinsieht.
        """
        rig_tmp = rig.copy()
        rig_tmp.data = rig.data.copy()
        rig_tmp.name = kopiename
        context.collection.objects.link(rig_tmp)
        if netze_verstecken:
            Ansichtsfenster._hide_meshes_for_retarget(rig_tmp)
        act, f_start, f_end = None, 1, 1
        try:
            if rig_tmp.animation_data:
                rig_tmp.animation_data.action = None
            act, f_start, f_end = retargeter(context, rig_tmp, bvh_path)
            if act:
                Aktionsspeicher._save_action_cache(bvh_path, act, nachsilbe)
        except Exception:
            logger.exception("Retarget %s fehlgeschlagen", kopiename)
            act = None
        finally:
            if netze_verstecken:
                Ansichtsfenster._show_meshes_after_retarget(rig_tmp)
            try:
                bpy.data.objects.remove(rig_tmp, do_unlink=True)
            # stumm gewollt: Aufraeumen im finally. Ein Fehler hier wuerde
            # den echten Fehler darueber verdecken.
            except Exception:
                pass
        return act, f_start, f_end
