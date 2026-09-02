# -*- coding: utf-8 -*-
import math
import logging
from mathutils import Vector
from .pinselzustand import Pinselzustand
logger = logging.getLogger(__name__)


class Pinsel:
    u"""Die frueheren Modulfunktionen, gebuendelt."""

    @staticmethod
    def _draw_brush_circle():
        """GPU overlay: draw a circle on the mesh surface at the brush position."""
        if not Pinselzustand.aktiv or Pinselzustand.mitte is None:
            return

        import gpu
        from gpu_extras.batch import batch_for_shader

        center = Pinselzustand.mitte
        normal = Pinselzustand.normale
        radius = Pinselzustand.radius

        # Build a tangent frame on the surface
        if abs(normal.dot(Vector((0, 0, 1)))) < 0.99:
            tangent = normal.cross(Vector((0, 0, 1))).normalized()
        else:
            tangent = normal.cross(Vector((1, 0, 0))).normalized()
        bitangent = normal.cross(tangent).normalized()

        # Circle vertices (32 segments)
        segments = 32
        coords = []
        for i in range(segments + 1):
            angle = 2.0 * math.pi * i / segments
            pt = (center
                  + tangent * (math.cos(angle) * radius)
                  + bitangent * (math.sin(angle) * radius))
            coords.append(pt)

        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": coords})

        gpu.state.blend_set('ALPHA')
        gpu.state.depth_test_set('LESS_EQUAL')
        gpu.state.line_width_set(2.0)

        shader.bind()
        shader.uniform_float("color", (1.0, 0.6, 0.1, 0.85))
        batch.draw(shader)

        gpu.state.blend_set('NONE')
        gpu.state.depth_test_set('NONE')
        gpu.state.line_width_set(1.0)
