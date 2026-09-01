# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Der Zustand der N-Panel-Anzeige, an einer Stelle.

WARUM EINE KLASSE (01.09.2026)
==============================
In `ui.py` standen dreizehn Modulvariablen, die drei Bauteile
gemeinsam benutzen — die Teilewahl im Viewport, das Zeichnen der
Hervorhebung und die Aktualisierung nach einer Netzaenderung. Gesetzt
wurden sie mit `global`, in Zeilen wie::

    global _pick_mode_active, _pick_generation, _hovered_category
    global _zone_tris, _face_cat_map
    global _draw_handler, _highlight_batch, _highlight_cat_cache

Solange alles in einer Datei stand, ging das. Beim Aufteilen bricht es
STILL: `global` bezieht sich immer auf das eigene Modul. Ein Bauteil,
das `_pick_mode_active = True` setzt, legt damit eine neue Variable in
SEINEM Modul an — das andere liest weiter seine eigene und sieht `False`.
Kein Fehler, keine Meldung; die Teilewahl liesse sich einschalten und
waere nie an.

Als Klassenattribute gibt es die Werte genau einmal. `global`
verschwindet damit ganz.

WAS HIER NICHT HINEINGEHOERT
============================
Nur Zustand, der WIRKLICH geteilt wird. Was ein Bauteil allein
braucht, bleibt dort.
"""


class Anzeigezustand:
    u"""Was die Anzeige gerade tut — geteilt von drei Bauteilen."""

    # --- Teilewahl im Viewport ---------------------------------------
    #: Laeuft der modale Operator gerade?
    wahl_laeuft = False
    #: Die Kategorie unter dem Mauszeiger ('' = keine).
    kategorie_unter_maus = ""
    #: Wird bei jeder Aktivierung erhoeht — ein alter modaler Lauf
    #: erkennt daran, dass er ueberholt ist, und beendet sich.
    lauf = 0

    # --- Zeichnen der Hervorhebung -----------------------------------
    #: Der bei Blender angemeldete Zeichner (`draw_handler_add`).
    zeichner = None
    #: Kategorie -> [(v0, v1, v2)] in Weltkoordinaten.
    zonendreiecke = {}
    #: Flaechennummer (Originalnetz) -> Kategorie.
    flaeche_zu_kategorie = {}
    #: Der zuletzt gebaute Zeichenstapel und die Kategorie dazu — damit
    #: er nicht in jedem Bild neu entsteht.
    stapel = None
    stapel_kategorie = ""

    # --- Aktualisierung nach einer Netzaenderung ----------------------
    #: Der bei Blender angemeldete Beobachter (`depsgraph_update_post`).
    beobachter = None
    #: Laeuft gerade eine Aktualisierung? Schuetzt vor Rekursion.
    aktualisiert = False
    #: Der Streuwert der zuletzt verarbeiteten Reglerstellungen.
    letzte_werte = None
    #: Steht eine Aktualisierung noch aus?
    aktualisierung_offen = False

    # --- Aufgeklappte Kategorien im Parts-Baum ------------------------
    aufgeklappt = set()
