# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Welcher BVH-Knochen auf welchen Rigify-Knochen wirkt — und wie.

Aus `retarget.retarget_rokoko` herausgeloest (01.09.2026): Die Funktion
hatte 232 Zeilen in acht nummerierten Abschnitten. Die Abschnitte 2 und 3
beantworten eine Frage fuer sich — sie ordnen die Knochen ein und haengen
den Armen ihre Zwangsbedingungen an. Sie laufen EINMAL, vor der
Bildschleife, und haengen an keinem Bild.

DREI WEGE FUER DREI KOERPERTEILE
================================
* **Rumpf und Beine** werden Bild fuer Bild konjugiert: `M @ q @ M⁻¹`
  rechnet die Drehung aus dem BVH-Ruhesystem in das des Rigs. `M` haengt
  nur an den Ruhelagen und wird deshalb hier einmal berechnet.
* **Arme und Finger** bekommen `COPY_ROTATION` im Weltraum und werden
  danach mit `nla.bake()` gebacken — das ist der C++-Loeser, um
  Groessenordnungen schneller als eine Python-Schleife.
* **Kopf und Schultern** werden uebersprungen: Ihre Topologie passt
  nicht, und eine erzwungene Zuordnung sieht schlechter aus als die
  Ruhelage.
"""
import logging

logger = logging.getLogger(__name__)


class Knochenplan:
    u"""Was die Bildschleife ueber die Knochen wissen muss.

    Ein Datensatz mit sieben Feldern — als Tupel zurueckgegeben waere an
    jeder Entnahmestelle zu raten, welches Feld an welcher Stelle steht.
    """

    __slots__ = ('conj_pairs', 'tgt_to_src', 'aim_levels', 'hips_src',
                 'hips_rest_world', 'skip_bones', 'constraint_bones')

    def __init__(self, conj_pairs, tgt_to_src, aim_levels, hips_src,
                 hips_rest_world, skip_bones, constraint_bones):
        #: [(BVH-Name, Rig-Name, Konjugationsmatrix)] fuer Rumpf und Beine.
        self.conj_pairs = conj_pairs
        #: {Rig-Name: BVH-Name} — ohne die Schultern.
        self.tgt_to_src = tgt_to_src
        #: Die Beinkette in drei Ebenen, von der Huefte abwaerts.
        self.aim_levels = aim_levels
        #: Der BVH-Knochen, aus dem die Wurzelbewegung kommt.
        self.hips_src = hips_src
        #: Seine Ruhelage in Weltkoordinaten — Bezug fuer den Versatz.
        self.hips_rest_world = hips_rest_world
        #: Knochen, die auf Ruhelage gesetzt werden.
        self.skip_bones = skip_bones
        #: Knochen, die ueber Zwangsbedingungen laufen.
        self.constraint_bones = constraint_bones

    @property
    def bildknochen(self):
        u"""Die Knochen, die je Bild einen Schluessel bekommen.

        Die Arme sind NICHT dabei — ihre Schluessel entstehen im Backen.
        """
        return [t for _, t, _ in self.conj_pairs] + list(self.skip_bones)


class Rokokoknochen:
    u"""Ordnet die Knochen ein und haengt den Armen ihre Zwaenge an."""

    #: Rumpf und Beine — Bild fuer Bild konjugiert.
    KONJUGIERT = {"torso", "spine_fk.001", "spine_fk.002", "spine_fk.003",
                  "neck",
                  "thigh_fk.L", "thigh_fk.R", "shin_fk.L", "shin_fk.R",
                  "foot_fk.L", "foot_fk.R"}

    #: Uebersprungen — Topologie passt nicht, Ruhelage sieht besser aus.
    UEBERSPRUNGEN = {"head", "shoulder.L", "shoulder.R"}

    #: Ueber `COPY_ROTATION` + `nla.bake()`.
    ARME = {"upper_arm_fk.L", "upper_arm_fk.R",
            "forearm_fk.L", "forearm_fk.R",
            "hand_fk.L", "hand_fk.R"}

    #: Die Beinkette von oben nach unten. Die Reihenfolge zaehlt: Jede
    #: Ebene rechnet auf der Stellung der darueberliegenden.
    ZIELEBENEN = [
        ["thigh_fk.L", "thigh_fk.R"],
        ["shin_fk.L", "shin_fk.R"],
        ["foot_fk.L", "foot_fk.R"],
    ]

    @staticmethod
    def einordnen(bvh_rig, rig, bone_map, bvh_mw, rig_mw, fingerziele=()):
        u"""Den `Knochenplan` fuer diese Zuordnung aufstellen."""
        conj_pairs = []
        tgt_to_src = {}
        for src_name, tgt_name in bone_map.items():
            src_bone = bvh_rig.data.bones.get(src_name)
            tgt_bone = rig.data.bones.get(tgt_name)
            if not src_bone or not tgt_bone:
                continue
            if tgt_name not in ("shoulder.L", "shoulder.R"):
                tgt_to_src[tgt_name] = src_name
            if tgt_name in Rokokoknochen.KONJUGIERT:
                src_rest_q = (bvh_mw @ src_bone.matrix_local).to_quaternion()
                tgt_rest_q = (rig_mw @ tgt_bone.matrix_local).to_quaternion()
                conj_pairs.append((src_name, tgt_name,
                                   tgt_rest_q.inverted() @ src_rest_q))

        aim_levels = []
        for namen in Rokokoknochen.ZIELEBENEN:
            ebene = [(tgt_to_src[n], n) for n in namen if n in tgt_to_src]
            if ebene:
                aim_levels.append(ebene)

        hips_src = tgt_to_src.get("torso")
        hips_rest_world = None
        if hips_src:
            hips_bone = bvh_rig.data.bones.get(hips_src)
            if hips_bone:
                hips_rest_world = (bvh_mw
                                   @ hips_bone.matrix_local).to_translation()

        return Knochenplan(conj_pairs, tgt_to_src, aim_levels, hips_src,
                           hips_rest_world, Rokokoknochen.UEBERSPRUNGEN,
                           set(Rokokoknochen.ARME) | set(fingerziele))

    @staticmethod
    def armzwang_setzen(rig, bvh_rig, plan):
        u"""`COPY_ROTATION` im Weltraum fuer Arme und Finger.

        Gibt [(Rig-Name, Name der Zwangsbedingung)] zurueck — genau das,
        was `armzwang_loesen` nach dem Backen wieder braucht.
        """
        gesetzt = []
        for tgt_name in plan.constraint_bones:
            src_name = plan.tgt_to_src.get(tgt_name)
            if not src_name:
                continue
            pb_tgt = rig.pose.bones.get(tgt_name)
            pb_src = bvh_rig.pose.bones.get(src_name)
            if not pb_tgt or not pb_src:
                continue
            c = pb_tgt.constraints.new('COPY_ROTATION')
            c.name = "_rt_arm_test"
            c.target = bvh_rig
            c.subtarget = src_name
            c.target_space = 'WORLD'
            c.owner_space = 'WORLD'
            c.influence = 1.0
            gesetzt.append((tgt_name, c.name))

        n_arm = sum(1 for t, _ in gesetzt if t in Rokokoknochen.ARME)
        logger.info("%s arm + %s finger COPY_ROTATION constraints added",
                    n_arm, len(gesetzt) - n_arm)
        return gesetzt

    @staticmethod
    def armzwang_loesen(rig, gesetzt):
        u"""Nach dem Backen wieder abnehmen — sonst wirken sie doppelt."""
        for tgt_name, c_name in gesetzt:
            pb = rig.pose.bones.get(tgt_name)
            if not pb:
                continue
            c = pb.constraints.get(c_name)
            if c:
                pb.constraints.remove(c)
