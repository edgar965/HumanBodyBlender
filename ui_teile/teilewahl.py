# -*- coding: utf-8 -*-
import bpy
from .zonen import _build_zone_data
from .zonen import _draw_zone_highlight
from .zonen import _position_to_category
from .zustand import Anzeigezustand


class HUMANBODY_OT_pick_part(bpy.types.Operator):
    """Click on the model to select body part categories — ESC to exit"""
    bl_idname = "humanbody.pick_part"
    bl_label = "Pick Part from Model"
    bl_options = {'REGISTER'}

    @classmethod
    def _find_view3d_area(cls, context):
        """Return the first VIEW_3D area in the current screen, or None."""
        if context.area and context.area.type == 'VIEW_3D':
            return context.area
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                return area
        return None

    @classmethod
    def _find_view3d_region(cls, area):
        """Return the WINDOW region inside a VIEW_3D area, or None."""
        if area is None:
            return None
        for r in area.regions:
            if r.type == 'WINDOW':
                return r
        return None

    def modal(self, context, event):

        # Stale modal (superseded by a newer activation) — exit silently
        if self._my_gen != Anzeigezustand.lauf or not Anzeigezustand.wahl_laeuft:
            return {'CANCELLED'}

        # Allow viewport navigation
        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            return {'PASS_THROUGH'}

        if event.type == 'MOUSEMOVE':
            result = self._raycast(context, event)
            new_cat = result or ""
            if new_cat != Anzeigezustand.kategorie_unter_maus:
                Anzeigezustand.kategorie_unter_maus = new_cat
                Anzeigezustand.stapel = None
                if context.area:
                    context.area.tag_redraw()
            if context.area:
                if Anzeigezustand.kategorie_unter_maus:
                    context.area.header_text_set(
                        f"Pick Mode: [{Anzeigezustand.kategorie_unter_maus}] — click to select, ESC to exit")
                else:
                    context.area.header_text_set(
                        "Pick Mode: hover over model — ESC to exit")
            return {'RUNNING_MODAL'}

        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            if Anzeigezustand.kategorie_unter_maus:
                context.scene.humanbody.parts_selected = Anzeigezustand.kategorie_unter_maus
                for area in context.screen.areas:
                    area.tag_redraw()
                self.report({'INFO'}, f"Selected: {Anzeigezustand.kategorie_unter_maus}")
            return {'RUNNING_MODAL'}

        if event.type in {'RIGHTMOUSE', 'ESC'}:
            self._do_cleanup(context)
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def invoke(self, context, event):

        # Find a VIEW_3D area — required for modal events and raycasting
        v3d_area = self._find_view3d_area(context)
        if v3d_area is None:
            self.report({'WARNING'}, "No 3D Viewport found")
            return {'CANCELLED'}
        v3d_region = self._find_view3d_region(v3d_area)

        # Toggle off — cleanup immediately, stale modal will auto-exit
        if Anzeigezustand.wahl_laeuft:
            Anzeigezustand.lauf += 1      # Invalidate any running modal
            self._do_cleanup(context)
            return {'FINISHED'}

        # Find the HumanBody object
        obj = context.active_object
        if not obj or not obj.data.get("humanbody"):
            for o in context.scene.objects:
                if o.type == 'MESH' and o.data.get("humanbody"):
                    obj = o
                    break
        if not obj:
            self.report({'WARNING'}, "No HumanBody object found")
            return {'CANCELLED'}

        # Set up new pick mode session
        Anzeigezustand.lauf += 1
        self._my_gen = Anzeigezustand.lauf

        Anzeigezustand.zonendreiecke, Anzeigezustand.flaeche_zu_kategorie = _build_zone_data(obj, context)

        if Anzeigezustand.zeichner is not None:
            bpy.types.SpaceView3D.draw_handler_remove(Anzeigezustand.zeichner, 'WINDOW')
        Anzeigezustand.zeichner = bpy.types.SpaceView3D.draw_handler_add(
            _draw_zone_highlight, (), 'WINDOW', 'POST_VIEW')

        Anzeigezustand.wahl_laeuft = True
        Anzeigezustand.kategorie_unter_maus = ""
        Anzeigezustand.stapel = None
        Anzeigezustand.stapel_kategorie = ""

        # Ensure sidebar is visible in the VIEW_3D area
        for space in v3d_area.spaces:
            if space.type == 'VIEW_3D':
                space.show_region_ui = True
                break

        context.window.cursor_set('EYEDROPPER')

        # If we are NOT already in the VIEW_3D area, re-invoke with
        # a context override so the modal handler is bound to VIEW_3D.
        if context.area != v3d_area and v3d_region is not None:
            v3d_area.header_text_set(
                "Pick Mode: hover over model — ESC to exit")
            with context.temp_override(area=v3d_area, region=v3d_region):
                context.window_manager.modal_handler_add(self)
        else:
            v3d_area.header_text_set(
                "Pick Mode: hover over model — ESC to exit")
            context.window_manager.modal_handler_add(self)

        return {'RUNNING_MODAL'}

    def _do_cleanup(self, context):
        """Full cleanup."""

        Anzeigezustand.wahl_laeuft = False
        Anzeigezustand.kategorie_unter_maus = ""
        Anzeigezustand.stapel = None
        Anzeigezustand.stapel_kategorie = ""
        Anzeigezustand.zonendreiecke = {}
        Anzeigezustand.flaeche_zu_kategorie = {}

        if Anzeigezustand.zeichner is not None:
            bpy.types.SpaceView3D.draw_handler_remove(Anzeigezustand.zeichner, 'WINDOW')
            Anzeigezustand.zeichner = None

        try:
            context.window.cursor_set('DEFAULT')
        # stumm gewollt: Den Mauszeiger zuruecksetzen. Ist das Fenster fort,
        # ist der Zeiger es auch.
        except Exception:
            pass

        # Reset header text on the VIEW_3D area (may differ from context.area)
        v3d_area = self._find_view3d_area(context)
        if v3d_area is not None:
            v3d_area.header_text_set(None)
            v3d_area.tag_redraw()
        elif context.area is not None:
            context.area.header_text_set(None)
            context.area.tag_redraw()

    def cancel(self, context):
        # Only cleanup if this is the current generation (not stale)
        if self._my_gen == Anzeigezustand.lauf:
            self._do_cleanup(context)

    def _raycast(self, context, event):
        """Raycast from mouse into scene, return body part category or None.

        Uses the evaluated (deformed) mesh for hit detection, but looks up
        the body zone from the pre-built rest-pose face map so that picking
        stays correct regardless of the current pose/animation.
        """
        from bpy_extras.view3d_utils import (
            region_2d_to_vector_3d, region_2d_to_origin_3d)

        region = context.region
        rv3d = context.region_data
        if rv3d is None:
            return None
        coord = (event.mouse_region_x, event.mouse_region_y)

        origin = region_2d_to_origin_3d(region, rv3d, coord)
        direction = region_2d_to_vector_3d(region, rv3d, coord)

        obj = context.active_object
        if not obj or not obj.data.get("humanbody"):
            for o in context.scene.objects:
                if o.type == 'MESH' and o.data.get("humanbody"):
                    obj = o
                    break
        if not obj:
            return None

        # Use the evaluated object (with armature/subdivision) for raycasting
        depsgraph = context.evaluated_depsgraph_get()
        eval_obj = obj.evaluated_get(depsgraph)

        mat_inv = eval_obj.matrix_world.inverted()
        ray_origin = mat_inv @ origin
        ray_dir = mat_inv.to_3x3() @ direction

        hit, loc, normal, face_idx = eval_obj.ray_cast(ray_origin, ray_dir)
        if not hit:
            return None

        # Look up category from the pre-built REST-pose face map
        if face_idx in Anzeigezustand.flaeche_zu_kategorie:
            return Anzeigezustand.flaeche_zu_kategorie[face_idx]

        # Fallback: use the REST-pose face center from original mesh
        if face_idx < len(obj.data.polygons):
            rest_center = obj.matrix_world @ obj.data.polygons[face_idx].center
            return _position_to_category(rest_center)

        # Last resort: deformed world position (for subdivided meshes)
        world_pos = eval_obj.matrix_world @ loc
        return _position_to_category(world_pos)
