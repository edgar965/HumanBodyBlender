# SPDX-License-Identifier: GPL-3.0-or-later
#
# Hair system for HumanBody addon.
# Hair colors, materials, hairstyle loading, hair operators.

import logging

from .klassenanmeldung import Klassenanmeldung
import bpy

# Die Bauteile liegen in `haare/`. Hier bleibt, was Blender
# sieht: die Klassen und die Anmeldung.
from .haare.frisurladen import HUMANBODY_OT_load_hairstyle
from .haare.haarmaterial import Haarmaterial
from .haare.haarpfade import Haarpfade

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hair color presets (from HumanBody hair_colors.yaml)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Eye colors (linear sRGB)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Material helpers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Hair listing / vertex group
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class MitNetz:
    u"""Ein Haaroperator, der auf dem aktiven Netz arbeitet.

    Die drei Zeilen standen DREIMAL — in `create_hair`, `remove_hair`
    und `recolor_hair`. Sie bleiben bewusst stumm: Haare sind eine
    Handlung auf dem ausgewaehlten Objekt, und ein Fehlerfenster, weil
    gerade eine Kamera aktiv ist, waere laestiger als der ausbleibende
    Knopfdruck. Ein Mixin OHNE `bpy.types.Operator` als Basis — siehe
    `MitKoerper` in `koerperoperator.py`.
    """

    @staticmethod
    def netz(context):
        u"""Das aktive Netz — oder `None`."""
        obj = context.active_object
        return obj if obj and obj.type == 'MESH' else None


class HUMANBODY_OT_create_hair(MitNetz, bpy.types.Operator):
    bl_idname = "humanbody.create_hair"
    bl_label = "Create Hair"
    bl_description = "Add procedural particle hair to the character"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = self.netz(context)
        if not obj:
            return {'CANCELLED'}

        props = context.scene.humanbody
        color_key = props.hair_color

        # Check for existing hair system
        for ps in obj.particle_systems:
            if ps.settings.type == 'HAIR':
                self.report({'WARNING'}, "Hair already exists. Remove first.")
                return {'CANCELLED'}

        # Ensure hair vertex group
        vg = Haarpfade._ensure_hair_vg(obj)

        # Create hair material
        mat_name = "HumanBody_Hair"
        mat = Haarmaterial._create_hair_material(mat_name, color_key)
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


class HUMANBODY_OT_remove_hair(MitNetz, bpy.types.Operator):
    bl_idname = "humanbody.remove_hair"
    bl_label = "Remove Hair"
    bl_description = "Remove particle hair system from the character"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = self.netz(context)
        if not obj:
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


class HUMANBODY_OT_recolor_hair(MitNetz, bpy.types.Operator):
    bl_idname = "humanbody.recolor_hair"
    bl_label = "Apply Color"
    bl_description = "Change hair color to selected preset"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = self.netz(context)
        if not obj:
            return {'CANCELLED'}

        props = context.scene.humanbody
        found = False

        # Recolor hair on body itself
        for mat in obj.data.materials:
            if mat and mat.name.startswith("HumanBody_Hair"):
                Haarmaterial._apply_hair_color(mat, props.hair_color)
                found = True

        # Recolor hair asset objects
        for o in bpy.data.objects:
            if o.get("humanbody_hair"):
                for mat in o.data.materials:
                    if mat and mat.name.startswith("HumanBody_Hair"):
                        Haarmaterial._apply_hair_color(mat, props.hair_color)
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
    Klassenanmeldung.an(classes)


def unregister():
    Klassenanmeldung.ab(classes)
