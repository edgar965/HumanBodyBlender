# -*- coding: utf-8 -*-
import os
import logging
import bpy
logger = logging.getLogger(__name__)
from .haarmaterial import _create_hair_material
from .haarmaterial import _create_mesh_hair_material
from .haarpfade import _get_hair_blend_path
from .haarpfade import _get_hairstyles_dir
from .haarpfade import _get_mesh_hair_blend_path


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
        from ..rig import _find_rig
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
                    # stumm gewollt: weight() wirft, wenn der Vertex nicht in
                    # der Gruppe ist. Genau das heisst hier Gewicht null.
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
