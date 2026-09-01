# -*- coding: utf-8 -*-
import logging
import bpy
from ..rigaktionen import _assign_action
logger = logging.getLogger(__name__)
from .gesten_koerper import _gen_clap
from .gesten_kopf import _gen_greeting
from .gesten_koerper import _gen_hands_on_hips
from .gesten_koerper import _gen_idle
from .gesten_kopf import _gen_look_around
from .gesten_kopf import _gen_nod_yes
from .gangarten import _gen_run
from .gesten_kopf import _gen_shake_no
from .gesten_koerper import _gen_stretch
from .gesten_koerper import _gen_wave
from .gesten_koerper import _gen_weight_shift


_PROCEDURAL_ANIMS = {
    "run":           ("Run",               "Walk",  _gen_run),
    "idle":          ("Idle (breathing)",   "Home",  _gen_idle),
    "wave":          ("Wave hand",          "Home",  _gen_wave),
    "nod_yes":       ("Nod yes",            "Home",  _gen_nod_yes),
    "shake_no":      ("Shake head no",      "Home",  _gen_shake_no),
    "look_around":   ("Look around",        "Home",  _gen_look_around),
    "stretch":       ("Stretch arms",       "Home",  _gen_stretch),
    "greeting":      ("Greeting bow",       "Home",  _gen_greeting),
    "hands_on_hips": ("Hands on hips",      "Home",  _gen_hands_on_hips),
    "clap":          ("Clapping",           "Home",  _gen_clap),
    "weight_shift":  ("Weight shift",       "Home",  _gen_weight_shift),
}


def _generate_procedural(rig, proc_key):
    """Generate a procedural animation on *rig*.

    Returns (action, f_start, f_end).
    """
    label, _cat, gen_func = _PROCEDURAL_ANIMS[proc_key]
    act_name = f"HB_Proc_{proc_key}"

    act = bpy.data.actions.new(act_name)
    _assign_action(rig, act)

    f_start, f_end = gen_func(rig)
    logger.info("Generated procedural: %s (%s frames)",
                label, f_end - f_start + 1)
    return act, f_start, f_end
