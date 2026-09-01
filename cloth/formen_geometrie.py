# -*- coding: utf-8 -*-
import math
import logging
import bmesh
logger = logging.getLogger(__name__)
from .netzbau import _bmesh_ring
from .netzbau import _bridge_rings
from .netzbau import _finish_primitive
from .koerpermass import _measure_body_at_z


def _create_prim_disc(context, body, segments, radius, z_pos):
    """Flat disc with concentric rings at *z_pos* for good cloth topology."""
    cx, cy, _ = _measure_body_at_z(body, z_pos)
    bm = bmesh.new()

    n_concentric = max(3, int(radius / 0.03))
    center_v = bm.verts.new((cx, cy, z_pos))
    rings = []

    for ri in range(1, n_concentric + 1):
        t = ri / n_concentric
        r = radius * t
        ring = _bmesh_ring(bm, cx, cy, z_pos, r, segments)
        if ri == 1:
            n = len(ring)
            for i in range(n):
                j = (i + 1) % n
                bm.faces.new([center_v, ring[i], ring[j]])
        else:
            _bridge_rings(bm, rings[-1], ring)
        rings.append(ring)

    # Pin: outer ring
    pin_verts = rings[-1] if rings else []
    return _finish_primitive(context, bm, "Cloth_Prim_Disc", body, pin_verts,
                             color=(0.50, 0.45, 0.40, 1.0))


def _create_prim_sphere(context, body, segments, radius, z_pos):
    """UV sphere at body center at *z_pos*."""
    cx, cy, _ = _measure_body_at_z(body, z_pos)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segments,
                               v_segments=max(4, segments // 2),
                               radius=radius)
    for v in bm.verts:
        v.co.x += cx
        v.co.y += cy
        v.co.z += z_pos

    # Pin: top-most ring of vertices
    bm.verts.ensure_lookup_table()
    z_max = max(v.co.z for v in bm.verts)
    pin_verts = [v for v in bm.verts if v.co.z >= z_max - 0.005]

    return _finish_primitive(context, bm, "Cloth_Prim_Sphere", body, pin_verts,
                             color=(0.45, 0.35, 0.30, 1.0))


def _create_prim_oval_disc(context, body, segments, radius, z_pos):
    """Elliptical disc (1.6x wider in X) at *z_pos*."""
    cx, cy, _ = _measure_body_at_z(body, z_pos)
    bm = bmesh.new()

    n_concentric = max(3, int(radius / 0.03))
    center_v = bm.verts.new((cx, cy, z_pos))
    rings = []

    for ri in range(1, n_concentric + 1):
        t = ri / n_concentric
        verts = []
        for i in range(segments):
            angle = 2.0 * math.pi * i / segments
            x = cx + radius * 1.6 * t * math.cos(angle)
            y = cy + radius * t * math.sin(angle)
            verts.append(bm.verts.new((x, y, z_pos)))
        if ri == 1:
            n = len(verts)
            for i in range(n):
                j = (i + 1) % n
                bm.faces.new([center_v, verts[i], verts[j]])
        else:
            _bridge_rings(bm, rings[-1], verts)
        rings.append(verts)

    pin_verts = rings[-1] if rings else []
    return _finish_primitive(context, bm, "Cloth_Prim_OvalDisc", body, pin_verts,
                             color=(0.45, 0.40, 0.35, 1.0))


def _create_prim_triangle(context, body, segments, radius, z_pos):
    """Subdivided equilateral triangle at *z_pos*."""
    cx, cy, _ = _measure_body_at_z(body, z_pos)
    bm = bmesh.new()

    # Three corners of equilateral triangle (point up)
    corners = []
    for i in range(3):
        angle = 2.0 * math.pi * i / 3 - math.pi / 2
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        corners.append(bm.verts.new((x, y, z_pos)))

    bm.faces.new(corners)

    # Subdivide for cloth sim resolution
    cuts = max(2, segments // 4)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=cuts)

    # Pin: the 3 original corner vertices (may have shifted index after subdiv)
    bm.verts.ensure_lookup_table()
    # Find outermost verts as pin
    dists = []
    for v in bm.verts:
        d = math.sqrt((v.co.x - cx) ** 2 + (v.co.y - cy) ** 2)
        dists.append((d, v))
    dists.sort(key=lambda x: -x[0])
    pin_verts = [v for _, v in dists[:3]]

    return _finish_primitive(context, bm, "Cloth_Prim_Triangle", body, pin_verts,
                             color=(0.40, 0.45, 0.35, 1.0))


def _create_prim_puffer(context, body, segments, length, count):
    """Multiple half-sphere domes arranged in rows around the torso.

    *count*: number of rows.  Columns are auto-calculated from circumference.
    """
    shoulder_z = 1.30
    gap = 0.018
    row_height = length / max(count, 1)

    bm = bmesh.new()
    all_pin_verts = []
    dome_rings_n = 4
    dome_segs = max(8, segments // 4)

    for row_idx in range(count):
        z_center = shoulder_z - (row_idx + 0.5) * row_height
        cx_body, cy_body, r_body = _measure_body_at_z(body, z_center)
        r_base = r_body + gap

        circumference = 2.0 * math.pi * r_base
        puff_r = row_height * 0.45
        n_cols = max(4, int(circumference / (puff_r * 2.2)))

        for col_idx in range(n_cols):
            angle = 2.0 * math.pi * col_idx / n_cols
            # Stagger odd rows by half a column
            if row_idx % 2 == 1:
                angle += math.pi / n_cols
            px = cx_body + r_base * math.cos(angle)
            py = cy_body + r_base * math.sin(angle)

            # Build half-sphere dome pointing outward from body center
            dome_dir_x = math.cos(angle)
            dome_dir_y = math.sin(angle)

            dome_rings = []
            for ri in range(dome_rings_n + 1):
                t = ri / dome_rings_n
                phi = t * math.pi * 0.5  # 0 to pi/2
                ring_r = puff_r * math.cos(phi)
                # Dome rises outward from body surface
                rise = puff_r * math.sin(phi)
                rcx = px + dome_dir_x * rise
                rcy = py + dome_dir_y * rise

                if ring_r < 0.002:
                    # Cap vertex
                    cap = bm.verts.new((rcx, rcy, z_center))
                    if dome_rings:
                        prev = dome_rings[-1]
                        np_ = len(prev)
                        for k in range(np_):
                            j = (k + 1) % np_
                            bm.faces.new([prev[k], prev[j], cap])
                    break

                ring = []
                for si in range(dome_segs):
                    a = 2.0 * math.pi * si / dome_segs
                    # Ring perpendicular to dome direction
                    rx = rcx + ring_r * (-dome_dir_y * math.cos(a))
                    ry = rcy + ring_r * (dome_dir_x * math.cos(a))
                    rz = z_center + ring_r * math.sin(a)
                    ring.append(bm.verts.new((rx, ry, rz)))

                if ri == 0 and row_idx == 0:
                    all_pin_verts.extend(ring)

                if dome_rings:
                    _bridge_rings(bm, dome_rings[-1], ring)
                dome_rings.append(ring)

    return _finish_primitive(context, bm, "Cloth_Prim_Puffer", body, all_pin_verts,
                             color=(0.35, 0.30, 0.45, 1.0))
