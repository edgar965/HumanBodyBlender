# -*- coding: utf-8 -*-
import logging
from ..rigaktionen import _get_action_fcurves
logger = logging.getLogger(__name__)


def _extract_fcurve_data(act, bone_names):
    """Save keyframe data for bones from an action.

    Returns {(data_path, array_index): [(frame, value, handle_left, handle_right), ...]}
    """
    saved = {}
    for fc in _get_action_fcurves(act):
        for bname in bone_names:
            if f'"{bname}"' in fc.data_path:
                kps = []
                for kp in fc.keyframe_points:
                    kps.append((kp.co[0], kp.co[1],
                                (kp.handle_left[0], kp.handle_left[1]),
                                (kp.handle_right[0], kp.handle_right[1]),
                                kp.interpolation))
                saved[(fc.data_path, fc.array_index)] = kps
                break
    return saved


def _apply_fcurve_data(act, saved, rig=None):
    """Overwrite fcurves in act with previously saved keyframe data.

    If *rig* is given, also creates NEW fcurves for saved entries that have
    no matching fcurve in *act* (required for merging spine data into a
    Rokoko action that only contains limb rotations).
    """
    applied = set()
    for fc in _get_action_fcurves(act):
        key = (fc.data_path, fc.array_index)
        kps_data = saved.get(key)
        if not kps_data:
            continue
        applied.add(key)
        while len(fc.keyframe_points) < len(kps_data):
            fc.keyframe_points.insert(kps_data[0][0], kps_data[0][1])
        for i, (frame, value, hl, hr, interp) in enumerate(kps_data):
            if i < len(fc.keyframe_points):
                kp = fc.keyframe_points[i]
                kp.co = (frame, value)
                kp.handle_left = hl
                kp.handle_right = hr
                kp.interpolation = interp
        fc.update()

    missing = {k: v for k, v in saved.items() if k not in applied}
    if not missing or not rig:
        return

    new_fc_fn = None
    try:
        new_fc_fn = act.fcurves.new
        act.fcurves.new  # verify attribute exists
    # stumm gewollt: Die API-Weiche selbst: Fehlt act.fcurves.new, ist es eine
    # Layered Action und der Weg darunter greift.
    except Exception:
        new_fc_fn = None
    if not new_fc_fn:
        try:
            layer = act.layers[0]
            strip = layer.strips[0]
            slot = rig.animation_data.action_slot
            cb = strip.channelbag(slot, ensure=True)
            new_fc_fn = cb.fcurves.new
        except Exception:
            logger.info("WARNING: cannot create fcurves in %s", act.name)
            return

    created = 0
    for (data_path, array_index), kps_data in missing.items():
        fc = new_fc_fn(data_path=data_path, index=array_index)
        for frame, value, hl, hr, interp in kps_data:
            kp = fc.keyframe_points.insert(frame, value)
            kp.handle_left = hl
            kp.handle_right = hr
            kp.interpolation = interp
        fc.update()
        created += 1
    if created:
        logger.info("created %s new fcurves in %s", created, act.name)
