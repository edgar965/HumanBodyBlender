# -*- coding: utf-8 -*-
import bpy
from ..morphing import Morpher
from .zustand import Anzeigezustand


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


def _build_zone_data(obj, context):
    """Build zone triangles (for overlay) and face→category map (for raycast).

    Uses the evaluated (deformed) mesh for overlay positions, but maps
    each face to its body zone using the REST-pose center so that picking
    stays correct regardless of the current pose.
    """
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

    if not Anzeigezustand.wahl_laeuft or not Anzeigezustand.kategorie_unter_maus:
        return

    import gpu
    from gpu_extras.batch import batch_for_shader

    cat = Anzeigezustand.kategorie_unter_maus
    if cat not in Anzeigezustand.zonendreiecke:
        return

    # Rebuild batch only when hovered category changes
    if Anzeigezustand.stapel is None or Anzeigezustand.stapel_kategorie != cat:
        coords = []
        for v0, v1, v2 in Anzeigezustand.zonendreiecke[cat]:
            coords.extend([v0, v1, v2])
        if not coords:
            return
        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        Anzeigezustand.stapel = batch_for_shader(shader, 'TRIS', {"pos": coords})
        Anzeigezustand.stapel_kategorie = cat

    shader = gpu.shader.from_builtin('UNIFORM_COLOR')

    gpu.state.blend_set('ALPHA')
    gpu.state.depth_test_set('LESS_EQUAL')
    gpu.state.face_culling_set('NONE')

    shader.bind()
    shader.uniform_float("color", (0.3, 0.6, 1.0, 0.22))
    Anzeigezustand.stapel.draw(shader)

    gpu.state.blend_set('NONE')
    gpu.state.depth_test_set('NONE')
    gpu.state.face_culling_set('NONE')


def _deferred_mesh_update():
    """Timer callback: apply pending morph update (debounced)."""
    Anzeigezustand.aktualisierung_offen = False

    if Anzeigezustand.aktualisiert:
        return None
    scene = bpy.context.scene
    if scene is None:
        return None

    for obj in scene.objects:
        if obj.type == 'MESH' and obj.data.get("humanbody"):
            m = Morpher.get(obj)
            if not m.body_type or m.basis is None:
                break
            Anzeigezustand.aktualisiert = True
            try:
                m.update()
            finally:
                Anzeigezustand.aktualisiert = False
            break
    return None


def _on_depsgraph_update(scene, depsgraph):
    """Called after every depsgraph update. Debounces mesh updates."""
    if Anzeigezustand.aktualisiert or Anzeigezustand.aktualisierung_offen:
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
            if h == Anzeigezustand.letzte_werte:
                return  # Nothing changed — skip entirely
            Anzeigezustand.letzte_werte = h
            break
    else:
        return  # No HumanBody object found

    Anzeigezustand.aktualisierung_offen = True
    bpy.app.timers.register(_deferred_mesh_update, first_interval=0.01)
