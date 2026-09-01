# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Wo die Daten liegen — einmal bestimmt, nicht je Datei geraten.

DER FEHLER, DEN DIESES MODUL VERHINDERT (01.09.2026)
====================================================
Sechs Dateien im Addon berechneten ihre Wurzel selbst::

    _TOOLS_ROOT = os.path.dirname(os.path.dirname(__file__))

Das stimmt genau so lange, wie die Datei direkt in `HumanBodyBlender/`
liegt. Beim Aufteilen rutschten `katalog.py` und `haarpfade.py` in ein
Unterpaket — und dieselbe Zeile zeigte plotzlich auf
`HumanBodyBlender/` statt auf `A:\\3DTools`.

DAS WIRFT NICHTS. Der BVH-Katalog waere leer, die Frisurenliste auch;
die Panels haetten sich normal aufgebaut und nichts angeboten. Genau
die Fehlerklasse, die in einem Projekt schon einmal als „alle
gespeicherten Optimierungen sind weg" gemeldet wurde
(`~/.claude/rules/projektpfade.md`).

`pfade.py` liegt fest im Addon-Wurzelverzeichnis. Von hier stimmt
`parent` immer — gleich, wie tief das fragende Modul liegt.
"""
from pathlib import Path

#: Fuer den Fall, dass das Addon nicht neben `HumanBody` liegt (etwa
#: kopiert in Blenders Addon-Ordner). War schon vorher der Rueckfall.
NOTNAGEL = Path(r'A:\3DTools')


class Projektpfade:
    u"""Die Wurzeln, an denen die Daten haengen."""

    #: `HumanBodyBlender/` — das Verzeichnis DIESER Datei.
    ADDON = Path(__file__).resolve().parent

    @classmethod
    def tools(cls):
        u"""`A:\\3DTools` — die Wurzel ueber allen vier Repos."""
        oben = cls.ADDON.parent
        return oben if (oben / 'HumanBody').is_dir() else NOTNAGEL

    @classmethod
    def humanbody(cls):
        u"""`HumanBody/` — Netze, Morphs, Gewichte, Animationen."""
        return cls.tools() / 'HumanBody'

    @classmethod
    def daten(cls):
        u"""`HumanBody/data` — NUR LESEN (Produktionsdaten)."""
        return cls.humanbody() / 'data'

    @classmethod
    def bvh(cls):
        u"""Wo die BVH-Dateien liegen."""
        return cls.daten() / 'animations' / 'bvh'

    @classmethod
    def assets(cls):
        u"""Kleidung und Zubehoer."""
        return cls.daten() / 'assets'

    @classmethod
    def frisuren(cls):
        u"""Die Frisuren-Blends."""
        return cls.daten() / 'hairstyles'

    @classmethod
    def addon_daten(cls):
        u"""`HumanBodyBlender/data` — die mitgelieferten Vorlagen.

        NUR LESEN: Hier liegen `autorig.blend`, die Gewichts-NPZ und die
        Posen. Sie sind Produktionsdaten wie `HumanBody/data`.
        """
        return cls.ADDON / 'data'

    @classmethod
    def geteilte_assets(cls):
        u"""`HumanBodyAssets/` — die geteilte Sammlung neben den Repos.

        Der Rueckfall, wenn eine Datei nicht im Addon liegt. Zwei
        Dateien fuehrten dafuer je ein eigenes `_get_assets_root()`, mit
        gleichem Namen und gleichem Inhalt — eine Namensdublette, die
        beim naechsten Umzug auseinandergelaufen waere.
        """
        return cls.tools() / 'HumanBodyAssets'

    @classmethod
    def webapp(cls):
        u"""`HumanBodyWeb/` — fuer die Weboberflaeche des MocapNET-Laufs."""
        return cls.tools() / 'HumanBodyWeb'
