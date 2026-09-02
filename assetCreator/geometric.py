# SPDX-License-Identifier: GPL-3.0-or-later
#
# Geometric Assets — simple primitives placed on body regions.

import bpy
import bmesh
from bpy.props import (EnumProperty, FloatProperty, FloatVectorProperty,
                       IntProperty)

from ..assetCreator.vorschau.vorschausuche import Vorschausuche

# Die Bauteile liegen in `assetCreator/`. Hier bleibt, was Blender
# sieht: die Klassen und die Anmeldung.
from .geoformen import Geoformen
from .geometriedaten import Geometrieassets

# ---------------------------------------------------------------------------
# Enum items
# ---------------------------------------------------------------------------

GEO_REGIONS = [
    ("ARMS",  "Arme",   ""),
    ("HANDS", "Haende", ""),
    ("NECK",  "Hals",   ""),
    ("HEAD",  "Kopf",   ""),
    ("TORSO", "Rumpf",  ""),
    ("LEGS",  "Beine",  ""),
    ("FEET",  "Fuesse", ""),
]

GEO_SHAPES = [
    ("CYLINDER", "Zylinder", ""),
    ("BOX",      "Quader",   ""),
    ("TRIANGLE", "Dreieck",  ""),
    ("DISC",     "Scheibe",  ""),
]

# ---------------------------------------------------------------------------
# Region vertex filter (world-space bounds, female rest pose)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# PropertyGroup
# ---------------------------------------------------------------------------

class HumanBodyGeoAssetProps(bpy.types.PropertyGroup):
    region: EnumProperty(
        name="Region",
        items=GEO_REGIONS,
        default="TORSO",
    )
    shape: EnumProperty(
        name="Shape",
        items=GEO_SHAPES,
        default="CYLINDER",
    )
    offset: FloatProperty(
        name="Abstand",
        default=0.01, min=0.0, max=0.1,
        step=0.1, precision=3,
    )
    scale: FloatProperty(
        name="Groesse",
        default=1.0, min=0.1, max=5.0,
        step=1, precision=2,
    )
    segments: IntProperty(
        name="Segmente",
        default=16, min=3, max=64,
    )
    color: FloatVectorProperty(
        name="Farbe",
        subtype='COLOR',
        default=(0.6, 0.6, 0.6),
        min=0, max=1, size=3,
    )


# ---------------------------------------------------------------------------
# Create operator
# ---------------------------------------------------------------------------

GEO_TAG = "hb_geo_asset"


class HUMANBODY_OT_create_geo_asset(bpy.types.Operator):
    """Create a geometric primitive on a body region"""
    bl_idname = "humanbody.create_geo_asset"
    bl_label = "Erstellen"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if obj and obj.type == 'MESH' and obj.data.get("humanbody"):
            return True
        for o in context.scene.objects:
            if o.type == 'MESH' and o.data.get("humanbody"):
                return True
        return False

    def execute(self, context):
        body = Vorschausuche.find_body_obj(context)
        if not body:
            self.report({'WARNING'}, "No HumanBody object found")
            return {'CANCELLED'}

        props = context.scene.humanbody_geo_asset
        region = props.region
        shape = props.shape

        center, size, normal = Geometrieassets._get_region_data(body, region)
        radius, height = Geoformen.masse(size, props.scale)

        bm = Geoformen.bauen(shape, radius, height, props.segments,
                             size, props.scale)

        # Apply region-based rotation
        rot_mat = Geometrieassets._region_orientation(region)
        bmesh.ops.transform(bm, matrix=rot_mat, verts=bm.verts[:])

        # Position: center + normal * offset
        bmesh.ops.translate(bm, vec=center + normal * props.offset,
                            verts=bm.verts[:])

        self._objekt_bauen(context, body, bm, region, shape, props.color)
        self.report({'INFO'}, f"Geometric Asset erstellt: {region} / {shape}")
        return {'FINISHED'}

    @staticmethod
    def _objekt_bauen(context, body, bm, region, shape, color):
        u"""Netz, Objekt, Material, Merkmal, Elternschaft.

        `bm` wird dabei geleert; der Aufrufer darf es danach nicht mehr
        anfassen.
        """
        mesh = bpy.data.meshes.new(f"hb_geo_{region}_{shape}")
        bm.to_mesh(mesh)
        bm.free()

        obj = bpy.data.objects.new(f"GeoAsset_{region}_{shape}", mesh)
        context.collection.objects.link(obj)

        # Smooth shading
        for poly in obj.data.polygons:
            poly.use_smooth = True

        # Material
        obj.data.materials.append(
            Geometrieassets._create_material(f"{region}_{shape}", color))

        # Tag as geo asset
        obj[GEO_TAG] = True

        # Parent to body
        obj.parent = body
        obj.matrix_parent_inverse = body.matrix_world.inverted()
        return obj


# ---------------------------------------------------------------------------
# Remove operator
# ---------------------------------------------------------------------------

class HUMANBODY_OT_remove_geo_assets(bpy.types.Operator):
    """Remove all geometric assets from the scene"""
    bl_idname = "humanbody.remove_geo_assets"
    bl_label = "Alle entfernen"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        for obj in context.scene.objects:
            if obj.get(GEO_TAG):
                return True
        return False

    def execute(self, context):
        removed = 0
        to_remove = [obj for obj in context.scene.objects if obj.get(GEO_TAG)]
        for obj in to_remove:
            bpy.data.objects.remove(obj, do_unlink=True)
            removed += 1
        self.report({'INFO'}, f"{removed} Geometric Asset(s) entfernt")
        return {'FINISHED'}
