# -*- coding: utf-8 -*-
import math
import logging
from mathutils import Quaternion, Euler, Vector
logger = logging.getLogger(__name__)


def _deg(x, y, z):
    """Euler degrees in bone-local space -> Quaternion.

    For spine/head/neck bones (local axes ~ world axes):
      X rotation: +lean_back / -lean_forward
      Y rotation: +turn_right / -turn_left
      Z rotation: +tilt_left  / -tilt_right

    For thigh/shin (local X ~ world right):
      +X = hip/knee flexion (leg forward / knee bend)
      -X = extension

    For forearm (local X ~ vertical):
      -X = elbow flexion (bend)
      +X = elbow extension
    """
    return Euler((math.radians(x), math.radians(y), math.radians(z))).to_quaternion()


def _wrot(pb, *axis_angle_pairs):
    """World-space rotation(s) -> bone rotation_quaternion.

    Each pair is ((wx, wy, wz), angle_deg).  Applied in order.

    World axes: X = right, Y = forward, Z = up.
    """
    world_rot = Quaternion((1, 0, 0, 0))
    for axis, angle in axis_angle_pairs:
        world_rot = Quaternion(Vector(axis), math.radians(angle)) @ world_rot
    rest_q = pb.bone.matrix_local.to_3x3().to_quaternion()
    return rest_q.conjugated() @ world_rot @ rest_q


def _kf(bone, frame):
    """Insert rotation_quaternion keyframe on *bone* at *frame*."""
    bone.keyframe_insert(data_path="rotation_quaternion", frame=frame)


def _kf_loc(bone, frame):
    """Insert location keyframe on *bone* at *frame*."""
    bone.keyframe_insert(data_path="location", frame=frame)


def _pb(rig, name):
    """Get pose bone by name, or None."""
    return rig.pose.bones.get(name)
