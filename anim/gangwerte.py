# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Die Stellschrauben eines Gangzyklus.

WARUM EIN DATENSATZ (01.09.2026)
================================
`_gen_walk` (115 Zeilen) und `_gen_run` (109 Zeilen) waren zu ueber
neunzig Prozent dieselbe Funktion. Was sie unterschied, waren
ausschliesslich Zahlen: Schrittlaenge, Beugewinkel, Federweg, wie stark
der Kopf mitgeht. Der Ablauf darunter — Wurzel, Rumpf, Beine, Arme, je
Bild — stand zweimal Zeile fuer Zeile daneben.

Zweimal derselbe Ablauf heisst: Wer eine Bewegung verbessert,
verbessert sie in einer der beiden Fassungen. Beim Umbau fiel auf, dass
genau das schon passiert war — der Laufzyklus neigt den Rumpf nach vorn,
der Gehzyklus hat die Zeile nicht.

Der Zyklus steht jetzt einmal (`gangzyklus.py`), die Zahlen hier. Eine
dritte Gangart ist damit ein Wertesatz, keine dritte Funktion.

VORLAGE = 0 IST DER TRICK
=========================
Der Gehzyklus schrieb `_deg(0, …)` fuer Rumpf und Brust, der Laufzyklus
`_deg(-FWD_LEAN, …)` und `_deg(-FWD_LEAN * 0.3, …)`. Mit `vorlage=0`
ergibt die Laufformel genau die Gehformel — dieselbe Zeile deckt beide
Faelle, ohne Fallunterscheidung.
"""


class Gangwerte:
    u"""Ein vollstaendiger Satz Bewegungswerte fuer einen Gangzyklus.

    Alle Winkel in Grad, alle Strecken in Metern.
    """

    __slots__ = ('bilder', 'takt', 'schritt', 'huefte', 'knie', 'armschwung',
                 'seitneigung', 'federn', 'pendeln', 'vorlage',
                 'rumpfdrehung', 'brustdrehung', 'kopfdrehung',
                 'fussphase', 'fusswinkel', 'ellbogen', 'ellbogenhub')

    def __init__(self, bilder, takt, schritt, huefte, knie, armschwung,
                 seitneigung, federn, pendeln, vorlage,
                 rumpfdrehung, brustdrehung, kopfdrehung,
                 fussphase, fusswinkel, ellbogen, ellbogenhub):
        #: Wie viele Bilder erzeugt werden (0 bis einschliesslich `bilder`).
        self.bilder = bilder
        #: Bilder je vollstaendigem Zyklus — kuerzer heisst schneller.
        self.takt = takt

        #: Strecke nach vorn je Zyklus, in Metern.
        self.schritt = schritt
        #: Ausschlag der Hueftbeugung.
        self.huefte = huefte
        #: Groesste Kniebeugung waehrend der Schwungphase.
        self.knie = knie
        #: Ausschlag des Armschwungs.
        self.armschwung = armschwung
        #: Seitliche Neigung des Rumpfes.
        self.seitneigung = seitneigung
        #: Senkrechtes Federn, in Metern.
        self.federn = federn
        #: Seitliches Pendeln, in Metern.
        self.pendeln = pendeln

        #: Neigung nach vorn. 0 = aufrecht (Gehen); der Wert steuert
        #: zugleich Brust (30 %) und Kopf (60 %).
        self.vorlage = vorlage

        #: Faktor der Rumpfdrehung (spine_fk.001) um die Hochachse.
        self.rumpfdrehung = rumpfdrehung
        #: Faktor der Brustdrehung (spine_fk.003).
        self.brustdrehung = brustdrehung
        #: Faktor der Kopfdrehung. 0 = der Kopf bleibt gerade.
        self.kopfdrehung = kopfdrehung

        #: Phasenversatz des Fussgelenks gegenueber dem Zyklus.
        self.fussphase = fussphase
        #: Ausschlag des Fussgelenks.
        self.fusswinkel = fusswinkel

        #: Ruhewinkel des Ellbogens.
        self.ellbogen = ellbogen
        #: Ausschlag des Ellbogens um den Ruhewinkel.
        self.ellbogenhub = ellbogenhub
