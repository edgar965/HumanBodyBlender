# -*- coding: utf-8 -*-
import logging
import numpy
logger = logging.getLogger(__name__)


class Gewichte:
    u"""Die frueheren Modulfunktionen, gebuendelt."""

    @staticmethod
    def _npz_names(z):
        """Decode null-separated UTF-8 names from NPZ 'names' array."""
        return [n.decode("utf-8") for n in bytes(z["names"]).split(b'\0')]

    @staticmethod
    def _npz_vg_iter(z):
        """Yield (name, idx_array, weights_array) from a HumanBody NPZ file."""
        idx = z["idx"]
        weights = z["weights"]
        i = 0
        for name, cnt in zip(Gewichte._npz_names(z), z["cnt"]):
            i2 = i + int(cnt)
            yield name, idx[i:i2], weights[i:i2]
            i = i2

    @staticmethod
    def _import_weights(obj, npz_path):
        """Create bone vertex groups from a HumanBody weights NPZ file.

        Keeps DEF- prefix on group names — these match Rigify deformation
        bone names (DEF-spine.001) in the rig.
        """
        z = numpy.load(npz_path)
        count = 0
        for name, idx, weights in Gewichte._npz_vg_iter(z):
            if name in obj.vertex_groups:
                obj.vertex_groups.remove(obj.vertex_groups[name])
            vg = obj.vertex_groups.new(name=name)
            for vi, w in zip(idx, weights):
                vg.add([int(vi)], float(w), 'REPLACE')
            count += 1
        return count
