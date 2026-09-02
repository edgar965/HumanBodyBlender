# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Ein Daz/Poser-BVH ueber den Loader der Diffeomorphic-Erweiterung.

AUS `retarget_bvh` HERAUSGELOEST (01.09.2026)
=============================================
Mitten in der 144-Zeilen-Funktion stand eine Klassendefinition::

    class _Loader(BvhLoader):
        scale = 1.0
        …

Eine Klasse in einem Funktionsrumpf ist hier kein Umweg, sondern noetig:
`BvhLoader` kommt aus `retarget_bvh`, und das Fremdmodul laesst sich erst
importieren, wenn `_init_retarget()` gelaufen ist und den Suchpfad
gesetzt hat. Sie wird also bei JEDEM Aufruf neu gebaut — nur stand sie
dabei zwischen dem uebrigen Ablauf und war von aussen nicht zu sehen.

WAS DIE WERTE BEDEUTEN
======================
`getOrientation` liefert `('-Z', 'Y')`: In Daz-BVH zeigt die Figur nach
-Z und „oben" ist +Y, waehrend Blender +Z als oben fuehrt. `-9999, 9999`
heisst „alle Bilder" — die Auswahl der Bilder trifft spaeter
`getActiveFrames`, nicht der Loader.
"""


class Dazbvhladen:
    u"""Der Loader, den die Diffeomorphic-Erweiterung erwartet."""

    @staticmethod
    def bauen():
        u"""Die Loader-Klasse — erst nach `_init_retarget()` aufrufbar."""
        from retarget_bvh.load import BvhLoader

        class _Loader(BvhLoader):
            scale = 1.0
            ssFactor = 1
            useDefaultSS = True
            useDeleteFbx = True

            def getOrientation(self):
                return '-Z', 'Y'

            def getStartEndFrame(self):
                return -9999, 9999

        return _Loader

    @staticmethod
    def lesen(context, bvh_path):
        u"""Das BVH einlesen und die entstandene Armatur zurueckgeben."""
        return Dazbvhladen.bauen()().readMocapFile(context, bvh_path)
