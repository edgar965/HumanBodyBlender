# -*- coding: utf-8 -*-
import bpy
from .zustand import Anzeigezustand


class HUMANBODY_OT_toggle_category(bpy.types.Operator):
    """Toggle a body part category open/closed in the tree view"""
    bl_idname = "humanbody.toggle_category"
    bl_label = "Toggle Category"
    bl_options = {'INTERNAL'}

    category: bpy.props.StringProperty()

    def execute(self, context):
        if self.category in Anzeigezustand.aufgeklappt:
            Anzeigezustand.aufgeklappt.discard(self.category)
        else:
            Anzeigezustand.aufgeklappt.add(self.category)
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
