# -*- coding: utf-8 -*-
u"""Gehen und Laufen — zwei Wertesaetze fuer denselben Zyklus.

ZUSAMMENGELEGT (01.09.2026)
===========================
Vorher: `_gen_walk` 115 Zeilen, `_gen_run` 109 Zeilen, davon ueber
neunzig Prozent identisch — bis in die Kommentare. Jetzt: der Ablauf in
`gangzyklus.py`, die Zahlen hier, und die beiden Gangarten sind je eine
Zeile. Eine dritte (Schleichen, Humpeln) waere ein weiterer Wertesatz.

Die Werte selbst sind unveraendert uebernommen. Der Gehzyklus fuehrt
`vorlage=0` — er neigte den Rumpf nie nach vorn.

`_gen_walk` HAT KEINEN AUFRUFER. In `prozedural._PROCEDURAL_ANIMS` steht
nur `run`. Die Funktion bleibt, weil sie nach dem Zusammenlegen eine
Zeile kostet; wer sie anbieten will, traegt sie dort ein.
"""
import logging

from .gangwerte import Gangwerte
from .gangzyklus import Gangzyklus

logger = logging.getLogger(__name__)


#: Gehen: 120 Bilder = zwei volle Zyklen, aufrechter Gang.
GEHEN = Gangwerte(
    bilder=120, takt=60,
    schritt=0.55, huefte=22.0, knie=42.0, armschwung=16.0,
    seitneigung=2.0, federn=0.008, pendeln=0.008,
    vorlage=0.0,
    rumpfdrehung=2.5, brustdrehung=1.5, kopfdrehung=1.5,
    fussphase=0.3, fusswinkel=8, ellbogen=25, ellbogenhub=15,
)

#: Laufen: 100 Bilder = rund zweieinhalb Zyklen. Kuerzerer Takt, groessere
#: Ausschlaege, Rumpf nach vorn geneigt, Ellbogen staerker gebeugt.
LAUFEN = Gangwerte(
    bilder=100, takt=40,
    schritt=1.0, huefte=35.0, knie=65.0, armschwung=28.0,
    seitneigung=3.0, federn=0.018, pendeln=0.006,
    vorlage=5.0,
    rumpfdrehung=3.0, brustdrehung=2.0, kopfdrehung=0.0,
    fussphase=0.4, fusswinkel=12, ellbogen=35.0, ellbogenhub=20,
)


class Gangarten:
    u"""Die Gangarten, die sich rechnerisch erzeugen lassen."""

    @staticmethod
    def _gen_walk(rig):
        """Walk cycle with root translation (120 frames = 2 full cycles)."""
        return Gangzyklus.erzeugen(rig, GEHEN)

    @staticmethod
    def _gen_run(rig):
        """Run cycle with root translation (100 frames = ~2.5 cycles)."""
        return Gangzyklus.erzeugen(rig, LAUFEN)
