# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Ein Garderobenteil einlesen, anpassen und wieder entfernen.

AUS `wardrobe.py` HERAUSGELOEST (01.09.2026)
============================================
Dort blieben die drei Operatoren und die Anmeldung — das, was Blender
sieht. Die Arbeit selbst haengt an `bpy.data` und an den Asset-Pfaden,
nicht an Blenders Operator-Protokoll, und liess `wardrobe.py` ueber die
300-Zeilen-Grenze wachsen.

WARUM DAS TEIL AN DIE ARMATUR GEHAENGT WIRD
===========================================
Ein Garderobenteil ohne Armatur-Modifikator bleibt stehen, waehrend
sich die Figur bewegt. Deshalb bekommt jedes eingelesene Netz die
Armatur des Charakters — und, wo Gewichte fehlen, eine automatische
Zuordnung.
"""
import logging

import bpy


logger = logging.getLogger(__name__)

__all__ = ['Garderobenaktionen']


class Garderobenaktionen:
    u"""Die frueheren Modulfunktionen, gebuendelt."""

    @staticmethod
    def import_asset(context, asset_info, char_obj):
        """Import an asset and attach it to the character."""
        if not asset_info.blend_file:
            return None

        imported = Garderobenaktionen._einlesen(context, asset_info)
        if not imported:
            return None

        asset_obj = Garderobenaktionen._hauptnetz(imported)

        # Tag as wardrobe asset
        asset_obj.data["hb_wardrobe_asset"] = asset_info.name

        # Parent to character
        asset_obj.parent = char_obj
        asset_obj.matrix_parent_inverse = char_obj.matrix_world.inverted()

        Garderobenaktionen._modifikatoren(asset_obj, asset_info)

        # Smooth shading
        for poly in asset_obj.data.polygons:
            poly.use_smooth = True

        # Remove any extra imported objects that aren't the main mesh
        for obj in imported:
            if obj != asset_obj and obj.type != 'ARMATURE':
                bpy.data.objects.remove(obj, do_unlink=True)

        logger.info("Imported wardrobe asset: %s", asset_info.name)
        return asset_obj

    # ------------------------------------------------------------ Bausteine

    @staticmethod
    def _einlesen(context, asset_info):
        u"""Alle Objekte aus der Asset-.blend in die Szene holen."""
        with bpy.data.libraries.load(asset_info.blend_file, link=False) as (data_from, data_to):
            data_to.objects = data_from.objects[:]

        imported = []
        for obj in data_to.objects:
            if obj is not None:
                context.collection.objects.link(obj)
                imported.append(obj)
        return imported

    @staticmethod
    def _hauptnetz(imported):
        u"""Das eigentliche Kleidungsstueck unter den geladenen Objekten.

        Asset-Dateien koennen mehr enthalten als das Netz — eine Armatur
        etwa. Gesucht ist das erste Netz; gibt es keins, wird das erste
        Objekt genommen, damit der Import nicht ohne Ergebnis endet.
        """
        for obj in imported:
            if obj.type == 'MESH':
                return obj
        return imported[0]

    @staticmethod
    def _modifikatoren(asset_obj, asset_info):
        u"""Abstand und Nachglaettung, mit den Werten aus der config.yaml.

        Die Vorgaben kommen aus `parameters.offset.default` und
        `parameters.smoothing.default`. Die `isinstance`-Pruefungen sind
        nicht ueberfluessig: Die Datei ist von Hand geschrieben, und ein
        `parameters:` ohne Inhalt ergibt `None`, kein leeres Woerterbuch.
        """
        params = asset_info.config.get("parameters", {})
        if not isinstance(params, dict):
            params = {}

        # Add offset modifier (Displace along normals)
        offset_conf = params.get("offset", {})
        mod = asset_obj.modifiers.new(name="hb_offset", type='DISPLACE')
        mod.direction = 'NORMAL'
        mod.mid_level = 0.0
        mod.strength = (offset_conf.get("default", 0.001)
                        if isinstance(offset_conf, dict) else 0.001)

        # Add corrective smooth
        smooth_conf = params.get("smoothing", {})
        mod_s = asset_obj.modifiers.new(name="hb_smooth",
                                        type='CORRECTIVE_SMOOTH')
        mod_s.use_pin_boundary = True
        default_smooth = (smooth_conf.get("default", 0.0)
                          if isinstance(smooth_conf, dict) else 0.0)
        mod_s.iterations = int(default_smooth * 10)

    @staticmethod
    def remove_asset(asset_obj):
        """Remove a fitted asset from the scene."""
        name = asset_obj.data.get("hb_wardrobe_asset", asset_obj.name)
        bpy.data.objects.remove(asset_obj, do_unlink=True)
        logger.info("Removed wardrobe asset: %s", name)
