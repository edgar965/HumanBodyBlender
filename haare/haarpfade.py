# -*- coding: utf-8 -*-
import os
import logging
import numpy
from ..pfade import Projektpfade

logger = logging.getLogger(__name__)


class Haarpfade:
    u"""Die frueheren Modulfunktionen, gebuendelt."""

    @staticmethod
    def _get_hairstyles_dir():
        """Return path to hairstyles data directory."""
        from ..morphing import MorphData
        return os.path.join(MorphData._addon_data_dir(), "hairstyles")

    @staticmethod
    def _get_hair_blend_path():
        """Get path to the HumanBody particle hair .blend asset."""
        return os.path.join(str(Projektpfade.tools()), "HumanBodyAssets",
                            "characters", "mb_female", "hair.blend")

    @staticmethod
    def _get_mesh_hair_blend_path():
        """Get path to the mesh hair .blend asset."""
        # Die Wurzel kommt aus `pfade.py`: Eine eigene `dirname`-Kette zeigte
        # hier eine Ebene zu tief, seit die Datei im Paket `haare/` liegt.
        local = str(Projektpfade.assets() / "Other" / "mesh_hair01.blend")
        if os.path.isfile(local):
            return local
        return os.path.join(str(Projektpfade.tools()), "HumanBodyAssets",
                            "characters", "mb_female", "assets", "mesh_hair01.blend")

    @staticmethod
    def _list_hairstyles():
        """List available hair assets (blend-based)."""
        assets = []
        if os.path.isfile(Haarpfade._get_hair_blend_path()):
            assets.append(("blend:particle", "Particle Hair"))
        if os.path.isfile(Haarpfade._get_mesh_hair_blend_path()):
            assets.append(("blend:mesh", "Mesh Hair"))
        # Scan hairstyles directory for additional .blend files
        hs_dir = Haarpfade._get_hairstyles_dir()
        if os.path.isdir(hs_dir):
            for fname in sorted(os.listdir(hs_dir)):
                if fname.endswith(".blend"):
                    name = fname[:-6]
                    label = name.replace("_", " ").title()
                    assets.append((f"blend:custom:{name}", label))
        return assets

    @staticmethod
    def _ensure_hair_vg(obj):
        """Ensure hair vertex group exists on the character. Load from _hair_vg.npz if needed."""
        vg = obj.vertex_groups.get("hair_scalp")
        if vg:
            return vg

        npz_path = os.path.join(Haarpfade._get_hairstyles_dir(), "_hair_vg.npz")
        if not os.path.isfile(npz_path):
            return None

        z = numpy.load(npz_path)
        indices = z["indices"]
        weights = z["weights"]

        vg = obj.vertex_groups.new(name="hair_scalp")
        for idx, w in zip(indices, weights):
            vg.add([int(idx)], float(w), 'REPLACE')
        return vg
