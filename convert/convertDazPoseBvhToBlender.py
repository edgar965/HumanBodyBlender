"""Convert Daz/Poser BVH motion capture to Blender Rigify animation.

Provides:
  - retarget_bvh(context, rig, bvh_path) — load and retarget a BVH file
  - BONE_MAP — Daz/CMU bone name -> Rigify FK bone name
  - rename_bones_in_bvh() — rename bones inside BVH files

Uses the Diffeomorphic retarget_bvh module (convert/retarget_bvh/) for
T-pose alignment and frame-by-frame retargeting.

Usage from morphing.py:
    from .convert.convertDazPoseBvhToBlender import retarget_bvh
    act, f_start, f_end = retarget_bvh(context, rig, bvh_path)
"""

import os
import re
import shutil
import sys

# ---------------------------------------------------------------------------
# Daz/Poser BVH bone name  ->  Blender Rigify FK bone name
# ---------------------------------------------------------------------------

BONE_MAP = {
    # Spine chain
    "hip":       "torso",
    "abdomen":   "spine_fk.001",
    "chest":     "spine_fk.003",
    "neck":      "neck",
    "head":      "head",

    # Left arm
    "lCollar":   "shoulder.L",
    "lShldr":    "upper_arm_fk.L",
    "lForeArm":  "forearm_fk.L",
    "lHand":     "hand_fk.L",

    # Right arm
    "rCollar":   "shoulder.R",
    "rShldr":    "upper_arm_fk.R",
    "rForeArm":  "forearm_fk.R",
    "rHand":     "hand_fk.R",

    # Left leg
    "lThigh":    "thigh_fk.L",
    "lShin":     "shin_fk.L",
    "lFoot":     "foot_fk.L",

    # Right leg
    "rThigh":    "thigh_fk.R",
    "rShin":     "shin_fk.R",
    "rFoot":     "foot_fk.R",

    # Left hand fingers
    "lThumb1":   "thumb.01.L",
    "lThumb2":   "thumb.02.L",
    "lIndex1":   "f_index.01.L",
    "lIndex2":   "f_index.02.L",
    "lMid1":     "f_middle.01.L",
    "lMid2":     "f_middle.02.L",
    "lRing1":    "f_ring.01.L",
    "lRing2":    "f_ring.02.L",
    "lPinky1":   "f_pinky.01.L",
    "lPinky2":   "f_pinky.02.L",

    # Right hand fingers
    "rThumb1":   "thumb.01.R",
    "rThumb2":   "thumb.02.R",
    "rIndex1":   "f_index.01.R",
    "rIndex2":   "f_index.02.R",
    "rMid1":     "f_middle.01.R",
    "rMid2":     "f_middle.02.R",
    "rRing1":    "f_ring.01.R",
    "rRing2":    "f_ring.02.R",
    "rPinky1":   "f_pinky.01.R",
    "rPinky2":   "f_pinky.02.R",
}

# Bones present in Daz BVH but NOT mapped to Rigify (ignored during retargeting)
UNMAPPED_BONES = [
    "lButtock", "rButtock",       # no Rigify equivalent
    "abdomen2",                    # intermediate spine (Rigify uses spine_fk.002)
    "chest2",                      # intermediate spine
    "lToe", "rToe",               # toe bones (toe.L / toe.R exist but rarely used)
    "figureHair",                  # hair bone
]


def print_mapping():
    """Print the bone name mapping table."""
    print("Daz/Poser BVH  ->  Blender Rigify FK")
    print("=" * 50)
    for daz, rigify in sorted(BONE_MAP.items()):
        print(f"  {daz:16s} -> {rigify}")
    print(f"\nTotal: {len(BONE_MAP)} mapped bones")
    print(f"\nUnmapped (skipped): {', '.join(UNMAPPED_BONES)}")


def rename_bones_in_bvh(filepath, backup_dir=None):
    """Rename Daz/Poser bone names to Rigify names inside a BVH file.

    Only renames in the HIERARCHY section (JOINT/ROOT lines).
    Returns (original_count, renamed_count).
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Backup
    if backup_dir:
        os.makedirs(backup_dir, exist_ok=True)
        shutil.copy2(filepath, os.path.join(backup_dir, os.path.basename(filepath)))

    original_count = 0
    renamed_count = 0

    def replace_bone(match):
        nonlocal original_count, renamed_count
        keyword = match.group(1)  # ROOT or JOINT
        name = match.group(2)
        original_count += 1
        if name in BONE_MAP:
            renamed_count += 1
            return f"{keyword} {BONE_MAP[name]}"
        return match.group(0)

    # Replace ROOT <name> and JOINT <name> lines
    content = re.sub(r"(ROOT|JOINT)\s+(\S+)", replace_bone, content)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return original_count, renamed_count


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--rename":
        if len(sys.argv) < 3:
            print("Usage: convertDazPoseBvhToBlender.py --rename <directory>")
            sys.exit(1)
        bvh_dir = sys.argv[2]
        if not os.path.isdir(bvh_dir):
            print(f"ERROR: Not a directory: {bvh_dir}")
            sys.exit(1)

        backup_dir = os.path.join(bvh_dir, "backup_daz")
        bvh_files = []
        for root, dirs, files in os.walk(bvh_dir):
            if "backup" in root:
                continue
            for f in files:
                if f.endswith(".bvh"):
                    bvh_files.append(os.path.join(root, f))

        print(f"Renaming bones in {len(bvh_files)} BVH files...")
        print(f"Backups: {backup_dir}")
        for fp in sorted(bvh_files):
            orig, renamed = rename_bones_in_bvh(fp, backup_dir)
            name = os.path.basename(fp)
            print(f"  {name:45s} {orig} bones, {renamed} renamed")
        print("Done!")
    else:
        print_mapping()


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------------------
# BVH Retargeting (requires Blender + retarget_bvh module)
# ---------------------------------------------------------------------------

# Maximum frames to retarget (prevents UI freeze on long animations)
MAX_RETARGET_FRAMES = 500

# Bones to exclude (MCH parent mismatch in Rigify causes twist)
_SKIP_BONES = {"head"}

_retarget_ready = False


def _init_retarget():
    """Register retarget_bvh module on first use."""
    global _retarget_ready
    if _retarget_ready:
        return

    import bpy

    convert_dir = os.path.dirname(os.path.abspath(__file__))
    if convert_dir not in sys.path:
        sys.path.insert(0, convert_dir)

    if not hasattr(bpy.types.PoseBone, 'bvh_retargeter'):
        import retarget_bvh
        retarget_bvh.register()

    from retarget_bvh.bsettings import BD
    if BD.prefs is None:
        class _Prefs:
            verbose = False
            useLimits = False
            useUnlock = False
            ignoreLeafBones = False
            useBlenderBvh = False
            useNativeFbx = False
        BD.prefs = _Prefs()

    _retarget_ready = True


def retarget_bvh(context, rig, bvh_path):
    """Load a Daz3D/CMU BVH file and retarget onto a Rigify rig.

    Args:
        context: Blender context
        rig: Target Rigify armature object
        bvh_path: Path to .bvh file

    Returns:
        (action, frame_start, frame_end)
    """
    import bpy
    _init_retarget()

    from retarget_bvh.bsettings import BD, mcpRna as mcp
    from retarget_bvh.utils import (
        setActiveObject, setInterpolation, setCurrentFrame,
        getTrgBone, getRnaFcurves,
    )
    from retarget_bvh.load import (
        BvhLoader, activateObject, renameBones, deleteSourceRig,
    )
    from retarget_bvh.source import (
        findSourceArmature, normalizeSourceRig, setSourceArmature,
    )
    from retarget_bvh.target import findTargetArmature
    from retarget_bvh.retarget import (
        CAnimation, changeTargetData, restoreTargetData,
    )
    from retarget_bvh.t_pose import setRigToFK, putInTPose
    from retarget_bvh.loop import getActiveFrames, centerAnimation

    scn = context.scene
    BD.ensureInited(scn)
    activateObject(context, rig)

    # --- Load BVH ---
    class _Loader(BvhLoader):
        scale = 1.0
        ssFactor = 1
        useDefaultSS = True
        useDeleteFbx = True
        def getOrientation(self):
            return '-Z', 'Y'
        def getStartEndFrame(self):
            return -9999, 9999

    srcRig = _Loader().readMocapFile(context, bvh_path)

    try:
        scn.frame_current = 0
        setActiveObject(context, srcRig)

        # Force Rigify 3 — auto-detection may fail on Blender 5.0
        mcp(scn).TargetRig = "Rigify 3"
        mcp(scn).TargetTPose = "Default"

        activateObject(context, rig)
        findTargetArmature(context, rig, False)

        activateObject(context, srcRig)
        findSourceArmature(context, srcRig, True)

        renameBones(srcRig, context)
        normalizeSourceRig(srcRig)
        putInTPose(context, srcRig, mcp(scn).SourceTPose)
        setInterpolation(srcRig)

        # Rescale source to match target proportions
        trgThigh = getTrgBone("thigh.L", rig, force=True)
        trgShin = getTrgBone("shin.L", rig)
        srcThigh = getTrgBone("thigh.L", srcRig, force=True)
        srcShin = getTrgBone("shin.L", srcRig)
        if trgThigh and trgShin and srcThigh and srcShin:
            trgLen = (trgThigh.head - trgShin.head).length
            srcLen = (srcThigh.head - srcShin.head).length
            if srcLen > 1e-4:
                scale = trgLen / srcLen
                print(f"[BVH retarget] Rescaling by {scale:.4f}")
                setActiveObject(context, srcRig)
                bpy.ops.object.mode_set(mode='EDIT')
                for eb in srcRig.data.edit_bones:
                    eb.use_connect = False
                for eb in srcRig.data.edit_bones:
                    eb.head *= scale
                    eb.tail *= scale
                bpy.ops.object.mode_set(mode='OBJECT')
                for fcu in getRnaFcurves(srcRig):
                    if fcu.data_path.split('.')[-1] == 'location':
                        for kp in fcu.keyframe_points:
                            kp.co[1] *= scale
        mcp(srcRig).Renamed = True

        # --- Retarget ---
        frames = getActiveFrames(srcRig, -9999, 9999)
        if not frames:
            raise RuntimeError("No animation frames in BVH file")

        if len(frames) > MAX_RETARGET_FRAMES:
            step = len(frames) // MAX_RETARGET_FRAMES + 1
            frames = frames[::step]
            print(f"[BVH retarget] Subsampled to {len(frames)} frames (step {step})")

        activateObject(context, rig)
        if rig.animation_data:
            rig.animation_data.action = None
        setRigToFK(rig)
        setCurrentFrame(scn, frames[0])

        oldData = changeTargetData(rig, scn)
        setSourceArmature(srcRig, scn)
        mcp(scn).TargetRig = "Rigify 3"
        mcp(scn).TargetTPose = "Default"
        info = findTargetArmature(context, rig, False)
        anim = CAnimation(srcRig, rig, info, context)

        for bone_name in _SKIP_BONES:
            anim.boneAnims.pop(bone_name, None)

        anim.putInTPoses(context)

        try:
            nFrames = len(frames)
            idx = 0
            while idx < nFrames:
                block = frames[idx:idx + 100]
                anim.retarget(block, context, idx, nFrames)
                idx += 100
            setCurrentFrame(scn, frames[0])
        finally:
            restoreTargetData(oldData)

        act = rig.animation_data.action
        centerAnimation(context, rig, act)
        setInterpolation(rig)

        f_start = int(min(frames))
        f_end = int(max(frames))

    finally:
        deleteSourceRig(context, srcRig, 'Y_')

    return act, f_start, f_end
