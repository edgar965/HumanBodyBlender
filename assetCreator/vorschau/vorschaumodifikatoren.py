# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Die vier Modifikatoren einer Asset-Vorschau.

AUS `_finalize_preview` HERAUSGELOEST (01.09.2026)
==================================================
Vierzig der fuenfundachtzig Zeilen hingen Modifikatoren an: Abstand vom
Koerper, Welligkeit, Stoffdicke, Nachglaettung. Immer dasselbe Muster —
`modifiers.new(...)`, dann fuenf Zuweisungen — und dazwischen die
Bedingung, ob dieser Modifikator ueberhaupt gebraucht wird.

DIE REIHENFOLGE IST NICHT BELIEBIG
==================================
Modifikatoren wirken in der Reihenfolge, in der sie haengen. Erst der
Abstand (die Flaeche vom Koerper wegschieben), dann die Welligkeit (sie
verformen), dann die Dicke (aus der Flaeche einen Koerper machen), dann
die Nachglaettung. Wer die Dicke vor die Welligkeit haengt, welliert die
Innen- und Aussenseite verschieden — und bekommt Loecher.

DIE GEWICHTSGRUPPE
==================
`hb_offset_weight` steuert, WIE WEIT ein Punkt weggeschoben wird. Ohne
eigene Gewichte bekommt jeder Punkt 1.0 und der Abstand ist ueberall
gleich; mit Gewichten aus der Bildanalyse steht der Stoff unten weiter
ab als an den Schultern.
"""
import logging

import bpy

logger = logging.getLogger(__name__)


class Vorschaumodifikatoren:
    u"""Abstand, Welligkeit, Dicke und Glaettung einer Vorschau."""

    @staticmethod
    def gewichtsgruppe(obj, mesh, offset_weights):
        u"""Die Vertexgruppe, an der der Abstand haengt."""
        vg = obj.vertex_groups.new(name="hb_offset_weight")
        if offset_weights:
            for vi, w in offset_weights.items():
                vg.add([vi], w, 'REPLACE')
        else:
            # All vertices get weight 1.0
            vg.add(list(range(len(mesh.vertices))), 1.0, 'REPLACE')
        return vg

    @staticmethod
    def alle_haengen(obj, props, offset_weights):
        u"""Die vier Modifikatoren in der richtigen Reihenfolge."""
        Vorschaumodifikatoren._abstand(obj, props, offset_weights)
        Vorschaumodifikatoren._welligkeit(obj, props)
        Vorschaumodifikatoren._dicke(obj, props)
        Vorschaumodifikatoren._glaettung(obj, props)

    # ------------------------------------------------------------- Einzeln

    @staticmethod
    def _abstand(obj, props, offset_weights):
        u"""Displace entlang der Normalen — der Abstand vom Koerper."""
        mod_disp = obj.modifiers.new(name="hb_offset", type='DISPLACE')
        mod_disp.direction = 'NORMAL'
        mod_disp.mid_level = 0.0
        mod_disp.vertex_group = "hb_offset_weight"
        if offset_weights:
            mod_disp.strength = props.image_offset_max
        else:
            mod_disp.strength = props.offset
        return mod_disp

    @staticmethod
    def _welligkeit(obj, props):
        u"""Ein zweiter Displace ueber eine Wolkentextur.

        Das ist der Unterschied zwischen „Stoff" und „lackierte Flaeche":
        eine feine, unregelmaessige Verformung. `mid_level = 0.5` sorgt
        dafuer, dass die Textur in beide Richtungen wirkt und die Flaeche
        im Mittel bleibt, wo sie war.
        """
        waviness = getattr(props, 'waviness', 0.0)
        if waviness <= 0.01:
            return None
        tex = bpy.data.textures.new(f"hb_wave_{props.name_}", type='CLOUDS')
        tex.noise_scale = 0.06
        tex.noise_depth = 3
        mod_wave = obj.modifiers.new(name="hb_wave", type='DISPLACE')
        mod_wave.texture = tex
        mod_wave.direction = 'NORMAL'
        mod_wave.texture_coords = 'LOCAL'
        mod_wave.mid_level = 0.5
        mod_wave.strength = waviness * 0.008
        return mod_wave

    @staticmethod
    def _dicke(obj, props):
        u"""Solidify — aus der Flaeche wird Stoff mit Staerke."""
        if props.thickness <= 0:
            return None
        mod_solid = obj.modifiers.new(name="hb_solidify", type='SOLIDIFY')
        mod_solid.thickness = props.thickness
        mod_solid.offset = 1.0
        return mod_solid

    @staticmethod
    def _glaettung(obj, props):
        u"""Corrective Smooth — mit festgehaltenem Rand.

        `use_pin_boundary` haelt Saum, Halsausschnitt und Aermel an Ort
        und Stelle; ohne das zieht sich die Glaettung die Raender nach
        innen und das Kleidungsstueck wird kleiner.
        """
        if props.smoothing <= 0:
            return None
        mod_smooth = obj.modifiers.new(name="hb_smooth",
                                       type='CORRECTIVE_SMOOTH')
        mod_smooth.use_pin_boundary = True
        mod_smooth.iterations = int(props.smoothing * 10)
        return mod_smooth
