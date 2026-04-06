# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class EkPurchaseReimbursementWizard(models.TransientModel):
    _inherit = 'ek.purchase.reimbursement.wizard'

    def aditional_domain(self):
        self.ensure_one()
        if not self.invoice_id.journey_crew_id or not self.invoice_id.ship_name_id:
            raise UserError('Antes debe seleccionar un viaje y un buque')
        return [
            ('invoice_ids.journey_crew_id', '=', self.invoice_id.journey_crew_id.id),
            ('invoice_ids.ship_name_id', '=', self.invoice_id.ship_name_id.id)
        ]

class EkMoveReimbursementWizard(models.TransientModel):
    _inherit = 'ek.account.move.reimbursement.wizard'

    def aditional_domain(self):
        self.ensure_one()
        if not self.invoice_id.journey_crew_id or not self.invoice_id.ship_name_id:
            raise UserError('Antes debe seleccionar un viaje y un buque')
        return [
            ('journey_crew_id', '=', self.invoice_id.journey_crew_id.id),
            ('ship_name_id', '=', self.invoice_id.ship_name_id.id)
        ]
