# -*- coding: utf-8 -*-
import os
import logging
import bpy
from ..rigaktionen import _set_fk_mode, _assign_action, _get_action_fcurves
logger = logging.getLogger(__name__)


def _get_retarget_func():
    """Import retarget function from convert module."""
    from .convert.convertDazPoseBvhToBlender import retarget_bvh
    return retarget_bvh


def _get_cache_dir():
    """Return path to animation cache directory (auto-created)."""
    d = os.path.join(os.path.dirname(__file__), "cache")
    os.makedirs(d, exist_ok=True)
    return d


def _load_cached_action(rig, bvh_path, prefix="HB_Anim", cache_suffix=""):
    """Try loading a cached action from cache/{stem}{cache_suffix}.blend.

    Returns (action, f_start, f_end) or (None, 0, 0).
    """
    stem = os.path.splitext(os.path.basename(bvh_path))[0]
    blend_path = os.path.join(_get_cache_dir(), f"{stem}{cache_suffix}.blend")
    if not os.path.isfile(blend_path):
        return None, 0, 0

    action_name = f"{prefix}_{stem}"

    try:
        with bpy.data.libraries.load(blend_path) as (data_from, data_to):
            if not data_from.actions:
                return None, 0, 0
            # Load the first (only) action, rename after
            data_to.actions = [data_from.actions[0]]

        act = data_to.actions[0]
        if not act:
            return None, 0, 0

        act.name = action_name

        # Assign to rig
        _assign_action(rig, act)

        # Determine frame range from fcurves
        fcs = _get_action_fcurves(act)
        if fcs:
            frames = set()
            for fc in fcs:
                for kp in fc.keyframe_points:
                    frames.add(int(kp.co[0]))
            if frames:
                f_start = min(frames)
                f_end = max(frames)
                logger.info("Cache hit: %s (%s frames)",
                            action_name, f_end - f_start + 1)
                _set_fk_mode(rig)
                return act, f_start, f_end

        logger.info("Cache hit: %s (no keyframes, default range)", action_name)
        _set_fk_mode(rig)
        return act, 1, 250
    except Exception as e:
        logger.warning("Cache load failed: %s", e)
        return None, 0, 0


def _save_action_cache(bvh_path, act, cache_suffix=""):
    """Save a retargeted action to cache/{stem}{cache_suffix}.blend."""
    stem = os.path.splitext(os.path.basename(bvh_path))[0]
    blend_path = os.path.join(_get_cache_dir(), f"{stem}{cache_suffix}.blend")
    try:
        bpy.data.libraries.write(blend_path, {act}, fake_user=True)
        logger.info("Cached: %s → %s", act.name, blend_path)
    except Exception as e:
        logger.warning("Cache save failed: %s", e)
