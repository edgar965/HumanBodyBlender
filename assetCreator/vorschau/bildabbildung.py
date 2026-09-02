# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Wie eine Weltkoordinate zu einem Bildpunkt wird.

AUS `create_preview_from_image` HERAUSGELOEST (01.09.2026)
==========================================================
Die Funktion war 129 Zeilen und reichte sieben zusammengehoerende Werte
durch ihren ganzen Rumpf: `sx, sz, ox, oz, w, h` und die Maske. Drei
Aufrufe an `Bildanalyse` bekamen sie in genau dieser Reihenfolge
uebergeben::

    Bildanalyse.vertex_to_image_uv(punkte, sx, sz, ox, oz, w, h)
    Bildanalyse.classify_garment_faces(zentren, uv, fg_mask, w, h)
    Bildanalyse.compute_offset_profile(verts, fg_mask, sx, sz, ox, oz, w, h)

Sieben Werte, die immer zusammen auftreten und immer in derselben
Reihenfolge stehen, sind ein Gegenstand und keine sieben Veraenderlichen:
die Abbildung zwischen Koerper und Bild. Ein vertauschtes `sx`/`sz`
faellt sonst nur als schief sitzendes Kleidungsstueck auf.

Die Massstabsberechnung braucht die Koerperpunkte, deshalb entsteht die
Abbildung ueber `aus_bild` und nicht ueber den Konstruktor.
"""
import logging

import bpy

from ..image_analysis import Bildanalyse

logger = logging.getLogger(__name__)


class Bildabbildung:
    u"""Vordergrundmaske eines Bildes samt Massstab zum Koerper."""

    __slots__ = ('maske', 'sx', 'sz', 'ox', 'oz', 'breite', 'hoehe')

    def __init__(self, maske, sx, sz, ox, oz, breite, hoehe):
        #: Vordergrund/Hintergrund je Bildpunkt.
        self.maske = maske
        #: Massstab in x und z — Weltmeter je Bildpunkt.
        self.sx = sx
        self.sz = sz
        #: Versatz in x und z.
        self.ox = ox
        self.oz = oz
        #: Bildgroesse in Punkten.
        self.breite = breite
        self.hoehe = hoehe

    @staticmethod
    def aus_bild(image_path, props, verts_xz):
        u"""Bild laden, Vordergrund bestimmen, auf den Koerper einpassen.

        `props.image_scale` wirkt NACH der automatischen Einpassung — der
        Nutzer zieht das Kleidungsstueck damit groesser oder kleiner, ohne
        dass die Mitte wandert.
        """
        bpy_img = bpy.data.images.load(image_path, check_existing=True)
        pixels = Bildanalyse.load_image_pixels(bpy_img)
        hoehe, breite = pixels.shape[:2]

        maske = Bildanalyse.classify_foreground(
            pixels, props.image_bg_mode, props.image_threshold)

        body_bounds = Bildanalyse.compute_body_bounds(verts_xz)
        sx, sz, ox, oz = Bildanalyse.auto_fit_scale(body_bounds, maske)

        # Apply user scale
        sx *= props.image_scale
        sz *= props.image_scale
        return Bildabbildung(maske, sx, sz, ox, oz, breite, hoehe)

    # ------------------------------------------------------------- Auskuenfte

    def uv(self, punkte_xz):
        u"""Weltpunkte (x, z) -> Bildkoordinaten."""
        return Bildanalyse.vertex_to_image_uv(
            punkte_xz, self.sx, self.sz, self.ox, self.oz,
            self.breite, self.hoehe)

    def bedeckt(self, zentren_xz):
        u"""Welche Flaechen liegen im Vordergrund des Bildes?"""
        return Bildanalyse.classify_garment_faces(
            zentren_xz, self.uv(zentren_xz), self.maske,
            self.breite, self.hoehe)

    def profil(self, verts_xz):
        u"""(Hoehen, Gewichte) — wie weit der Stoff je Hoehe absteht."""
        return Bildanalyse.compute_offset_profile(
            verts_xz, self.maske, self.sx, self.sz, self.ox, self.oz,
            self.breite, self.hoehe)
