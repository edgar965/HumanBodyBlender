# -*- coding: utf-8 -*-
import os
import logging
from ..pfade import Projektpfade
logger = logging.getLogger(__name__)


# Die Wurzeln kommen aus `pfade.py` — nicht je Datei ausgerechnet.
def _addon_data_dir():
    """Return the addon's data directory."""
    return str(Projektpfade.addon_daten())


def _get_assets_root():
    """Get the parent directory of the addon."""
    return str(Projektpfade.tools())


def _get_autorig_blend_path():
    """Path to the pre-generated AutoRig .blend."""
    local = os.path.join(_addon_data_dir(), "autorig.blend")
    if os.path.isfile(local):
        return local
    return os.path.join(_get_assets_root(), "HumanBodyAssets", "autorig.blend")


def _get_weights_npz_path():
    """Path to the bone weight NPZ file."""
    local = os.path.join(_addon_data_dir(), "weights", "original.npz")
    if os.path.isfile(local):
        return local
    return os.path.join(_get_assets_root(), "HumanBodyAssets",
                        "characters", "mb_female", "weights", "original.npz")


def _get_poses_dir():
    """Path to the pose JSON directory."""
    local = os.path.join(_addon_data_dir(), "poses")
    if os.path.isdir(local):
        return local
    return os.path.join(_get_assets_root(), "HumanBodyAssets",
                        "characters", "mb_female", "poses")
