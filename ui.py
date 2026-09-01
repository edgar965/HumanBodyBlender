# SPDX-License-Identifier: GPL-3.0-or-later
#
# Daz3D-style N-Panel UI for HumanBody addon.
# Tree-view for body parts, Daz-style sliders.

import bpy
from .ui_teile.zustand import Anzeigezustand

# Die Bauteile liegen in `ui_teile/`. Hier bleiben die Panel-Klassen
# und die Anmeldung — das, was Blender sieht.
from .ui_teile.panelbau import Panelbau, Panelbereich
from .ui_teile.zonen import _deferred_mesh_update, _on_depsgraph_update
from .ui_teile.auswahl import (
    HUMANBODY_OT_toggle_category, HUMANBODY_OT_select_category,
    HUMANBODY_OT_nudge_prop, HUMANBODY_OT_select_wardrobe_cat,
    HUMANBODY_OT_select_anim_cat,
)
from .ui_teile.teilewahl import HUMANBODY_OT_pick_part
from .ui_teile.zeichnen_koerper import (
    _draw_main_body, _draw_body_type, _draw_parts_body, _draw_favorites_body,
    _poll_humanbody, _draw_materials_body,
)
from .ui_teile.zeichnen_garderobe import (
    _draw_wardrobe_body, _draw_asset_creator_body, _draw_geo_assets_body,
)
from .ui_teile.zeichnen_stoff import (
    _draw_cloth_builder_body, _draw_cloth_primitive_body,
    _draw_cloth_template_body,
)
from .ui_teile.zeichnen_weitere import (
    _draw_hair_body, _draw_rig_body, _draw_pose_body, _draw_animation_body,
    _draw_randomize_body, _draw_finalize_body, _draw_file_io_body,
)


# ---------------------------------------------------------------------------
# Die Panels
# ---------------------------------------------------------------------------

#: Die Abschnitte der Oberflaeche, in der Reihenfolge, in der sie
#: erscheinen. Der ERSTE ist das Hauptpanel; alle weiteren haengen
#: darunter. Warum erzeugt statt geschrieben: siehe `ui_teile/panelbau.py`.
BEREICHE = [
    Panelbereich('main', 'HumanBody 0.30', _draw_main_body, eltern=None),
    Panelbereich('body_type', 'Body Type', _draw_body_type),
    Panelbereich('materials', 'Materials', _draw_materials_body),
    Panelbereich('parts', 'Parts', _draw_parts_body),
    Panelbereich('favorites', 'Currently Used', _draw_favorites_body),
    Panelbereich('wardrobe', 'Wardrobe', _draw_wardrobe_body),
    Panelbereich('asset_creator', 'Asset Creator',
                 _draw_asset_creator_body, eltern='wardrobe'),
    Panelbereich('geo_assets', 'Geometric Assets',
                 _draw_geo_assets_body, eltern='wardrobe'),
    Panelbereich('cloth_builder', 'Cloth Builder',
                 _draw_cloth_builder_body, eltern='wardrobe'),
    Panelbereich('cloth_primitive', 'Cloth - Primitive',
                 _draw_cloth_primitive_body, eltern='wardrobe'),
    Panelbereich('cloth_template', 'Cloth - from Template',
                 _draw_cloth_template_body, eltern='wardrobe'),
    Panelbereich('hair', 'Hair / Brows / Lashes', _draw_hair_body),
    Panelbereich('rig', 'Rig', _draw_rig_body),
    Panelbereich('pose', 'Pose', _draw_pose_body),
    Panelbereich('animation', 'Animation', _draw_animation_body),
    Panelbereich('randomize', 'Randomize', _draw_randomize_body),
    Panelbereich('finalize', 'Finalize', _draw_finalize_body),
    Panelbereich('file_io', 'File I/O', _draw_file_io_body),
]

#: Beide Saetze — N-Leiste und Eigenschaften-Editor — aus derselben
#: Liste. Vorher standen sie zweimal da und wichen in einem Punkt
#: voneinander ab, ohne dass das jemandem auffiel.
PANELS = [k for ort in Panelbau.ORTE
          for k in Panelbau(ort, BEREICHE, _poll_humanbody).erzeugen()]

# Die erzeugten Klassen unter ihrem Namen ins Modul stellen: Blender
# und andere Module suchen sie dort (`ui.HUMANBODY_PT_main`).
for _panel in PANELS:
    globals()[_panel.__name__] = _panel
del _panel


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = (
    HUMANBODY_OT_toggle_category,
    HUMANBODY_OT_select_category,
    HUMANBODY_OT_nudge_prop,
    HUMANBODY_OT_pick_part,
    HUMANBODY_OT_select_wardrobe_cat,
    HUMANBODY_OT_select_anim_cat,
    # Die 36 Panels stehen nicht einzeln hier: Sie entstehen in
    # `ui_teile/panelbau.py` aus BEREICHE, und zwar in genau der
    # Reihenfolge, die Blender braucht (Eltern vor Kind).
) + tuple(PANELS)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    # Install depsgraph handler for live L2 morph updates
    Anzeigezustand.beobachter = _on_depsgraph_update
    bpy.app.handlers.depsgraph_update_post.append(Anzeigezustand.beobachter)


def unregister():
    if Anzeigezustand.beobachter in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(Anzeigezustand.beobachter)
    Anzeigezustand.beobachter = None

    # Den Timer mit abmelden (Review 13.08.2026). Er ist einmalig
    # (`_deferred_mesh_update` gibt auf allen Wegen None zurueck, Blender meldet
    # ihn danach selbst ab) — das Fenster ist also klein: Wird das Addon in den
    # 10 ms nach einer Morph-Aenderung deaktiviert, feuert er noch EINMAL und
    # greift dann auf abgemeldete Klassen zu. Ein Traceback beim Deaktivieren
    # sieht aus wie ein kaputtes Addon; das ist es nicht wert.
    if bpy.app.timers.is_registered(_deferred_mesh_update):
        bpy.app.timers.unregister(_deferred_mesh_update)

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
