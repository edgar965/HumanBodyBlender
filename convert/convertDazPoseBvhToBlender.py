"""Retarget Daz/Poser BVH motion capture onto a Blender Rigify rig.

Provides:
  - retarget_bvh(context, rig, bvh_path) — load and retarget a BVH file

Uses the Diffeomorphic retarget_bvh module (convert/retarget_bvh/) for
T-pose alignment and frame-by-frame retargeting.

Die Knochennamen-Tabelle und der BVH-Umbenenner liegen seit dem
01.09.2026 in `dazknochennamen.py` — sie brauchen kein Blender.

AUFGETEILT (01.09.2026)
=======================
`retarget_bvh` war 144 Zeilen und tat vier Dinge nacheinander. Drei
davon liegen jetzt daneben:

    dazbvhladen.py    der Loader mit der Daz-Ausrichtung (-Z / Y)
    dazausrichten.py  Armaturen zuordnen, Groesse angleichen
    dazuebertragen.py die Bilder in Bloecken uebertragen

Uebrig bleibt der Ablauf mit seinem `try/finally` — und das ist der
Grund fuer die Klammer: Die Quellarmatur MUSS am Ende weg, auch wenn
mittendrin etwas schiefgeht. Sonst bleibt ein `Y_`-Rig in der Szene
liegen, und der naechste Lauf findet zwei.

Usage from morphing.py:
    from .convert.convertDazPoseBvhToBlender import retarget_bvh
    act, f_start, f_end = retarget_bvh(context, rig, bvh_path)
"""

import logging
import os
import sys

from .dazausrichten import Dazausrichten
from .dazbvhladen import Dazbvhladen
from .dazuebertragen import Dazuebertragen

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# BVH Retargeting (requires Blender + retarget_bvh module)
# ---------------------------------------------------------------------------

# Bones to exclude (MCH parent mismatch in Rigify causes twist)
_SKIP_BONES = {"head"}


class Dazretarget:
    u"""Der Ablauf: BVH laden, ausrichten, uebertragen, aufraeumen."""

    #: Ist das Fremdmodul `retarget_bvh` schon geladen?
    bereit = False

    @staticmethod
    def _init_retarget():
        """Register retarget_bvh module on first use."""
        if Dazretarget.bereit:
            return

        import bpy

        convert_dir = os.path.dirname(os.path.abspath(__file__))
        if convert_dir not in sys.path:
            sys.path.insert(0, convert_dir)

        if not hasattr(bpy.types.PoseBone, 'bvh_retargeter'):
            # `retarget_bvh` heisst hier ZWEIERLEI: das Fremdmodul und die
            # Methode darunter. Beim Buendeln der frueheren Modulfunktionen
            # wurde daraus `Dazretarget.retarget_bvh.register()` — ein
            # Aufruf auf die eigene Methode, der beim ersten Daz-BVH mit
            # `AttributeError` gefallen waere. Der Aliasname haelt die
            # beiden auseinander.
            import retarget_bvh as retarget_erweiterung
            retarget_erweiterung.register()

        from retarget_bvh.bsettings import BD
        if BD.prefs is None:
            class _Prefs:
                verbose = False
                useLimits = False
                useUnlock = False
                ignoreLeafBones = False
                useBlenderBvh = False
                useNativeFbx = False
            BD.prefs = _Prefs()

        Dazretarget.bereit = True

    @staticmethod
    def retarget_bvh(context, rig, bvh_path):
        """Load a Daz3D/CMU BVH file and retarget onto a Rigify rig.

        Args:
            context: Blender context
            rig: Target Rigify armature object
            bvh_path: Path to .bvh file

        Returns:
            (action, frame_start, frame_end)
        """
        Dazretarget._init_retarget()

        from retarget_bvh.bsettings import BD, mcpRna as mcp
        from retarget_bvh.load import activateObject, deleteSourceRig

        scn = context.scene
        BD.ensureInited(scn)
        activateObject(context, rig)

        srcRig = Dazbvhladen.lesen(context, bvh_path)

        try:
            Dazausrichten.zuordnen(context, rig, srcRig, scn)
            Dazausrichten.groesse_angleichen(context, rig, srcRig)
            mcp(srcRig).Renamed = True

            act, f_start, f_end = Dazuebertragen.fahren(
                context, rig, srcRig, scn, _SKIP_BONES)
        finally:
            deleteSourceRig(context, srcRig, 'Y_')

        return act, f_start, f_end


#: Die frueheren Modulnamen — die Importpfade von
#: aussen bleiben damit unveraendert. `zuweisungen_weg`
#: nimmt sie, sobald niemand sie mehr holt.
_init_retarget = Dazretarget._init_retarget
retarget_bvh = Dazretarget.retarget_bvh
