# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Den Charakter finden, auch wenn gerade etwas anderes ausgewaehlt ist.

AUS `teilewahl.py` HERAUSGELOEST (01.09.2026)
=============================================
Zweimal wortgleich in derselben Datei::

    obj = context.active_object
    if not obj or not obj.data.get("humanbody"):
        for o in context.scene.objects:
            if o.type == 'MESH' and o.data.get("humanbody"):
                obj = o
                break

Und die erste Zeile der Bedingung fehlte der Typtest: Bei einem Empty
ist `obj.data` gleich `None`, und `.get()` darauf wirft — mitten im
Auswahlwerkzeug, waehrend der Nutzer ins Fenster klickt.

WARUM DER RUECKFALL NOETIG IST
==============================
Das Auswahlwerkzeug laeuft, waehrend der Nutzer mit der Maus im Fenster
arbeitet. Was gerade aktiv ist, kann alles sein — ein Kleidungsstueck,
eine Lampe, das Rig. Gesucht wird aber immer der Charakter.
"""
import logging

from ..charakter.charakterpruefung import Charakterpruefung

logger = logging.getLogger(__name__)


class Charakterwahl:
    u"""Findet den HumanBody-Charakter in der Szene."""

    @staticmethod
    def aktiv_oder_erster(context):
        u"""Das aktive HumanBody-Netz, sonst das erste in der Szene.

        `None`, wenn die Szene keines enthaelt.
        """
        obj = context.active_object
        if Charakterpruefung.ist_charakter(obj):
            return obj
        for o in context.scene.objects:
            if Charakterpruefung.ist_charakter(o):
                return o
        return None
