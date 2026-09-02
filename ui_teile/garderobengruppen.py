# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Welches Kleidungsstueck in welche Kategorie gehoert.

AUS `_draw_wardrobe_body` HERAUSGELOEST (01.09.2026)
====================================================
Dieselbe Bewegung wie bei `morphgruppen.py`: Die Zeichenfunktion baute
in ihren ersten zwanzig Zeilen eine Zuordnung auf, die mit dem Zeichnen
nichts zu tun hat. Reine Datenarbeit laesst sich pruefen, ohne dass
Blender laeuft — die Zeichenfunktion nicht.

Die Suche greift auf Namen UND Schlagwoerter; Haare bleiben aussen vor,
sie haben ein eigenes Bedienfeld.
"""
from ..garderobe.assetsuche import WARDROBE_CATEGORIES


class Garderobengruppen:
    u"""Ordnet die gefundenen Kleidungsstuecke nach Kategorie."""

    @staticmethod
    def bauen(assets, suche):
        u"""``{Kategorie: [Asset, …]}`` — gefiltert nach Suchtext."""
        cat_assets = {}
        for a in assets:
            if a.category == "Hair":
                continue  # Hair is in the Hair panel
            if suche and suche not in a.name.lower() and \
               not any(suche in t.lower() for t in a.tags):
                continue
            cat = a.category
            if cat not in cat_assets:
                cat_assets[cat] = []
            cat_assets[cat].append(a)
        return cat_assets

    @staticmethod
    def gewaehlt(selected, cat_assets):
        u"""Die angezeigte Kategorie — die erste, wenn keine passt."""
        ordered = [name for name, _ in WARDROBE_CATEGORIES
                   if name in cat_assets]
        if (not selected or selected not in cat_assets) and ordered:
            return ordered[0]
        return selected
