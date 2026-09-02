# -*- coding: utf-8 -*-
import logging
import bpy
from ..rigaktionen import Rigaktionen
logger = logging.getLogger(__name__)
from .gangarten import Gangarten
from .gesten_kopf import Kopfgesten
from .gesten_koerper import Koerpergesten


_PROCEDURAL_ANIMS = {
    "run":           ("Run",               "Walk",  Gangarten._gen_run),
    "idle":          ("Idle (breathing)",   "Home",  Koerpergesten._gen_idle),
    "wave":          ("Wave hand",          "Home",  Koerpergesten._gen_wave),
    "nod_yes":       ("Nod yes",            "Home",  Kopfgesten._gen_nod_yes),
    "shake_no":      ("Shake head no",      "Home",  Kopfgesten._gen_shake_no),
    "look_around":   ("Look around",        "Home",  Kopfgesten._gen_look_around),
    "stretch":       ("Stretch arms",       "Home",  Koerpergesten._gen_stretch),
    "greeting":      ("Greeting bow",       "Home",  Kopfgesten._gen_greeting),
    "hands_on_hips": ("Hands on hips",      "Home",  Koerpergesten._gen_hands_on_hips),
    "clap":          ("Clapping",           "Home",  Koerpergesten._gen_clap),
    "weight_shift":  ("Weight shift",       "Home",  Koerpergesten._gen_weight_shift),
}


class Prozedural:
    u"""Die frueheren Modulfunktionen, gebuendelt."""

    @staticmethod
    def _generate_procedural(rig, proc_key):
        """Generate a procedural animation on *rig*.

        Returns (action, f_start, f_end).
        """
        label, _cat, gen_func = _PROCEDURAL_ANIMS[proc_key]
        act_name = f"HB_Proc_{proc_key}"

        act = bpy.data.actions.new(act_name)
        Rigaktionen._assign_action(rig, act)

        f_start, f_end = gen_func(rig)
        logger.info("Generated procedural: %s (%s frames)",
                    label, f_end - f_start + 1)
        return act, f_start, f_end
