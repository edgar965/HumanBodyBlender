# -*- coding: utf-8 -*-
import logging
from humanbody_core.morphing import LazyMorph
logger = logging.getLogger(__name__)
from .daten import MorphData
from .daten import Morphdaten, char_defaults, morph_data


class Morpher:
    """Manages morphing state for one mesh object."""

    _morphers = {}

    @classmethod
    def get(cls, obj):
        """Get or create a Morpher for the given object."""
        key = obj.name
        m = cls._morphers.get(key)
        if m is None or m.obj != obj:
            m = cls(obj)
            cls._morphers[key] = m
        return m

    @classmethod
    def clear(cls, obj):
        """Remove the cached Morpher for the given object."""
        cls._morphers.pop(obj.name, None)

    @staticmethod
    def _is_mass_morph(name):
        """Check if a morph name is a mass-type morph."""
        return "Mass" in name

    @staticmethod
    def _calc_meta_val(coeffs, val):
        """Calculate meta morph contribution with asymmetric coefficients."""
        if not coeffs:
            return 0.0
        return coeffs[1] * val if val > 0 else -coeffs[0] * val

    def __init__(self, obj):
        self.obj = obj
        self.basis = None
        self.morphed = None
        self.body_type = ""
        self.l2_morphs = []
        self.l2_combo = {}
        self._categories = {}
        self._sorted_cats = []
        self._needs_full_reset = True

    def set_body_type(self, body_type):
        """Switch L1 body type."""
        if body_type not in morph_data.l1:
            logger.warning("Unknown body type: %s", body_type)
            return
        self.body_type = body_type
        self.basis = morph_data.l1[body_type].copy()
        self.l2_morphs, self.l2_combo = morph_data.get_l2_for_type(body_type)
        self.morphed = None
        self._needs_full_reset = True
        self._apply_skin_color(body_type)
        self._init_l2_props()
        self._build_category_cache()
        self._pre_resolve_morphs()

    def _init_l2_props(self):
        """Pre-create all L2 custom properties on the mesh."""
        lm = char_defaults.l2_mass
        for morph in self.l2_morphs:
            key = "hb_L2_" + morph.name
            if self._is_mass_morph(morph.name):
                if key not in self.obj.data:
                    self.obj.data[key] = lm.default
                ui = self.obj.data.id_properties_ui(key)
                ui.update(min=lm.min, max=lm.max, soft_min=lm.min, soft_max=lm.max)
            else:
                if key not in self.obj.data:
                    self.obj.data[key] = 0.0
                ui = self.obj.data.id_properties_ui(key)
                ui.update(min=-1.0, max=1.0, soft_min=-1.0, soft_max=1.0)

    def _build_category_cache(self):
        """Pre-group morphs by category for fast UI access."""
        cats = {}
        for morph in self.l2_morphs:
            cat = morph.category
            if cat not in cats:
                cats[cat] = []
            cats[cat].append(morph)
        self._categories = cats
        self._sorted_cats = sorted(cats.keys())

    def _pre_resolve_morphs(self):
        """Eagerly resolve all lazy morphs."""
        for morph in self.l2_morphs:
            if morph.data is None:
                continue
            for i, item in enumerate(morph.data):
                if isinstance(item, LazyMorph):
                    morph._resolve(i)
        for combo in self.l2_combo.values():
            if combo.data is None:
                continue
            for i, item in enumerate(combo.data):
                if isinstance(item, LazyMorph):
                    combo._resolve(i)

    def _apply_skin_color(self, body_type):
        """Update skin, censor, nail, and lip materials for the given body type."""
        r, g, b = MorphData._get_skin_color(body_type)
        mats = self.obj.data.materials

        for i in (0, 1):
            if i < len(mats) and mats[i] and mats[i].node_tree:
                mats[i].diffuse_color = (r, g, b, 1.0)
                for node in mats[i].node_tree.nodes:
                    if node.type == 'BSDF_PRINCIPLED':
                        node.inputs['Base Color'].default_value = (r, g, b, 1.0)

        nr = Morphdaten._nail_color((r, g, b))
        for i in (9, 10):
            if len(mats) > i and mats[i] and mats[i].node_tree:
                mats[i].diffuse_color = (*nr, 1.0)
                for node in mats[i].node_tree.nodes:
                    if node.type == 'BSDF_PRINCIPLED':
                        node.inputs['Base Color'].default_value = (*nr, 1.0)

    @property
    def current_gender(self):
        """Return 'male' or 'female' based on body_type prefix."""
        return "male" if self.body_type.startswith("Male_") else "female"

    def apply_meta_morphs(self):
        """Apply meta morph values (age, mass, tone) to L2 properties."""
        if self.current_gender == "male" and morph_data.morphs_meta_male:
            meta = morph_data.morphs_meta_male
        else:
            meta = morph_data.morphs_meta
        if not meta:
            return

        meta_vals = {}
        for meta_name in meta:
            meta_vals[meta_name] = self.obj.data.get("hb_meta_" + meta_name, 0.0)

        l2_contributions = {}
        for meta_name, meta_data in meta.items():
            val = meta_vals[meta_name]
            if abs(val) < 0.001:
                continue
            morphs_map = meta_data.get("morphs", {})
            for l2_name, coeffs in morphs_map.items():
                contribution = self._calc_meta_val(coeffs, val)
                if l2_name in l2_contributions:
                    l2_contributions[l2_name] += contribution
                else:
                    l2_contributions[l2_name] = contribution

        height_val = self.obj.data.get("hb_meta_height", 0.0)
        if abs(height_val) > 0.001:
            if "Body_Size" in l2_contributions:
                l2_contributions["Body_Size"] += height_val
            else:
                l2_contributions["Body_Size"] = height_val

        for l2_name, value in l2_contributions.items():
            value = max(-1.0, min(1.0, value))
            if self._is_mass_morph(l2_name):
                self.obj.data["hb_L2_" + l2_name] = int(char_defaults.l2_mass.to_display(value))
            else:
                self.obj.data["hb_L2_" + l2_name] = value

    def update(self):
        """Apply all morphs and write to mesh.

        AUFGETEILT (01.09.2026): Die drei Bloecke sind Methoden, die je
        EINMAL gerufen werden. Die inneren Schleifen sind unveraendert —
        sie laufen ueber alle Morphs bei jeder Schieberbewegung, und die
        lokalen Kurznamen (`is_mass`, `lm_to_int`, `obj_data`) sind
        Absicht: Ein Attributzugriff je Morph ist hier messbar.
        """
        if self.basis is None:
            return

        self._ausgangslage()
        obj_data = self.obj.data
        self._l2_anwenden(obj_data)
        self._kombi_anwenden(obj_data)

        # Write to Blender mesh
        self.obj.data.vertices.foreach_set("co", self.morphed.ravel())
        self.obj.data.update()

    # ------------------------------------------------------------ Bausteine

    def _ausgangslage(self):
        u"""`morphed` auf das unverformte Netz zuruecksetzen.

        Der `_needs_full_reset`-Zweig unterscheidet sich nur beim
        allerersten Mal, wenn `morphed` noch gar nicht steht: Dann wird
        kopiert statt zugewiesen. Danach schreibt `[:]` in das
        vorhandene Feld — das spart eine Zuteilung je Aktualisierung.
        """
        if self.morphed is None:
            self.morphed = self.basis.copy()
            self._needs_full_reset = False
            return
        self.morphed[:] = self.basis
        self._needs_full_reset = False

    def _l2_anwenden(self, obj_data):
        u"""Die eindimensionalen L2-Morphs."""
        lm = char_defaults.l2_mass
        is_mass = self._is_mass_morph
        lm_default = lm.default
        lm_to_int = lm.to_internal

        for morph in self.l2_morphs:
            data = morph.data
            if data is None:
                continue
            if is_mass(morph.name):
                val = lm_to_int(obj_data.get("hb_L2_" + morph.name, lm_default))
            else:
                val = obj_data.get("hb_L2_" + morph.name, 0.0)
            if abs(val) < 0.001:
                continue
            morph.apply(self.morphed, val)

    def _kombi_anwenden(self, obj_data):
        u"""Die zweidimensionalen Kombi-Morphs.

        Ein Kombi-Morph hat je Achse mehrere Teilmorphs; welcher wie
        stark wirkt, rechnet `_get_combo_item_value` aus den Achswerten.
        Stehen alle Achsen auf null, wird der ganze Kombi uebersprungen —
        das ist der haeufige Fall.

        `LazyMorph` wird ERST HIER aufgeloest: Die Morphdaten eines
        Kombis liegen als Datei vor und werden nur geladen, wenn sein
        Gewicht ueber der Schwelle liegt.
        """
        lm = char_defaults.l2_mass
        is_mass = self._is_mass_morph
        lm_default = lm.default
        lm_to_int = lm.to_internal
        _get_val = MorphData._get_combo_item_value

        for combo_name, combo in self.l2_combo.items():
            axis_names = MorphData._enum_combo_names(combo_name)
            values = []
            for n in axis_names:
                if is_mass(n):
                    v = lm_to_int(obj_data.get("hb_L2_" + n, lm_default))
                else:
                    v = obj_data.get("hb_L2_" + n, 0.0)
                values.append(v)
            if all(abs(v) < 0.001 for v in values):
                continue
            combo_data = combo.data
            cnt = len(combo_data)
            coeff = 2.0 / cnt
            for i in range(cnt):
                item = combo_data[i]
                if item is None:
                    continue
                weight = _get_val(i, values) * coeff
                if weight < 0.001:
                    continue
                if isinstance(item, LazyMorph):
                    item = combo._resolve(i)
                item.apply(self.morphed, weight)
