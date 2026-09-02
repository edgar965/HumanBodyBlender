# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Welche Koerperregion welches Kleidungsstueck ergibt.

AUS `kleidungsstueck.py` HERAUSGELOEST (01.09.2026)
===================================================
Die beiden Tabellen standen ueber `_create_garment` — dort, wo sie
gebraucht werden. Beim Aufteilen der 133-Zeilen-Funktion wurde daraus
ein Zwang: Das Auswahlfeld in `eigenschaften.py` holt `GARMENT_REGIONS`
aus dem Modul, und das neue `kleidungsobjekt.py` braucht dieselbe
Tabelle fuer die Beschriftung. Beides aus `kleidungsstueck` zu holen
haette einen Zyklus ergeben (Stueck -> Objekt -> Stueck).

Daten haben hier keinen Halter noetig, aber einen Ort: Wer eine Region
hinzufuegt, aendert eine Datei, nicht drei.
"""


class Kleidungsregionen:
    u"""Die Regionen, aus denen ein Kleidungsstueck geschnitten wird."""

    #: (Schluessel, Beschriftung, Erklaerung) — die Form, die Blenders
    #: `EnumProperty` in `items=` erwartet.
    AUSWAHL = [
        ('TOP',       "Top",       "Shirt / Jacket / Sweater"),
        ('PANTS',     "Pants",     "Trousers / Jeans"),
        ('SKIRT',     "Skirt",     "Skirt / Dress bottom"),
        ('FULL',      "Full",      "Full body suit / Dress"),
        ('UNDERWEAR', "Underwear", "Underwear / Bikini"),
        ('SHOES',     "Shoes",     "Shoes / Boots"),
    ]

    #: Je Region: der Z-Bereich in Metern, ob die Arme dazugehoeren, die
    #: Kategorie fuer den Flaechenfilter (`None` = kein Filter) und wie
    #: weit die Auswahl nach dem Schnitt waechst.
    VORGABEN = {
        'TOP':       {'z_min': 0.72, 'z_max': 1.42, 'arms': True,  'cat': 'Tops',      'grow': 2},
        'PANTS':     {'z_min': 0.06, 'z_max': 0.82, 'arms': False, 'cat': 'Bottoms',   'grow': 2},
        'SKIRT':     {'z_min': 0.40, 'z_max': 0.82, 'arms': False, 'cat': 'Bottoms',   'grow': 2},
        'FULL':      {'z_min': 0.06, 'z_max': 1.42, 'arms': True,  'cat': 'Full',      'grow': 2},
        'UNDERWEAR': {'z_min': 0.70, 'z_max': 0.88, 'arms': False, 'cat': 'Underwear', 'grow': 2},
        'SHOES':     {'z_min': -0.02, 'z_max': 0.12, 'arms': False, 'cat': None,       'grow': 4},
    }

    @staticmethod
    def beschriftung(schluessel):
        u"""Der lesbare Name einer Region — der Schluessel, wenn unbekannt."""
        return {k: v for k, v, _ in Kleidungsregionen.AUSWAHL}.get(
            schluessel, schluessel)
