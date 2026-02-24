 

import bpy
from . import anim_ui, curve_tools, anim_offset, key_manager, utils
from bpy.app.handlers import persistent
from bpy.props import PointerProperty
from bpy.types import PropertyGroup


class AnimRetargetScene(PropertyGroup):
    clone: PointerProperty(type=curve_tools.props.AnimRetargetClone)
    tool: PointerProperty(type=curve_tools.props.AnimRetargetTool)
    anim_offset: PointerProperty(type=anim_offset.props.AnimRetargetOffset)
    key_tweak: PointerProperty(type=key_manager.props.KeyTweak)

classes = \
    anim_offset.classes + \
    curve_tools.classes + \
    key_manager.classes + \
    anim_ui.menu_classes + \
    (AnimRetargetScene,)

@persistent
def load_post_handler(scene):
    # if support.magnet_handlers in bpy.app.handlers.depsgraph_update_post:
    #     bpy.app.handlers.depsgraph_update_post.remove(support.magnet_handlers)
    utils.remove_message()
    print('init')


def register_classes():

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.app.handlers.load_post.append(load_post_handler)

    bpy.types.Scene.animretarget = PointerProperty(type=AnimRetargetScene)

    # bpy.types.TIME_MT_editor_menus.append(curve_tools.ui.draw_bookmarks)

    bpy.types.DOPESHEET_MT_editor_menus.append(anim_ui.draw_menu)
    bpy.types.GRAPH_MT_editor_menus.append(anim_ui.draw_menu)
    bpy.types.VIEW3D_MT_editor_menus.append(anim_ui.draw_menu)
    # bpy.types.TIME_MT_editor_menus.append(ui.draw_menu)

    # if pref.info_panel:
    #     for cls in ui.info_classes:
    #         bpy.utils.register_class(cls)

    # atexit.register(utils.remove_message)


def unregister_classes():

    # utils.remove_message()

    bpy.app.handlers.load_post.remove(load_post_handler)

    # bpy.types.TIME_MT_editor_menus.remove(curve_tools.ui.draw_bookmarks)

    bpy.types.DOPESHEET_MT_editor_menus.remove(anim_ui.draw_menu)
    bpy.types.GRAPH_MT_editor_menus.remove(anim_ui.draw_menu)
    bpy.types.VIEW3D_MT_editor_menus.remove(anim_ui.draw_menu)
    # bpy.types.TIME_MT_editor_menus.remove(ui.draw_menu)

    # if pref.info_panel:
    #     for cls in reversed(ui.info_classes):
    #         bpy.utils.unregister_class(cls)

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.animretarget
