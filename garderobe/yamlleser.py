# -*- coding: utf-8 -*-
import os
import logging
logger = logging.getLogger(__name__)


class Yamlleser:
    u"""Die frueheren Modulfunktionen, gebuendelt."""

    @staticmethod
    def _load_yaml(path):
        """Load a YAML file."""
        if not os.path.isfile(path):
            return None
        try:
            from yaml import safe_load
            with open(path, "r", encoding="utf-8") as f:
                return safe_load(f)
        # stumm gewollt: Ohne PyYAML greift der eigene Leser darunter. Das ist der
        # Zweck der Weiche, kein Fehlschlag.
        except ImportError:
            return Yamlleser._parse_config_yaml(path)

    @staticmethod
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
                    stack[-1][key] = Yamlleser._parse_yaml_value(val)

        return result

    @staticmethod
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
                    # stumm gewollt: float() wirft bei Text, siehe unten. Ein Log
                    # je Listenelement waere Rauschen.
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
        # stumm gewollt: float() wirft bei Text — genau daran wird Text erkannt.
        # Das IST die Typbestimmung.
        except ValueError:
            return val
