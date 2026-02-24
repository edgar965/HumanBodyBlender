import bpy
from bpy.props import StringProperty
from bpy.props import BoolProperty
from bpy.props import FloatProperty
from bpy.props import PointerProperty
from bpy.types import Context, Operator, Menu, Panel
from bl_operators.presets import AddPresetBase

from . import operators
from . import preset_handler
from . import bone_utils


def menu_header(layout):
    row = layout.row()
    row.separator()

    row = layout.row()
    row.label(text="Retarget", icon='ARMATURE_DATA')

class BindingsMenu(Menu):
    bl_label = "Binding"
    bl_idname = "OBJECT_MT_retarget_binding_menu"

    def draw(self, context):
        layout = self.layout

        row = layout.row()
        row.operator(operators.ConstrainToArmature.bl_idname)

        row = layout.row()
        row.operator(operators.UnbindArmature.bl_idname)

        row = layout.row()
        row.operator(operators.ConstraintStatus.bl_idname)

        row = layout.row()
        row.operator(operators.SelectConstrainedControls.bl_idname)

        row = layout.row()
        row.operator(operators.AlignBone.bl_idname)


class ConvertMenu(Menu):
    bl_label = "Conversion"
    bl_idname = "OBJECT_MT_retarget_convert_menu"

    def draw(self, context):
        layout = self.layout

        row = layout.row()
        row.operator(operators.ConvertGameFriendly.bl_idname)

        row = layout.row()
        row.operator(operators.ConvertBoneNaming.bl_idname)

        row = layout.row()
        row.operator(operators.ExtractMetarig.bl_idname)

        row = layout.row()
        row.operator(operators.ApplyAsRestPose.bl_idname)

        row = layout.row()
        row.operator(operators.CreateTransformOffset.bl_idname)

        row = layout.row()
        row.operator(operators.MergeHeadTails.bl_idname)


class AnimMenu(Menu):
    bl_label = "Animation"
    bl_idname = "OBJECT_MT_retarget_anim_menu"

    def draw(self, context):
        layout = self.layout

        row = layout.row()
        row.operator(operators.ActionRangeToScene.bl_idname)

        row = layout.row()
        row.operator(operators.AdjustAnimation.bl_idname)

        row = layout.row()
        row.operator(operators.BakeConstrainedActions.bl_idname)

        row = layout.row()
        row.operator(operators.AddRoot.bl_idname)

        row = layout.row()
        row.operator(operators.AddRootMotion.bl_idname)

def pose_context_options(self, context):
    layout = self.layout
    menu_header(layout)

    # use an operator enum property to populate a sub-menu
    layout.operator('wm.call_menu_pie', text="Pie Retarget").name = 'VIEW3D_MT_PIE_Retarget'
    layout.menu(BindingsMenu.bl_idname)
    layout.menu(ConvertMenu.bl_idname)
    layout.menu(AnimMenu.bl_idname)

    layout.separator()


def armature_context_options(self, context):
    layout = self.layout
    menu_header(layout)

    row = layout.row()
    row.operator(operators.MergeHeadTails.bl_idname)


def action_header_buttons(self, context):
    layout = self.layout
    row = layout.row()
    row.operator(operators.ActionRangeToScene.bl_idname, icon='PREVIEW_RANGE', text='To Scene Range')

#pie menu short cut

    
class VIEW3D_MT_PIE_Retarget(Menu):
    bl_idanme = 'VIEW3D_MT_PIE_Retarget'
    bl_label = "RETARGET"

    @classmethod
    def poll(cls, context):
        if context.mode not in ['POSE', 'OBJECT']:
            return False
       
        return True

    def draw(self, context):
        layout = self.layout

        pie = layout.menu_pie()
        
        gap = pie.column()

        menu = gap.box()
        my_text = "BINDING".center(40)
        menu.label(text= my_text, icon='LINKED')
        menu.operator(operators.ConstrainToArmature.bl_idname)
        menu.operator(operators.UnbindArmature.bl_idname)
        menu.operator(operators.ConstraintStatus.bl_idname)
        menu.operator(operators.SelectConstrainedControls.bl_idname)
        menu.operator(operators.AlignBone.bl_idname)

        
        gap = pie.column()
        gap.separator()
        gap.separator()
        gap.separator()
        gap.separator()

        menu = gap.box()
        my_text = "CONVERSION".center(40)
        menu.label(text= my_text, icon='BONE_DATA')
        menu.operator(operators.ConvertGameFriendly.bl_idname)
        menu.operator(operators.ConvertBoneNaming.bl_idname)
        menu.operator(operators.ExtractMetarig.bl_idname)
        menu.operator(operators.ApplyAsRestPose.bl_idname)
        menu.operator(operators.CreateTransformOffset.bl_idname)
        menu.operator(operators.MergeHeadTails.bl_idname)

        gap = pie.column()

        menu = gap.box()
        my_text = "ANIMATION".center(40)
        menu.label(text= my_text, icon='OUTLINER_DATA_ARMATURE')
        menu.operator(operators.ActionRangeToScene.bl_idname)
        menu.operator(operators.AdjustAnimation.bl_idname)
        menu.operator(operators.BakeConstrainedActions.bl_idname)
        menu.operator(operators.AddRoot.bl_idname)
        menu.operator(operators.AddRootMotion.bl_idname)

#---------

class AddPresetArmatureRetarget(AddPresetBase, Operator):
    """Add a Bone Retarget Preset"""
    bl_idname = "object.retarget_armature_preset_add"
    bl_label = "Retarget Preset (select a armature)"
    preset_menu = "VIEW3D_MT_retarget_presets"

    # variable used for all preset values
    preset_defines = [
        "skeleton = bpy.context.object.data.retarget_retarget"
    ]

    # properties to store in the preset
    preset_values = [
        "skeleton.face",

        "skeleton.spine",
        "skeleton.right_arm",
        "skeleton.left_arm",
        "skeleton.right_leg",
        "skeleton.left_leg",

        "skeleton.left_fingers",
        "skeleton.right_fingers",

        "skeleton.right_arm_ik",
        "skeleton.left_arm_ik",

        "skeleton.right_leg_ik",
        "skeleton.left_leg_ik",

        "skeleton.deform_preset",
        "skeleton.root",
    ]

    preset_subdir = preset_handler.PRESETS_SUBDIR

class GuessRetarget(Operator):
    bl_idname = "object.retarget_guess"
    bl_label = "Guess Settings"
    bl_options = {'REGISTER', 'UNDO'}

    starwith:StringProperty(name = "Start With", description="Bone Name Start With This Value", options = {'SKIP_SAVE'},
                            default="")
    
    dontstarwith:StringProperty(name = "Don't Start With", description="Bone Name Don't Start With This Value (separate with a comma)", options = {'SKIP_SAVE'},
                            default="")
    
    dontcontain:StringProperty(name = "Don't contain", description="Bone Name Don't contain This Value  (separate with a comma)", options = {'SKIP_SAVE'},
                            default="")

    @classmethod
    def poll(cls, context):
        if not context.object:
            return False
        if context.object.type != 'ARMATURE':
            return False

        return True
    
    def execute(self, context):

        current_m = context.mode
        bpy.ops.object.mode_set(mode='POSE')

        armatures = context.selected_objects

        if self.dontstarwith:
            donts = self.dontstarwith.split(",")
        else:
            donts = []

        lowercase_list = [s.lower() for s in donts if s]

        if self.dontcontain:
            dontc = self.dontcontain.split(",")
        else:
            dontc = []

        dontcontain_list = [s.lower() for s in dontc if s]

        startwith = self.starwith.lower()

        

        for ob in armatures:

            if ob.type != 'ARMATURE':
                continue

            context.view_layer.objects.active = ob

            preset_handler.guess(ob.data, startwith, lowercase_list, dontcontain_list)

        bpy.ops.object.mode_set(mode= current_m)
        return {'FINISHED'}


class ClearArmatureRetarget(Operator):
    bl_idname = "object.retarget_armature_clear"
    bl_label = "Clear Retarget Settings"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if not context.object:
            return False
        if context.object.type != 'ARMATURE':
            return False

        return True

    def execute(self, context):

        armatures = context.selected_objects
        for ob in armatures:

            if ob.type != 'ARMATURE':
                continue

            skeleton = ob.data.retarget_retarget
            for setting in (skeleton.right_arm, skeleton.left_arm, skeleton.spine, skeleton.right_leg,
                            skeleton.left_leg, skeleton.right_arm_ik, skeleton.left_arm_ik,
                            skeleton.right_leg_ik, skeleton.left_leg_ik,
                            skeleton.face,
                            ):
                for k in setting.keys():
                    if k == 'name':
                        continue
                    try:
                        setattr(setting, k, '')
                    except TypeError:
                        continue

            for settings in (skeleton.right_fingers, skeleton.left_fingers):
                for setting in [getattr(settings, k) for k in settings.keys() if k != 'name']:

                    try:
                        for k in setting.keys():
                            if k == 'name':
                                continue
                            setattr(setting, k, '')
                    except AttributeError:
                        continue

            skeleton.root = ''
            skeleton.deform_preset = '--'

        return {'FINISHED'}


class SetToActiveBone(Operator):
    """Set adjacent UI entry to active bone"""
    bl_idname = "object.retarget_set_to_active_bone"
    bl_label = "Set Retarget value to active bone"

    attr_name: StringProperty(default="", options={'SKIP_SAVE'})
    sub_attr_name: StringProperty(default="", options={'SKIP_SAVE'})
    slot_name: StringProperty(default="", options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        if context.mode  == 'EDIT_ARMATURE':
            return False
        return True

    def execute(self, context):
        current_m = context.mode
        bpy.ops.object.mode_set(mode='POSE')
        if not self.attr_name or not  context.active_pose_bone:
            bpy.ops.object.mode_set(mode= current_m)
            return {'FINISHED'}

        skeleton = context.object.data.retarget_retarget

        if not self.slot_name:
            if self.attr_name == 'root':
                setattr(skeleton, 'root', context.active_pose_bone.name)

            bpy.ops.object.mode_set(mode= current_m)
            return {'FINISHED'}

        try:
            rig_grp = getattr(skeleton, self.attr_name)
        except AttributeError:
            # TODO: warning
            bpy.ops.object.mode_set(mode= current_m)
            return {'FINISHED'}
        else:
            if self.sub_attr_name:
                rig_grp = getattr(rig_grp, self.sub_attr_name)
                
            setattr(rig_grp, self.slot_name, context.active_pose_bone.name)

        
        bpy.ops.object.mode_set(mode= current_m)
        return {'FINISHED'}


class MirrorSettings(Operator):
    """Mirror Settings to the other side"""
    bl_idname = "object.retarget_settings_mirror"
    bl_label = "Mirror Skeleton Mapping"
    bl_options = {'REGISTER', 'UNDO'}

    src_setting: StringProperty(default="", options={'SKIP_SAVE'})
    trg_setting: StringProperty(default="", options={'SKIP_SAVE'})

    use_name: BoolProperty(name="Use Name",
                                description= "Use the Name of the bone to quickly find other bone",
                                default= True)
    
    use_tolerance: BoolProperty(name="Use Tolerance",
                                default= False)

    tolerance: FloatProperty(default=0.0001)

    @classmethod
    def poll(cls, context):
        if not context.object:
            return False
        if context.object.type != 'ARMATURE':
            return False
        if not context.object.data.retarget_retarget:
            return False

        return True

    def _is_mirrored_vec(self, trg_head, src_head):
        epsilon = self.tolerance
        # if abs(trg_head.x + src_head.x) > epsilon:
        #     return False
        if abs(trg_head.y - src_head.y) > epsilon:
            return False
        return abs(trg_head.z - src_head.z) <= epsilon
    
    def _is_mirrored(self, src_bone, trg_bone):
        if not self._is_mirrored_vec(src_bone.head_local, trg_bone.head_local):
            return False
        if not self._is_mirrored_vec(src_bone.tail_local, trg_bone.tail_local):
            return False
        
        return True

    def find_mirrored(self, arm_data, bone):
        # TODO: should be in bone_utils
        # DONE: should select best among mirror candidates

        lookup_name = bone_utils.lrl_strip(bone)
        return next((b for b in arm_data.bones if (
                            bone != b
                            and (self.use_name and lookup_name == bone_utils.lrl_strip(b) or not self.use_name)
                            and (self.use_tolerance and self._is_mirrored(bone, b) or not self.use_tolerance)
                        )
                    ), None)

    def execute(self, context):
        current_m = context.mode
        bpy.ops.object.mode_set(mode='POSE')

        if not self.src_setting:
            bpy.ops.object.mode_set(mode= current_m)
            return {'FINISHED'}
        if not self.trg_setting:
            bpy.ops.object.mode_set(mode= current_m)
            return {'FINISHED'}

        skeleton = context.object.data.retarget_retarget

        try:
            src_grp = getattr(skeleton, self.src_setting)
        except AttributeError:
            # TODO: warning
            bpy.ops.object.mode_set(mode= current_m)
            return {'FINISHED'}
        
        try:
            trg_grp = getattr(skeleton, self.trg_setting)
        except AttributeError:
            # TODO: warning
            bpy.ops.object.mode_set(mode= current_m)
            return {'FINISHED'}

        arm_data = context.object.data
        if 'fingers' in self.trg_setting:
            for finger_name in ('thumb', 'index', 'middle', 'ring', 'pinky'):
                for attr_name in ('a', 'b', 'c'):
                    bone_name = getattr(getattr(src_grp, finger_name), attr_name)
                    if not bone_name:
                        m_bone = None
                    else:
                        m_bone = self.find_mirrored(arm_data,
                                                    arm_data.bones[bone_name])
                    if  m_bone:
                        setattr(getattr(trg_grp, finger_name), attr_name, m_bone.name)
                    # else:
                    #     setattr(getattr(trg_grp, finger_name), attr_name, "")

            bpy.ops.object.mode_set(mode= current_m)
            return {'FINISHED'}

        for k, v in src_grp.items():

            if k == "name":
                continue

            if not v:
                bone = None
            else:
                try:
                    bone = arm_data.bones[v]
                except KeyError:
                    bone = None

            if bone:
                m_bone = self.find_mirrored(arm_data, bone)
            else:
                m_bone = None

            if m_bone:
                setattr(trg_grp, k, m_bone.name)
            # else:
            #     setattr(trg_grp, k, "")

        bpy.ops.object.mode_set(mode= current_m)
        return {'FINISHED'}


class SetPresetArmatureRetarget(Operator):
    """Apply a Bone Retarget Preset"""
    bl_idname = "object.expy_kit_armature_preset_apply"
    bl_label = "Apply Bone Retarget Preset"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: StringProperty(
        subtype='FILE_PATH',
        options={'SKIP_SAVE'},
    )
    menu_idname: StringProperty(
        name="Menu ID Name",
        description="ID name of the menu this was called from",
        options={'SKIP_SAVE'},
    )

    def execute(self, context):

        if not context.active_object:
            return {'FINISHED'}

        if context.object.type != 'ARMATURE':
            return {'FINISHED'}
        
        from os.path import basename, splitext
        filepath = self.filepath

        # change the menu title to the most recently chosen option
        preset_class = VIEW3D_MT_retarget_presets
        preset_class.bl_label = bpy.path.display_name(basename(filepath), title_case=False)

        ext = splitext(filepath)[1].lower()

        if ext not in {".py", ".xml"}:
            self.report({'ERROR'}, "Unknown file type: %r" % ext)
            return {'CANCELLED'}
        
        armatures = context.selected_objects
        for src_object in armatures:

            if src_object.type != 'ARMATURE':
                continue
            context.view_layer.objects.active = src_object

            if hasattr(preset_class, "reset_cb"):
                preset_class.reset_cb(context)

            if ext == ".py":
                try:
                    bpy.utils.execfile(filepath)
                except Exception as ex:
                    self.report({'ERROR'}, "Failed to set the preset: " + repr(ex))

            elif ext == ".xml":
                import rna_xml
                rna_xml.xml_file_run(context,
                                    filepath,
                                    preset_class.preset_xml_map)

            if hasattr(preset_class, "post_cb"):
                preset_class.post_cb(context)

            preset_handler.validate_preset(context.object.data)

            settings = context.object.data.retarget_retarget
            preset_handler.reset_preset_names(settings)

        return {'FINISHED'}
    
class VIEW3D_MT_retarget_presets(Menu):
    bl_label = "Retarget Presets"
    preset_subdir = AddPresetArmatureRetarget.preset_subdir
    #preset_operator = "script.execute_preset"
    preset_operator = SetPresetArmatureRetarget.bl_idname

    draw = Menu.draw_preset


class BindFromPanelSelection(Operator):
    """Constrain to armature selected in panel"""
    bl_idname = "object.retarget_bind_from_panel"
    bl_label = "Bind Armatures"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode != 'EDIT_ARMATURE' and context.scene.retarget_bind_to and context.object != context.scene.retarget_bind_to and context.object.type == 'ARMATURE'
    
    def execute(self, context: Context):

        current_m = context.mode

        for ob in context.selected_objects:
            if not ob.hide_viewport:
                ob.select_set(ob == context.object)
       
        if not context.scene.retarget_bind_to.hide_viewport and context.scene.retarget_bind_to.name in context.view_layer.objects:
            context.scene.retarget_bind_to.select_set(True)

        if len(context.selected_objects) < 2:
            self.report({'WARNING'}, "A object is hidden")
            return {'FINISHED'}
        
        context.view_layer.objects.active = context.scene.retarget_bind_to

        if context.scene.retarget_bind_to.animation_data and context.scene.retarget_bind_to.animation_data.action:
            # TODO: this should be in the constrain operator
            bpy.ops.object.retarget_action_to_range()

        bpy.ops.object.mode_set(mode= current_m)
        
        bpy.ops.armature.retarget_constrain_to_armature('INVOKE_DEFAULT', force_dialog=True)

        return {'FINISHED'}


class VIEW3D_PT_BindPanel(Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Retarget"
    bl_label = "Bind To"

    @classmethod
    def poll(cls, context):
        return context.mode  != 'EDIT_ARMATURE'

    def draw(self, context):
        layout = self.layout
        layout.prop(context.scene, 'retarget_bind_to', text="")

        layout.operator(BindFromPanelSelection.bl_idname)


class RetargetBasePanel:
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Retarget"

    @classmethod
    def poll(cls, context):
        return context.mode != 'EDIT_ARMATURE'

    def sided_rows(self, ob, limbs, bone_names, suffix=""):
        split = self.layout.split()

        labels = None
        side = 'right'
        for group in limbs:
            attr_tokens = [side, group.name]
            attr_suffix = suffix.strip(' ').lower()
            if attr_suffix:
                attr_tokens.append(attr_suffix)

            attr_name = '_'.join(attr_tokens)
            
            col = split.column()
            row = col.row()
            if not labels:
                row.label(text=side.title())
                labels = split.column()
                row = labels.row()

                mirror_props = row.operator(MirrorSettings.bl_idname, text="<--")
                mirror_props.trg_setting = attr_name

                mirror_props_2 = row.operator(MirrorSettings.bl_idname, text="-->")
                mirror_props_2.src_setting = attr_name
                side = 'left'
            else:
                mirror_props.src_setting = attr_name
                mirror_props_2.trg_setting = attr_name
                row.label(text=side.title())

            for k in bone_names:
                bsplit = col.split(factor=0.85)
                bsplit.prop_search(group, k, ob.data, "bones", text="")

                props = bsplit.operator(SetToActiveBone.bl_idname, text="<-")
                props.attr_name = attr_name
                props.slot_name = k

        for k in bone_names:
            row = labels.row()
            row.label(text=(k + suffix).title())


class VIEW3D_PT_retarget_retarget(RetargetBasePanel, Panel):
    bl_label = "Retarget Mapping"

    def draw(self, context):
        layout = self.layout

        split = layout.split(factor=0.75)
        split.menu(VIEW3D_MT_retarget_presets.__name__, text=VIEW3D_MT_retarget_presets.bl_label)
        row = split.row(align=True)
        row.operator(AddPresetArmatureRetarget.bl_idname, text="+")
        row.operator(AddPresetArmatureRetarget.bl_idname, text="-").remove_active = True

class VIEW3D_PT_retarget_retarget_face(RetargetBasePanel, Panel):
    bl_label = "Face"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        ob = context.object
        layout = self.layout

        if not context.active_object or ob.type != 'ARMATURE':
            return
        
        skeleton = ob.data.retarget_retarget

        bsplit = layout.split(factor=0.85)
        bsplit.prop_search(skeleton.face, "jaw", ob.data, "bones", text="Jaw")
        props = bsplit.operator(SetToActiveBone.bl_idname, text="<-")
        props.attr_name = 'face'
        props.slot_name = 'jaw'

        split = layout.split()
        col = split.column()
        col.label(text="Right")

        bsplit = col.split(factor=0.85)
        col = bsplit.column()
        col.prop_search(skeleton.face, "right_eye", ob.data, "bones", text="")
        col.prop_search(skeleton.face, "right_upLid", ob.data, "bones", text="")

        col = bsplit.column()
        eye_props = col.operator(SetToActiveBone.bl_idname, text="<-")
        eye_props.attr_name = 'face'
        eye_props.slot_name = 'right_eye'

        eye_props = col.operator(SetToActiveBone.bl_idname, text="<-")
        eye_props.attr_name = 'face'
        eye_props.slot_name = 'right_upLid'

        col = split.column()
        col.label(text="")
        col.label(text="Eye")
        col.label(text="Up Lid")

        col = split.column()
        col.label(text="Left")

        bsplit = col.split(factor=0.85)
        col = bsplit.column()
        col.prop_search(skeleton.face, "left_eye", ob.data, "bones", text="")
        col.prop_search(skeleton.face, "left_upLid", ob.data, "bones", text="")

        col = bsplit.column()
        eye_props = col.operator(SetToActiveBone.bl_idname, text="<-")
        eye_props.attr_name = 'face'
        eye_props.slot_name = 'left_eye'

        eye_props = col.operator(SetToActiveBone.bl_idname, text="<-")
        eye_props.attr_name = 'face'
        eye_props.slot_name = 'left_upLid'

        row = layout.row()
        row.prop(skeleton.face, "super_copy", text="As Rigify Super Copy")


class VIEW3D_PT_retarget_retarget_fingers(RetargetBasePanel, Panel):
    bl_label = "Fingers"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        ob = context.object
        layout = self.layout

        if not context.active_object or ob.type != 'ARMATURE':
            return
        
        skeleton = ob.data.retarget_retarget
        
        sides = "right", "left"
        split = layout.split()
        finger_bones = ('a', 'b', 'c')
        fingers = ('thumb', 'index', 'middle', 'ring', 'pinky')
        m_props = []
        for side, group in zip(sides, [skeleton.right_fingers, skeleton.left_fingers]):
            col = split.column()
            m_props.append(col.operator(MirrorSettings.bl_idname, text="<--" if side == 'right' else "-->"))

            for k in fingers:
                if k == 'name':  # skip Property Group name
                    continue
                row = col.row()
                row.label(text=" ".join((side, k)).title())
                finger = getattr(group, k)
                for slot in finger_bones:
                    bsplit = col.split(factor=0.85)
                    bsplit.prop_search(finger, slot, ob.data, "bones", text="")
                    
                    f_props = bsplit.operator(SetToActiveBone.bl_idname, text="<-")
                    f_props.attr_name = '_'.join([side, group.name])
                    f_props.sub_attr_name = k
                    f_props.slot_name = slot

        m_props[0].trg_setting = "right_fingers"
        m_props[0].src_setting = "left_fingers"

        m_props[1].trg_setting = "left_fingers"
        m_props[1].src_setting = "right_fingers"


class VIEW3D_PT_retarget_retarget_arms_IK(RetargetBasePanel, Panel):
    bl_label = "Arms IK"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        ob = context.object
        layout = self.layout

        try:

            skeleton = ob.data.retarget_retarget
            arm_bones = ('arm', 'hand')
            #arm_bones = ('shoulder', 'arm', 'forearm', 'hand')

            self.sided_rows(ob, (skeleton.right_arm_ik, skeleton.left_arm_ik), arm_bones, suffix=" IK")
        except AttributeError:
            pass

class VIEW3D_PT_retarget_retarget_arms(RetargetBasePanel, Panel):
    bl_label = "Arms"

    def draw(self, context):
        ob = context.object
        layout = self.layout

        try:

            skeleton = ob.data.retarget_retarget

            row = layout.row()
            row.prop(ob.data, "retarget_twist_on", text="Display Twist Bones")
            
            if ob.data.retarget_twist_on:
                arm_bones = ('shoulder', 'arm', 'arm_twist', 'arm_twist_02', 'forearm', 'forearm_twist', 'forearm_twist_02', 'hand')
            else:
                arm_bones = ('shoulder', 'arm', 'forearm', 'hand')

            self.sided_rows(ob, (skeleton.right_arm, skeleton.left_arm), arm_bones)
        except AttributeError:
            pass

class VIEW3D_PT_retarget_retarget_spine(RetargetBasePanel, Panel):
    bl_label = "Spine"

    def draw(self, context):
        ob = context.object
        layout = self.layout

        try:

            skeleton = ob.data.retarget_retarget

            for slot in ('head', 'neck', 'spine2', 'spine1', 'spine', 'hips'):
                split = layout.split(factor=0.85)
                split.prop_search(skeleton.spine, slot, ob.data, "bones", text="Chest" if slot == 'spine2' else slot.title())
                props = split.operator(SetToActiveBone.bl_idname, text="<-")
                props.attr_name = 'spine'
                props.slot_name = slot
        except AttributeError:
            pass

class VIEW3D_PT_retarget_retarget_leg_IK(RetargetBasePanel, Panel):
    bl_label = "Legs IK"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        ob = context.object
        
        try:

            skeleton = ob.data.retarget_retarget
            
            leg_bones = ('upleg', 'foot', 'toe', 'foot_spin', 'foot_heel')
            #leg_bones = ('upleg', 'leg', 'foot', 'toe', 'foot_spin', 'foot_heel')
            self.sided_rows(ob, (skeleton.right_leg_ik, skeleton.left_leg_ik), leg_bones, suffix=" IK")
        except AttributeError:
            pass

class VIEW3D_PT_retarget_retarget_leg(RetargetBasePanel, Panel):
    bl_label = "Legs"

    def draw(self, context):
        ob = context.object

        try:

            skeleton = ob.data.retarget_retarget

            row = self.layout.row(align=True)
            row.prop(ob.data, "retarget_twist_on", text="Display Twist Bones")

            if ob.data.retarget_twist_on:
                leg_bones = ('upleg', 'upleg_twist', 'upleg_twist_02', 'leg', 'leg_twist', 'leg_twist_02', 'foot', 'toe')
            else:
                leg_bones = ('upleg', 'leg', 'foot', 'toe')

            self.sided_rows(ob, (skeleton.right_leg, skeleton.left_leg), leg_bones)
        except AttributeError:
            pass

class VIEW3D_PT_retarget_retarget_root(RetargetBasePanel, Panel):
    bl_label = "Root"

    def draw(self, context):
        ob = context.object
        layout = self.layout

        try:

            skeleton = ob.data.retarget_retarget

            split = layout.split(factor=0.85)
            split.prop_search(skeleton, 'root', ob.data, "bones", text="Root")
            s_props = split.operator(SetToActiveBone.bl_idname, text="<-")
            s_props.attr_name = 'root'
            s_props.sub_attr_name = ''

            layout.separator()
            row = layout.row()
            row.prop(skeleton, 'deform_preset')

            row = layout.row()
            row.operator(GuessRetarget.bl_idname, text="Guess Settings", icon='SHADERFX')

            row = layout.row()
            row.operator(ClearArmatureRetarget.bl_idname, text="Clear All", icon='PANEL_CLOSE')

        except AttributeError:
            pass

def poll_armature_bind_to(self, object):
    return object != bpy.context.object and object.type == 'ARMATURE' 


classes = (
     GuessRetarget,
	 ClearArmatureRetarget,
	 VIEW3D_MT_retarget_presets,
     SetPresetArmatureRetarget,
	 AddPresetArmatureRetarget,
	 SetToActiveBone,
	 MirrorSettings,
	 BindingsMenu,
	 ConvertMenu,
	 AnimMenu,
	 BindFromPanelSelection,
	 VIEW3D_PT_BindPanel,
	 VIEW3D_PT_retarget_retarget,
	 VIEW3D_PT_retarget_retarget_face,
	 VIEW3D_PT_retarget_retarget_fingers,
	 VIEW3D_PT_retarget_retarget_arms_IK,
	 VIEW3D_PT_retarget_retarget_arms,
	 VIEW3D_PT_retarget_retarget_spine,
	 VIEW3D_PT_retarget_retarget_leg_IK,
	 VIEW3D_PT_retarget_retarget_leg,
	 VIEW3D_PT_retarget_retarget_root,

     VIEW3D_MT_PIE_Retarget,
)


def register_classes():
    bpy.types.Scene.retarget_bind_to = bpy.props.PointerProperty(type=bpy.types.Object,
                                                                name="Bind To",
                                                                poll=poll_armature_bind_to,
                                                                description="This armature will drive another one.")
                                                         
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.VIEW3D_MT_pose_context_menu.append(pose_context_options)
    bpy.types.VIEW3D_MT_object_context_menu.append(pose_context_options)
    bpy.types.VIEW3D_MT_armature_context_menu.append(armature_context_options)
    bpy.types.DOPESHEET_HT_header.append(action_header_buttons)
    bpy.types.GRAPH_HT_header.append(action_header_buttons)


def unregister_classes():
    
    bpy.types.VIEW3D_MT_pose_context_menu.remove(pose_context_options)
    bpy.types.VIEW3D_MT_object_context_menu.remove(pose_context_options)
    bpy.types.VIEW3D_MT_armature_context_menu.remove(armature_context_options)
    bpy.types.DOPESHEET_HT_header.remove(action_header_buttons)
    bpy.types.GRAPH_HT_header.remove(action_header_buttons)
    
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.retarget_bind_to

