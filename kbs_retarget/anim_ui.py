 

from bpy.types import Menu


# class ANIMRETARGET_PT_help:
#     bl_label = "Help"
#     bl_region_type = 'UI'
#     bl_category = 'Anim_RT'
#     bl_options = {'DEFAULT_CLOSED'}
#
#     def draw(self, context):
#
#         layout = self.layout
#
#         row = layout.row(align=True)
#
#         row.operator('anim.retarget_aide_manual', text='', icon='HELP', emboss=False)
#         row.operator('anim.retarget_aide_demo', text='', icon='FILE_MOVIE', emboss=False)


# class ANIMRETARGET_PT_info:
#     bl_label = "Info"
#     bl_region_type = 'UI'
#     bl_category = 'Anim_RT'
#
#     def draw(self, context):
#
#         layout = self.layout
#
#         layout.label(text='-Anim-offset and Key-manager')
#         layout.label(text='can now be put on the headers')
#         layout.label(text='instead of the panels.')
#         layout.label(text='-that and other preferences are')
#         layout.label(text='now located in the addon tab')
#         layout.label(text='in Blender Preferences.')
#         layout.label(text='Because of that Blender')
#         layout.label(text='will remember them after')
#         layout.label(text='you quit.')
#         layout.label(text='-This info panel can also')
#         layout.label(text='be removed in the addon')
#         layout.label(text='preferences.')
#         layout.label(text='Find more information at:')
#         layout.label(text='https://github.com/aresdevo/animaide')


# class ANIMRETARGET_PT_info_3d(Panel, ANIMRETARGET_PT_info):
#     bl_idname = 'ANIMRETARGET_PT_info_3d'
#     bl_space_type = 'VIEW_3D'
#
#
# class ANIMRETARGET_PT_info_ge(Panel, ANIMRETARGET_PT_info):
#     bl_idname = 'ANIMRETARGET_PT_info_ge'
#     bl_space_type = 'GRAPH_EDITOR'
#
#
# class ANIMRETARGET_PT_info_de(Panel, ANIMRETARGET_PT_info):
#     bl_idname = 'ANIMRETARGET_PT_info_de'
#     bl_space_type = 'DOPESHEET_EDITOR'


class ANIMRETARGET_MT_operators(Menu):
    bl_idname = 'ANIMRETARGET_MT_menu_operators'
    bl_label = "Anim_RT"

    @classmethod
    def poll(cls, context):
        if context.mode not in ['POSE', 'OBJECT']:
            return False
       
        return True


    def draw(self, context):
        layout = self.layout

        if context.area.type == 'VIEW_3D':
            layout.menu('ANIMRETARGET_MT_curve_tools', text='On Frame Curve Tools')
            layout.separator()
            layout.menu('ANIMRETARGET_MT_anim_offset')

        elif context.area.type == 'DOPESHEET_EDITOR':
            layout.operator('wm.call_menu_pie', text="Pie Anim Aide").name = 'ANIMRETARGET_MT_PIE_Retarget_anim_aide'
            layout.menu('ANIMRETARGET_MT_anim_offset')
            layout.menu('ANIMRETARGET_MT_anim_offset_mask')

        elif context.area.type == 'GRAPH_EDITOR':
            layout.operator('wm.call_menu_pie', text="Pie Anim Aide").name = 'ANIMRETARGET_MT_PIE_Retarget_anim_aide'
            layout.menu('ANIMRETARGET_MT_curve_tools')
            layout.menu('ANIMRETARGET_MT_tweak')
            layout.separator()
            layout.menu('ANIMRETARGET_MT_anim_offset')
            layout.menu('ANIMRETARGET_MT_anim_offset_mask')


def draw_menu(self, context):
    if context.mode == 'OBJECT' or context.mode == 'POSE':
        layout = self.layout
        layout.menu('ANIMRETARGET_MT_menu_operators')


menu_classes = (
    ANIMRETARGET_MT_operators,
)

# info_classes = (
#     ANIMRETARGET_PT_info_3d,
#     ANIMRETARGET_PT_info_ge,
#     ANIMRETARGET_PT_info_de,
# )
