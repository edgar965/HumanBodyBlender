# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Die Namen, unter denen der Stoffbau seine Daten in Blender ablegt.

Vertexgruppen und Objekt-Merkmale werden an einer Stelle GESETZT und an
einer anderen GESUCHT — meist in verschiedenen Dateien. Ein Tippfehler
auf einer der beiden Seiten wirft nichts: Die Gruppe wird angelegt und
nie gefunden, das Kleidungsstueck faellt beim Simulieren einfach zu
Boden.

Deshalb stehen sie hier, unterhalb aller Bauteile — und niemand tippt
sie ein zweites Mal.
"""

PIN_GROUP_NAME = 'pinned'
STIFFNESS_GROUP_NAME = 'stiffness'
SHRINKING_GROUP_NAME = 'shrinking'
PRESSURE_GROUP_NAME = 'pressure'
CLOTH_TRIANGULATION = 'hb_cloth_triangulation'
CLOTH_GARMENT_TAG = 'hb_cloth_garment'
