# SPDX-License-Identifier: GPL-3.0-or-later
#
# Brush-mode modal operator for interactive offset weight painting.

import math
import logging

import bpy
from mathutils import Vector

from .preview import find_preview

logger = logging.getLogger(__name__)

# Module-level brush state
_brush_active = False
_brush_draw_handler = None
_brush_center_3d = None
_brush_normal_3d = None
_brush_radius_world = 0.03


def _draw_brush_circle():
    """GPU overlay: draw a circle on the mesh surface at the brush position."""
    if not _brush_active or _brush_center_3d is None:
        return

    import gpu
    from gpu_extras.batch import batch_for_shader

    center = _brush_center_3d
    normal = _brush_normal_3d
    radius = _brush_radius_world

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


class HUMANBODY_OT_brush_offset(bpy.types.Operator):
    """Interactively paint offset weights on the asset preview"""
    bl_idname = "humanbody.brush_offset"
    bl_label = "Edit Offset"
    bl_description = "Paint offset weights — drag up/down to increase/decrease"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return find_preview(context) is not None

    def invoke(self, context, event):
        global _brush_active, _brush_draw_handler
        global _brush_center_3d, _brush_normal_3d, _brush_radius_world

        preview = find_preview(context)
        if not preview:
            self.report({'WARNING'}, "No preview object found")
            return {'CANCELLED'}

        self._preview = preview
        self._dragging = False
        self._last_mouse_y = 0

        # Ensure vertex group exists
        vg = preview.vertex_groups.get("hb_offset_weight")
        if not vg:
            vg = preview.vertex_groups.new(name="hb_offset_weight")
            vg.add(list(range(len(preview.data.vertices))), 1.0, 'REPLACE')

        self._vg_index = vg.index

        # Read brush settings
        ac = context.scene.humanbody_asset_creator
        _brush_radius_world = ac.brush_radius

        # Install draw handler
        if _brush_draw_handler is not None:
            bpy.types.SpaceView3D.draw_handler_remove(
                _brush_draw_handler, 'WINDOW')
        _brush_draw_handler = bpy.types.SpaceView3D.draw_handler_add(
            _draw_brush_circle, (), 'WINDOW', 'POST_VIEW')

        _brush_active = True
        _brush_center_3d = None
        _brush_normal_3d = None

        context.window.cursor_set('PAINT_BRUSH')
        context.area.header_text_set(
            "Brush: LMB drag up/down to paint — "
            "Wheel to resize — ESC to exit")

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):

        # Viewport navigation pass-through
        if event.type == 'MIDDLEMOUSE':
            return {'PASS_THROUGH'}

        if event.type == 'MOUSEMOVE':
            self._update_brush_pos(context, event)
            if self._dragging:
                delta_y = event.mouse_y - self._last_mouse_y
                self._paint_weights(context, delta_y)
                self._last_mouse_y = event.mouse_y
            if context.area:
                context.area.tag_redraw()
            return {'RUNNING_MODAL'}

        if event.type == 'LEFTMOUSE':
            if event.value == 'PRESS':
                self._dragging = True
                self._last_mouse_y = event.mouse_y
                self._update_brush_pos(context, event)
                return {'RUNNING_MODAL'}
            elif event.value == 'RELEASE':
                self._dragging = False
                return {'RUNNING_MODAL'}

        if event.type == 'WHEELUPMOUSE':
            _brush_radius_world = min(_brush_radius_world * 1.15, 0.2)
            context.scene.humanbody_asset_creator.brush_radius = \
                _brush_radius_world
            if context.area:
                context.area.tag_redraw()
            return {'RUNNING_MODAL'}

        if event.type == 'WHEELDOWNMOUSE':
            _brush_radius_world = max(_brush_radius_world / 1.15, 0.005)
            context.scene.humanbody_asset_creator.brush_radius = \
                _brush_radius_world
            if context.area:
                context.area.tag_redraw()
            return {'RUNNING_MODAL'}

        if event.type in {'RIGHTMOUSE', 'ESC'}:
            self._cleanup(context)
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def cancel(self, context):
        self._cleanup(context)

    def _cleanup(self, context):
        global _brush_active, _brush_draw_handler
        global _brush_center_3d, _brush_normal_3d

        _brush_active = False
        _brush_center_3d = None
        _brush_normal_3d = None

        if _brush_draw_handler is not None:
            bpy.types.SpaceView3D.draw_handler_remove(
                _brush_draw_handler, 'WINDOW')
            _brush_draw_handler = None

        try:
            context.window.cursor_set('DEFAULT')
        # stumm gewollt: Den Mauszeiger zuruecksetzen. Ist das Fenster schon
        # zu, ist der Zeiger es auch.
        except Exception:
            pass
        if context.area:
            context.area.header_text_set(None)
            context.area.tag_redraw()

    def _update_brush_pos(self, context, event):
        """Raycast onto preview mesh and update brush position."""
        global _brush_center_3d, _brush_normal_3d

        from bpy_extras.view3d_utils import (
            region_2d_to_vector_3d, region_2d_to_origin_3d)

        region = context.region
        rv3d = context.region_data
        if rv3d is None:
            return

        coord = (event.mouse_region_x, event.mouse_region_y)
        origin = region_2d_to_origin_3d(region, rv3d, coord)
        direction = region_2d_to_vector_3d(region, rv3d, coord)

        preview = self._preview
        if not preview or preview.name not in bpy.data.objects:
            return

        depsgraph = context.evaluated_depsgraph_get()
        eval_obj = preview.evaluated_get(depsgraph)

        mat_inv = eval_obj.matrix_world.inverted()
        ray_origin = mat_inv @ origin
        ray_dir = mat_inv.to_3x3() @ direction

        hit, loc, normal, _ = eval_obj.ray_cast(ray_origin, ray_dir)
        if hit:
            _brush_center_3d = eval_obj.matrix_world @ loc
            _brush_normal_3d = (
                eval_obj.matrix_world.to_3x3() @ normal).normalized()
        else:
            _brush_center_3d = None
            _brush_normal_3d = None

    def _paint_weights(self, context, delta_y):
        """Modify vertex weights within the brush radius."""
        if _brush_center_3d is None:
            return

        preview = self._preview
        if not preview or preview.name not in bpy.data.objects:
            return

        ac = context.scene.humanbody_asset_creator
        radius = _brush_radius_world
        strength = ac.brush_strength
        sign = 1.0 if delta_y > 0 else -1.0
        intensity = min(abs(delta_y) / 50.0, 1.0)

        vg = preview.vertex_groups.get("hb_offset_weight")
        if not vg:
            return

        mat_w = preview.matrix_world
        mesh = preview.data

        for v in mesh.vertices:
            world_co = mat_w @ v.co
            dist = (world_co - _brush_center_3d).length
            if dist > radius:
                continue

            falloff = 1.0 - (dist / radius)

            # Get current weight
            try:
                current = vg.weight(v.index)
            # stumm gewollt: weight() wirft, wenn der Vertex nicht in der
            # Gruppe ist. Genau das heisst hier Gewicht null.
            except RuntimeError:
                current = 0.0

            delta = strength * sign * falloff * intensity
            new_w = max(0.0, min(1.0, current + delta))
            vg.add([v.index], new_w, 'REPLACE')

        mesh.update()
