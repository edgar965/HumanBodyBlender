
import os
import shutil

import bpy
from humanbody_core.skeleton.mapping import HumanFingers, HumanSpine, HumanLeg, HumanArm, SimpleFace
from humanbody_core.skeleton.skeleton import Skeleton
from humanbody_core.skeleton.presets import PresetSkeleton, PresetFinger, get_preset_from_file as _core_get_preset_from_file

PRESETS_SUBDIR = os.path.join("retarget", "humanoid")

def get_retarget_dir():
    
    presets_dir = os.path.join("presets", PRESETS_SUBDIR)
    retarget_dir = bpy.utils.user_resource('SCRIPTS', path= presets_dir, create=True)
    
    return retarget_dir


def install_presets():
    retarget_dir = get_retarget_dir()

    extensions_path = os.path.join(os.path.dirname(__file__))

    bundled_dir = os.path.join(extensions_path, "rig_mapping", "presets")

    for f in os.listdir(bundled_dir):
        shutil.copy2(os.path.join(bundled_dir, f), retarget_dir)


def iterate_presets_with_current(scene, context):
    """CallBack for Enum Property. Must take scene, context arguments"""

    yield '--', "--", "None"  # first menu entry, doesn't do anything
    yield "--Current--", "-- Current Settings --", "Use Bones set in Retarget Retarget Panel"

    for f in os.listdir(get_retarget_dir()):
        if not f.endswith('.py'):
            continue
        yield f, os.path.splitext(f)[0].title(), ""


def iterate_presets(scene, context):
    """CallBack for Enum Property. Must take scene, context arguments"""

    yield '--', "--", "None"  # first menu entry, doesn't do anything

    for f in os.listdir(get_retarget_dir()):
        if not f.endswith('.py'):
            continue
        yield f, os.path.splitext(f)[0].title(), ""


def get_settings_skel(settings):
    mapping = Skeleton(preset=settings)
    return mapping

def guessBone(name, attrlist, ik, l, r, number, bones, starwith, dontstarwith, dontcontain, used):

    if name != "":
        v = name
        if ":" in name:
            v = name.split(":")[-1]

        for bone in bones:
            if v.lower() in bone.name.lower():
                return bone.name
           
    for attr in attrlist:
        if 'eye' in attr.lower():
            attr = 'eye'
        
       
        for bone in bones:

            #used
            if bone.name in used:
                continue

            #start with
            if starwith and not bone.name.lower().startswith(starwith):
                continue
            
            #dont start with
            cont = True
            for d in dontstarwith:
                if d and bone.name.lower().startswith(d):
                    cont = False
                    break

            if not cont:
                continue
            
            #dont contain
            for d in dontcontain:
                if d and d in bone.name.lower():
                    cont = False
                    break

            if not cont:
                continue

            #------

            if attr.lower() in bone.name.lower() and ((ik and "ik" in bone.name.lower() and attr.lower()) or (not ik)):

                #handle twist bone
                if ("twist" in bone.name.lower() or "tweak" in bone.name.lower()) and (not "twist" in attr.lower() and not "tweak" in attr.lower()):
                    continue

                if r:
                    if not "right" in bone.name.lower():
                        if not "rgt" in bone.name.lower():
                            if not "_r" in bone.name.lower() or "_ring" in bone.name.lower()  or "_roll" in bone.name.lower() :
                                if not ".r" in bone.name.lower():
                                    continue
                if l:
                    if not "left" in bone.name.lower():
                        if not "lft" in bone.name.lower():
                            if not "_l" in bone.name.lower():
                                if not ".l" in bone.name.lower():
                                    continue
                #finger
                if number != "0":
                    if not number in bone.name.lower():
                        continue

                used.append(bone.name)
                
                return bone.name
        
    return ""

def guess(armature_data, starwith, dontstarwith, dontcontain,separator=':'):
    settings = armature_data.retarget_retarget

    if not armature_data.bones:
        return
    
    a_name = armature_data.bones[0].name

    prefix = ""
    if separator in a_name:
        prefix = a_name.rsplit(separator, 1)[0]
        prefix += separator

    used = []

    #root bone
    v = getattr(settings, "root", "")
    with_prefix = prefix + v
    try:
        setattr(settings, "root" , with_prefix if with_prefix in armature_data.bones \
        else guessBone(v, ["c_pos","root","master"], False, False, False, "0", armature_data.bones, starwith, dontstarwith, dontcontain, used))
    except:
        pass
    #---

    for group in ('spine', 'left_arm', 'left_arm_ik', 'right_arm', 'right_arm_ik',
                    'right_leg', 'right_leg_ik', 'left_leg', 'left_leg_ik', 'face'):

        trg_setting = getattr(settings, group)

        for k in sorted(dir(trg_setting)):

            if k.startswith("__") or k in ["bl_rna", "type", "name"]:
                continue

            # coherence

            if (k == "foot_heel" or k == "foot_spin") and not "ik" in group:
                continue
        
            if "twist" in k and "ik" in group:
                continue

            if (k == "forearm" or k == "shoulder") and "ik" in group:
                continue

            if k == "leg" and "ik" in group:
                continue

            #---------

            try:
                v = getattr(trg_setting, k)
                if v not in armature_data.bones:
                    with_prefix = prefix + v
                    l = bool("left" in group)
                    r = bool("right" in group)
                    if group == "face":
                        l = bool("left" in k)
                        r = bool("right" in k)

                    attrlist = []
                    
                    if k == "shoulder":
                        attrlist.append("clavicle")
                    if "twist" in k:
                        attrlist.append(k.replace("twist", "tweak"))
                    if k == "arm":
                        attrlist.append("upper_arm")
                        attrlist.append("upperarm")
                    if k == "forearm":
                        attrlist.append("lower_arm")
                        attrlist.append("lowerarm")
                    if k == "spine2":
                        attrlist.append("spine_03")
                        attrlist.append("spine_fk.003")
                        attrlist.append("upperchest")
                        attrlist.append("chest")
                    if k == "spine1":
                        attrlist.append("spine_02")
                        attrlist.append("spine_fk.002")
                        attrlist.append("chest")
                    if k == "spine":
                        attrlist.append("waist")
                        attrlist.append("spine_01")
                        attrlist.append("spine_fk.001")
                    if k == "hips":
                        attrlist.append("torso")
                        attrlist.append("pelvis")
                        attrlist.append("master")
                        attrlist.append("hip")
                    if k == "upleg":
                        attrlist.append("thigh")
                        attrlist.append("upperleg")
                        attrlist.append(k)
                        attrlist.append("leg")
                    if k == "leg":
                        attrlist.append("lowerleg")
                        attrlist.append("shin")
                        attrlist.append("calf")
                        attrlist.append("leftleg")
                        attrlist.append("rightleg")
                        attrlist.append("_leg")
                        attrlist.append("leg_")
                    if k == "foot_spin":
                        attrlist.append("foot_01")
                        attrlist.append("spin")
                    if k == "foot_heel":
                        attrlist.append("footroll")
                        attrlist.append("Cursor")
                        attrlist.append("heel")

                    attrlist.append(k)

                    ik = bool("ik" in group and k != "foot_spin" and k != "foot_heel")

                    setattr(trg_setting, k, with_prefix if with_prefix in armature_data.bones \
                    else guessBone(v, attrlist, ik, l, r, "0", armature_data.bones, starwith, dontstarwith, dontcontain, used))
            
            except TypeError:
                continue

    #finger_bones = 'meta', 'a', 'b', 'c'
    finger_bones = 'a', 'b', 'c'
    for trg_grp in settings.left_fingers, settings.right_fingers:
        for k, trg_finger in trg_grp.items():
            if k == 'name':  # skip Property Group name
                continue
            i = 1
            for slot in finger_bones:
                bone_name = trg_finger.get(slot)
                if not bone_name or bone_name not in armature_data.bones:
                    if not bone_name:
                        bone_name = ""
                    with_prefix = prefix + bone_name
                    
                    l = bool(trg_grp == settings.left_fingers)
                    r = bool(trg_grp == settings.right_fingers)

                    attrlist = []
                    attrlist.append(k)
                    if k == "pinky":
                        attrlist.append("little")

                    trg_finger[slot] = with_prefix if with_prefix in armature_data.bones \
                        else guessBone(bone_name, attrlist, False, l, r, str(i), armature_data.bones, starwith, dontstarwith, dontcontain, used)
                i += 1


def findBone(name, bones):

    if name != "":

        v = name
        if ":" in name:
            v = name.split(":")[-1]

        for bone in bones:
            if v.lower() in bone.name.lower():
                return bone.name
        
    return ""

def validate_preset(armature_data, separator=':'):
    settings = armature_data.retarget_retarget

    if not armature_data.bones:
        return
    
    a_name = armature_data.bones[0].name

    prefix = ""
    if separator in a_name:
        prefix = a_name.rsplit(separator, 1)[0]
        prefix += separator

    #root bone
    v = getattr(settings, "root", "")
    with_prefix = prefix + v
    try:
        setattr(settings, "root" , with_prefix if with_prefix in armature_data.bones else findBone(v, armature_data.bones))
    except:
        pass
    #---

    for group in ('spine', 'left_arm', 'left_arm_ik', 'right_arm', 'right_arm_ik',
                    'right_leg', 'right_leg_ik', 'left_leg', 'left_leg_ik', 'face'):

        trg_setting = getattr(settings, group)

        for k in sorted(dir(trg_setting)):

            if k.startswith("__") or k in ["bl_rna", "type", "name"]:
                continue
            
            try:
                v = getattr(trg_setting, k)
                if v not in armature_data.bones:
                    with_prefix = prefix + v
                    setattr(trg_setting, k, with_prefix if with_prefix in armature_data.bones else findBone(v, armature_data.bones))
            except TypeError:
                continue

    finger_bones = 'meta', 'a', 'b', 'c'
    for trg_grp in settings.left_fingers, settings.right_fingers:
        for k, trg_finger in trg_grp.items():
            if k == 'name':  # skip Property Group name
                continue
           
            for slot in finger_bones:
                bone_name = trg_finger.get(slot)
                if bone_name and bone_name not in armature_data.bones:
                    with_prefix = prefix + bone_name
                    trg_finger[slot] = with_prefix if with_prefix in armature_data.bones else findBone(bone_name, armature_data.bones)
                

def get_preset_from_file(filename, settings=None):
    """Delegate to humanbody_core implementation."""
    return _core_get_preset_from_file(filename, settings)

    
def set_preset_skel(preset, context, validate=True):
    
    if not preset:
        return
    if not preset.endswith(".py"):
        return

    preset_path = os.path.join(get_retarget_dir(), preset)
    if not os.path.isfile(preset_path):
        return
    
    skeleton = context.active_object.data.retarget_retarget

    get_preset_from_file(preset_path, skeleton)

    if validate:
        validate_preset(skeleton.id_data)

    mapping = get_settings_skel(skeleton)
    return mapping

def get_preset_skel(preset, settings=None, validate=True):
    if not preset:
        return
    if not preset.endswith(".py"):
        return

    preset_path = os.path.join(get_retarget_dir(), preset)
    if not os.path.isfile(preset_path):
        return
    
    defaut_s = get_preset_from_file(preset_path, settings)

    skeleton = settings if settings else defaut_s

    if settings and validate:
        validate_preset(settings.id_data)

    mapping = Skeleton(preset=skeleton)
    del skeleton
    
    return mapping


def reset_preset_names(settings):
    "Reset preset names used by scripts"
    settings.right_arm.name = 'arm'
    settings.left_arm.name = 'arm'

    settings.right_leg.name = 'leg'
    settings.left_leg.name = 'leg'

    settings.right_fingers.name = 'fingers'
    settings.left_fingers.name = 'fingers'


# PresetFinger and PresetSkeleton are now imported from humanbody_core.skeleton.presets (see top)
