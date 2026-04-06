# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class EkTypeRequest(models.Model):
    _inherit = 'ek.l10n.type.model.mixin'

    change_state_travel_after_confirm = fields.Selection(
        selection=[
            ("anotification", "Arrival Notification"),
            ("arribo", "Arribo"),
            ("inspection", "Inspection/Capacity"),
            ("transfer", "Transfer"),
            ("desconsolidation", "Desconsolidation"),
            ("return", "Return Container"),
        ],
        string="Auto Change State",
        copy=True,
    )

    use_in_regimen_60 = fields.Boolean(
        string="Use in Regimen 60",
                copy=True,

    )



    regime = fields.Selection(
        selection=[
            ("21", "21"),
            ("60", "60"),
            ("61", "61"),
            ("70", "70"),

        ],        copy=True, string="Régimen",

    )

    has_bl_import = fields.Boolean(
        string="Has BL Import",
    )
    has_bl_export = fields.Boolean(
        string="Has BL Export",
    )    

    @api.constrains('has_bl_import', 'has_bl_export')
    def check_bl_import_export(self):
        if self.has_bl_import and self.has_bl_export:
            raise ValidationError("Solo puede seleccionar uno de los campos 'Has BL Import' o 'Has BL Export'")


    sequence_bl_import = fields.Many2one("ir.sequence", string="Sequence Import", required=False)
    sequence_bl_export = fields.Many2one("ir.sequence", string="Sequence Export", required=False)

    @api.onchange("regime")
    def onchange_regime(self):
        self.use_in_regimen_60 = False
        self.use_in_regimen_61 = False
        self.use_in_regimen_70 = False

        if self.regime == "60":
            self.use_in_regimen_60 = True
        elif self.regime == "61":
            self.use_in_regimen_61 = True
        elif self.regime == "70":
            self.use_in_regimen_70 = True







            

