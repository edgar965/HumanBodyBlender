# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Blender-Klassen anmelden und wieder abmelden.

ACHTMAL DERSELBE RUMPF (01.09.2026)
===================================
In acht Modulen standen dieselben vier Zeilen::

    def register():
        for cls in classes:
            bpy.utils.register_class(cls)

    def unregister():
        for cls in reversed(classes):
            bpy.utils.unregister_class(cls)

`register` und `unregister` MUESSEN am Modul stehen — so ruft Blenders
Addon-Protokoll sie, und `__init__.py` reicht sie an alle Teilmodule
weiter. Ihr RUMPF muss dort nicht stehen.

WARUM `reversed`
================
Klassen koennen aufeinander verweisen — ein Panel auf sein Elternpanel,
eine Eigenschaftsgruppe auf ihren Typ. Beim Anmelden muss die
Voraussetzung zuerst da sein, beim Abmelden zuletzt weg. Genau das
leistet die umgekehrte Reihenfolge; wer sie vergisst, bekommt beim
Deaktivieren des Addons `RuntimeError` und eine halb abgemeldete Szene.

WARUM DAS ABMELDEN FEHLER VERSCHLUCKT
=====================================
Beim Neuladen eines Addons waehrend der Entwicklung ist regelmaessig
eine Klasse schon weg — Blender hat sie beim Fehlschlag der letzten
Anmeldung selbst entfernt. Bricht das Abmelden daran ab, bleibt der
REST angemeldet, und die naechste Anmeldung scheitert an genau diesen
Resten. Ein Addon, das sich nicht mehr deaktivieren laesst, ist teurer
als eine Zeile im Protokoll.

Das Anmelden verschluckt NICHTS: Dort ist ein Fehler eine echte
Nachricht — die Klasse fehlt danach in der Oberflaeche.
"""
import logging

import bpy

logger = logging.getLogger(__name__)


class Klassenanmeldung:
    u"""Meldet eine Liste Blender-Klassen an und wieder ab."""

    @staticmethod
    def an(klassen):
        u"""Der Reihe nach anmelden."""
        for cls in klassen:
            bpy.utils.register_class(cls)

    @staticmethod
    def ab(klassen):
        u"""In umgekehrter Reihenfolge abmelden, Fehler protokollieren."""
        for cls in reversed(klassen):
            try:
                bpy.utils.unregister_class(cls)
            except RuntimeError as fehler:
                logger.warning("Abmelden von %s uebersprungen: %s",
                               getattr(cls, '__name__', cls), fehler)
