# -*- coding: utf-8 -*-
u"""Der Dreifachvergleich: BVH-Skelett | Rokoko | KBS.

AUFGETEILT (01.09.2026)
=======================
`execute` war 139 Zeilen (davor 257). Was jetzt daneben liegt:

    vorschauaufraeumen.py  die Objekte des letzten Laufs wegraeumen
    retargetlauf.py        ein Retarget auf einer Wegwerfkopie
    vergleichsaufbau.py    Skelett, Tiefe, Hoehe, Abspielbereich
    vorschaurigs.py        die Kopien und ihre Ausrichtung

Die beiden Retargets standen als zwei fast gleiche Bloecke untereinander
— rund fuenfundzwanzig Zeilen je Fall, die sich in drei Namen
unterschieden. Jetzt sind es zwei Aufrufe.
"""
import os
import logging
import bpy
from ..rigaktionen import Rigaktionen
from ..retarget import Rokoko
from ..retarget_teile.kbs import Kbsanbindung
logger = logging.getLogger(__name__)
from ..charakter.charakterpruefung import Charakterpruefung
from .vergleichsaufbau import Vergleichsaufbau
from .vorschaurigs import Vorschaurigs
from .vorschauaufraeumen import Vorschauaufraeumen
from .retargetlauf import Retargetlauf
from .viewport import Ansichtsfenster


class HUMANBODY_OT_load_bvh_native(bpy.types.Operator):
    bl_idname = "humanbody.load_bvh_native"
    bl_label = "BVH Compare"
    bl_description = (
        "3-way compare: BVH skeleton | Rokoko | KBS retarget"
    )
    bl_options = {'REGISTER', 'UNDO'}

    bvh_path: bpy.props.StringProperty()
    anim_name: bpy.props.StringProperty()

    def execute(self, context):
        obj, rig = self._pruefen(context)
        if not rig:
            return {'CANCELLED'}

        # --- Parse BVH file info ---
        bvh_fps, bvh_nframes = Rigaktionen._parse_bvh_info(self.bvh_path)

        context.scene.render.fps = bvh_fps
        context.scene.render.fps_base = 1.0

        # --- Cleanup previous previews ---
        Vorschauaufraeumen.alle_weg()
        Ansichtsfenster._cleanup_old_anim(context, rig)
        Ansichtsfenster._set_cloth_viewport(False)
        Ansichtsfenster._optimize_viewport(context)

        # ============================================================
        # PHASE 1: Retargets on temp copies (no BVH_Preview yet)
        # ============================================================
        act, act_kbs, f_end = self._retargets(context, rig)

        # ============================================================
        # PHASE 2: Display setup (retargets done, scene is clean)
        # ============================================================
        self._aufstellen(context, rig, act_kbs)
        Vergleichsaufbau.abspielen(context, obj,
                                   max(bvh_nframes, f_end if act else 1))

        fname = os.path.basename(self.bvh_path)
        self.report({'INFO'},
                    f"3-way: BVH | Rokoko | KBS — {fname}")
        return {'FINISHED'}

    # ------------------------------------------------------------ Bausteine

    def _pruefen(self, context):
        u"""(Objekt, Rig) — oder (None, None) mit einer Meldung."""
        if not os.path.isfile(self.bvh_path):
            self.report({'ERROR'}, f"BVH not found: {self.bvh_path}")
            return None, None
        return Charakterpruefung.rig_holen(context, self)

    def _retargets(self, context, rig):
        u"""Beide Retargets fahren. Zurueck: (Rokoko, KBS, letztes Bild).

        Die Rokoko-Aktion landet direkt auf dem echten Rig — sie ist die
        mittlere Spalte des Vergleichs. Die KBS-Aktion wird nur benannt;
        sie kommt spaeter auf die rechte Kopie.
        """
        act, _f_start, f_end = Retargetlauf.holen(
            context, rig, self.bvh_path, "TMP_rok_retarget",
            Rokoko.retarget_rokoko)
        if act:
            act.name = f"HB_Anim_{self.anim_name}"
            Rigaktionen._assign_action(rig, act)
        else:
            self.report({'WARNING'}, "Rokoko retarget failed")

        act_kbs, _, _ = Retargetlauf.holen(
            context, rig, self.bvh_path, "TMP_kbs_retarget",
            Kbsanbindung.retarget_kbs, praefix="HB_KBS", nachsilbe="_kbs")
        if act_kbs:
            act_kbs.name = f"HB_KBS_{self.anim_name}"
        else:
            logger.warning("KBS retarget failed")
        return act, act_kbs, f_end

    def _aufstellen(self, context, rig, act_kbs):
        u"""Die drei Spalten nebeneinander stellen und ausrichten.

        Links das rohe BVH-Skelett, in der Mitte das echte Rig mit der
        Rokoko-Aktion, rechts eine Kopie mit der KBS-Aktion. Ausgerichtet
        wird bei Bild 1 — vorher steht jedes Rig in seiner Ruhelage, und
        die Fusshoehen haetten keinen Bezug zueinander.
        """
        # ---- LEFT: BVH native skeleton (filtered to mapped bones) ----
        bvh_rig = Vergleichsaufbau.bvh_skelett(context, self.bvh_path, rig)

        # ---- CENTER: Main rig with Rokoko action ----
        rig.location.x = 0.0

        # ---- RIGHT: KBS copy with KBS action ----
        rig_kbs = Vorschaurigs.kopieren(context, rig, "KBS")
        if rig_kbs:
            rig_kbs.location.x = 2.0
            if act_kbs:
                Rigaktionen._assign_action(rig_kbs, act_kbs)

        # ---- Align all models at frame 1 ----
        bpy.context.scene.frame_set(1)
        bpy.context.view_layer.update()
        Vergleichsaufbau.tiefe_angleichen(bvh_rig, rig)
        ground_z, center_root = Vergleichsaufbau.bezugspunkte(rig)
        Vergleichsaufbau.hoehe_angleichen(bvh_rig, ground_z)
        Vorschaurigs.ausrichten(rig_kbs, ground_z, center_root)
