# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Die Kopien, die der BVH-Vergleich nebeneinander stellt.

Die Helfer standen als verschachtelte Funktionen IN
`HUMANBODY_OT_load_bvh_native.execute` — zusammen 64 der 257 Zeilen. Sie
haben mit dem Ablauf nichts zu tun: Sie kopieren ein Rig samt Netzen
und stellen es auf denselben Boden wie das mittlere.

Was frueher aus dem Umfeld kam (`context`, `rig`), steht jetzt in der
Aufrufliste. Damit sind sie einzeln zu lesen — und einzeln pruefbar,
was sie als Verschachtelung nie waren.

DER DRITTE HELFER WAR TOT. `_style_preview_rig` (12 Zeilen) hat die
Strichdarstellung gesetzt und wurde von niemandem gerufen — in der
Verschachtelung faellt so etwas nicht auf, weil kein Werkzeug in einen
Funktionsrumpf hineinsieht. Er ist beim Umzug entfallen.
"""
import logging

import bpy

logger = logging.getLogger(__name__)


class Vorschaurigs:
    u"""Kopieren und ausrichten — je ein Schritt fuer sich."""

    @staticmethod
    def kopieren(context, vorlage, name_prefix):
        u"""Tiefe Kopie eines Rigs mit seinen Netzkindern.

        Kopiert werden auch die Zwangsbedingungen und die Treiber, die auf
        das Original zeigen — sonst haengt die Kopie am Original und folgt
        dessen Bewegung statt der eigenen.
        """
        try:
            rc = vorlage.copy()
            rc.data = vorlage.data.copy()
            rc.name = f"{name_prefix}_Preview"
            context.collection.objects.link(rc)
            for pb in rc.pose.bones:
                for c in pb.constraints:
                    if hasattr(c, 'target') and c.target == vorlage:
                        c.target = rc
            if rc.data.animation_data:
                for drv_fc in rc.data.animation_data.drivers:
                    for var in drv_fc.driver.variables:
                        for tgt in var.targets:
                            if tgt.id == vorlage:
                                tgt.id = rc
            Vorschaurigs._netze_kopieren(context, vorlage, rc, name_prefix)
            return rc
        except Exception as e:
            logger.exception("Rig-Kopie fehlgeschlagen")
            logger.warning("Rig copy '%s' failed: %s", name_prefix, e)
            return None

    @staticmethod
    def _netze_kopieren(context, vorlage, rc, name_prefix):
        u"""Die Netzkinder mitnehmen — an die Kopie gehaengt, ohne Stoffsim.

        Die Stoff-Modifikatoren werden abgeschaltet: Drei Rigs
        nebeneinander mit laufender Simulation bringen die Wiedergabe zum
        Stehen, und verglichen wird die Bewegung, nicht der Faltenwurf.
        """
        for child in list(vorlage.children):
            if child.type != 'MESH':
                continue
            mc = child.copy()
            mc.data = child.data.copy()
            mc.name = f"{name_prefix}_{child.name}"
            context.collection.objects.link(mc)
            mc.parent = rc
            mc.parent_type = child.parent_type
            mc.parent_bone = child.parent_bone
            mc.matrix_parent_inverse = child.matrix_parent_inverse.copy()
            for mod in mc.modifiers:
                if mod.type == 'ARMATURE' and mod.object == vorlage:
                    mod.object = rc
                if mod.type == 'CLOTH':
                    mod.show_viewport = False
                    mod.show_render = False

    @staticmethod
    def ausrichten(rc, ground_z, center_root_pos):
        u"""Auf denselben Boden und dieselbe Tiefe wie das mittlere Rig.

        Ohne das stehen die drei Fassungen auf verschiedenen Hoehen, und
        der Vergleich zeigt vor allem den Versatz.
        """
        if not rc or rc.name not in bpy.data.objects:
            return
        for fname in ("foot_fk.L", "ORG-foot.L", "DEF-foot.L"):
            pb = rc.pose.bones.get(fname)
            if pb:
                foot = (rc.matrix_world @ pb.matrix).to_translation()
                rc.location.z -= (foot.z - ground_z)
                break
        root_pb = rc.pose.bones.get("root")
        if root_pb:
            rpos = (rc.matrix_world @ root_pb.matrix).to_translation()
            rc.location.y -= (rpos.y - center_root_pos.y)
