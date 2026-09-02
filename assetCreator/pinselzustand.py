# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Der geteilte Zustand des Malpinsels im Asset Creator.

WARUM EINE KLASSE UND KEINE MODULVARIABLEN (01.09.2026)
=======================================================
Die fuenf Werte standen als Modulvariablen in `brush.py`, und
`_draw_brush_circle` las sie. Beim Aufteilen wanderte diese Funktion nach
`pinselzeichnung.py` — und las dort fuenf Namen, die es in ihrem Modul
nicht gibt. Die Datei parst, das Addon laedt, und erst der GPU-Rueckruf
beim ersten Mausbewegen wirft `NameError`.

`global` bezieht sich immer auf das EIGENE Modul. Zwei Bauteile, die
sich Zustand teilen, brauchen deshalb einen Halter, den beide beim
Namen kennen. Dieselbe Loesung wie `ui_teile/zustand.Anzeigezustand`.
"""


class Pinselzustand:
    u"""Wo der Pinsel gerade steht und wie gross er ist."""

    #: Laeuft der modale Operator?
    aktiv = False
    #: Der angemeldete GPU-Zeichner (`SpaceView3D.draw_handler_add`).
    zeichner = None
    #: Mittelpunkt auf der Oberflaeche, in Weltkoordinaten — oder None,
    #: wenn der Zeiger neben dem Netz steht.
    mitte = None
    #: Flaechennormale an dieser Stelle.
    normale = None
    #: Radius in Metern; das Mausrad aendert ihn zwischen 0,005 und 0,2.
    radius = 0.03
