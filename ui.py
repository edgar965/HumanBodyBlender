# SPDX-License-Identifier: GPL-3.0-or-later
#
# Daz3D-style N-Panel UI for HumanBody addon.
# Tree-view for body parts, Daz-style sliders.

from .klassenanmeldung import Klassenanmeldung
import bpy
from .ui_teile.zustand import Anzeigezustand

# Die Bauteile liegen in `ui_teile/`. Hier bleiben die Panel-Klassen
# und die Anmeldung — das, was Blender sieht.
from .ui_teile.panelbau import Panelbau, Panelbereich
from .ui_teile.zonen import Zonen
from .ui_teile.auswahl import (
    HUMANBODY_OT_toggle_category, HUMANBODY_OT_select_category,
    HUMANBODY_OT_nudge_prop, HUMANBODY_OT_select_wardrobe_cat,
    HUMANBODY_OT_select_anim_cat,
)
from .ui_teile.teilewahl import HUMANBODY_OT_pick_part
from .ui_teile.zeichnen_koerper import Koerperseite
from .ui_teile.zeichnen_garderobe import Garderobenseite
from .ui_teile.zeichnen_stoff import Stoffseite
from .ui_teile.zeichnen_stoffbau import Stoffbauseite
from .ui_teile.zeichnen_assetbau import Assetbauseite
from .ui_teile.zeichnen_teile import Teileseite
from .ui_teile.zeichnen_weitere import Weitereseite


# ---------------------------------------------------------------------------
# Die Panels
# ---------------------------------------------------------------------------

#: Die Abschnitte der Oberflaeche, in der Reihenfolge, in der sie
#: erscheinen. Der ERSTE ist das Hauptpanel; alle weiteren haengen
#: darunter. Warum erzeugt statt geschrieben: siehe `ui_teile/panelbau.py`.
BEREICHE = [
    Panelbereich('main', 'HumanBody 0.30', Koerperseite._draw_main_body, eltern=None),
    Panelbereich('body_type', 'Body Type', Koerperseite._draw_body_type),
    Panelbereich('materials', 'Materials', Koerperseite._draw_materials_body),
    Panelbereich('parts', 'Parts', Teileseite.zeichnen),
    Panelbereich('favorites', 'Currently Used', Koerperseite._draw_favorites_body),
    Panelbereich('wardrobe', 'Wardrobe', Garderobenseite._draw_wardrobe_body),
    Panelbereich('asset_creator', 'Asset Creator',
                 Assetbauseite.zeichnen, eltern='wardrobe'),
    Panelbereich('geo_assets', 'Geometric Assets',
                 Garderobenseite._draw_geo_assets_body, eltern='wardrobe'),
    Panelbereich('cloth_builder', 'Cloth Builder',
                 Stoffbauseite.zeichnen, eltern='wardrobe'),
    Panelbereich('cloth_primitive', 'Cloth - Primitive',
                 Stoffseite._draw_cloth_primitive_body, eltern='wardrobe'),
    Panelbereich('cloth_template', 'Cloth - from Template',
                 Stoffseite._draw_cloth_template_body, eltern='wardrobe'),
    Panelbereich('hair', 'Hair / Brows / Lashes', Weitereseite._draw_hair_body),
    Panelbereich('rig', 'Rig', Weitereseite._draw_rig_body),
    Panelbereich('pose', 'Pose', Weitereseite._draw_pose_body),
    Panelbereich('animation', 'Animation', Weitereseite._draw_animation_body),
    Panelbereich('randomize', 'Randomize', Weitereseite._draw_randomize_body),
    Panelbereich('finalize', 'Finalize', Weitereseite._draw_finalize_body),
    Panelbereich('file_io', 'File I/O', Weitereseite._draw_file_io_body),
]

#: Beide Saetze — N-Leiste und Eigenschaften-Editor — aus derselben
#: Liste. Vorher standen sie zweimal da und wichen in einem Punkt
#: voneinander ab, ohne dass das jemandem auffiel.
PANELS = [k for ort in Panelbau.ORTE
          for k in Panelbau(ort, BEREICHE, Koerperseite._poll_humanbody).erzeugen()]

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
    Klassenanmeldung.an(classes)

    # Install depsgraph handler for live L2 morph updates
    Anzeigezustand.beobachter = Zonen._on_depsgraph_update
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
    if bpy.app.timers.is_registered(Zonen._deferred_mesh_update):
        bpy.app.timers.unregister(Zonen._deferred_mesh_update)

    Klassenanmeldung.ab(classes)
