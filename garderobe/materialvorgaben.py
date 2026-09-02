# -*- coding: utf-8 -*-
import logging
logger = logging.getLogger(__name__)


class Materialvorgaben:
    u"""Die frueheren Modulfunktionen, gebuendelt."""

    @staticmethod
    def get_material_presets(asset_info):
        """Return dict of preset_key -> label from config."""
        presets = asset_info.config.get("material_presets", {})
        if not isinstance(presets, dict):
            return {}
        return {k: v.get("label", k) if isinstance(v, dict) else k
                for k, v in presets.items()}

    @staticmethod
    def apply_material_preset(asset_obj, asset_info, preset_key):
        """Apply a material preset to a fitted asset."""
        presets = asset_info.config.get("material_presets", {})
        if preset_key not in presets:
            return False

        preset = presets[preset_key]
        mat_configs = preset.get("materials", {})
        if not isinstance(mat_configs, dict):
            return False

        for mat_name, props in mat_configs.items():
            if not isinstance(props, dict):
                continue
            # Find matching material on the object
            for mat in asset_obj.data.materials:
                if mat is None:
                    continue
                if mat_name.lower() in mat.name.lower() or mat.name.lower() in mat_name.lower():
                    Materialvorgaben._apply_bsdf_props(mat, props)
                    break

        return True

    @staticmethod
    def _apply_bsdf_props(mat, props):
        """Apply properties to a material's Principled BSDF."""
        if not mat.node_tree:
            return

        bsdf = None
        for node in mat.node_tree.nodes:
            if node.type == 'BSDF_PRINCIPLED':
                bsdf = node
                break
        if bsdf is None:
            return

        for key, val in props.items():
            if key == "label":
                continue
            if key == "Base Color":
                if isinstance(val, list):
                    if len(val) == 3:
                        val = val + [1.0]
                    bsdf.inputs['Base Color'].default_value = val
                    mat.diffuse_color = tuple(val)
            elif key in bsdf.inputs:
                inp = bsdf.inputs[key]
                if hasattr(inp, 'default_value'):
                    inp.default_value = val
