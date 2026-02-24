# SPDX-License-Identifier: GPL-3.0-or-later
#
# Wardrobe system for HumanBody addon.
# Discovers, imports, and manages clothing/accessory assets.

import os
import logging

import bpy

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Asset paths
# ---------------------------------------------------------------------------

# Primary: HumanBody core data assets directory
_TOOLS_ROOT = os.path.dirname(os.path.dirname(__file__))
_HUMANBODY_ROOT = os.path.join(_TOOLS_ROOT, "HumanBody")
if not os.path.isdir(_HUMANBODY_ROOT):
    _HUMANBODY_ROOT = r"A:\3DTools\HumanBody"
_ASSETS_DIR = os.path.join(_HUMANBODY_ROOT, "data", "assets")

# Fallback: HumanBodyAssets shared directory
_HUMANBODY_ASSETS_DIR = os.path.join(
    r"A:\3DTools\HumanBodyAssets", "characters", "mb_female", "assets")


def _get_assets_dir():
    """Return the assets directory path."""
    if os.path.isdir(_ASSETS_DIR):
        return _ASSETS_DIR
    if os.path.isdir(_HUMANBODY_ASSETS_DIR):
        return _HUMANBODY_ASSETS_DIR
    return None


# ---------------------------------------------------------------------------
# YAML loader (reuse from morphing)
# ---------------------------------------------------------------------------

def _load_yaml(path):
    """Load a YAML file."""
    if not os.path.isfile(path):
        return None
    try:
        from yaml import safe_load
        with open(path, "r", encoding="utf-8") as f:
            return safe_load(f)
    except ImportError:
        return _parse_config_yaml(path)


def _parse_config_yaml(path):
    """Minimal YAML parser for asset config.yaml files."""
    result = {}
    stack = [result]
    indent_stack = [-1]

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.rstrip()
            if not stripped or stripped.lstrip().startswith("#"):
                continue

            indent = len(line) - len(line.lstrip())
            content = stripped.strip()

            # Pop stack to correct level
            while len(indent_stack) > 1 and indent <= indent_stack[-1]:
                indent_stack.pop()
                stack.pop()

            if content.endswith(":"):
                # New section
                key = content[:-1].strip()
                new_dict = {}
                stack[-1][key] = new_dict
                stack.append(new_dict)
                indent_stack.append(indent)
            elif ":" in content:
                key, val = content.split(":", 1)
                key = key.strip()
                val = val.strip()
                stack[-1][key] = _parse_yaml_value(val)

    return result


def _parse_yaml_value(val):
    """Parse a YAML value string."""
    if not val:
        return ""
    # Strip quotes
    if (val.startswith('"') and val.endswith('"')) or \
       (val.startswith("'") and val.endswith("'")):
        return val[1:-1]
    # Array
    if val.startswith("[") and val.endswith("]"):
        inner = val[1:-1]
        if not inner.strip():
            return []
        parts = [p.strip() for p in inner.split(",")]
        result = []
        for p in parts:
            # Strip quotes from array items
            if (p.startswith('"') and p.endswith('"')) or \
               (p.startswith("'") and p.endswith("'")):
                result.append(p[1:-1])
            else:
                try:
                    result.append(float(p))
                except ValueError:
                    result.append(p)
        return result
    # Boolean
    if val.lower() in ("true", "yes"):
        return True
    if val.lower() in ("false", "no"):
        return False
    # Number
    try:
        return float(val)
    except ValueError:
        return val


# ---------------------------------------------------------------------------
# Asset data class
# ---------------------------------------------------------------------------

# Wardrobe categories for the panel display
WARDROBE_CATEGORIES = [
    ("Tops",        'TRIA_UP'),
    ("Bottoms",     'TRIA_DOWN'),
    ("Skirts",      'MESH_CONE'),
    ("Full",        'USER'),
    ("Underwear",   'MOD_CLOTH'),
    ("Shoes",       'CONSTRAINT_BONE'),
    ("Accessories", 'PROP_CON'),
]

# Auto-categorization by name keywords
_NAME_CAT_MAP = {
    "pants": "Bottoms", "trousers": "Bottoms", "jeans": "Bottoms",
    "btm": "Bottoms", "tights": "Bottoms",
    "skirt": "Skirts", "rock": "Skirts", "minirock": "Skirts",
    "top": "Tops", "shirt": "Tops", "jumper": "Tops", "jacket": "Tops",
    "boots": "Shoes", "shoes": "Shoes",
    "gloves": "Accessories", "hat": "Accessories", "headpiece": "Accessories",
    "dress": "Full", "suit_full": "Full", "dresses": "Full",
    "hair": "Hair",
    "thong": "Underwear", "panties": "Underwear", "bra": "Underwear",
}


def _guess_category(name):
    """Guess asset category from name when config says 'Other'."""
    lower = name.lower()
    for key, cat in _NAME_CAT_MAP.items():
        if key in lower:
            return cat
    return "Other"


class AssetInfo:
    """Metadata for a discovered asset."""
    __slots__ = ("name", "directory", "blend_file", "config",
                 "category", "tags", "label")

    def __init__(self, name, directory):
        self.name = name
        self.directory = directory
        self.blend_file = ""
        self.config = {}
        self.category = "Other"
        self.tags = []
        self.label = name.replace("_", " ").replace(".", " ")

        # Find blend file
        blend = os.path.join(directory, "asset.blend")
        if os.path.isfile(blend):
            self.blend_file = blend
        else:
            # Try name.blend
            blend = os.path.join(directory, name + ".blend")
            if os.path.isfile(blend):
                self.blend_file = blend

        # Load config
        conf_path = os.path.join(directory, "config.yaml")
        conf = _load_yaml(conf_path)
        if conf:
            self.config = conf
            self.category = conf.get("category", "Other")
            if isinstance(self.category, str):
                self.category = self.category.strip('"')
            self.tags = conf.get("tags", [])

        # Normalize category names
        _CAT_NORMALIZE = {"Dresses": "Full"}
        self.category = _CAT_NORMALIZE.get(self.category, self.category)

        # Auto-categorize when config is missing or says "Other"
        if self.category == "Other":
            self.category = _guess_category(name)


# Asset cache
_asset_cache = None


def _scan_dir_for_assets(directory, category_override=None):
    """Scan a single directory for assets, return list of AssetInfo."""
    result = []
    for entry in sorted(os.listdir(directory)):
        full = os.path.join(directory, entry)

        if os.path.isdir(full):
            info = AssetInfo(entry, full)
            if info.blend_file:
                if category_override:
                    info.category = category_override
                result.append(info)
        elif entry.endswith(".blend") and not entry.startswith("."):
            name = entry[:-6]
            info = AssetInfo(name, directory)
            info.blend_file = full
            if category_override:
                info.category = category_override
            result.append(info)
    return result


# Known category directory names
_CATEGORY_DIRS = {"Tops", "Bottoms", "Skirts", "Full", "Underwear", "Shoes",
                  "Accessories", "Other"}


def discover_assets():
    """Scan the assets directory and return list of AssetInfo.

    Supports both flat layout and category-subdirectory layout:
      assets/Tops/jeans.blend   -> category = Tops
      assets/my_asset.blend     -> category guessed from name
    """
    global _asset_cache
    if _asset_cache is not None:
        return _asset_cache

    assets_dir = _get_assets_dir()
    if not assets_dir:
        _asset_cache = []
        return _asset_cache

    result = []
    for entry in sorted(os.listdir(assets_dir)):
        full = os.path.join(assets_dir, entry)

        if os.path.isdir(full) and entry in _CATEGORY_DIRS:
            # Category subdirectory — scan contents with category override
            result.extend(_scan_dir_for_assets(full, category_override=entry))
        elif os.path.isdir(full):
            # Folder-based asset at root level (legacy/flat layout)
            info = AssetInfo(entry, full)
            if info.blend_file:
                result.append(info)
        elif entry.endswith(".blend") and not entry.startswith("."):
            # Standalone .blend file at root level
            name = entry[:-6]
            info = AssetInfo(name, assets_dir)
            info.blend_file = full
            result.append(info)

    _asset_cache = result
    logger.info("Discovered %d wardrobe assets", len(result))
    return result


def invalidate_cache():
    global _asset_cache
    _asset_cache = None


def get_filtered_assets(category="ALL", search=""):
    """Return assets filtered by category and search string."""
    assets = discover_assets()
    result = []
    search_lower = search.lower()
    for a in assets:
        if category != "ALL" and a.category != category:
            continue
        if search_lower:
            if search_lower not in a.name.lower() and \
               not any(search_lower in t.lower() for t in a.tags):
                continue
        result.append(a)
    return result


# ---------------------------------------------------------------------------
# Fitted asset tracking
# ---------------------------------------------------------------------------

def get_fitted_assets(char_obj):
    """Return list of (object, asset_name) for fitted assets on a character."""
    result = []
    for child in char_obj.children:
        if child.type == 'MESH' and child.data.get("hb_wardrobe_asset"):
            result.append((child, child.data["hb_wardrobe_asset"]))
    return result


def find_asset_info(name):
    """Find AssetInfo by name."""
    for a in discover_assets():
        if a.name == name:
            return a
    return None


# ---------------------------------------------------------------------------
# Import / Remove
# ---------------------------------------------------------------------------

def import_asset(context, asset_info, char_obj):
    """Import an asset and attach it to the character."""
    if not asset_info.blend_file:
        return None

    # Import all objects from the blend file
    with bpy.data.libraries.load(asset_info.blend_file, link=False) as (data_from, data_to):
        data_to.objects = data_from.objects[:]

    imported = []
    for obj in data_to.objects:
        if obj is not None:
            context.collection.objects.link(obj)
            imported.append(obj)

    if not imported:
        return None

    # Find the main mesh object
    asset_obj = None
    for obj in imported:
        if obj.type == 'MESH':
            asset_obj = obj
            break
    if asset_obj is None:
        asset_obj = imported[0]

    # Tag as wardrobe asset
    asset_obj.data["hb_wardrobe_asset"] = asset_info.name

    # Parent to character
    asset_obj.parent = char_obj
    asset_obj.matrix_parent_inverse = char_obj.matrix_world.inverted()

    # Add offset modifier (Displace along normals)
    offset_conf = {}
    params = asset_info.config.get("parameters", {})
    if isinstance(params, dict):
        offset_conf = params.get("offset", {})

    mod = asset_obj.modifiers.new(name="hb_offset", type='DISPLACE')
    mod.direction = 'NORMAL'
    mod.mid_level = 0.0
    mod.strength = offset_conf.get("default", 0.001) if isinstance(offset_conf, dict) else 0.001

    # Add corrective smooth
    smooth_conf = {}
    if isinstance(params, dict):
        smooth_conf = params.get("smoothing", {})

    mod_s = asset_obj.modifiers.new(name="hb_smooth", type='CORRECTIVE_SMOOTH')
    mod_s.use_pin_boundary = True
    default_smooth = smooth_conf.get("default", 0.0) if isinstance(smooth_conf, dict) else 0.0
    mod_s.iterations = int(default_smooth * 10)

    # Smooth shading
    for poly in asset_obj.data.polygons:
        poly.use_smooth = True

    # Remove any extra imported objects that aren't the main mesh
    for obj in imported:
        if obj != asset_obj and obj.type != 'ARMATURE':
            bpy.data.objects.remove(obj, do_unlink=True)

    logger.info("Imported wardrobe asset: %s", asset_info.name)
    return asset_obj


def remove_asset(asset_obj):
    """Remove a fitted asset from the scene."""
    name = asset_obj.data.get("hb_wardrobe_asset", asset_obj.name)
    bpy.data.objects.remove(asset_obj, do_unlink=True)
    logger.info("Removed wardrobe asset: %s", name)


# ---------------------------------------------------------------------------
# Material presets
# ---------------------------------------------------------------------------

def get_material_presets(asset_info):
    """Return dict of preset_key -> label from config."""
    presets = asset_info.config.get("material_presets", {})
    if not isinstance(presets, dict):
        return {}
    return {k: v.get("label", k) if isinstance(v, dict) else k
            for k, v in presets.items()}


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
                _apply_bsdf_props(mat, props)
                break

    return True


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


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class HUMANBODY_OT_wardrobe_add(bpy.types.Operator):
    bl_idname = "humanbody.wardrobe_add"
    bl_label = "Add Asset"
    bl_description = "Import and fit a wardrobe asset"
    bl_options = {'REGISTER', 'UNDO'}

    asset_name: bpy.props.StringProperty()

    def execute(self, context):
        char_obj = context.active_object
        if not char_obj or not char_obj.data.get("humanbody"):
            self.report({'ERROR'}, "Select a HumanBody character first")
            return {'CANCELLED'}

        info = find_asset_info(self.asset_name)
        if not info:
            self.report({'ERROR'}, f"Asset not found: {self.asset_name}")
            return {'CANCELLED'}

        # Check if already fitted
        for child, name in get_fitted_assets(char_obj):
            if name == self.asset_name:
                self.report({'WARNING'}, f"Asset already fitted: {info.label}")
                return {'CANCELLED'}

        obj = import_asset(context, info, char_obj)
        if obj is None:
            self.report({'ERROR'}, f"Failed to import: {self.asset_name}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Added: {info.label}")
        return {'FINISHED'}


class HUMANBODY_OT_wardrobe_remove(bpy.types.Operator):
    bl_idname = "humanbody.wardrobe_remove"
    bl_label = "Remove Asset"
    bl_description = "Remove a fitted wardrobe asset"
    bl_options = {'REGISTER', 'UNDO'}

    asset_name: bpy.props.StringProperty()

    def execute(self, context):
        char_obj = context.active_object
        if not char_obj or not char_obj.data.get("humanbody"):
            self.report({'ERROR'}, "Select a HumanBody character first")
            return {'CANCELLED'}

        for child, name in get_fitted_assets(char_obj):
            if name == self.asset_name:
                remove_asset(child)
                self.report({'INFO'}, f"Removed: {self.asset_name}")
                return {'FINISHED'}

        self.report({'WARNING'}, f"Asset not found on character: {self.asset_name}")
        return {'CANCELLED'}


class HUMANBODY_OT_wardrobe_preset(bpy.types.Operator):
    bl_idname = "humanbody.wardrobe_preset"
    bl_label = "Apply Preset"
    bl_description = "Apply a material color preset"

    asset_name: bpy.props.StringProperty()
    preset_key: bpy.props.StringProperty()

    def execute(self, context):
        char_obj = context.active_object
        if not char_obj:
            return {'CANCELLED'}

        info = find_asset_info(self.asset_name)
        if not info:
            return {'CANCELLED'}

        for child, name in get_fitted_assets(char_obj):
            if name == self.asset_name:
                apply_material_preset(child, info, self.preset_key)
                self.report({'INFO'}, f"Preset: {self.preset_key}")
                return {'FINISHED'}

        return {'CANCELLED'}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = (
    HUMANBODY_OT_wardrobe_add,
    HUMANBODY_OT_wardrobe_remove,
    HUMANBODY_OT_wardrobe_preset,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
