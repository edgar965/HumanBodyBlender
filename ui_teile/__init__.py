# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Die Bauteile der Oberflaeche — aufgeteilt aus ui.py.

`ui.py` hatte 2.194 Zeilen: den Zonen-Aufbau fuer die Teilewahl im
Viewport, sechs Operatoren, siebzehn Zeichenfunktionen und 36
Panel-Klassen. Hier liegt das Handwerk; in `ui.py` bleiben die
Bereichsliste und die Anmeldung.

DIE ORDNUNG VON UNTEN NACH OBEN
===============================
    zustand              der geteilte Anzeigezustand (eine Klasse)
    panelbau             erzeugt die 36 Panels aus 18 Bereichen
    zonen                Koerperzonen, Hervorhebung, Netz-Aktualisierung
    auswahl              die kleinen Operatoren (auf-/zuklappen, waehlen)
    teilewahl            der modale Operator zum Anklicken im Viewport
    zeichnen_koerper     Hauptseite, Typ, Regler, Favoriten, Material
    zeichnen_garderobe   Garderobe, Asset Creator, geometrische Assets
    zeichnen_stoff       Stoffbau, Grundformen, Schablonen
    zeichnen_weitere     Haare, Rig, Pose, Animation, Zufall, Abschluss

DIESE DATEI FEHLTE ZUERST. Das Paket lief trotzdem — Python nimmt seit
3.3 auch ein Verzeichnis ohne `__init__.py` als Namensraum-Paket an.
Ohne die Datei gibt es aber keinen Ort fuer diese Uebersicht, und die
Reihenfolge oben ist das, was den Baum zyklenfrei haelt.
"""
