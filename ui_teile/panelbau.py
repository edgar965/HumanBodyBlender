# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Die Panel-Klassen erzeugen, statt sie 36-mal zu schreiben.

DER BEFUND (01.09.2026)
=======================
`ui.py` fuehrte 36 Panel-Klassen. Sie unterschieden sich in DREI Werten
— Beschriftung, Kennung und der Funktion, die den Inhalt zeichnet.
Alles andere stand 36-mal gleich da::

    class HUMANBODY_PT_hair(bpy.types.Panel):
        bl_label = "Hair / Brows / Lashes"
        bl_idname = "HUMANBODY_PT_hair"
        bl_space_type = 'VIEW_3D'
        bl_region_type = 'UI'
        bl_category = "HumanBody"
        bl_parent_id = "HUMANBODY_PT_main"
        bl_options = {'DEFAULT_CLOSED'}

        @classmethod
        def poll(cls, context):
            return _poll_humanbody(context)

        def draw(self, context):
            _draw_hair_body(self.layout, context)

Das sind 540 Zeilen, in denen genau 54 Werte stecken. Und es sind zwei
Saetze desselben: einer in der N-Leiste des Viewports, einer im
Eigenschaften-Editor — bis auf `main` Zeile fuer Zeile deckungsgleich.

Eine Kopie ist eine Stelle, an der man etwas vergessen kann. Wer ein
Panel ergaenzt und nur einen der beiden Saetze pflegt, hat es an einem
Ort und am anderen nicht — und das faellt erst auf, wenn jemand dort
sucht.

WARUM DAS IN BLENDER GEHT
=========================
Blender liest `bl_*` als Klassenattribute und `register_class` nimmt
jede Klasse, die von `bpy.types.Panel` erbt. Ob sie mit `class` oder
mit `type()` entstanden ist, sieht es nicht — der Klassenname landet
identisch in `__name__`, und `bl_idname` bleibt derselbe Text wie
vorher. Der Test `DieAnmeldung` vergleicht die angemeldeten Namen
Zeichen fuer Zeichen mit dem Stand davor.
"""
import bpy


class Panelbau:
    u"""Erzeugt einen Satz Panels fuer einen Ort in Blenders Oberflaeche."""

    #: Die beiden Orte, an denen dieselben Panels erscheinen.
    #:
    #: `wurzel` traegt die beiden Punkte, in denen sich die Hauptpanels
    #: WIRKLICH unterscheiden — beim Abgleich mit dem alten Stand kamen
    #: sie heraus, und sie sind kein Versehen: In der N-Leiste steht das
    #: Hauptpanel IMMER (sonst faende niemand den Knopf zum Anlegen), im
    #: Eigenschaften-Editor nur bei einem HumanBody.
    ORTE = {
        'viewport': {
            'vorsilbe': 'HUMANBODY_PT_',
            'raum': 'VIEW_3D', 'gebiet': 'UI',
            'zusatz': {'bl_category': 'HumanBody'},
            # Die Fassung steht so im Bestand. Sie stimmt nicht mit
            # `bl_info` ueberein (0.0.54) — unveraendert uebernommen,
            # Versionsnummern werden hier nicht nebenbei angefasst.
            'wurzel': {'beschriftung': 'HumanBody 0.30', 'poll': False},
        },
        'eigenschaften': {
            'vorsilbe': 'HUMANBODY_PT_props_',
            'raum': 'PROPERTIES', 'gebiet': 'WINDOW',
            'zusatz': {'bl_context': 'data'},
            'wurzel': {'beschriftung': 'HumanBody', 'poll': True},
        },
    }

    def __init__(self, ort, bereiche, poll):
        angabe = self.ORTE[ort]
        self.vorsilbe = angabe['vorsilbe']
        self.raum = angabe['raum']
        self.gebiet = angabe['gebiet']
        self.zusatz = angabe['zusatz']
        self.wurzelangabe = angabe['wurzel']
        self.bereiche = bereiche
        self.poll = poll

    def erzeugen(self):
        u"""[Panel-Klasse] — die Wurzel zuerst, dann alles darunter.

        Die REIHENFOLGE ist nicht beliebig: Blender braucht das
        Elternpanel angemeldet, bevor ein Kind auf es zeigt. Die
        Bereichsliste steht schon in dieser Folge; sie wird nicht
        umsortiert.
        """
        return [self._klasse(b) for b in self.bereiche]

    def _klasse(self, bereich):
        name = self.vorsilbe + bereich.kurz
        wurzel = bereich.eltern is None
        felder = {
            'bl_label': (self.wurzelangabe['beschriftung'] if wurzel
                         else bereich.beschriftung),
            'bl_idname': name,
            'bl_space_type': self.raum,
            'bl_region_type': self.gebiet,
            # `self.layout` ist gewollt: Blender reicht das Layout so
            # durch, und alle 36 Panels taten es vorher genauso.
            'draw': lambda selbst, kontext, _z=bereich.zeichner:
                _z(selbst.layout, kontext),
            '__doc__': bereich.beschriftung,
        }
        felder.update(self.zusatz)
        if not wurzel:
            felder['bl_parent_id'] = self.vorsilbe + bereich.eltern
            felder['bl_options'] = {'DEFAULT_CLOSED'}
        if not wurzel or self.wurzelangabe['poll']:
            felder['poll'] = classmethod(
                lambda _k, kontext, _p=self.poll: _p(kontext))
        return type(name, (bpy.types.Panel,), felder)


class Panelbereich:
    u"""Ein Abschnitt der Oberflaeche — Name, Beschriftung, Inhalt."""

    def __init__(self, kurz, beschriftung, zeichner, eltern='main'):
        self.kurz = kurz
        self.beschriftung = beschriftung
        self.zeichner = zeichner
        #: Der Kurzname des Elternbereichs — ``None`` beim Hauptpanel.
        #: DIE VERSCHACHTELUNG IST NICHT FLACH: Fuenf Panels haengen
        #: unter `wardrobe`, nicht unter `main`. Beim ersten Wurf dieser
        #: Fabrik gingen genau die verloren, weil sie „alle Kinder an
        #: die Wurzel" annahm — gefunden hat es der Feldvergleich gegen
        #: den alten Stand, nicht der Ladetest.
        self.eltern = eltern
