# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Operatoren, die einen HumanBody-Koerper in der Szene brauchen.

FUENFMAL DIESELBE ZEILE (01.09.2026)
====================================
`assetCreator/operators.py`, `cloth/erzeugoperatoren.py`,
`cloth/schablonenoperator.py` und zweimal `cloth/operatoren.py`
schrieben jeweils::

    @classmethod
    def poll(cls, context):
        return Vorschausuche.find_body_obj(context) is not None

Das ist keine Eigenheit der einzelnen Operatoren, sondern eine
Bedingung, die sie teilen — und die man an fuenf Stellen aendern
muesste, wenn sich die Suche nach dem Koerper aendert.

WARUM EIN MIXIN OHNE `bpy.types.Operator`
=========================================
Erbt das Mixin selbst von `bpy.types.Operator`, wird es zu einer
anmeldbaren Klasse: Blender fordert dann `bl_idname` und `bl_label`,
und `register_class` versucht es anzumelden. Als reine Python-Klasse
bleibt es unsichtbar und taucht in keiner `classes`-Liste auf.
Dasselbe Muster wie `MitStoff` in `cloth/operatoren.py` und `MitAsset`
in `wardrobe.py`.
"""

from .assetCreator.vorschau.vorschausuche import Vorschausuche

__all__ = ['MitKoerper']


class MitKoerper:
    u"""Nur brauchbar, solange ein HumanBody-Koerper in der Szene ist."""

    @classmethod
    def poll(cls, context):
        return Vorschausuche.find_body_obj(context) is not None
