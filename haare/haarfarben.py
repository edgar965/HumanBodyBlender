# -*- coding: utf-8 -*-
import logging
logger = logging.getLogger(__name__)


HAIR_COLORS = {
    "Silken Black":       {"melanin": 1.0,   "melanin_redness": 0.3, "viewport": (0.02, 0.02, 0.02)},
    "Dark Brown":         {"melanin": 0.814, "melanin_redness": 0.3, "viewport": (0.08, 0.04, 0.02)},
    "Cocoa Brown":        {"melanin": 0.514, "melanin_redness": 0.3, "viewport": (0.25, 0.12, 0.05)},
    "Light Golden Brown": {"melanin": 0.114, "melanin_redness": 0.3, "viewport": (0.7, 0.5, 0.25)},
    "Honey Blonde":       {"melanin": 0.373, "melanin_redness": 1.0, "viewport": (0.6, 0.26, 0.08)},
    "Light Blonde":       {"melanin": 0.373, "melanin_redness": 1.0, "viewport": (0.6, 0.3, 0.05),
                           "coat": 0.686, "ior": 5.15, "offset": 0.18},
    "Auburn":             {"melanin": 0.5,   "melanin_redness": 0.8, "viewport": (0.5, 0.2, 0.05)},
    "Natural Black":      {"melanin": 1.0,   "melanin_redness": 0.005, "viewport": (0.05, 0.05, 0.05)},
    "Burgundy":           {"melanin": 1.0,   "melanin_redness": 0.005, "viewport": (0.13, 0.085, 0.08),
                           "random_color": 0.568},
    "Plum":               {"melanin": 0.3,   "melanin_redness": 0.3, "viewport": (0.33, 0.17, 0.05)},
}


EYE_COLORS = {
    "Blue":    (0.08, 0.20, 0.65),
    "Green":   (0.10, 0.35, 0.15),
    "Brown":   (0.15, 0.07, 0.03),
    "Hazel":   (0.30, 0.20, 0.07),
    "Gray":    (0.25, 0.25, 0.27),
    "Amber":   (0.45, 0.25, 0.05),
}
