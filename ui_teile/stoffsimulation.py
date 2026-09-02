# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Die Simulationsknoepfe — Abspielen, Anhalten, Zuruecksetzen.

DREIMAL DASSELBE (01.09.2026)
=============================
Dieser Kasten stand wortgleich in allen drei Stoffseiten: Stoffbau,
Grundkoerper und Vorlage. Neun Zeilen, dreimal — und wer den Knopf
umbenennt oder das Symbol tauscht, aendert eine davon.

Der Kasten kommt zurueck, damit der Aufrufer weiterschreiben kann: Die
Stoffbauseite haengt vier Einstellungen darunter, die anderen beiden
nicht.
"""
import bpy


class Stoffsimulation:
    u"""Der gemeinsame Simulationskasten der Stoffseiten."""

    @staticmethod
    def zeichnen(layout):
        u"""Zeichnet den Kasten und gibt ihn zurueck."""
        box = layout.box()
        box.label(text="Simulation", icon='PLAY')
        row = box.row(align=True)
        row.scale_y = 1.2
        if bpy.context.screen.is_animation_playing:
            row.operator("humanbody.cloth_stop_sim", text="Stop", icon='PAUSE')
        else:
            row.operator("humanbody.cloth_run_sim", text="Play", icon='PLAY')
        row.operator("humanbody.cloth_reset_sim", text="Reset",
                     icon='LOOP_BACK')
        return box
