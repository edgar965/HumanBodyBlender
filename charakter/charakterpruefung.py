# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Steht ein HumanBody-Charakter bereit — und hat er ein Rig?

DIESELBEN ZEHN ZEILEN, SIEBENMAL FALSCH (01.09.2026)
=====================================================
Die Eingangspruefung stand in ueber zwanzig Operatoren, und sieben davon
liessen den Typtest weg::

    if not obj or not obj.data.get("humanbody"):

Bei einem Empty (oder einer Kamera, einem Licht) ist `obj.data` gleich
`None`. `.get()` darauf beendet den Operator mit einem Traceback statt
mit der Meldung, die eine Zeile weiter steht — der Nutzer sieht ein
rotes Fenster, keine Erklaerung.

Der Fall ist am 13.08.2026 schon einmal gefunden worden; ein Kommentar
in `rig_teile/posenoperatoren.py` beschrieb ihn und nannte drei Stellen.
Beim Aufteilen kamen zwei neue dazu — abgeschrieben aus einer der
falschen Fassungen. Genau daran erkennt man eine Pruefung, die an
zwanzig Stellen steht statt an einer.

WARUM DER OPERATOR UEBERGEBEN WIRD
==================================
`operator.report(...)` gehoert dem Operator: Nur er kann eine Meldung in
Blenders Statuszeile schreiben. Statt den Grund zurueckzugeben und jeden
Aufrufer melden zu lassen, meldet die Pruefung selbst. Fuer `poll()`,
das nichts melden darf, gibt es `ist_charakter`.
"""
import logging

logger = logging.getLogger(__name__)


class Charakterpruefung:
    u"""Die Eingangspruefung der Charakter-Operatoren."""

    @staticmethod
    def ist_charakter(obj):
        u"""Ist das ein HumanBody-Netz? — ohne Meldung, fuer `poll()`.

        Der Typtest MUSS vor `obj.data` stehen: Nur ein Netz hat
        ueberhaupt `data` mit einem Woerterbuch darin.
        """
        return bool(obj and obj.type == 'MESH'
                    and obj.data.get("humanbody"))

    @staticmethod
    def charakter(context, operator, meldung="Select a HumanBody character"):
        u"""Das aktive HumanBody-Netz — oder `None` mit einer Meldung."""
        obj = context.active_object
        if not Charakterpruefung.ist_charakter(obj):
            operator.report({'ERROR'}, meldung)
            return None
        return obj

    @staticmethod
    def rig_holen(context, operator):
        u"""(Objekt, Rig) — oder (None, None), wenn etwas fehlt.

        Gemeldet wird sofort; der Aufrufer gibt nur noch `CANCELLED`
        zurueck.
        """
        from ..rig_teile.rigsuche import Rigsuche

        obj = Charakterpruefung.charakter(context, operator)
        if not obj:
            return None, None
        rig = Rigsuche._find_rig(obj)
        if not rig:
            operator.report({'ERROR'}, "Add a rig first")
            return None, None
        return obj, rig
