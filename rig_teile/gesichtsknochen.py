# -*- coding: utf-8 -*-
import logging
logger = logging.getLogger(__name__)


# MCH/ORG bones that carry HumanBody NPZ weights for face geometry.
# Rigify sets use_deform=False on these, but we need them to deform.
_FACE_DEFORM_BONES = [
    "MCH-eye.L", "MCH-eye.R",
    "MCH-lid.B.L.001", "MCH-lid.B.L.002", "MCH-lid.B.L.003",
    "MCH-lid.B.R.001", "MCH-lid.B.R.002", "MCH-lid.B.R.003",
    "MCH-lid.T.L.001", "MCH-lid.T.L.002", "MCH-lid.T.L.003",
    "MCH-lid.T.R.001", "MCH-lid.T.R.002", "MCH-lid.T.R.003",
    "ORG-teeth.B", "ORG-teeth.T",
]


def _enable_face_deform_bones(rig):
    """Enable use_deform on MCH/ORG bones that carry NPZ face weights."""
    count = 0
    for bname in _FACE_DEFORM_BONES:
        bone = rig.data.bones.get(bname)
        if bone and not bone.use_deform:
            bone.use_deform = True
            count += 1
    if count:
        logger.info("Enabled use_deform on %d face bones (MCH/ORG)", count)


def _setup_rigify_properties(rig):
    """Set Rigify custom properties for FK pose mode."""
    torso = rig.pose.bones.get("torso")
    if torso:
        torso["neck_follow"] = 1.0
        torso["head_follow"] = 1.0
