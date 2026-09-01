# SPDX-License-Identifier: GPL-3.0-or-later
#
# Cloth Builder for HumanBody addon.
# Adapts patterns from Bystedt's Cloth Builder for integrated cloth simulation.

import logging

import bpy

# Die Bauteile liegen in `cloth/`. Hier bleibt, was Blender
# sieht: die Klassen und die Anmeldung.
from .cloth.eigenschaften import (
    HumanBodyClothBuilderProps, HumanBodyClothPrimitiveProps,
    HumanBodyClothTemplateProps,
)
from .cloth.erzeugoperatoren import (
    HUMANBODY_OT_cloth_prim_create, HUMANBODY_OT_cloth_tpl_create,
)
from .cloth.operatoren import (
    HUMANBODY_OT_cloth_add, HUMANBODY_OT_cloth_add_pin,
    HUMANBODY_OT_cloth_apply_base, HUMANBODY_OT_cloth_clear_pins,
    HUMANBODY_OT_cloth_fit_to_body, HUMANBODY_OT_cloth_paint_weight,
    HUMANBODY_OT_cloth_rebuild, HUMANBODY_OT_cloth_remove,
    HUMANBODY_OT_cloth_remove_garment, HUMANBODY_OT_cloth_remove_pin,
    HUMANBODY_OT_cloth_reset_sim, HUMANBODY_OT_cloth_run_sim,
    HUMANBODY_OT_cloth_shake, HUMANBODY_OT_cloth_stop_sim,
)


# Die Bauteile liegen in `cloth/` — siehe den Kopf dort. Hier bleiben
# nur die Eigenschaften, die Operatoren und die Anmeldung: das, was
# Blender sieht.

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Garment auto-creation from body region
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Body-measurement helpers (for Primitive / Template cloth)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Primitive creation functions
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Template creation functions (measured radii per ring, high density)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Primitive / Template PropertyGroups
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Primitive / Template Operators
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# PropertyGroup
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Poll / find helpers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = (
    HumanBodyClothBuilderProps,
    HumanBodyClothPrimitiveProps,
    HumanBodyClothTemplateProps,
    HUMANBODY_OT_cloth_prim_create,
    HUMANBODY_OT_cloth_tpl_create,
    HUMANBODY_OT_cloth_add,
    HUMANBODY_OT_cloth_remove,
    HUMANBODY_OT_cloth_rebuild,
    HUMANBODY_OT_cloth_remove_garment,
    HUMANBODY_OT_cloth_run_sim,
    HUMANBODY_OT_cloth_stop_sim,
    HUMANBODY_OT_cloth_reset_sim,
    HUMANBODY_OT_cloth_add_pin,
    HUMANBODY_OT_cloth_remove_pin,
    HUMANBODY_OT_cloth_clear_pins,
    HUMANBODY_OT_cloth_fit_to_body,
    HUMANBODY_OT_cloth_apply_base,
    HUMANBODY_OT_cloth_shake,
    HUMANBODY_OT_cloth_paint_weight,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.humanbody_cloth_builder = bpy.props.PointerProperty(
        type=HumanBodyClothBuilderProps)
    bpy.types.Scene.humanbody_cloth_primitive = bpy.props.PointerProperty(
        type=HumanBodyClothPrimitiveProps)
    bpy.types.Scene.humanbody_cloth_template = bpy.props.PointerProperty(
        type=HumanBodyClothTemplateProps)


def unregister():
    del bpy.types.Scene.humanbody_cloth_template
    del bpy.types.Scene.humanbody_cloth_primitive
    del bpy.types.Scene.humanbody_cloth_builder
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
