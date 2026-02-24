# SPDX-License-Identifier: GPL-3.0-or-later
#
# HumanBody data-model class.
# Single clean interface to all morphable properties on a HumanBody mesh.

from .morphing import Morpher, char_defaults


class HumanBody:
    """Wraps a Blender mesh object and exposes all morphable properties.

    Usage:
        body = HumanBody(obj)
        body.body_type = "Female_Caucasian"
        body.gender = 0
        body.age = 25
        body.forearm_length = 0.3
        body.update()
        print(body.to_dict())
    """

    # Core property names (handled via explicit @property)
    _CORE = {"body_type", "gender", "age", "mass", "tone", "height"}

    def __init__(self, obj):
        object.__setattr__(self, "_obj", obj)
        object.__setattr__(self, "_morpher", Morpher.get(obj))

    # ------------------------------------------------------------------
    # Helpers: convert between python snake_case and morph CamelCase
    # ------------------------------------------------------------------

    def _morph_key(self, name):
        """snake_case python name -> 'hb_L2_Category_Property' mesh key."""
        for morph in self._morpher.l2_morphs:
            if self._to_python_name(morph.name) == name:
                return "hb_L2_" + morph.name, morph.name
        return None, None

    @staticmethod
    def _to_python_name(morph_name):
        """'Arms_ForearmLength' -> 'arms_forearm_length', 'Head_Size' -> 'head_size'."""
        import re
        s = re.sub(r'([A-Z])', r'_\1', morph_name).lower().lstrip('_')
        return s.replace('__', '_')

    # ------------------------------------------------------------------
    # Core properties (body_type, gender, age, mass, tone)
    # ------------------------------------------------------------------

    @property
    def obj(self):
        return self._obj

    @property
    def morpher(self):
        return self._morpher

    @property
    def body_type(self):
        return self._morpher.body_type

    @body_type.setter
    def body_type(self, value):
        self._morpher.set_body_type(value)

    @property
    def gender(self):
        """Gender 0-100 (0=female, 100=male)."""
        return int(char_defaults.gender.to_display(
            (self._morpher.gender - 0.5) * 2.0))

    @gender.setter
    def gender(self, value):
        self._morpher.set_gender(
            char_defaults.gender.to_internal(value) / 2.0 + 0.5)

    @property
    def age(self):
        return int(char_defaults.age.to_display(
            self._obj.data.get("hb_meta_age", 0.0)))

    @age.setter
    def age(self, value):
        self._obj.data["hb_meta_age"] = char_defaults.age.to_internal(value)
        self._morpher.apply_meta_morphs()

    @property
    def mass(self):
        return int(char_defaults.mass.to_display(
            self._obj.data.get("hb_meta_mass", 0.0)))

    @mass.setter
    def mass(self, value):
        self._obj.data["hb_meta_mass"] = char_defaults.mass.to_internal(value)
        self._morpher.apply_meta_morphs()

    @property
    def tone(self):
        return int(char_defaults.tone.to_display(
            self._obj.data.get("hb_meta_tone", 0.0)))

    @tone.setter
    def tone(self, value):
        self._obj.data["hb_meta_tone"] = char_defaults.tone.to_internal(value)
        self._morpher.apply_meta_morphs()

    @property
    def height(self):
        return int(char_defaults.height.to_display(
            self._obj.data.get("hb_meta_height", 0.0)))

    @height.setter
    def height(self, value):
        self._obj.data["hb_meta_height"] = char_defaults.height.to_internal(value)
        self._morpher.apply_meta_morphs()

    # ------------------------------------------------------------------
    # Dynamic L2 properties via __getattr__ / __setattr__
    # ------------------------------------------------------------------

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        key, morph_name = self._morph_key(name)
        if key is None:
            raise AttributeError(
                f"HumanBody has no morph property '{name}'")
        if Morpher._is_mass_morph(morph_name):
            return self._obj.data.get(key, char_defaults.l2_mass.default)
        return self._obj.data.get(key, 0.0)

    def __setattr__(self, name, value):
        if name.startswith("_") or name in self._CORE:
            object.__setattr__(self, name, value)
            return
        key, morph_name = self._morph_key(name)
        if key is None:
            raise AttributeError(
                f"HumanBody has no morph property '{name}'")
        self._obj.data[key] = value

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def update(self):
        """Recalculate and apply all morphs to mesh."""
        self._morpher.update()

    def reset(self):
        """Reset all properties to defaults."""
        lm = char_defaults.l2_mass
        for morph in self._morpher.l2_morphs:
            key = "hb_L2_" + morph.name
            if Morpher._is_mass_morph(morph.name):
                self._obj.data[key] = lm.default
            else:
                self._obj.data[key] = 0.0
        self._obj.data["hb_meta_age"] = 0.0
        self._obj.data["hb_meta_mass"] = 0.0
        self._obj.data["hb_meta_tone"] = 0.0
        self._obj.data["hb_meta_height"] = 0.0
        self._morpher.update()

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self):
        """Serialize all current values to a dict."""
        d = {
            "body_type": self.body_type,
            "gender": self.gender,
            "age": self.age,
            "mass": self.mass,
            "tone": self.tone,
            "height": self.height,
        }
        for morph in self._morpher.l2_morphs:
            key = "hb_L2_" + morph.name
            py_name = self._to_python_name(morph.name)
            if Morpher._is_mass_morph(morph.name):
                d[py_name] = self._obj.data.get(key, char_defaults.l2_mass.default)
            else:
                d[py_name] = self._obj.data.get(key, 0.0)
        return d

    def from_dict(self, d):
        """Restore all values from a dict (as produced by to_dict)."""
        if "body_type" in d:
            self.body_type = d["body_type"]
        if "gender" in d:
            self.gender = d["gender"]
        if "age" in d:
            self.age = d["age"]
        if "mass" in d:
            self.mass = d["mass"]
        if "tone" in d:
            self.tone = d["tone"]
        if "height" in d:
            self.height = d["height"]
        for morph in self._morpher.l2_morphs:
            py_name = self._to_python_name(morph.name)
            if py_name in d:
                self._obj.data["hb_L2_" + morph.name] = d[py_name]
        self.update()

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def available_morphs(self):
        """Return list of (python_name, morph_name, category) for all L2 morphs."""
        result = []
        for morph in self._morpher.l2_morphs:
            py = self._to_python_name(morph.name)
            cat = morph.name.split("_", 1)[0]
            result.append((py, morph.name, cat))
        return result

    def __repr__(self):
        return f"HumanBody({self._obj.name!r}, type={self.body_type!r})"
