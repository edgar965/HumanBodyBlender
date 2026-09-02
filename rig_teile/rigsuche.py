# -*- coding: utf-8 -*-
import os
import logging
from ..rig_teile.rigpfade import Rigpfade
logger = logging.getLogger(__name__)


class Rigsuche:
    u"""Die frueheren Modulfunktionen, gebuendelt."""

    @staticmethod
    def _find_rig(obj):
        """Find the armature rig for a HumanBody object."""
        if obj.parent and obj.parent.type == 'ARMATURE':
            return obj.parent
        for mod in obj.modifiers:
            if mod.type == 'ARMATURE' and mod.object:
                return mod.object
        return None

    @staticmethod
    def _list_poses():
        """Return list of (filename_no_ext, label) for available poses."""
        d = Rigpfade._get_poses_dir()
        if not os.path.isdir(d):
            return []
        result = []
        for f in sorted(os.listdir(d)):
            if f.endswith(".json"):
                name = f[:-5]
                label = name.replace("_", " ").title()
                result.append((name, label))
        return result


#: Die frueheren Modulnamen — die Importpfade von
#: aussen bleiben damit unveraendert.
_find_rig = Rigsuche._find_rig
_list_poses = Rigsuche._list_poses
