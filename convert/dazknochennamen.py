# -*- coding: utf-8 -*-
u"""Daz/Poser-Knochennamen auf Rigify — Tabelle und Umbenenner.

Aus `convertDazPoseBvhToBlender.py` herausgeloest (01.09.2026): Die
Datei hatte 356 Zeilen und zwei Haelften, die nichts voneinander
wissen. Hier steht die Namenstabelle und das, was BVH-Dateien auf der
Platte umschreibt — ein Werkzeug fuer die Kommandozeile, ohne Blender.
Drueben bleibt das Retargeting, das `bpy` braucht.

Aufruf::

    python dazknochennamen.py --rename <verzeichnis>
    python dazknochennamen.py            # nur die Tabelle zeigen
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


class Dazknochennamen:
    u"""Die frueheren Modulfunktionen, gebuendelt."""

    @staticmethod
    def print_mapping():
        """Print the bone name mapping table."""
        print("Daz/Poser BVH  ->  Blender Rigify FK")
        print("=" * 50)
        for daz, rigify in sorted(BONE_MAP.items()):
            print(f"  {daz:16s} -> {rigify}")
        print(f"\nTotal: {len(BONE_MAP)} mapped bones")
        print(f"\nUnmapped (skipped): {', '.join(UNMAPPED_BONES)}")

    @staticmethod
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
            orig, renamed = Dazknochennamen.rename_bones_in_bvh(fp, backup_dir)
            name = os.path.basename(fp)
            print(f"  {name:45s} {orig} bones, {renamed} renamed")
        print("Done!")
    else:
        Dazknochennamen.print_mapping()


if __name__ == "__main__":
    main()
