# SPDX-License-Identifier: GPL-3.0-or-later
#
# Daz3D-style N-Panel UI for HumanBody addon.
# Tree-view for body parts, Daz-style sliders.

import bpy
from mathutils import Vector
from .morphing import morph_data, Morpher
from .rig import _find_rig, _list_poses
from .animation import _list_animations, _ANIM_CATEGORIES, _PROC_PREFIX
from .hair import _list_hairstyles, EYE_COLORS
from . import wardrobe, cloth_builder
from .wardrobe import WARDROBE_CATEGORIES
from .cloth_builder import (_has_modifier, _get_modifiers, _find_garment,
                            PIN_GROUP_NAME, STIFFNESS_GROUP_NAME,
                            SHRINKING_GROUP_NAME, PRESSURE_GROUP_NAME,
                            PRIMITIVE_TYPES, TEMPLATE_TYPES)


# ---------------------------------------------------------------------------
# Main category grouping for Parts panel
# ---------------------------------------------------------------------------

# Map detailed morph categories → 4 main groups
_CATEGORY_GROUPS = {
    "Head":      "Head",
    "Face":      "Head",
    "Eyes":      "Head",
    "Eyebrows":  "Head",
    "Ears":      "Head",
    "Nose":      "Head",
    "Mouth":     "Head",
    "Chin":      "Head",
    "Cheeks":    "Head",
    "Jaw":       "Head",
    "Torso":     "Body",
    "Abdomen":   "Body",
    "Stomach":   "Body",
    "Waist":     "Body",
    "Neck":      "Body",
    "Shoulders": "Body",
    "Pelvis":    "Body",
    "Body":      "Body",
    "Arms":      "Arms",
    "Elbows":    "Arms",
    "Hands":     "Arms",
    "Wrists":    "Arms",
    "Legs":      "Legs",
    "Feet":      "Legs",
}

# Display order and icons
_MAIN_CATEGORIES = [
    ("Head", 'USER'),
    ("Body", 'MOD_CLOTH'),
    ("Arms", 'CON_ARMATURE'),
    ("Legs", 'CONSTRAINT_BONE'),
]


def _group_category(cat):
    """Map a detailed category to its main group."""
    return _CATEGORY_GROUPS.get(cat, "Body")


# ---------------------------------------------------------------------------
# Body region mapping: vertex position → morph category
# ---------------------------------------------------------------------------

# Rough body zones by world-space vertex position (female basis, standing)
# Each entry: (z_min, z_max, x_min, x_max, category)
# Checked top-to-bottom, first match wins
_BODY_ZONES = [
    # Head & Face
    (1.58, 99.0, -99, 99, "Head"),
    (1.52, 1.58, -0.06, 0.06, "Nose"),
    (1.46, 1.52, -0.08, 0.08, "Eyes"),
    (1.42, 1.46, -0.08, 0.08, "Cheeks"),
    (1.38, 1.42, -0.06, 0.06, "Mouth"),
    (1.32, 1.38, -0.08, 0.08, "Chin"),
    (1.32, 1.58, -0.15, 0.15, "Face"),
    (1.28, 1.38, -0.06, 0.06, "Neck"),
    (1.32, 1.58, -0.10, -0.06, "Ears"),
    (1.32, 1.58, 0.06, 0.10, "Ears"),
    # Upper body
    (1.22, 1.32, -0.25, 0.25, "Shoulders"),
    (1.05, 1.22, -0.15, 0.15, "Chest"),
    (0.90, 1.05, -0.14, 0.14, "Abdomen"),
    (0.78, 0.90, -0.14, 0.14, "Waist"),
    (0.70, 0.78, -0.14, 0.14, "Pelvis"),
    # Arms
    (0.85, 1.22, -0.50, -0.20, "Arms"),
    (0.85, 1.22, 0.20, 0.50, "Arms"),
    (0.60, 0.85, -0.50, -0.20, "Elbows"),
    (0.60, 0.85, 0.20, 0.50, "Elbows"),
    (0.40, 0.60, -99, -0.25, "Hands"),
    (0.40, 0.60, 0.25, 99, "Hands"),
    # Legs
    (0.30, 0.70, -0.15, 0.15, "Legs"),
    (0.05, 0.30, -0.12, 0.12, "Legs"),
    (0.0, 0.05, -99, 99, "Feet"),
]


def _position_to_category(pos):
    """Map a 3D world position to a body part category."""
    z, x = pos.z, pos.x
    for z_min, z_max, x_min, x_max, cat in _BODY_ZONES:
        if z_min <= z <= z_max and x_min <= x <= x_max:
            return cat
    # Fallback: use z-height
    if z > 1.3:
        return "Head"
    if z > 0.9:
        return "Torso"
    if z > 0.3:
        return "Legs"
    return "Feet"


# ---------------------------------------------------------------------------
# Pick-mode state for interactive body part selection
# ---------------------------------------------------------------------------

_pick_mode_active = False
_hovered_category = ""
_draw_handler = None
_zone_tris = {}            # category -> list of (v0, v1, v2) world-space
_face_cat_map = {}         # face_idx (original mesh) -> category
_highlight_batch = None
_highlight_cat_cache = ""
_pick_generation = 0       # Incremented each activation; stale modals auto-exit


def _build_zone_data(obj, context):
    """Build zone triangles (for overlay) and face→category map (for raycast).

    Uses the evaluated (deformed) mesh for overlay positions, but maps
    each face to its body zone using the REST-pose center so that picking
    stays correct regardless of the current pose.
    """
    import bpy as _bpy
    orig_mesh = obj.data
    mat_w = obj.matrix_world

    # Build face → category map from REST mesh (original, undeformed)
    face_cat = {}
    for poly in orig_mesh.polygons:
        rest_center = mat_w @ poly.center
        face_cat[poly.index] = _position_to_category(rest_center)

    # Build overlay triangles from EVALUATED mesh (deformed by armature)
    depsgraph = context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    eval_mesh = eval_obj.data
    eval_mat = eval_obj.matrix_world

    tris = {}
    for poly in eval_mesh.polygons:
        # Use rest-pose category if face index matches original mesh
        if poly.index in face_cat:
            cat = face_cat[poly.index]
        else:
            # Fallback for subdivided meshes — use deformed position
            cat = _position_to_category(eval_mat @ poly.center)

        if cat not in tris:
            tris[cat] = []

        pverts = [eval_mat @ eval_mesh.vertices[vi].co.copy()
                  for vi in poly.vertices]
        for i in range(1, len(pverts) - 1):
            tris[cat].append((pverts[0], pverts[i], pverts[i + 1]))

    return tris, face_cat


def _draw_zone_highlight():
    """GPU overlay callback: draw translucent highlight over hovered zone."""
    global _highlight_batch, _highlight_cat_cache

    if not _pick_mode_active or not _hovered_category:
        return

    import gpu
    from gpu_extras.batch import batch_for_shader

    cat = _hovered_category
    if cat not in _zone_tris:
        return

    # Rebuild batch only when hovered category changes
    if _highlight_batch is None or _highlight_cat_cache != cat:
        coords = []
        for v0, v1, v2 in _zone_tris[cat]:
            coords.extend([v0, v1, v2])
        if not coords:
            return
        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        _highlight_batch = batch_for_shader(shader, 'TRIS', {"pos": coords})
        _highlight_cat_cache = cat

    shader = gpu.shader.from_builtin('UNIFORM_COLOR')

    gpu.state.blend_set('ALPHA')
    gpu.state.depth_test_set('LESS_EQUAL')
    gpu.state.face_culling_set('NONE')

    shader.bind()
    shader.uniform_float("color", (0.3, 0.6, 1.0, 0.22))
    _highlight_batch.draw(shader)

    gpu.state.blend_set('NONE')
    gpu.state.depth_test_set('NONE')
    gpu.state.face_culling_set('NONE')


# ---------------------------------------------------------------------------
# Depsgraph handler: update morph mesh when custom properties change
# ---------------------------------------------------------------------------

_depsgraph_handler = None
_updating = False
_last_values_hash = None
_update_pending = False


def _deferred_mesh_update():
    """Timer callback: apply pending morph update (debounced)."""
    global _updating, _update_pending
    _update_pending = False

    if _updating:
        return None
    scene = bpy.context.scene
    if scene is None:
        return None

    for obj in scene.objects:
        if obj.type == 'MESH' and obj.data.get("humanbody"):
            m = Morpher.get(obj)
            if not m.body_type or m.basis is None:
                break
            _updating = True
            try:
                m.update()
            finally:
                _updating = False
            break
    return None


def _on_depsgraph_update(scene, depsgraph):
    """Called after every depsgraph update. Debounces mesh updates."""
    global _update_pending, _last_values_hash
    if _updating or _update_pending:
        return
    if not depsgraph.updates:
        return

    # Quick hash check BEFORE scheduling timer — avoids unnecessary timer overhead
    for obj in scene.objects:
        if obj.type == 'MESH' and obj.data.get("humanbody"):
            m = Morpher.get(obj)
            if not m.body_type or m.basis is None:
                return
            obj_data = obj.data
            h = hash(tuple(
                obj_data.get("hb_L2_" + morph.name, 0.0)
                for morph in m.l2_morphs
            ))
            if h == _last_values_hash:
                return  # Nothing changed — skip entirely
            _last_values_hash = h
            break
    else:
        return  # No HumanBody object found

    _update_pending = True
    bpy.app.timers.register(_deferred_mesh_update, first_interval=0.01)


# ---------------------------------------------------------------------------
# Tree view state: which categories are expanded
# ---------------------------------------------------------------------------

_expanded_categories = set()


class HUMANBODY_OT_toggle_category(bpy.types.Operator):
    """Toggle a body part category open/closed in the tree view"""
    bl_idname = "humanbody.toggle_category"
    bl_label = "Toggle Category"
    bl_options = {'INTERNAL'}

    category: bpy.props.StringProperty()

    def execute(self, context):
        if self.category in _expanded_categories:
            _expanded_categories.discard(self.category)
        else:
            _expanded_categories.add(self.category)
        return {'FINISHED'}


class HUMANBODY_OT_select_category(bpy.types.Operator):
    """Select a body part category to show its sliders"""
    bl_idname = "humanbody.select_category"
    bl_label = "Select Category"
    bl_options = {'INTERNAL'}

    category: bpy.props.StringProperty()

    def execute(self, context):
        props = context.scene.humanbody
        # Toggle: click again to deselect
        if props.parts_selected == self.category:
            props.parts_selected = ""
        else:
            props.parts_selected = self.category
        return {'FINISHED'}


class HUMANBODY_OT_nudge_prop(bpy.types.Operator):
    """Increment or decrement a morph custom property by a small step"""
    bl_idname = "humanbody.nudge_prop"
    bl_label = "Nudge"
    bl_options = {'INTERNAL', 'UNDO'}

    key: bpy.props.StringProperty()
    delta: bpy.props.FloatProperty(default=0.01)

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            return {'CANCELLED'}
        val = obj.data.get(self.key, 0.0) + self.delta
        val = max(-1.0, min(1.0, val))
        obj.data[self.key] = val
        return {'FINISHED'}


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
        global _hovered_category, _highlight_batch

        # Stale modal (superseded by a newer activation) — exit silently
        if self._my_gen != _pick_generation or not _pick_mode_active:
            return {'CANCELLED'}

        # Allow viewport navigation
        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            return {'PASS_THROUGH'}

        if event.type == 'MOUSEMOVE':
            result = self._raycast(context, event)
            new_cat = result or ""
            if new_cat != _hovered_category:
                _hovered_category = new_cat
                _highlight_batch = None
                if context.area:
                    context.area.tag_redraw()
            if context.area:
                if _hovered_category:
                    context.area.header_text_set(
                        f"Pick Mode: [{_hovered_category}] — click to select, ESC to exit")
                else:
                    context.area.header_text_set(
                        "Pick Mode: hover over model — ESC to exit")
            return {'RUNNING_MODAL'}

        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            if _hovered_category:
                context.scene.humanbody.parts_selected = _hovered_category
                for area in context.screen.areas:
                    area.tag_redraw()
                self.report({'INFO'}, f"Selected: {_hovered_category}")
            return {'RUNNING_MODAL'}

        if event.type in {'RIGHTMOUSE', 'ESC'}:
            self._do_cleanup(context)
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        global _pick_mode_active, _pick_generation, _hovered_category
        global _zone_tris, _face_cat_map
        global _draw_handler, _highlight_batch, _highlight_cat_cache

        # Find a VIEW_3D area — required for modal events and raycasting
        v3d_area = self._find_view3d_area(context)
        if v3d_area is None:
            self.report({'WARNING'}, "No 3D Viewport found")
            return {'CANCELLED'}
        v3d_region = self._find_view3d_region(v3d_area)

        # Toggle off — cleanup immediately, stale modal will auto-exit
        if _pick_mode_active:
            _pick_generation += 1      # Invalidate any running modal
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
        _pick_generation += 1
        self._my_gen = _pick_generation

        _zone_tris, _face_cat_map = _build_zone_data(obj, context)

        if _draw_handler is not None:
            bpy.types.SpaceView3D.draw_handler_remove(_draw_handler, 'WINDOW')
        _draw_handler = bpy.types.SpaceView3D.draw_handler_add(
            _draw_zone_highlight, (), 'WINDOW', 'POST_VIEW')

        _pick_mode_active = True
        _hovered_category = ""
        _highlight_batch = None
        _highlight_cat_cache = ""

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
        global _pick_mode_active, _hovered_category, _draw_handler
        global _highlight_batch, _highlight_cat_cache, _zone_tris, _face_cat_map

        _pick_mode_active = False
        _hovered_category = ""
        _highlight_batch = None
        _highlight_cat_cache = ""
        _zone_tris = {}
        _face_cat_map = {}

        if _draw_handler is not None:
            bpy.types.SpaceView3D.draw_handler_remove(_draw_handler, 'WINDOW')
            _draw_handler = None

        try:
            context.window.cursor_set('DEFAULT')
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
        if self._my_gen == _pick_generation:
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
        if face_idx in _face_cat_map:
            return _face_cat_map[face_idx]

        # Fallback: use the REST-pose face center from original mesh
        if face_idx < len(obj.data.polygons):
            rest_center = obj.matrix_world @ obj.data.polygons[face_idx].center
            return _position_to_category(rest_center)

        # Last resort: deformed world position (for subdivided meshes)
        world_pos = eval_obj.matrix_world @ loc
        return _position_to_category(world_pos)


class HUMANBODY_OT_select_wardrobe_cat(bpy.types.Operator):
    """Select a wardrobe category to show its items"""
    bl_idname = "humanbody.select_wardrobe_cat"
    bl_label = "Select Wardrobe Category"
    bl_options = {'INTERNAL'}

    category: bpy.props.StringProperty()

    def execute(self, context):
        props = context.scene.humanbody
        if props.wardrobe_selected == self.category:
            props.wardrobe_selected = ""
        else:
            props.wardrobe_selected = self.category
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Helper: Daz3D-style slider
# ---------------------------------------------------------------------------

def _draw_daz_slider(layout, data, prop_name, label):
    """Standard Blender property row: label left, value right."""
    layout.prop(data, prop_name, text=label)


def _draw_daz_custom_prop(layout, obj, key, label):
    """Full-width native Blender slider: [Label ═══slider═══ value]"""
    if key not in obj.data:
        return
    layout.prop(obj.data, f'["{key}"]', text=label, slider=True)


# ---------------------------------------------------------------------------
# Main Panel
# ---------------------------------------------------------------------------

def _draw_main_body(layout, context):
    """Shared draw logic for the main HumanBody panel."""
    props = context.scene.humanbody
    obj = context.active_object

    if not obj or obj.type != 'MESH' or not obj.data.get("humanbody"):
        layout.operator("humanbody.import_character", icon='IMPORT')
        layout.label(text="Select a HumanBody character", icon='INFO')
        return False

    # Pick mode toggle — always visible in main panel
    pick_row = layout.row(align=True)
    pick_row.scale_y = 1.3
    if _pick_mode_active:
        pick_row.operator("humanbody.pick_part",
                          text="Exit Pick Mode",
                          icon='RESTRICT_SELECT_OFF', depress=True)
    else:
        pick_row.operator("humanbody.pick_part",
                          text="Click to Select on Model",
                          icon='RESTRICT_SELECT_OFF')

    return True


def _draw_body_type(layout, context):
    """Shared draw logic for the Body Type sub-panel."""
    props = context.scene.humanbody

    # Body Type combo
    layout.prop(props, "body_type", text="Body Type")

    layout.separator()

    # Quick Adjust sliders
    _draw_daz_slider(layout, props, "meta_age", "Age")
    _draw_daz_slider(layout, props, "meta_mass", "Mass")
    _draw_daz_slider(layout, props, "meta_tone", "Tone")
    _draw_daz_slider(layout, props, "meta_height", "Height (cm)")

    layout.separator()

    row = layout.row(align=True)
    row.operator("humanbody.update_morphs", icon='FILE_REFRESH')
    row.operator("humanbody.reset_morphs", icon='LOOP_BACK')


def _draw_parts_body(layout, context):
    """Shared draw logic for the Parts morph sliders with main category grouping."""
    props = context.scene.humanbody
    obj = context.active_object
    m = Morpher.get(obj)

    if not m.l2_morphs:
        layout.label(text="No morph data loaded")
        return

    # Pick-on-model button (also in main panel, repeated here for convenience)
    pick_row = layout.row(align=True)
    if _pick_mode_active:
        pick_row.operator("humanbody.pick_part",
                          text="Exit Pick Mode",
                          icon='RESTRICT_SELECT_OFF', depress=True)
    else:
        pick_row.operator("humanbody.pick_part",
                          text="Click to Select on Model",
                          icon='RESTRICT_SELECT_OFF')

    # Search bar
    row = layout.row(align=True)
    row.prop(props, "filter_text", text="", icon='VIEWZOOM')

    filt = props.filter_text.lower()

    # Build main-group → subcategory → morphs mapping
    main_groups = {}  # main_cat -> {sub_cat -> [morph, ...]}
    if filt:
        for morph in m.l2_morphs:
            if filt not in morph.name.lower():
                continue
            main = _group_category(morph.category)
            if main not in main_groups:
                main_groups[main] = {}
            sub = morph.category
            if sub not in main_groups[main]:
                main_groups[main][sub] = []
            main_groups[main][sub].append(morph)
    else:
        for cat, morphs in m._categories.items():
            main = _group_category(cat)
            if main not in main_groups:
                main_groups[main] = {}
            main_groups[main][cat] = morphs

    if not main_groups:
        layout.label(text="No morphs match filter")
        return

    selected = props.parts_selected

    # Auto-select first main group
    ordered_mains = [name for name, _ in _MAIN_CATEGORIES if name in main_groups]
    if (not selected or selected not in main_groups) and ordered_mains:
        selected = ordered_mains[0]

    # --- Two-column split: main categories left, sliders right ---
    split = layout.split(factor=0.22)

    # LEFT COLUMN: main category buttons
    left = split.column(align=True)
    obj_data = obj.data
    for main_name, main_icon in _MAIN_CATEGORIES:
        if main_name not in main_groups:
            continue
        is_selected = (selected == main_name)

        # Check if any morph in this group is non-zero
        nonzero = False
        for morphs in main_groups[main_name].values():
            for morph in morphs:
                if abs(obj_data.get("hb_L2_" + morph.name, 0.0)) > 0.001:
                    nonzero = True
                    break
            if nonzero:
                break

        icon = main_icon if not nonzero else 'RADIOBUT_ON'
        op = left.operator("humanbody.select_category",
                           text=main_name,
                           depress=is_selected,
                           icon=icon)
        op.category = main_name

    # RIGHT COLUMN: sliders grouped by subcategory
    right = split.column()

    if selected and selected in main_groups:
        subcats = main_groups[selected]
        sorted_subs = sorted(subcats.keys())

        for sub_name in sorted_subs:
            morphs = subcats[sub_name]
            # Subcategory header
            box = right.box()
            box.label(text=sub_name, icon='MESH_DATA')
            col = box.column(align=True)
            prefix = sub_name + "_"
            prefix_len = len(prefix)
            for morph in morphs:
                short = morph.name
                if short.startswith(prefix):
                    short = short[prefix_len:]
                short = short.replace("_", " ")
                _draw_daz_custom_prop(col, obj, "hb_L2_" + morph.name,
                                      short)


def _draw_favorites_body(layout, context):
    """Shared draw logic for the Currently Used panel."""
    obj = context.active_object
    m = Morpher.get(obj)

    count = 0
    col = layout.column(align=True)
    for morph in m.l2_morphs:
        val = obj.data.get("hb_L2_" + morph.name, 0.0)
        if abs(val) > 0.001:
            _draw_daz_custom_prop(col, obj, "hb_L2_" + morph.name,
                                  morph.name.replace("_", " "))
            count += 1

    if count == 0:
        layout.label(text="No morphs active")


def _poll_humanbody(context):
    obj = context.active_object
    return obj and obj.type == 'MESH' and obj.data.get("humanbody")


# ---------------------------------------------------------------------------
# N-Panel (3D Viewport sidebar) — backup/original location
# ---------------------------------------------------------------------------

class HUMANBODY_PT_main(bpy.types.Panel):
    bl_label = "HumanBody 0.30"
    bl_idname = "HUMANBODY_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "HumanBody"

    def draw(self, context):
        _draw_main_body(self.layout, context)


# ---------------------------------------------------------------------------
# Body Type sub-panel
# ---------------------------------------------------------------------------

class HUMANBODY_PT_body_type(bpy.types.Panel):
    bl_label = "Body Type"
    bl_idname = "HUMANBODY_PT_body_type"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "HumanBody"
    bl_parent_id = "HUMANBODY_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _poll_humanbody(context)

    def draw(self, context):
        _draw_body_type(self.layout, context)


# ---------------------------------------------------------------------------
# Materials sub-panel
# ---------------------------------------------------------------------------

def _draw_materials_body(layout, context):
    """Draw logic for the Materials panel."""
    props = context.scene.humanbody
    obj = context.active_object
    mats = obj.data.materials if obj else []

    # Eye color preset
    layout.prop(props, "eye_color")

    if len(mats) < 10:
        layout.label(text="Import character first", icon='INFO')
        return

    layout.separator()

    # Editable material Base Color (directly on shader node)
    _MAT_LABELS = [
        (0,  "Skin",           'USER'),
        (9,  "Nails - Hand",   'BONE_DATA'),
        (10, "Nails - Feet",   'BONE_DATA'),
        (6,  "Iris",           'HIDE_OFF'),
        (4,  "Sclera",         'SHADING_SOLID'),
        (8,  "Teeth",          'MESH_DATA'),
        (7,  "Tongue",         'MESH_DATA'),
        (3,  "Pupil",          'PMARKER_ACT'),
        (1,  "Areola",         'MESH_CIRCLE'),
        (2,  "Eyelash",        'HIDE_OFF'),
    ]
    box = layout.box()
    for idx, label, icon in _MAT_LABELS:
        if idx >= len(mats):
            continue
        mat = mats[idx]
        if mat and mat.node_tree:
            for node in mat.node_tree.nodes:
                if node.type == 'BSDF_PRINCIPLED':
                    row = box.row(align=True)
                    row.label(text=label, icon=icon)
                    row.prop(node.inputs['Base Color'], "default_value", text="")
                    break

    layout.separator()
    layout.label(text="Skin & nails auto-update with Body Type", icon='INFO')


class HUMANBODY_PT_materials(bpy.types.Panel):
    bl_label = "Materials"
    bl_idname = "HUMANBODY_PT_materials"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "HumanBody"
    bl_parent_id = "HUMANBODY_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _poll_humanbody(context)

    def draw(self, context):
        _draw_materials_body(self.layout, context)


# ---------------------------------------------------------------------------
# Parts sub-panel (tree view)
# ---------------------------------------------------------------------------

class HUMANBODY_PT_parts(bpy.types.Panel):
    bl_label = "Parts"
    bl_idname = "HUMANBODY_PT_parts"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "HumanBody"
    bl_parent_id = "HUMANBODY_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _poll_humanbody(context)

    def draw(self, context):
        _draw_parts_body(self.layout, context)


class HUMANBODY_PT_favorites(bpy.types.Panel):
    bl_label = "Currently Used"
    bl_idname = "HUMANBODY_PT_favorites"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "HumanBody"
    bl_parent_id = "HUMANBODY_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _poll_humanbody(context)

    def draw(self, context):
        _draw_favorites_body(self.layout, context)


# ---------------------------------------------------------------------------
# Wardrobe sub-panel
# ---------------------------------------------------------------------------

def _draw_wardrobe_body(layout, context):
    """Wardrobe panel with category buttons left, items right (like Parts)."""
    props = context.scene.humanbody
    obj = context.active_object

    all_assets = wardrobe.discover_assets()
    fitted_names = {n for _, n in wardrobe.get_fitted_assets(obj)}

    # Search bar
    row = layout.row(align=True)
    row.prop(props, "wardrobe_search", text="", icon='VIEWZOOM')

    search = props.wardrobe_search.lower()

    # Group assets by category
    cat_assets = {}
    for a in all_assets:
        if a.category == "Hair":
            continue  # Hair is in the Hair panel
        if search and search not in a.name.lower() and \
           not any(search in t.lower() for t in a.tags):
            continue
        cat = a.category
        if cat not in cat_assets:
            cat_assets[cat] = []
        cat_assets[cat].append(a)

    if not cat_assets:
        layout.label(text="No assets found", icon='INFO')
        return

    # Auto-select first category
    selected = props.wardrobe_selected
    ordered = [name for name, _ in WARDROBE_CATEGORIES if name in cat_assets]
    if (not selected or selected not in cat_assets) and ordered:
        selected = ordered[0]

    # --- Two-column split ---
    split = layout.split(factor=0.28)

    # LEFT: category buttons
    left = split.column(align=True)
    for cat_name, cat_icon in WARDROBE_CATEGORIES:
        if cat_name not in cat_assets:
            continue
        count = len(cat_assets[cat_name])
        fitted_count = sum(1 for a in cat_assets[cat_name]
                           if a.name in fitted_names)
        is_sel = (selected == cat_name)
        icon = 'RADIOBUT_ON' if fitted_count > 0 else cat_icon
        op = left.operator("humanbody.select_wardrobe_cat",
                           text=f"{cat_name} ({count})",
                           depress=is_sel, icon=icon)
        op.category = cat_name

    # RIGHT: items in selected category
    right = split.column()

    if selected and selected in cat_assets:
        for asset in cat_assets[selected]:
            is_fitted = asset.name in fitted_names
            box = right.box()
            row = box.row(align=True)
            row.label(text=asset.label,
                      icon='CHECKMARK' if is_fitted else 'MESH_DATA')
            if is_fitted:
                op = row.operator("humanbody.wardrobe_remove",
                                  text="", icon='X')
                op.asset_name = asset.name
            else:
                op = row.operator("humanbody.wardrobe_add",
                                  text="", icon='ADD')
                op.asset_name = asset.name

            # Show controls for fitted assets
            if is_fitted:
                child = None
                for c, n in wardrobe.get_fitted_assets(obj):
                    if n == asset.name:
                        child = c
                        break
                if child:
                    info = wardrobe.find_asset_info(asset.name)
                    if info:
                        presets = wardrobe.get_material_presets(info)
                        if presets:
                            row2 = box.row(align=True)
                            for key, label in presets.items():
                                op = row2.operator(
                                    "humanbody.wardrobe_preset", text=label)
                                op.asset_name = asset.name
                                op.preset_key = key
                    offset_mod = child.modifiers.get("hb_offset")
                    if offset_mod:
                        box.prop(offset_mod, "strength", text="Offset")
                    smooth_mod = child.modifiers.get("hb_smooth")
                    if smooth_mod:
                        box.prop(smooth_mod, "iterations", text="Smoothing")


class HUMANBODY_PT_wardrobe(bpy.types.Panel):
    bl_label = "Wardrobe"
    bl_idname = "HUMANBODY_PT_wardrobe"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "HumanBody"
    bl_parent_id = "HUMANBODY_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _poll_humanbody(context)

    def draw(self, context):
        _draw_wardrobe_body(self.layout, context)


# ---------------------------------------------------------------------------
# Asset Creator sub-panel (under Wardrobe)
# ---------------------------------------------------------------------------

def _draw_asset_creator_body(layout, context):
    """Draw logic for the Asset Creator panel."""
    from . import assetCreator as asset_creator

    ac = context.scene.humanbody_asset_creator
    preview = asset_creator.find_preview(context)

    # Name + Category
    layout.prop(ac, "name_", text="Name")
    layout.prop(ac, "category")

    layout.separator()

    # --- Mode toggle ---
    row = layout.row(align=True)
    row.prop(ac, "creation_mode", expand=True)

    # --- Z-Range mode ---
    if ac.creation_mode == "ZRANGE":
        box = layout.box()
        box.label(text="Cutout", icon='MOD_BOOLEAN')
        col = box.column(align=True)
        col.prop(ac, "z_max", text="Z Top")
        col.prop(ac, "z_min", text="Z Bottom")
        box.prop(ac, "include_arms")

    # --- Image mode ---
    if ac.creation_mode == "IMAGE":
        box = layout.box()
        box.label(text="Image", icon='IMAGE_DATA')
        box.prop(ac, "image_path", text="")
        col = box.column(align=True)
        col.prop(ac, "image_bg_mode")
        col.prop(ac, "image_threshold")
        col.prop(ac, "image_scale")

        box2 = layout.box()
        box2.label(text="Offset Range", icon='DRIVER_DISTANCE')
        col = box2.column(align=True)
        col.prop(ac, "image_offset_min", text="Min")
        col.prop(ac, "image_offset_max", text="Max")

    # --- Passform (shared) ---
    box = layout.box()
    box.label(text="Fit", icon='MOD_CLOTH')
    col = box.column(align=True)
    if ac.creation_mode == "ZRANGE":
        col.prop(ac, "offset")
    col.prop(ac, "thickness")
    col.prop(ac, "smoothing")
    col.prop(ac, "waviness")
    col.prop(ac, "drape")
    col.prop(ac, "grow")

    # --- Material ---
    box = layout.box()
    box.label(text="Material", icon='MATERIAL')
    box.prop(ac, "color", text="")
    col = box.column(align=True)
    col.prop(ac, "roughness")
    col.prop(ac, "metallic")

    layout.separator()

    # --- Buttons ---
    row = layout.row(align=True)
    row.scale_y = 1.3
    row.operator("humanbody.create_asset_preview",
                 text="Update Preview", icon='FILE_REFRESH')
    if preview:
        row.operator("humanbody.save_asset",
                     text="Save Asset", icon='FILE_TICK')
    row = layout.row(align=True)
    if preview:
        row.operator("humanbody.delete_asset_preview",
                     text="Delete Preview", icon='X')
        row.label(text=f"{len(preview.data.polygons)} faces",
                  icon='MESH_DATA')

    # --- Brush Editor ---
    if preview:
        layout.separator()
        box = layout.box()
        box.label(text="Brush Editor", icon='BRUSH_DATA')
        box.operator("humanbody.brush_offset",
                     text="Edit Offset", icon='BRUSH_DATA')
        col = box.column(align=True)
        col.prop(ac, "brush_radius")
        col.prop(ac, "brush_strength")


class HUMANBODY_PT_asset_creator(bpy.types.Panel):
    bl_label = "Asset Creator"
    bl_idname = "HUMANBODY_PT_asset_creator"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "HumanBody"
    bl_parent_id = "HUMANBODY_PT_wardrobe"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _poll_humanbody(context)

    def draw(self, context):
        _draw_asset_creator_body(self.layout, context)


# ---------------------------------------------------------------------------
# Geometric Assets sub-panel (under Wardrobe)
# ---------------------------------------------------------------------------

def _draw_geo_assets_body(layout, context):
    """Draw logic for the Geometric Assets panel."""
    from .assetCreator.geometric import GEO_TAG

    props = context.scene.humanbody_geo_asset

    layout.prop(props, "region")
    layout.prop(props, "shape")

    layout.separator()

    col = layout.column(align=True)
    col.prop(props, "offset")
    col.prop(props, "scale")
    col.prop(props, "segments")

    layout.separator()
    layout.prop(props, "color")

    layout.separator()

    row = layout.row(align=True)
    row.scale_y = 1.3
    row.operator("humanbody.create_geo_asset", icon='MESH_CYLINDER')

    # "Alle entfernen" only when geo assets exist
    has_geo = any(obj.get(GEO_TAG) for obj in context.scene.objects)
    if has_geo:
        row = layout.row(align=True)
        row.operator("humanbody.remove_geo_assets", icon='X')


class HUMANBODY_PT_geo_assets(bpy.types.Panel):
    bl_label = "Geometric Assets"
    bl_idname = "HUMANBODY_PT_geo_assets"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "HumanBody"
    bl_parent_id = "HUMANBODY_PT_wardrobe"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _poll_humanbody(context)

    def draw(self, context):
        _draw_geo_assets_body(self.layout, context)


# ---------------------------------------------------------------------------
# Cloth Builder sub-panel (under Wardrobe)
# ---------------------------------------------------------------------------

def _draw_cloth_builder_body(layout, context):
    """Draw logic for the Cloth Builder panel."""
    from .assetCreator.preview import find_body_obj

    props = context.scene.humanbody_cloth_builder
    body = find_body_obj(context)
    garment = _find_garment(context)

    has_cloth = False
    if garment:
        has_cloth = _has_modifier(garment, 'CLOTH')

    # --- Setup ---
    box = layout.box()
    box.label(text="Setup", icon='MODIFIER')

    # Region selector — always visible
    box.prop(props, "garment_region")
    box.prop(props, "looseness", slider=True)

    if has_cloth and garment:
        row = box.row(align=True)
        row.label(text=f"Cloth: {garment.name}", icon='MOD_CLOTH')
        cloth_mods = _get_modifiers('CLOTH', [garment])
        if cloth_mods:
            row.prop(cloth_mods[0], "show_viewport", text="",
                     icon='HIDE_OFF' if cloth_mods[0].show_viewport else 'HIDE_ON')
        row.operator("humanbody.cloth_remove", text="", icon='X')
        # Rebuild + Remove
        row = box.row(align=True)
        row.operator("humanbody.cloth_rebuild", text="Rebuild",
                     icon='FILE_REFRESH')
        row.operator("humanbody.cloth_remove_garment", text="Remove",
                     icon='TRASH')
    elif garment:
        box.label(text=f"Target: {garment.name}", icon='MESH_DATA')
        row = box.row(align=True)
        row.scale_y = 1.3
        row.operator("humanbody.cloth_add", icon='MOD_CLOTH')
        row.operator("humanbody.cloth_remove_garment", text="",
                     icon='TRASH')
    else:
        row = box.row(align=True)
        row.scale_y = 1.3
        row.operator("humanbody.cloth_add", icon='MOD_CLOTH')

    if body:
        row = box.row(align=True)
        has_coll = _has_modifier(body, 'COLLISION')
        icon = 'CHECKMARK' if has_coll else 'ERROR'
        row.label(text=f"Collision: {body.name}", icon=icon)

    # --- Simulation ---
    box = layout.box()
    box.label(text="Simulation", icon='PLAY')

    row = box.row(align=True)
    row.scale_y = 1.2
    if bpy.context.screen.is_animation_playing:
        row.operator("humanbody.cloth_stop_sim", text="Stop", icon='PAUSE')
    else:
        row.operator("humanbody.cloth_run_sim", text="Play", icon='PLAY')
    row.operator("humanbody.cloth_reset_sim", text="Reset", icon='LOOP_BACK')

    col = box.column(align=True)
    col.prop(props, "simulation_frames")
    col.prop(props, "sim_quality")
    col.prop(props, "collision_quality")
    col.prop(props, "collision_distance")

    # --- Cloth Settings (direct modifier access) ---
    if has_cloth and garment:
        cloth_mods = _get_modifiers('CLOTH', [garment])
        if cloth_mods:
            mod = cloth_mods[0]
            box = layout.box()
            box.label(text="Cloth Settings", icon='PREFERENCES')

            col = box.column(align=True)
            col.prop(mod.collision_settings, "use_self_collision",
                     text="Self Collision")
            col.prop(mod.settings, "use_pressure")
            if mod.settings.use_pressure:
                col.prop(mod.settings, "uniform_pressure_force",
                         text="Pressure Force")
            col.prop(mod.settings, "shrink_min", text="Shrink Min")
            col.prop(mod.settings, "bending_stiffness",
                     text="Bending Stiffness")

    # --- Pinning ---
    box = layout.box()
    box.label(text="Pinning", icon='PINNED')

    col = box.column(align=True)
    col.prop(props, "pin_scale")
    col.prop(props, "pin_shape")

    row = box.row(align=True)
    row.operator("humanbody.cloth_add_pin", icon='PINNED')

    row = box.row(align=True)
    row.operator("humanbody.cloth_remove_pin", text="Remove Selected",
                 icon='UNPINNED')
    row.operator("humanbody.cloth_clear_pins", text="Clear All", icon='X')

    # --- Fit & Apply ---
    box = layout.box()
    box.label(text="Fit & Apply", icon='CHECKMARK')

    col = box.column(align=True)
    col.prop(props, "fit_offset", text="Offset")
    col.prop(props, "fit_corrective_iters", text="Corrective Iterations")

    box.operator("humanbody.cloth_fit_to_body", icon='MOD_SHRINKWRAP')
    box.operator("humanbody.cloth_apply_base", icon='CHECKMARK')

    row = box.row(align=True)
    row.operator("humanbody.cloth_shake", icon='RNDCURVE')
    row.operator("humanbody.cloth_paint_weight", icon='WPAINT_HLT')


class HUMANBODY_PT_cloth_builder(bpy.types.Panel):
    bl_label = "Cloth Builder"
    bl_idname = "HUMANBODY_PT_cloth_builder"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "HumanBody"
    bl_parent_id = "HUMANBODY_PT_wardrobe"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _poll_humanbody(context)

    def draw(self, context):
        _draw_cloth_builder_body(self.layout, context)


# ---------------------------------------------------------------------------
# Cloth - Primitive sub-panel (under Wardrobe)
# ---------------------------------------------------------------------------

def _draw_cloth_primitive_body(layout, context):
    """Draw logic for the Cloth Primitive panel."""
    props = context.scene.humanbody_cloth_primitive
    pt = props.prim_type

    # Primitive type selector
    layout.prop(props, "prim_type")

    col = layout.column(align=True)
    col.prop(props, "segments")

    # Body-wrap types: length
    _BODY_TYPES = {'PRIM_SKIRT', 'PRIM_PANTS', 'PRIM_TOP', 'PRIM_ARMS',
                   'PRIM_NECK', 'PRIM_HEAD', 'PRIM_SHOES', 'PRIM_PUFFER'}
    # Freeform types: radius + z position
    _FREE_TYPES = {'PRIM_DISC', 'PRIM_SPHERE', 'PRIM_OVAL_DISC', 'PRIM_TRIANGLE'}

    if pt in _BODY_TYPES:
        col.prop(props, "prim_length")
    if pt in _FREE_TYPES:
        col.prop(props, "prim_radius")
        col.prop(props, "prim_z")
    if pt == 'PRIM_SKIRT':
        col.prop(props, "prim_flare")
    if pt == 'PRIM_PUFFER':
        col.prop(props, "prim_count")

    layout.separator()

    # Create button
    row = layout.row(align=True)
    row.scale_y = 1.3
    row.operator("humanbody.cloth_prim_create", icon='MESH_CONE')

    # Simulation controls (shared)
    layout.separator()
    box = layout.box()
    box.label(text="Simulation", icon='PLAY')
    row = box.row(align=True)
    row.scale_y = 1.2
    if bpy.context.screen.is_animation_playing:
        row.operator("humanbody.cloth_stop_sim", text="Stop", icon='PAUSE')
    else:
        row.operator("humanbody.cloth_run_sim", text="Play", icon='PLAY')
    row.operator("humanbody.cloth_reset_sim", text="Reset", icon='LOOP_BACK')


class HUMANBODY_PT_cloth_primitive(bpy.types.Panel):
    bl_label = "Cloth - Primitive"
    bl_idname = "HUMANBODY_PT_cloth_primitive"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "HumanBody"
    bl_parent_id = "HUMANBODY_PT_wardrobe"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _poll_humanbody(context)

    def draw(self, context):
        _draw_cloth_primitive_body(self.layout, context)


# ---------------------------------------------------------------------------
# Cloth - from Template sub-panel (under Wardrobe)
# ---------------------------------------------------------------------------

def _draw_cloth_template_body(layout, context):
    """Draw logic for the Cloth Template panel."""
    from .assetCreator.preview import find_body_obj

    props = context.scene.humanbody_cloth_template

    # Template type selector
    layout.prop(props, "template_type")
    layout.prop(props, "segments")
    layout.prop(props, "tightness", slider=True)
    row = layout.row(align=True)
    row.prop(props, "top_extend")
    row.prop(props, "bottom_extend")

    layout.separator()

    # Create button
    row = layout.row(align=True)
    row.scale_y = 1.3
    row.operator("humanbody.cloth_tpl_create", icon='MOD_CLOTH')

    # Simulation controls (shared)
    layout.separator()
    box = layout.box()
    box.label(text="Simulation", icon='PLAY')
    row = box.row(align=True)
    row.scale_y = 1.2
    if bpy.context.screen.is_animation_playing:
        row.operator("humanbody.cloth_stop_sim", text="Stop", icon='PAUSE')
    else:
        row.operator("humanbody.cloth_run_sim", text="Play", icon='PLAY')
    row.operator("humanbody.cloth_reset_sim", text="Reset", icon='LOOP_BACK')


class HUMANBODY_PT_cloth_template(bpy.types.Panel):
    bl_label = "Cloth - from Template"
    bl_idname = "HUMANBODY_PT_cloth_template"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "HumanBody"
    bl_parent_id = "HUMANBODY_PT_wardrobe"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _poll_humanbody(context)

    def draw(self, context):
        _draw_cloth_template_body(self.layout, context)


# ---------------------------------------------------------------------------
# New feature panels (stubs)
# ---------------------------------------------------------------------------

def _draw_hair_body(layout, context):
    """Draw logic for the Hair / Brows / Lashes panel."""
    import bpy as _bpy
    props = context.scene.humanbody
    obj = context.active_object
    mats = obj.data.materials if obj else []

    layout.separator()

    # ---- Hair ----
    # Check if any hair exists (on body or as hair object)
    has_hair = False
    if obj:
        for ps in obj.particle_systems:
            if ps.settings.type == 'HAIR':
                has_hair = True
                break
    if not has_hair:
        for o in _bpy.data.objects:
            if o.get("humanbody_hair"):
                has_hair = True
                break

    # Hair color
    layout.prop(props, "hair_color")

    # Hair assets (from .blend files)
    assets = _list_hairstyles()
    if assets:
        layout.separator()
        layout.label(text="Hair Assets:", icon='ASSET_MANAGER')
        col = layout.column(align=True)
        for key, label in assets:
            icon = 'STRANDS' if 'particle' in key else 'MESH_DATA'
            op = col.operator("humanbody.load_hairstyle",
                              text=label, icon=icon)
            op.asset_key = key

    layout.separator()

    # Procedural hair section
    layout.label(text="Procedural:", icon='OUTLINER_OB_CURVES')
    layout.prop(props, "hair_length")
    layout.prop(props, "hair_count")
    row = layout.row(align=True)
    row.operator("humanbody.create_hair", icon='STRANDS')

    layout.separator()

    # Remove / Recolor
    if has_hair:
        row = layout.row(align=True)
        row.operator("humanbody.recolor_hair", icon='COLOR')
        row.operator("humanbody.remove_hair", icon='X')


def _draw_rig_body(layout, context):
    """Draw logic for the Rig panel."""
    obj = context.active_object
    rig = _find_rig(obj) if obj else None

    if rig:
        layout.label(text=f"Rig: {rig.name} ({len(rig.data.bones)} bones)",
                     icon='ARMATURE_DATA')
        layout.operator("humanbody.remove_rig", text="Remove Rig", icon='X')
    else:
        layout.label(text="No rig attached", icon='INFO')
        layout.operator("humanbody.add_rig", text="Add Rig",
                        icon='ARMATURE_DATA')


def _draw_pose_body(layout, context):
    """Draw logic for the Pose panel."""
    obj = context.active_object
    rig = _find_rig(obj) if obj else None

    if not rig:
        layout.label(text="Add a rig first", icon='INFO')
        return

    # Clear pose button
    layout.operator("humanbody.clear_pose", text="Reset Pose", icon='LOOP_BACK')
    layout.separator()

    # List available poses
    poses = _list_poses()
    if not poses:
        layout.label(text="No poses found", icon='INFO')
        return

    layout.label(text=f"{len(poses)} Poses:", icon='POSE_HLT')
    col = layout.column(align=True)
    for name, label in poses:
        op = col.operator("humanbody.load_pose", text=label, icon='ARMATURE_DATA')
        op.pose_name = name


class HUMANBODY_OT_select_anim_cat(bpy.types.Operator):
    """Select an animation category"""
    bl_idname = "humanbody.select_anim_cat"
    bl_label = "Select Animation Category"
    bl_options = {'INTERNAL'}

    category: bpy.props.StringProperty()

    def execute(self, context):
        props = context.scene.humanbody
        if props.anim_selected == self.category:
            props.anim_selected = ""
        else:
            props.anim_selected = self.category
        return {'FINISHED'}


def _draw_animation_body(layout, context):
    """Draw logic for the Animation panel (BVH motion capture)."""
    props = context.scene.humanbody
    obj = context.active_object
    rig = _find_rig(obj) if obj else None

    if not rig:
        layout.label(text="Add a rig first", icon='INFO')
        return

    # Stop button + Speed slider
    row = layout.row(align=True)
    row.operator("humanbody.stop_animation", text="Stop", icon='CANCEL')
    row.prop(props, "anim_speed", slider=True)

    row = layout.row(align=True)
    row.operator("humanbody.batch_retarget", text="Pre-cache All", icon='FILE_CACHE')
    row.operator("humanbody.mocapnet_webui", text="", icon='URL')
    layout.separator()

    # Get animations
    anims = _list_animations()
    if not anims:
        layout.label(text="No animations found", icon='INFO')
        return

    selected = props.anim_selected
    ordered = [name for name, _ in _ANIM_CATEGORIES if name in anims]
    if (not selected or selected not in anims) and ordered:
        selected = ordered[0]

    # Two-column layout: categories left, items right
    split = layout.split(factor=0.25)

    # LEFT: category buttons
    left = split.column(align=True)
    for cat_name, cat_icon in _ANIM_CATEGORIES:
        if cat_name not in anims:
            continue
        count = len(anims[cat_name])
        is_sel = (selected == cat_name)
        op = left.operator("humanbody.select_anim_cat",
                           text=f"{cat_name} ({count})",
                           depress=is_sel, icon=cat_icon)
        op.category = cat_name

    # RIGHT: animation items
    right = split.column()
    if selected and selected in anims:
        col = right.column(align=True)
        for label, path in anims[selected]:
            is_bvh = not path.startswith(_PROC_PREFIX)
            if is_bvh:
                row = col.row(align=True)
                op = row.operator("humanbody.load_animation",
                                  text=label, icon='PLAY')
                op.bvh_path = path
                op.anim_name = label
                op2 = row.operator("humanbody.load_bvh_native",
                                   text="", icon='IMPORT')
                op2.bvh_path = path
                op2.anim_name = label
            else:
                op = col.operator("humanbody.load_animation",
                                  text=label, icon='PLAY')
                op.bvh_path = path
                op.anim_name = label


def _draw_randomize_body(layout, context):
    """Draw logic for the Randomize panel."""
    props = context.scene.humanbody
    layout.prop(props, "randomize_strength", slider=True)
    layout.operator("humanbody.randomize", icon='RNDCURVE')


def _draw_finalize_body(layout, context):
    """Draw logic for the Finalize panel."""
    layout.label(text="Bake current shape into mesh:", icon='INFO')
    layout.operator("humanbody.finalize", icon='CHECKMARK')


def _draw_file_io_body(layout, context):
    """Draw logic for the File I/O panel."""
    has_char = _poll_humanbody(context)
    if has_char:
        row = layout.row(align=True)
        row.operator("humanbody.export_character", icon='EXPORT')
        row.operator("humanbody.import_settings", icon='IMPORT')
        layout.separator()

    layout.operator("humanbody.import_character", icon='MESH_DATA',
                     text="Import New Character")


class HUMANBODY_PT_hair(bpy.types.Panel):
    bl_label = "Hair / Brows / Lashes"
    bl_idname = "HUMANBODY_PT_hair"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "HumanBody"
    bl_parent_id = "HUMANBODY_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _poll_humanbody(context)

    def draw(self, context):
        _draw_hair_body(self.layout, context)


class HUMANBODY_PT_rig(bpy.types.Panel):
    bl_label = "Rig"
    bl_idname = "HUMANBODY_PT_rig"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "HumanBody"
    bl_parent_id = "HUMANBODY_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _poll_humanbody(context)

    def draw(self, context):
        _draw_rig_body(self.layout, context)


class HUMANBODY_PT_pose(bpy.types.Panel):
    bl_label = "Pose"
    bl_idname = "HUMANBODY_PT_pose"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "HumanBody"
    bl_parent_id = "HUMANBODY_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _poll_humanbody(context)

    def draw(self, context):
        _draw_pose_body(self.layout, context)


class HUMANBODY_PT_animation(bpy.types.Panel):
    bl_label = "Animation"
    bl_idname = "HUMANBODY_PT_animation"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "HumanBody"
    bl_parent_id = "HUMANBODY_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _poll_humanbody(context)

    def draw(self, context):
        _draw_animation_body(self.layout, context)


class HUMANBODY_PT_randomize(bpy.types.Panel):
    bl_label = "Randomize"
    bl_idname = "HUMANBODY_PT_randomize"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "HumanBody"
    bl_parent_id = "HUMANBODY_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _poll_humanbody(context)

    def draw(self, context):
        _draw_randomize_body(self.layout, context)


class HUMANBODY_PT_finalize(bpy.types.Panel):
    bl_label = "Finalize"
    bl_idname = "HUMANBODY_PT_finalize"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "HumanBody"
    bl_parent_id = "HUMANBODY_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _poll_humanbody(context)

    def draw(self, context):
        _draw_finalize_body(self.layout, context)


class HUMANBODY_PT_file_io(bpy.types.Panel):
    bl_label = "File I/O"
    bl_idname = "HUMANBODY_PT_file_io"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "HumanBody"
    bl_parent_id = "HUMANBODY_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        # Always show — Import New Character available even without a character
        return True

    def draw(self, context):
        _draw_file_io_body(self.layout, context)


# ---------------------------------------------------------------------------
# Properties Editor panels (Object Data Properties -> green mesh icon)
# ---------------------------------------------------------------------------

class HUMANBODY_PT_props_main(bpy.types.Panel):
    bl_label = "HumanBody"
    bl_idname = "HUMANBODY_PT_props_main"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'data'  # Object Data Properties (mesh icon)

    @classmethod
    def poll(cls, context):
        return _poll_humanbody(context)

    def draw(self, context):
        _draw_main_body(self.layout, context)


class HUMANBODY_PT_props_body_type(bpy.types.Panel):
    bl_label = "Body Type"
    bl_idname = "HUMANBODY_PT_props_body_type"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'data'
    bl_parent_id = "HUMANBODY_PT_props_main"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _poll_humanbody(context)

    def draw(self, context):
        _draw_body_type(self.layout, context)


class HUMANBODY_PT_props_materials(bpy.types.Panel):
    bl_label = "Materials"
    bl_idname = "HUMANBODY_PT_props_materials"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'data'
    bl_parent_id = "HUMANBODY_PT_props_main"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _poll_humanbody(context)

    def draw(self, context):
        _draw_materials_body(self.layout, context)


class HUMANBODY_PT_props_parts(bpy.types.Panel):
    bl_label = "Parts"
    bl_idname = "HUMANBODY_PT_props_parts"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'data'
    bl_parent_id = "HUMANBODY_PT_props_main"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _poll_humanbody(context)

    def draw(self, context):
        _draw_parts_body(self.layout, context)


class HUMANBODY_PT_props_favorites(bpy.types.Panel):
    bl_label = "Currently Used"
    bl_idname = "HUMANBODY_PT_props_favorites"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'data'
    bl_parent_id = "HUMANBODY_PT_props_main"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _poll_humanbody(context)

    def draw(self, context):
        _draw_favorites_body(self.layout, context)


class HUMANBODY_PT_props_wardrobe(bpy.types.Panel):
    bl_label = "Wardrobe"
    bl_idname = "HUMANBODY_PT_props_wardrobe"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'data'
    bl_parent_id = "HUMANBODY_PT_props_main"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _poll_humanbody(context)

    def draw(self, context):
        _draw_wardrobe_body(self.layout, context)


class HUMANBODY_PT_props_asset_creator(bpy.types.Panel):
    bl_label = "Asset Creator"
    bl_idname = "HUMANBODY_PT_props_asset_creator"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'data'
    bl_parent_id = "HUMANBODY_PT_props_wardrobe"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _poll_humanbody(context)

    def draw(self, context):
        _draw_asset_creator_body(self.layout, context)


class HUMANBODY_PT_props_geo_assets(bpy.types.Panel):
    bl_label = "Geometric Assets"
    bl_idname = "HUMANBODY_PT_props_geo_assets"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'data'
    bl_parent_id = "HUMANBODY_PT_props_wardrobe"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _poll_humanbody(context)

    def draw(self, context):
        _draw_geo_assets_body(self.layout, context)


class HUMANBODY_PT_props_cloth_builder(bpy.types.Panel):
    bl_label = "Cloth Builder"
    bl_idname = "HUMANBODY_PT_props_cloth_builder"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'data'
    bl_parent_id = "HUMANBODY_PT_props_wardrobe"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _poll_humanbody(context)

    def draw(self, context):
        _draw_cloth_builder_body(self.layout, context)


class HUMANBODY_PT_props_cloth_primitive(bpy.types.Panel):
    bl_label = "Cloth - Primitive"
    bl_idname = "HUMANBODY_PT_props_cloth_primitive"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'data'
    bl_parent_id = "HUMANBODY_PT_props_wardrobe"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _poll_humanbody(context)

    def draw(self, context):
        _draw_cloth_primitive_body(self.layout, context)


class HUMANBODY_PT_props_cloth_template(bpy.types.Panel):
    bl_label = "Cloth - from Template"
    bl_idname = "HUMANBODY_PT_props_cloth_template"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'data'
    bl_parent_id = "HUMANBODY_PT_props_wardrobe"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _poll_humanbody(context)

    def draw(self, context):
        _draw_cloth_template_body(self.layout, context)


class HUMANBODY_PT_props_hair(bpy.types.Panel):
    bl_label = "Hair / Brows / Lashes"
    bl_idname = "HUMANBODY_PT_props_hair"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'data'
    bl_parent_id = "HUMANBODY_PT_props_main"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _poll_humanbody(context)

    def draw(self, context):
        _draw_hair_body(self.layout, context)


class HUMANBODY_PT_props_rig(bpy.types.Panel):
    bl_label = "Rig"
    bl_idname = "HUMANBODY_PT_props_rig"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'data'
    bl_parent_id = "HUMANBODY_PT_props_main"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _poll_humanbody(context)

    def draw(self, context):
        _draw_rig_body(self.layout, context)


class HUMANBODY_PT_props_pose(bpy.types.Panel):
    bl_label = "Pose"
    bl_idname = "HUMANBODY_PT_props_pose"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'data'
    bl_parent_id = "HUMANBODY_PT_props_main"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _poll_humanbody(context)

    def draw(self, context):
        _draw_pose_body(self.layout, context)


class HUMANBODY_PT_props_animation(bpy.types.Panel):
    bl_label = "Animation"
    bl_idname = "HUMANBODY_PT_props_animation"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'data'
    bl_parent_id = "HUMANBODY_PT_props_main"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _poll_humanbody(context)

    def draw(self, context):
        _draw_animation_body(self.layout, context)


class HUMANBODY_PT_props_randomize(bpy.types.Panel):
    bl_label = "Randomize"
    bl_idname = "HUMANBODY_PT_props_randomize"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'data'
    bl_parent_id = "HUMANBODY_PT_props_main"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _poll_humanbody(context)

    def draw(self, context):
        _draw_randomize_body(self.layout, context)


class HUMANBODY_PT_props_finalize(bpy.types.Panel):
    bl_label = "Finalize"
    bl_idname = "HUMANBODY_PT_props_finalize"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'data'
    bl_parent_id = "HUMANBODY_PT_props_main"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _poll_humanbody(context)

    def draw(self, context):
        _draw_finalize_body(self.layout, context)


class HUMANBODY_PT_props_file_io(bpy.types.Panel):
    bl_label = "File I/O"
    bl_idname = "HUMANBODY_PT_props_file_io"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'data'
    bl_parent_id = "HUMANBODY_PT_props_main"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return True

    def draw(self, context):
        _draw_file_io_body(self.layout, context)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = (
    HUMANBODY_OT_toggle_category,
    HUMANBODY_OT_select_category,
    HUMANBODY_OT_nudge_prop,
    HUMANBODY_OT_pick_part,
    HUMANBODY_OT_select_wardrobe_cat,
    HUMANBODY_OT_select_anim_cat,
    # N-Panel (3D Viewport sidebar)
    HUMANBODY_PT_main,
    HUMANBODY_PT_body_type,
    HUMANBODY_PT_materials,
    HUMANBODY_PT_parts,
    HUMANBODY_PT_favorites,
    HUMANBODY_PT_wardrobe,
    HUMANBODY_PT_asset_creator,
    HUMANBODY_PT_geo_assets,
    HUMANBODY_PT_cloth_builder,
    HUMANBODY_PT_cloth_primitive,
    HUMANBODY_PT_cloth_template,
    HUMANBODY_PT_hair,
    HUMANBODY_PT_rig,
    HUMANBODY_PT_pose,
    HUMANBODY_PT_animation,
    HUMANBODY_PT_randomize,
    HUMANBODY_PT_finalize,
    HUMANBODY_PT_file_io,
    # Properties Editor (Object Data Properties)
    HUMANBODY_PT_props_main,
    HUMANBODY_PT_props_body_type,
    HUMANBODY_PT_props_materials,
    HUMANBODY_PT_props_parts,
    HUMANBODY_PT_props_favorites,
    HUMANBODY_PT_props_wardrobe,
    HUMANBODY_PT_props_asset_creator,
    HUMANBODY_PT_props_geo_assets,
    HUMANBODY_PT_props_cloth_builder,
    HUMANBODY_PT_props_cloth_primitive,
    HUMANBODY_PT_props_cloth_template,
    HUMANBODY_PT_props_hair,
    HUMANBODY_PT_props_rig,
    HUMANBODY_PT_props_pose,
    HUMANBODY_PT_props_animation,
    HUMANBODY_PT_props_randomize,
    HUMANBODY_PT_props_finalize,
    HUMANBODY_PT_props_file_io,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    # Install depsgraph handler for live L2 morph updates
    global _depsgraph_handler
    _depsgraph_handler = _on_depsgraph_update
    bpy.app.handlers.depsgraph_update_post.append(_depsgraph_handler)


def unregister():
    global _depsgraph_handler
    if _depsgraph_handler in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_depsgraph_handler)
    _depsgraph_handler = None

    # Den Timer mit abmelden (Review 13.08.2026). Er ist einmalig
    # (`_deferred_mesh_update` gibt auf allen Wegen None zurueck, Blender meldet
    # ihn danach selbst ab) — das Fenster ist also klein: Wird das Addon in den
    # 10 ms nach einer Morph-Aenderung deaktiviert, feuert er noch EINMAL und
    # greift dann auf abgemeldete Klassen zu. Ein Traceback beim Deaktivieren
    # sieht aus wie ein kaputtes Addon; das ist es nicht wert.
    if bpy.app.timers.is_registered(_deferred_mesh_update):
        bpy.app.timers.unregister(_deferred_mesh_update)

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
