# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Die Vorschauobjekte des letzten Vergleichs entfernen.

AUS `bvhladen.execute` HERAUSGELOEST (01.09.2026)
=================================================
Der Aufraeumblock war eine einzige `if`-Bedingung ueber zwoelf
`o.name.startswith(…)`-Aufrufe — dreizehn Zeilen, in denen dieselben
Praefixe teils doppelt vorkamen (`KBS_Preview` UND `KBS_`, wobei das
zweite das erste bereits einschliesst).

Jetzt ist es eine Liste. Wer einen Vergleichslauf hinzufuegt, traegt
sein Praefix dort ein und nirgends sonst.

WARUM DAS AUFRAEUMEN NOETIG IST
===============================
Jeder Vergleichslauf legt Kopien des Rigs an. Bleiben sie liegen,
findet der naechste Lauf mehrere Rigs mit demselben Namen — Blender
haengt dann `.001` an, und ab da zeigt die Szene zwei Skelette
uebereinander, ohne dass etwas schiefgegangen waere.
"""
import logging

import bpy

logger = logging.getLogger(__name__)

#: Womit die Objekte eines Vergleichslaufs beginnen. `KBS_` deckt
#: `KBS_Preview` mit ab; die frueheren Doppelungen sind entfallen.
PRAEFIXE = (
    "BVH_Preview",
    "Rig_Preview",
    "Preview_",
    "KBS_",
    "ROK_",
    "ROK46_",
    "RTEST_",
    "TMP_",
)


class Vorschauaufraeumen:
    u"""Raeumt die Objekte des vorigen Vergleichslaufs weg."""

    @staticmethod
    def alle_weg():
        u"""Entfernt jedes Vorschauobjekt. Zurueck kommt die Anzahl."""
        weg = [o for o in list(bpy.data.objects)
               if o.name.startswith(PRAEFIXE)]
        for o in weg:
            bpy.data.objects.remove(o, do_unlink=True)
        if weg:
            logger.info("%d Vorschauobjekte entfernt", len(weg))
        return len(weg)
