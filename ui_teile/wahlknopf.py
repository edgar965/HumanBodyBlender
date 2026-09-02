# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Der Knopf, der die Teilewahl am Modell ein- und ausschaltet.

STAND ZWEIMAL (01.09.2026)
==========================
Acht Zeilen, Wort fuer Wort gleich — einmal im Hauptpanel
(`zeichnen_koerper`), einmal ueber dem Teilebaum (`zeichnen_teile`),
mit dem Kommentar „also in main panel, repeated here for convenience"
daneben. Wer die Beschriftung oder das Symbol aendert, aendert sonst
eine von zwei Stellen; die andere zeigt weiter den alten Text, und im
Panel daneben faellt es nicht auf.

Beschriftung und `depress` haengen an `Anzeigezustand.wahl_laeuft` —
dem einen Wert, den der modale Operator setzt.
"""

from .zustand import Anzeigezustand

__all__ = ['Wahlknopf']


class Wahlknopf:
    u"""Der Umschalter „am Modell waehlen"."""

    #: Der modale Operator, den der Knopf startet und beendet.
    OPERATOR = "humanbody.pick_part"

    #: Symbol in beiden Zustaenden dasselbe — nur der Text wechselt.
    SYMBOL = 'RESTRICT_SELECT_OFF'

    EIN = "Click to Select on Model"
    AUS = "Exit Pick Mode"

    @staticmethod
    def zeichnen(layout, hoehe=None):
        u"""Den Knopf in *layout* legen.

        `hoehe` skaliert ihn (das Hauptpanel nimmt 1.3, damit er dort
        als Haupthandlung auffaellt); ohne Angabe bleibt er normal hoch.
        """
        reihe = layout.row(align=True)
        if hoehe is not None:
            reihe.scale_y = hoehe
        if Anzeigezustand.wahl_laeuft:
            reihe.operator(Wahlknopf.OPERATOR, text=Wahlknopf.AUS,
                           icon=Wahlknopf.SYMBOL, depress=True)
        else:
            reihe.operator(Wahlknopf.OPERATOR, text=Wahlknopf.EIN,
                           icon=Wahlknopf.SYMBOL)
        return reihe
