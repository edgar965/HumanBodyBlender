# Skeleton classes moved to humanbody_core — re-export for backwards compatibility
from humanbody_core.skeleton.mapping import *  # noqa: F401,F403
from humanbody_core.skeleton.mapping import (
    rigify_face_bones,
    HumanLimb,
    SimpleFace,
    HumanSpine,
    HumanArm,
    HumanLeg,
    HumanFingers,
)
from humanbody_core.skeleton.skeleton import (
    Skeleton, SkeletonRigify, SkeletonMeta,
)
# Backwards-compat aliases
HumanSkeleton = Skeleton
RigifySkeleton = SkeletonRigify
RigifyMeta = SkeletonMeta
