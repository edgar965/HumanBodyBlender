# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Was vom vorigen Animationslauf uebrig ist, wegraeumen.

AUS `Ansichtsfenster._cleanup_old_anim` HERAUSGELOEST (01.09.2026)
==================================================================
Die Methode war mit 33 Verzweigungen die verschachteltste Funktion im
ganzen Addon (Rang E). Sie tat fuenf Dinge hintereinander, die nichts
miteinander zu tun haben — die Wiedergabe anhalten, Zwaenge loesen, die
Aktion abhaengen, die Pose nullen, alte Objekte entfernen — und der
groesste Teil ihrer Verzweigungen kam aus ZWEI `if`-Bedingungen mit
zusammen sechzehn `o.name.startswith(…)`-Aufrufen.

`str.startswith` nimmt ein Tupel. Damit werden aus sechzehn
Verzweigungen zwei, und wer einen neuen Vergleichslauf hinzufuegt,
traegt sein Praefix in eine Liste ein statt in eine Bedingung.

WARUM DIE REIHENFOLGE FEST IST
==============================
Erst anhalten, dann aufraeumen: Laeuft die Wiedergabe noch, wertet
Blender bei jedem Bild die Zwaenge aus, die gerade entfernt werden.
Und die Pose wird zuletzt genullt — vorher haenge sie noch an der
Aktion, die eine Zeile darueber abgehaengt wird.

DIE PRAEFIXE UEBERSCHNEIDEN SICH ABSICHTLICH NICHT
===================================================
`ROK_` deckt `ROK_Preview` bereits ab, `RTEST_` deckt `RTEST_Preview`
ab. Die frueheren Doppelungen (beide Formen nebeneinander) sind
entfallen; sie waren wirkungslos, sahen aber nach zwei verschiedenen
Faellen aus. Dieselbe Liste noch einmal in `vorschauaufraeumen.py` —
die raeumt nach einem VERGLEICHSLAUF auf und kennt deshalb `KBS_` und
`TMP_` zusaetzlich, dafuer ohne Typunterscheidung.
"""
import logging

import bpy
from mathutils import Quaternion

logger = logging.getLogger(__name__)

__all__ = ['Altbestand']


class Altbestand:
    u"""Reste des vorigen Animationslaufs."""

    #: Zwaenge mit diesen Namen hat ein frueherer Lauf gesetzt.
    ZWANG_PRAEFIXE = ("hb_anim", "_rt")

    #: Armaturen, die ein Lade- oder Vergleichslauf angelegt hat.
    RIG_PRAEFIXE = (
        "BvhRig",
        "Y_",
        "BVH_Preview",
        "Rig_Preview",
        "_BVH_retarget_tmp",
        "ROK_",
        "ROK46_",
        "RTEST_",
        "_Rokoko_",
    )

    #: Netzkopien, die eine Vorschau angelegt hat.
    NETZ_PRAEFIXE = ("Preview_", "ROK_", "ROK46_", "RTEST_")

    #: Merkmal, das ein eingelesenes BVH-Objekt traegt.
    BVH_MERKMAL = "humanbody_bvh"

    @staticmethod
    def raeumen(context, rig):
        u"""Alles vom vorigen Lauf entfernen — in dieser Reihenfolge."""
        Altbestand._wiedergabe_anhalten(context)
        Altbestand._zwaenge_loesen(rig)
        Altbestand._aktion_loesen(rig)
        Altbestand._pose_nullen(rig)
        Altbestand._objekte_weg()

    @staticmethod
    def _wiedergabe_anhalten(context):
        u"""Die Zeitleiste anhalten, falls sie laeuft."""
        try:
            if context.screen.is_animation_playing:
                bpy.ops.screen.animation_play()
        # stumm gewollt: Die Wiedergabe anzuhalten ist Vorarbeit. Laeuft
        # keine — oder gibt es gar keinen Bildschirm, etwa im
        # Hintergrundlauf —, ist nichts zu tun.
        except Exception:
            pass

    @staticmethod
    def _zwaenge_loesen(rig):
        u"""Zwaenge entfernen, die ein frueherer Lauf gesetzt hat.

        Fremde Zwaenge bleiben stehen: Nur was mit einem unserer
        Praefixe beginnt, stammt von uns.
        """
        for pbone in rig.pose.bones:
            for zwang in list(pbone.constraints):
                if zwang.name.startswith(Altbestand.ZWANG_PRAEFIXE):
                    pbone.constraints.remove(zwang)

    @staticmethod
    def _aktion_loesen(rig):
        u"""Die laufende Aktion abhaengen und, wenn niemand sie mehr
        braucht, aus der Datei entfernen.

        `users == 0` ist die Bedingung: Eine Aktion, die noch woanders
        haengt (ein zweites Rig, ein NLA-Streifen), darf nicht weg.
        """
        if not (rig.animation_data and rig.animation_data.action):
            return
        aktion = rig.animation_data.action
        rig.animation_data.action = None
        if aktion.users == 0:
            bpy.data.actions.remove(aktion)

    @staticmethod
    def _pose_nullen(rig):
        u"""Jeden Posenknochen in die Ruhelage stellen."""
        for pbone in rig.pose.bones:
            pbone.rotation_quaternion = Quaternion((1, 0, 0, 0))
            pbone.rotation_euler = (0, 0, 0)
            pbone.location = (0, 0, 0)

    @staticmethod
    def _objekte_weg():
        u"""Eingelesene BVH-Objekte, Vorschaurigs und Netzkopien entfernen.

        Zurueck kommt die Anzahl. Am Merkmal `humanbody_bvh` haengen
        die eingelesenen Aufnahmen unabhaengig von ihrem Namen — es
        gilt fuer jeden Objekttyp.
        """
        weg = 0
        for o in list(bpy.data.objects):
            if (o.get(Altbestand.BVH_MERKMAL)
                    or (o.type == 'ARMATURE'
                        and o.name.startswith(Altbestand.RIG_PRAEFIXE))
                    or (o.type == 'MESH'
                        and o.name.startswith(Altbestand.NETZ_PRAEFIXE))):
                bpy.data.objects.remove(o, do_unlink=True)
                weg += 1
        if weg:
            logger.info("%d Objekte des vorigen Laufs entfernt", weg)
        return weg
