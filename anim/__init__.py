# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Die Bauteile der Animation — aufgeteilt aus animation.py.

`animation.py` hatte 1.745 Zeilen: den BVH-Katalog, dreizehn erzeugte
Animationen, den Zwischenspeicher fuer fertige Actions, das Auf- und
Abruesten des Viewports und fuenf Blender-Operatoren — darunter einen
mit 266 Zeilen.

Hier liegt das Handwerk; in `animation.py` bleiben die Operatoren und
die Anmeldung.

DIE ORDNUNG VON UNTEN NACH OBEN
===============================
    katalog            BVH-Verzeichnis, Kategorien, was es gibt
    keyframes          `_deg`, `_wrot`, `_kf` — die kleinsten Bausteine
    gesten_kopf        nicken, schuetteln, umsehen, gruessen
    gesten_koerper     stehen, winken, strecken, klatschen, verlagern
    gangarten          gehen und laufen (die beiden langen)
    prozedural         die Liste der erzeugten Animationen
    zwischenspeicher   fertige Actions als .blend ablegen und holen
    viewport           Netze verstecken, Handler aussetzen, aufraeumen
    bvhladen           der Operator, der eine BVH-Datei uebertraegt
"""
