# -*- coding: utf-8 -*-
import os
import logging
logger = logging.getLogger(__name__)
from ..pfade import Projektpfade
from .prozedural import _PROCEDURAL_ANIMS


# BVH animations live in HumanBody/data (core data repo).
# Die Wurzeln kommen aus `pfade.py` — eine eigene `dirname`-Kette
# zeigte hier eine Ebene zu tief, seit die Datei im Paket liegt.
_TOOLS_ROOT = str(Projektpfade.tools())
_HUMANBODY_ROOT = str(Projektpfade.humanbody())
_BVH_DIR = str(Projektpfade.bvh())


# Animation catalog: file_stem -> description
# Order within each category section defines display order in UI.
_BVH_CATALOG = {
    # MocapNET
    "test_Mocapv4": "MocapNET v4 Test (shuffle dance, Full Body)",
    "testOpenPose": "MocapNET Test (shuffle dance, OpenPose)",
    "testMediaPipe": "MocapNET Test (shuffle dance, MediaPipe)",
    "mocapnet_sample": "CMU Sample (164 joints)",
    "mocapnet_tpose": "T-Pose",
    "mocapnet_help": "Help Gesture",
    "mocapnet_push": "Push Gesture",
    "mocapnet_doubleclap": "Double Clap",
    "mocapnet_handsup": "Hands Up",
    "mocapnet_leftkick": "Left Kick",
    "mocapnet_rightkick": "Right Kick",
    "mocapnet_waveleft": "Wave Left",
    "mocapnet_waveright": "Wave Right",
    "mocapnet_lefthandcircle": "Left Hand Circle",
    "mocapnet_righthandcircle": "Right Hand Circle",
    # Walk
    "walk_short": "Walk (short)",
    "01_01": "playground - forward jumps, turn around",
    "05_01": "walk",
    "02_02": "walk",
    "03_01": "walk on uneven terrain",
    "133_14": "Walk Left",
    "133_17": "Walk Right",
    "133_07": "Walk Jump",
    "133_24": "Walk ZigZag",
    "136_12": "Walk Backwards Crouched",
    "136_28": "Walk on Toes",
    "141_29": "Random Walk",
    "139_12": "Run in Circles",
    "137_37": "Sexy Lady Wait",
    "01_04": "playground - climb",
    "01_13": "playground - climb, go under, jump down",
    "01_14": "playground - climb, jump down, dangle, legs push off against",
    "13_26": "direct traffic, wave",
    "13_27": "direct traffic, wave, point",
    "13_28": "direct traffic, wave, point",
    # Sport
    "02_07": "swordplay",
    "02_03": "run/jog",
    "02_04": "jump, balance",
    "02_05": "punch/strike",
    "02_06": "bend over, scoop up, rise, lift arm",
    "02_08": "swordplay",
    "02_10": "wash self",
    "03_02": "walk on uneven terrain",
    "03_03": "walk on uneven terrain",
    "03_04": "walk on uneven terrain",
    "13_13": "forward jump",
    # Dance
    "64_01": "Swing",
    "61_01": "salsa dance",
    "61_02": "salsa dance",
    "05_02": "expressive arms, pirouette",
    "05_03": "sideways arabesque, turn step, folding arms",
    "05_04": "sideways arabesque, folding arms, bending back",
    "05_05": "cou-de-pied, raised leg, jete en tourant",
    "05_06": "cartwheel-like, pirouettes, jete",
    "05_07": "small jetes, attitude, pirouette, turn",
    "05_08": "rond de jambe, jete, turn",
    "05_09": "glissade devant, derriere, arabesque",
    "05_10": "glissade devant, derriere, arabesque",
    "05_11": "sideways steps, pirouette",
    "05_12": "arms high, pointe tendue, rotation",
    "05_13": "small jetes, pirouette",
    "05_14": "retire derriere, arabesque",
    "05_15": "retire derriere, arabesque",
    "05_16": "coupe dessous, jete en tourant",
    "05_17": "coupe dessous, grand jete en tourant",
    "05_18": "arabesque, jete en tourant, bending back",
    "05_19": "arabesque, jete en tourant, bending back",
    "05_20": "arabesque, jete en tourant, bending back",
    # Home
    "13_07": "unscrew bottlecap, drink soda",
    "13_14": "laugh",
    "13_15": "laugh",
    "13_16": "laugh",
    "13_17": "boxing",
    "13_18": "boxing",
    "13_19": "forward jump",
    "13_20": "wash windows",
    "13_21": "wash windows",
    "13_22": "wash windows",
    "13_23": "sweep floor",
    "13_24": "sweep floor",
    "13_25": "sweep floor",
    "13_08": "unscrew bottlecap, drink soda, screw on bottlecap",
    "13_09": "drink soda",
    "13_10": "jump up to grab, reach for, tiptoe",
    "13_11": "forward jump",
    "13_12": "jump up to grab, reach for, tiptoe",
    "14_10": "wash windows",
    "14_11": "wash windows",
    "14_12": "wash windows",
    "14_13": "mop floor",
    "14_14": "jumping jacks, jog, squats, side twists, stretches",
    "14_15": "mop floor",
    "14_16": "sweep floor",
}


_ANIM_CATEGORIES = [
    ("MocapNET", 'OUTLINER_OB_ARMATURE'),
    ("Walk",  'ANIM_DATA'),
    ("Sport", 'POSE_HLT'),
    ("Dance", 'OUTLINER_OB_CURVES'),
    ("Home",  'HOME'),
]


# Prefix for procedural animation paths (not real files)
_PROC_PREFIX = "@proc:"


def _list_animations():
    """Return dict: category -> [(label, path_or_proc_key), ...]

    Scans BVH directories AND adds procedural animations.
    Labels come from _BVH_CATALOG if available, otherwise from filename.
    """
    result = {}
    if os.path.isdir(_BVH_DIR):
        for cat_name, _ in _ANIM_CATEGORIES:
            cat_dir = os.path.join(_BVH_DIR, cat_name)
            if not os.path.isdir(cat_dir):
                continue
            # Build set of available files in this category
            available = {}
            for fname in os.listdir(cat_dir):
                if fname.endswith(".bvh"):
                    available[fname[:-4]] = os.path.join(cat_dir, fname)
            items = []
            # Add files in catalog order first
            for stem in _BVH_CATALOG:
                if stem in available:
                    items.append((_BVH_CATALOG[stem], available.pop(stem)))
            # Then any remaining files not in catalog (alphabetical)
            for stem in sorted(available):
                items.append((stem.replace("_", " "), available[stem]))
            if items:
                result[cat_name] = items

    # Add procedural animations by category
    for key, (label, cat, _func) in _PROCEDURAL_ANIMS.items():
        cat_list = result.setdefault(cat, [])
        cat_list.insert(0, (label, _PROC_PREFIX + key))

    return result
