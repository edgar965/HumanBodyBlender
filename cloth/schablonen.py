# -*- coding: utf-8 -*-
import logging
import bmesh
logger = logging.getLogger(__name__)
from .netzbau import Netzbau
from .hosennetz import Hosennetz
from .koerpermass import Koerpermass


class Schablonen:
    u"""Die frueheren Modulfunktionen, gebuendelt."""

    @staticmethod
    def _create_tpl_tshirt(context, body, segments, gap, top_ext=0.0, bot_ext=0.0):
        """T-Shirt: single continuous torso tube (neckline→waist).

        Uses body-conforming rings that follow the actual cross-section shape
        instead of perfect circles, so the fit is tight at shoulders/chest.
        """
        neck_z = 1.42 + top_ext
        waist_z = 0.78 - bot_ext

        bm = bmesh.new()
        pin_verts = []

        n_torso = max(10, int((neck_z - waist_z) / 0.012))
        torso_rings = []
        for i in range(n_torso):
            t = i / max(n_torso - 1, 1)
            z = neck_z - t * (neck_z - waist_z)
            ring = Netzbau._bmesh_body_ring(bm, body, z, segments, gap, x_limit=0.20)
            if i == 0:
                pin_verts.extend(ring)
            if torso_rings:
                Netzbau._bridge_rings(bm, torso_rings[-1], ring)
            torso_rings.append(ring)

        obj = Netzbau._finish_primitive(context, bm, "Cloth_Tpl_TShirt", body, pin_verts,
                                color=(0.30, 0.35, 0.50, 1.0))

        # Light corrective smooth (not applied — stays as modifier)
        Netzbau.nachglaetten(obj)
        return obj

    @staticmethod
    def _create_tpl_pants(context, body, segments, gap, top_ext=0.0, bot_ext=0.0):
        """Eine koerpernahe Hose — gemessene Radien je Ring.

        Das Netz baut `Hosennetz`; siehe dort, warum. Diese Schablone
        legt die Ringe fein (0,012) und darf oben und unten verlaengert
        werden.
        """
        bund_z = 0.92 + top_ext
        bm, nadeln = Hosennetz.bauen(
            body, segments, bund_z, 0.08 - bot_ext,
            zugabe=gap, ringschritt=0.012, mindest_bein=8, mindest_huefte=4)
        obj = Netzbau._finish_primitive(context, bm, "Cloth_Tpl_Pants", body,
                                        nadeln, color=(0.15, 0.18, 0.35, 1.0))
        Netzbau.nachglaetten(obj)
        return obj

    @staticmethod
    def _create_tpl_skirt(context, body, segments, gap, top_ext=0.0, bot_ext=0.0):
        """Body-conforming skirt with measured waist + flare."""
        waist_z = 1.00 + top_ext
        knee_z = 0.40 - bot_ext
        flare = 0.4

        cx_w, cy_w, r_waist = Koerpermass._measure_body_at_z(body, waist_z)
        r_top = r_waist + gap

        n_rings = max(10, int((waist_z - knee_z) / 0.012))
        bm = bmesh.new()
        rings = []
        pin_verts = None

        for i in range(n_rings):
            t = i / max(n_rings - 1, 1)
            z = waist_z - t * (waist_z - knee_z)
            r = r_top * (1.0 + flare * t)
            ring = Netzbau._bmesh_ring(bm, cx_w, cy_w, z, r, segments)
            if i == 0:
                pin_verts = list(ring)
            if rings:
                Netzbau._bridge_rings(bm, rings[-1], ring)
            rings.append(ring)

        obj = Netzbau._finish_primitive(context, bm, "Cloth_Tpl_Skirt", body, pin_verts,
                                color=(0.40, 0.20, 0.25, 1.0))

        Netzbau.nachglaetten(obj)
        return obj

    @staticmethod
    def _create_tpl_dress(context, body, segments, gap, top_ext=0.0, bot_ext=0.0):
        """Dress: measured torso tube (shoulder→waist) + flare skirt (waist→knee)."""
        shoulder_z = 1.30 + top_ext
        waist_z = 0.82
        knee_z = 0.40 - bot_ext
        flare = 0.35

        bm = bmesh.new()
        pin_verts = None

        # Torso — body-conforming rings (x_limit excludes arm verts)
        n_torso = max(8, int((shoulder_z - waist_z) / 0.012))
        rings = []
        for i in range(n_torso):
            t = i / max(n_torso - 1, 1)
            z = shoulder_z - t * (shoulder_z - waist_z)
            ring = Netzbau._bmesh_body_ring(bm, body, z, segments, gap, x_limit=0.20)
            if i == 0:
                pin_verts = list(ring)
            if rings:
                Netzbau._bridge_rings(bm, rings[-1], ring)
            rings.append(ring)

        # Skirt — flare cone from waist
        cx_w, cy_w, r_waist = Koerpermass._measure_body_at_z(body, waist_z)
        r_top = r_waist + gap
        n_skirt = max(8, int((waist_z - knee_z) / 0.012))
        for i in range(1, n_skirt + 1):
            t = i / n_skirt
            z = waist_z - t * (waist_z - knee_z)
            r = r_top * (1.0 + flare * t)
            ring = Netzbau._bmesh_ring(bm, cx_w, cy_w, z, r, segments)
            Netzbau._bridge_rings(bm, rings[-1], ring)
            rings.append(ring)

        obj = Netzbau._finish_primitive(context, bm, "Cloth_Tpl_Dress", body, pin_verts,
                                color=(0.45, 0.20, 0.30, 1.0))

        Netzbau.nachglaetten(obj)
        return obj
