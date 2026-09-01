# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Die Bauteile des Stoffbaus — aufgeteilt aus cloth_builder.py.

`cloth_builder.py` hatte 2.254 Zeilen und trug alles zugleich: Messen am
Koerper, Netze bauen, vierzehn Grundformen, vier Schablonen, die
Simulation samt Modifikatoren, die Nadeln, die Knochengewichte, dazu die
Blender-Operatoren und die Anmeldung.

Hier liegt jetzt das Handwerk; in `cloth_builder.py` bleiben die
Eigenschaften, die Operatoren und die Anmeldung — also das, was Blender
sieht.

DIE ORDNUNG VON UNTEN NACH OBEN
===============================
Jedes Modul darf nur nach OBEN in dieser Liste greifen. So bleibt der
Baum zyklenfrei; `abhaengigkeiten` prueft das::

    namen              Vertexgruppen- und Merkmalsnamen, sonst nichts
    modifikatorsuche   fragt nur ab, aendert nie
    koerpermass        misst am ausgewerteten Koerpernetz
    netzbau            Ringe, Bruecken, Abschluss eines Netzes
    formen_koerper     Rock, Oberteil, Hose, Arme, Hals, Kopf, Schuhe
    formen_geometrie   Scheibe, Kugel, Oval, Dreieck, Puffer
    schablonen         T-Shirt, Hose, Rock, Kleid aus Koerpermassen
    kleidungsstueck    ein Kleidungsstueck aus einer Koerperregion
    knochengewichte    Gewichte vom Koerper aufs Kleidungsstueck
    modifikatoren      Cloth, Collision, Vertexgruppen einrichten
    nadeln             Pins setzen, loesen, zuruecksetzen
    stoffaktionen      simulieren, anlegen, uebernehmen, schuetteln
    garmentsuche       das Kleidungsstueck finden, poll-Bedingungen

`modifikatorsuche` steht so weit oben, weil `_has_modifier` von fast
allem gebraucht wird: Lag es bei `modifikatoren`, entstand mit
`knochengewichte` sofort ein Ring.
"""
