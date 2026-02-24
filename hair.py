# SPDX-License-Identifier: GPL-3.0-or-later
#
# Hair system for HumanBody addon.
# Hair colors, materials, hairstyle loading, hair operators.

import os
import logging

import bpy
import numpy

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hair color presets (from HumanBody hair_colors.yaml)
# ---------------------------------------------------------------------------

HAIR_COLORS = {
    "Silken Black":       {"melanin": 1.0,   "melanin_redness": 0.3, "viewport": (0.02, 0.02, 0.02)},
    "Dark Brown":         {"melanin": 0.814, "melanin_redness": 0.3, "viewport": (0.08, 0.04, 0.02)},
    "Cocoa Brown":        {"melanin": 0.514, "melanin_redness": 0.3, "viewport": (0.25, 0.12, 0.05)},
    "Light Golden Brown": {"melanin": 0.114, "melanin_redness": 0.3, "viewport": (0.7, 0.5, 0.25)},
    "Honey Blonde":       {"melanin": 0.373, "melanin_redness": 1.0, "viewport": (0.6, 0.26, 0.08)},
    "Light Blonde":       {"melanin": 0.373, "melanin_redness": 1.0, "viewport": (0.6, 0.3, 0.05),
                           "coat": 0.686, "ior": 5.15, "offset": 0.18},
    "Auburn":             {"melanin": 0.5,   "melanin_redness": 0.8, "viewport": (0.5, 0.2, 0.05)},
    "Natural Black":      {"melanin": 1.0,   "melanin_redness": 0.005, "viewport": (0.05, 0.05, 0.05)},
    "Burgundy":           {"melanin": 1.0,   "melanin_redness": 0.005, "viewport": (0.13, 0.085, 0.08),
                           "random_color": 0.568},
    "Plum":               {"melanin": 0.3,   "melanin_redness": 0.3, "viewport": (0.33, 0.17, 0.05)},
}


# ---------------------------------------------------------------------------
# Eye colors (linear sRGB)
# ---------------------------------------------------------------------------

EYE_COLORS = {
    "Blue":    (0.08, 0.20, 0.65),
    "Green":   (0.10, 0.35, 0.15),
    "Brown":   (0.15, 0.07, 0.03),
    "Hazel":   (0.30, 0.20, 0.07),
    "Gray":    (0.25, 0.25, 0.27),
    "Amber":   (0.45, 0.25, 0.05),
}


# ---------------------------------------------------------------------------
# Material helpers
# ---------------------------------------------------------------------------

def _create_hair_material(name, color_key):
    """Create a Principled Hair BSDF material."""
    mat = bpy.data.materials.new(name)
    tree = mat.node_tree
    tree.nodes.clear()

    hair_node = tree.nodes.new("ShaderNodeBsdfHairPrincipled")
    hair_node.location = (0, 0)
    hair_node.parametrization = 'MELANIN'

    output = tree.nodes.new("ShaderNodeOutputMaterial")
    output.location = (300, 0)
    tree.links.new(hair_node.outputs[0], output.inputs[0])

    settings = HAIR_COLORS.get(color_key, {})
    hair_node.inputs[1].default_value = settings.get("melanin", 0.8)
    hair_node.inputs[2].default_value = settings.get("melanin_redness", 0.3)
    hair_node.inputs[5].default_value = settings.get("roughness", 0.5)
    hair_node.inputs[6].default_value = settings.get("radial_roughness", 0.05)
    hair_node.inputs[7].default_value = settings.get("coat", 0.0)
    hair_node.inputs[8].default_value = settings.get("ior", 1.45)
    hair_node.inputs[9].default_value = settings.get("offset", 0.035)
    hair_node.inputs[10].default_value = settings.get("random_color", 0.0)
    hair_node.inputs[11].default_value = settings.get("random_roughness", 0.0)

    vp = settings.get("viewport", (0.02, 0.02, 0.02))
    mat.diffuse_color = (vp[0], vp[1], vp[2], 1.0)

    return mat


def _create_mesh_hair_material(name, color_key):
    """Create a Principled BSDF material for mesh-based hair."""
    mat = bpy.data.materials.new(name)
    tree = mat.node_tree
    tree.nodes.clear()

    bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (0, 0)

    output = tree.nodes.new("ShaderNodeOutputMaterial")
    output.location = (300, 0)
    tree.links.new(bsdf.outputs[0], output.inputs[0])

    settings = HAIR_COLORS.get(color_key, {})
    vp = settings.get("viewport", (0.08, 0.04, 0.02))
    bsdf.inputs['Base Color'].default_value = (vp[0], vp[1], vp[2], 1.0)
    bsdf.inputs['Roughness'].default_value = 0.4

    mat.diffuse_color = (vp[0], vp[1], vp[2], 1.0)
    return mat


def _apply_hair_color(mat, color_key):
    """Update an existing hair material's color settings."""
    if not mat or not mat.node_tree:
        return
    settings = HAIR_COLORS.get(color_key, {})
    vp = settings.get("viewport", (0.02, 0.02, 0.02))
    for node in mat.node_tree.nodes:
        if node.type == 'BSDF_HAIR_PRINCIPLED':
            node.inputs[1].default_value = settings.get("melanin", 0.8)
            node.inputs[2].default_value = settings.get("melanin_redness", 0.3)
            node.inputs[7].default_value = settings.get("coat", 0.0)
            node.inputs[8].default_value = settings.get("ior", 1.45)
            node.inputs[10].default_value = settings.get("random_color", 0.0)
            mat.diffuse_color = (vp[0], vp[1], vp[2], 1.0)
            return
        elif node.type == 'BSDF_PRINCIPLED' and mat.name.startswith("HumanBody_Hair"):
            node.inputs['Base Color'].default_value = (vp[0], vp[1], vp[2], 1.0)
            mat.diffuse_color = (vp[0], vp[1], vp[2], 1.0)
            return


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _get_hairstyles_dir():
    """Return path to hairstyles data directory."""
    from .morphing import MorphData
    return os.path.join(MorphData._addon_data_dir(), "hairstyles")


def _get_assets_root():
    """Get the parent directory of the addon (resolves symlinks/junctions)."""
    return os.path.dirname(os.path.realpath(os.path.dirname(__file__)))


def _get_hair_blend_path():
    """Get path to the HumanBody particle hair .blend asset."""
    return os.path.join(_get_assets_root(), "HumanBodyAssets",
                        "characters", "mb_female", "hair.blend")


def _get_mesh_hair_blend_path():
    """Get path to the mesh hair .blend asset."""
    _tools = os.path.dirname(os.path.dirname(__file__))
    _hb = os.path.join(_tools, "HumanBody") if os.path.isdir(os.path.join(_tools, "HumanBody")) else r"A:\3DTools\HumanBody"
    local = os.path.join(_hb, "data", "assets",
                         "Other", "mesh_hair01.blend")
    if os.path.isfile(local):
        return local
    return os.path.join(_get_assets_root(), "HumanBodyAssets",
                        "characters", "mb_female", "assets", "mesh_hair01.blend")


# ---------------------------------------------------------------------------
# Hair listing / vertex group
# ---------------------------------------------------------------------------

def _list_hairstyles():
    """List available hair assets (blend-based)."""
    assets = []
    if os.path.isfile(_get_hair_blend_path()):
        assets.append(("blend:particle", "Particle Hair"))
    if os.path.isfile(_get_mesh_hair_blend_path()):
        assets.append(("blend:mesh", "Mesh Hair"))
    # Scan hairstyles directory for additional .blend files
    hs_dir = _get_hairstyles_dir()
    if os.path.isdir(hs_dir):
        for fname in sorted(os.listdir(hs_dir)):
            if fname.endswith(".blend"):
                name = fname[:-6]
                label = name.replace("_", " ").title()
                assets.append((f"blend:custom:{name}", label))
    return assets


def _ensure_hair_vg(obj):
    """Ensure hair vertex group exists on the character. Load from _hair_vg.npz if needed."""
    vg = obj.vertex_groups.get("hair_scalp")
    if vg:
        return vg

    npz_path = os.path.join(_get_hairstyles_dir(), "_hair_vg.npz")
    if not os.path.isfile(npz_path):
        return None

    z = numpy.load(npz_path)
    indices = z["indices"]
    weights = z["weights"]

    vg = obj.vertex_groups.new(name="hair_scalp")
    for idx, w in zip(indices, weights):
        vg.add([int(idx)], float(w), 'REPLACE')
    return vg


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class HUMANBODY_OT_create_hair(bpy.types.Operator):
    bl_idname = "humanbody.create_hair"
    bl_label = "Create Hair"
    bl_description = "Add procedural particle hair to the character"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            return {'CANCELLED'}

        props = context.scene.humanbody
        color_key = props.hair_color

        # Check for existing hair system
        for ps in obj.particle_systems:
            if ps.settings.type == 'HAIR':
                self.report({'WARNING'}, "Hair already exists. Remove first.")
                return {'CANCELLED'}

        # Ensure hair vertex group
        vg = _ensure_hair_vg(obj)

        # Create hair material
        mat_name = "HumanBody_Hair"
        mat = _create_hair_material(mat_name, color_key)
        obj.data.materials.append(mat)
        mat_slot = len(obj.data.materials)

        # Add particle system
        mod = obj.modifiers.new("HumanBody_Hair", 'PARTICLE_SYSTEM')
        psys = mod.particle_system
        s = psys.settings
        s.type = 'HAIR'

        # Assign vertex group BEFORE count so distribution respects it
        if vg:
            psys.vertex_group_density = vg.name
            psys.vertex_group_length = vg.name

        s.hair_length = props.hair_length
        s.count = props.hair_count
        s.child_type = 'INTERPOLATED'
        s.child_percent = 10
        s.rendered_child_count = 50
        s.create_long_hair_children = True
        s.root_radius = 0.005
        s.tip_radius = 0.001
        s.material = mat_slot

        self.report({'INFO'}, f"Hair created with color: {color_key}")
        return {'FINISHED'}


class HUMANBODY_OT_load_hairstyle(bpy.types.Operator):
    bl_idname = "humanbody.load_hairstyle"
    bl_label = "Load Hairstyle"
    bl_description = "Load a pre-made hairstyle from asset library"
    bl_options = {'REGISTER', 'UNDO'}

    asset_key: bpy.props.StringProperty()

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            return {'CANCELLED'}

        props = context.scene.humanbody

        # Remove existing hair objects first
        for o in list(bpy.data.objects):
            if o.get("humanbody_hair"):
                bpy.data.objects.remove(o, do_unlink=True)

        if self.asset_key == "blend:particle":
            return self._load_particle_hair(context, obj, props)
        elif self.asset_key == "blend:mesh":
            return self._load_mesh_hair(context, obj, props)
        elif self.asset_key.startswith("blend:custom:"):
            name = self.asset_key.split(":", 2)[2]
            return self._load_custom_hair(context, obj, props, name)
        else:
            self.report({'ERROR'}, f"Unknown asset: {self.asset_key}")
            return {'CANCELLED'}

    def _load_particle_hair(self, context, obj, props):
        blend_path = _get_hair_blend_path()
        if not os.path.isfile(blend_path):
            self.report({'ERROR'}, "hair.blend not found")
            return {'CANCELLED'}

        with bpy.data.libraries.load(blend_path, link=False) as (data_from, data_to):
            data_to.objects = ["hair"]

        hair_obj = bpy.data.objects.get("hair")
        if not hair_obj:
            self.report({'ERROR'}, "Failed to load hair object")
            return {'CANCELLED'}

        # Link to scene
        context.collection.objects.link(hair_obj)

        # Create and apply hair material
        mat = _create_hair_material("HumanBody_Hair", props.hair_color)
        hair_obj.data.materials.clear()
        hair_obj.data.materials.append(mat)
        for ps in hair_obj.particle_systems:
            ps.settings.material = 1

        # Parent to character
        hair_obj.parent = obj
        hair_obj.location = (0, 0, 0)
        hair_obj["humanbody_hair"] = True

        # Hide base mesh of hair object (only particles should be visible)
        hair_obj.display_type = 'WIRE'

        self.report({'INFO'}, "Particle hair loaded (3 systems)")
        return {'FINISHED'}

    def _load_mesh_hair(self, context, obj, props):
        blend_path = _get_mesh_hair_blend_path()
        if not os.path.isfile(blend_path):
            self.report({'ERROR'}, "mesh_hair01.blend not found")
            return {'CANCELLED'}

        with bpy.data.libraries.load(blend_path, link=False) as (data_from, data_to):
            data_to.objects = ["hair01_human_female"]

        hair_obj = bpy.data.objects.get("hair01_human_female")
        if not hair_obj:
            self.report({'ERROR'}, "Failed to load mesh hair object")
            return {'CANCELLED'}

        # Link to scene
        context.collection.objects.link(hair_obj)

        # Strip body faces: the mesh hair contains the full body topology
        # (first N verts) plus additional hair-only vertices.
        # Delete all faces that only use body-range vertex indices.
        body_vcount = len(obj.data.vertices)
        hair_vcount = len(hair_obj.data.vertices)
        if hair_vcount > body_vcount:
            import bmesh
            bm = bmesh.new()
            bm.from_mesh(hair_obj.data)
            bm.faces.ensure_lookup_table()
            to_del = [f for f in bm.faces
                      if all(v.index < body_vcount for v in f.verts)]
            if to_del:
                bmesh.ops.delete(bm, geom=to_del, context='FACES')
                # Clean up orphaned vertices
                loose = [v for v in bm.verts if not v.link_faces]
                if loose:
                    bmesh.ops.delete(bm, geom=loose, context='VERTS')
            bm.to_mesh(hair_obj.data)
            bm.free()

        # Apply mesh hair material (Principled BSDF, not Hair BSDF)
        mat = _create_mesh_hair_material("HumanBody_Hair_Mesh", props.hair_color)
        hair_obj.data.materials.clear()
        hair_obj.data.materials.append(mat)

        # Smooth shading
        for poly in hair_obj.data.polygons:
            poly.use_smooth = True

        # Parent to character
        hair_obj.parent = obj
        hair_obj.location = (0, 0, 0)
        hair_obj["humanbody_hair"] = True

        self.report({'INFO'}, "Mesh hair loaded")
        return {'FINISHED'}

    def _load_custom_hair(self, context, obj, props, name):
        blend_path = os.path.join(_get_hairstyles_dir(), name + ".blend")
        if not os.path.isfile(blend_path):
            self.report({'ERROR'}, f"{name}.blend not found")
            return {'CANCELLED'}

        with bpy.data.libraries.load(blend_path, link=False) as (data_from, data_to):
            data_to.objects = data_from.objects[:]

        hair_obj = None
        for o in data_to.objects:
            if o and o.type == 'MESH':
                hair_obj = o
                break

        if not hair_obj:
            self.report({'ERROR'}, f"No mesh in {name}.blend")
            return {'CANCELLED'}

        context.collection.objects.link(hair_obj)

        # Apply mesh hair material
        mat = _create_mesh_hair_material(f"HumanBody_Hair_{name}", props.hair_color)
        hair_obj.data.materials.clear()
        hair_obj.data.materials.append(mat)

        for poly in hair_obj.data.polygons:
            poly.use_smooth = True

        hair_obj["humanbody_hair"] = True

        # Rig the hair: parent to armature + transfer bone weights
        from .rig import _find_rig
        rig = _find_rig(obj)
        if rig:
            hair_obj.parent = rig
            hair_obj.matrix_parent_inverse = rig.matrix_world.inverted()
            hair_obj.location = (0, 0, 0)

            mod = hair_obj.modifiers.new("HumanBody_Rig", "ARMATURE")
            mod.object = rig
            mod.use_vertex_groups = True

            # Transfer DEF- bone weights from body via nearest vertex
            from mathutils.kdtree import KDTree
            mat_body = obj.matrix_world
            n_body = len(obj.data.vertices)
            kd = KDTree(n_body)
            for i, v in enumerate(obj.data.vertices):
                kd.insert(mat_body @ v.co, i)
            kd.balance()

            # Collect body DEF- vertex groups
            def_groups = {vg.index: vg for vg in obj.vertex_groups
                          if vg.name.startswith("DEF-")}
            # Create matching groups on hair
            for vg in def_groups.values():
                if vg.name not in hair_obj.vertex_groups:
                    hair_obj.vertex_groups.new(name=vg.name)

            mat_hair = hair_obj.matrix_world
            for hv in hair_obj.data.vertices:
                co_world = mat_hair @ hv.co
                _co, body_vi, _dist = kd.find(co_world)
                for gi, vg in def_groups.items():
                    try:
                        w = vg.weight(body_vi)
                    except RuntimeError:
                        continue
                    if w > 0.001:
                        hair_obj.vertex_groups[vg.name].add(
                            [hv.index], w, 'REPLACE')
        else:
            # No rig: just parent to body
            hair_obj.parent = obj
            hair_obj.location = (0, 0, 0)

        self.report({'INFO'}, f"Loaded: {name}")
        return {'FINISHED'}


class HUMANBODY_OT_remove_hair(bpy.types.Operator):
    bl_idname = "humanbody.remove_hair"
    bl_label = "Remove Hair"
    bl_description = "Remove particle hair system from the character"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            return {'CANCELLED'}

        removed = False

        # Remove hair asset objects (loaded from .blend)
        for o in list(bpy.data.objects):
            if o.get("humanbody_hair"):
                bpy.data.objects.remove(o, do_unlink=True)
                removed = True

        # Remove particle systems on the body itself (from Create Hair)
        for mod in list(obj.modifiers):
            if mod.type == 'PARTICLE_SYSTEM' and mod.particle_system:
                if mod.particle_system.settings.type == 'HAIR':
                    obj.modifiers.remove(mod)
                    removed = True

        # Clean up hair materials on body (reverse to keep indices stable)
        for i in range(len(obj.data.materials) - 1, -1, -1):
            mat = obj.data.materials[i]
            if mat and mat.name.startswith("HumanBody_Hair"):
                obj.data.materials.pop(index=i)

        if removed:
            self.report({'INFO'}, "Hair removed")
        else:
            self.report({'WARNING'}, "No hair found")
        return {'FINISHED'}


class HUMANBODY_OT_recolor_hair(bpy.types.Operator):
    bl_idname = "humanbody.recolor_hair"
    bl_label = "Apply Color"
    bl_description = "Change hair color to selected preset"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            return {'CANCELLED'}

        props = context.scene.humanbody
        found = False

        # Recolor hair on body itself
        for mat in obj.data.materials:
            if mat and mat.name.startswith("HumanBody_Hair"):
                _apply_hair_color(mat, props.hair_color)
                found = True

        # Recolor hair asset objects
        for o in bpy.data.objects:
            if o.get("humanbody_hair"):
                for mat in o.data.materials:
                    if mat and mat.name.startswith("HumanBody_Hair"):
                        _apply_hair_color(mat, props.hair_color)
                        found = True

        if found:
            self.report({'INFO'}, f"Hair color: {props.hair_color}")
            return {'FINISHED'}

        self.report({'WARNING'}, "No hair material found")
        return {'CANCELLED'}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = (
    HUMANBODY_OT_create_hair,
    HUMANBODY_OT_load_hairstyle,
    HUMANBODY_OT_remove_hair,
    HUMANBODY_OT_recolor_hair,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
