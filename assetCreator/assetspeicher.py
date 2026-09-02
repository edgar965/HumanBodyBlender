# -*- coding: utf-8 -*-
import os
import logging
import bpy
from ..assetCreator.vorschau.vorschausuche import Vorschausuche
from ..pfade import Projektpfade
logger = logging.getLogger(__name__)


class Assetspeicher:
    u"""Die frueheren Modulfunktionen, gebuendelt."""

    @staticmethod
    def save_asset(context, props):
        """Save the preview mesh as a wardrobe asset.

        1. Create asset directory: data/assets/{category}/{name}/
        2. Apply modifiers (bake)
        3. Save asset.blend (mesh + material only)
        4. Generate config.yaml
        5. Invalidate wardrobe cache
        6. Remove preview, load via wardrobe
        """
        from ..garderobe.assetsuche import Assetsuche

        preview = Vorschausuche.find_preview(context)
        if not preview:
            return False, "No preview to save"

        body = Vorschausuche.find_body_obj(context)
        if not body:
            return False, "No HumanBody character found"

        # Asset directory (in HumanBody core data)
        asset_dir = os.path.join(str(Projektpfade.assets()),
                                 props.category, props.name_)
        os.makedirs(asset_dir, exist_ok=True)

        Assetspeicher._backen(context, preview, body)
        blend_path = Assetspeicher._blend_schreiben(preview, asset_dir)

        # Generate config.yaml
        Assetspeicher._write_config_yaml(
            os.path.join(asset_dir, "config.yaml"), props)

        # Remove preview object
        bpy.data.objects.remove(preview, do_unlink=True)

        # Invalidate wardrobe cache
        Assetsuche.invalidate_cache()

        logger.info("Saved asset: %s -> %s", props.name_, blend_path)
        return True, blend_path

    @staticmethod
    def _backen(context, preview, body):
        u"""Alle Modifikatoren anwenden und vom Koerper loesen.

        Gespeichert wird das Ergebnis, nicht das Rezept: In der
        Asset-Datei soll ein fertiges Netz liegen, kein Netz mit fuenf
        Modifikatoren, die beim Anziehen erneut rechnen.

        Ein Modifikator, der sich nicht anwenden laesst (deaktiviert,
        oder das Netz hat keine Form dafuer), wird uebergangen und
        protokolliert — sonst gibt es gar kein Asset.
        """
        context.view_layer.objects.active = preview
        for mod in preview.modifiers[:]:
            try:
                bpy.ops.object.modifier_apply(modifier=mod.name)
            except Exception as e:
                logger.warning("Could not apply modifier %s: %s", mod.name, e)

        # Unparent but keep transform
        preview.parent = None
        preview.matrix_world = body.matrix_world.copy()

    @staticmethod
    def _blend_schreiben(preview, asset_dir):
        u"""Netz, Material und Knotenbaum in `asset.blend`.

        Der Knotenbaum muss EINZELN mitgegeben werden: Blender schreibt
        nur, was in `data_blocks` steht, und ein Material ohne seinen
        Knotenbaum kommt in der Zieldatei grau und ohne Textur an.

        `fake_user=True` haelt die Bloecke am Leben — sonst raeumt
        Blender sie beim naechsten Laden weg, weil sie niemand benutzt.
        """
        blend_path = os.path.join(asset_dir, "asset.blend")
        mesh_data = preview.data
        materials = [m for m in mesh_data.materials if m]

        data_blocks = {preview, mesh_data}
        data_blocks.update(materials)
        for mat in materials:
            if mat.node_tree:
                data_blocks.add(mat.node_tree)

        bpy.data.libraries.write(blend_path, data_blocks, fake_user=True)
        return blend_path

    @staticmethod
    def _write_config_yaml(path, props):
        """Write a config.yaml for the saved asset."""
        lines = [
            f'name: "{props.name_}"',
            f'category: "{props.category}"',
            f'tags: []',
            f'parameters:',
            f'  offset:',
        ]

        if props.creation_mode == 'IMAGE':
            lines.append(f'    default: {props.image_offset_max}')
        else:
            lines.append(f'    default: {props.offset}')

        lines += [
            f'    min: -0.01',
            f'    max: 0.05',
            f'  smoothing:',
            f'    default: {props.smoothing}',
            f'material:',
            f'  color: [{props.color[0]:.3f}, {props.color[1]:.3f}, {props.color[2]:.3f}]',
            f'  roughness: {props.roughness}',
            f'  metallic: {props.metallic}',
            f'creation:',
        ]

        if props.creation_mode == 'IMAGE':
            lines += [
                f'  method: "image"',
                f'  image_threshold: {props.image_threshold}',
                f'  image_bg_mode: "{props.image_bg_mode}"',
                f'  image_scale: {props.image_scale}',
                f'  offset_min: {props.image_offset_min}',
                f'  offset_max: {props.image_offset_max}',
                f'  thickness: {props.thickness}',
                f'  grow: {props.grow}',
            ]
        else:
            lines += [
                f'  method: "zrange"',
                f'  z_min: {props.z_min}',
                f'  z_max: {props.z_max}',
                f'  include_arms: {str(props.include_arms).lower()}',
                f'  offset: {props.offset}',
                f'  thickness: {props.thickness}',
                f'  grow: {props.grow}',
            ]

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
