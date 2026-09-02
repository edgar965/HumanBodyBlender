# SPDX-License-Identifier: GPL-3.0-or-later
# -*- coding: utf-8 -*-
u"""Rig- und Action-Helfer, die animation.py und retarget.py teilen.

DER RING (01.09.2026)
=====================
`retarget.py` holte sechs Helfer aus `animation.py`, und `animation.py`
holte sich `retarget` in Zeile 1718 zurueck — ganz am Dateiende, mit
einem `# noqa: E402` und dem Kommentar::

    # Retarget module (imported late to avoid circular dependency)

Ein Import am Dateiende ist keine Loesung, sondern die Stelle, an der
ein Ring sichtbar wird. Er haelt nur, solange niemand oben etwas
braucht, was unten steht — und beim naechsten Aufteilen faellt er um.

Die sechs Helfer haengen an keinem der beiden Module: Sie bekommen ein
Rig oder einen Pfad und geben etwas zurueck. Hier stehen sie einmal,
beide importieren sie, und der Ring ist weg.
"""
import logging

logger = logging.getLogger(__name__)


class Rigaktionen:
    u"""Die frueheren Modulfunktionen, gebuendelt."""

    @staticmethod
    def _parse_bvh_info(bvh_path):
        """Read Frames count and Frame Time from BVH header.

        Returns (fps, n_frames).
        """
        n_frames = 0
        fps = 120
        with open(bvh_path, 'r') as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith('Frames:'):
                    n_frames = int(stripped.split(':')[1])
                elif 'Frame Time' in stripped:
                    parts = stripped.split(':')
                    if len(parts) >= 2:
                        ft = float(parts[1].strip())
                        if ft > 0:
                            fps = round(1.0 / ft)
                    break
        return fps, n_frames

    @staticmethod
    def _rig_height(rig):
        """Height of armature (rest pose) from lowest to highest bone endpoint."""
        bones = rig.data.bones
        if not bones:
            return 1.7
        zs = []
        for b in bones:
            zs.append(b.head_local.z)
            zs.append(b.tail_local.z)
        return max(zs) - min(zs) if zs else 1.7

    @staticmethod
    def _set_fk_mode(rig):
        """Set IK/FK switches to 1.0 (FK mode) on Rigify rig."""
        count = 0
        for pb in rig.pose.bones:
            for key in list(pb.keys()):
                kl = key.lower()
                if 'ik_fk' in kl or 'fk_ik' in kl or key == 'IK_FK':
                    try:
                        pb[key] = 1.0
                        count += 1
                    # stumm gewollt: Laeuft ueber JEDEN Knochen und jeden
                    # Schluessel. Nicht jeder Wert ist schreibbar; ein Log je
                    # Fehlschlag waere ein Sturm.
                    except Exception:
                        pass
        logger.info("FK mode: %d IK/FK switches set", count)
        return count

    @staticmethod
    def _transfer_root_motion(rig):
        """Move torso location keyframes to root bone, zero torso location."""
        ad = rig.animation_data
        if not ad or not ad.action:
            return
        act = ad.action
        try:
            fcs = act.fcurves
            new_fc = act.fcurves.new
        except Exception:
            try:
                layer = act.layers[0]
                strip = layer.strips[0]
                slot = ad.action_slot
                cb = strip.channelbag(slot)
                fcs = cb.fcurves
                new_fc = cb.fcurves.new
            except Exception:
                # KEIN "stumm gewollt": Hier steigt die Funktion AUS. Die
                # Wurzelbewegung wird dann nicht uebertragen, und die
                # Animation laeuft auf der Stelle — sichtbar, aber ohne
                # jeden Hinweis, woran es lag.
                logger.warning("Root motion: keine Kurven zugaenglich "
                               "(weder klassisch noch als Layered Action)")
                return
        torso_loc = {}
        root_loc = {}
        for fc in fcs:
            if ('pose.bones["torso"]' in fc.data_path
                    and fc.data_path.endswith('location')):
                torso_loc[fc.array_index] = fc
            if ('pose.bones["root"]' in fc.data_path
                    and fc.data_path.endswith('location')):
                root_loc[fc.array_index] = fc
        if not torso_loc or root_loc:
            return
        for axis in range(3):
            src = torso_loc.get(axis)
            if not src:
                continue
            dst = new_fc(data_path='pose.bones["root"].location', index=axis)
            for kp in src.keyframe_points:
                dst.keyframe_points.insert(kp.co[0], kp.co[1])
            for kp in src.keyframe_points:
                kp.co[1] = 0.0
                kp.handle_left[1] = 0.0
                kp.handle_right[1] = 0.0
        logger.info("Root motion transferred torso -> root (%d axes)",
                    len(torso_loc))

    @staticmethod
    def _assign_action(rig, act):
        """Assign action to rig with proper Blender 5.0 slot binding + FK mode."""
        if not rig or not act:
            return
        if not rig.animation_data:
            rig.animation_data_create()
        rig.animation_data.action = act
        # Blender 5.0 layered actions: rebind slot to target rig
        if hasattr(act, 'slots') and hasattr(rig.animation_data, 'action_slot') and act.slots:
            slot = act.slots[0]
            rig_id = f"OB{rig.name}"
            if hasattr(slot, 'identifier') and slot.identifier != rig_id:
                try:
                    slot.identifier = rig_id
                # stumm gewollt: Die Kennung ist in manchen Faellen
                # schreibgeschuetzt. Die Zuweisung darunter wirkt trotzdem.
                except Exception:
                    pass
            rig.animation_data.action_slot = slot
        # Ensure FK mode so animated FK bones drive DEF bones
        Rigaktionen._set_fk_mode(rig)

    @staticmethod
    def _get_action_fcurves(act):
        """Get fcurves from action, compatible with Blender 4.x and 5.0+."""
        if hasattr(act, 'fcurves') and act.fcurves is not None:
            try:
                len(act.fcurves)
                return act.fcurves
            # stumm gewollt: Die API-Weiche selbst: Wirft len(), ist es eine
            # Layered Action und der Weg darunter greift.
            except Exception:
                pass
        # Blender 5.0: layered actions
        if act.layers:
            strip = act.layers[0].strips[0]
            for slot in act.slots:
                bag = strip.channelbag(slot, ensure=False)
                if bag:
                    return bag.fcurves
        return []
