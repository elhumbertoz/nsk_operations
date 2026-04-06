# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class EkShipRegistration(models.Model):
    _inherit = 'ek.ship.registration'

    def action_open_documents_container(self):
        self.ensure_one()
        return {
            "name": _("Containers"),
            "type": "ir.actions.act_window",
            "res_model": "ek.boats.information",
            "view_mode": "tree,form",
            "context": {
                "default_ship_name_id": self.id,
                "default_fuel": self.fuel,
                "default_fuel_uom" : self.fuel_uom.id,
                "default_gasoline": self.gasoline,
                "default_gasoline_uom": self.gasoline_uom.id,
                "default_water": self.water,
                "default_water_uom": self.water_uom.id,
                'form_view_ref': 'ek_l10n_shipping_operations_charging_regimes.view_ek_boats_information_regimens_form',
                'tree_view_ref': 'ek_l10n_shipping_operations.ek_boats_information_tree',
            },
            "domain": [("ship_name_id", "in", self.ids)],
            "target": "current",
        }

