# -*- coding: utf-8 -*-
import math
import logging
import bpy
logger = logging.getLogger(__name__)
from .koerpermass import _get_body_wverts
from .namen import CLOTH_GARMENT_TAG


def _add_cloth_material(obj, label, color=(0.25, 0.30, 0.45, 1.0)):
    """Attach a default fabric material to *obj*."""
    mat = bpy.data.materials.new(name=f"hb_cloth_{label}")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs['Base Color'].default_value = color
        bsdf.inputs['Roughness'].default_value = 0.8
        bsdf.inputs['Specular IOR Level'].default_value = 0.2
    mat.diffuse_color = color
    obj.data.materials.append(mat)


def _bmesh_ring(bm, cx, cy, z, radius, segments):
    """Create a ring of vertices in *bm*, return list of BMVerts."""
    verts = []
    for i in range(segments):
        angle = 2.0 * math.pi * i / segments
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        verts.append(bm.verts.new((x, y, z)))
    return verts


def _bmesh_body_ring(bm, body, z, segments, gap, x_limit=None, z_tol=0.03):
    """Create a ring that conforms to the body cross-section at *z*.

    Unlike _bmesh_ring (perfect circle), this measures the body radius at
    each angular direction and places vertices to match the actual shape.
    """
    wverts = _get_body_wverts(body)

    pts = []
    for wx, wy, wz in wverts:
        if abs(wz - z) <= z_tol:
            if x_limit is not None and abs(wx) > x_limit:
                continue
            pts.append((wx, wy))

    if not pts:
        return _bmesh_ring(bm, 0.0, 0.0, z, 0.12 + gap, segments)

    cx = (min(p[0] for p in pts) + max(p[0] for p in pts)) * 0.5
    cy = (min(p[1] for p in pts) + max(p[1] for p in pts)) * 0.5

    # Measure max body radius per angular wedge
    wedge = math.pi / segments * 2.0
    radii = []
    for i in range(segments):
        angle = 2.0 * math.pi * i / segments
        max_r = 0.01
        for px, py in pts:
            dx = px - cx
            dy = py - cy
            r = math.sqrt(dx * dx + dy * dy)
            if r < 0.001:
                continue
            pt_angle = math.atan2(dy, dx)
            da = (pt_angle - angle + math.pi) % (2.0 * math.pi) - math.pi
            if abs(da) <= wedge:
                if r > max_r:
                    max_r = r
        radii.append(max_r)

    # Smooth to avoid jagged edges
    smoothed = list(radii)
    for _ in range(2):
        temp = list(smoothed)
        for i in range(segments):
            prev_r = temp[(i - 1) % segments]
            nxt_r = temp[(i + 1) % segments]
            smoothed[i] = temp[i] * 0.5 + (prev_r + nxt_r) * 0.25

    verts = []
    for i in range(segments):
        angle = 2.0 * math.pi * i / segments
        r = smoothed[i] + gap
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        verts.append(bm.verts.new((x, y, z)))
    return verts


def _bmesh_ring_yz(bm, x, cy, cz, radius, segments):
    """Create a ring in the YZ plane at *x* (for arm sleeves), return BMVerts."""
    verts = []
    for i in range(segments):
        angle = 2.0 * math.pi * i / segments
        y = cy + radius * math.cos(angle)
        z = cz + radius * math.sin(angle)
        verts.append(bm.verts.new((x, y, z)))
    return verts


def _bridge_rings(bm, ring_a, ring_b):
    """Create quad faces between two rings of same length."""
    n = len(ring_a)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new([ring_a[i], ring_a[j], ring_b[j], ring_b[i]])


def _finish_primitive(context, bm, name, body, pin_verts, thickness=0.002,
                      color=(0.25, 0.30, 0.45, 1.0)):
    """Convert bmesh to object, tag, solidify, parent, material. Return obj.

    *pin_verts* can be a list of BMVerts OR a list of integer indices.
    """
    # bm.free() im finally (Review 13.08.2026): Die sechzehn `_create_*`-
    # Funktionen legen den bmesh an und geben ihn NICHT frei — das erledigt
    # bewusst diese Funktion hier. Damit hängt die Freigabe aber daran, dass
    # nichts davor scheitert: `ensure_lookup_table`, die Pin-Indizes,
    # `meshes.new` oder `to_mesh` können werfen, und dann bleibt der bmesh im
    # Speicher liegen. Blender räumt ihn nicht auf; er hält den Platz bis zum
    # Beenden. Ein `finally` kostet nichts und schließt alle diese Wege.
    try:
        bm.verts.ensure_lookup_table()
        if pin_verts and isinstance(pin_verts[0], int):
            pin_indices = list(pin_verts)
        else:
            pin_indices = [v.index for v in pin_verts] if pin_verts else []

        mesh = bpy.data.meshes.new(name)
        bm.to_mesh(mesh)
    finally:
        bm.free()

    obj = bpy.data.objects.new(name, mesh)
    context.collection.objects.link(obj)

    # Tag
    obj.data[CLOTH_GARMENT_TAG] = name
    obj.data['hb_pin_indices'] = pin_indices

    # Smooth shading
    for poly in obj.data.polygons:
        poly.use_smooth = True

    # Solidify
    mod_solid = obj.modifiers.new(name="hb_solidify", type='SOLIDIFY')
    mod_solid.thickness = thickness
    mod_solid.offset = 1.0

    # Parent to body
    obj.parent = body
    obj.matrix_parent_inverse = body.matrix_world.inverted()

    # Material
    _add_cloth_material(obj, name, color)

    return obj
