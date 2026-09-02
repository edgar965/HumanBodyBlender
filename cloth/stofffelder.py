# -*- coding: utf-8 -*-
import logging
from ..cloth.modifikatoren import Modifikatoren
logger = logging.getLogger(__name__)


class Stofffelder:
    u"""Die frueheren Modulfunktionen, gebuendelt."""

    @staticmethod
    def _on_setting_update(self, context):
        Modifikatoren._sync_modifier_settings(context)
